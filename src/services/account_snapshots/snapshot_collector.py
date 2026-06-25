"""
Snapshot Collector

Collects identity, behavioral, and ban telemetry for swarm accounts.
Writes to Redis time-series for consumption by the GNN training pipeline.
"""

from __future__ import annotations

import json
import logging
import math
import time
from collections import Counter
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set

import redis.asyncio as aioredis

from src.services.health_monitor.health_monitor import (
    AccountHealthMonitor,
    AccountStatus,
)
from src.services.onboarding.onboarding_scheduler import OnboardingScheduler
from src.ryan_api_ultimate import RyanTwitterAPISecure as RyanTwitterAPI

from .snapshot_models import (
    AccountIdentitySnapshot,
    BanEvent,
    BehavioralSnapshot,
)

logger = logging.getLogger("account_snapshots.collector")

# Redis key helpers
_PREFIX = "snapshot"

# Ban-triggering statuses
_BAN_STATUSES = {
    AccountStatus.SUSPENDED,
    AccountStatus.LOCKED,
    AccountStatus.SHADOWBANNED,
    AccountStatus.RATE_LIMITED,
}

# Burst window: two tweets within 5 minutes = a burst
_BURST_WINDOW_SECONDS = 300

# Behaviour history retention: 30 days
_HISTORY_TTL_SECONDS = 30 * 24 * 3600

# Shield/CTA keywords that identify campaign content
_SHIELD_KEYWORDS = [
    "privacy", "tracking", "shield", "protect", "browser", "extension",
    "ai privacy", "block ai", "stop tracking",
]


def _identity_key(account_id: str) -> str:
    return f"{_PREFIX}:identity:{account_id}"


def _behavior_key(account_id: str) -> str:
    return f"{_PREFIX}:behavior:{account_id}"


def _behavior_history_key(account_id: str) -> str:
    return f"{_PREFIX}:behavior_history:{account_id}"


def _ban_key(account_id: str) -> str:
    return f"{_PREFIX}:ban:{account_id}"


def _bans_all_key() -> str:
    return f"{_PREFIX}:bans:all"


def _survivors_key() -> str:
    return f"{_PREFIX}:survivors"


def _prev_status_key(account_id: str) -> str:
    return f"{_PREFIX}:previous_status:{account_id}"


class SnapshotCollector:
    """
    Collects and stores rich behavioral telemetry for swarm accounts.

    Dependencies are injected; the collector never opens its own Redis
    connection — the caller supplies one.
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        ryan_api: RyanTwitterAPI,
        health_monitor: AccountHealthMonitor,
        onboarding_scheduler: OnboardingScheduler,
        swarm_account_ids: Set[str],
        username_map: Optional[Dict[str, str]] = None,
    ) -> None:
        self.redis = redis_client
        self.ryan = ryan_api
        self.health = health_monitor
        self.onboarding = onboarding_scheduler
        self.swarm_ids = swarm_account_ids
        # Mapping of Twitter usernames -> soul IDs for network classification
        self._username_to_soul: Dict[str, str] = username_map or {}

    # ------------------------------------------------------------------
    # Identity snapshot (called once at creation)
    # ------------------------------------------------------------------

    async def collect_identity_snapshot(
        self,
        account_id: str,
        creation_metadata: Dict[str, Any],
    ) -> AccountIdentitySnapshot:
        """
        Build and persist an identity snapshot from creation metadata.

        creation_metadata is expected to contain any subset of the
        AccountIdentitySnapshot fields; missing fields fall back to
        safe defaults so the caller never has to populate everything.
        """
        cm = creation_metadata

        snapshot = AccountIdentitySnapshot(
            account_id=account_id,
            twitter_username=cm.get("twitter_username", account_id),
            email_domain=cm.get("email_domain", "unknown"),
            creation_timestamp=cm.get("creation_timestamp", time.time()),
            creation_ip=cm.get("creation_ip", "0.0.0.0"),
            creation_proxy_type=cm.get("creation_proxy_type", "unknown"),
            browser_profile_id=cm.get("browser_profile_id", "default"),
            user_agent=cm.get("user_agent", ""),
            webgl_renderer=cm.get("webgl_renderer", ""),
            timezone=cm.get("timezone", "UTC"),
            locale=cm.get("locale", "en-US"),
            screen_resolution=cm.get("screen_resolution", "1920x1080"),
            has_bio=bool(cm.get("has_bio", False)),
            has_avatar=bool(cm.get("has_avatar", False)),
            username_pattern=cm.get("username_pattern", "unknown"),
            password_entropy=float(cm.get("password_entropy", 0.0)),
            birth_date_age=int(cm.get("birth_date_age", 25)),
        )

        await self.redis.set(
            _identity_key(account_id),
            json.dumps(snapshot.to_dict()),
        )
        logger.info("Stored identity snapshot for %s", account_id)
        return snapshot

    # ------------------------------------------------------------------
    # Behavioral snapshot (called periodically)
    # ------------------------------------------------------------------

    async def collect_behavioral_snapshot(
        self, account_id: str
    ) -> BehavioralSnapshot:
        """
        Pull live data from RyanAPI + health monitor + onboarding scheduler,
        compute all features, and persist the snapshot to Redis.
        """
        now = time.time()

        # Resolve twitter username from identity snapshot (if available)
        username = await self._get_username(account_id)

        # ---- RyanAPI calls -------------------------------------------
        profile: Dict[str, Any] = {}
        tweets: List[Dict[str, Any]] = []
        followers: List[str] = []
        following: List[str] = []

        if username:
            try:
                profile = await self.ryan.get_user_profile(username) or {}
            except Exception as exc:
                logger.warning("get_user_profile failed for %s: %s", account_id, exc)

            try:
                ctx = await self.ryan.fetch_target_context(username, limit=50)
                tweets = ctx.get("tweets", []) if isinstance(ctx, dict) else []
            except Exception as exc:
                logger.warning("fetch_target_context failed for %s: %s", account_id, exc)

            user_id = profile.get("user_id", "")
            if user_id:
                try:
                    followers = await self.ryan.get_followers(user_id, limit=100)
                except Exception as exc:
                    logger.warning("get_followers failed for %s: %s", account_id, exc)

                try:
                    following = await self.ryan.get_following(user_id, limit=50)
                except Exception as exc:
                    logger.warning("get_following failed for %s: %s", account_id, exc)

        # ---- Onboarding phase ----------------------------------------
        onboarding_phase = "unknown"
        total_actions = 0

        schedule = await self.onboarding.get_schedule(account_id)
        if schedule is not None:
            onboarding_phase = schedule.current_phase.value
            total_actions = schedule.metadata.get("total_actions_lifetime", 0)

        # ---- Feature computation -------------------------------------
        temporal = self._compute_temporal_features(tweets)
        content = self._compute_content_features(tweets)
        engagement = self._compute_engagement_features(tweets)
        network = self._classify_network(account_id, followers, following)

        follower_count = int(profile.get("followers_count", 0))
        following_count = int(profile.get("following_count", 0))
        tweet_count = int(profile.get("tweet_count", 0))

        # Account age from identity snapshot
        account_age_hours = 0.0
        identity_raw = await self.redis.get(_identity_key(account_id))
        if identity_raw:
            try:
                identity_data = json.loads(identity_raw)
                creation_ts = float(identity_data.get("creation_timestamp", now))
                account_age_hours = (now - creation_ts) / 3600.0
            except (json.JSONDecodeError, ValueError):
                pass

        follow_ratio = (
            follower_count / max(following_count, 1)
        )

        # ---- Scribe-aware session / social graph / red flag features ----
        # Baselines derived from Twitter Scribe forensic analysis:
        #   - min_action_types_per_session: 3 (red flag below this)
        #   - min_dwell_events_per_session: 2
        #   - min_action_interval_ms: 300 (100ms is their threshold)
        #   - min_session_duration_variance_pct: 30
        #   - min_ad_impression_ratio: 0.01
        #   - max_rate_limit_events_per_day: 0
        # Real values from runtime session logs override these when available.

        # Try loading runtime session data from Redis first
        session_key = f"session:behavior:{account_id}"
        try:
            session_data = await self.redis.hgetall(session_key)
        except Exception:
            session_data = {}

        if session_data:
            session_action_diversity = float(session_data.get("action_diversity", 0.0))
            avg_dwell_time_ms = float(session_data.get("avg_dwell_time_ms", 0.0))
            session_duration_cv = float(session_data.get("session_duration_cv", 0.0))
            impression_action_ratio = float(session_data.get("impression_action_ratio", 0.0))
            avg_actions_per_session = float(session_data.get("avg_actions_per_session", 0.0))
            scroll_impression_ratio = float(session_data.get("scroll_impression_ratio", 0.0))
        else:
            # Human-baseline defaults from Scribe forensic analysis
            # These represent minimum safe behavior for a real human account
            session_action_diversity = 4.2    # real humans use 4-6 action types per session
            avg_dwell_time_ms = 3200.0        # ~3.2s avg content dwell (300ms is bot floor)
            session_duration_cv = 0.45        # 45% variance between sessions (30% min rule)
            impression_action_ratio = 0.35    # ~35% of impressions get an action
            avg_actions_per_session = 12.0    # ~12 actions per session (3 is red flag min)
            scroll_impression_ratio = 0.85    # scroll between 85% of impressions (required)

        # Social graph dynamics
        follow_velocity_per_day = (
            following_count / max(account_age_hours / 24.0, 1.0)
        )

        # Load social graph tracking from Redis if available
        social_key = f"social:dynamics:{account_id}"
        try:
            social_data = await self.redis.hgetall(social_key)
        except Exception:
            social_data = {}

        if social_data:
            unfollow_ratio = float(social_data.get("unfollow_ratio", 0.0))
            reply_thread_depth_avg = float(social_data.get("reply_thread_depth_avg", 0.0))
            follow_back_ratio = float(social_data.get("follow_back_ratio", 0.0))
        else:
            # Human-baseline defaults from forensic analysis
            unfollow_ratio = 0.05             # real humans unfollow ~5% of follows
            reply_thread_depth_avg = 1.8      # avg reply depth ~1.8 (some threads, mostly top-level)
            follow_back_ratio = 0.25          # ~25% reciprocation is normal

        # Red flag indicators
        rate_limit_events_per_day = 0.0       # target: 0 (any hit is a red flag per Scribe rules)
        # Check health monitor history for RATE_LIMITED status events
        try:
            rl_history_key = f"health:history:{account_id}"
            rl_entries = await self.redis.lrange(rl_history_key, 0, -1)
            if rl_entries:
                rl_count = sum(
                    1 for entry in rl_entries
                    if AccountStatus.RATE_LIMITED.value in str(entry)
                )
                age_days = max(account_age_hours / 24.0, 1.0)
                rate_limit_events_per_day = rl_count / age_days
        except Exception as exc:
            logger.debug("Could not read rate limit history for %s: %s", account_id, exc)

        error_rate = 0.0                      # target: 0 (high error rate = red flag)
        # Load error tracking from Redis if available
        try:
            error_data = await self.redis.get(f"health:error_rate:{account_id}")
            if error_data:
                error_rate = float(error_data)
        except Exception:
            pass

        ad_impression_ratio = 0.015           # baseline: 1.5% (1% min per Scribe rules)

        snapshot = BehavioralSnapshot(
            account_id=account_id,
            snapshot_timestamp=now,
            # Temporal
            total_tweets=tweet_count,
            tweets_last_hour=temporal["tweets_last_hour"],
            tweets_last_24h=temporal["tweets_last_24h"],
            avg_gap_between_tweets_seconds=temporal["avg_gap_seconds"],
            gap_variance=temporal["gap_variance"],
            burst_count=temporal["burst_count"],
            hour_entropy=temporal["hour_entropy"],
            weekend_ratio=temporal["weekend_ratio"],
            # Content
            original_tweet_count=content["original_count"],
            retweet_count=content["retweet_count"],
            reply_count=content["reply_count"],
            quote_count=content["quote_count"],
            url_ratio=content["url_ratio"],
            hashtag_density=content["hashtag_density"],
            mention_density=content["mention_density"],
            avg_tweet_length=content["avg_length"],
            shield_cta_ratio=content["shield_cta_ratio"],
            # Engagement
            total_likes_received=engagement["total_likes"],
            total_replies_received=engagement["total_replies"],
            total_retweets_received=engagement["total_retweets"],
            engagement_variance=engagement["variance"],
            # Profile
            follower_count=follower_count,
            following_count=following_count,
            follow_ratio=follow_ratio,
            account_age_hours=account_age_hours,
            onboarding_phase=onboarding_phase,
            # Network
            follows_real_humans=network["follows_real"],
            follows_swarm_accounts=network["follows_swarm"],
            followed_by_real=network["followed_by_real"],
            followed_by_swarm=network["followed_by_swarm"],
            # Session behavior (Scribe-aware)
            session_action_diversity=session_action_diversity,
            avg_dwell_time_ms=avg_dwell_time_ms,
            session_duration_cv=session_duration_cv,
            impression_action_ratio=impression_action_ratio,
            avg_actions_per_session=avg_actions_per_session,
            scroll_impression_ratio=scroll_impression_ratio,
            # Social graph dynamics
            follow_velocity_per_day=follow_velocity_per_day,
            unfollow_ratio=unfollow_ratio,
            reply_thread_depth_avg=reply_thread_depth_avg,
            follow_back_ratio=follow_back_ratio,
            # Red flag indicators
            rate_limit_events_per_day=rate_limit_events_per_day,
            error_rate=error_rate,
            ad_impression_ratio=ad_impression_ratio,
        )

        # Persist latest snapshot
        pipe = self.redis.pipeline()
        pipe.set(_behavior_key(account_id), json.dumps(snapshot.to_dict()))

        # Append to time-series sorted set
        pipe.zadd(
            _behavior_history_key(account_id),
            {json.dumps(snapshot.to_dict()): now},
        )

        # Trim to 30-day retention window
        cutoff = now - _HISTORY_TTL_SECONDS
        pipe.zremrangebyscore(_behavior_history_key(account_id), "-inf", cutoff)

        await pipe.execute()

        logger.debug(
            "Collected behavioral snapshot for %s (phase=%s, tweets=%d)",
            account_id,
            onboarding_phase,
            tweet_count,
        )
        return snapshot

    # ------------------------------------------------------------------
    # Ban detection
    # ------------------------------------------------------------------

    async def detect_ban(self, account_id: str) -> Optional[BanEvent]:
        """
        Compare previous health status to current status.
        If a ban transition is detected, construct and store a BanEvent.
        Returns the BanEvent on a newly detected ban, None otherwise.
        """
        current_check = await self.health.get_current_status(account_id)
        if current_check is None:
            return None

        current_status = current_check.status
        prev_status_raw = await self.redis.get(_prev_status_key(account_id))
        prev_status_str = prev_status_raw if prev_status_raw else AccountStatus.HEALTHY.value

        # Record ban if:
        # 1. Previous was HEALTHY, current is banned (new ban)
        # 2. Previous was banned type X, current is DIFFERENT banned type Y (type change)
        if prev_status_str == AccountStatus.HEALTHY.value:
            if current_status not in _BAN_STATUSES:
                # Still healthy, no ban event
                await self.redis.set(_prev_status_key(account_id), current_status.value)
                return None
            # Fall through to record the ban
        elif prev_status_str in [s.value for s in _BAN_STATUSES]:
            if current_status.value == prev_status_str:
                # Same ban state, no new event
                return None
            if current_status not in _BAN_STATUSES:
                # Recovery: banned -> healthy. Not a new ban.
                await self.redis.set(_prev_status_key(account_id), current_status.value)
                return None
            # Different ban type: record the transition
        else:
            if current_status not in _BAN_STATUSES:
                await self.redis.set(_prev_status_key(account_id), current_status.value)
                return None

        # Update previous status
        await self.redis.set(_prev_status_key(account_id), current_status.value)

        # This is a fresh ban transition — build the event
        logger.warning(
            "Ban detected for %s: %s -> %s",
            account_id, prev_status_str, current_status.value,
        )

        # Load identity snapshot
        identity_raw = await self.redis.get(_identity_key(account_id))
        if identity_raw:
            identity = AccountIdentitySnapshot.from_dict(json.loads(identity_raw))
        else:
            # Construct a minimal identity if we have nothing
            identity = AccountIdentitySnapshot(
                account_id=account_id,
                twitter_username=account_id,
                email_domain="unknown",
                creation_timestamp=time.time(),
                creation_ip="0.0.0.0",
                creation_proxy_type="unknown",
                browser_profile_id="unknown",
                user_agent="",
                webgl_renderer="",
                timezone="UTC",
                locale="en-US",
                screen_resolution="1920x1080",
                has_bio=False,
                has_avatar=False,
                username_pattern="unknown",
                password_entropy=0.0,
                birth_date_age=25,
            )

        # Load or collect latest behavioral snapshot
        behavior_raw = await self.redis.get(_behavior_key(account_id))
        if behavior_raw:
            behavioral = BehavioralSnapshot.from_dict(json.loads(behavior_raw))
        else:
            behavioral = await self.collect_behavioral_snapshot(account_id)

        # Determine account age at ban
        account_age_hours = behavioral.account_age_hours

        # Pull schedule for total actions and last action
        schedule = await self.onboarding.get_schedule(account_id)
        total_actions = 0
        last_action = "unknown"
        last_action_ts = time.time()

        if schedule is not None:
            total_actions = schedule.metadata.get("total_actions_lifetime", 0)
            if schedule.last_action_at is not None:
                last_action_ts = schedule.last_action_at.timestamp()
                # Most recently recorded action type
                action_counts = schedule.action_counts_today
                if action_counts:
                    last_action = max(action_counts, key=action_counts.get)

        # Heuristic trigger classification
        suspected_trigger = self._classify_trigger(behavioral, current_status)

        ban_event = BanEvent(
            account_id=account_id,
            ban_timestamp=time.time(),
            ban_type=current_status.value.upper(),
            account_age_at_ban_hours=account_age_hours,
            total_actions_before_ban=total_actions,
            last_action_before_ban=last_action,
            last_action_timestamp=last_action_ts,
            identity_snapshot=identity,
            behavioral_snapshot=behavioral,
            suspected_trigger=suspected_trigger,
        )

        # Persist ban record
        ban_ts = ban_event.ban_timestamp
        pipe = self.redis.pipeline()
        pipe.set(_ban_key(account_id), json.dumps(ban_event.to_dict()))
        pipe.zadd(_bans_all_key(), {json.dumps(ban_event.to_dict()): ban_ts})
        # Trim bans older than 90 days
        cutoff_90d = time.time() - (90 * 86400)
        pipe.zremrangebyscore(_bans_all_key(), "-inf", cutoff_90d)
        await pipe.execute()

        logger.info(
            "Ban event stored for %s (type=%s, trigger=%s, age=%.1fh)",
            account_id,
            ban_event.ban_type,
            ban_event.suspected_trigger,
            account_age_hours,
        )
        return ban_event

    # ------------------------------------------------------------------
    # Batch collection
    # ------------------------------------------------------------------

    async def collect_all(self, account_ids: List[str]) -> Dict[str, Any]:
        """
        Run behavioral snapshot collection for all supplied account IDs.
        Errors per-account are caught and logged rather than propagated,
        so one bad account does not abort the batch.
        """
        results = {"success": [], "failed": []}

        for account_id in account_ids:
            try:
                await self.collect_behavioral_snapshot(account_id)
                results["success"].append(account_id)
            except Exception as exc:
                logger.error("collect_all: failed for %s: %s", account_id, exc)
                results["failed"].append(account_id)

        logger.info(
            "collect_all complete: %d ok, %d failed",
            len(results["success"]),
            len(results["failed"]),
        )
        return results

    # ------------------------------------------------------------------
    # Private: temporal feature computation
    # ------------------------------------------------------------------

    def _compute_temporal_features(self, tweets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Compute temporal features from a list of tweet dicts.

        Each tweet is expected to have a 'created_at' field (Twitter date string
        or ISO-8601). Missing/unparseable timestamps are skipped gracefully.
        """
        now = time.time()
        timestamps: List[float] = []

        for tw in tweets:
            raw_ts = tw.get("created_at", "")
            if not raw_ts:
                continue
            ts = _parse_tweet_timestamp(raw_ts)
            if ts is not None:
                timestamps.append(ts)

        timestamps.sort()

        tweets_last_hour = sum(1 for ts in timestamps if now - ts <= 3600)
        tweets_last_24h = sum(1 for ts in timestamps if now - ts <= 86400)

        # Inter-tweet gaps
        gaps: List[float] = []
        for i in range(1, len(timestamps)):
            gaps.append(timestamps[i] - timestamps[i - 1])

        avg_gap = (sum(gaps) / len(gaps)) if gaps else 0.0
        gap_variance = _variance(gaps) if gaps else 0.0

        # Burst count: consecutive tweets within _BURST_WINDOW_SECONDS
        burst_count = 0
        for i in range(1, len(timestamps)):
            if timestamps[i] - timestamps[i - 1] < _BURST_WINDOW_SECONDS:
                burst_count += 1

        # Shannon entropy over posting hours
        hour_counts: Counter = Counter()
        weekend_count = 0
        for ts in timestamps:
            dt = datetime.fromtimestamp(ts, tz=timezone.utc)
            hour_counts[dt.hour] += 1
            if dt.weekday() >= 5:
                weekend_count += 1

        total = len(timestamps)
        hour_entropy = 0.0
        if total > 0:
            for count in hour_counts.values():
                p = count / total
                if p > 0:
                    hour_entropy -= p * math.log2(p)

        weekend_ratio = (weekend_count / total) if total > 0 else 0.0

        return {
            "tweets_last_hour": tweets_last_hour,
            "tweets_last_24h": tweets_last_24h,
            "avg_gap_seconds": avg_gap,
            "gap_variance": gap_variance,
            "burst_count": burst_count,
            "hour_entropy": hour_entropy,
            "weekend_ratio": weekend_ratio,
        }

    # ------------------------------------------------------------------
    # Private: content feature computation
    # ------------------------------------------------------------------

    def _compute_content_features(self, tweets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Classify tweets and extract content-level features."""
        total = len(tweets)
        if total == 0:
            return {
                "original_count": 0,
                "retweet_count": 0,
                "reply_count": 0,
                "quote_count": 0,
                "url_ratio": 0.0,
                "hashtag_density": 0.0,
                "mention_density": 0.0,
                "avg_length": 0,
                "shield_cta_ratio": 0.0,
            }

        retweet_count = 0
        reply_count = 0
        quote_count = 0
        url_count = 0
        total_hashtags = 0
        total_mentions = 0
        total_chars = 0
        shield_count = 0

        for tw in tweets:
            text: str = tw.get("text", "") or ""

            # Classification by prefix / structure
            if text.startswith("RT @"):
                retweet_count += 1
            elif text.startswith("@"):
                reply_count += 1
            elif tw.get("quoted_tweet_id") or tw.get("is_quote"):
                quote_count += 1

            # URL presence
            if "http://" in text or "https://" in text or "t.co/" in text:
                url_count += 1

            # Hashtag count
            total_hashtags += text.count("#")

            # Mention count
            total_mentions += len([w for w in text.split() if w.startswith("@")])

            total_chars += len(text)

            # Shield/CTA detection
            lower_text = text.lower()
            if any(kw in lower_text for kw in _SHIELD_KEYWORDS):
                shield_count += 1

        original_count = total - retweet_count - reply_count - quote_count
        original_count = max(original_count, 0)

        return {
            "original_count": original_count,
            "retweet_count": retweet_count,
            "reply_count": reply_count,
            "quote_count": quote_count,
            "url_ratio": url_count / total,
            "hashtag_density": total_hashtags / total,
            "mention_density": total_mentions / total,
            "avg_length": int(total_chars / total) if total > 0 else 0,
            "shield_cta_ratio": shield_count / total,
        }

    # ------------------------------------------------------------------
    # Private: engagement feature computation
    # ------------------------------------------------------------------

    def _compute_engagement_features(self, tweets: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Aggregate engagement received across all fetched tweets."""
        if not tweets:
            return {
                "total_likes": 0,
                "total_replies": 0,
                "total_retweets": 0,
                "variance": 0.0,
            }

        likes_per_tweet: List[int] = []
        total_likes = 0
        total_replies = 0
        total_retweets = 0

        for tw in tweets:
            likes = int(tw.get("likes", tw.get("favorite_count", 0)) or 0)
            replies = int(tw.get("reply_count", 0) or 0)
            retweets = int(tw.get("retweet_count", 0) or 0)

            total_likes += likes
            total_replies += replies
            total_retweets += retweets
            likes_per_tweet.append(likes)

        variance = _variance(likes_per_tweet) if likes_per_tweet else 0.0

        return {
            "total_likes": total_likes,
            "total_replies": total_replies,
            "total_retweets": total_retweets,
            "variance": variance,
        }

    # ------------------------------------------------------------------
    # Private: network classification
    # ------------------------------------------------------------------

    def _classify_network(
        self,
        account_id: str,
        followers: List[str],
        following: List[str],
    ) -> Dict[str, int]:
        """
        Classify follower/following lists as swarm vs real humans.

        The swarm_ids set contains internal soul IDs which map to Twitter
        usernames. Since RyanAPI returns usernames, we check membership
        against both the raw set and any loaded username mappings.
        """
        follows_swarm = 0
        follows_real = 0
        followed_by_swarm = 0
        followed_by_real = 0

        swarm_lower = {sid.lower() for sid in self.swarm_ids}
        username_map_lower = {u.lower() for u in self._username_to_soul}

        for username in following:
            uname_lower = username.lower()
            if uname_lower in swarm_lower or uname_lower in username_map_lower:
                follows_swarm += 1
            else:
                follows_real += 1

        for username in followers:
            uname_lower = username.lower()
            if uname_lower in swarm_lower or uname_lower in username_map_lower:
                followed_by_swarm += 1
            else:
                followed_by_real += 1

        return {
            "follows_swarm": follows_swarm,
            "follows_real": follows_real,
            "followed_by_swarm": followed_by_swarm,
            "followed_by_real": followed_by_real,
        }

    # ------------------------------------------------------------------
    # Private: ban trigger heuristic
    # ------------------------------------------------------------------

    def _classify_trigger(
        self, behavioral: BehavioralSnapshot, status: AccountStatus
    ) -> str:
        """
        Heuristic to classify the probable cause of a ban/action.

        This is best-effort signal enrichment for the GNN labels, not
        a deterministic classification system.
        """
        if status == AccountStatus.RATE_LIMITED:
            return "velocity"

        # High tweet velocity in last 24h
        if behavioral.tweets_last_24h > 50:
            return "velocity"

        # Very new account (< 48h)
        if behavioral.account_age_hours < 48:
            return "fingerprint"

        # Lots of Shield/CTA content
        if behavioral.shield_cta_ratio > 0.5:
            return "content"

        # Follows predominantly swarm accounts (looks coordinated)
        total_following = behavioral.follows_swarm_accounts + behavioral.follows_real_humans
        if total_following > 0:
            swarm_ratio = behavioral.follows_swarm_accounts / total_following
            if swarm_ratio > 0.7:
                return "fingerprint"

        # High burst count
        if behavioral.burst_count > 10:
            return "velocity"

        # Very low hour entropy (bot-like posting pattern)
        if behavioral.hour_entropy < 1.0:
            return "fingerprint"

        return "unknown"

    # ------------------------------------------------------------------
    # Private: helpers
    # ------------------------------------------------------------------

    async def _get_username(self, account_id: str) -> Optional[str]:
        """Retrieve twitter username from persisted identity snapshot."""
        raw = await self.redis.get(_identity_key(account_id))
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return data.get("twitter_username") or None
        except (json.JSONDecodeError, KeyError):
            return None


# ---------------------------------------------------------------------------
# Utility functions
# ---------------------------------------------------------------------------

def _parse_tweet_timestamp(raw: str) -> Optional[float]:
    """
    Parse a Twitter date string to a Unix timestamp.
    Accepts Twitter's legacy format ("Thu Jan 01 00:00:00 +0000 2025")
    and ISO-8601 variants.
    """
    if not raw:
        return None

    # ISO-8601
    try:
        dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
        return dt.timestamp()
    except (ValueError, AttributeError):
        pass

    # Twitter legacy format: "Thu Jan 01 00:00:00 +0000 2025"
    try:
        dt = datetime.strptime(raw, "%a %b %d %H:%M:%S %z %Y")
        return dt.timestamp()
    except (ValueError, AttributeError):
        pass

    return None


def _variance(values: List[float]) -> float:
    """Population variance of a numeric list."""
    if len(values) < 2:
        return 0.0
    mean = sum(values) / len(values)
    return sum((v - mean) ** 2 for v in values) / len(values)
