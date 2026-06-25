"""X/Twitter signup automation flow."""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from services.browser_stealth import HumanSimulator, StealthBrowser
from services.captcha_solver import CAPTCHASolver
from services.email_verification import EmailVerificationClient
from services.phone_verification import PhoneVerificationService

from .profile_generator import AccountIdentity

logger = logging.getLogger(__name__)

# Twitter/X Arkose Labs public key (FunCaptcha)
ARKOSE_PUBLIC_KEY = "2CB16598-CB82-4CF7-B332-5990DB66F3AB"
SIGNUP_URL = "https://x.com/i/flow/signup"


@dataclass
class SignupResult:
    """Result of a signup attempt."""

    success: bool
    account_id: str
    identity: AccountIdentity
    auth_token: Optional[str] = None
    ct0: Optional[str] = None
    twid: Optional[str] = None
    username: Optional[str] = None
    error: Optional[str] = None
    stage_reached: str = "init"


class SignupFlow:
    """Execute the full X/Twitter signup flow using stealth browser and human simulation."""

    def __init__(
        self,
        browser: StealthBrowser,
        human: HumanSimulator,
        email_client: EmailVerificationClient,
        captcha_solver: CAPTCHASolver,
        phone_service: Optional[PhoneVerificationService] = None,
    ):
        self.browser = browser
        self.human = human
        self.email_client = email_client
        self.captcha_solver = captcha_solver
        self.phone_service = phone_service
        self.page = None

    async def _find_element(self, page: Any, selectors: List[str], timeout: int = 5000) -> Any:
        """Try multiple selectors, return first match.

        Provides resilience against selector changes by trying multiple
        strategies (data-testid, aria-label, CSS selectors, text content).
        """
        for sel in selectors:
            try:
                el = await page.wait_for_selector(sel, timeout=timeout)
                if el:
                    return el
            except Exception:
                continue
        return None

    async def _click_next_button(self, page: Any) -> bool:
        """Find and click the Next button using multiple strategies."""
        next_selectors = [
            'button[data-testid="ocfSignupNextLink"]',
            'button[data-testid="NextButton"]',
            'div[role="button"]:has-text("Next")',
            'button:has-text("Next")',
            'span:has-text("Next")',
        ]
        el = await self._find_element(page, next_selectors, timeout=8000)
        if el:
            await el.click()
            # Wait for navigation/transition
            await asyncio.sleep(2)
            return True

        # Last resort: evaluate JS to find by text content
        try:
            clicked = await page.evaluate("""
                () => {
                    const buttons = [...document.querySelectorAll('button, div[role="button"]')];
                    const next = buttons.find(b => b.textContent.trim() === 'Next');
                    if (next) { next.click(); return true; }
                    return false;
                }
            """)
            if clicked:
                await asyncio.sleep(2)
                return True
        except Exception:
            pass

        return False

    async def _fill_dob(self, page: Any, identity: AccountIdentity) -> None:
        """Fill date of birth dropdowns."""
        dob = identity.dob_parts

        # Month dropdown
        month_selectors = [
            'select[id="SELECTOR_1"]',
            'select[name="month"]',
            'select[aria-label="Month"]',
        ]
        month_el = await self._find_element(page, month_selectors)
        if month_el:
            await self.human.select_option(month_el, str(dob["month"]))

        await asyncio.sleep(0.5)

        # Day dropdown
        day_selectors = [
            'select[id="SELECTOR_2"]',
            'select[name="day"]',
            'select[aria-label="Day"]',
        ]
        day_el = await self._find_element(page, day_selectors)
        if day_el:
            await self.human.select_option(day_el, str(dob["day"]))

        await asyncio.sleep(0.5)

        # Year dropdown
        year_selectors = [
            'select[id="SELECTOR_3"]',
            'select[name="year"]',
            'select[aria-label="Year"]',
        ]
        year_el = await self._find_element(page, year_selectors)
        if year_el:
            await self.human.select_option(year_el, str(dob["year"]))

    async def _check_for_captcha(self, page: Any) -> bool:
        """Check if Arkose/FunCaptcha is present on the page."""
        captcha_indicators = [
            'iframe[src*="arkoselabs"]',
            'iframe[src*="funcaptcha"]',
            '#arkoseFrame',
            '[data-testid="arkose_iframe"]',
            'iframe[title*="arkose"]',
        ]
        el = await self._find_element(page, captcha_indicators, timeout=3000)
        return el is not None

    async def _handle_captcha(self, page: Any) -> bool:
        """Solve Arkose CAPTCHA and inject token."""
        logger.info("CAPTCHA detected - solving via captcha_solver")
        try:
            token = await self.captcha_solver.solve_arkose(
                public_key=ARKOSE_PUBLIC_KEY,
                page_url=SIGNUP_URL,
            )
            if not token:
                logger.error("CAPTCHA solver returned empty token")
                return False

            # Inject the Arkose token
            await page.evaluate(
                """(token) => {
                    // Try multiple injection methods
                    if (typeof window.funCaptchaCallback === 'function') {
                        window.funCaptchaCallback(token);
                    }
                    // Dispatch custom event
                    const event = new CustomEvent('arkose-token', { detail: token });
                    document.dispatchEvent(event);
                    // Try setting the hidden input
                    const input = document.querySelector('input[name="arkose_token"]');
                    if (input) {
                        input.value = token;
                        input.dispatchEvent(new Event('input', { bubbles: true }));
                    }
                }""",
                token,
            )
            logger.info("CAPTCHA token injected successfully")
            await asyncio.sleep(2)
            return True

        except Exception as e:
            logger.error(f"CAPTCHA handling failed: {e}")
            return False

    async def _check_for_phone_verification(self, page: Any) -> bool:
        """Check if phone verification is being requested."""
        phone_indicators = [
            'input[name="phone_number"]',
            'input[autocomplete="tel"]',
            '[data-testid="ocfEnterPhoneLink"]',
            'text="phone number"',
        ]
        el = await self._find_element(page, phone_indicators, timeout=3000)
        return el is not None

    async def _handle_phone_verification(self, page: Any, identity: AccountIdentity) -> bool:
        """Handle phone verification challenge."""
        if not self.phone_service:
            logger.error("Phone verification required but no phone service configured")
            return False

        rental = None
        try:
            # Rent a number
            rental = await self.phone_service.rent_number(
                service="twitter",
                country=identity.region,
            )
            logger.info(f"Rented phone number: ***{rental.number[-4:]}")

            # Type the phone number
            phone_selectors = [
                'input[name="phone_number"]',
                'input[autocomplete="tel"]',
                'input[type="tel"]',
            ]
            phone_input = await self._find_element(page, phone_selectors)
            if phone_input:
                await self.human.type_text(phone_input, rental.number)
            else:
                logger.error("Could not find phone number input")
                await self.phone_service.release_number(rental, success=False)
                return False

            # Click Next/Send code
            await self._click_next_button(page)

            # Wait for SMS code
            try:
                code = await self.phone_service.wait_for_code(rental, timeout=180)
            except (TimeoutError, ConnectionError, OSError) as e:
                code = None
                logger.warning(f"Phone code wait failed: {type(e).__name__}")
            if not code:
                logger.error("No SMS code received within timeout")
                await self.phone_service.release_number(rental, success=False)
                return False

            logger.info("SMS code received, entering...")

            # Find code input and type
            code_selectors = [
                'input[name="verfication_code"]',
                'input[name="verification_code"]',
                'input[data-testid="ocfEnterTextTextInput"]',
                'input[autocomplete="one-time-code"]',
            ]
            code_input = await self._find_element(page, code_selectors)
            if code_input:
                await self.human.type_text(code_input, code)
            else:
                logger.error("Could not find SMS code input")
                await self.phone_service.release_number(rental, success=False)
                return False

            # Confirm
            await self._click_next_button(page)
            await self.phone_service.release_number(rental, success=True)
            logger.info("Phone verification completed")
            return True

        except Exception as e:
            logger.error(f"Phone verification failed: {type(e).__name__}")
            if rental:
                try:
                    await self.phone_service.release_number(rental, success=False)
                except Exception:
                    logger.warning("Failed to release phone rental during error cleanup")
            return False

    async def _extract_tokens(self, page: Any) -> Dict[str, Optional[str]]:
        """Extract auth cookies from browser."""
        cookies = await self.browser.get_cookies()
        auth_token = next((c["value"] for c in cookies if c["name"] == "auth_token"), None)
        ct0 = next((c["value"] for c in cookies if c["name"] == "ct0"), None)
        twid = next((c["value"] for c in cookies if c["name"] == "twid"), None)
        return {"auth_token": auth_token, "ct0": ct0, "twid": twid}

    async def execute(self, identity: AccountIdentity) -> SignupResult:
        """Full signup flow. Returns result with extracted tokens on success."""
        result = SignupResult(
            success=False,
            account_id=identity.profile_id,
            identity=identity,
        )

        try:
            page = self.browser.page
            self.page = page

            # ── Stage 1: Navigate to signup ──
            result.stage_reached = "navigate"
            logger.info(f"[{identity.profile_id}] Navigating to {SIGNUP_URL}")
            await self.browser.goto(SIGNUP_URL)

            # ── Stage 2: Wait for page load ──
            result.stage_reached = "page_load"
            await self.human.wait_and_observe(2, 4)

            # ── Stage 3: Fill name ──
            result.stage_reached = "fill_name"
            logger.info(f"[{identity.profile_id}] Filling name")
            name_selectors = [
                'input[name="name"]',
                'input[autocomplete="name"]',
                'input[data-testid="name"]',
            ]
            name_el = await self._find_element(page, name_selectors)
            if not name_el:
                result.error = "Could not find name input"
                return result
            await self.human.type_text(name_el, identity.full_name)
            await asyncio.sleep(0.5)

            # ── Stage 4: Fill email ──
            result.stage_reached = "fill_email"
            logger.info(f"[{identity.profile_id}] Filling email: ***@{identity.email.split('@')[-1]}")
            email_selectors = [
                'input[name="email"]',
                'input[autocomplete="email"]',
                'input[type="email"]',
                'input[data-testid="email"]',
            ]
            email_el = await self._find_element(page, email_selectors)
            if not email_el:
                result.error = "Could not find email input"
                return result
            await self.human.type_text(email_el, identity.email)
            await asyncio.sleep(0.5)

            # ── Stage 5: Fill DOB ──
            result.stage_reached = "fill_dob"
            logger.info(f"[{identity.profile_id}] Filling DOB")
            await self._fill_dob(page, identity)
            await asyncio.sleep(1)

            # ── Stage 6: Click Next ──
            result.stage_reached = "click_next_1"
            logger.info(f"[{identity.profile_id}] Clicking Next")
            if not await self._click_next_button(page):
                result.error = "Could not find or click Next button"
                return result
            await self.human.wait_and_observe(2, 4)

            # There may be a confirmation / "customize experience" screen - click through
            result.stage_reached = "click_next_2"
            await self._click_next_button(page)
            await self.human.wait_and_observe(1, 3)

            # Click "Sign Up" if present
            signup_selectors = [
                'button[data-testid="ocfSignupButton"]',
                'button:has-text("Sign up")',
                'div[role="button"]:has-text("Sign up")',
            ]
            signup_el = await self._find_element(page, signup_selectors, timeout=3000)
            if signup_el:
                await signup_el.click()
                await self.human.wait_and_observe(2, 4)

            # ── Stage 7: Email verification ──
            result.stage_reached = "email_verification"
            logger.info(f"[{identity.profile_id}] Waiting for email verification code...")
            try:
                code = await self.email_client.wait_for_code(identity.email, timeout=180)
            except (TimeoutError, ConnectionError, OSError) as e:
                code = None
                logger.warning(f"[{identity.profile_id}] Email code wait failed: {type(e).__name__}")
            if not code:
                result.error = "Email verification code not received within timeout"
                return result

            logger.info(f"[{identity.profile_id}] Email code received, entering...")
            verification_selectors = [
                'input[data-testid="ocfEnterTextTextInput"]',
                'input[name="verfication_code"]',
                'input[name="verification_code"]',
                'input[autocomplete="one-time-code"]',
            ]
            code_input = await self._find_element(page, verification_selectors, timeout=10000)
            if not code_input:
                result.error = "Could not find email verification code input"
                return result
            await self.human.type_text(code_input, code)
            await asyncio.sleep(1)

            # Click Next after code entry
            await self._click_next_button(page)
            await self.human.wait_and_observe(1, 3)

            # Clear used code
            await self.email_client.clear_code(identity.email)

            # ── Stage 8: Set password ──
            result.stage_reached = "set_password"
            logger.info(f"[{identity.profile_id}] Setting password")
            password_selectors = [
                'input[name="password"]',
                'input[type="password"]',
                'input[autocomplete="new-password"]',
            ]
            pw_input = await self._find_element(page, password_selectors, timeout=10000)
            if not pw_input:
                result.error = "Could not find password input"
                return result
            await self.human.type_text(pw_input, identity.password)
            await asyncio.sleep(1)

            # Click Next/Reveal password button if present, then Next
            await self._click_next_button(page)
            await self.human.wait_and_observe(2, 4)

            # ── Stage 9: Handle CAPTCHA (if present) ──
            result.stage_reached = "captcha_check"
            if await self._check_for_captcha(page):
                result.stage_reached = "captcha_solve"
                logger.info(f"[{identity.profile_id}] CAPTCHA detected")
                if not await self._handle_captcha(page):
                    result.error = "CAPTCHA solving failed"
                    return result
                await self.human.wait_and_observe(2, 4)

            # ── Stage 10: Handle phone verification (if required) ──
            result.stage_reached = "phone_check"
            if await self._check_for_phone_verification(page):
                result.stage_reached = "phone_verification"
                logger.info(f"[{identity.profile_id}] Phone verification required")
                if not await self._handle_phone_verification(page, identity):
                    result.error = "Phone verification failed"
                    return result
                await self.human.wait_and_observe(2, 4)

            # ── Stage 11: Profile setup ──
            result.stage_reached = "profile_setup"
            logger.info(f"[{identity.profile_id}] Handling profile setup")

            # Skip avatar upload for now - look for skip buttons
            skip_selectors = [
                'button[data-testid="ocfSelectAvatarSkipForNowButton"]',
                'button:has-text("Skip for now")',
                'div[role="button"]:has-text("Skip")',
            ]
            skip_el = await self._find_element(page, skip_selectors, timeout=5000)
            if skip_el:
                await skip_el.click()
                await asyncio.sleep(2)

            # Handle username selection if prompted
            username_selectors = [
                'input[data-testid="ocfEnterUsernameTextInput"]',
                'input[name="username"]',
            ]
            username_input = await self._find_element(page, username_selectors, timeout=3000)
            if username_input:
                await username_input.fill("")
                await self.human.type_text(username_input, identity.username)
                await self._click_next_button(page)
                await asyncio.sleep(2)
                result.username = identity.username

            # Skip other optional profile steps
            for _ in range(3):
                skip_el = await self._find_element(page, skip_selectors, timeout=2000)
                if skip_el:
                    await skip_el.click()
                    await asyncio.sleep(1.5)
                else:
                    break

            # ── Stage 12: Extract tokens ──
            result.stage_reached = "extract_tokens"
            logger.info(f"[{identity.profile_id}] Extracting auth tokens")
            tokens = await self._extract_tokens(page)

            result.auth_token = tokens["auth_token"]
            result.ct0 = tokens["ct0"]
            result.twid = tokens["twid"]

            if not result.auth_token:
                result.error = "No auth_token cookie found after signup"
                result.stage_reached = "token_missing"
                return result

            # Try to extract actual username from twid or page
            if result.twid and not result.username:
                # twid format is usually u%3D<user_id>
                result.username = identity.username

            if not result.username:
                # Try to get from page
                try:
                    result.username = await page.evaluate("""
                        () => {
                            const el = document.querySelector('[data-testid="UserName"]');
                            if (el) return el.textContent.replace('@', '');
                            return null;
                        }
                    """)
                except Exception:
                    result.username = identity.username

            # ── Success ──
            result.success = True
            result.stage_reached = "complete"
            logger.info(
                f"[{identity.profile_id}] Signup SUCCESSFUL - "
                f"username={result.username}, auth_token=***{result.auth_token[-4:]}"
            )

        except Exception as e:
            result.error = f"Unexpected error at stage '{result.stage_reached}': {str(e)}"
            logger.exception(f"[{identity.profile_id}] Signup failed: {result.error}")

        return result
