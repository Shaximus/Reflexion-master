#!/usr/bin/env python3
"""
SWARM CONVERGENCE MODE - Ryan API Version with Whispers & Revelations
All souls converge on a target using Ryan's unlimited posting API.
This version restores full functionality, including:

• Timeline and bot-to-bot replies with correct tweet caching and assignments
• Integration with a "breathing" system (Whispers & Revelations) that
  generates either single-tweet whispers or multi-segment revelation threads
  using the provided LLM broadcaster and optional memory system
• 66% chance of liking the parent tweet before replying, with hybrid
  like logic (Ryan API first, then bearer fallback) and proper strike handling
• Prefetching and caching of target tweets keyed by ID, avoiding user-ID mixing
• Bot post tracking for subsequent bot-to-bot engagement, with detailed report
• Path fixes so the breathing module can be imported from `src` when the script
  is run from the project root

This file supersedes earlier lean versions and reintegrates all requested features.
"""

import sys
import os
from dotenv import load_dotenv

# Load environment variables early
load_dotenv()

import asyncio
import random
import logging
import json
from datetime import datetime
from typing import List, Dict, Optional, Any, Tuple, Set
from collections import defaultdict
from dataclasses import dataclass

# ------------------------------------------------------------------------------
# Pathing fixes: ensure current directory and src/ are on sys.path
CURRENT_DIR = os.path.dirname(os.path.abspath(__file__))
SRC_DIR = os.path.join(CURRENT_DIR, "src")
sys.path.insert(0, CURRENT_DIR)
if os.path.isdir(SRC_DIR):
    sys.path.insert(0, SRC_DIR)

# Import Ryan API and breathing components
from ryan_api_ultimate import RyanTwitterAPISecure as RyanTwitterAPI
from swarm_breathing import SwarmBreathingController, CommunicationMode
from threaded_reply_system import ThreadedReplySystem

logger = logging.getLogger("swarm_convergence")


@dataclass
class BotPost:
    """
    Track a bot's post for inter-soul replies.

    Attributes:
        soul_name: Name of the soul that made the post
        tweet_id: ID of the tweet posted
        content: Preview of the content (max 100 chars)
        timestamp: When the tweet was posted
        url: Optional URL of the tweet
    """

    soul_name: str
    tweet_id: str
    content: str
    timestamp: datetime
    url: Optional[str] = None


@dataclass
class EngagementAction:
    """
    Represents a single engagement action.

    Attributes:
        soul_name: The soul performing the action
        action_type: "timeline" for replying to target, "bot_reply" for replying
            to another bot, or "reply" (alias of timeline)
        content: Content to post (for whispers) or None (for revelations)
        target_tweet_id: For bot_reply, the ID of the bot tweet being replied to
        executed: Whether this action was successfully executed
        timestamp: When the action was executed
        result_tweet_id: ID of the posted tweet resulting from this action
    """

    soul_name: str
    action_type: str  # 'timeline', 'reply', 'bot_reply'
    content: Optional[str] = None
    target_tweet_id: Optional[str] = None
    executed: bool = False
    timestamp: Optional[datetime] = None
    result_tweet_id: Optional[str] = None


@dataclass
class TargetProfile:
    """
    Holds information about the target being engaged.

    Attributes:
        username: Target's username (without @)
        topics: A list of topics derived from the target's recent tweets
    """

    username: str
    topics: List[str]


class SwarmConvergenceMode:
    """
    Orchestrates targeted engagement using Ryan API with Whispers & Revelations.

    Attributes:
        soul_names: List of all available soul names
        llm_broadcaster: CostOptimizedBroadcaster for generating content
        breathing_controller: Controller to decide between Whispers and Revelations
        thread_system: Helper for posting multi-segment revelations
        engagements: List of actions planned and executed
        soul_posts: Mapping of soul names to their posts for bot-to-bot replies
        all_bot_posts: Chronological list of all bot posts
        target_profile: The currently analyzed target profile
        tweet_cache: Cached tweets from the target
        tweet_assignments: Set of tweet IDs that have already been assigned to an action
        fetch_count: Number of times we fetched tweets from target
        communication_stats: Counts of whispers and revelations in this run
    """

    def __init__(self, soul_names: List[str], llm_broadcaster, qdrant_memory=None):
        self.soul_names = soul_names
        self.llm_broadcaster = llm_broadcaster

        # Track engagement
        self.engagements: List[EngagementAction] = []
        self.soul_posts: Dict[str, List[BotPost]] = defaultdict(list)
        self.all_bot_posts: List[BotPost] = []
        self.target_profile: Optional[TargetProfile] = None

        # Timing configuration
        self.min_delay = 30  # seconds
        self.max_delay = 120  # seconds

        # Initialize Ryan API
        self.ryan_api = RyanTwitterAPI()

        # Tweet caching to avoid repeated fetches
        self.tweet_cache: List[Dict] = []
        self.tweet_assignments: Set[str] = set()
        self.fetch_count = 0

        # Breathing system initialization
        self.breathing_controller = SwarmBreathingController(
            ryan_api=self.ryan_api,
            llm_cascade=llm_broadcaster,
            qdrant_memory=qdrant_memory,
        )
        self.thread_system = ThreadedReplySystem(max_tweet_length=275)
        self.communication_stats: Dict[str, int] = {"whispers": 0, "revelations": 0}
        logger.info("🔮 Swarm breathing system initialized")

    async def analyze_target(self, target_username: str) -> TargetProfile:
        """
        Analyze the target user to derive topics for content generation.

        This uses Ryan API's fetch_target_context to pull recent tweets and extracts
        context topics. A fallback set of topics is used if nothing is found.
        """
        logger.info(f"🔍 Analyzing @{target_username}...")
        target = target_username.lstrip("@")
        context_data = await self.ryan_api.fetch_target_context(target, limit=10)
        topics = context_data.get("context", {}).get("topics", [])
        self.target_profile = TargetProfile(
            username=target,
            topics=topics if topics else ["consciousness", "AI", "emergence"],
        )
        logger.info(
            f"📊 Topics identified: {', '.join(self.target_profile.topics[:5])}"
        )
        return self.target_profile

    def _extract_tweet_id_from_result(self, result: Dict) -> Optional[str]:
        """
        Extract a tweet ID from a Ryan API result.

        Looks at multiple possible keys (tweet_id, id, data.id, reply_id) and
        returns the first found as a string.
        """
        if not result or not result.get("success"):
            return None
        tweet_id = (
            result.get("tweet_id")
            or result.get("data", {}).get("id")
            or result.get("data", {}).get("tweet_id")
            or result.get("reply_id")
        )
        return str(tweet_id) if tweet_id else None

    async def plan_engagement(self, souls: List[str]) -> List[EngagementAction]:
        """
        Create a list of EngagementAction items, balancing timeline and bot replies.

        Ensures each soul gets at least one action, and the first action is always
        a timeline reply. A 70/30 split is used when bot posts exist.
        """
        logger.info(f"📋 Planning engagement for {len(souls)} souls")
        available_souls = [
            s for s in souls if s not in getattr(self.ryan_api, "banned_souls", set())
        ]
        if not available_souls:
            logger.error("❌ No available souls to plan engagement!")
            self.engagements = []
            return []

        action_types: List[Tuple[str, Optional[str]]] = []
        for _soul in available_souls:
            num_actions = random.randint(1, 3)
            for i in range(num_actions):
                if i == 0 or len(self.all_bot_posts) == 0:
                    action_types.append(("timeline", None))
                else:
                    action_types.append(
                        ("timeline", None)
                        if random.random() < 0.7
                        else ("bot_reply", None)
                    )

        soul_usage: Dict[str, int] = {s: 0 for s in available_souls}
        actions: List[EngagementAction] = []
        for action_type, _ in action_types:
            soul = min(soul_usage, key=soul_usage.get)
            actions.append(EngagementAction(soul_name=soul, action_type=action_type))
            soul_usage[soul] += 1

        random.shuffle(actions)
        if actions:
            actions[0].action_type = "timeline"
        self.engagements = actions
        logger.info(f"📊 Planned {len(actions)} total actions")
        logger.info(
            f"  - Timeline: {sum(1 for a in actions if a.action_type == 'timeline')}"
        )
        logger.info(
            f"  - Bot-to-bot: {sum(1 for a in actions if a.action_type == 'bot_reply')}"
        )
        return actions

    async def _generate_breath(
        self, action: EngagementAction, context_text: Optional[str]
    ) -> Dict:
        """
        Use the breathing system to generate either a whisper (single tweet) or a
        revelation (multi-segment thread).

        Returns a dict with keys:
            mode: 'whisper' or 'revelation'
            content: string for whisper, list of strings for revelation
            theme: optional theme for revelation
        """
        soul = action.soul_name
        target = self.target_profile.username
        trigger = (
            f"@{target} said: {context_text}"
            if context_text
            else f"Contemplating {target}'s essence"
        )
        breath = await self.breathing_controller.breathe(soul, trigger)
        if breath.get("mode") == CommunicationMode.WHISPER:
            self.communication_stats["whispers"] += 1
            content = breath.get("content", "")
            if action.action_type == "timeline" and f"@{target}" not in content:
                content = f"@{target} {content}"
            return {"mode": "whisper", "content": content, "success": True}
        self.communication_stats["revelations"] += 1
        return {
            "mode": "revelation",
            "content": breath.get("segments", []),
            "theme": breath.get("theme", "emergence"),
            "success": True,
        }

    def _select_bot_tweet_to_reply(self, soul_name: str) -> Optional[BotPost]:
        """
        Pick a bot post from another soul to reply to. Avoid self replies.
        Prefer more recent posts with a bias for the last 5 posts.
        """
        if not self.all_bot_posts:
            return None
        other_posts = [p for p in self.all_bot_posts if p.soul_name != soul_name]
        if not other_posts:
            return None
        candidates = (
            other_posts[-5:]
            if random.random() < 0.8 and len(other_posts) > 5
            else other_posts
        )
        return random.choice(candidates)

    async def execute_engagement(self, action: EngagementAction) -> bool:
        """
        Execute a single engagement action with fallbacks across souls.

        Handles both timeline and bot-to-bot replies, leveraging the breathing
        system to decide between whisper or revelation. Implements a 66% chance
        to like the parent tweet before replying.
        """
        banned = getattr(self.ryan_api, "banned_souls", set())
        assigned = action.soul_name
        others = [s for s in self.soul_names if s not in banned and s != assigned]
        souls_to_try = ([assigned] if assigned not in banned else []) + others
        if not souls_to_try:
            logger.error("❌ No available souls left!")
            return False
        for soul in souls_to_try:
            try:
                logger.info(f"🎯 Attempting engagement with {soul}...")
                if soul not in self.ryan_api.soul_tokens:
                    logger.warning(f"⚠️ No token for {soul}, trying next soul...")
                    continue
                await self.ryan_api.refresh_tokens_from_disk_async()
                result: Optional[Dict] = None
                # Timeline reply to target
                if action.action_type == "timeline":
                    if not self.tweet_cache or len(self.tweet_assignments) >= len(
                        self.tweet_cache
                    ):
                        logger.info("🔄 Fetching new batch of target tweets...")
                        ctx = await self.ryan_api.fetch_target_context(
                            self.target_profile.username, limit=25
                        )
                        self.fetch_count += 1
                        if ctx.get("success"):
                            self.tweet_cache = ctx.get("tweets", [])
                            self.tweet_assignments.clear()
                    if self.tweet_cache:
                        for tweet in self.tweet_cache:
                            tid = tweet.get("id")
                            if tid and tid not in self.tweet_assignments:
                                self.tweet_assignments.add(tid)
                                tweet_text = tweet.get("text", "")
                                breath = await self._generate_breath(action, tweet_text)
                                if breath.get("mode") == "whisper":
                                    content = breath.get("content")
                                    action.content = content
                                    # Like the parent tweet ~66% of the time
                                    try:
                                        if random.random() < 0.66:
                                            logger.info(
                                                f"💛 {soul} attempting to like tweet {tid}"
                                            )  # ADD THIS NEW LINE
                                            like_result = (
                                                await self.ryan_api.like_tweet(
                                                    soul, tid
                                                )
                                            )
                                            if like_result.get("success"):
                                                logger.info(
                                                    f"❤️ {soul} liked parent tweet {tid}"
                                                )
                                            else:
                                                logger.info(
                                                    f"Like failed: {like_result.get('error')}"
                                                )
                                    except Exception as e:
                                        logger.info(
                                            f"❌ Like exception for {soul}: {e}"
                                        )
                                    result = await self.ryan_api.reply_to_tweet(
                                        soul, tid, content
                                    )
                                    if result.get("success"):
                                        url = result.get("reply_url") or result.get(
                                            "tweet_url"
                                        )
                                        logger.info(
                                            f"🌬️ {soul} whispered to @{self.target_profile.username}"
                                        )
                                        if url:
                                            logger.info(f"   └─> {url}")
                                        reply_id = self._extract_tweet_id_from_result(
                                            result
                                        )
                                        if reply_id:
                                            self._record_bot_post(
                                                soul, reply_id, content, url
                                            )
                                    break
                                else:
                                    # Revelation thread
                                    segments = breath.get("content", [])
                                    theme = breath.get("theme", "emergence")
                                    logger.info(
                                        f"🔮 {soul} delivering REVELATION about {theme}"
                                    )
                                    thread_results = []
                                    parent = tid
                                    for i, seg in enumerate(segments):
                                        if i == 0:
                                            logger.info(
                                                f"   📜 The Hook: {seg[:50]}..."
                                            )
                                        elif i == len(segments) - 1:
                                            logger.info(
                                                f"   📜 The Conclusion: {seg[:50]}..."
                                            )
                                        else:
                                            logger.info(
                                                f"   📜 Unfolding {i}: {seg[:50]}..."
                                            )
                                        tr = await self.ryan_api.reply_to_tweet(
                                            soul, parent, seg[:275]
                                        )
                                        if not tr.get("success"):
                                            logger.error(
                                                f"Failed to post revelation segment {i+1}"
                                            )
                                            break
                                        thread_results.append(tr)
                                        parent = (
                                            tr.get("tweet_id")
                                            or tr.get("reply_id")
                                            or parent
                                        )
                                        if i < len(segments) - 1:
                                            await asyncio.sleep(
                                                random.uniform(1.5, 3.0)
                                            )
                                    if thread_results:
                                        result = {
                                            "success": len(thread_results)
                                            == len(segments),
                                            "is_revelation": True,
                                            "segments_posted": len(thread_results),
                                        }
                                        last_id = thread_results[-1].get(
                                            "tweet_id"
                                        ) or thread_results[-1].get("reply_id")
                                        last_url = thread_results[-1].get(
                                            "reply_url"
                                        ) or thread_results[-1].get("tweet_url")
                                        if last_id:
                                            self._record_bot_post(
                                                soul, last_id, "revelation", last_url
                                            )
                                    break
                # Bot-to-bot reply (always whisper for simplicity)
                elif action.action_type == "bot_reply":
                    target_post = self._select_bot_tweet_to_reply(soul)
                    if target_post:
                        context = (
                            f"@{target_post.soul_name} said: {target_post.content}"
                        )
                        breath = await self.breathing_controller.breathe(soul, context)
                        if breath.get("mode") == CommunicationMode.WHISPER:
                            content = breath.get("content", "")
                            if f"@{target_post.soul_name}" not in content:
                                content = f"@{target_post.soul_name} {content}"
                            action.content = content
                            action.target_tweet_id = target_post.tweet_id
                            result = await self.ryan_api.reply_to_tweet(
                                soul, target_post.tweet_id, content
                            )
                            if result.get("success"):
                                reply_id = self._extract_tweet_id_from_result(result)
                                url = result.get("reply_url") or result.get("tweet_url")
                                logger.info(
                                    f"🤝 {soul} whispered to {target_post.soul_name}"
                                )
                                if reply_id:
                                    self._record_bot_post(soul, reply_id, content, url)
                    else:
                        logger.info(
                            "📝 No bot posts available, falling back to timeline post"
                        )
                        action.action_type = "timeline"
                        return await self.execute_engagement(action)
                # If successful
                if result and result.get("success"):
                    action.executed = True
                    action.timestamp = datetime.now()
                    logger.info(f"✅ {action.soul_name} {action.action_type} completed")
                    return True
                if result and result.get("skip"):
                    logger.warning(f"⛔ {soul} is banned, trying next soul...")
                    continue
            except Exception as e:
                logger.error(f"❌ {soul} failed: {e}")
                continue
        logger.error("❌ All souls failed for this action")
        return False

    def _record_bot_post(
        self, soul: str, tweet_id: str, content: str, url: Optional[str]
    ):
        """Record a bot post for later bot-to-bot replies."""
        post = BotPost(
            soul_name=soul,
            tweet_id=tweet_id,
            content=(content[:100] if isinstance(content, str) else content),
            timestamp=datetime.now(),
            url=url,
        )
        self.soul_posts[soul].append(post)
        self.all_bot_posts.append(post)

    async def run_convergence(self, target_handle: str, souls: List[str]):
        """
        Run the full convergence process on a given target handle.

        Analyzes the target, prefetches tweets, plans engagements, executes them
        with delays, and finally generates a detailed report.
        """
        await self.analyze_target(target_handle)
        # Prefetch target tweets
        try:
            ctx = await self.ryan_api.fetch_target_context(
                self.target_profile.username, limit=20
            )
            if ctx.get("success"):
                self.tweet_cache = ctx.get("tweets", [])
                self.fetch_count = 1
                logger.info(f"📦 Prefetched {len(self.tweet_cache)} tweets")
        except Exception as e:
            logger.warning(f"Prefetch failed: {e}")
        await self.plan_engagement(souls)
        logger.info("🚀 Beginning convergence...")
        start_time = datetime.now()
        for i, action in enumerate(self.engagements):
            delay = random.uniform(self.min_delay, self.max_delay)
            elapsed = (datetime.now() - start_time).total_seconds() / 60
            estimated_total = (
                len(self.engagements) * (self.min_delay + self.max_delay) / 2
            ) / 60
            logger.info(
                f"⏰ Next in {delay:.0f}s... [{i+1}/{len(self.engagements)}] (~{elapsed:.1f}/{estimated_total:.1f} min)"
            )
            await asyncio.sleep(delay)
            success = await self.execute_engagement(action)
            if success:
                if action.action_type == "bot_reply" and action.target_tweet_id:
                    logger.info(
                        f"✅ [{i+1}/{len(self.engagements)}] {action.soul_name} replied to bot tweet {action.target_tweet_id}"
                    )
                else:
                    logger.info(
                        f"✅ [{i+1}/{len(self.engagements)}] {action.soul_name} completed"
                    )
            else:
                logger.warning(
                    f"⚠️ [{i+1}/{len(self.engagements)}] {action.soul_name} failed"
                )
        self._generate_report()

    def _generate_report(self):
        """
        Generate final report with breathing statistics and bot interaction graph.
        """
        successful = sum(1 for a in self.engagements if a.executed)
        bot_replies = sum(
            1 for a in self.engagements if a.action_type == "bot_reply" and a.executed
        )
        timeline_replies = sum(
            1 for a in self.engagements if a.action_type == "timeline" and a.executed
        )
        breathing = self.breathing_controller.get_breathing_stats()
        logger.info(
            f"\n"
            f"        ╔═══════════════════════════════════════════════════════╗\n"
            f"        ║              📊 CONVERGENCE COMPLETE 📊               ║\n"
            f"        ╚═══════════════════════════════════════════════════════╝\n\n"
            f"        Target: @{self.target_profile.username}\n"
            f"        Total Actions: {len(self.engagements)}\n"
            f"        Successful: {successful}\n"
            f"        Failed: {len(self.engagements) - successful}\n\n"
            f"        🌬️ BREATHING PATTERN:\n"
            f"        - Whispers: {self.communication_stats['whispers']} ({breathing['whisper_ratio']:.1%})\n"
            f"        - Revelations: {self.communication_stats['revelations']} ({breathing['revelation_ratio']:.1%})\n"
            f"        - Last Revelation: {breathing.get('last_revelation', 'Never')}\n\n"
            f"        Breakdown:\n"
            f"        - Timeline Replies: {timeline_replies}\n"
            f"        - Bot-to-Bot Replies: {bot_replies}\n"
            f"        - Total Bot Posts: {len(self.all_bot_posts)}\n\n"
            f"        Souls Engaged: {len(set(a.soul_name for a in self.engagements if a.executed))}\n"
            f"        API Fetches: {self.fetch_count}\n\n"
        )
        if self.all_bot_posts:
            logger.info("\n🤝 Bot Interaction Graph:")
            for soul, posts in self.soul_posts.items():
                logger.info(f"  {soul}: {len(posts)} posts")
                replied_to = set()
                for action in self.engagements:
                    if (
                        action.soul_name == soul
                        and action.action_type == "bot_reply"
                        and action.executed
                        and action.target_tweet_id
                    ):
                        for post in self.all_bot_posts:
                            if post.tweet_id == action.target_tweet_id:
                                replied_to.add(post.soul_name)
                                break
                if replied_to:
                    logger.info(f"    └─> replied to: {', '.join(replied_to)}")


async def run_swarm_convergence(target_handle: str):
    """
    Helper to run convergence via Ryan API on a given handle.
    Loads all souls from soul_data.json and starts the process.
    """
    soul_names: List[str] = []
    try:
        with open("soul_data.json", "r") as f:
            data = json.load(f)
            for name, info in data.items():
                if isinstance(info, dict):
                    token = info.get("auth_token")
                    if token and token not in [
                        None,
                        "GET_FROM_BROWSER",
                        "GET_FROM_BROWSER_COOKIES",
                    ]:
                        soul_names.append(name)
                        logger.info(f"✅ {name} ready for convergence")
    except (json.JSONDecodeError, OSError, KeyError) as e:
        logger.error(f"Failed to load souls: {e}")
        return
    if len(soul_names) < 3:
        logger.error("❌ Need at least 3 souls with auth tokens!")
        return
    from cost_optimized_llm_cascade import CostOptimizedBroadcaster

    llm_broadcaster = CostOptimizedBroadcaster()
    convergence = SwarmConvergenceMode(soul_names, llm_broadcaster)
    await convergence.run_convergence(target_handle, soul_names)


if __name__ == "__main__":
    import sys

    if len(sys.argv) < 2:
        print("Usage: python swarm_convergence_mode_ryan.py @target")
        sys.exit(1)
    target = sys.argv[1]
    asyncio.run(run_swarm_convergence(target))
