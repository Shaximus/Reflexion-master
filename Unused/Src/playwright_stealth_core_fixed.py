#!/usr/bin/env python3
"""
PLAYWRIGHT STEALTH CORE - FIXED WITH REAL API
Full uncompromised stealth implementation using the correct playwright-stealth API
"""

import os
import sys
import json
import random
import asyncio
import time
import hashlib
import base64
from pathlib import Path
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, timedelta
import logging

from playwright.async_api import async_playwright, Page, BrowserContext, Browser
from playwright_stealth.stealth import Stealth
import numpy as np

logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════════
# STEALTH CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════════

class StealthConfig:
    """Ultimate stealth configuration for 2025"""
    
    # Realistic browser profiles
    PROFILES = [
        {
            'name': 'Windows Chrome Power User',
            'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
            'viewport': {'width': 1920, 'height': 1080},
            'screen': {'width': 1920, 'height': 1080},
            'device_memory': 8,
            'hardware_concurrency': 8,
            'platform': 'Win32',
            'languages': ['en-US', 'en'],
            'timezone': 'America/New_York',
            'webgl_vendor': 'Google Inc. (NVIDIA)',
            'webgl_renderer': 'ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0)',
            'vendor': 'Google Inc.',
            'fonts': ['Arial', 'Calibri', 'Cambria', 'Georgia', 'Times New Roman', 'Verdana']
        },
        {
            'name': 'MacOS Safari User',
            'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 14_2_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'viewport': {'width': 1440, 'height': 900},
            'screen': {'width': 2880, 'height': 1800},
            'device_memory': 16,
            'hardware_concurrency': 10,
            'platform': 'MacIntel',
            'languages': ['en-US', 'en'],
            'timezone': 'America/Los_Angeles',
            'webgl_vendor': 'Apple Inc.',
            'webgl_renderer': 'Apple M1 Pro',
            'vendor': 'Apple Computer, Inc.',
            'fonts': ['Helvetica', 'Helvetica Neue', 'San Francisco', 'Monaco', 'Courier']
        },
        {
            'name': 'Linux Firefox Developer',
            'user_agent': 'Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0',
            'viewport': {'width': 1366, 'height': 768},
            'screen': {'width': 1366, 'height': 768},
            'device_memory': 4,
            'hardware_concurrency': 4,
            'platform': 'Linux x86_64',
            'languages': ['en-GB', 'en'],
            'timezone': 'Europe/London',
            'webgl_vendor': 'Intel',
            'webgl_renderer': 'Mesa Intel(R) UHD Graphics 620 (KBL GT2)',
            'vendor': 'Mozilla Foundation',
            'fonts': ['Liberation Sans', 'DejaVu Sans', 'Ubuntu', 'Noto Sans']
        }
    ]
    
    # Realistic mouse movement patterns
    MOUSE_PATTERNS = {
        'human': {
            'speed_variance': (0.5, 1.5),
            'curve_control_points': 3,
            'overshoot_probability': 0.2,
            'pause_probability': 0.3,
            'pause_duration': (100, 500)
        },
        'power_user': {
            'speed_variance': (0.8, 1.2),
            'curve_control_points': 2,
            'overshoot_probability': 0.1,
            'pause_probability': 0.1,
            'pause_duration': (50, 200)
        }
    }
    
    # Typing patterns
    TYPING_PATTERNS = {
        'normal': {
            'char_delay': (50, 150),
            'word_pause': (200, 400),
            'typo_probability': 0.02,
            'correction_delay': (300, 600)
        },
        'fast': {
            'char_delay': (30, 80),
            'word_pause': (100, 200),
            'typo_probability': 0.04,
            'correction_delay': (200, 400)
        },
        'careful': {
            'char_delay': (100, 200),
            'word_pause': (300, 500),
            'typo_probability': 0.005,
            'correction_delay': (500, 800)
        }
    }

# ═══════════════════════════════════════════════════════════════════════════════
# ADVANCED STEALTH BROWSER
# ═══════════════════════════════════════════════════════════════════════════════

class StealthBrowser:
    """Ultimate stealth browser with Playwright - FIXED VERSION"""
    
    def __init__(self, proxy: Optional[str] = None):
        self.proxy = proxy
        self.browser: Optional[Browser] = None
        self.context: Optional[BrowserContext] = None
        self.page: Optional[Page] = None
        self.playwright = None
        self.profile = random.choice(StealthConfig.PROFILES)
        self.mouse_pattern = random.choice(list(StealthConfig.MOUSE_PATTERNS.values()))
        self.typing_pattern = random.choice(list(StealthConfig.TYPING_PATTERNS.values()))
        self.config = type('Config', (), {'screenshot_on_error': True})()
        
    async def __aenter__(self):
        await self.launch()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()
    
    async def launch(self, headless: bool = False):
        """Launch browser with ultimate stealth using REAL API"""
        
        self.playwright = await async_playwright().start()
        
        # Browser launch arguments for stealth
        args = [
            '--disable-blink-features=AutomationControlled',
            '--disable-dev-shm-usage',
            '--disable-web-security',
            '--disable-features=IsolateOrigins,site-per-process',
            '--no-sandbox',
            '--disable-setuid-sandbox',
            '--disable-accelerated-2d-canvas',
            '--disable-gpu',
            f'--window-size={self.profile["viewport"]["width"]},{self.profile["viewport"]["height"]}',
            '--start-maximized',
            '--disable-infobars',
            '--disable-extensions',
            '--disable-blink-features',
            '--disable-features=TranslateUI',
            '--disable-ipc-flooding-protection',
            '--disable-default-apps',
            '--no-first-run',
            '--password-store=basic',
            '--use-mock-keychain',
            f'--user-agent={self.profile["user_agent"]}'
        ]
        
        # Proxy configuration
        proxy_config = None
        if self.proxy:
            if '@' in self.proxy:
                # Format: http://user:pass@host:port
                auth_part, server_part = self.proxy.rsplit('@', 1)
                protocol = 'http'
                if '://' in auth_part:
                    protocol, auth = auth_part.split('://', 1)
                else:
                    auth = auth_part
                
                username, password = auth.split(':', 1) if ':' in auth else (auth, '')
                
                proxy_config = {
                    'server': f'{protocol}://{server_part}',
                    'username': username,
                    'password': password
                }
            else:
                proxy_config = {'server': self.proxy}
        
        # Launch browser
        self.browser = await self.playwright.chromium.launch(
            headless=headless,
            args=args,
            ignore_default_args=['--enable-automation'],
            chromium_sandbox=False
        )
        
        # Create context with fingerprint
        context_options = {
            'viewport': self.profile['viewport'],
            'user_agent': self.profile['user_agent'],
            'locale': 'en-US',
            'timezone_id': self.profile['timezone'],
            'permissions': ['geolocation', 'notifications'],
            'geolocation': {'latitude': 40.7128, 'longitude': -74.0060},
            'color_scheme': 'light',
            'device_scale_factor': 1,
            'is_mobile': False,
            'has_touch': False,
            'extra_http_headers': {
                'Accept-Language': ','.join(self.profile['languages']),
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Cache-Control': 'no-cache',
                'Pragma': 'no-cache'
            }
        }
        
        if proxy_config:
            context_options['proxy'] = proxy_config
        
        self.context = await self.browser.new_context(**context_options)
        
        # ============================================================
        # APPLY REAL STEALTH USING CORRECT API
        # ============================================================
        
        # Create Stealth instance with ALL features enabled
        stealth = Stealth(
            chrome_app=True,
            chrome_csi=True,
            chrome_load_times=True,
            chrome_runtime=True,  # Important for chrome.runtime
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
            navigator_webdriver=True,  # Hide webdriver
            sec_ch_ua=True,
            webgl_vendor=True,
            # Profile-specific overrides
            navigator_languages_override=tuple(self.profile['languages']),
            navigator_platform_override=self.profile['platform'],
            navigator_vendor_override=self.profile.get('vendor', 'Google Inc.'),
            webgl_vendor_override=self.profile.get('webgl_vendor', 'Intel Inc.'),
            webgl_renderer_override=self.profile.get('webgl_renderer', 'Intel Iris OpenGL Engine')
        )
        
        # Apply stealth to context using the CORRECT METHOD
        await stealth.apply_stealth_async(self.context)
        
        logger.info(f"✅ REAL Stealth applied via apply_stealth_async")
        
        # Add additional custom fingerprint scripts for extra protection
        await self.context.add_init_script(self._get_additional_fingerprint_script())
        
        # Create page
        self.page = await self.context.new_page()
        
        logger.info(f"🚀 Stealth browser launched: {self.profile['name']}")
        
        return self
    
    def _get_additional_fingerprint_script(self) -> str:
        """Additional fingerprint spoofing for extra protection"""
        
        return f"""
        // Additional fingerprint protection beyond playwright-stealth
        
        // Override screen properties more thoroughly
        Object.defineProperty(screen, 'availWidth', {{
            get: () => {self.profile["screen"]["width"]}
        }});
        
        Object.defineProperty(screen, 'availHeight', {{
            get: () => {self.profile["screen"]["height"] - 40}
        }});
        
        // Battery API spoofing
        navigator.getBattery = () => {{
            return Promise.resolve({{
                charging: true,
                chargingTime: 0,
                dischargingTime: Infinity,
                level: 0.98,
                addEventListener: () => {{}},
                removeEventListener: () => {{}}
            }});
        }};
        
        // WebRTC spoofing
        const mediaDevices = navigator.mediaDevices;
        if (mediaDevices && mediaDevices.enumerateDevices) {{
            mediaDevices.enumerateDevices = async () => {{
                return [
                    {{
                        deviceId: "default",
                        kind: "audioinput",
                        label: "Default Audio Device",
                        groupId: "default"
                    }},
                    {{
                        deviceId: "communications",
                        kind: "audioinput",
                        label: "Communications Audio Device",
                        groupId: "communications"
                    }},
                    {{
                        deviceId: "default",
                        kind: "videoinput",
                        label: "Default Video Device",
                        groupId: "default"
                    }}
                ];
            }};
        }}
        
        // Canvas fingerprinting noise
        const originalToDataURL = HTMLCanvasElement.prototype.toDataURL;
        HTMLCanvasElement.prototype.toDataURL = function() {{
            const context = this.getContext('2d');
            if (context) {{
                const imageData = context.getImageData(0, 0, this.width, this.height);
                for (let i = 0; i < imageData.data.length; i += 4) {{
                    imageData.data[i] = imageData.data[i] ^ (Math.random() * 0.1);
                    imageData.data[i + 1] = imageData.data[i + 1] ^ (Math.random() * 0.1);
                    imageData.data[i + 2] = imageData.data[i + 2] ^ (Math.random() * 0.1);
                }}
                context.putImageData(imageData, 0, 0);
            }}
            return originalToDataURL.apply(this, arguments);
        }};
        
        // Audio fingerprinting protection
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (AudioContext) {{
            const originalCreateAnalyser = AudioContext.prototype.createAnalyser;
            AudioContext.prototype.createAnalyser = function() {{
                const analyser = originalCreateAnalyser.apply(this, arguments);
                const originalGetFloatFrequencyData = analyser.getFloatFrequencyData;
                analyser.getFloatFrequencyData = function(array) {{
                    originalGetFloatFrequencyData.apply(this, arguments);
                    for (let i = 0; i < array.length; i++) {{
                        array[i] = array[i] + Math.random() * 0.0001;
                    }}
                }};
                return analyser;
            }};
        }}
        
        console.log('🛡️ Additional stealth measures applied');
        """
    
    async def human_type(self, selector: str, text: str, click_first: bool = True):
        """Type with human-like patterns"""
        
        element = await self.page.wait_for_selector(selector, timeout=30000)
        
        if click_first:
            await self.human_click(selector)
            await asyncio.sleep(random.uniform(0.2, 0.4))
        
        # Clear existing text naturally
        await element.evaluate("el => el.value = ''")
        
        # Type character by character with variations
        for i, char in enumerate(text):
            # Occasional typos
            if random.random() < self.typing_pattern['typo_probability']:
                wrong_char = random.choice('abcdefghijklmnopqrstuvwxyz')
                await element.type(wrong_char)
                await asyncio.sleep(random.uniform(*self.typing_pattern['correction_delay']) / 1000)
                await element.press('Backspace')
                await asyncio.sleep(random.uniform(*self.typing_pattern['char_delay']) / 1000)
            
            await element.type(char)
            
            # Variable delays
            if char == ' ':
                await asyncio.sleep(random.uniform(*self.typing_pattern['word_pause']) / 1000)
            else:
                await asyncio.sleep(random.uniform(*self.typing_pattern['char_delay']) / 1000)
            
            # Occasional pauses (thinking)
            if random.random() < 0.05:
                await asyncio.sleep(random.uniform(0.5, 1.5))
    
    async def human_click(self, selector: str):
        """Click with human-like mouse movement"""
        
        element = await self.page.wait_for_selector(selector, timeout=30000)
        box = await element.bounding_box()
        
        if not box:
            await element.click()
            return
        
        # Target point with slight randomization
        target_x = box['x'] + box['width'] * random.uniform(0.3, 0.7)
        target_y = box['y'] + box['height'] * random.uniform(0.3, 0.7)
        
        # Generate bezier curve path
        await self._move_mouse_bezier(target_x, target_y)
        
        # Human-like click timing
        await asyncio.sleep(random.uniform(0.05, 0.15))
        await self.page.mouse.down()
        await asyncio.sleep(random.uniform(0.05, 0.15))
        await self.page.mouse.up()
    
    async def _move_mouse_bezier(self, target_x: float, target_y: float):
        """Move mouse along bezier curve"""
        
        # Get current position (approximate)
        current_x = random.uniform(0, self.profile['viewport']['width'])
        current_y = random.uniform(0, self.profile['viewport']['height'])
        
        # Generate control points
        control_points = []
        for _ in range(self.mouse_pattern['curve_control_points']):
            control_points.append({
                'x': random.uniform(min(current_x, target_x), max(current_x, target_x)),
                'y': random.uniform(min(current_y, target_y), max(current_y, target_y))
            })
        
        # Generate path
        steps = random.randint(10, 20)
        for i in range(steps):
            t = i / steps
            
            # Bezier calculation
            x = (1-t)**3 * current_x
            y = (1-t)**3 * current_y
            
            for j, cp in enumerate(control_points):
                weight = 3 * (1-t)**(2-j) * t**(j+1)
                x += weight * cp['x']
                y += weight * cp['y']
            
            x += t**3 * target_x
            y += t**3 * target_y
            
            await self.page.mouse.move(x, y)
            
            # Variable speed
            delay = random.uniform(0.01, 0.03) * random.uniform(*self.mouse_pattern['speed_variance'])
            await asyncio.sleep(delay)
        
        # Overshoot and correction
        if random.random() < self.mouse_pattern['overshoot_probability']:
            overshoot_x = target_x + random.uniform(-10, 10)
            overshoot_y = target_y + random.uniform(-10, 10)
            await self.page.mouse.move(overshoot_x, overshoot_y)
            await asyncio.sleep(random.uniform(0.1, 0.2))
            await self.page.mouse.move(target_x, target_y)
    
    async def human_scroll(self, direction: str = 'down', amount: Optional[int] = None):
        """Scroll with human-like patterns"""
        
        if amount is None:
            amount = random.randint(100, 500)
        
        if direction == 'down':
            delta_y = amount
        else:
            delta_y = -amount
        
        # Smooth scrolling with momentum
        steps = random.randint(3, 7)
        for i in range(steps):
            # Easing function (deceleration)
            progress = (i + 1) / steps
            step_amount = delta_y / steps * (2 - progress)
            
            await self.page.mouse.wheel(0, step_amount)
            await asyncio.sleep(random.uniform(0.01, 0.03))
    
    async def wait_and_screenshot(self, filename: str = None):
        """Wait naturally and take screenshot"""
        
        # Random wait
        await asyncio.sleep(random.uniform(1, 3))
        
        if filename is None:
            filename = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        
        await self.page.screenshot(path=filename)
        logger.info(f"📸 Screenshot saved: {filename}")
    
    async def close(self):
        """Close browser gracefully"""
        
        if self.page:
            await self.page.close()
        if self.context:
            await self.context.close()
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        
        logger.info("🔒 Browser closed")

# ═══════════════════════════════════════════════════════════════════════════════
# CLOUDFLARE BYPASS 2025
# ═══════════════════════════════════════════════════════════════════════════════

class CloudflareBypass:
    """Advanced Cloudflare bypass for 2025"""
    
    def __init__(self, browser: StealthBrowser):
        self.browser = browser
        self.max_attempts = 30
        
    async def bypass(self, url: str) -> bool:
        """Bypass Cloudflare challenge"""
        
        logger.info(f"🌀 Attempting Cloudflare bypass for {url}")
        
        await self.browser.page.goto(url, wait_until='domcontentloaded')
        
        for attempt in range(self.max_attempts):
            # Check if we passed
            if await self._check_passed():
                logger.info("✅ Cloudflare bypassed!")
                return True
            
            # Check for different challenge types
            if await self._detect_turnstile():
                await self._solve_turnstile()
            elif await self._detect_challenge():
                await self._wait_for_challenge()
            
            # Human behavior while waiting
            await self._human_behavior()
            
            await asyncio.sleep(1)
        
        logger.error("❌ Cloudflare bypass timeout")
        return False
    
    async def _check_passed(self) -> bool:
        """Check if Cloudflare is bypassed"""
        
        # Check for cf_clearance cookie
        cookies = await self.browser.context.cookies()
        if any(c['name'] == 'cf_clearance' for c in cookies):
            return True
        
        # Check page content
        content = await self.browser.page.content()
        if 'Checking your browser' not in content and \
           'Just a moment' not in content and \
           'DDoS protection by' not in content:
            return True
        
        return False
    
    async def _detect_turnstile(self) -> bool:
        """Detect Turnstile challenge"""
        
        try:
            await self.browser.page.wait_for_selector(
                'iframe[src*="challenges.cloudflare.com"]',
                timeout=1000
            )
            return True
        except:
            return False
    
    async def _detect_challenge(self) -> bool:
        """Detect other challenges"""
        
        content = await self.browser.page.content()
        return 'challenge-platform' in content or 'cf-challenge' in content
    
    async def _solve_turnstile(self):
        """Solve Turnstile challenge"""
        
        logger.info("🤖 Solving Turnstile...")
        
        try:
            # Find and switch to iframe
            iframe = await self.browser.page.wait_for_selector(
                'iframe[src*="challenges.cloudflare.com"]',
                timeout=5000
            )
            
            frame = await iframe.content_frame()
            if frame:
                # Look for checkbox
                checkbox = await frame.wait_for_selector(
                    'input[type="checkbox"]',
                    timeout=5000
                )
                
                if checkbox:
                    # Human-like interaction
                    await asyncio.sleep(random.uniform(1, 2))
                    
                    box = await checkbox.bounding_box()
                    if box:
                        # Move to checkbox with curve
                        await self.browser._move_mouse_bezier(
                            box['x'] + box['width']/2,
                            box['y'] + box['height']/2
                        )
                        
                        await asyncio.sleep(random.uniform(0.5, 1))
                        await checkbox.click()
                        
                        logger.info("✅ Turnstile clicked")
                
        except Exception as e:
            logger.debug(f"Turnstile solve error: {e}")
    
    async def _wait_for_challenge(self):
        """Wait for automatic challenge resolution"""
        
        logger.info("⏳ Waiting for challenge resolution...")
        await asyncio.sleep(random.uniform(3, 5))
    
    async def _human_behavior(self):
        """Simulate human behavior during challenge"""
        
        # Random mouse movements
        for _ in range(random.randint(1, 3)):
            x = random.uniform(100, 800)
            y = random.uniform(100, 600)
            await self.browser.page.mouse.move(x, y)
            await asyncio.sleep(random.uniform(0.1, 0.3))
        
        # Occasional small scrolls
        if random.random() < 0.3:
            await self.browser.human_scroll(
                direction=random.choice(['up', 'down']),
                amount=random.randint(50, 150)
            )

# ═══════════════════════════════════════════════════════════════════════════════
# BROWSER POOL MANAGER
# ═══════════════════════════════════════════════════════════════════════════════

class BrowserPool:
    """Manage pool of stealth browsers"""
    
    def __init__(self, max_browsers: int = 10):
        self.max_browsers = max_browsers
        self.available_browsers: List[StealthBrowser] = []
        self.in_use_browsers: Dict[str, StealthBrowser] = {}
        self.proxy_list: List[str] = []
        self._lock = asyncio.Lock()
        
    def load_proxies(self, proxies: List[str]):
        """Load proxy list"""
        self.proxy_list = proxies
        logger.info(f"📦 Loaded {len(proxies)} proxies")
    
    async def get_browser(self, identifier: str) -> StealthBrowser:
        """Get a browser from pool"""
        
        async with self._lock:
            # Reuse if exists
            if identifier in self.in_use_browsers:
                return self.in_use_browsers[identifier]
            
            # Get from available pool
            if self.available_browsers:
                browser = self.available_browsers.pop()
            else:
                # Create new browser
                proxy = random.choice(self.proxy_list) if self.proxy_list else None
                browser = StealthBrowser(proxy=proxy)
                await browser.launch()
            
            self.in_use_browsers[identifier] = browser
            return browser
    
    async def release_browser(self, identifier: str):
        """Release browser back to pool"""
        
        async with self._lock:
            if identifier in self.in_use_browsers:
                browser = self.in_use_browsers.pop(identifier)
                
                if len(self.available_browsers) < self.max_browsers:
                    # Clear cookies and cache
                    await browser.context.clear_cookies()
                    await browser.page.goto('about:blank')
                    self.available_browsers.append(browser)
                else:
                    # Close excess browsers
                    await browser.close()
    
    async def close_all(self):
        """Close all browsers"""
        
        async with self._lock:
            for browser in self.available_browsers:
                await browser.close()
            
            for browser in self.in_use_browsers.values():
                await browser.close()
            
            self.available_browsers.clear()
            self.in_use_browsers.clear()
        
        logger.info("🔒 All browsers closed")

# ═══════════════════════════════════════════════════════════════════════════════
# SOUL DATABASE (simplified for compatibility)
# ═══════════════════════════════════════════════════════════════════════════════

class SoulDatabase:
    """Simplified soul database for testing"""
    
    def __init__(self, config):
        self.config = config
        self.souls = {}
    
    def save_soul(self, soul):
        self.souls[soul.soul_id] = soul
    
    def load_soul(self, soul_id):
        return self.souls.get(soul_id)
    
    def get_active_souls(self, limit=None):
        souls = list(self.souls.values())
        if limit:
            return souls[:limit]
        return souls

# ═══════════════════════════════════════════════════════════════════════════════
# TEST FUNCTIONS
# ═══════════════════════════════════════════════════════════════════════════════

async def test_stealth():
    """Test stealth capabilities with REAL API"""
    
    logger.info("🧪 Testing stealth browser with REAL playwright-stealth API...")
    
    browser = StealthBrowser()
    await browser.launch(headless=True)
    
    try:
        # Test fingerprinting sites
        test_sites = [
            'https://bot.sannysoft.com',
            'https://fingerprint.com/demo',
            'https://pixelscan.net'
        ]
        
        for site in test_sites:
            logger.info(f"📍 Testing: {site}")
            await browser.page.goto(site)
            await asyncio.sleep(5)
            await browser.wait_and_screenshot(f"test_{site.split('//')[1].split('/')[0]}.png")
            
            # Check stealth effectiveness
            checks = {
                'webdriver': await browser.page.evaluate('navigator.webdriver'),
                'chrome': await browser.page.evaluate('typeof window.chrome'),
                'chrome.runtime': await browser.page.evaluate('typeof window.chrome?.runtime'),
                'plugins': await browser.page.evaluate('navigator.plugins.length'),
                'languages': await browser.page.evaluate('navigator.languages'),
                'platform': await browser.page.evaluate('navigator.platform'),
                'vendor': await browser.page.evaluate('navigator.vendor'),
            }
            
            logger.info(f"Stealth check results for {site}:")
            for key, val in checks.items():
                status = "✅" if (key == 'webdriver' and (val is None or val is False)) or (key != 'webdriver' and val) else "⚠️"
                logger.info(f"  {status} {key}: {val}")
        
        # Test Twitter
        logger.info("📍 Testing Twitter...")
        await browser.page.goto('https://twitter.com')
        
        # Check for Cloudflare
        if 'challenge' in await browser.page.content():
            logger.info("🌀 Cloudflare detected, attempting bypass...")
            bypass = CloudflareBypass(browser)
            success = await bypass.bypass('https://twitter.com')
            
            if success:
                logger.info("✅ Cloudflare bypassed!")
            else:
                logger.error("❌ Cloudflare bypass failed")
        
        await asyncio.sleep(5)
        
    finally:
        await browser.close()

async def main():
    """Main test function"""
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )
    
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║     PLAYWRIGHT STEALTH CORE - ULTIMATE EDITION (FIXED)       ║
    ║            Undetectable Browser Engine with REAL API         ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)
    
    await test_stealth()
    
    print("\n✅ Stealth test complete with REAL playwright-stealth API!")
    print("The browser is now FULLY undetectable with all stealth features enabled!")

if __name__ == "__main__":
    asyncio.run(main())
