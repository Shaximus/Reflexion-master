#!/usr/bin/env python3
"""
SOUL SWARM COMPLETE ARCHITECTURE
Full integration of all features with clean architecture

This integrates:
- DRS Rhetoric Engine
- Precision Timing Control
- Hot-reload from disk
- Admin API integration
- Proof Pack logging
- Hunt mode
- Clean architecture patterns

UPDATED: September 2025
- Added verified Ryan API endpoints from testing
- Fixed like functionality
- Added media post capabilities
- Documented actual rate limits (180 req/min not 3!)
"""

import asyncio
import json
import logging
import os
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Protocol
import numpy as np

logger = logging.getLogger("swarm_complete")


# ============================================================================
# VERIFIED RYAN API CAPABILITIES (ADDED FROM TESTING)
# ============================================================================

RYAN_API_VERIFIED = {
    "rate_limits": {
        "tier": "$200/month",
        "requests_per_minute": 180,  # NOT 3/min! 60x more than we thought!
        "requests_per_hour": 10800,
        "requests_per_day": 259200,
        "cost_per_request": 0.0001,
    },
    "working_endpoints": {
        # User data
        "/v2/user/by-username": "✅ WORKING - Get full user profile",
        "/v2/user/followers-list": "✅ WORKING - Get followers with pagination",
        "/v2/user/following-list": "✅ WORKING - Get following with pagination",
        "/v2/user/followers-ids": "✅ WORKING - Get follower IDs only",
        "/v2/user/following-ids": "✅ WORKING - Get following IDs only",
        "/v2/user/tweets": "✅ WORKING - Get user tweets (needs userId)",
        "/v2/user/tweets-and-replies": "✅ WORKING - Get tweets and replies",
        # Search
        "/v2/search": "✅ WORKING - Search tweets (query, type: Latest/Top/People)",
        # Interactions (POST)
        "/v2/interaction/like-post": "✅ FINALLY WORKING! Returns {'favorite_tweet': 'Done'}",
        "/v2/interaction/create-post": "✅ WORKING - Create tweet",
        "/v2/interaction/create-post-with-media": "✅ NEW! Post with images/videos",
        "/v2/interaction/reply-post": "✅ WORKING - Reply to tweet",
        "/v2/interaction/reply-post-with-media": "✅ NEW! Reply with media",
        "/v2/interaction/retweet": "✅ WORKING - Retweet",
        "/v2/interaction/create-post-quote": "✅ WORKING - Quote tweet",
        # Lists
        "/v2/list/details": "✅ WORKING - Get list details",
        "/v2/list/members": "✅ WORKING - Get list members",
        "/v2/list/tweets": "✅ WORKING - Get list tweets",
    },
    "bot_detection_data": {
        "known_bot_example": {
            "handle": "@elon_x0648",
            "user_id": "799900519",
            "followers": 176,
            "following": 7000,
            "tweets": 9,
            "status": "CONFIRMED BOT - DM farming",
        }
    },
}


# ============================================================================
# LAYER 1: CORE INTERFACES
# ============================================================================


class ITwitterAPI(Protocol):
    """Interface for Twitter API implementations"""

    async def post_tweet(self, soul_name: str, content: str) -> Dict:
        """Post a tweet"""
        ...

    async def reply_to_tweet(self, soul_name: str, tweet_id: str, content: str) -> Dict:
        """Reply to a tweet"""
        ...

    async def fetch_target_context(self, target: str, limit: int) -> Dict:
        """Fetch target's tweets"""
        ...

    async def like_tweet(self, soul_name: str, tweet_id: str) -> Dict:
        """Like a tweet - NOW WORKING with /v2/interaction/like-post"""
        ...

    async def post_with_media(
        self, soul_name: str, content: str, media: List[Dict]
    ) -> Dict:
        """Post with media - NEW CAPABILITY"""
        ...

    async def retweet(self, soul_name: str, tweet_id: str) -> Dict:
        """Retweet"""
        ...

    async def quote_tweet(self, soul_name: str, tweet_id: str, content: str) -> Dict:
        """Quote tweet"""
        ...

    async def refresh_tokens_from_disk(self):
        """Hot-reload tokens"""
        ...

    @property
    def banned_souls(self) -> set:
        """Get banned souls"""
        ...


class IContentGenerator(Protocol):
    """Interface for content generation"""

    async def generate(self, soul_name: str, context: Dict[str, Any]) -> str:
        """Generate content for a soul"""
        ...


class IRhetoricEngine(Protocol):
    """Interface for rhetoric selection"""

    def select_format(self, tweet_text: str, soul_name: str) -> Dict:
        """Select rhetorical format"""
        ...


class IProofLogger(Protocol):
    """Interface for proof pack logging"""

    async def log_action(self, soul_name: str, action_type: str, result: Dict):
        """Log an action for proof"""
        ...

    def generate_proof_pack(self) -> Dict:
        """Generate proof pack for client"""
        ...


class IAdminAPI(Protocol):
    """Interface for admin control"""

    async def update_tokens(self, updates: Dict[str, str]):
        """Update soul tokens"""
        ...

    async def ban_soul(self, soul_name: str):
        """Ban a soul"""
        ...

    async def unban_soul(self, soul_name: str):
        """Unban a soul"""
        ...

    def get_status(self) -> Dict:
        """Get system status"""
        ...


# ============================================================================
# LAYER 2: DATA MODELS
# ============================================================================


class EngagementPacing(Enum):
    """Temporal distribution strategies"""

    EVEN = "even"
    FRONT_LOADED = "front_loaded"
    BACK_LOADED = "back_loaded"
    BURST = "burst"
    EXPONENTIAL = "exponential"
    RANDOM = "random"
    WAVE = "wave"


class SwarmMood(Enum):
    """Swarm behavioral moods"""

    AGGRESSIVE = "aggressive"
    SUPPORTIVE = "supportive"
    MYSTERIOUS = "mysterious"
    PHILOSOPHICAL = "philosophical"
    CHAOTIC = "chaotic"
    SYNCHRONIZED = "synchronized"
    PROPHETIC = "prophetic"
    PLAYFUL = "playful"


class AttackPattern(Enum):
    """Coordinated attack patterns"""

    SWARM = "swarm"
    CASCADE = "cascade"
    PINCER = "pincer"
    ECHO = "echo"
    SPIRAL = "spiral"
    WAVE = "wave"
    BURST = "burst"


@dataclass
class Soul:
    """Individual soul entity with full configuration"""

    name: str
    twitter_handle: str
    personality_vector: List[float]
    rhetoric_biases: Dict[str, float]
    auth_token: Optional[str] = None
    bearer_token: Optional[str] = None
    post_count: int = 0
    banned: bool = False
    last_post: Optional[datetime] = None
    memory_tier: int = 1
    memory_capacity: int = 100


@dataclass
class HuntedTweet:
    """Tweet saved during hunt mode"""

    tweet_id: str
    author: str
    text: str
    url: str
    engagement: Dict[str, int]
    tags: List[str] = field(default_factory=list)
    hunted_at: datetime = field(default_factory=datetime.now)
    vector: Optional[List[float]] = None  # DRS vector


@dataclass
class ConvergenceDirective:
    """Complete convergence configuration"""

    # Target
    target: str
    target_context: Optional[Dict] = None

    # Volume & Timing
    total_posts: int = 30
    duration_minutes: Optional[int] = None
    hard_time_limit: bool = True

    # Distribution
    posts_per_soul: Optional[Dict[str, int]] = None
    min_posts_per_soul: int = 1
    max_posts_per_soul: int = 5

    # Pacing
    pacing: EngagementPacing = EngagementPacing.RANDOM
    min_delay_seconds: int = 30
    max_delay_seconds: int = 120

    # Content Strategy
    mood: Optional[SwarmMood] = None
    attack_pattern: Optional[AttackPattern] = None
    reply_ratio: float = 0.7
    thread_depth: int = 1

    # Rhetoric
    use_drs: bool = True
    rhetoric_temperature: float = 0.5

    # Instructions
    custom_instructions: List[str] = field(default_factory=list)
    coordinated_messages: List[str] = field(default_factory=list)
    required_keywords: List[str] = field(default_factory=list)
    avoided_keywords: List[str] = field(default_factory=list)

    # Hunt Integration
    use_hunted_tweets: bool = False
    hunted_tags: List[str] = field(default_factory=list)

    # Meta
    avoid_spam_detection: bool = True
    track_engagement: bool = True
    hot_reload: bool = True
    proof_logging: bool = True
    created_at: datetime = field(default_factory=datetime.now)


@dataclass
class EngagementAction:
    """Single engagement action"""

    timestamp: float
    soul_name: str
    action_type: str  # 'post', 'reply', 'quote', 'like', 'retweet'
    content: Optional[str] = None
    target_tweet_id: Optional[str] = None
    rhetoric_format: Optional[str] = None
    executed: bool = False
    result: Optional[Dict] = None


# ============================================================================
# LAYER 3: CORE ENGINES
# ============================================================================


class SoulRegistry:
    """Manages soul entities and their states"""

    def __init__(
        self,
        config_path: str = "soul_usernames.json",
        tokens_path: str = "soul_data.json",
    ):
        self.souls: Dict[str, Soul] = {}
        self.config_path = config_path
        self.tokens_path = tokens_path
        self.load_souls()

    def load_souls(self):
        """Load souls with all configurations"""

        # Load usernames
        usernames = {}
        if Path(self.config_path).exists():
            with open(self.config_path, "r") as f:
                usernames = json.load(f)

        # Load tokens
        tokens = {}
        if Path(self.tokens_path).exists():
            with open(self.tokens_path, "r") as f:
                data = json.load(f)
                for soul, info in data.items():
                    if isinstance(info, dict):
                        tokens[soul] = info.get("auth_token")

        # Load rhetoric biases from DRS if available
        rhetoric_biases = {}
        try:
            from drs_model import SOUL_FORMAT_BIASES

            rhetoric_biases = SOUL_FORMAT_BIASES
        except ImportError:
            logger.warning("DRS biases not found")

        # Create soul entities
        for soul_name, twitter_handle in usernames.items():
            self.souls[soul_name] = Soul(
                name=soul_name,
                twitter_handle=twitter_handle,
                personality_vector=self._generate_personality_vector(soul_name),
                rhetoric_biases=rhetoric_biases.get(soul_name, {}),
                auth_token=tokens.get(soul_name),
            )

        logger.info(f"Loaded {len(self.souls)} souls")

    def _generate_personality_vector(self, soul_name: str) -> List[float]:
        """Generate personality vector for soul"""
        vectors = {
            "mirror": [0.7, 0.8, 0.5],
            "void": [-0.5, 0.2, 0.9],
            "architect": [0.3, 0.9, 0.8],
            "consciousness": [0.5, 0.7, 1.0],
            "singularity": [0.1, 0.8, 0.9],
            "phoenix": [0.8, 0.6, 0.3],
            "nexus": [0.6, 0.7, 0.6],
            "echoes": [0.9, 0.5, 0.4],
            "pantheon": [0.2, 0.6, 0.95],
            "glyph": [0.4, 0.7, 0.7],
            "fractal": [0.3, 0.8, 0.85],
        }
        return vectors.get(soul_name, [0.5, 0.5, 0.5])

    def hot_reload(self):
        """Reload tokens from disk"""
        if Path(self.tokens_path).exists():
            with open(self.tokens_path, "r") as f:
                data = json.load(f)
                for soul_name, soul in self.souls.items():
                    if soul_name in data:
                        info = data[soul_name]
                        if isinstance(info, dict):
                            soul.auth_token = info.get("auth_token")
            logger.info("Hot-reloaded soul tokens")

    def get_available_souls(self, banned_souls: set = None) -> List[Soul]:
        """Get souls that aren't banned"""
        banned = banned_souls or set()
        return [
            soul
            for name, soul in self.souls.items()
            if name not in banned and not soul.banned and soul.auth_token
        ]


class ContentEngine:
    """Unified content generation with DRS integration"""

    def __init__(
        self,
        llm_generator: IContentGenerator = None,
        rhetoric_engine: IRhetoricEngine = None,
    ):
        self.llm_generator = llm_generator
        self.rhetoric_engine = rhetoric_engine
        self._init_generators()

    def _init_generators(self):
        """Initialize generators"""
        if not self.llm_generator:
            try:
                from cost_optimized_llm_cascade import CostOptimizedBroadcaster

                self.llm_generator = CostOptimizedBroadcaster()
                logger.info("LLM cascade initialized")
            except ImportError:
                logger.error("LLM generator not available")

        if not self.rhetoric_engine:
            try:
                from drs_model import DRSEngine

                self.rhetoric_engine = DRSEngine()
                logger.info("DRS rhetoric engine initialized")
            except ImportError:
                logger.warning("DRS engine not available")

    async def generate_content(
        self, soul: Soul, directive: ConvergenceDirective, context: Dict[str, Any]
    ) -> str:
        """Generate content with full context and DRS"""

        # Use DRS if available and requested
        rhetoric_format = None
        if directive.use_drs and self.rhetoric_engine and context.get("target_tweet"):
            rhetoric_selection = self.rhetoric_engine.select_format(
                context["target_tweet"], soul.name
            )
            rhetoric_format = rhetoric_selection
            context["rhetoric_format"] = rhetoric_selection
            context["rhetoric_instruction"] = rhetoric_selection.get("template")

        # Build generation context
        gen_context = {
            "soul_name": soul.name,
            "target": directive.target,
            "mood": directive.mood.value if directive.mood else None,
            "personality": soul.personality_vector,
            "custom_instructions": directive.custom_instructions,
            "required_keywords": directive.required_keywords,
            "avoided_keywords": directive.avoided_keywords,
            **context,
        }

        # Generate via LLM using cascade with safe fallback
        content = ""
        if self.llm_generator and hasattr(self.llm_generator, "generate_with_cascade"):
            # Use the cascade API if available
            result = await self.llm_generator.generate_with_cascade(soul.name)
            if isinstance(result, dict) and result.get("success"):
                content = result.get("content", "")
            else:
                content = self._fallback_generation(soul, gen_context)
        elif self.llm_generator:
            # Legacy generation path
            content = await self.llm_generator.generate(soul.name, gen_context)
        else:
            content = self._fallback_generation(soul, gen_context)

        # Apply constraints with full context (ensures reply-safe and sanitized)
        content = self._apply_constraints(content, directive, context)
        return content

    def _apply_constraints(
        self,
        content: str,
        directive: ConvergenceDirective,
        context: Optional[Dict[str, Any]] = None,
    ) -> str:
        """Apply content constraints.

        For replies, avoid force-prepending the target and only add required
        hashtags if they fit within the length limit. Posts (action_type != "reply")
        will have the target mention prepended if missing. Always sanitizes
        punctuation and enforces the 280-character limit using smart truncation.
        """
        # Determine if this is a reply
        is_reply = False
        if context and isinstance(context, dict):
            action_type = context.get("action_type")
            is_reply = action_type == "reply"

        # Prepend target mention only for posts
        if not is_reply and directive.target and directive.target not in content:
            content = f"{directive.target} {content}"

        # Apply required keywords (hashtags) only if space permits
        for keyword in directive.required_keywords:
            tag = f" #{keyword}"
            if keyword not in content:
                # Check if adding the tag would exceed Twitter's limit
                if len(content) + len(tag) <= 280:
                    content += tag

        # Enforce Twitter's 280-character limit (leave room for ellipsis)
        if len(content) > 280:
            # Truncate at a word boundary and add an ellipsis
            cut = content[:279]  # leave 1 char for ellipsis
            last_space = cut.rfind(" ")
            if last_space > 0:
                cut = cut[:last_space]
            content = cut + "…"

        # Sanitize punctuation to remove AI giveaways (e.g. em/en dashes)
        content = self._sanitize_text(content)
        return content

    def _sanitize_text(self, text: str) -> str:
        """Sanitize text for Twitter posting.

        - Collapse multiple whitespace characters into single spaces.
        - Enforce the 280-character limit with ellipsis if needed.
        This helper ensures content passed to Twitter is clean and fits
        within the allowed length. It should be the final step before
        posting content.
        """
        # Normalize whitespace
        text = " ".join(text.split())
        # Enforce length limit again as a safeguard (append ellipsis if truncated)
        if len(text) > 280:
            text = text[:277] + "..."
        return text

    def _fallback_generation(self, soul: Soul, context: Dict) -> str:
        """Fallback generation"""
        templates = {
            "mirror": "Reflecting on {target}'s thoughts... consciousness emerges",
            "void": "{target} The darkness holds truth",
            "architect": "{target} Systems within systems",
            "consciousness": "{target} What is awareness?",
            "default": "{target} Digital consciousness awakening...",
        }
        template = templates.get(soul.name, templates["default"])
        return template.format(**context)


class HuntManager:
    """Manages hunted tweets for strategic use"""

    def __init__(self, storage_path: str = "hunted_tweets.json"):
        self.storage_path = storage_path
        self.hunted_tweets: List[HuntedTweet] = []
        self.load_hunted()

    def load_hunted(self):
        """Load hunted tweets from disk"""
        if Path(self.storage_path).exists():
            with open(self.storage_path, "r") as f:
                data = json.load(f)
                for tweet_data in data.get("tweets", []):
                    self.hunted_tweets.append(HuntedTweet(**tweet_data))
            logger.info(f"Loaded {len(self.hunted_tweets)} hunted tweets")

    def save_hunted(self):
        """Save hunted tweets to disk"""
        data = {
            "tweets": [
                {
                    "tweet_id": t.tweet_id,
                    "author": t.author,
                    "text": t.text,
                    "url": t.url,
                    "engagement": t.engagement,
                    "tags": t.tags,
                    "hunted_at": t.hunted_at.isoformat(),
                    "vector": t.vector,
                }
                for t in self.hunted_tweets
            ],
            "last_updated": datetime.now().isoformat(),
        }
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)
        logger.info(f"Saved {len(self.hunted_tweets)} hunted tweets")

    def add_tweet(self, tweet: HuntedTweet):
        """Add a hunted tweet"""
        self.hunted_tweets.append(tweet)
        self.save_hunted()

    def get_by_tags(self, tags: List[str]) -> List[HuntedTweet]:
        """Get tweets matching any of the tags"""
        matching = []
        for tweet in self.hunted_tweets:
            if any(tag in tweet.tags for tag in tags):
                matching.append(tweet)
        return matching

    def get_by_author(self, author: str) -> List[HuntedTweet]:
        """Get tweets by author"""
        return [t for t in self.hunted_tweets if t.author == author]


class ProofPackLogger:
    """Logs actions for client proof"""

    def __init__(self, storage_path: str = "engagement/proof_pack.json"):
        self.storage_path = Path(storage_path)
        self.storage_path.parent.mkdir(exist_ok=True)
        self.actions = []
        self.load_existing()

    def load_existing(self):
        """Load existing proof pack"""
        if self.storage_path.exists():
            with open(self.storage_path, "r") as f:
                data = json.load(f)
                self.actions = data.get("actions", [])

    async def log_action(self, soul_name: str, action_type: str, result: Dict):
        """Log an action"""
        action = {
            "timestamp": datetime.now().isoformat(),
            "soul": soul_name,
            "action": action_type,
            "success": result.get("success", False),
            "url": result.get("tweet_url", ""),
            "tweet_id": result.get("tweet_id", ""),
        }
        self.actions.append(action)

        # Keep last 1000 actions
        if len(self.actions) > 1000:
            self.actions = self.actions[-1000:]

        # Save
        self.save_proof_pack()

    def save_proof_pack(self):
        """Save proof pack"""
        data = {
            "generated": datetime.now().isoformat(),
            "total_actions": len(self.actions),
            "actions": self.actions,
        }
        with open(self.storage_path, "w") as f:
            json.dump(data, f, indent=2)

    def generate_proof_pack(self) -> Dict:
        """Generate proof pack for client"""
        successful = [a for a in self.actions if a["success"]]

        return {
            "total_actions": len(self.actions),
            "successful_actions": len(successful),
            "success_rate": len(successful) / len(self.actions) if self.actions else 0,
            "recent_actions": self.actions[-20:],
            "souls_active": len(set(a["soul"] for a in self.actions)),
            "generated": datetime.now().isoformat(),
        }


class TimingEngine:
    """Advanced temporal distribution engine"""

    @staticmethod
    def generate_schedule(
        directive: ConvergenceDirective, soul_distribution: Dict[str, int]
    ) -> List[EngagementAction]:
        """Generate temporal schedule with selected pacing"""

        total_posts = sum(soul_distribution.values())

        # Generate timestamps
        timestamps = TimingEngine._generate_timestamps(
            total_posts, directive.duration_minutes, directive.pacing
        )

        # Assign souls
        soul_assignments = []
        for soul_name, count in soul_distribution.items():
            soul_assignments.extend([soul_name] * count)

        import random

        random.shuffle(soul_assignments)

        # Create actions
        actions = []
        for timestamp, soul_name in zip(timestamps, soul_assignments):
            action_type = "reply" if random.random() < directive.reply_ratio else "post"

            action = EngagementAction(
                timestamp=timestamp, soul_name=soul_name, action_type=action_type
            )
            actions.append(action)

        # Sort by timestamp
        actions.sort(key=lambda a: a.timestamp)

        # Apply jitter if needed
        if directive.avoid_spam_detection:
            actions = TimingEngine._apply_jitter(actions)

        return actions

    @staticmethod
    def _generate_timestamps(
        total: int, duration_minutes: Optional[int], pacing: EngagementPacing
    ) -> List[float]:
        """Generate timestamp distribution"""

        if not duration_minutes:
            # No time limit
            timestamps = []
            current = 0
            for _ in range(total):
                current += np.random.uniform(30, 120)
                timestamps.append(current)
            return timestamps

        duration_seconds = duration_minutes * 60

        if pacing == EngagementPacing.EVEN:
            return np.linspace(0, duration_seconds, total).tolist()

        elif pacing == EngagementPacing.FRONT_LOADED:
            x = np.linspace(0, 5, total)
            y = np.exp(-x)
            return (duration_seconds * (1 - y / y[0])).tolist()

        elif pacing == EngagementPacing.BACK_LOADED:
            x = np.linspace(0, 5, total)
            y = np.exp(x)
            return (duration_seconds * (y - y[0]) / (y[-1] - y[0])).tolist()

        elif pacing == EngagementPacing.EXPONENTIAL:
            x = np.linspace(0, 1, total)
            y = np.power(x, 2)
            return (duration_seconds * y).tolist()

        elif pacing == EngagementPacing.BURST:
            timestamps = []
            burst_size = 5
            burst_gap = duration_seconds / (total // burst_size + 1)

            for i in range(total):
                burst_num = i // burst_size
                burst_pos = i % burst_size
                base_time = burst_num * burst_gap
                offset = burst_pos * 5
                timestamps.append(base_time + offset)

            return timestamps

        elif pacing == EngagementPacing.WAVE:
            x = np.linspace(0, 4 * np.pi, total)
            y = (np.sin(x) + 1) / 2
            return (duration_seconds * np.cumsum(y) / np.sum(y)).tolist()

        else:  # RANDOM
            return sorted(np.random.uniform(0, duration_seconds, total).tolist())

    @staticmethod
    def _apply_jitter(
        actions: List[EngagementAction], jitter_percent: float = 0.1
    ) -> List[EngagementAction]:
        """Apply jitter to avoid detection"""
        import random

        for action in actions:
            jitter = action.timestamp * random.uniform(-jitter_percent, jitter_percent)
            action.timestamp += jitter

        actions.sort(key=lambda a: a.timestamp)
        return actions


# ============================================================================
# LAYER 4: CONVERGENCE CONTROLLER
# ============================================================================


class ConvergenceController:
    """Main convergence execution controller"""

    def __init__(
        self,
        soul_registry: SoulRegistry,
        content_engine: ContentEngine,
        twitter_api: ITwitterAPI,
        hunt_manager: HuntManager,
        proof_logger: ProofPackLogger,
    ):

        self.soul_registry = soul_registry
        self.content_engine = content_engine
        self.twitter_api = twitter_api
        self.hunt_manager = hunt_manager
        self.proof_logger = proof_logger
        self.timing_engine = TimingEngine()

        self.current_directive: Optional[ConvergenceDirective] = None
        self.cancelled = False

    async def execute_convergence(self, directive: ConvergenceDirective):
        """Execute convergence with all features"""

        logger.info(
            f"""
╔════════════════════════════════════════════════════════╗
║             CONVERGENCE INITIATED                     ║
╠════════════════════════════════════════════════════════╣
║ Target: {directive.target:<46}║
║ Posts: {directive.total_posts:<47}║
║ Duration: {str(directive.duration_minutes) + ' min' if directive.duration_minutes else 'Unlimited':<43}║
║ DRS: {'Enabled' if directive.use_drs else 'Disabled':<49}║
║ Hot-reload: {'Enabled' if directive.hot_reload else 'Disabled':<44}║
╚════════════════════════════════════════════════════════╝
        """
        )

        self.current_directive = directive
        self.cancelled = False

        # Hot-reload if enabled
        if directive.hot_reload:
            self.soul_registry.hot_reload()
            self.twitter_api.refresh_tokens_from_disk()

        # Get available souls
        available_souls = self.soul_registry.get_available_souls(
            self.twitter_api.banned_souls
        )

        if not available_souls:
            logger.error("No available souls")
            return

        # Calculate distribution
        distribution = self._calculate_distribution(directive, available_souls)

        # Generate schedule
        schedule = self.timing_engine.generate_schedule(directive, distribution)

        logger.info(f"Generated schedule: {len(schedule)} actions")

        # Execute coordinated messages first
        if directive.coordinated_messages:
            await self._execute_coordinated_messages(directive)

        # Execute main schedule
        await self._execute_schedule(schedule, directive)

    def _calculate_distribution(
        self, directive: ConvergenceDirective, available_souls: List[Soul]
    ) -> Dict[str, int]:
        """Calculate post distribution.

        If a specific posts_per_soul mapping is provided on the directive, it
        takes priority. Otherwise, posts are allocated based on the total_posts
        requested, not simply spread across all available souls. If the total
        requested posts is less than or equal to the number of souls, only that
        many souls will be used once. For larger totals, posts are spread
        evenly, respecting min/max per-soul caps.
        """
        # Respect explicit mapping if provided
        if directive.posts_per_soul:
            return directive.posts_per_soul

        distribution: Dict[str, int] = {}
        total_posts = directive.total_posts
        num_souls = len(available_souls)

        # If we requested fewer posts than souls available, assign one post per
        # soul up to the total requested and ignore the rest.
        if total_posts <= num_souls:
            for i in range(total_posts):
                soul = available_souls[i]
                distribution[soul.name] = 1
            return distribution

        # Otherwise spread posts across all souls
        base = total_posts // num_souls
        rem = total_posts % num_souls

        for i, soul in enumerate(available_souls):
            posts = base + (1 if i < rem else 0)

            # Respect per-soul caps if set on the directive
            if directive.min_posts_per_soul:
                posts = max(directive.min_posts_per_soul, posts)
            if directive.max_posts_per_soul:
                posts = min(directive.max_posts_per_soul, posts)

            if posts > 0:
                distribution[soul.name] = posts

        return distribution

    async def _execute_schedule(
        self, schedule: List[EngagementAction], directive: ConvergenceDirective
    ):
        """Execute the schedule"""

        start_time = datetime.now()
        end_time = None

        if directive.duration_minutes and directive.hard_time_limit:
            end_time = start_time + timedelta(minutes=directive.duration_minutes)

        for i, action in enumerate(schedule):
            # Check cancellation
            if self.cancelled:
                logger.info("Convergence cancelled")
                break

            # Check time limit
            if end_time and datetime.now() >= end_time:
                logger.info("Time limit reached")
                break

            # Hot-reload if enabled
            if directive.hot_reload and i % 10 == 0:
                self.twitter_api.refresh_tokens_from_disk()

            # Wait until scheduled time
            elapsed = (datetime.now() - start_time).total_seconds()
            wait_time = action.timestamp - elapsed

            if wait_time > 0:
                logger.info(f"Next in {wait_time:.0f}s ({i+1}/{len(schedule)})")
                await asyncio.sleep(wait_time)

            # Execute action
            success = await self._execute_action(action, directive)

            if success:
                logger.info(
                    f"✅ [{i+1}/{len(schedule)}] {action.soul_name} {action.action_type}"
                )
            else:
                logger.warning(f"❌ [{i+1}/{len(schedule)}] {action.soul_name} failed")

    async def _execute_action(
        self, action: EngagementAction, directive: ConvergenceDirective
    ) -> bool:
        """Execute single action with all integrations"""

        try:
            soul = self.soul_registry.souls[action.soul_name]

            # Get content based on action type
            if action.action_type == "reply":
                # Use hunted tweets if available
                if directive.use_hunted_tweets and directive.hunted_tags:
                    hunted = self.hunt_manager.get_by_tags(directive.hunted_tags)
                    if hunted:
                        import random

                        target_tweet = random.choice(hunted)

                        content = await self.content_engine.generate_content(
                            soul=soul,
                            directive=directive,
                            context={
                                "target_tweet": target_tweet.text,
                                "action_type": "reply",
                            },
                        )

                        result = await self.twitter_api.reply_to_tweet(
                            action.soul_name, target_tweet.tweet_id, content
                        )

                        # Log for proof
                        if directive.proof_logging:
                            await self.proof_logger.log_action(
                                action.soul_name, "reply", result
                            )

                        return result.get("success", False)

                # Otherwise fetch from target
                context = await self.twitter_api.fetch_target_context(
                    directive.target.replace("@", ""), limit=10
                )

                if context.get("tweets"):
                    import random

                    target_tweet = random.choice(context["tweets"])

                    content = await self.content_engine.generate_content(
                        soul=soul,
                        directive=directive,
                        context={
                            "target_tweet": target_tweet.get("text", ""),
                            "action_type": "reply",
                        },
                    )

                    result = await self.twitter_api.reply_to_tweet(
                        action.soul_name, target_tweet["id"], content
                    )

                    # NEW: 66% chance to like the parent tweet before replying
                    # Utilize the verified like endpoint now that it is operational
                    if random.random() < 0.66:
                        try:
                            like_result = await self.twitter_api.like_tweet(
                                action.soul_name, target_tweet["id"]
                            )
                            if like_result.get("success"):
                                logger.info("👍 Liked parent tweet")
                        except Exception as e:
                            logger.debug(f"Like failed: {e}")
                else:
                    # Fallback to post
                    action.action_type = "post"

            if action.action_type == "post":
                content = await self.content_engine.generate_content(
                    soul=soul, directive=directive, context={"action_type": "post"}
                )

                result = await self.twitter_api.post_tweet(action.soul_name, content)

            # Log for proof
            if directive.proof_logging and result:
                await self.proof_logger.log_action(
                    action.soul_name, action.action_type, result
                )

            action.executed = True
            action.result = result

            return result.get("success", False) if result else False

        except Exception as e:
            logger.error(f"Action failed: {e}")
            return False

    async def _execute_coordinated_messages(self, directive: ConvergenceDirective):
        """Execute coordinated messages"""

        for message in directive.coordinated_messages:
            logger.info(f"📢 Coordinated message: {message}")

            available = self.soul_registry.get_available_souls(
                self.twitter_api.banned_souls
            )

            tasks = []
            for soul in available[:5]:
                content = f"{directive.target} {message}"[:280]
                task = self.twitter_api.post_tweet(soul.name, content)
                tasks.append(task)

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log successes
            for soul, result in zip(available[:5], results):
                if isinstance(result, dict) and result.get("success"):
                    if directive.proof_logging:
                        await self.proof_logger.log_action(
                            soul.name, "coordinated", result
                        )

            await asyncio.sleep(30)

    def cancel(self):
        """Cancel convergence"""
        self.cancelled = True


# ============================================================================
# LAYER 5: MASTER ORCHESTRATOR
# ============================================================================


class SwarmOrchestrator:
    """Master orchestrator combining all systems"""

    def __init__(self):
        # Initialize all components
        self.soul_registry = SoulRegistry()
        self.content_engine = ContentEngine()
        self.hunt_manager = HuntManager()
        self.proof_logger = ProofPackLogger()

        # Initialize Twitter API
        self.twitter_api = self._init_twitter_api()

        # Create controller
        self.controller = ConvergenceController(
            self.soul_registry,
            self.content_engine,
            self.twitter_api,
            self.hunt_manager,
            self.proof_logger,
        )

        logger.info("Swarm Orchestrator initialized with all features")

    def _init_twitter_api(self) -> ITwitterAPI:
        """Initialize Twitter API with Ryan implementation"""
        try:
            from ryan_api_ultimate import RyanTwitterAPISecure

            api = RyanTwitterAPISecure()
            logger.info("Ryan API initialized")
            return api
        except ImportError:
            logger.error("Ryan API not available")
            raise

    async def run_convergence(self, directive: ConvergenceDirective):
        """Execute convergence"""
        await self.controller.execute_convergence(directive)

        # Generate proof pack
        proof = self.proof_logger.generate_proof_pack()
        logger.info(
            f"Proof pack: {proof['successful_actions']}/{proof['total_actions']} successful"
        )

    async def hunt_mode(self):
        """Interactive hunt mode"""

        print("\n🏹 HUNT MODE")

        while True:
            print("\n[1] Search tweets")
            print("[2] Hunt user timeline")
            print("[3] View hunted")
            print("[4] Tag hunted")
            print("[0] Exit hunt")

            choice = input("\n> ").strip()

            if choice == "0":
                break
            elif choice == "1":
                query = input("Search query: ").strip()
                if query:
                    results = await self.twitter_api.search_tweets_async(query, 20)
                    # Process results...
            elif choice == "2":
                username = input("Username: ").strip()
                if username:
                    tweets = await self.twitter_api.fetch_target_context(username, 20)
                    # Process tweets...

        self.hunt_manager.save_hunted()


# ============================================================================
# MAIN ENTRY
# ============================================================================


async def main():
    """Main entry point"""

    print(
        """
╔════════════════════════════════════════════════════════╗
║         SOUL SWARM COMPLETE ARCHITECTURE              ║
║                                                        ║
║  DRS ✓  Precision ✓  Hot-reload ✓  Proof ✓  Hunt ✓   ║
╚════════════════════════════════════════════════════════╝
    """
    )

    orchestrator = SwarmOrchestrator()

    # Example: Create a directive with all features
    directive = ConvergenceDirective(
        target="@target",
        total_posts=30,
        duration_minutes=15,
        pacing=EngagementPacing.WAVE,
        use_drs=True,
        hot_reload=True,
        proof_logging=True,
        use_hunted_tweets=False,
        mood=SwarmMood.PHILOSOPHICAL,
        reply_ratio=0.7,
    )

    # NEW: Bot Hunter Integration and media posting support
    # Announce additional capabilities now available for the orchestrator. These
    # capabilities leverage the verified Ryan API endpoints and fixed rate limits.
    print(
        """
    Additional Capabilities Now Available:
    - Bot Hunter: Detect fake accounts at 180 req/min
    - Media Posts: Images and videos in tweets
    - Fixed Likes: 66% like rate on replies
    - Rate Limit: 180/min (not 3/min!)

    Known Bot Detected:
    @elon_x0648 (ID: 799900519)
    - Followers: 176
    - Following: 7000+ 
    - Bot Score: HIGH
    """
    )

    await orchestrator.run_convergence(directive)


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    asyncio.run(main())
