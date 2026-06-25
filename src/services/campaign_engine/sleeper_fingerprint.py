"""
GOTCHA Campaign Sleeper Behavioral Fingerprint
Generates per-account behavioral profiles that pass bot detection.

Each account gets a deterministic fingerprint from its seed.
Same seed = same behavioral profile. Different seed = different behavior.

Design principle: invert every signal the BotRGCN flags as bot-like.
"""

from __future__ import annotations

import hashlib
import json
import random
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple
from datetime import datetime, timedelta
import logging

logger = logging.getLogger("campaign.fingerprint")

# ---------------------------------------------------------------------------
# Redis keys for spec-driven fingerprint constraints
# ---------------------------------------------------------------------------
_SPEC_LATEST_KEY = "botrgcn:sleeper_spec:latest"
_FINGERPRINT_OVERRIDES_KEY = "botrgcn:fingerprint_overrides:latest"

# Single source of truth for soul names
from .campaign_config import SOUL_NAMES

# Timezone offsets (North American range — where accounts "live")
TIMEZONE_OFFSETS = list(range(-8, 4))  # PST to AST/EDT+ range

# Topic pools for organic posting (non-Shield content)
# DIVERSE — real humans aren't all tech workers. Mix of interests prevents
# the swarm from looking like a coordinated tech-only bot network.
ORGANIC_TOPICS = [
    # Tech (keep some — these accounts DO eventually post about privacy)
    "AI capabilities and limitations",
    "open source software development",
    "tech industry trends",
    "cybersecurity fundamentals",
    "programming languages and tools",
    "startup ecosystem dynamics",
    # Sports & fitness
    "NBA basketball and game highlights",
    "NFL football and fantasy leagues",
    "UFC and combat sports",
    "running and marathon training",
    "gym workouts and fitness tips",
    # Entertainment
    "movies and film reviews",
    "TV shows and streaming recommendations",
    "video games and gaming culture",
    "music discovery and playlists",
    "anime and manga",
    # Lifestyle
    "cooking recipes and food culture",
    "travel destinations and tips",
    "personal finance and budgeting",
    "home improvement and DIY projects",
    "parenting and family life",
    # Current events & culture
    "science news and discoveries",
    "space exploration and astronomy",
    "climate and environmental news",
    "book recommendations and reading",
    "photography and visual art",
    # Misc human interests
    "pets and animal content",
    "cars and automotive culture",
    "fashion and style trends",
    "mental health and wellness",
    "local community events and news",
]


@dataclass
class SleeperFingerprint:
    """Behavioral profile for a sleeper account.

    Every field is derived from account_seed for deterministic replay.
    """
    account_seed: str
    soul_name: str

    # Circadian rhythm
    timezone_offset: int            # UTC offset (-8 to +3)
    sleep_start_hour: int           # Local hour when posting stops (22-2)
    wake_hour: int                  # Local hour when posting resumes (6-10)

    # Posting rhythm
    weekly_post_caps: List[int]     # 7 values, one per day of week (e.g., [2, 0, 1, 3, 0, 1, 2])
    posting_jitter_minutes: int     # Random offset range for post timing (15-120)
    min_gap_between_posts_hours: float  # Minimum hours between posts (2-8)

    # Engagement behavior
    daily_like_range: Tuple[int, int]    # (min, max) likes per active day
    retweet_probability: float           # 0.03 - 0.12
    reply_probability: float             # 0.02 - 0.08
    follow_rate_per_day: Tuple[int, int] # (min, max) new follows per day

    # Content preferences
    preferred_topics: List[str]     # 3-5 topics from ORGANIC_TOPICS
    original_content_ratio: float   # 0.7 - 0.95 (bots are low, humans are high)

    # Anti-detection
    skip_day_probability: float     # 0.15 - 0.35 (some days, don't post at all)
    weekend_activity_modifier: float  # 0.3 - 0.8 (less active on weekends)
    burst_avoidance: bool           # Always True — never post multiple times in quick succession

    # Session behavior constraints (Scribe-aware -- from SleeperSpec overrides)
    min_session_action_diversity: float = 3.0       # Min distinct action types per session
    min_avg_dwell_time_ms: int = 2000               # Min avg dwell time per content (ms)
    min_session_duration_variance_pct: float = 30.0  # Sessions must vary by this % in duration
    min_scroll_impression_ratio: float = 0.7         # Fraction of impressions preceded by scroll
    min_impression_action_ratio: float = 3.0         # See N items before acting on one
    max_follow_velocity_per_day: float = 3.0         # Max new follows per day
    max_rate_limit_events_per_day: int = 0           # Never hit rate limits
    max_error_rate: float = 0.02                     # Max fraction of errored requests
    min_ad_impression_ratio: float = 0.01            # Must see some promoted content

    def is_awake(self, utc_hour: int) -> bool:
        """Check if the account would be 'awake' at this UTC hour."""
        local_hour = (utc_hour + self.timezone_offset) % 24

        if self.sleep_start_hour > self.wake_hour:
            # Normal case: sleep 23 -> wake 7
            return not (self.sleep_start_hour <= local_hour or local_hour < self.wake_hour)
        else:
            # Edge case: sleep 1 -> wake 8
            return not (self.sleep_start_hour <= local_hour < self.wake_hour)

    def should_post_today(self, date: datetime) -> Tuple[bool, int]:
        """Determine if account should post today and how many posts.

        Returns: (should_post, max_posts_today)
        """
        rng = random.Random(f"{self.account_seed}:{date.strftime('%Y-%m-%d')}")

        # Check skip day
        if rng.random() < self.skip_day_probability:
            return False, 0

        # Get base cap for this day of week
        day_idx = date.weekday()  # 0=Monday
        base_cap = self.weekly_post_caps[day_idx]

        # Weekend modifier
        if day_idx >= 5:  # Saturday/Sunday
            if rng.random() > self.weekend_activity_modifier:
                return False, 0
            base_cap = max(0, int(base_cap * self.weekend_activity_modifier))

        if base_cap == 0:
            return False, 0

        return True, base_cap

    def get_post_times(self, date: datetime, count: int) -> List[datetime]:
        """Generate human-like post times for a given day.

        Posts are spaced with minimum gaps and jitter, within awake hours.
        """
        rng = random.Random(f"{self.account_seed}:times:{date.strftime('%Y-%m-%d')}")

        # Determine awake window in UTC
        wake_utc = (self.wake_hour - self.timezone_offset) % 24
        sleep_utc = (self.sleep_start_hour - self.timezone_offset) % 24

        times = []
        for i in range(count):
            # Pick a random hour within awake window
            if wake_utc < sleep_utc:
                hour = rng.randint(wake_utc, sleep_utc - 1)
            else:
                # Wraps midnight
                hours = list(range(wake_utc, 24)) + list(range(0, sleep_utc))
                hour = rng.choice(hours) if hours else 12

            minute = rng.randint(0, 59)
            jitter = rng.randint(-self.posting_jitter_minutes, self.posting_jitter_minutes)

            post_time = date.replace(hour=hour, minute=minute, second=rng.randint(0, 59))
            post_time += timedelta(minutes=jitter)

            # Clamp to same day
            post_time = post_time.replace(
                year=date.year, month=date.month, day=date.day
            )

            times.append(post_time)

        # Sort and enforce minimum gap
        times.sort()
        min_gap = timedelta(hours=self.min_gap_between_posts_hours)
        filtered = []
        for t in times:
            if not filtered or (t - filtered[-1]) >= min_gap:
                filtered.append(t)

        return filtered

    def get_daily_likes(self, date: datetime) -> int:
        """How many likes this account should do today."""
        rng = random.Random(f"{self.account_seed}:likes:{date.strftime('%Y-%m-%d')}")

        if date.weekday() >= 5:  # Weekend
            modifier = self.weekend_activity_modifier
        else:
            modifier = 1.0

        base = rng.randint(self.daily_like_range[0], self.daily_like_range[1])
        return max(0, int(base * modifier))

    def should_retweet(self, date: datetime, tweet_index: int) -> bool:
        """Decide whether to retweet a specific tweet."""
        rng = random.Random(f"{self.account_seed}:rt:{date.strftime('%Y-%m-%d')}:{tweet_index}")
        return rng.random() < self.retweet_probability

    def to_dict(self) -> Dict:
        """Serialize fingerprint for storage."""
        return {
            "account_seed": self.account_seed,
            "soul_name": self.soul_name,
            "timezone_offset": self.timezone_offset,
            "sleep_start_hour": self.sleep_start_hour,
            "wake_hour": self.wake_hour,
            "weekly_post_caps": self.weekly_post_caps,
            "posting_jitter_minutes": self.posting_jitter_minutes,
            "min_gap_between_posts_hours": self.min_gap_between_posts_hours,
            "daily_like_range": list(self.daily_like_range),
            "retweet_probability": self.retweet_probability,
            "reply_probability": self.reply_probability,
            "follow_rate_per_day": list(self.follow_rate_per_day),
            "preferred_topics": self.preferred_topics,
            "original_content_ratio": self.original_content_ratio,
            "skip_day_probability": self.skip_day_probability,
            "weekend_activity_modifier": self.weekend_activity_modifier,
            "burst_avoidance": self.burst_avoidance,
            # Session behavior constraints (Scribe-aware)
            "min_session_action_diversity": self.min_session_action_diversity,
            "min_avg_dwell_time_ms": self.min_avg_dwell_time_ms,
            "min_session_duration_variance_pct": self.min_session_duration_variance_pct,
            "min_scroll_impression_ratio": self.min_scroll_impression_ratio,
            "min_impression_action_ratio": self.min_impression_action_ratio,
            "max_follow_velocity_per_day": self.max_follow_velocity_per_day,
            "max_rate_limit_events_per_day": self.max_rate_limit_events_per_day,
            "max_error_rate": self.max_error_rate,
            "min_ad_impression_ratio": self.min_ad_impression_ratio,
        }


class FingerprintGenerator:
    """Generates deterministic behavioral fingerprints from account seeds.

    Supports two modes:
    1. Standalone (original): generate() uses hardcoded ranges
    2. Spec-driven (closed loop): generate() accepts spec_overrides from
       Redis that clamp all generated values to model-derived constraints.

    The closed-loop flow:
        Training -> feature_importances -> SleeperSpecGenerator -> Redis
        -> FingerprintGenerator reads overrides -> clamped fingerprints
    """

    @staticmethod
    async def load_spec_overrides(redis_client: Any) -> Optional[Dict[str, Any]]:
        """Load fingerprint constraint overrides from Redis.

        Reads the latest spec-derived overrides written by
        AdversarialTrainer.generate_and_store_spec().

        Returns None if no overrides exist (first run, or spec not yet generated).
        """
        try:
            raw = await redis_client.get(_FINGERPRINT_OVERRIDES_KEY)
            if raw:
                overrides = json.loads(raw)
                logger.info(
                    "Loaded spec overrides from Redis (version=%s, generated_at=%s)",
                    overrides.get("_spec_version", "unknown"),
                    overrides.get("_generated_at", "unknown"),
                )
                return overrides
        except Exception as exc:
            logger.warning("Could not load spec overrides from Redis: %s", exc)

        return None

    @staticmethod
    def generate(
        account_seed: str,
        spec_overrides: Optional[Dict[str, Any]] = None,
    ) -> SleeperFingerprint:
        """Generate a complete behavioral fingerprint from a seed.

        Every parameter is derived deterministically -- same seed always
        produces the same fingerprint. If spec_overrides are provided
        (from SleeperSpecGenerator via Redis), generated values are
        clamped to the spec limits.

        Parameters
        ----------
        account_seed : str
            Deterministic seed for this account.
        spec_overrides : dict, optional
            Constraint overrides from SleeperSpecGenerator.generate_fingerprint_params().
            Read from Redis key ``botrgcn:fingerprint_overrides:latest``.
            When provided, all generated values are clamped to spec limits.
        """
        rng = random.Random(hashlib.sha256(account_seed.encode()).hexdigest())
        ov = spec_overrides or {}

        # Soul assignment
        soul_name = rng.choice(SOUL_NAMES)

        # Circadian rhythm
        timezone_offset = rng.choice(TIMEZONE_OFFSETS)
        sleep_start_hour = ov.get("sleep_start_hour", rng.randint(22, 26) % 24)
        wake_hour = ov.get("wake_hour", rng.randint(6, 10))

        # Posting rhythm -- varied daily caps
        # Key insight: real humans have VERY irregular posting
        if "weekly_post_caps" in ov:
            weekly_caps = ov["weekly_post_caps"]
        else:
            weekly_caps = []
            for _ in range(7):
                r = rng.random()
                if r < 0.25:
                    weekly_caps.append(0)   # No posts this day
                elif r < 0.55:
                    weekly_caps.append(1)   # One post
                elif r < 0.80:
                    weekly_caps.append(2)   # Two posts
                else:
                    weekly_caps.append(3)   # Three posts (rare)

        posting_jitter = ov.get("posting_jitter_minutes", rng.randint(15, 120))
        min_gap = rng.uniform(2.0, 8.0)
        if "min_gap_between_posts_hours" in ov:
            # Spec says minimum gap; enforce it as a floor
            min_gap = max(min_gap, ov["min_gap_between_posts_hours"])

        # Engagement -- inverted from BotRGCN bot signals
        daily_like_min = rng.randint(0, 3)
        daily_like_max = daily_like_min + rng.randint(2, 6)
        if "daily_like_range" in ov:
            ov_range = ov["daily_like_range"]
            daily_like_min = max(daily_like_min, ov_range[0])
            daily_like_max = min(daily_like_max, ov_range[1])

        retweet_prob = rng.uniform(0.03, 0.12)
        if "retweet_probability" in ov:
            # Clamp to spec maximum
            retweet_prob = min(retweet_prob, ov["retweet_probability"])

        reply_prob = rng.uniform(0.02, 0.08)
        if "reply_probability" in ov:
            reply_prob = min(reply_prob, ov["reply_probability"])

        follow_min = rng.randint(0, 2)
        follow_max = follow_min + rng.randint(1, 3)
        if "follow_rate_per_day" in ov:
            ov_fr = ov["follow_rate_per_day"]
            follow_min = max(follow_min, ov_fr[0])
            follow_max = min(follow_max, ov_fr[1])

        # Content preferences -- 3-5 random topics
        topic_count = rng.randint(3, 5)
        preferred_topics = rng.sample(ORGANIC_TOPICS, topic_count)

        # Human-like ratios
        original_ratio = rng.uniform(0.70, 0.95)
        if "original_content_ratio" in ov:
            # Spec says minimum original content; enforce as floor
            original_ratio = max(original_ratio, ov["original_content_ratio"])

        skip_day_prob = rng.uniform(0.15, 0.35)
        if "skip_day_probability" in ov:
            skip_day_prob = min(max(skip_day_prob, ov["skip_day_probability"]), 0.40)

        weekend_mod = rng.uniform(0.30, 0.80)
        if "weekend_activity_modifier" in ov:
            weekend_mod = min(weekend_mod, ov["weekend_activity_modifier"])

        burst_avoidance = ov.get("burst_avoidance", True)

        # Session behavior constraints -- use spec overrides or defaults
        min_session_div = ov.get("min_session_action_diversity", 3.0)
        min_dwell = ov.get("min_avg_dwell_time_ms", 2000)
        min_sess_var = ov.get("min_session_duration_variance_pct", 30.0)
        min_scroll = ov.get("min_scroll_impression_ratio", 0.7)
        min_imp_ratio = ov.get("min_impression_action_ratio", 3.0)
        max_follow_vel = ov.get("max_follow_velocity_per_day", 3.0)
        max_rl = ov.get("max_rate_limit_events_per_day", 0)
        max_err = ov.get("max_error_rate", 0.02)
        min_ad = ov.get("min_ad_impression_ratio", 0.01)

        fingerprint = SleeperFingerprint(
            account_seed=account_seed,
            soul_name=soul_name,
            timezone_offset=timezone_offset,
            sleep_start_hour=sleep_start_hour,
            wake_hour=wake_hour,
            weekly_post_caps=weekly_caps,
            posting_jitter_minutes=posting_jitter,
            min_gap_between_posts_hours=round(min_gap, 1),
            daily_like_range=(daily_like_min, daily_like_max),
            retweet_probability=round(retweet_prob, 3),
            reply_probability=round(reply_prob, 3),
            follow_rate_per_day=(follow_min, follow_max),
            preferred_topics=preferred_topics,
            original_content_ratio=round(original_ratio, 2),
            skip_day_probability=round(skip_day_prob, 2),
            weekend_activity_modifier=round(weekend_mod, 2),
            burst_avoidance=burst_avoidance,
            # Session behavior constraints (from spec or defaults)
            min_session_action_diversity=min_session_div,
            min_avg_dwell_time_ms=min_dwell,
            min_session_duration_variance_pct=min_sess_var,
            min_scroll_impression_ratio=min_scroll,
            min_impression_action_ratio=min_imp_ratio,
            max_follow_velocity_per_day=max_follow_vel,
            max_rate_limit_events_per_day=max_rl,
            max_error_rate=max_err,
            min_ad_impression_ratio=min_ad,
        )

        spec_note = " (spec-constrained)" if ov else ""
        logger.info(
            "Generated fingerprint%s for %s: soul=%s, "
            "tz=%d, weekly_caps=%s, topics=%d",
            spec_note, account_seed, soul_name,
            timezone_offset, weekly_caps, len(preferred_topics),
        )

        return fingerprint

    @staticmethod
    def generate_batch(
        seeds: List[str],
        spec_overrides: Optional[Dict[str, Any]] = None,
    ) -> List[SleeperFingerprint]:
        """Generate fingerprints for multiple accounts.

        If spec_overrides is provided, all fingerprints are clamped to
        the same spec constraints (from SleeperSpecGenerator via Redis).
        """
        return [
            FingerprintGenerator.generate(seed, spec_overrides=spec_overrides)
            for seed in seeds
        ]

    @staticmethod
    async def generate_with_redis(
        account_seed: str,
        redis_client: Any,
    ) -> SleeperFingerprint:
        """Generate a fingerprint, automatically loading spec overrides from Redis.

        This is the primary entry point for the closed-loop pipeline:
          1. Reads botrgcn:fingerprint_overrides:latest from Redis
          2. Generates fingerprint with spec constraints applied
          3. Falls back to hardcoded ranges if no spec exists

        Usage::

            import redis.asyncio as aioredis
            redis = aioredis.Redis(host="localhost", port=6379, password="...")
            fp = await FingerprintGenerator.generate_with_redis("seed_123", redis)
        """
        overrides = await FingerprintGenerator.load_spec_overrides(redis_client)
        return FingerprintGenerator.generate(account_seed, spec_overrides=overrides)

    @staticmethod
    async def generate_batch_with_redis(
        seeds: List[str],
        redis_client: Any,
    ) -> List[SleeperFingerprint]:
        """Generate fingerprints for multiple accounts, loading spec from Redis once.

        Reads the spec overrides once and applies to all fingerprints in the batch.
        """
        overrides = await FingerprintGenerator.load_spec_overrides(redis_client)
        return [
            FingerprintGenerator.generate(seed, spec_overrides=overrides)
            for seed in seeds
        ]

    @staticmethod
    def preview(seed: str, spec_overrides: Optional[Dict[str, Any]] = None) -> str:
        """Generate a human-readable preview of a fingerprint."""
        fp = FingerprintGenerator.generate(seed, spec_overrides=spec_overrides)
        avg_daily = sum(fp.weekly_post_caps) / 7
        lines = [
            f"=== Fingerprint: {seed[:16]}... ===",
            f"Soul: {fp.soul_name}",
            f"Timezone: UTC{fp.timezone_offset:+d}",
            f"Awake: {fp.wake_hour:02d}:00 - {fp.sleep_start_hour:02d}:00 local",
            f"Weekly caps: {fp.weekly_post_caps} (avg {avg_daily:.1f}/day)",
            f"Post jitter: ±{fp.posting_jitter_minutes} min",
            f"Min gap: {fp.min_gap_between_posts_hours}h",
            f"Likes/day: {fp.daily_like_range[0]}-{fp.daily_like_range[1]}",
            f"RT prob: {fp.retweet_probability:.1%}",
            f"Skip day prob: {fp.skip_day_probability:.0%}",
            f"Weekend activity: {fp.weekend_activity_modifier:.0%}",
            f"Original content: {fp.original_content_ratio:.0%}",
            f"Topics: {', '.join(fp.preferred_topics[:3])}...",
            f"--- Session constraints ---",
            f"Min session diversity: {fp.min_session_action_diversity}",
            f"Min dwell time: {fp.min_avg_dwell_time_ms}ms",
            f"Min session variance: {fp.min_session_duration_variance_pct}%",
            f"Min scroll ratio: {fp.min_scroll_impression_ratio}",
            f"Min impression ratio: {fp.min_impression_action_ratio}",
            f"Max follow velocity: {fp.max_follow_velocity_per_day}/day",
            f"Max rate limits: {fp.max_rate_limit_events_per_day}/day",
            f"Max error rate: {fp.max_error_rate}",
            f"Min ad ratio: {fp.min_ad_impression_ratio}",
        ]
        return "\n".join(lines)
