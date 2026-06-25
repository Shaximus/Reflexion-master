"""
Stealth Validation Suite - Automated tests against browser detection sites.
Checks fingerprint consistency and bot detection evasion.
"""

import asyncio
import json
import logging
import re
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

from playwright.async_api import Page

logger = logging.getLogger(__name__)


@dataclass
class ValidationResult:
    site: str
    passed: bool
    score: Optional[str] = None
    details: Dict[str, Any] = field(default_factory=dict)
    warnings: List[str] = field(default_factory=list)
    errors: List[str] = field(default_factory=list)


class StealthValidator:
    """Validates stealth configuration against known detection sites."""

    def __init__(self, page: Page):
        self.page = page

    async def validate_all(self) -> Dict[str, ValidationResult]:
        """Run all validation checks. Returns dict keyed by site name."""
        results = {}

        checks = [
            ("bot.sannysoft.com", self.check_bot_sannysoft),
            ("browserleaks.com", self.check_browserleaks),
            ("pixelscan.net", self.check_pixelscan),
            ("creepjs", self.check_creepjs),
        ]

        for name, check_fn in checks:
            try:
                result = await check_fn()
                results[name] = result
                status = "PASS" if result.passed else "FAIL"
                logger.info(f"[{status}] {name}: {result.score or 'N/A'}")
                for w in result.warnings:
                    logger.warning(f"  - {w}")
                for e in result.errors:
                    logger.error(f"  - {e}")
            except Exception as e:
                results[name] = ValidationResult(
                    site=name, passed=False, errors=[str(e)]
                )
                logger.error(f"[ERROR] {name}: {e}")

        return results

    # =========================================================================
    # BOT.SANNYSOFT.COM
    # =========================================================================

    async def check_bot_sannysoft(self) -> ValidationResult:
        """
        Navigate to bot.sannysoft.com and extract detection results.
        This site checks basic bot indicators.
        """
        result = ValidationResult(site="bot.sannysoft.com", passed=True)

        await self.page.goto("https://bot.sannysoft.com", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        # Extract results from the table
        rows = await self.page.query_selector_all("#fp2 table tr")
        for row in rows:
            cells = await row.query_selector_all("td")
            if len(cells) >= 2:
                key_el = cells[0]
                val_el = cells[1]
                key = (await key_el.inner_text()).strip()
                val = (await val_el.inner_text()).strip()
                classes = await val_el.get_attribute("class") or ""

                result.details[key] = val

                if "failed" in classes.lower() or "warn" in classes.lower():
                    result.warnings.append(f"{key}: {val}")
                if key.lower() == "webdriver" and val.lower() not in ("false", "undefined", "missing"):
                    result.errors.append(f"WebDriver detected: {val}")
                    result.passed = False

        # Check critical fields
        webdriver_val = result.details.get("WebDriver", "").lower()
        if webdriver_val in ("true", "present"):
            result.passed = False
            result.errors.append("WebDriver flag is set")

        result.score = "PASS" if result.passed else "FAIL"
        return result

    # =========================================================================
    # BROWSERLEAKS.COM
    # =========================================================================

    async def check_browserleaks(self) -> ValidationResult:
        """
        Navigate to browserleaks.com canvas test and check for inconsistencies.
        """
        result = ValidationResult(site="browserleaks.com", passed=True)

        await self.page.goto("https://browserleaks.com/javascript", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(4)

        # Extract key navigator properties
        js_checks = {
            "userAgent": "navigator.userAgent",
            "platform": "navigator.platform",
            "languages": "JSON.stringify(navigator.languages)",
            "hardwareConcurrency": "navigator.hardwareConcurrency",
            "deviceMemory": "navigator.deviceMemory",
            "webdriver": "navigator.webdriver",
            "vendor": "navigator.vendor",
            "plugins_count": "navigator.plugins.length",
            "cookieEnabled": "navigator.cookieEnabled",
            "doNotTrack": "navigator.doNotTrack",
        }

        for key, expr in js_checks.items():
            try:
                val = await self.page.evaluate(expr)
                result.details[key] = val
            except Exception as e:
                result.details[key] = f"error: {e}"

        # Validate critical checks
        if result.details.get("webdriver") not in (None, False, "undefined"):
            result.passed = False
            result.errors.append(f"webdriver detected: {result.details['webdriver']}")

        if result.details.get("plugins_count", 0) == 0:
            result.warnings.append("No plugins detected (suspicious for Chrome)")

        # Check WebGL
        await self.page.goto("https://browserleaks.com/webgl", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)

        try:
            webgl_vendor = await self.page.evaluate("""
                (() => {
                    const canvas = document.createElement('canvas');
                    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (!gl) return 'N/A';
                    const ext = gl.getExtension('WEBGL_debug_renderer_info');
                    if (!ext) return 'N/A';
                    return gl.getParameter(ext.UNMASKED_VENDOR_WEBGL);
                })()
            """)
            webgl_renderer = await self.page.evaluate("""
                (() => {
                    const canvas = document.createElement('canvas');
                    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (!gl) return 'N/A';
                    const ext = gl.getExtension('WEBGL_debug_renderer_info');
                    if (!ext) return 'N/A';
                    return gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);
                })()
            """)
            result.details["webgl_vendor"] = webgl_vendor
            result.details["webgl_renderer"] = webgl_renderer

            # Check for VM indicators
            renderer_lower = (webgl_renderer or "").lower()
            if any(vm in renderer_lower for vm in ["vmware", "virtualbox", "llvmpipe", "swiftshader"]):
                result.warnings.append(f"VM-like WebGL renderer: {webgl_renderer}")
        except Exception as e:
            result.details["webgl_error"] = str(e)

        result.score = "PASS" if result.passed else "FAIL"
        return result

    # =========================================================================
    # PIXELSCAN.NET
    # =========================================================================

    async def check_pixelscan(self) -> ValidationResult:
        """
        Navigate to pixelscan.net and check environment consistency.
        Pixelscan specifically looks for mismatches between reported values.
        """
        result = ValidationResult(site="pixelscan.net", passed=True)

        await self.page.goto("https://pixelscan.net", wait_until="networkidle", timeout=45000)
        await asyncio.sleep(8)  # Pixelscan takes longer to analyze

        # Try to extract the consistency result
        try:
            # Look for the main status indicator
            status_el = await self.page.query_selector(".consistency-status, .result-status, [class*='status']")
            if status_el:
                status_text = (await status_el.inner_text()).strip()
                result.details["status"] = status_text
                result.score = status_text

                if "inconsistent" in status_text.lower() or "suspicious" in status_text.lower():
                    result.passed = False
                    result.errors.append(f"Pixelscan status: {status_text}")
        except Exception:
            pass

        # Extract individual check items
        try:
            items = await self.page.query_selector_all(".check-item, .result-item, [class*='check']")
            for item in items:
                text = (await item.inner_text()).strip()
                classes = await item.get_attribute("class") or ""
                if text:
                    is_fail = "fail" in classes.lower() or "inconsistent" in classes.lower() or "warn" in classes.lower()
                    result.details[text[:50]] = "FAIL" if is_fail else "OK"
                    if is_fail:
                        result.warnings.append(text[:100])
        except Exception:
            pass

        # Fallback: run our own consistency checks via JS
        consistency = await self._check_consistency_js()
        result.details["js_consistency"] = consistency
        for issue in consistency.get("issues", []):
            result.warnings.append(issue)
            if "critical" in issue.lower():
                result.passed = False

        if result.score is None:
            result.score = "PASS" if result.passed else "FAIL"

        return result

    async def _check_consistency_js(self) -> Dict[str, Any]:
        """Run our own JS-side consistency checks."""
        return await self.page.evaluate("""
            (() => {
                const issues = [];
                const info = {};

                // Check UA vs platform consistency
                const ua = navigator.userAgent;
                const plat = navigator.platform;
                info.ua = ua;
                info.platform = plat;

                if (ua.includes('Windows') && plat !== 'Win32') {
                    issues.push('CRITICAL: UA says Windows but platform is ' + plat);
                }
                if (ua.includes('Macintosh') && plat !== 'MacIntel') {
                    issues.push('CRITICAL: UA says Mac but platform is ' + plat);
                }
                if (ua.includes('Linux') && !plat.includes('Linux')) {
                    issues.push('CRITICAL: UA says Linux but platform is ' + plat);
                }

                // Check webdriver
                if (navigator.webdriver === true) {
                    issues.push('CRITICAL: navigator.webdriver is true');
                }

                // Check chrome object
                if (ua.includes('Chrome') && !window.chrome) {
                    issues.push('Chrome UA but no window.chrome object');
                }

                // Check plugins
                if (ua.includes('Chrome') && navigator.plugins.length === 0) {
                    issues.push('Chrome UA but 0 plugins');
                }

                // Check languages
                if (!navigator.languages || navigator.languages.length === 0) {
                    issues.push('Empty navigator.languages');
                }

                return { issues, info };
            })()
        """)

    # =========================================================================
    # CREEPJS
    # =========================================================================

    async def check_creepjs(self) -> ValidationResult:
        """
        Navigate to CreepJS and extract the trust score.
        CreepJS is one of the most advanced detection tools.
        """
        result = ValidationResult(site="creepjs", passed=True)

        await self.page.goto(
            "https://abrahamjuliot.github.io/creepjs/",
            wait_until="networkidle",
            timeout=60000,
        )
        # CreepJS runs extensive analysis - give it time
        await asyncio.sleep(15)

        try:
            # Try to get the trust score
            score_el = await self.page.query_selector(".trust-score, [class*='trust'], [class*='grade']")
            if score_el:
                score_text = (await score_el.inner_text()).strip()
                result.details["trust_score"] = score_text
                result.score = score_text

            # Try to get the overall grade/rating
            grade_el = await self.page.query_selector(".grade, [class*='rating']")
            if grade_el:
                grade = (await grade_el.inner_text()).strip()
                result.details["grade"] = grade

            # Extract individual test results
            test_items = await self.page.query_selector_all(".test-result, [class*='fingerprint'] li")
            for item in test_items[:20]:  # Limit to avoid bloat
                text = (await item.inner_text()).strip()
                if text:
                    classes = await item.get_attribute("class") or ""
                    if "fail" in classes.lower() or "blocked" in classes.lower():
                        result.warnings.append(text[:100])

            # Check for specific red flags via JS
            red_flags = await self.page.evaluate("""
                (() => {
                    const flags = [];
                    // CreepJS stores results in various places
                    const elements = document.querySelectorAll('[class*="fail"], [class*="lie"], [class*="trash"]');
                    elements.forEach(el => {
                        const text = el.textContent.trim();
                        if (text.length > 0 && text.length < 200) {
                            flags.push(text);
                        }
                    });
                    return flags.slice(0, 10);
                })()
            """)

            if red_flags:
                result.details["red_flags"] = red_flags
                for flag in red_flags:
                    result.warnings.append(f"CreepJS flag: {flag}")

        except Exception as e:
            result.details["error"] = str(e)

        # CreepJS is hard to fully pass - we mark as passed unless we got critical failures
        critical_count = sum(1 for w in result.warnings if "lie" in w.lower() or "fake" in w.lower())
        if critical_count > 3:
            result.passed = False

        if not result.score:
            result.score = f"{len(result.warnings)} warnings"

        return result

    # =========================================================================
    # QUICK CHECK (no navigation)
    # =========================================================================

    async def quick_fingerprint_check(self) -> Dict[str, Any]:
        """
        Run fingerprint checks on the current page without navigating.
        Useful for verifying stealth before hitting a target site.
        """
        return await self.page.evaluate("""
            (() => {
                const results = {};

                // Navigator checks
                results.webdriver = navigator.webdriver;
                results.platform = navigator.platform;
                results.vendor = navigator.vendor;
                results.languages = navigator.languages;
                results.hardwareConcurrency = navigator.hardwareConcurrency;
                results.deviceMemory = navigator.deviceMemory;
                results.plugins = navigator.plugins.length;

                // Screen
                results.screenWidth = screen.width;
                results.screenHeight = screen.height;
                results.colorDepth = screen.colorDepth;

                // Chrome object
                results.hasChrome = typeof window.chrome !== 'undefined';
                results.hasChromeRuntime = typeof window.chrome?.runtime !== 'undefined';

                // WebGL
                try {
                    const canvas = document.createElement('canvas');
                    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (gl) {
                        const ext = gl.getExtension('WEBGL_debug_renderer_info');
                        if (ext) {
                            results.webglVendor = gl.getParameter(ext.UNMASKED_VENDOR_WEBGL);
                            results.webglRenderer = gl.getParameter(ext.UNMASKED_RENDERER_WEBGL);
                        }
                    }
                } catch(e) {
                    results.webglError = e.message;
                }

                // Timezone
                results.timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;

                // Permissions
                results.permissionsAPI = typeof navigator.permissions !== 'undefined';

                return results;
            })()
        """)


async def run_validation(page: Page) -> Dict[str, ValidationResult]:
    """Convenience function to run full validation suite."""
    validator = StealthValidator(page)
    return await validator.validate_all()
