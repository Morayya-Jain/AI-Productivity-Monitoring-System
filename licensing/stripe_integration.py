"""
Stripe Integration for BrainDock.

Handles Stripe Checkout session creation, payment verification,
and promo code handling.
"""

import logging
import webbrowser
from typing import Optional, Dict, Any, Tuple

logger = logging.getLogger(__name__)

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
            return None, error_msg
        except Exception as e:
            error_msg = str(e)
            logger.error(f"Error creating checkout session: {error_msg}")
            return None, error_msg
    
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
        
        try:
            webbrowser.open(checkout_url)
            logger.info("Opened Stripe checkout in browser")
            return session_id, None
        except Exception as e:
            error_msg = f"Failed to open browser: {e}"
            logger.warning(error_msg)
            # Still return session_id - user can manually navigate
            return session_id, f"Browser failed to open. Please visit: {checkout_url}"
    
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
