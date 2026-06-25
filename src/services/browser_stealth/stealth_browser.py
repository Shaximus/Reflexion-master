"""
Stealth Browser - CDP connection and stealth injection layer.
Supports GoLogin API (anti-detect browser) and direct Chromium fallback.
"""

import asyncio
import json
import logging
import re
from pathlib import Path
from typing import Optional, Dict, Any

import aiohttp
from playwright.async_api import async_playwright, Page, BrowserContext, Browser, Playwright

from .profile_manager import BrowserProfile

logger = logging.getLogger(__name__)

_STEALTH_JS_PATH = Path(__file__).parent / "stealth_scripts.js"


def _build_stealth_js(profile: BrowserProfile) -> str:
    """Read the stealth_scripts.js template and inject profile values."""
    template = _STEALTH_JS_PATH.read_text()

    replacements = {
        "{{DEVICE_MEMORY}}": str(profile.device_memory),
        "{{HARDWARE_CONCURRENCY}}": str(profile.hardware_concurrency),
        "{{PLATFORM}}": profile.platform,
        "{{LANGUAGES}}": json.dumps(profile.languages),
        "{{LANGUAGE}}": profile.languages[0] if profile.languages else "en-US",
        "{{VENDOR}}": profile.vendor,
        "{{SCREEN_WIDTH}}": str(profile.screen["width"]),
        "{{SCREEN_HEIGHT}}": str(profile.screen["height"]),
        "{{COLOR_DEPTH}}": str(profile.screen.get("colorDepth", 24)),
        "{{PIXEL_DEPTH}}": str(profile.screen.get("pixelDepth", 24)),
        "{{WEBGL_VENDOR}}": profile.webgl_vendor,
        "{{WEBGL_RENDERER}}": profile.webgl_renderer,
        "{{CANVAS_SEED}}": str(profile.canvas_seed),
        "{{TIMEZONE}}": profile.timezone,
        "{{UA_BRANDS}}": json.dumps(profile.ua_brands),
        "{{UA_PLATFORM}}": profile.ua_platform or "Windows",
        "{{UA_PLATFORM_VERSION}}": profile.ua_platform_version or "10.0.0",
        "{{UA_ARCHITECTURE}}": profile.ua_architecture or "x86",
        "{{UA_FULL_VERSION_LIST}}": json.dumps(profile.ua_full_version_list),
    }

    js = template
    for token, value in replacements.items():
        js = js.replace(token, value)

    return js


class StealthBrowser:
    """
    Stealth browser with Playwright, supporting GoLogin CDP connection
    and direct Chromium launch with full fingerprint spoofing.
    """

    def __init__(self, profile: BrowserProfile):
        self.profile = profile
        self.playwright: Optional[Playwright] = None
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self._owns_playwright = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    # =========================================================================
    # GoLogin connection
    # =========================================================================

    async def connect_goLogin(self, api_token: str, goLogin_profile_id: Optional[str] = None) -> Page:
        """
        Launch a GoLogin profile and connect via CDP WebSocket.

        Args:
            api_token: GoLogin API token.
            goLogin_profile_id: Existing GoLogin profile ID to launch.
                If None, creates a temporary profile.

        Returns:
            Playwright Page connected through GoLogin's anti-detect browser.
        """
        base_url = "https://api.gologin.com/browser"
        headers = {
            "Authorization": f"Bearer {api_token}",
            "Content-Type": "application/json",
        }

        async with aiohttp.ClientSession() as session:
            if goLogin_profile_id is None:
                # Create a temporary profile via GoLogin API
                profile_payload = self._build_goLogin_profile()
                async with session.post(
                    "https://api.gologin.com/browser",
                    headers=headers,
                    json=profile_payload,
                ) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        raise RuntimeError(f"GoLogin profile creation failed ({resp.status}): {body}")
                    data = await resp.json()
                    goLogin_profile_id = data["id"]
                    logger.info(f"Created GoLogin profile: {goLogin_profile_id}")

            # Start the profile
            async with session.post(
                f"{base_url}/{goLogin_profile_id}/start",
                headers=headers,
                json={"isHeadless": False},
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(f"GoLogin start failed ({resp.status}): {body}")
                data = await resp.json()
                ws_url = data.get("wsUrl") or data.get("ws", {}).get("puppeteer")
                if not ws_url:
                    raise RuntimeError(f"No WebSocket URL in GoLogin response: {data}")
                logger.info(f"GoLogin WS: {ws_url}")

        # Connect Playwright over CDP
        self.playwright = await async_playwright().start()
        self._owns_playwright = True

        self.browser = await self.playwright.chromium.connect_over_cdp(ws_url)
        contexts = self.browser.contexts
        self.context = contexts[0] if contexts else await self.browser.new_context()

        # Inject our stealth scripts on top of GoLogin's
        await self._inject_stealth(self.context)

        pages = self.context.pages
        self.page = pages[0] if pages else await self.context.new_page()

        logger.info("Connected to GoLogin browser via CDP")
        return self.page

    def _build_goLogin_profile(self) -> Dict[str, Any]:
        """Build a GoLogin-compatible profile payload from our BrowserProfile."""
        p = self.profile
        return {
            "name": p.name,
            "os": "win" if p.platform == "Win32" else ("mac" if p.platform == "MacIntel" else "lin"),
            "navigator": {
                "userAgent": p.user_agent,
                "resolution": f"{p.screen['width']}x{p.screen['height']}",
                "language": p.languages[0] if p.languages else "en-US",
                "platform": p.platform,
                "hardwareConcurrency": p.hardware_concurrency,
                "deviceMemory": p.device_memory,
            },
            "proxy": {
                "mode": "http" if p.proxy.get("server") else "none",
                "host": p.proxy.get("server", "").split("://")[-1].split(":")[0] if p.proxy.get("server") else "",
                "port": int(p.proxy.get("server", ":0").split(":")[-1]) if p.proxy.get("server") else 0,
                "username": p.proxy.get("username", ""),
                "password": p.proxy.get("password", ""),
            },
            "webGL": {
                "mode": "manual",
                "vendor": p.webgl_vendor,
                "renderer": p.webgl_renderer,
            },
            "timezone": {
                "enabled": True,
                "fillBasedOnIp": False,
                "timezone": p.timezone,
            },
            "geolocation": {
                "mode": "manual",
                "latitude": p.geolocation.get("lat", 0),
                "longitude": p.geolocation.get("lon", 0),
                "accuracy": p.geolocation.get("accuracy", 100),
            },
        }

    # =========================================================================
    # Direct Chromium launch (no GoLogin)
    # =========================================================================

    async def connect_direct(self, headless: bool = False) -> Page:
        """
        Launch a local Chromium instance with full stealth injection.
        This is the fallback path when GoLogin is not available.

        Returns:
            Playwright Page with stealth applied.
        """
        self.playwright = await async_playwright().start()
        self._owns_playwright = True

        launch_args = [
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
            "--disable-features=IsolateOrigins,site-per-process,TranslateUI",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-infobars",
            "--disable-default-apps",
            "--no-first-run",
            "--password-store=basic",
            "--use-mock-keychain",
            f"--window-size={self.profile.screen['width']},{self.profile.screen['height']}",
            f"--user-agent={self.profile.user_agent}",
        ]

        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=launch_args,
            ignore_default_args=["--enable-automation"],
            chromium_sandbox=False,
        )

        # Build context with profile fingerprint
        proxy_config = None
        if self.profile.proxy.get("server"):
            proxy_config = {"server": self.profile.proxy["server"]}
            if self.profile.proxy.get("username"):
                proxy_config["username"] = self.profile.proxy["username"]
                proxy_config["password"] = self.profile.proxy.get("password", "")

        context_opts: Dict[str, Any] = {
            "viewport": self.profile.viewport,
            "user_agent": self.profile.user_agent,
            "locale": self.profile.languages[0] if self.profile.languages else "en-US",
            "timezone_id": self.profile.timezone,
            "geolocation": {
                "latitude": self.profile.geolocation.get("lat", 0),
                "longitude": self.profile.geolocation.get("lon", 0),
                "accuracy": self.profile.geolocation.get("accuracy", 100),
            },
            "permissions": ["geolocation"],
            "color_scheme": "light",
            "device_scale_factor": 1,
            "is_mobile": False,
            "has_touch": False,
            "extra_http_headers": self._build_headers(),
        }

        if proxy_config:
            context_opts["proxy"] = proxy_config

        self.context = await self.browser.new_context(**context_opts)

        # Inject stealth
        await self._inject_stealth(self.context)

        self.page = await self.context.new_page()

        logger.info(f"Direct stealth browser launched: {self.profile.name}")
        return self.page

    # =========================================================================
    # Stealth injection
    # =========================================================================

    async def inject_stealth(self, page: Page, profile: BrowserProfile):
        """
        Public method to inject stealth overrides into an existing page.
        Useful when you already have a page from another source.
        """
        self.profile = profile
        js = _build_stealth_js(profile)
        await page.evaluate(js)

    async def _inject_stealth(self, context: BrowserContext):
        """Inject stealth scripts as init_script so they run before ANY page JS."""
        js = _build_stealth_js(self.profile)
        await context.add_init_script(js)
        logger.debug("Stealth scripts injected into context")

        # Also try playwright-stealth if available
        try:
            from playwright_stealth.stealth import Stealth
            stealth = Stealth(
                chrome_app=True,
                chrome_csi=True,
                chrome_load_times=True,
                chrome_runtime=True,
                hairline=True,
                iframe_content_window=True,
                media_codecs=True,
                navigator_hardware_concurrency=True,
                navigator_languages=True,
                navigator_permissions=True,
                navigator_platform=True,
                navigator_plugins=True,
                navigator_user_agent=True,
                navigator_vendor=True,
                navigator_webdriver=True,
                sec_ch_ua=True,
                webgl_vendor=True,
                navigator_languages_override=tuple(self.profile.languages),
                navigator_platform_override=self.profile.platform,
                navigator_vendor_override=self.profile.vendor,
                webgl_vendor_override=self.profile.webgl_vendor,
                webgl_renderer_override=self.profile.webgl_renderer,
            )
            await stealth.apply_stealth_async(context)
            logger.debug("playwright-stealth applied as additional layer")
        except ImportError:
            logger.debug("playwright-stealth not installed, using custom JS only")
        except Exception as e:
            logger.debug(f"playwright-stealth failed (non-critical): {e}")

    def _build_headers(self) -> Dict[str, str]:
        """Build extra HTTP headers matching the profile."""
        headers = {
            "Accept-Language": ",".join(self.profile.languages),
            "Accept-Encoding": "gzip, deflate, br, zstd",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        }

        # sec-ch-ua headers
        if self.profile.ua_brands:
            brands_str = ", ".join(
                f'"{b["brand"]}";v="{b["version"]}"' for b in self.profile.ua_brands
            )
            headers["sec-ch-ua"] = brands_str
            headers["sec-ch-ua-mobile"] = "?0"
            headers["sec-ch-ua-platform"] = f'"{self.profile.ua_platform}"'

        return headers

    # =========================================================================
    # Navigation helpers
    # =========================================================================

    async def goto(self, url: str, wait_until: str = "domcontentloaded", timeout: int = 30000) -> None:
        """Navigate to URL with error handling."""
        if not self.page:
            raise RuntimeError("No page available. Call connect_direct() or connect_goLogin() first.")
        await self.page.goto(url, wait_until=wait_until, timeout=timeout)

    async def get_cookies(self) -> list:
        """Get all cookies from the current context."""
        if not self.context:
            return []
        return await self.context.cookies()

    async def set_cookies(self, cookies: list):
        """Set cookies on the current context."""
        if self.context:
            await self.context.add_cookies(cookies)

    async def screenshot(self, path: str = None, full_page: bool = False) -> bytes:
        """Take a screenshot."""
        if not self.page:
            raise RuntimeError("No page available.")
        return await self.page.screenshot(path=path, full_page=full_page)

    async def evaluate(self, expression: str) -> Any:
        """Evaluate JS expression in page context."""
        if not self.page:
            raise RuntimeError("No page available.")
        return await self.page.evaluate(expression)

    # =========================================================================
    # Stealth verification
    # =========================================================================

    async def verify_stealth(self) -> Dict[str, Any]:
        """Quick self-check of stealth injection. Returns dict of check results."""
        if not self.page:
            raise RuntimeError("No page available.")

        checks = {}
        checks["webdriver"] = await self.page.evaluate("navigator.webdriver")
        checks["platform"] = await self.page.evaluate("navigator.platform")
        checks["vendor"] = await self.page.evaluate("navigator.vendor")
        checks["languages"] = await self.page.evaluate("navigator.languages")
        checks["deviceMemory"] = await self.page.evaluate("navigator.deviceMemory")
        checks["hardwareConcurrency"] = await self.page.evaluate("navigator.hardwareConcurrency")
        checks["chrome_exists"] = await self.page.evaluate("typeof window.chrome !== 'undefined'")
        checks["chrome_runtime"] = await self.page.evaluate("typeof window.chrome?.runtime !== 'undefined'")
        checks["plugins_count"] = await self.page.evaluate("navigator.plugins.length")

        # Validate against profile
        ok = True
        if checks["webdriver"] is not None and checks["webdriver"] is not False:
            logger.warning("FAIL: navigator.webdriver is not undefined/false")
            ok = False
        if checks["platform"] != self.profile.platform:
            logger.warning(f"FAIL: platform mismatch: {checks['platform']} != {self.profile.platform}")
            ok = False
        if checks["deviceMemory"] != self.profile.device_memory:
            logger.warning(f"FAIL: deviceMemory mismatch: {checks['deviceMemory']} != {self.profile.device_memory}")
            ok = False

        checks["all_passed"] = ok
        return checks

    # =========================================================================
    # Lifecycle
    # =========================================================================

    async def close(self):
        """Close browser and release resources."""
        if self.page:
            try:
                await self.page.close()
            except Exception:
                pass
            self.page = None
        if self.context:
            try:
                await self.context.close()
            except Exception:
                pass
            self.context = None
        if self.browser:
            try:
                await self.browser.close()
            except Exception:
                pass
            self.browser = None
        if self.playwright and self._owns_playwright:
            try:
                await self.playwright.stop()
            except Exception:
                pass
            self.playwright = None
        logger.debug("StealthBrowser closed")
