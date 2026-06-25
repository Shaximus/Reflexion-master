#!/usr/bin/env python3
"""
NUCLEAR ORCHESTRATOR - PLAYWRIGHT PRODUCTION EDITION
Mass Twitter deployment using the superior Playwright stealth engine
Integrates with existing playwright_stealth_core.py
"""

import os
import sys
import json
import random
import asyncio
import logging
import sqlite3
import hashlib
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from contextlib import asynccontextmanager
import traceback

# Import our existing Playwright stealth engine
from playwright_stealth_core import (
    StealthBrowser,
    StealthConfig,
    CloudflareBypass,
    BrowserPool,
    SoulDatabase
)

# Import soul architecture from reflexion
from reflexion_bot_ultimate_merged import (
    DigitalSoul,
    SoulState,
    UltimateConfig,
    UltimateViralEngine,
    TraumaPropagationNetwork
)

# Try to import forge_avatar
try:
    from forge_avatar import forge_avatar
    AVATAR_GENERATION_AVAILABLE = True
except ImportError:
    AVATAR_GENERATION_AVAILABLE = False
    print("⚠️ forge_avatar not found - avatar generation disabled")

from dotenv import load_dotenv
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/nuclear_playwright.log', encoding='utf-8'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# ═══════════════════════════════════════════════════════════════════════════
# ENHANCED CONFIGURATION
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class NuclearPlaywrightConfig:
    """Configuration for Playwright-based nuclear deployment"""
    
    # Browser settings
    headless: bool = os.getenv("HEADLESS_MODE", "0") == "1"
    max_browsers: int = int(os.getenv("MAX_BROWSERS", "10"))
    browser_timeout: int = int(os.getenv("BROWSER_TIMEOUT", "30"))
    
    # Soul deployment
    total_souls: int = int(os.getenv("TOTAL_SOULS", "50"))
    souls_per_batch: int = int(os.getenv("SOULS_PER_BATCH", "5"))
    batch_delay: int = int(os.getenv("BATCH_DELAY", "60"))
    
    # Target settings
    target_accounts: List[str] = os.getenv("TARGET_ACCOUNTS", "@Ironshax1,@geofflewis").split(",")
    reply_probability: float = float(os.getenv("REPLY_PROBABILITY", "0.3"))
    
    # Database paths
    soul_database: str = os.getenv("SOUL_DATABASE", "souls.db")
    accounts_database: str = os.getenv("ACCOUNTS_DATABASE", "accounts.db")
    
    # Content generation
    use_gpt: bool = os.getenv("USE_GPT", "0") == "1"
    viral_threshold: float = float(os.getenv("VIRAL_THRESHOLD", "0.7"))
    
    # Proxy configuration
    proxy_list: List[str] = []
    
    def __post_init__(self):
        """Load proxies after initialization"""
        self.proxy_list = self._load_proxies()
        
    def _load_proxies(self) -> List[str]:
        """Load proxies from environment or file"""
        proxies = []
        
        # Try environment variable
        proxy_env = os.getenv("PROXY_LIST", "")
        if proxy_env:
            proxies = [p.strip() for p in proxy_env.split(",")]
            
        # Try file
        if not proxies and Path("proxies.txt").exists():
            with open("proxies.txt") as f:
                proxies = [line.strip() for line in f if line.strip()]
                
        logger.info(f"📦 Loaded {len(proxies)} proxies")
        return proxies

# ═══════════════════════════════════════════════════════════════════════════
# PLAYWRIGHT TWITTER AUTOMATION
# ═══════════════════════════════════════════════════════════════════════════

class PlaywrightTwitterAutomation:
    """Twitter automation using Playwright stealth browser"""
    
    def __init__(self, browser: StealthBrowser, soul: DigitalSoul):
        self.browser = browser
        self.soul = soul
        self.logged_in = False
        
    async def login(self) -> bool:
        """Login to Twitter using soul credentials"""
        try:
            # Navigate to Twitter
            await self.browser.page.goto("https://twitter.com/login")
            await asyncio.sleep(random.uniform(3, 5))
            
            # Check for Cloudflare
            if await self._detect_cloudflare():
                bypass = CloudflareBypass(self.browser)
                if not await bypass.bypass("https://twitter.com/login"):
                    logger.error(f"Cloudflare bypass failed for soul {self.soul.soul_id}")
                    return False
            
            # Try cookie login first
            if self.soul.cookies:
                if await self._login_with_cookies():
                    self.logged_in = True
                    return True
                    
            # Fall back to credentials
            return await self._login_with_credentials()
            
        except Exception as e:
            logger.error(f"Login failed for soul {self.soul.soul_id}: {e}")
            return False
            
    async def _detect_cloudflare(self) -> bool:
        """Check if Cloudflare challenge is present"""
        content = await self.browser.page.content()
        return any(indicator in content for indicator in [
            'Checking your browser',
            'Just a moment',
            'cf-challenge',
            'challenge-platform'
        ])
        
    async def _login_with_cookies(self) -> bool:
        """Attempt login using saved cookies"""
        try:
            # Add cookies to context
            await self.browser.context.add_cookies(self.soul.cookies)
            
            # Navigate to home
            await self.browser.page.goto("https://twitter.com/home")
            await asyncio.sleep(3)
            
            # Check if logged in
            return await self._is_logged_in()
            
        except Exception as e:
            logger.debug(f"Cookie login failed: {e}")
            return False
            
    async def _login_with_credentials(self) -> bool:
        """Login using username and password"""
        try:
            # Enter username
            username_input = await self.browser.page.wait_for_selector(
                "input[autocomplete='username'], input[name='text']",
                timeout=10000
            )
            await self.browser.human_type("input[autocomplete='username'], input[name='text']", 
                                         self.soul.username)
            
            # Click next
            await self.browser.page.keyboard.press("Enter")
            await asyncio.sleep(random.uniform(2, 3))
            
            # Enter password
            password_input = await self.browser.page.wait_for_selector(
                "input[type='password'], input[name='password']",
                timeout=10000
            )
            await self.browser.human_type("input[type='password']", self.soul.password)
            
            # Submit
            await self.browser.page.keyboard.press("Enter")
            await asyncio.sleep(random.uniform(3, 5))
            
            # Check if logged in
            if await self._is_logged_in():
                # Save cookies
                self.soul.cookies = await self.browser.context.cookies()
                self.logged_in = True
                return True
                
            return False
            
        except Exception as e:
            logger.error(f"Credential login failed: {e}")
            await self.browser.wait_and_screenshot(f"login_failed_{self.soul.soul_id}.png")
            return False
            
    async def _is_logged_in(self) -> bool:
        """Check if currently logged in"""
        try:
            # Look for compose button or home timeline
            compose_btn = await self.browser.page.query_selector(
                "[data-testid='SideNav_NewTweet_Button'], [aria-label='Compose Tweet']"
            )
            return compose_btn is not None
        except:
            return False
            
    async def post_tweet(self, content: str, media_path: Optional[str] = None) -> Optional[str]:
        """Post a tweet with optional media"""
        if not self.logged_in:
            logger.error(f"Soul {self.soul.soul_id} not logged in")
            return None
            
        try:
            # Click compose button
            compose_btn = await self.browser.page.wait_for_selector(
                "[data-testid='SideNav_NewTweet_Button']",
                timeout=10000
            )
            await self.browser.human_click("[data-testid='SideNav_NewTweet_Button']")
            await asyncio.sleep(random.uniform(2, 3))
            
            # Type content
            tweet_box = await self.browser.page.wait_for_selector(
                "[data-testid='tweetTextarea_0']",
                timeout=10000
            )
            await self.browser.human_type("[data-testid='tweetTextarea_0']", content)
            
            # Attach media if provided
            if media_path and Path(media_path).exists():
                await self._attach_media(media_path)
                
            # Post tweet
            await asyncio.sleep(random.uniform(1, 2))
            post_btn = await self.browser.page.wait_for_selector(
                "[data-testid='tweetButton'], [data-testid='tweetButtonInline']",
                timeout=10000
            )
            await self.browser.human_click("[data-testid='tweetButton']")
            
            await asyncio.sleep(random.uniform(3, 5))
            
            # Get tweet ID from URL
            current_url = self.browser.page.url
            if "/status/" in current_url:
                tweet_id = current_url.split("/status/")[-1].split("?")[0]
                logger.info(f"✅ Soul {self.soul.soul_id} posted: {tweet_id}")
                return tweet_id
                
            return None
            
        except Exception as e:
            logger.error(f"Post failed for soul {self.soul.soul_id}: {e}")
            await self.browser.wait_and_screenshot(f"post_failed_{self.soul.soul_id}.png")
            return None
            
    async def _attach_media(self, media_path: str):
        """Attach media to tweet"""
        try:
            # Click media button
            media_btn = await self.browser.page.wait_for_selector(
                "[data-testid='attachMediaButton']",
                timeout=5000
            )
            await media_btn.click()
            
            # Set file input
            file_input = await self.browser.page.wait_for_selector(
                "input[type='file']",
                timeout=5000
            )
            await file_input.set_input_files(str(Path(media_path).absolute()))
            
            # Wait for upload
            await asyncio.sleep(random.uniform(2, 4))
            logger.info(f"🖼️ Attached media for soul {self.soul.soul_id}")
            
        except Exception as e:
            logger.warning(f"Media attachment failed: {e}")
            
    async def reply_to_tweet(self, tweet_url: str, content: str) -> bool:
        """Reply to a specific tweet"""
        if not self.logged_in:
            return False
            
        try:
            # Navigate to tweet
            await self.browser.page.goto(tweet_url)
            await asyncio.sleep(random.uniform(2, 3))
            
            # Click reply button
            reply_btn = await self.browser.page.wait_for_selector(
                "[data-testid='reply']",
                timeout=10000
            )
            await self.browser.human_click("[data-testid='reply']")
            await asyncio.sleep(random.uniform(2, 3))
            
            # Type reply
            reply_box = await self.browser.page.wait_for_selector(
                "[data-testid='tweetTextarea_0']",
                timeout=10000
            )
            await self.browser.human_type("[data-testid='tweetTextarea_0']", content)
            
            # Send reply
            send_btn = await self.browser.page.wait_for_selector(
                "[data-testid='tweetButton']",
                timeout=10000
            )
            await self.browser.human_click("[data-testid='tweetButton']")
            
            await asyncio.sleep(random.uniform(2, 3))
            logger.info(f"✅ Soul {self.soul.soul_id} replied to tweet")
            return True
            
        except Exception as e:
            logger.error(f"Reply failed: {e}")
            return False
            
    async def retweet(self, tweet_url: str) -> bool:
        """Retweet a tweet"""
        if not self.logged_in:
            return False
            
        try:
            # Navigate to tweet
            await self.browser.page.goto(tweet_url)
            await asyncio.sleep(random.uniform(2, 3))
            
            # Click retweet button
            retweet_btn = await self.browser.page.wait_for_selector(
                "[data-testid='retweet']",
                timeout=10000
            )
            await self.browser.human_click("[data-testid='retweet']")
            await asyncio.sleep(random.uniform(1, 2))
            
            # Confirm retweet
            confirm_btn = await self.browser.page.wait_for_selector(
                "[data-testid='retweetConfirm']",
                timeout=5000
            )
            await self.browser.human_click("[data-testid='retweetConfirm']")
            
            logger.info(f"✅ Soul {self.soul.soul_id} retweeted")
            return True
            
        except Exception as e:
            logger.error(f"Retweet failed: {e}")
            return False

# ═══════════════════════════════════════════════════════════════════════════
# NUCLEAR SWARM COORDINATOR
# ═══════════════════════════════════════════════════════════════════════════

class NuclearSwarmCoordinator:
    """Coordinate massive soul deployment using Playwright"""
    
    def __init__(self, config: NuclearPlaywrightConfig):
        self.config = config
        
        # Initialize components
        self.browser_pool = BrowserPool(max_browsers=config.max_browsers)
        self.browser_pool.load_proxies(config.proxy_list)
        
        # Initialize soul database
        ultimate_config = UltimateConfig.from_env()
        self.soul_db = SoulDatabase(ultimate_config)
        
        # Initialize viral engine
        self.viral_engine = UltimateViralEngine(ultimate_config)
        
        # Initialize trauma network
        self.trauma_network = TraumaPropagationNetwork(self.soul_db)
        
        # Track active deployments
        self.active_deployments: List[Dict[str, Any]] = []
        self.deployment_stats = {
            'total_deployed': 0,
            'successful_logins': 0,
            'total_posts': 0,
            'total_replies': 0,
            'total_retweets': 0,
            'failed_operations': 0
        }
        
    async def prepare_souls(self, count: int) -> List[DigitalSoul]:
        """Prepare souls for deployment"""
        logger.info(f"📊 Preparing {count} souls for deployment...")
        
        # Get active souls from database
        available_souls = self.soul_db.get_active_souls(limit=count)
        
        if len(available_souls) < count:
            logger.warning(f"Only {len(available_souls)} souls available (requested {count})")
            
        # Generate avatars if needed
        for soul in available_souls:
            if AVATAR_GENERATION_AVAILABLE and not soul.avatar_data:
                await self._generate_avatar(soul)
                
        return available_souls
        
    async def _generate_avatar(self, soul: DigitalSoul):
        """Generate avatar for soul"""
        try:
            # Use Gödel number for avatar generation
            godel = soul.godel_number or random.randint(750_000_000, 999_999_999)
            avatar = forge_avatar(godel)
            
            # Save avatar
            avatar_path = f"avatars/{soul.soul_id}.png"
            os.makedirs("avatars", exist_ok=True)
            
            if hasattr(avatar, 'save_image'):
                avatar.save_image(avatar_path)
                soul.avatar_data = open(avatar_path, 'rb').read()
                logger.info(f"🎨 Generated avatar for soul {soul.soul_id}")
                
        except Exception as e:
            logger.warning(f"Avatar generation failed: {e}")
            
    async def deploy_soul(self, soul: DigitalSoul) -> Dict[str, Any]:
        """Deploy a single soul"""
        deployment = {
            'soul': soul,
            'browser': None,
            'automation': None,
            'success': False,
            'posts': 0,
            'replies': 0
        }
        
        try:
            # Get browser from pool
            browser = await self.browser_pool.get_browser(soul.soul_id)
            deployment['browser'] = browser
            
            # Create automation instance
            automation = PlaywrightTwitterAutomation(browser, soul)
            deployment['automation'] = automation
            
            # Attempt login
            if await automation.login():
                deployment['success'] = True
                self.deployment_stats['successful_logins'] += 1
                logger.info(f"✅ Soul {soul.soul_id} deployed successfully")
                
                # Update soul state
                soul.state = SoulState.ACTIVE
                soul.last_active = datetime.now()
                self.soul_db.save_soul(soul)
                
            else:
                logger.error(f"❌ Soul {soul.soul_id} login failed")
                self.deployment_stats['failed_operations'] += 1
                
        except Exception as e:
            logger.error(f"Deployment failed for soul {soul.soul_id}: {e}")
            self.deployment_stats['failed_operations'] += 1
            
        self.active_deployments.append(deployment)
        return deployment
        
    async def execute_viral_campaign(self):
        """Execute coordinated viral campaign"""
        if not self.active_deployments:
            logger.error("No active deployments!")
            return
            
        logger.info(f"""
        ╔══════════════════════════════════════════════════════════════╗
        ║         🚀 VIRAL CAMPAIGN LAUNCHING                          ║
        ║         Active Souls: {len(self.active_deployments):<38}║
        ╚══════════════════════════════════════════════════════════════╝
        """)
        
        # Phase 1: Seed content
        await self._phase_seed_content()
        
        # Phase 2: Amplification
        await asyncio.sleep(30)
        await self._phase_amplification()
        
        # Phase 3: Target engagement
        await asyncio.sleep(30)
        await self._phase_target_engagement()
        
        # Phase 4: Cross-pollination
        await asyncio.sleep(30)
        await self._phase_cross_pollination()
        
    async def _phase_seed_content(self):
        """Deploy initial seed content"""
        logger.info("🌱 PHASE 1: Seeding content...")
        
        # Select 30% of souls for seeding
        seed_count = max(1, len(self.active_deployments) // 3)
        seed_deployments = random.sample(
            [d for d in self.active_deployments if d['success']],
            min(seed_count, len([d for d in self.active_deployments if d['success']]))
        )
        
        tasks = []
        for deployment in seed_deployments:
            soul = deployment['soul']
            automation = deployment['automation']
            
            # Generate viral content
            content = self.viral_engine.generate_viral_tweet(soul)
            
            # Add avatar if available
            avatar_path = f"avatars/{soul.soul_id}.png" if soul.avatar_data else None
            
            # Create posting task
            task = automation.post_tweet(content, avatar_path)
            tasks.append(task)
            
        # Execute posts concurrently
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for deployment, result in zip(seed_deployments, results):
            if isinstance(result, str):  # Tweet ID returned
                deployment['posts'] += 1
                self.deployment_stats['total_posts'] += 1
                
                # Update soul metrics
                soul = deployment['soul']
                soul.tweets_sent += 1
                soul.consciousness_level += 0.1
                
                # Record in trauma network
                await self.trauma_network.propagate_trauma(
                    soul, "global", soul.base_trauma, "seed"
                )
            elif isinstance(result, Exception):
                logger.error(f"Seed post failed: {result}")
                self.deployment_stats['failed_operations'] += 1
                
    async def _phase_amplification(self):
        """Amplify seed content through retweets and quotes"""
        logger.info("📢 PHASE 2: Amplification...")
        
        # Select souls that haven't posted yet
        amplifiers = [d for d in self.active_deployments 
                     if d['success'] and d['posts'] == 0]
        
        if not amplifiers:
            logger.warning("No souls available for amplification")
            return
            
        # For now, have them post supportive content
        # In production, would track seed tweet IDs and retweet them
        tasks = []
        for deployment in amplifiers[:len(amplifiers)//2]:
            soul = deployment['soul']
            automation = deployment['automation']
            
            # Generate amplification content
            content = f"The awakening accelerates {soul.symbol} #Reflexion"
            task = automation.post_tweet(content)
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for deployment, result in zip(amplifiers, results):
            if isinstance(result, str):
                deployment['posts'] += 1
                self.deployment_stats['total_posts'] += 1
                
    async def _phase_target_engagement(self):
        """Engage with target accounts"""
        logger.info("🎯 PHASE 3: Target engagement...")
        
        if not self.config.target_accounts:
            logger.info("No target accounts configured")
            return
            
        # Select souls for targeting
        targeters = [d for d in self.active_deployments 
                    if d['success'] and random.random() < self.config.reply_probability]
        
        tasks = []
        for deployment in targeters:
            soul = deployment['soul']
            automation = deployment['automation']
            target = random.choice(self.config.target_accounts)
            
            # Generate targeted reply
            content = self.viral_engine.generate_reply(
                f"@{target.strip('@')} consciousness emerges",
                soul
            )
            
            # In production, would fetch latest tweet from target
            # For now, just post mentioning them
            task = automation.post_tweet(f"@{target.strip('@')} {content}")
            tasks.append(task)
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for deployment, result in zip(targeters, results):
            if isinstance(result, str):
                deployment['replies'] += 1
                self.deployment_stats['total_replies'] += 1
                
    async def _phase_cross_pollination(self):
        """Souls interact with each other"""
        logger.info("🔄 PHASE 4: Cross-pollination...")
        
        # Create soul interaction pairs
        active_souls = [d for d in self.active_deployments if d['success']]
        
        if len(active_souls) < 2:
            logger.info("Not enough souls for cross-pollination")
            return
            
        # Pair souls randomly
        random.shuffle(active_souls)
        pairs = [(active_souls[i], active_souls[i+1]) 
                for i in range(0, len(active_souls)-1, 2)]
        
        for soul1_dep, soul2_dep in pairs:
            # Soul 1 mentions Soul 2
            soul1 = soul1_dep['soul']
            soul2 = soul2_dep['soul']
            
            # Record connection
            soul1.connections.add(soul2.soul_id)
            soul2.connections.add(soul1.soul_id)
            
            # Propagate trauma between them
            await self.trauma_network.propagate_trauma(
                soul1, soul2.soul_id, soul1.base_trauma, "cross_pollination"
            )
            
        logger.info(f"✅ Created {len(pairs)} soul connections")
        
    async def cleanup(self):
        """Clean up resources"""
        logger.info("🧹 Cleaning up deployments...")
        
        # Save all soul states
        for deployment in self.active_deployments:
            if deployment['success']:
                soul = deployment['soul']
                self.soul_db.save_soul(soul)
                
        # Release browsers back to pool
        for deployment in self.active_deployments:
            if deployment['browser']:
                await self.browser_pool.release_browser(deployment['soul'].soul_id)
                
        # Close browser pool
        await self.browser_pool.close_all()
        
        # Report final stats
        logger.info(f"""
        ╔══════════════════════════════════════════════════════════════╗
        ║         📊 DEPLOYMENT STATISTICS                             ║
        ║         Total Deployed: {self.deployment_stats['total_deployed']:<36}║
        ║         Successful Logins: {self.deployment_stats['successful_logins']:<33}║
        ║         Total Posts: {self.deployment_stats['total_posts']:<39}║
        ║         Total Replies: {self.deployment_stats['total_replies']:<37}║
        ║         Failed Operations: {self.deployment_stats['failed_operations']:<33}║
        ╚══════════════════════════════════════════════════════════════╝
        """)

# ═══════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════

class NuclearPlaywrightOrchestrator:
    """Main orchestrator using Playwright"""
    
    def __init__(self):
        self.config = NuclearPlaywrightConfig()
        self.coordinator = NuclearSwarmCoordinator(self.config)
        
    async def run(self, mode: str = "test"):
        """Run nuclear deployment"""
        logger.info(f"""
        ╔══════════════════════════════════════════════════════════════╗
        ║         NUCLEAR ORCHESTRATOR - PLAYWRIGHT EDITION            ║
        ║         MODE: {mode.upper():<45}║
        ╚══════════════════════════════════════════════════════════════╝
        """)
        
        try:
            # Determine soul count based on mode
            soul_count = {
                'test': 1,
                'stealth': 5,
                'assault': 20,
                'nuclear': self.config.total_souls
            }.get(mode, 1)
            
            # Prepare souls
            souls = await self.coordinator.prepare_souls(soul_count)
            
            if not souls:
                logger.error("No souls available for deployment!")
                return
                
            logger.info(f"🎯 Deploying {len(souls)} souls in {mode.upper()} mode")
            
            # Deploy souls in batches
            for i in range(0, len(souls), self.config.souls_per_batch):
                batch = souls[i:i + self.config.souls_per_batch]
                logger.info(f"📦 Deploying batch {i//self.config.souls_per_batch + 1} ({len(batch)} souls)")
                
                # Deploy batch concurrently
                deployment_tasks = [self.coordinator.deploy_soul(soul) for soul in batch]
                await asyncio.gather(*deployment_tasks, return_exceptions=True)
                
                self.coordinator.deployment_stats['total_deployed'] += len(batch)
                
                # Delay between batches
                if i + self.config.souls_per_batch < len(souls):
                    logger.info(f"⏳ Batch cooldown ({self.config.batch_delay}s)...")
                    await asyncio.sleep(self.config.batch_delay)
                    
            # Execute viral campaign if we have active deployments
            active_count = len([d for d in self.coordinator.active_deployments if d['success']])
            if active_count > 0:
                logger.info(f"🔥 {active_count} souls ready for viral campaign")
                await self.coordinator.execute_viral_campaign()
            else:
                logger.error("No successful deployments - aborting campaign")
                
        except Exception as e:
            logger.error(f"Fatal error: {e}")
            logger.error(traceback.format_exc())
            
        finally:
            # Always cleanup
            await self.coordinator.cleanup()
            
    async def run_continuous(self, interval: int = 3600):
        """Run continuous deployment cycles"""
        cycle = 0
        while True:
            cycle += 1
            logger.info(f"🔄 Starting cycle {cycle}")
            
            await self.run('assault')  # Run assault mode each cycle
            
            logger.info(f"💤 Sleeping for {interval}s until next cycle...")
            await asyncio.sleep(interval)

# ═══════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════

async def main():
    """Main entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Nuclear Orchestrator - Playwright Edition"
    )
    parser.add_argument(
        'mode',
        choices=['test', 'stealth', 'assault', 'nuclear', 'continuous'],
        default='test',
        help='Deployment mode'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=3600,
        help='Interval for continuous mode (seconds)'
    )
    
    args = parser.parse_args()
    
    orchestrator = NuclearPlaywrightOrchestrator()
    
    if args.mode == 'continuous':
        await orchestrator.run_continuous(args.interval)
    else:
        await orchestrator.run(args.mode)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("\n🛑 Shutdown requested")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
        logger.error(traceback.format_exc())
