#!/usr/bin/env python3
"""
ULTIMATE STEALTH CORE - ENHANCED VERSION
Robust account creation system with proxy reliability improvements
"""

import os
import sys
import json
import random
import asyncio
import logging
import hashlib
import time
import re
import imaplib
import email
import traceback
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum, auto
from faker import Faker

# ============================================================================
# PACKAGE MANAGEMENT
# ============================================================================

def ensure_packages():
    """Ensure all required packages are installed"""
    packages = {
        'aiohttp': 'aiohttp',
        'playwright': 'playwright',
        'faker': 'Faker',
        'dotenv': 'python-dotenv',
        'colorama': 'colorama',
        'rich': 'rich'
    }
    
    for import_name, install_name in packages.items():
        try:
            __import__(import_name)
        except ImportError:
            print(f"Installing {install_name}...")
            import subprocess
            subprocess.check_call([sys.executable, "-m", "pip", "install", install_name])

ensure_packages()

import aiohttp
from playwright.async_api import async_playwright, Page, Browser, BrowserContext
from dotenv import load_dotenv
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, SpinnerColumn, TextColumn
from colorama import init, Fore, Style

# Initialize colorama and rich
init(autoreset=True)
console = Console()

# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================

class ColoredFormatter(logging.Formatter):
    """Custom colored formatter for better visibility"""
    
    COLORS = {
        'DEBUG': Fore.CYAN,
        'INFO': Fore.GREEN,
        'WARNING': Fore.YELLOW,
        'ERROR': Fore.RED,
        'CRITICAL': Fore.RED + Style.BRIGHT
    }
    
    def format(self, record):
        log_color = self.COLORS.get(record.levelname, '')
        record.levelname = f"{log_color}{record.levelname}{Style.RESET_ALL}"
        record.msg = f"{log_color}{record.msg}{Style.RESET_ALL}"
        return super().format(record)

def setup_logging(debug: bool = False):
    """Setup enhanced logging with colors"""
    log_level = logging.DEBUG if debug else logging.INFO
    
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(ColoredFormatter(
        '%(asctime)s - %(levelname)s - [%(funcName)s:%(lineno)d] %(message)s'
    ))
    
    Path("logs").mkdir(exist_ok=True)
    file_handler = logging.FileHandler(f'logs/stealth_core_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log')
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - [%(funcName)s:%(lineno)d] %(message)s'
    ))
    
    logging.basicConfig(
        level=log_level,
        handlers=[console_handler, file_handler]
    )
    
    return logging.getLogger(__name__)

logger = setup_logging()

# ============================================================================
# CONFIGURATION
# ============================================================================

@dataclass
class StealthConfig:
    """Central configuration for all operations"""
    
    # Browser settings
    headless: bool = False
    slow_mo: int = 50
    timeout: int = 60000  # Increased timeout
    viewport_width: int = 1920
    viewport_height: int = 1080
    
    # Stealth settings
    use_stealth: bool = True
    use_proxies: bool = False
    rotate_proxy_on_fail: bool = True
    proxy_retry_count: int = 3  # Max retries per proxy
    
    # Proxy configuration
    proxy_list: List[str] = field(default_factory=list)
    current_proxy_index: int = 0
    
    # API Keys
    capsolver_api_key: Optional[str] = None
    twocaptcha_api_key: Optional[str] = None
    anticaptcha_api_key: Optional[str] = None
    sms_activate_key: Optional[str] = None
    fivesim_key: Optional[str] = None
    smsman_key: Optional[str] = None
    openai_api_key: Optional[str] = None
    claude_api_key: Optional[str] = None
    gemini_api_key: Optional[str] = None
    deepseek_api_key: Optional[str] = None
    grok_api_key: Optional[str] = None
    gmail_app_password: Optional[str] = None
    gmail_recovery_email: Optional[str] = None
    
    # Rate limiting
    min_action_delay: float = 1.0
    max_action_delay: float = 3.0
    min_typing_delay: float = 0.05
    max_typing_delay: float = 0.15
    
    # Retry settings
    max_retries: int = 3
    retry_delay: int = 5
    
    # Paths
    data_dir: Path = field(default_factory=lambda: Path("data"))
    accounts_dir: Path = field(default_factory=lambda: Path("accounts"))
    screenshots_dir: Path = field(default_factory=lambda: Path("screenshots"))
    sessions_dir: Path = field(default_factory=lambda: Path("sessions"))
    
    @classmethod
    def from_env(cls) -> 'StealthConfig':
        """Load configuration from environment variables"""
        load_dotenv()
        
        config = cls()
        config.headless = os.getenv("HEADLESS_MODE", "false").lower() == "true"
        config.slow_mo = int(os.getenv("SLOW_MO", "50"))
        
        proxy_env = os.getenv("PROXY_LIST", "")
        if proxy_env:
            config.proxy_list = [p.strip() for p in proxy_env.split(",") if p.strip()]
        elif Path("proxies.txt").exists():
            with open("proxies.txt") as f:
                config.proxy_list = [line.strip() for line in f if line.strip()]
        
        config.use_proxies = len(config.proxy_list) > 0
        
        # Load API keys
        config.capsolver_api_key = os.getenv("CAPSOLVER_API_KEY")
        config.twocaptcha_api_key = os.getenv("TWOCAPTCHA_API_KEY")
        config.anticaptcha_api_key = os.getenv("ANTICAPTCHA_API_KEY")
        config.sms_activate_key = os.getenv("SMS_ACTIVATE_API_KEY")
        config.fivesim_key = os.getenv("FIVESIM_API_KEY")
        config.smsman_key = os.getenv("SMSMAN_API_KEY")
        config.openai_api_key = os.getenv("OPENAI_API_KEY")
        config.claude_api_key = os.getenv("CLAUDE_API_KEY")
        config.gemini_api_key = os.getenv("GEMINI_API_KEY")
        config.deepseek_api_key = os.getenv("DEEPSEEK_API_KEY")
        config.grok_api_key = os.getenv("GROK_LLM_API_KEY")
        config.gmail_app_password = os.getenv("GMAIL_APP_PASSWORD")
        config.gmail_recovery_email = os.getenv("GMAIL_RECOVERY_EMAIL")
        
        for dir_path in [config.data_dir, config.accounts_dir, config.screenshots_dir, config.sessions_dir]:
            dir_path.mkdir(exist_ok=True)
        
        return config
    
    def get_next_proxy(self) -> Optional[str]:
        """Get next proxy from the list"""
        if not self.proxy_list:
            return None
        
        proxy = self.proxy_list[self.current_proxy_index]
        self.current_proxy_index = (self.current_proxy_index + 1) % len(self.proxy_list)
        return proxy

# ============================================================================
# ACCOUNT DATA MODELS
# ============================================================================

@dataclass
class AccountProfile:
    """Profile data for account creation"""
    first_name: str
    last_name: str
    username: str
    email: str
    password: str
    birth_date: datetime
    gender: str
    country: str = "US"
    language: str = "en"
    timezone: str = "America/New_York"
    
    @property
    def full_name(self) -> str:
        return f"{self.first_name} {self.last_name}"
    
    @property
    def birth_year(self) -> str:
        return str(self.birth_date.year)
    
    @property
    def birth_month(self) -> str:
        return str(self.birth_date.month)
    
    @property
    def birth_day(self) -> str:
        return str(self.birth_date.day)

@dataclass
class GmailAccount:
    """Gmail account data"""
    profile: AccountProfile
    created_at: datetime
    success: bool
    error: Optional[str] = None
    session_file: Optional[str] = None
    godel_number: Optional[int] = None
    assigned_api: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'email': self.profile.email,
            'password': self.profile.password,
            'username': self.profile.username,
            'first_name': self.profile.first_name,
            'last_name': self.profile.last_name,
            'birth_date': self.profile.birth_date.isoformat(),
            'created_at': self.created_at.isoformat(),
            'success': self.success,
            'error': self.error,
            'session_file': self.session_file,
            'godel_number': self.godel_number,
            'assigned_api': self.assigned_api
        }

@dataclass
class TwitterAccount:
    """Twitter account data"""
    profile: AccountProfile
    gmail_account: GmailAccount
    twitter_username: Optional[str]
    created_at: datetime
    success: bool
    error: Optional[str] = None
    session_file: Optional[str] = None
    godel_number: Optional[int] = None
    assigned_api: Optional[str] = None
    
    def to_dict(self) -> dict:
        return {
            'twitter_username': self.twitter_username,
            'email': self.profile.email,
            'password': self.profile.password,
            'gmail_password': self.gmail_account.profile.password,
            'first_name': self.profile.first_name,
            'last_name': self.profile.last_name,
            'created_at': self.created_at.isoformat(),
            'success': self.success,
            'error': self.error,
            'session_file': self.session_file,
            'godel_number': self.godel_number,
            'assigned_api': self.assigned_api
        }

# ============================================================================
# PROFILE GENERATOR
# ============================================================================

class ProfileGenerator:
    """Generate realistic account profiles"""
    
    def __init__(self):
        self.faker = Faker()
        self.used_usernames = set()
        self.used_emails = set()
    
    def generate_profile(self) -> AccountProfile:
        first_name = self.faker.first_name()
        last_name = self.faker.last_name()
        
        base_username = f"{first_name.lower()}{last_name.lower()}"
        username = self._make_unique_username(base_username)
        
        email = f"{username}@gmail.com"
        while email in self.used_emails:
            username = self._make_unique_username(base_username)
            email = f"{username}@gmail.com"
        
        self.used_usernames.add(username)
        self.used_emails.add(email)
        
        birth_date = self.faker.date_of_birth(minimum_age=21, maximum_age=45)
        gender = random.choice(['male', 'female', 'other'])
        password = self._generate_password()
        
        return AccountProfile(
            first_name=first_name,
            last_name=last_name,
            username=username,
            email=email,
            password=password,
            birth_date=birth_date,
            gender=gender
        )
    
    def _make_unique_username(self, base: str) -> str:
        random_suffix = random.randint(10000, 99999)
        username = f"{base}{random_suffix}"
        
        while username in self.used_usernames:
            random_suffix = random.randint(10000, 99999)
            username = f"{base}{random_suffix}"
        
        return username
    
    def _generate_password(self) -> str:
        import string
        lowercase = random.choice(string.ascii_lowercase)
        uppercase = random.choice(string.ascii_uppercase)
        digit = random.choice(string.digits)
        special = random.choice("!@#$%^&*")
        
        remaining_length = 12
        remaining_chars = ''.join(random.choices(
            string.ascii_letters + string.digits + "!@#$%^&*",
            k=remaining_length
        ))
        
        password = lowercase + uppercase + digit + special + remaining_chars
        password_list = list(password)
        random.shuffle(password_list)
        
        return ''.join(password_list)

# ============================================================================
# GÖDEL NUMBER SYSTEM
# ============================================================================

class GodelSystem:
    """Gödel number generation and API assignment"""
    
    def __init__(self, config: StealthConfig):
        self.config = config
        self.api_mapping = self._setup_api_mapping()
    
    def _setup_api_mapping(self) -> Dict[str, Dict]:
        mapping = {}
        
        if self.config.claude_api_key:
            mapping['claude'] = {
                'key': self.config.claude_api_key,
                'range': (950_000_000, 999_999_999),
                'weight': 0.25
            }
        
        if self.config.openai_api_key:
            mapping['openai'] = {
                'key': self.config.openai_api_key,
                'range': (900_000_000, 949_999_999),
                'weight': 0.20
            }
        
        if self.config.deepseek_api_key:
            mapping['deepseek'] = {
                'key': self.config.deepseek_api_key,
                'range': (850_000_000, 899_999_999),
                'weight': 0.20
            }
        
        if self.config.gemini_api_key:
            mapping['gemini'] = {
                'key': self.config.gemini_api_key,
                'range': (800_000_000, 849_999_999),
                'weight': 0.20
            }
        
        if self.config.grok_api_key:
            mapping['grok'] = {
                'key': self.config.grok_api_key,
                'range': (750_000_000, 799_999_999),
                'weight': 0.15
            }
        
        return mapping
    
    def generate_godel_number(self, seed: str) -> int:
        hash_val = int(hashlib.sha256(seed.encode()).hexdigest(), 16)
        godel = 750_000_000 + (hash_val % 249_999_999)
        return godel
    
    def assign_api(self, godel_number: int) -> Tuple[Optional[str], Optional[str]]:
        if not self.api_mapping:
            return None, None
        
        for api_name, api_config in self.api_mapping.items():
            min_range, max_range = api_config['range']
            if min_range <= godel_number <= max_range:
                return api_name, api_config['key']
        
        api_names = list(self.api_mapping.keys())
        selected = api_names[godel_number % len(api_names)]
        return selected, self.api_mapping[selected]['key']

# ============================================================================
# STEALTH BROWSER - IMPROVED PROXY HANDLING
# ============================================================================

class StealthBrowser:
    """Enhanced stealth browser with reliable proxy support"""
    
    def __init__(self, config: StealthConfig, proxy: Optional[str] = None):
        self.config = config
        self.proxy = proxy
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
    
    async def launch(self):
        """Launch browser with robust proxy handling"""
        logger.info("🚀 Launching browser...")
        
        try:
            self.playwright = await async_playwright().start()
            logger.info("✅ Playwright started")
        except Exception as e:
            logger.error(f"❌ Playwright failed: {e}")
            raise
        
        # Browser launch arguments
        args = [
            '--disable-blink-features=AutomationControlled',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-dev-shm-usage',
            f'--window-size={self.config.viewport_width},{self.config.viewport_height}',
            '--start-maximized',
            '--disable-infobars',
            '--mute-audio',
            '--disable-background-timer-throttling',
            '--disable-backgrounding-occluded-windows',
            '--disable-renderer-backgrounding',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--password-store=basic',
            '--use-mock-keychain',
            '--disable-features=IsolateOrigins,site-per-process',
            '--disable-site-isolation-trials',
            '--disable-features=BlockInsecurePrivateNetworkRequests',
            '--ignore-certificate-errors',
            '--ignore-ssl-errors'
        ]
        
        browser_launched = False
        
        # Try Chrome first
        try:
            logger.info("🔍 Launching Chrome...")
            self.browser = await self.playwright.chromium.launch(
                channel='chrome',
                headless=self.config.headless,
                args=args,
                ignore_default_args=['--enable-automation'],
                slow_mo=self.config.slow_mo
            )
            logger.info("✅ Chrome launched")
            browser_type = "Chrome"
            browser_launched = True
        except Exception as e:
            logger.warning(f"⚠️ Chrome failed: {e}")
        
        # Try Chromium if Chrome failed
        if not browser_launched:
            try:
                logger.info("🔍 Launching Chromium...")
                self.browser = await self.playwright.chromium.launch(
                    headless=self.config.headless,
                    args=args,
                    ignore_default_args=['--enable-automation'],
                    slow_mo=self.config.slow_mo
                )
                logger.info("✅ Chromium launched")
                browser_type = "Chromium"
                browser_launched = True
            except Exception as e:
                logger.warning(f"⚠️ Chromium failed: {e}")
        
        # Try Firefox as last resort
        if not browser_launched:
            try:
                logger.info("🔍 Launching Firefox...")
                self.browser = await self.playwright.firefox.launch(
                    headless=self.config.headless,
                    slow_mo=self.config.slow_mo
                )
                logger.info("✅ Firefox launched")
                browser_type = "Firefox"
                browser_launched = True
            except Exception as e:
                logger.error(f"❌ Firefox failed: {e}")
                raise Exception("No browser launched. Run: playwright install")
        
        logger.info(f"📊 Browser: {browser_type}, Headless: {self.config.headless}")
        
        viewport = self._get_random_viewport()
        
        context_options = {
            'viewport': viewport,
            'screen': viewport,
            'user_agent': self._get_user_agent(),
            'locale': 'en-US',
            'timezone_id': self._get_random_timezone(),
            'device_scale_factor': 1,
            'is_mobile': False,
            'has_touch': False
        }
        
        # Enhanced proxy handling
        if self.proxy and self.config.use_proxies:
            proxy_dict = self._parse_proxy(self.proxy)
            context_options['proxy'] = proxy_dict
            logger.info(f"🌐 Using proxy: {self.proxy[:30]}...")
            # Set longer timeouts for proxy connections
            context_options['timeout'] = 180000  # 3 minutes
        
        try:
            self.context = await self.browser.new_context(**context_options)
            logger.info("✅ Context created")
        except Exception as e:
            logger.error(f"❌ Context failed: {e}")
            raise
        
        # Add stealth scripts
        if self.config.use_stealth:
            await self.context.add_init_script(self._get_stealth_script())
            logger.info("🛡️ Stealth injected")
        
        try:
            self.page = await self.context.new_page()
            logger.info("✅ Page created")
            
            # Set extended timeouts for proxy
            if self.proxy and self.config.use_proxies:
                self.page.set_default_timeout(120000)
                self.page.set_default_navigation_timeout(180000)
                logger.info("Extended timeouts for proxy")
        except Exception as e:
            logger.error(f"❌ Page failed: {e}")
            raise
        
        # Set headers
        await self.page.set_extra_http_headers({
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8'
        })
        
        # Add debug listeners
        self.page.on("console", lambda msg: logger.debug(f"Console: {msg.text}"))
        self.page.on("pageerror", lambda err: logger.error(f"Page error: {err}"))
        self.page.on("requestfailed", lambda req: logger.warning(f"Request failed: {req.url} | Reason: {req.failure}"))
        
        logger.info(f"✅ Browser ready!")

    # Existing helper methods (_get_user_agent, _get_random_viewport, etc.)
    # Remain unchanged from original implementation
    
    async def human_type(self, selector: str, text: str, clear_first: bool = True):
        """Type text with human-like behavior"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=5000)
            
            if element:
                is_visible = await element.is_visible()
                is_enabled = await element.is_enabled()
                
                if not is_visible or not is_enabled:
                    logger.debug(f"Element {selector} not interactable")
                    return False
                
                if clear_first:
                    await element.click()
                    await element.press("Control+a")
                    await element.press("Delete")
                
                for char in text:
                    await element.type(char)
                    delay = random.uniform(self.config.min_typing_delay, self.config.max_typing_delay)
                    await asyncio.sleep(delay)
                
                return True
            return False
            
        except Exception as e:
            logger.debug(f"Typing failed: {str(e)[:100]}")
            return False
    
    async def human_click(self, selector: str) -> bool:
        """Click with human-like behavior"""
        try:
            element = await self.page.wait_for_selector(selector, timeout=3000)
            box = await element.bounding_box()
            if box:
                x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
                y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
                await self.page.mouse.move(x, y)
                await asyncio.sleep(random.uniform(0.1, 0.3))
            
            await element.click()
            return True
        except Exception as e:
            logger.debug(f"Click failed: {str(e)[:50]}")
            return False
    
    async def wait_randomly(self):
        """Random wait between actions"""
        delay = random.uniform(self.config.min_action_delay, self.config.max_action_delay)
        await asyncio.sleep(delay)
    
    async def screenshot(self, name: str = None) -> str:
        """Take screenshot"""
        if not name:
            name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        path = self.config.screenshots_dir / f"{name}.png"
        await self.page.screenshot(path=str(path), full_page=True)
        logger.debug(f"📸 Screenshot: {path}")
        return str(path)
    
    async def save_session(self, name: str) -> str:
        """Save browser session"""
        path = self.config.sessions_dir / f"{name}_session.json"
        await self.context.storage_state(path=str(path))
        logger.debug(f"💾 Session saved: {path}")
        return str(path)
    
    async def load_session(self, path: str) -> bool:
        """Load browser session"""
        try:
            if Path(path).exists():
                await self.context.close()
                self.context = await self.browser.new_context(storage_state=path)
                self.page = await self.context.new_page()
                logger.debug(f"📂 Session loaded: {path}")
                return True
        except Exception as e:
            logger.error(f"Session load failed: {e}")
        return False
    
    async def close(self):
        """Close browser resources"""
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
    
    async def check_page_loaded(self, timeout: int = 30) -> bool:
        """Check if page has loaded content"""
        start_time = time.time()
        while time.time() - start_time < timeout:
            content = await self.page.content()
            if len(content.strip()) > 100 and "<body>" in content:
                return True
            await asyncio.sleep(1)
        return False

# ============================================================================
# GMAIL ACCOUNT CREATOR - IMPROVED NAVIGATION
# ============================================================================

class GmailCreator:
    """Gmail account creation with reliable navigation"""
    
    def __init__(self, browser: StealthBrowser, config: StealthConfig):
        self.browser = browser
        self.config = config
        self.profile_generator = ProfileGenerator()
    
    async def create_account(self, profile: Optional[AccountProfile] = None) -> GmailAccount:
        """Create Gmail account with robust navigation"""
        if not profile:
            profile = self.profile_generator.generate_profile()
        
        logger.info(f"📧 Creating Gmail: {profile.email}")
        account = GmailAccount(
            profile=profile,
            created_at=datetime.now(),
            success=False
        )
        
        try:
            # Attempt navigation with retries
            navigation_success = await self._navigate_to_signup()
            if not navigation_success:
                raise Exception("Gmail signup page navigation failed")
            
            # Account creation steps
            if not await self._fill_basic_info(profile):
                raise Exception("Basic info failed")
            
            if not await self._fill_personal_info(profile):
                raise Exception("Personal info failed")
            
            if not await self._choose_email(profile):
                raise Exception("Email selection failed")
            
            if not await self._set_password(profile):
                raise Exception("Password setup failed")
            
            logger.info("⏳ Finalizing account...")
            await asyncio.sleep(random.uniform(5, 8))
            
            await self._handle_verification()
            await self._accept_terms()
            
            # Save session
            session_file = await self.browser.save_session(f"gmail_{profile.username}")
            account.session_file = session_file
            
            # Generate Gödel number
            godel_system = GodelSystem(self.config)
            account.godel_number = godel_system.generate_godel_number(profile.email)
            account.assigned_api, _ = godel_system.assign_api(account.godel_number)
            
            account.success = True
            logger.info(f"✅ Gmail created: {profile.email}")
            
        except Exception as e:
            account.error = str(e)
            logger.error(f"❌ Gmail failed: {e}")
            await self.browser.screenshot(f"gmail_error_{profile.username}")
        
        return account
    
    async def _navigate_to_signup(self) -> bool:
        """Robust navigation to signup page with proxy handling"""
        signup_urls = [
            "https://accounts.google.com/signup/v2/webcreateaccount?flowName=GlifWebSignIn&flowEntry=SignUp",
            "https://accounts.google.com/signup",
            "https://accounts.google.com/SignUp"
        ]
        
        for url_idx, url in enumerate(signup_urls):
            logger.info(f"🌐 Attempting URL {url_idx+1}/{len(signup_urls)}: {url}")
            
            try:
                # Attempt navigation with extended timeout
                timeout = 180000 if self.browser.proxy else 90000
                await self.browser.page.goto(url, wait_until='domcontentloaded', timeout=timeout)
                
                # Verify page actually loaded
                if not await self.browser.check_page_loaded():
                    logger.warning("Page content not detected, reloading...")
                    await self.browser.page.reload(wait_until='domcontentloaded', timeout=timeout)
                    await asyncio.sleep(3)
                
                # Check if we're on sign-in page
                current_url = self.browser.page.url
                if "signin" in current_url.lower() or "identifier" in current_url.lower():
                    logger.info("Redirected to sign-in, clicking 'Create account'")
                    try:
                        create_btn = await self.browser.page.wait_for_selector(
                            'span:has-text("Create account"), text="Create account"',
                            timeout=10000
                        )
                        if create_btn:
                            await create_btn.click()
                            await asyncio.sleep(2)
                            
                            # Handle "For myself" option
                            try:
                                personal_option = await self.browser.page.wait_for_selector(
                                    'div:has-text("For my personal use"), div:has-text("For myself")',
                                    timeout=5000
                                )
                                if personal_option:
                                    await personal_option.click()
                                    await asyncio.sleep(2)
                            except:
                                logger.debug("No personal option found")
                    except:
                        logger.warning("Create account button not found")
                
                # Verify form elements exist
                first_name_field = await self.browser.page.wait_for_selector(
                    '#firstName, input[name="firstName"]',
                    timeout=15000
                )
                if first_name_field:
                    logger.info("✅ Signup form loaded")
                    return True
                
            except Exception as e:
                logger.warning(f"Navigation attempt failed: {str(e)[:200]}")
                await self.browser.screenshot(f"nav_fail_{url_idx}")
        
        logger.error("All navigation attempts failed")
        return False

    # Existing account creation methods (_fill_basic_info, etc.)
    # Remain unchanged from original implementation

# ============================================================================
# TWITTER ACCOUNT CREATOR
# ============================================================================

class TwitterCreator:
    """Twitter account creation using Gmail"""
    
    def __init__(self, browser: StealthBrowser, config: StealthConfig):
        self.browser = browser
        self.config = config
    
    async def create_account(self, gmail_account: GmailAccount) -> TwitterAccount:
        profile = gmail_account.profile
        logger.info(f"🐦 Creating Twitter: {profile.email}")
        
        account = TwitterAccount(
            profile=profile,
            gmail_account=gmail_account,
            twitter_username=None,
            created_at=datetime.now(),
            success=False
        )
        
        try:
            # Attempt Twitter navigation
            if not await self._navigate_to_twitter_signup():
                raise Exception("Twitter signup page navigation failed")
            
            # Account creation steps
            await self._fill_initial_signup(profile)
            await self._fill_birthdate(profile)
            await self._handle_customization()
            await self._confirm_signup()
            await self._handle_verification(profile)
            await self._set_password(profile)
            await self._complete_onboarding()
            
            # Get username
            username = await self._get_username()
            account.twitter_username = username
            
            # Save session
            session_file = await self.browser.save_session(f"twitter_{username}")
            account.session_file = session_file
            
            # Inherit Gödel from Gmail
            account.godel_number = gmail_account.godel_number
            account.assigned_api = gmail_account.assigned_api
            
            account.success = True
            logger.info(f"✅ Twitter created: @{username}")
            
        except Exception as e:
            account.error = str(e)
            logger.error(f"❌ Twitter failed: {e}")
            await self.browser.screenshot(f"twitter_error_{profile.username}")
        
        return account
    
    async def _navigate_to_twitter_signup(self) -> bool:
        """Robust navigation to Twitter signup"""
        urls_to_try = [
            "https://twitter.com/i/flow/signup",
            "https://x.com/i/flow/signup"
        ]
        
        for url in urls_to_try:
            logger.info(f"🌐 Attempting Twitter URL: {url}")
            try:
                await self.browser.page.goto(url, wait_until='domcontentloaded', timeout=60000)
                await asyncio.sleep(3)
                
                # Verify page loaded
                if not await self.browser.check_page_loaded():
                    logger.warning("Twitter page content not detected, reloading...")
                    await self.browser.page.reload(wait_until='domcontentloaded', timeout=60000)
                    await asyncio.sleep(5)
                
                content = await self.browser.page.content()
                if ("create" in content.lower() or "sign up" in content.lower()) and \
                   "browser is no longer supported" not in content.lower():
                    logger.info("✅ Twitter signup loaded")
                    return True
                
                await self._handle_challenges()
                
            except Exception as e:
                logger.warning(f"Twitter navigation failed: {str(e)[:200]}")
        
        logger.error("All Twitter navigation attempts failed")
        return False

    # Existing Twitter creation methods remain unchanged

# ============================================================================
# ACCOUNT MANAGER
# ============================================================================

class AccountManager:
    """Manage created accounts with persistence"""
    
    def __init__(self, config: StealthConfig):
        self.config = config
        self.gmail_db = config.accounts_dir / "gmail_accounts.json"
        self.twitter_db = config.accounts_dir / "twitter_accounts.json"
        self._ensure_files()
    
    def _ensure_files(self):
        for db_file in [self.gmail_db, self.twitter_db]:
            if not db_file.exists():
                with open(db_file, 'w') as f:
                    json.dump([], f)
    
    def save_gmail_account(self, account: GmailAccount):
        accounts = self.load_gmail_accounts()
        accounts.append(account.to_dict())
        with open(self.gmail_db, 'w') as f:
            json.dump(accounts, f, indent=2)
        
        txt_file = self.config.accounts_dir / "gmail_credentials.txt"
        with open(txt_file, 'a') as f:
            f.write(f"Email: {account.profile.email}\n")
            f.write(f"Password: {account.profile.password}\n")
            f.write(f"Gödel: {account.godel_number}\n")
            f.write(f"API: {account.assigned_api}\n")
            f.write(f"Created: {account.created_at}\n")
            f.write("-" * 50 + "\n")
    
    def save_twitter_account(self, account: TwitterAccount):
        accounts = self.load_twitter_accounts()
        accounts.append(account.to_dict())
        with open(self.twitter_db, 'w') as f:
            json.dump(accounts, f, indent=2)
        
        txt_file = self.config.accounts_dir / "twitter_credentials.txt"
        with open(txt_file, 'a') as f:
            f.write(f"Username: @{account.twitter_username}\n")
            f.write(f"Email: {account.profile.email}\n")
            f.write(f"Password: {account.profile.password}\n")
            f.write(f"Gmail Password: {account.gmail_account.profile.password}\n")
            f.write(f"Gödel: {account.godel_number}\n")
            f.write(f"API: {account.assigned_api}\n")
            f.write(f"Created: {account.created_at}\n")
            f.write("-" * 50 + "\n")
    
    def load_gmail_accounts(self) -> List[dict]:
        try:
            with open(self.gmail_db, 'r') as f:
                return json.load(f)
        except:
            return []
    
    def load_twitter_accounts(self) -> List[dict]:
        try:
            with open(self.twitter_db, 'r') as f:
                return json.load(f)
        except:
            return []

# ============================================================================
# MAIN ORCHESTRATOR
# ============================================================================

class UltimateStealthCore:
    """Main orchestrator with proxy rotation"""
    
    def __init__(self):
        self.config = StealthConfig.from_env()
        self.account_manager = AccountManager(self.config)
        self.profile_generator = ProfileGenerator()
        self.godel_system = GodelSystem(self.config)
    
    async def create_account_pair(self) -> Tuple[Optional[GmailAccount], Optional[TwitterAccount]]:
        console.print("\n[bold cyan]Step 1: Creating Gmail[/bold cyan]")
        
        proxy = self.config.get_next_proxy() if self.config.use_proxies else None
        browser = StealthBrowser(self.config, proxy)
        gmail_account = None
        
        try:
            await browser.launch()
            gmail_creator = GmailCreator(browser, self.config)
            gmail_account = await gmail_creator.create_account()
            
            if gmail_account.success:
                self.account_manager.save_gmail_account(gmail_account)
                console.print(f"[green]✅ Gmail: {gmail_account.profile.email}[/green]")
            else:
                console.print(f"[red]❌ Gmail failed: {gmail_account.error}[/red]")
                return None, None
                
        except Exception as e:
            logger.error(f"Gmail creation crashed: {e}")
            return None, None
        finally:
            await browser.close()
        
        # Inter-account delay
        wait_time = random.randint(30, 60)
        console.print(f"[yellow]⏳ Waiting {wait_time}s...[/yellow]")
        await asyncio.sleep(wait_time)
        
        console.print("\n[bold cyan]Step 2: Creating Twitter[/bold cyan]")
        
        proxy = self.config.get_next_proxy() if self.config.use_proxies else None
        browser = StealthBrowser(self.config, proxy)
        twitter_account = None
        
        try:
            await browser.launch()
            twitter_creator = TwitterCreator(browser, self.config)
            twitter_account = await twitter_creator.create_account(gmail_account)
            
            if twitter_account.success:
                self.account_manager.save_twitter_account(twitter_account)
                console.print(f"[green]✅ Twitter: @{twitter_account.twitter_username}[/green]")
            else:
                console.print(f"[red]❌ Twitter failed: {twitter_account.error}[/red]")
                
        except Exception as e:
            logger.error(f"Twitter creation crashed: {e}")
        finally:
            await browser.close()
        
        return gmail_account, twitter_account
    
    async def run_batch(self, count: int):
        """Create multiple account pairs"""
        table = Table(title="Ultimate Stealth Core")
        table.add_column("Setting", style="cyan")
        table.add_column("Value", style="green")
        table.add_row("Accounts", str(count))
        table.add_row("Headless", str(self.config.headless))
        table.add_row("Proxies", str(len(self.config.proxy_list)))
        table.add_row("APIs", str(len(self.godel_system.api_mapping)))
        console.print(table)
        
        successful_gmail = 0
        successful_twitter = 0
        failed = 0
        
        with Progress() as progress:
            task = progress.add_task("[cyan]Creating accounts...", total=count)
            
            for i in range(count):
                console.print(f"\n[bold]Account Pair {i+1}/{count}[/bold]")
                
                try:
                    gmail, twitter = await self.create_account_pair()
                    
                    if gmail and gmail.success:
                        successful_gmail += 1
                    if twitter and twitter.success:
                        successful_twitter += 1
                    if not (gmail and gmail.success):
                        failed += 1
                    
                    progress.update(task, advance=1)
                    
                    # Inter-pair delay
                    if i < count - 1:
                        wait_time = random.randint(60, 120)
                        console.print(f"[yellow]⏳ Waiting {wait_time}s before next pair...[/yellow]")
                        await asyncio.sleep(wait_time)
                    
                except Exception as e:
                    logger.error(f"Account pair error: {e}")
                    failed += 1
                    progress.update(task, advance=1)
        
        # Final report
        table = Table(title="Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Count", style="green")
        table.add_row("Gmail Success", str(successful_gmail))
        table.add_row("Twitter Success", str(successful_twitter))
        table.add_row("Failed", str(failed))
        table.add_row("Total Attempted", str(count))
        
        console.print("\n")
        console.print(table)
        console.print("\n[bold cyan]📁 Output files:[/bold cyan]")
        console.print(f"  • {self.config.accounts_dir}/gmail_accounts.json")
        console.print(f"  • {self.config.accounts_dir}/twitter_accounts.json")
        console.print(f"  • {self.config.accounts_dir}/gmail_credentials.txt")
        console.print(f"  • {self.config.accounts_dir}/twitter_credentials.txt")

# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Ultimate Stealth Core - Advanced Account Creation"
    )
    parser.add_argument('--count', type=int, default=1, help='Number of account pairs to create')
    parser.add_argument('--headless', action='store_true', help='Run in headless mode')
    parser.add_argument('--debug', action='store_true', help='Enable debug logging')
    
    args = parser.parse_args()
    
    # Update configuration
    if args.headless:
        os.environ['HEADLESS_MODE'] = 'true'
    
    # Setup debug logging if requested
    if args.debug:
        global logger
        logger = setup_logging(debug=True)
    
    # Display banner
    console.print("""
[bold cyan]╔════════════════════════════════════════════════════════════════╗
║              ULTIMATE STEALTH CORE - ENHANCED                ║
║                                                                ║
║  Reliable Account Creation System:                            ║
║  • Proxy stability improvements                               ║
║  • Robust navigation handling                                 ║
║  • Enhanced error recovery                                    ║
╚════════════════════════════════════════════════════════════════╝[/bold cyan]
""")
    
    # Check Playwright
    try:
        p = await async_playwright().start()
        browser = await p.chromium.launch(headless=True)
        await browser.close()
        await p.stop()
        console.print("[green]✅ Playwright verified[/green]\n")
    except Exception as e:
        console.print(f"[red]❌ Playwright error: {e}[/red]")
        console.print("[yellow]Run: python -m playwright install chromium[/yellow]")
        return
    
    # Run the system
    core = UltimateStealthCore()
    await core.run_batch(args.count)

if __name__ == "__main__":
    asyncio.run(main())
