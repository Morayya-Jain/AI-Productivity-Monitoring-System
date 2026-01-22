"""
Licensing module for BrainDock.

Handles license validation, Stripe payment integration, and license key management.
"""

from licensing.license_manager import LicenseManager, get_license_manager

__all__ = ["LicenseManager", "get_license_manager"]
