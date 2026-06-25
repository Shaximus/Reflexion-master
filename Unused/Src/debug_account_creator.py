#!/usr/bin/env python3
"""
DEBUG SCRIPT FOR STEALTH ACCOUNT CREATOR
Comprehensive debugging and testing for the account creation system
"""

import os
import sys
import json
import asyncio
import logging
import traceback
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import argparse

# Setup paths
current_dir = Path(__file__).parent
sys.path.insert(0, str(current_dir))

# ═══════════════════════════════════════════════════════════════════════════════
# ENHANCED DEBUG LOGGING
# ═══════════════════════════════════════════════════════════════════════════════

class DebugLogger:
    """Enhanced logger for debugging account creation"""
    
    def __init__(self, log_dir: str = "debug_logs"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(exist_ok=True)
        
        # Create timestamped session directory
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.log_dir / self.session_id
        self.session_dir.mkdir(exist_ok=True)
        
        # Setup different log files
        self.setup_loggers()
        
    def setup_loggers(self):
        """Setup multiple specialized loggers"""
        
        # Main debug log
        self.main_logger = self._create_logger(
            'main',
            self.session_dir / 'main_debug.log',
            logging.DEBUG
        )
        
        # Browser events log
        self.browser_logger = self._create_logger(
            'browser',
            self.session_dir / 'browser_events.log',
            logging.DEBUG
        )
        
        # Network log
        self.network_logger = self._create_logger(
            'network',
            self.session_dir / 'network.log',
            logging.DEBUG
        )
        
        # Error log
        self.error_logger = self._create_logger(
            'errors',
            self.session_dir / 'errors.log',
            logging.ERROR
        )
        
        # Success log
        self.success_logger = self._create_logger(
            'success',
            self.session_dir / 'success.log',
            logging.INFO
        )
        
    def _create_logger(self, name: str, filepath: Path, level: int) -> logging.Logger:
        """Create a specialized logger"""
        logger = logging.getLogger(name)
        logger.setLevel(level)
        
        # File handler
        fh = logging.FileHandler(filepath, encoding='utf-8')
        fh.setLevel(level)
        
        # Console handler for errors
        ch = logging.StreamHandler()
        ch.setLevel(logging.INFO if name == 'main' else logging.ERROR)
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s | %(levelname)-8s | %(name)-10s | %(message)s',
            datefmt='%H:%M:%S'
        )
        fh.setFormatter(formatter)
        ch.setFormatter(formatter)
        
        logger.addHandler(fh)
        logger.addHandler(ch)
        
        return logger
    
    def save_state(self, data: Dict, filename: str):
        """Save debug state to JSON"""
        filepath = self.session_dir / filename
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2, default=str)

# ═══════════════════════════════════════════════════════════════════════════════
# MOCK COMPONENTS FOR TESTING
# ═══════════════════════════════════════════════════════════════════════════════

class MockCaptchaSolver:
    """Mock CAPTCHA solver for testing"""
    
    def __init__(self, debug_logger: DebugLogger):
        self.logger = debug_logger
        self.solve_success_rate = 0.8  # 80% success rate for testing
        
    async def solve_recaptcha_v2(self, sitekey: str, url: str) -> Optional[str]:
        """Mock CAPTCHA solving"""
        self.logger.main_logger.info(f"Mock CAPTCHA solve requested for {url}")
        await asyncio.sleep(2)  # Simulate solving time
        
        if os.getenv("MOCK_CAPTCHA_FAIL") == "1":
            self.logger.error_logger.error("Mock CAPTCHA solve failed (forced)")
            return None
            
        import random
        if random.random() < self.solve_success_rate:
            solution = "MOCK_CAPTCHA_SOLUTION_" + "".join(random.choices("0123456789ABCDEF", k=32))
            self.logger.success_logger.info(f"Mock CAPTCHA solved: {solution[:20]}...")
            return solution
        else:
            self.logger.error_logger.error("Mock CAPTCHA solve failed (random)")
            return None

class MockSMSService:
    """Mock SMS service for testing"""
    
    def __init__(self, debug_logger: DebugLogger):
        self.logger = debug_logger
        self.get_number_success_rate = 0.9
        self.get_code_success_rate = 0.85
        
    async def get_number(self, service: str = "tw", country: str = "0") -> Optional[Dict]:
        """Mock phone number acquisition"""
        self.logger.main_logger.info(f"Mock SMS number requested for {service}")
        await asyncio.sleep(1)
        
        if os.getenv("MOCK_SMS_FAIL") == "1":
            self.logger.error_logger.error("Mock SMS number failed (forced)")
            return None
            
        import random
        if random.random() < self.get_number_success_rate:
            number = f"+1555{random.randint(1000000, 9999999)}"
            result = {
                "provider": "mock",
                "activation_id": f"MOCK_{random.randint(100000, 999999)}",
                "phone": number,
                "service": service
            }
            self.logger.success_logger.info(f"Mock SMS number obtained: {number}")
            return result
        else:
            self.logger.error_logger.error("Mock SMS number failed (random)")
            return None
    
    async def wait_for_code(self, number_data: Dict, timeout: int = 300) -> Optional[str]:
        """Mock SMS code reception"""
        self.logger.main_logger.info(f"Waiting for mock SMS code...")
        await asyncio.sleep(3)
        
        import random
        if random.random() < self.get_code_success_rate:
            code = "".join(random.choices("0123456789", k=6))
            self.logger.success_logger.info(f"Mock SMS code received: {code}")
            return code
        else:
            self.logger.error_logger.error("Mock SMS code timeout")
            return None

# ═══════════════════════════════════════════════════════════════════════════════
# DEBUG BROWSER WRAPPER
# ═══════════════════════════════════════════════════════════════════════════════

class DebugStealthBrowser:
    """Wrapper around StealthBrowser with enhanced debugging"""
    
    def __init__(self, browser, debug_logger: DebugLogger):
        self.browser = browser
        self.logger = debug_logger
        self.page = browser.page
        self.context = browser.context
        
        # Track events
        self.events = []
        self.screenshots_taken = 0
        
    async def goto(self, url: str):
        """Navigate with logging"""
        self.logger.browser_logger.info(f"Navigating to: {url}")
        try:
            response = await self.page.goto(url)
            status = response.status if response else "No response"
            self.logger.browser_logger.info(f"Navigation complete: {status}")
            self.events.append({'type': 'navigation', 'url': url, 'status': status})
            return response
        except Exception as e:
            self.logger.error_logger.error(f"Navigation failed: {e}")
            await self.debug_screenshot("navigation_error")
            raise
    
    async def human_type(self, selector: str, text: str):
        """Type with debug logging"""
        self.logger.browser_logger.debug(f"Typing in {selector}: {text[:20]}...")
        try:
            await self.browser.human_type(selector, text)
            self.events.append({'type': 'type', 'selector': selector, 'text_length': len(text)})
        except Exception as e:
            self.logger.error_logger.error(f"Typing failed in {selector}: {e}")
            await self.debug_screenshot("type_error")
            raise
    
    async def human_click(self, selector: str):
        """Click with debug logging"""
        self.logger.browser_logger.debug(f"Clicking: {selector}")
        try:
            await self.browser.human_click(selector)
            self.events.append({'type': 'click', 'selector': selector})
        except Exception as e:
            self.logger.error_logger.error(f"Click failed on {selector}: {e}")
            await self.debug_screenshot("click_error")
            raise
    
    async def debug_screenshot(self, name: str = None):
        """Take debug screenshot"""
        if name is None:
            name = f"debug_{self.screenshots_taken}"
        
        screenshot_path = self.logger.session_dir / "screenshots"
        screenshot_path.mkdir(exist_ok=True)
        
        filepath = screenshot_path / f"{name}.png"
        try:
            await self.page.screenshot(path=str(filepath))
            self.logger.browser_logger.info(f"Screenshot saved: {filepath.name}")
            self.screenshots_taken += 1
        except Exception as e:
            self.logger.error_logger.error(f"Screenshot failed: {e}")
    
    async def get_page_info(self) -> Dict:
        """Get current page information for debugging"""
        try:
            info = {
                'url': self.page.url,
                'title': await self.page.title(),
                'viewport': await self.page.viewport_size(),
                'cookies': len(await self.context.cookies()),
                'local_storage': await self.page.evaluate("Object.keys(localStorage).length"),
                'session_storage': await self.page.evaluate("Object.keys(sessionStorage).length")
            }
            return info
        except Exception as e:
            self.logger.error_logger.error(f"Failed to get page info: {e}")
            return {}

# ═══════════════════════════════════════════════════════════════════════════════
# DEBUG ACCOUNT CREATOR
# ═══════════════════════════════════════════════════════════════════════════════

class DebugAccountCreator:
    """Debug version of account creator with extensive logging"""
    
    def __init__(self, debug_logger: DebugLogger, use_mocks: bool = False):
        self.logger = debug_logger
        self.use_mocks = use_mocks
        
        # Import actual components
        try:
            from playwright_stealth_core import BrowserPool, StealthBrowser
            self.browser_pool = BrowserPool(max_browsers=1)
            self.logger.main_logger.info("✅ Playwright stealth core imported")
        except ImportError as e:
            self.logger.error_logger.error(f"Failed to import playwright_stealth_core: {e}")
            raise
        
        # Setup services (mock or real)
        if use_mocks:
            self.logger.main_logger.info("Using MOCK services")
            self.captcha_solver = MockCaptchaSolver(debug_logger)
            self.sms_service = MockSMSService(debug_logger)
        else:
            try:
                from stealth_account_creator import CaptchaSolver, SMSService
                self.captcha_solver = CaptchaSolver()
                self.sms_service = SMSService()
                self.logger.main_logger.info("Using REAL services")
            except ImportError:
                self.logger.main_logger.warning("Real services not available, using mocks")
                self.captcha_solver = MockCaptchaSolver(debug_logger)
                self.sms_service = MockSMSService(debug_logger)
    
    async def test_browser_launch(self) -> bool:
        """Test basic browser launch"""
        self.logger.main_logger.info("=" * 60)
        self.logger.main_logger.info("TEST: Browser Launch")
        self.logger.main_logger.info("=" * 60)
        
        try:
            from playwright_stealth_core import StealthBrowser
            
            # Test with headless mode
            browser = StealthBrowser(proxy=None)
            await browser.launch(headless=True)
            
            # Wrap in debug browser
            debug_browser = DebugStealthBrowser(browser, self.logger)
            
            # Test navigation
            await debug_browser.goto("https://example.com")
            
            # Get page info
            info = await debug_browser.get_page_info()
            self.logger.success_logger.info(f"Browser launched successfully: {info}")
            
            # Take screenshot
            await debug_browser.debug_screenshot("test_launch")
            
            # Close
            await browser.close()
            
            return True
            
        except Exception as e:
            self.logger.error_logger.error(f"Browser launch test failed: {e}")
            self.logger.error_logger.error(traceback.format_exc())
            return False
    
    async def test_cloudflare_detection(self) -> bool:
        """Test Cloudflare detection and bypass"""
        self.logger.main_logger.info("=" * 60)
        self.logger.main_logger.info("TEST: Cloudflare Detection")
        self.logger.main_logger.info("=" * 60)
        
        try:
            from playwright_stealth_core import StealthBrowser, CloudflareBypass
            
            browser = StealthBrowser(proxy=None)
            await browser.launch(headless=True)
            debug_browser = DebugStealthBrowser(browser, self.logger)
            
            # Test sites that might have Cloudflare
            test_sites = [
                "https://twitter.com",
                "https://discord.com",
                "https://www.cloudflare.com"
            ]
            
            for site in test_sites:
                self.logger.main_logger.info(f"Testing {site}")
                await debug_browser.goto(site)
                
                # Check for Cloudflare
                content = await browser.page.content()
                has_cf = any(indicator in content for indicator in [
                    'Checking your browser',
                    'Just a moment',
                    'cf-challenge'
                ])
                
                if has_cf:
                    self.logger.main_logger.warning(f"Cloudflare detected on {site}")
                    
                    # Try bypass
                    bypass = CloudflareBypass(browser)
                    success = await bypass.bypass(site)
                    
                    if success:
                        self.logger.success_logger.info(f"Cloudflare bypassed for {site}")
                    else:
                        self.logger.error_logger.error(f"Cloudflare bypass failed for {site}")
                else:
                    self.logger.main_logger.info(f"No Cloudflare on {site}")
                
                await debug_browser.debug_screenshot(f"cf_test_{site.split('//')[1].split('/')[0]}")
            
            await browser.close()
            return True
            
        except Exception as e:
            self.logger.error_logger.error(f"Cloudflare test failed: {e}")
            self.logger.error_logger.error(traceback.format_exc())
            return False
    
    async def test_twitter_elements(self) -> bool:
        """Test Twitter element detection"""
        self.logger.main_logger.info("=" * 60)
        self.logger.main_logger.info("TEST: Twitter Element Detection")
        self.logger.main_logger.info("=" * 60)
        
        try:
            from playwright_stealth_core import StealthBrowser
            
            browser = StealthBrowser(proxy=None)
            await browser.launch(headless=True)
            debug_browser = DebugStealthBrowser(browser, self.logger)
            
            # Navigate to Twitter signup
            await debug_browser.goto("https://twitter.com/i/flow/signup")
            await asyncio.sleep(3)
            
            # Check for key elements
            elements_to_check = [
                ('Create account button', 'span:has-text("Create account")'),
                ('Name input', 'input[name="name"]'),
                ('Email input', 'input[name="email"]'),
                ('Birth month', 'select[aria-label*="Month"]'),
                ('Birth day', 'select[aria-label*="Day"]'),
                ('Birth year', 'select[aria-label*="Year"]')
            ]
            
            found_elements = {}
            for name, selector in elements_to_check:
                try:
                    element = await browser.page.query_selector(selector)
                    found_elements[name] = element is not None
                    
                    if element:
                        self.logger.success_logger.info(f"✅ Found: {name}")
                    else:
                        self.logger.error_logger.warning(f"❌ Not found: {name}")
                except Exception as e:
                    found_elements[name] = False
                    self.logger.error_logger.error(f"Error checking {name}: {e}")
            
            # Save element detection results
            self.logger.save_state({
                'elements_found': found_elements,
                'url': browser.page.url,
                'timestamp': datetime.now().isoformat()
            }, 'twitter_elements.json')
            
            await debug_browser.debug_screenshot("twitter_signup_page")
            await browser.close()
            
            return all(found_elements.values())
            
        except Exception as e:
            self.logger.error_logger.error(f"Twitter element test failed: {e}")
            self.logger.error_logger.error(traceback.format_exc())
            return False
    
    async def test_full_account_flow(self, dry_run: bool = True) -> bool:
        """Test full account creation flow"""
        self.logger.main_logger.info("=" * 60)
        self.logger.main_logger.info(f"TEST: Full Account Creation ({'DRY RUN' if dry_run else 'LIVE'})")
        self.logger.main_logger.info("=" * 60)
        
        if not dry_run:
            self.logger.main_logger.warning("⚠️ LIVE MODE - This will attempt to create a real account!")
            
        try:
            from playwright_stealth_core import StealthBrowser
            from faker import Faker
            
            faker = Faker()
            
            # Generate test account details
            account = {
                'name': faker.name(),
                'username': f"test_{faker.user_name()}{faker.random_int(100, 999)}",
                'email': f"test_{faker.user_name()}@reflexion.ai",
                'password': faker.password(length=16, special_chars=True, digits=True, upper_case=True),
                'birth_year': faker.random_int(1985, 2003),
                'birth_month': faker.random_int(1, 12),
                'birth_day': faker.random_int(1, 28)
            }
            
            self.logger.save_state(account, 'test_account.json')
            self.logger.main_logger.info(f"Test account: {account['name']} ({account['email']})")
            
            browser = StealthBrowser(proxy=None)
            await browser.launch(headless=True)
            debug_browser = DebugStealthBrowser(browser, self.logger)
            
            # Step 1: Navigate to signup
            await debug_browser.goto("https://twitter.com/i/flow/signup")
            await asyncio.sleep(3)
            await debug_browser.debug_screenshot("01_signup_page")
            
            if dry_run:
                self.logger.main_logger.info("DRY RUN: Would click 'Create account'")
            else:
                # Step 2: Click create account
                await debug_browser.human_click('span:has-text("Create account")')
                await asyncio.sleep(2)
                await debug_browser.debug_screenshot("02_after_create_click")
                
                # Step 3: Enter name
                await debug_browser.human_type('input[name="name"]', account['name'])
                await asyncio.sleep(1)
                
                # Step 4: Switch to email
                try:
                    await debug_browser.human_click('span:has-text("Use email instead")')
                    await asyncio.sleep(1)
                except:
                    self.logger.main_logger.info("Email option not needed")
                
                # Step 5: Enter email
                await debug_browser.human_type('input[name="email"]', account['email'])
                await asyncio.sleep(1)
                await debug_browser.debug_screenshot("03_filled_info")
                
                # More steps would follow...
            
            # Get final page state
            final_state = await debug_browser.get_page_info()
            self.logger.save_state({
                'account': account,
                'final_state': final_state,
                'events': debug_browser.events,
                'screenshots': debug_browser.screenshots_taken
            }, 'test_flow_result.json')
            
            await browser.close()
            
            self.logger.success_logger.info("Test flow completed successfully")
            return True
            
        except Exception as e:
            self.logger.error_logger.error(f"Full flow test failed: {e}")
            self.logger.error_logger.error(traceback.format_exc())
            return False

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN DEBUG RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

async def run_debug_suite(args):
    """Run comprehensive debug suite"""
    
    # Initialize debug logger
    debug_logger = DebugLogger(args.log_dir)
    
    print(f"""
    ╔═══════════════════════════════════════════════════════════════╗
    ║          STEALTH ACCOUNT CREATOR - DEBUG MODE                ║
    ║                                                               ║
    ║  Session ID: {debug_logger.session_id}                              ║
    ║  Log Directory: {debug_logger.session_dir}                      ║
    ║  Mode: {'MOCK' if args.use_mocks else 'REAL'} Services                                   ║
    ║  Headless: {args.headless}                                        ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Set environment for headless
    if args.headless:
        os.environ['HEADLESS_MODE'] = '1'
    
    # Initialize debug creator
    debug_creator = DebugAccountCreator(debug_logger, use_mocks=args.use_mocks)
    
    # Run selected tests
    test_results = {}
    
    if args.test_browser or args.test_all:
        result = await debug_creator.test_browser_launch()
        test_results['browser_launch'] = result
        
    if args.test_cloudflare or args.test_all:
        result = await debug_creator.test_cloudflare_detection()
        test_results['cloudflare'] = result
        
    if args.test_elements or args.test_all:
        result = await debug_creator.test_twitter_elements()
        test_results['twitter_elements'] = result
        
    if args.test_flow or args.test_all:
        result = await debug_creator.test_full_account_flow(dry_run=args.dry_run)
        test_results['full_flow'] = result
    
    # Generate report
    print("\n" + "=" * 60)
    print("DEBUG SUITE RESULTS")
    print("=" * 60)
    
    for test_name, result in test_results.items():
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{test_name:20} {status}")
    
    # Save final report
    debug_logger.save_state({
        'session_id': debug_logger.session_id,
        'timestamp': datetime.now().isoformat(),
        'args': vars(args),
        'test_results': test_results
    }, 'debug_report.json')
    
    print(f"\n📁 Debug logs saved to: {debug_logger.session_dir}")
    print("✨ Debug suite complete!")

def main():
    """Main entry point"""
    parser = argparse.ArgumentParser(
        description="Debug script for stealth account creator"
    )
    
    # General options
    parser.add_argument('--headless', action='store_true', 
                       help='Run browsers in headless mode')
    parser.add_argument('--use-mocks', action='store_true',
                       help='Use mock services instead of real APIs')
    parser.add_argument('--log-dir', default='debug_logs',
                       help='Directory for debug logs')
    
    # Test selection
    parser.add_argument('--test-all', action='store_true',
                       help='Run all tests')
    parser.add_argument('--test-browser', action='store_true',
                       help='Test browser launch')
    parser.add_argument('--test-cloudflare', action='store_true',
                       help='Test Cloudflare detection')
    parser.add_argument('--test-elements', action='store_true',
                       help='Test Twitter element detection')
    parser.add_argument('--test-flow', action='store_true',
                       help='Test full account creation flow')
    
    # Flow options
    parser.add_argument('--dry-run', action='store_true',
                       help='Dry run mode (no actual account creation)')
    
    # Environment overrides
    parser.add_argument('--mock-captcha-fail', action='store_true',
                       help='Force CAPTCHA failures for testing')
    parser.add_argument('--mock-sms-fail', action='store_true',
                       help='Force SMS failures for testing')
    
    args = parser.parse_args()
    
    # Set environment variables for mocking
    if args.mock_captcha_fail:
        os.environ['MOCK_CAPTCHA_FAIL'] = '1'
    if args.mock_sms_fail:
        os.environ['MOCK_SMS_FAIL'] = '1'
    
    # Default to test-all if no specific test selected
    if not any([args.test_browser, args.test_cloudflare, 
                args.test_elements, args.test_flow]):
        args.test_all = True
    
    # Run async debug suite
    asyncio.run(run_debug_suite(args))

if __name__ == "__main__":
    main()
