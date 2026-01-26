"""
Stripe Integration for BrainDock.

Handles Stripe Checkout session creation, payment verification,
and promo code handling.
"""

import logging
import os
import subprocess
import sys
import traceback
import webbrowser
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

# Fix SSL certificates for bundled apps (PyInstaller)
# This must be done BEFORE importing stripe
def _fix_ssl_certificates():
    """
    Fix SSL certificate paths for PyInstaller bundles.
    
    PyInstaller's certifi hook should handle this automatically, but we set
    environment variables as a backup for libraries that don't use certifi directly.
    Works on both macOS and Windows.
    """
    cert_path = None
    
    # Try certifi module first - PyInstaller's hook patches this to work in bundles
    try:
        import certifi
        cert_path = certifi.where()
        if os.path.exists(cert_path):
            logger.debug(f"Using certifi SSL certificates: {cert_path}")
        else:
            logger.warning(f"certifi.where() returned non-existent path: {cert_path}")
            cert_path = None
    except ImportError:
        logger.debug("certifi not available")
    except Exception as e:
        logger.warning(f"Error getting certifi path: {e}")
    
    # Platform-specific fallback locations
    if not cert_path:
        if sys.platform == "darwin":
            # macOS certificate locations
            macos_certs = [
                '/etc/ssl/cert.pem',
                '/private/etc/ssl/cert.pem',
                '/usr/local/etc/openssl/cert.pem',
                '/usr/local/etc/openssl@1.1/cert.pem',
                '/opt/homebrew/etc/openssl/cert.pem',
                '/opt/homebrew/etc/openssl@3/cert.pem',
            ]
            for path in macos_certs:
                if os.path.exists(path):
                    cert_path = path
                    logger.debug(f"Using macOS system SSL certificates: {cert_path}")
                    break
        
        elif sys.platform == "win32":
            # Windows - try ssl module's default paths
            try:
                import ssl
                default_paths = ssl.get_default_verify_paths()
                if default_paths.cafile and os.path.exists(default_paths.cafile):
                    cert_path = default_paths.cafile
                    logger.debug(f"Using Windows SSL default certificates: {cert_path}")
            except Exception:
                pass
    
    if cert_path:
        os.environ['SSL_CERT_FILE'] = cert_path
        os.environ['REQUESTS_CA_BUNDLE'] = cert_path
        os.environ['CURL_CA_BUNDLE'] = cert_path
        logger.info(f"SSL certificates configured: {cert_path}")
    else:
        # Log warning but don't fail - some systems use built-in certificate stores
        logger.warning("Could not find SSL certificates - relying on system defaults")

# Apply SSL fix before importing stripe
_fix_ssl_certificates()

# Stripe SDK - imported conditionally to handle missing dependency gracefully
try:
    import stripe
    STRIPE_AVAILABLE = True
except ImportError:
    STRIPE_AVAILABLE = False
    logger.warning("Stripe SDK not installed. Run: pip install stripe")


class StripeIntegration:
    """
    Handles Stripe API interactions for payment processing.
    
    Provides methods to create checkout sessions, verify payments,
    and handle promo codes.
    """
    
    def __init__(self, secret_key: str, product_price_id: str):
        """
        Initialize Stripe integration.
        
        Args:
            secret_key: Stripe secret API key.
            product_price_id: Stripe Price ID for the product.
        """
        self.secret_key = secret_key
        self.product_price_id = product_price_id
        self._initialized = False
        
        if STRIPE_AVAILABLE and secret_key:
            stripe.api_key = secret_key
            self._initialized = True
            logger.debug("Stripe integration initialized")
        elif not STRIPE_AVAILABLE:
            logger.error("Stripe SDK not available")
        elif not secret_key:
            logger.error("Stripe secret key not configured")
    
    def is_available(self) -> bool:
        """
        Check if Stripe integration is available and configured.
        
        Returns:
            True if Stripe is ready to use.
        """
        return self._initialized
    
    def create_checkout_session(
        self,
        success_url: str = "https://stripe.com",
        cancel_url: str = "https://stripe.com",
        promo_code: Optional[str] = None,
        customer_email: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create a Stripe Checkout session.
        
        Args:
            success_url: URL to redirect after successful payment.
            cancel_url: URL to redirect if payment is cancelled.
            promo_code: Optional promo code to apply.
            customer_email: Optional pre-filled customer email.
            
        Returns:
            Tuple of (session_id, checkout_url) or (None, error_message) on failure.
        """
        if not self._initialized:
            return None, "Stripe not configured"
        
        try:
            # Import config for terms requirement setting
            import config
            
            # Build session parameters
            session_params = {
                "payment_method_types": ["card"],
                "line_items": [{
                    "price": self.product_price_id,
                    "quantity": 1,
                }],
                "mode": "payment",
                "success_url": success_url + "?session_id={CHECKOUT_SESSION_ID}",
                "cancel_url": cancel_url,
                "allow_promotion_codes": True,  # Allow users to enter promo codes
            }
            
            # Add Terms of Service consent if enabled (requires T&C URL in Stripe Dashboard)
            if config.STRIPE_REQUIRE_TERMS:
                session_params["consent_collection"] = {
                    "terms_of_service": "required"
                }
            
            # Add customer email if provided
            if customer_email:
                session_params["customer_email"] = customer_email
            
            # Apply specific promo code if provided
            if promo_code:
                # Look up the promotion code
                try:
                    promo_codes = stripe.PromotionCode.list(code=promo_code, active=True)
                    if promo_codes.data:
                        session_params["discounts"] = [{
                            "promotion_code": promo_codes.data[0].id
                        }]
                        # Remove allow_promotion_codes if applying a specific code
                        session_params.pop("allow_promotion_codes", None)
                except stripe.error.StripeError as e:
                    logger.warning(f"Failed to apply promo code: {e}")
                    # Continue without the promo code
            
            # Create the session
            session = stripe.checkout.Session.create(**session_params)
            
            logger.info(f"Created Stripe checkout session: {session.id[:20]}...")
            return session.id, session.url
            
        except stripe.error.StripeError as e:
            error_msg = str(e)
            logger.error(f"Stripe error creating checkout session: {error_msg}")
            logger.debug(f"Stripe error traceback: {traceback.format_exc()}")
            return None, f"Payment service error: {error_msg}"
        except FileNotFoundError as e:
            # This can happen if SSL certificates are not found or other file issues
            filename = getattr(e, 'filename', None) or 'unknown'
            error_msg = f"File not found: {filename} - {e}"
            logger.error(f"FileNotFoundError in checkout session: {error_msg}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            # Show actual error for debugging
            return None, f"Missing file: {filename}"
        except OSError as e:
            # Catch other OS errors (permissions, etc.)
            error_msg = f"OS error: {e}"
            logger.error(f"OSError in checkout session: {error_msg}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None, f"System error: {e}"
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error creating checkout session: {error_msg}")
            logger.error(f"Full traceback: {traceback.format_exc()}")
            return None, f"Error: {error_msg}"
    
    def verify_session(self, session_id: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Verify a Stripe Checkout session payment status.
        
        Args:
            session_id: The Stripe Checkout session ID to verify.
            
        Returns:
            Tuple of (is_paid, session_info) where session_info contains
            payment details or error information.
        """
        if not self._initialized:
            return False, {"error": "Stripe not configured"}
        
        try:
            # Retrieve the session
            session = stripe.checkout.Session.retrieve(session_id)
            
            # Check payment status
            is_paid = session.payment_status == "paid"
            
            info = {
                "session_id": session.id,
                "payment_status": session.payment_status,
                "payment_intent": session.payment_intent,
                "customer_email": session.customer_details.email if session.customer_details else None,
                "amount_total": session.amount_total,
                "currency": session.currency,
                "terms_accepted": session.consent.terms_of_service if session.consent else None,
            }
            
            if is_paid:
                logger.info(f"Session {session_id[:20]}... verified as paid")
            else:
                logger.warning(f"Session {session_id[:20]}... not paid (status: {session.payment_status})")
            
            return is_paid, info
            
        except stripe.error.InvalidRequestError as e:
            error_msg = f"Invalid session ID: {e}"
            logger.error(error_msg)
            return False, {"error": error_msg}
        except stripe.error.StripeError as e:
            error_msg = f"Stripe error: {e}"
            logger.error(error_msg)
            return False, {"error": error_msg}
        except Exception as e:
            error_msg = f"Error verifying session: {e}"
            logger.error(error_msg)
            return False, {"error": error_msg}
    
    def open_checkout(
        self,
        success_url: Optional[str] = None,
        cancel_url: Optional[str] = None,
        promo_code: Optional[str] = None,
        customer_email: Optional[str] = None
    ) -> Tuple[Optional[str], Optional[str]]:
        """
        Create a checkout session and open it in the default browser.
        
        Args:
            success_url: URL to redirect after successful payment.
            cancel_url: URL to redirect if payment is cancelled.
            promo_code: Optional promo code to apply.
            customer_email: Optional pre-filled customer email.
            
        Returns:
            Tuple of (session_id, error_message). Session ID is returned
            even if browser fails to open.
        """
        # Use provided URLs or defaults
        final_success_url = success_url if success_url else "https://stripe.com"
        final_cancel_url = cancel_url if cancel_url else "https://stripe.com"
        
        session_id, result = self.create_checkout_session(
            success_url=final_success_url,
            cancel_url=final_cancel_url,
            promo_code=promo_code,
            customer_email=customer_email
        )
        
        if not session_id:
            return None, result  # result contains error message
        
        # result contains the checkout URL
        checkout_url = result
        
        open_error = self._open_checkout_url(checkout_url)
        if open_error:
            return session_id, open_error
        
        logger.info("Opened Stripe checkout in browser")
        return session_id, None

    def _open_checkout_url(self, checkout_url: str) -> Optional[str]:
        """
        Open the checkout URL in the default browser with fallbacks.
        
        Uses multiple methods to ensure URL opens even in sandboxed/bundled apps.
        
        Args:
            checkout_url: The Stripe Checkout URL to open.
        
        Returns:
            None if opened successfully, otherwise an error message.
        """
        errors = []
        
        # Method 1: macOS - Use AppleScript via osascript (most reliable for bundled apps)
        if sys.platform == "darwin":
            try:
                # AppleScript command to open URL in default browser
                script = f'open location "{checkout_url}"'
                result = subprocess.run(
                    ["/usr/bin/osascript", "-e", script],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    logger.info("Opened URL via AppleScript")
                    return None
                else:
                    errors.append(f"AppleScript failed: {result.stderr}")
                    logger.warning(f"AppleScript failed: {result.stderr}")
            except Exception as e:
                errors.append(f"AppleScript error: {e}")
                logger.warning(f"AppleScript error: {e}")
            
            # Method 2: macOS - Use /usr/bin/open directly
            try:
                result = subprocess.run(
                    ["/usr/bin/open", checkout_url],
                    capture_output=True,
                    text=True,
                    timeout=10
                )
                if result.returncode == 0:
                    logger.info("Opened URL via /usr/bin/open")
                    return None
                else:
                    errors.append(f"/usr/bin/open failed: {result.stderr}")
                    logger.warning(f"/usr/bin/open failed: {result.stderr}")
            except Exception as e:
                errors.append(f"/usr/bin/open error: {e}")
                logger.warning(f"/usr/bin/open error: {e}")
        
        # Method 3: Windows - Multiple fallback approaches
        if sys.platform.startswith("win"):
            # Method 3a: os.startfile (most common)
            try:
                os.startfile(checkout_url)  # type: ignore[attr-defined]
                logger.info("Opened URL via os.startfile")
                return None
            except Exception as e:
                errors.append(f"Windows startfile error: {e}")
                logger.warning(f"Windows startfile error: {e}")
            
            # Method 3b: Use 'start' command via cmd.exe
            try:
                # 'start' command opens URL in default browser
                result = subprocess.run(
                    ['cmd', '/c', 'start', '', checkout_url],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    shell=False
                )
                if result.returncode == 0:
                    logger.info("Opened URL via cmd start")
                    return None
                else:
                    errors.append(f"cmd start failed: {result.stderr}")
                    logger.warning(f"cmd start failed: {result.stderr}")
            except Exception as e:
                errors.append(f"cmd start error: {e}")
                logger.warning(f"cmd start error: {e}")
            
            # Method 3c: Use PowerShell Start-Process
            try:
                result = subprocess.run(
                    ['powershell', '-Command', f'Start-Process "{checkout_url}"'],
                    capture_output=True,
                    text=True,
                    timeout=10,
                    shell=False
                )
                if result.returncode == 0:
                    logger.info("Opened URL via PowerShell")
                    return None
                else:
                    errors.append(f"PowerShell failed: {result.stderr}")
                    logger.warning(f"PowerShell failed: {result.stderr}")
            except Exception as e:
                errors.append(f"PowerShell error: {e}")
                logger.warning(f"PowerShell error: {e}")
        
        # Method 4: Linux
        if sys.platform.startswith("linux"):
            for cmd in ["/usr/bin/xdg-open", "/usr/bin/gio"]:
                if os.path.exists(cmd):
                    try:
                        args = [cmd, "open", checkout_url] if cmd.endswith("gio") else [cmd, checkout_url]
                        subprocess.Popen(args)
                        logger.info(f"Opened URL via {cmd}")
                        return None
                    except Exception as e:
                        errors.append(f"{cmd} error: {e}")
                        logger.warning(f"{cmd} error: {e}")
        
        # Method 5: Python webbrowser module (last resort)
        try:
            opened = webbrowser.open(checkout_url, new=2)
            if opened:
                logger.info("Opened URL via webbrowser module")
                return None
            errors.append("webbrowser.open returned False")
        except Exception as e:
            errors.append(f"webbrowser error: {e}")
            logger.warning(f"webbrowser error: {e}")
        
        # All methods failed
        error_details = "; ".join(errors) if errors else "Unknown error"
        logger.error(f"All browser open methods failed: {error_details}")
        return f"Could not open browser. Please copy this URL: {checkout_url}"
    
    def validate_promo_code(self, promo_code: str) -> Tuple[bool, Dict[str, Any]]:
        """
        Validate a promo code with Stripe.
        
        Args:
            promo_code: The promo code to validate.
            
        Returns:
            Tuple of (is_valid, promo_info) with discount details.
        """
        if not self._initialized:
            return False, {"error": "Stripe not configured"}
        
        try:
            # Look up the promotion code
            promo_codes = stripe.PromotionCode.list(code=promo_code, active=True)
            
            if not promo_codes.data:
                return False, {"error": "Invalid or expired promo code"}
            
            promo = promo_codes.data[0]
            coupon = promo.coupon
            
            info = {
                "code": promo_code,
                "promo_id": promo.id,
                "discount_type": "percent" if coupon.percent_off else "amount",
                "discount_value": coupon.percent_off or coupon.amount_off,
                "is_100_percent": coupon.percent_off == 100,
            }
            
            logger.info(f"Promo code '{promo_code}' validated successfully")
            return True, info
            
        except stripe.error.StripeError as e:
            error_msg = f"Stripe error: {e}"
            logger.error(error_msg)
            return False, {"error": error_msg}
        except Exception as e:
            error_msg = f"Error validating promo code: {e}"
            logger.error(error_msg)
            return False, {"error": error_msg}


# Global instance
_stripe_instance: Optional[StripeIntegration] = None


def get_stripe_integration() -> StripeIntegration:
    """
    Get the global StripeIntegration instance.
    
    Returns:
        Singleton StripeIntegration instance.
    """
    global _stripe_instance
    if _stripe_instance is None:
        # Import config here to avoid circular imports
        import config
        _stripe_instance = StripeIntegration(
            secret_key=config.STRIPE_SECRET_KEY,
            product_price_id=config.STRIPE_PRICE_ID
        )
    return _stripe_instance


def reset_stripe_integration() -> None:
    """Reset the global Stripe integration instance (useful for testing)."""
    global _stripe_instance
    _stripe_instance = None
