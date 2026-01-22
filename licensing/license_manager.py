"""
License Manager for BrainDock.

Handles license validation, storage, and verification.
Supports Stripe payments and license keys as activation methods.
"""

import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


class LicenseManager:
    """
    Manages BrainDock license state.
    
    Handles checking license validity, saving license data,
    validating license keys, and verifying Stripe payments.
    """
    
    # License types
    LICENSE_TYPE_STRIPE = "stripe_payment"
    LICENSE_TYPE_KEY = "license_key"
    LICENSE_TYPE_PROMO = "promo_code"
    
    def __init__(self, license_file: Path, license_keys_file: Optional[Path] = None):
        """
        Initialize the license manager.
        
        Args:
            license_file: Path to the license data JSON file.
            license_keys_file: Optional path to hashed license keys file.
        """
        self.license_file = license_file
        self.license_keys_file = license_keys_file
        self.data = self._load_data()
        self._license_keys_cache: Optional[set] = None
        
    def _load_data(self) -> Dict[str, Any]:
        """
        Load license data from JSON file.
        
        Returns:
            Dict containing license data.
        """
        if self.license_file.exists():
            try:
                with open(self.license_file, 'r') as f:
                    data = json.load(f)
                    # Verify checksum if present
                    if not self._verify_checksum(data):
                        logger.warning("License file checksum mismatch - possible tampering")
                        return self._default_data()
                    logger.debug(f"Loaded license data: licensed={data.get('licensed', False)}")
                    return data
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load license data: {e}")
        
        return self._default_data()
    
    def _default_data(self) -> Dict[str, Any]:
        """Return default license data for unlicensed state."""
        return {
            "licensed": False,
            "license_type": None,
            "stripe_session_id": None,
            "stripe_payment_intent": None,
            "license_key": None,
            "activated_at": None,
            "email": None,
            "checksum": None
        }
    
    def _calculate_checksum(self, data: Dict[str, Any]) -> str:
        """
        Calculate checksum for license data integrity.
        
        Args:
            data: License data dictionary.
            
        Returns:
            SHA256 checksum string.
        """
        # Create a copy without the checksum field
        data_copy = {k: v for k, v in data.items() if k != "checksum"}
        # Sort keys for consistent hashing
        data_str = json.dumps(data_copy, sort_keys=True)
        return hashlib.sha256(data_str.encode()).hexdigest()[:16]
    
    def _verify_checksum(self, data: Dict[str, Any]) -> bool:
        """
        Verify the checksum of license data.
        
        Args:
            data: License data dictionary.
            
        Returns:
            True if checksum is valid or not present, False if mismatch.
        """
        stored_checksum = data.get("checksum")
        if not stored_checksum:
            return True  # No checksum = old format, accept it
        
        calculated = self._calculate_checksum(data)
        return stored_checksum == calculated
    
    def _save_data(self) -> None:
        """Save license data to JSON file with checksum."""
        try:
            # Ensure parent directory exists
            self.license_file.parent.mkdir(parents=True, exist_ok=True)
            
            # Add checksum before saving
            self.data["checksum"] = self._calculate_checksum(self.data)
            
            with open(self.license_file, 'w') as f:
                json.dump(self.data, f, indent=2)
            logger.debug("Saved license data")
        except IOError as e:
            logger.error(f"Failed to save license data: {e}")
    
    def is_licensed(self) -> bool:
        """
        Check if the app is licensed.
        
        Returns:
            True if licensed, False otherwise.
        """
        return self.data.get("licensed", False)
    
    def get_license_type(self) -> Optional[str]:
        """
        Get the type of license activation.
        
        Returns:
            License type string or None if not licensed.
        """
        return self.data.get("license_type")
    
    def get_license_info(self) -> Dict[str, Any]:
        """
        Get license information for display.
        
        Returns:
            Dict with license details.
        """
        return {
            "licensed": self.data.get("licensed", False),
            "type": self.data.get("license_type"),
            "activated_at": self.data.get("activated_at"),
            "email": self.data.get("email")
        }
    
    def activate_with_stripe(
        self,
        session_id: str,
        payment_intent: Optional[str] = None,
        email: Optional[str] = None
    ) -> bool:
        """
        Activate license after successful Stripe payment.
        
        Args:
            session_id: Stripe Checkout session ID.
            payment_intent: Optional Stripe payment intent ID.
            email: Optional customer email from Stripe.
            
        Returns:
            True if activation successful.
        """
        self.data = {
            "licensed": True,
            "license_type": self.LICENSE_TYPE_STRIPE,
            "stripe_session_id": session_id,
            "stripe_payment_intent": payment_intent,
            "license_key": None,
            "activated_at": datetime.now().isoformat(),
            "email": email,
            "checksum": None
        }
        self._save_data()
        logger.info(f"License activated via Stripe payment (session: {session_id[:20]}...)")
        return True
    
    def activate_with_key(self, license_key: str) -> bool:
        """
        Activate license using a license key.
        
        Args:
            license_key: The license key to validate and activate.
            
        Returns:
            True if key is valid and activation successful, False otherwise.
        """
        if not self.validate_license_key(license_key):
            logger.warning(f"Invalid license key attempted")
            return False
        
        # Store the normalized key
        normalized_key = license_key.strip().upper()
        
        self.data = {
            "licensed": True,
            "license_type": self.LICENSE_TYPE_KEY,
            "stripe_session_id": None,
            "stripe_payment_intent": None,
            "license_key": normalized_key,
            "activated_at": datetime.now().isoformat(),
            "email": None,
            "checksum": None
        }
        self._save_data()
        logger.info("License activated via license key")
        return True
    
    def activate_with_promo(
        self,
        session_id: str,
        promo_code: str,
        email: Optional[str] = None
    ) -> bool:
        """
        Activate license after successful promo code redemption via Stripe.
        
        Args:
            session_id: Stripe Checkout session ID.
            promo_code: The promo code that was used.
            email: Optional customer email from Stripe.
            
        Returns:
            True if activation successful.
        """
        self.data = {
            "licensed": True,
            "license_type": self.LICENSE_TYPE_PROMO,
            "stripe_session_id": session_id,
            "stripe_payment_intent": None,
            "license_key": promo_code,  # Store the promo code used
            "activated_at": datetime.now().isoformat(),
            "email": email,
            "checksum": None
        }
        self._save_data()
        logger.info(f"License activated via promo code")
        return True
    
    def _hash_key(self, key: str) -> str:
        """
        Hash a license key using SHA256.
        
        Args:
            key: Plain text license key.
            
        Returns:
            SHA256 hash of the key.
        """
        # Normalize: strip whitespace and convert to uppercase
        normalized = key.strip().upper()
        return hashlib.sha256(normalized.encode()).hexdigest()
    
    def _load_license_keys(self) -> set:
        """
        Load valid license keys from file.
        
        Returns:
            Set of valid license keys (plain text, normalized to uppercase).
        """
        if self._license_keys_cache is not None:
            return self._license_keys_cache
        
        self._license_keys_cache = set()
        
        if self.license_keys_file and self.license_keys_file.exists():
            try:
                with open(self.license_keys_file, 'r') as f:
                    data = json.load(f)
                    # New format: {"keys": ["KEY1", "KEY2", ...]}
                    if isinstance(data, dict) and "keys" in data:
                        for key in data["keys"]:
                            # Normalize to uppercase for comparison
                            self._license_keys_cache.add(key.strip().upper())
                    # Legacy list format
                    elif isinstance(data, list):
                        for key in data:
                            self._license_keys_cache.add(key.strip().upper())
                logger.debug(f"Loaded {len(self._license_keys_cache)} valid license keys")
            except (json.JSONDecodeError, IOError) as e:
                logger.warning(f"Failed to load license keys: {e}")
        
        return self._license_keys_cache
    
    def validate_license_key(self, key: str) -> bool:
        """
        Validate a license key against the known valid keys.
        
        Args:
            key: The license key to validate.
            
        Returns:
            True if key is valid, False otherwise.
        """
        # Normalize input key to uppercase
        normalized_key = key.strip().upper()
        valid_keys = self._load_license_keys()
        return normalized_key in valid_keys
    
    def revoke_license(self) -> None:
        """Revoke the current license (reset to unlicensed state)."""
        self.data = self._default_data()
        self._save_data()
        logger.info("License revoked")
    
    def get_activation_date(self) -> Optional[datetime]:
        """
        Get the date when the license was activated.
        
        Returns:
            Datetime of activation or None if not licensed.
        """
        activated_at = self.data.get("activated_at")
        if activated_at:
            try:
                return datetime.fromisoformat(activated_at)
            except ValueError:
                pass
        return None


# Global instance for easy access
_license_manager_instance: Optional[LicenseManager] = None


def get_license_manager() -> LicenseManager:
    """
    Get the global LicenseManager instance.
    
    Returns:
        Singleton LicenseManager instance.
    """
    global _license_manager_instance
    if _license_manager_instance is None:
        # Import config here to avoid circular imports
        import config
        _license_manager_instance = LicenseManager(
            license_file=config.LICENSE_FILE,
            license_keys_file=config.LICENSE_KEYS_FILE
        )
    return _license_manager_instance


def reset_license_manager() -> None:
    """Reset the global license manager instance (useful for testing)."""
    global _license_manager_instance
    _license_manager_instance = None
