"""
Browser Stealth Framework
~~~~~~~~~~~~~~~~~~~~~~~~~

Anti-detect browser profile management with comprehensive fingerprint spoofing,
human-like interaction primitives, and validation against detection sites.

Usage::

    from browser_stealth import ProfileManager, StealthBrowser, HumanSimulator, StealthValidator

    # Create a profile
    pm = ProfileManager()
    profile = pm.create_profile(region="US")
    pm.save_profile(profile)

    # Launch stealth browser
    browser = StealthBrowser(profile)
    page = await browser.connect_direct(headless=False)

    # Interact like a human
    human = HumanSimulator(page)
    await human.type_text("#search", "hello world")
    await human.click("#submit")

    # Validate stealth
    validator = StealthValidator(page)
    results = await validator.validate_all()

    await browser.close()
"""

from .profile_manager import BrowserProfile, ProfileManager
from .stealth_browser import StealthBrowser
from .human_behavior import HumanSimulator
from .validate_stealth import StealthValidator, ValidationResult, run_validation

__all__ = [
    "BrowserProfile",
    "ProfileManager",
    "StealthBrowser",
    "HumanSimulator",
    "StealthValidator",
    "ValidationResult",
    "run_validation",
]

__version__ = "1.0.0"
