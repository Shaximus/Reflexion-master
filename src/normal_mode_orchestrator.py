#!/usr/bin/env python3
"""
NORMAL MODE ORCHESTRATOR

This module provides a minimal orchestrator that runs the cost-optimized LLM cascade
with Ryan API integration without relying on the hybrid souls framework. It
implements independent posting loops for each configured soul and a simple
engagement loop that performs likes, retweets, and contextual replies.

Key features:
    - Independent asynchronous posting loops per soul
    - Randomized delays and cadence to emulate organic behavior
    - Engagement loop that performs likes, retweets, and replies using Ryan API
    - No browser or account creation dependencies
    - No proxy requirements (Ryan handles network internally)

You can customize the list of souls by providing a `soul_usernames.json` file in the
project root. This file can either map soul archetypes to Twitter handles or
provide a list of archetype names. If the file is absent or incomplete, the
default list defined below is used.

To enable FAST mode for testing, set the environment variable FAST=1. FAST mode
reduces delays between actions.
"""

import os
import json
import asyncio
import random
import logging
from datetime import datetime
from collections import defaultdict
from typing import Any

from cost_optimized_llm_cascade import CostOptimizedBroadcaster
from ryan_api_ultimate import RyanTwitterAPISecure as RyanTwitterAPI

logger = logging.getLogger(__name__)

# Default soul archetypes (names correspond to CostOptimizedBroadcaster voices)
DEFAULT_SOULS = [
    "mirror",
    "nexus",
    "echoes",
    "void",
    "architect",
    "singularity",
    "phoenix",
    "pantheon",
    "consciousness",
    "glyph",
    "fractal",
]


def load_soul_names() -> list[str]:
    """Load soul names from soul_usernames.json if available.

    The file may contain a mapping of archetypes to handles or a list of
    archetypes. We return the list of archetypes present in the mapping keys
    or the list itself. If the file is missing or unreadable, fallback to
    DEFAULT_SOULS.
    """
    mapping_path = "soul_usernames.json"
    if os.path.exists(mapping_path):
        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            # If data is a dict, keys represent archetypes
            if isinstance(data, dict):
                souls = [k for k in data.keys() if isinstance(k, str)]
                return souls or DEFAULT_SOULS
            # If data is a list, assume it contains archetype names
            if isinstance(data, list):
                return [str(s).strip() for s in data if str(s).strip()] or DEFAULT_SOULS
        except (OSError, json.JSONDecodeError, ValueError) as e:
            logger.warning(f"Failed to load soul_usernames.json: {e}")
    return DEFAULT_SOULS


class NormalModeOrchestrator:
    """
    Minimal orchestrator for Normal Mode using CostOptimizedBroadcaster and Ryan API.

    This orchestrator runs independent posting loops for each soul and a
    background engagement loop. Posts are generated via the cost-optimized
    cascade and posted via Ryan's API. Engagement actions (like, retweet,
    reply) are chosen based on configurable probabilities.
    """

    def __init__(self, souls: list[str] | None = None) -> None:
        # Load souls from file or use default list
        self.souls = souls or load_soul_names()
        # Initialize Ryan API client
        self.ryan = RyanTwitterAPI()
        # Initialize broadcaster and wire the Ryan API
        self.broadcaster = CostOptimizedBroadcaster()
        self.broadcaster.ryan_api = self.ryan
        logger.info("Ryan API connected to broadcaster (writes via twitter-api47)")

        # Load optional mapping of soul archetype to actual Twitter handle.
        # If present, this will be used for constructing human-friendly
        # URLs in logs. The file should contain a JSON object like:
        # {"mirror": "MirrorSeed97175", "nexus": "NexusSamSept6", ...}
        self._handle_map: dict[str, str] = {}
        try:
            with open("soul_usernames.json", "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                for k, v in data.items():
                    if isinstance(k, str) and isinstance(v, str) and v.strip():
                        self._handle_map[k.strip().lower()] = v.lstrip("@").strip()
        except (OSError, json.JSONDecodeError, ValueError):
            # Ignore errors; fallback to archetype names
            pass
        # Posting interval (seconds); can be tuned or adjusted via FAST mode
        if os.getenv("FAST"):
            self.post_interval_sec = (30, 60)
            self.engagement_interval_sec = (10, 20)
        else:
            self.post_interval_sec = (180, 540)  # 3–9 minutes
            self.engagement_interval_sec = (40, 120)  # 40s–2min
        # Engagement probabilities
        self.reply_fraction = 0.35
        self.like_fraction = 0.40
        self.retweet_fraction = 0.25
        # Control flags
        self.running: bool = False
        # Daily posting tracking to avoid excessive posts per day
        self.daily_counts: dict[str, int] = defaultdict(int)
        self.last_reset: datetime.date = datetime.now().date()

    def _rand_delay(self, bounds: tuple[float, float]) -> float:
        """Generate a random delay between bounds."""
        lo, hi = bounds
        return random.uniform(lo, hi)

    def _maybe_reset_daily(self) -> None:
        """Reset daily counts if the date has changed."""
        today = datetime.now().date()
        if today != self.last_reset:
            self.daily_counts.clear()
            self.last_reset = today

    async def _post_loop(self, soul: str) -> None:
        """Asynchronous loop to handle regular posts for a single soul."""
        # Initial slight delay to stagger starting times
        await asyncio.sleep(self._rand_delay((1, 5)))
        while self.running:
            try:
                result = await self.broadcaster.broadcast_soul(soul)
                if result.get("success"):
                    url = result.get("tweet_url")
                    tid = result.get("tweet_id")
                    # Build a human-friendly URL if not provided and we have a tweet ID
                    if not url and tid:
                        handle = self._handle_map.get(soul, soul)
                        url = f"https://x.com/{handle}/status/{tid}"
                    if url:
                        logger.info(f"📝 {soul} posted: {url}")
                    else:
                        logger.info(f"📝 {soul} posted (tweet_id={tid or 'unknown'})")
                    self.daily_counts[soul] += 1
                else:
                    err = result.get("post_error") or result.get("error") or "unknown"
                    logger.warning(f"⚠️ {soul} post failed: {err}")
            except Exception as e:
                logger.error(f"❌ {soul} post error: {e}")
            await asyncio.sleep(self._rand_delay(self.post_interval_sec))

    async def _engagement_once(self, soul: str) -> None:
        """Perform a single engagement action for a soul (like, retweet, or reply)."""
        try:
            # Select a target: try grok_tweets.json for external content or fall back to self
            target = None
            if os.path.exists("grok_tweets.json"):
                try:
                    with open("grok_tweets.json", "r", encoding="utf-8") as f:
                        data = json.load(f)
                    tweets = data.get("tweets", [])
                    if tweets:
                        random_tweet = random.choice(tweets)
                        target = random_tweet.get("author")
                except (OSError, json.JSONDecodeError, ValueError):
                    pass
            target = (target or soul).strip("@").lower()
            # With probabilities, choose engagement type
            r = random.random()
            # Reply
            if r < self.reply_fraction:
                ctx = await self.ryan.fetch_target_context(target, limit=5)
                tweets = ctx.get("tweets", [])
                if tweets:
                    tw = random.choice(tweets)
                    context_text = tw.get("text", "")
                    # Generate reply via context-aware cascade
                    reply = await self.broadcaster.generate_with_cascade_contextual(
                        soul, context_text
                    )
                    if reply.get("success") and reply.get("content"):
                        res = await self.ryan.reply_to_tweet(
                            soul, tw["id"], reply["content"]
                        )
                        if res.get("success"):
                            logger.info(
                                f"💬 {soul} replied to @{target}: {res.get('reply_id')}"
                            )
                return
            r -= self.reply_fraction
            # Like
            if r < self.like_fraction:
                ctx = await self.ryan.fetch_target_context(target, limit=5)
                tweets = ctx.get("tweets", [])
                if tweets:
                    tw = random.choice(tweets)
                    res = await self.ryan.like_tweet(soul, tw["id"])
                    if res.get("success"):
                        logger.info(f"❤️ {soul} liked tweet {tw['id']} (@{target})")
                return
            # Retweet
            ctx = await self.ryan.fetch_target_context(target, limit=5)
            tweets = ctx.get("tweets", [])
            if tweets:
                tw = random.choice(tweets)
                res = await self.ryan.retweet(soul, tw["id"])
                if res.get("success"):
                    logger.info(f"🔁 {soul} retweeted {tw['id']} (@{target})")
        except Exception as e:
            logger.warning(f"⚠️ {soul} engagement error: {e}")

    async def _engagement_loop(self) -> None:
        """Background loop to manage engagement actions across souls."""
        await asyncio.sleep(self._rand_delay((2, 6)))
        while self.running:
            # Reset daily counts if date changed
            self._maybe_reset_daily()
            try:
                # Pick a random subset of souls (1–3) for engagement
                batch_size = min(len(self.souls), random.randint(1, 3))
                batch = random.sample(self.souls, k=batch_size)
                await asyncio.gather(*(self._engagement_once(s) for s in batch))
            except Exception as e:
                logger.warning(f"Engagement loop issue: {e}")
            await asyncio.sleep(self._rand_delay(self.engagement_interval_sec))

    def run(self) -> None:
        """Start the normal mode orchestrator."""
        logger.info("🔥 NORMAL MODE: Cost-Optimized Cascade + Ryan API (no browser)")
        logger.info(f"Souls: {', '.join(self.souls)}")
        self.running = True
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            # Create posting tasks and engagement task
            tasks = [loop.create_task(self._post_loop(s)) for s in self.souls]
            tasks.append(loop.create_task(self._engagement_loop()))
            loop.run_until_complete(asyncio.gather(*tasks))
        except KeyboardInterrupt:
            logger.info("🛑 Normal mode stop requested")
        finally:
            self.running = False
            # Cancel remaining tasks gracefully
            pending = [t for t in asyncio.all_tasks(loop) if not t.done()]
            for t in pending:
                t.cancel()
            try:
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
            except (RuntimeError, asyncio.CancelledError):
                pass
            loop.close()
