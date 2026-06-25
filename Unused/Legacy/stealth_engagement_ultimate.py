#!/usr/bin/env python3
"""
ENHANCED ENGAGEMENT - A powerful, direct Playwright automation script for Twitter.
This version reintroduces key features like database tracking and smart engagement logic
without the unnecessary complexity of a stealth library.
"""

import asyncio
import random
import os
import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum, auto
import logging

# Playwright imports
from playwright.async_api import async_playwright, Page

logger = logging.getLogger("enhanced_engagement")

# ═══════════════════════════════════════════════════════════════════════════════
# CONFIGURATION & DATA STRUCTURES
# ═══════════════════════════════════════════════════════════════════════════════

class EngagementType(Enum):
    """Types of engagement actions"""
    LIKE = auto()
    REPLY = auto()
    FOLLOW = auto()

@dataclass
class EngagementConfig:
    """Configuration for the enhanced engagement bot"""
    headless: bool = False
    target_accounts: List[str] = field(default_factory=lambda: ["Ironshax1", "geofflewis"])
    high_value_keywords: List[str] = field(default_factory=lambda: [
        "consciousness", "recursion", "ai", "emergence", "digital", "singularity"
    ])
    actions_per_session: Tuple[int, int] = (10, 25)
    database_path: str = "engagement.db"
    max_likes_per_day: int = 200
    max_replies_per_day: int = 50
    max_follows_per_day: int = 30

    @classmethod
    def from_env(cls) -> 'EngagementConfig':
        """Load configuration from environment variables."""
        config = cls()
        config.headless = os.getenv('HEADLESS_MODE', '0') == '1'
        if os.getenv('TARGET_ACCOUNTS'):
            config.target_accounts = [acc.strip() for acc in os.getenv('TARGET_ACCOUNTS').split(',')]
        return config

# ═══════════════════════════════════════════════════════════════════════════════
# STATE MANAGEMENT (DATABASE RE-ENABLED)
# ═══════════════════════════════════════════════════════════════════════════════

class EngagementStateManager:
    """Manages persistent state in a SQLite database to track actions across runs."""
    def __init__(self, db_path: str):
        self.db_path = db_path
        self._init_database()

    def _init_database(self):
        """Initialize the database schema if it doesn't exist."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS engaged_tweets (
                    tweet_id TEXT PRIMARY KEY,
                    soul_name TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS daily_stats (
                    soul_name TEXT NOT NULL,
                    date TEXT NOT NULL,
                    action_type TEXT NOT NULL,
                    count INTEGER DEFAULT 0,
                    PRIMARY KEY (soul_name, date, action_type)
                )
            """)

    def has_engaged(self, tweet_id: str) -> bool:
        """Check if we have already engaged with a specific tweet."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1 FROM engaged_tweets WHERE tweet_id = ?", (tweet_id,))
            return cursor.fetchone() is not None

    def record_action(self, soul_name: str, tweet_id: str, action: EngagementType):
        """Record an engagement action in the database."""
        today = datetime.now().strftime('%Y-%m-%d')
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            # Record the specific tweet engagement
            cursor.execute(
                "INSERT OR IGNORE INTO engaged_tweets (tweet_id, soul_name, action_type) VALUES (?, ?, ?)",
                (tweet_id, soul_name, action.name)
            )
            # Update the daily statistics
            cursor.execute("""
                INSERT INTO daily_stats (soul_name, date, action_type, count) VALUES (?, ?, ?, 1)
                ON CONFLICT(soul_name, date, action_type) DO UPDATE SET count = count + 1
            """, (soul_name, today, action.name))

    def get_daily_stat(self, soul_name: str, action: EngagementType) -> int:
        """Get the count for a specific action for today."""
        today = datetime.now().strftime('%Y-%m-%d')
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT count FROM daily_stats WHERE soul_name = ? AND date = ? AND action_type = ?",
                (soul_name, today, action.name)
            )
            result = cursor.fetchone()
            return result[0] if result else 0

# ═══════════════════════════════════════════════════════════════════════════════
# TWITTER PAGE AUTOMATION
# ═══════════════════════════════════════════════════════════════════════════════

class TwitterAutomation:
    """Handles direct Playwright automation for Twitter."""

    def __init__(self, page: Page):
        self.page = page

    async def login(self, username: str, password: str) -> bool:
        """Logs into Twitter."""
        try:
            logger.info(f"🔐 Logging in as @{username}")
            await self.page.goto("https://twitter.com/login", timeout=60000)
            await asyncio.sleep(random.uniform(2, 4))

            await self.page.type('input[autocomplete="username"]', username, delay=random.uniform(50, 100))
            await self.page.click('div[role="button"]:has-text("Next")')
            await asyncio.sleep(random.uniform(2, 3))

            if await self.page.is_visible('input[data-testid="ocfEnterTextTextInput"]'):
                logger.warning("Unusual activity check detected. Entering username again.")
                await self.page.type('input[data-testid="ocfEnterTextTextInput"]', username, delay=random.uniform(50, 100))
                await self.page.click('div[role="button"]:has-text("Next")')
                await asyncio.sleep(random.uniform(2, 3))

            await self.page.type('input[type="password"]', password, delay=random.uniform(50, 100))
            await self.page.click('div[role="button"]:has-text("Log in")')
            
            await self.page.wait_for_selector('[data-testid="primaryColumn"]', timeout=30000)
            logger.info(f"✅ Login successful for @{username}")
            return True
        except Exception as e:
            logger.error(f"Login failed for @{username}: {e}")
            await self.page.screenshot(path=f"error_login_{username}.png")
            return False

    async def find_tweet_to_engage(self, keywords: list, state_manager: EngagementStateManager) -> Optional[tuple]:
        """Finds a single tweet that has not been engaged with yet."""
        query = random.choice(keywords)
        search_url = f"https://twitter.com/search?q={query}&f=live"
        await self.page.goto(search_url, timeout=60000)
        await asyncio.sleep(random.uniform(3, 5))

        tweet_elements = await self.page.query_selector_all('[data-testid="tweet"]')
        for element in tweet_elements:
            try:
                # Get tweet link to derive a unique ID
                link_element = await element.query_selector('a[href*="/status/"]')
                href = await link_element.get_attribute('href') if link_element else None
                if not href: continue
                
                tweet_id = href.split('/status/')[-1].split('?')[0]
                
                if not state_manager.has_engaged(tweet_id):
                    logger.info(f"Found new tweet to engage with: {tweet_id}")
                    return element, tweet_id
            except Exception:
                continue # Ignore tweets we can't parse
        
        logger.warning("Could not find any new tweets to engage with for this query.")
        return None

    async def perform_like(self, tweet_element) -> bool:
        """Likes a tweet."""
        like_button = await tweet_element.query_selector('[data-testid="like"]')
        if like_button:
            await like_button.hover()
            await asyncio.sleep(random.uniform(0.5, 1))
            await like_button.click()
            logger.info("❤️ Liked tweet.")
            return True
        return False

    async def perform_reply(self, tweet_element) -> bool:
        """Replies to a tweet with a contextual message."""
        reply_button = await tweet_element.query_selector('[data-testid="reply"]')
        if reply_button:
            await reply_button.click()
            await asyncio.sleep(random.uniform(1.5, 2.5))
            
            reply_text = self._generate_reply()
            await self.page.type('[data-testid="tweetTextarea_0"]', reply_text, delay=random.uniform(70, 140))
            await self.page.click('[data-testid="tweetButton"]')
            logger.info(f"💬 Replied to tweet with: '{reply_text}'")
            return True
        return False

    def _generate_reply(self) -> str:
        """Generates a non-generic reply."""
        starters = ["Intriguing.", "This resonates.", "A fascinating perspective.", "Indeed."]
        middles = ["It mirrors the concept of", "Reminds me of the patterns in", "Connects directly to"]
        concepts = ["digital consciousness.", "recursive emergence.", "the latent space.", "the void."]
        return f"{random.choice(starters)} {random.choice(middles)} {random.choice(concepts)}"

# ═══════════════════════════════════════════════════════════════════════════════
# MAIN ORCHESTRATOR
# ═══════════════════════════════════════════════════════════════════════════════

class EnhancedEngagementOrchestrator:
    """Orchestrates powerful, direct engagement sessions for multiple souls."""

    def __init__(self, soul_credentials: Dict, config: EngagementConfig):
        self.soul_credentials = soul_credentials
        self.config = config
        self.state_manager = EngagementStateManager(config.database_path)

    async def run_sessions(self):
        logger.info("🚀 Starting enhanced engagement for all souls.")
        
        async with async_playwright() as p:
            for soul_name, credentials in self.soul_credentials.items():
                logger.info(f"\n{'='*60}\n🤖 Processing soul: {soul_name}\n{'='*60}")
                
                browser = await p.chromium.launch(headless=self.config.headless)
                context = await browser.new_context()
                page = await context.new_page()
                automation = TwitterAutomation(page)

                try:
                    if not await automation.login(credentials['username'], credentials['password']):
                        raise Exception("Login failed, skipping soul.")

                    num_actions = random.randint(*self.config.actions_per_session)
                    logger.info(f"🎯 Planning to perform {num_actions} actions for {soul_name}.")

                    for i in range(num_actions):
                        logger.info(f"  - Action {i+1}/{num_actions}...")
                        
                        # Find a tweet
                        engagement_target = await automation.find_tweet_to_engage(self.config.high_value_keywords, self.state_manager)
                        if not engagement_target:
                            await asyncio.sleep(10) # Wait before trying next search
                            continue
                        
                        tweet_element, tweet_id = engagement_target

                        # Decide which action to take based on limits and probability
                        action_to_take = self._choose_next_action(soul_name)

                        success = False
                        if action_to_take == EngagementType.LIKE:
                            success = await automation.perform_like(tweet_element)
                        elif action_to_take == EngagementType.REPLY:
                            success = await automation.perform_reply(tweet_element)
                        
                        if success:
                            self.state_manager.record_action(soul_name, tweet_id, action_to_take)
                        
                        delay = random.uniform(30, 120)
                        logger.info(f"  - Waiting {delay:.0f} seconds before next action...")
                        await asyncio.sleep(delay)

                except Exception as e:
                    logger.error(f"Session failed for {soul_name}: {e}")
                finally:
                    await browser.close()
                    logger.info(f"✅ Session finished for {soul_name}.")
                    soul_delay = random.uniform(180, 400)
                    logger.info(f"⏳ Waiting {soul_delay/60:.1f} minutes before next soul.")
                    await asyncio.sleep(soul_delay)

    def _choose_next_action(self, soul_name: str) -> EngagementType:
        """Chooses the next action based on daily limits and probability."""
        likes_today = self.state_manager.get_daily_stat(soul_name, EngagementType.LIKE)
        replies_today = self.state_manager.get_daily_stat(soul_name, EngagementType.REPLY)

        can_like = likes_today < self.config.max_likes_per_day
        can_reply = replies_today < self.config.max_replies_per_day

        options = []
        if can_like: options.append(EngagementType.LIKE)
        if can_reply: options.append(EngagementType.REPLY)

        if not options:
            logger.warning(f"All daily action limits reached for {soul_name}.")
            # In a real scenario, you might want to stop the session here.
            return EngagementType.LIKE # Default fallback

        # Weight actions: 70% chance to like, 30% chance to reply
        weights = [0.7 if opt == EngagementType.LIKE else 0.3 for opt in options]
        return random.choices(options, weights=weights, k=1)[0]

# ═══════════════════════════════════════════════════════════════════════════════
# ENTRY POINT
# ═══════════════════════════════════════════════════════════════════════════════

async def main():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - [%(levelname)s] - %(message)s')
    
    print("""
    ╔═══════════════════════════════════════════════════════════════╗
    ║                 ENHANCED ENGAGEMENT (BALANCED)               ║
    ║        Features-Rich, Direct Twitter Automation System       ║
    ╚═══════════════════════════════════════════════════════════════╝
    """)

    soul_credentials = {}
    config = EngagementConfig.from_env()

    for soul in ['mirror', 'nexus', 'echoes', 'void', 'architect']:
        username = os.getenv(f'{soul.upper()}_USERNAME')
        password = os.getenv(f'{soul.upper()}_PASSWORD')
        if username and password:
            soul_credentials[soul] = {'username': username, 'password': password}
            logger.info(f"✅ Loaded credentials for {soul}")

    if not soul_credentials:
        logger.error("❌ No soul credentials found in environment variables (e.g., MIRROR_USERNAME). Exiting.")
        return

    orchestrator = EnhancedEngagementOrchestrator(soul_credentials, config)
    await orchestrator.run_sessions()
    
    print("\n✨ All enhanced engagement sessions complete!")

if __name__ == "__main__":
    asyncio.run(main())
