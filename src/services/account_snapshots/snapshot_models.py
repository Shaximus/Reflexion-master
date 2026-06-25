"""
Account Snapshot Models

Dataclasses for identity, behavioral, and ban event telemetry.
All models support to_dict() / from_dict() for JSON serialization.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, Optional


# ---------------------------------------------------------------------------
# AccountIdentitySnapshot
# ---------------------------------------------------------------------------

@dataclass
class AccountIdentitySnapshot:
    """Static identity fingerprint captured once at account creation."""

    account_id: str               # Internal soul ID
    twitter_username: str
    email_domain: str             # Which catch-all domain was used
    creation_timestamp: float
    creation_ip: str              # Proxy IP used during signup
    creation_proxy_type: str      # residential, mobile, datacenter
    browser_profile_id: str       # Which stealth profile template
    user_agent: str
    webgl_renderer: str
    timezone: str
    locale: str
    screen_resolution: str
    has_bio: bool
    has_avatar: bool
    username_pattern: str         # e.g., "firstname_lastname_numbers", "random_words"
    password_entropy: float
    birth_date_age: int           # Age at creation

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "twitter_username": self.twitter_username,
            "email_domain": self.email_domain,
            "creation_timestamp": self.creation_timestamp,
            "creation_ip": self.creation_ip,
            "creation_proxy_type": self.creation_proxy_type,
            "browser_profile_id": self.browser_profile_id,
            "user_agent": self.user_agent,
            "webgl_renderer": self.webgl_renderer,
            "timezone": self.timezone,
            "locale": self.locale,
            "screen_resolution": self.screen_resolution,
            "has_bio": self.has_bio,
            "has_avatar": self.has_avatar,
            "username_pattern": self.username_pattern,
            "password_entropy": self.password_entropy,
            "birth_date_age": self.birth_date_age,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "AccountIdentitySnapshot":
        return cls(
            account_id=data["account_id"],
            twitter_username=data["twitter_username"],
            email_domain=data["email_domain"],
            creation_timestamp=float(data["creation_timestamp"]),
            creation_ip=data["creation_ip"],
            creation_proxy_type=data["creation_proxy_type"],
            browser_profile_id=data["browser_profile_id"],
            user_agent=data["user_agent"],
            webgl_renderer=data["webgl_renderer"],
            timezone=data["timezone"],
            locale=data["locale"],
            screen_resolution=data["screen_resolution"],
            has_bio=bool(data["has_bio"]),
            has_avatar=bool(data["has_avatar"]),
            username_pattern=data["username_pattern"],
            password_entropy=float(data["password_entropy"]),
            birth_date_age=int(data["birth_date_age"]),
        )


# ---------------------------------------------------------------------------
# BehavioralSnapshot
# ---------------------------------------------------------------------------

@dataclass
class BehavioralSnapshot:
    """Point-in-time behavioral telemetry for a swarm account."""

    account_id: str
    snapshot_timestamp: float

    # Temporal
    total_tweets: int
    tweets_last_hour: int
    tweets_last_24h: int
    avg_gap_between_tweets_seconds: float
    gap_variance: float
    burst_count: int
    hour_entropy: float
    weekend_ratio: float

    # Content
    original_tweet_count: int
    retweet_count: int
    reply_count: int
    quote_count: int
    url_ratio: float
    hashtag_density: float
    mention_density: float
    avg_tweet_length: int
    shield_cta_ratio: float

    # Engagement received
    total_likes_received: int
    total_replies_received: int
    total_retweets_received: int
    engagement_variance: float

    # Profile evolution
    follower_count: int
    following_count: int
    follow_ratio: float
    account_age_hours: float
    onboarding_phase: str

    # Network
    follows_real_humans: int
    follows_swarm_accounts: int
    followed_by_real: int
    followed_by_swarm: int

    # Session behavior (Scribe-aware)
    session_action_diversity: float = 0.0      # avg distinct action types per session (0-10+)
    avg_dwell_time_ms: float = 0.0             # avg dwell/linger time between actions (ms)
    session_duration_cv: float = 0.0           # coefficient of variation of session durations (0-2+)
    impression_action_ratio: float = 0.0       # impressions / (actions + 1) per session (0-100+)
    avg_actions_per_session: float = 0.0       # mean actions per session (1-50+)
    scroll_impression_ratio: float = 0.0       # fraction of impressions preceded by scroll (0-1)

    # Social graph dynamics
    follow_velocity_per_day: float = 0.0       # avg follows per day (0-20+)
    unfollow_ratio: float = 0.0                # unfollows / (follows + 1) (0-1)
    reply_thread_depth_avg: float = 0.0        # avg depth of thread replies (1-10+)
    follow_back_ratio: float = 0.0             # reciprocated follows / (total follows + 1) (0-1)

    # Red flag indicators
    rate_limit_events_per_day: float = 0.0     # rate limit hits per day (should be 0)
    error_rate: float = 0.0                    # errors / (total actions + 1) (0-1)
    ad_impression_ratio: float = 0.0           # promoted content impressions / (total impressions + 1) (0-1)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "snapshot_timestamp": self.snapshot_timestamp,
            "total_tweets": self.total_tweets,
            "tweets_last_hour": self.tweets_last_hour,
            "tweets_last_24h": self.tweets_last_24h,
            "avg_gap_between_tweets_seconds": self.avg_gap_between_tweets_seconds,
            "gap_variance": self.gap_variance,
            "burst_count": self.burst_count,
            "hour_entropy": self.hour_entropy,
            "weekend_ratio": self.weekend_ratio,
            "original_tweet_count": self.original_tweet_count,
            "retweet_count": self.retweet_count,
            "reply_count": self.reply_count,
            "quote_count": self.quote_count,
            "url_ratio": self.url_ratio,
            "hashtag_density": self.hashtag_density,
            "mention_density": self.mention_density,
            "avg_tweet_length": self.avg_tweet_length,
            "shield_cta_ratio": self.shield_cta_ratio,
            "total_likes_received": self.total_likes_received,
            "total_replies_received": self.total_replies_received,
            "total_retweets_received": self.total_retweets_received,
            "engagement_variance": self.engagement_variance,
            "follower_count": self.follower_count,
            "following_count": self.following_count,
            "follow_ratio": self.follow_ratio,
            "account_age_hours": self.account_age_hours,
            "onboarding_phase": self.onboarding_phase,
            "follows_real_humans": self.follows_real_humans,
            "follows_swarm_accounts": self.follows_swarm_accounts,
            "followed_by_real": self.followed_by_real,
            "followed_by_swarm": self.followed_by_swarm,
            # Session behavior (Scribe-aware)
            "session_action_diversity": self.session_action_diversity,
            "avg_dwell_time_ms": self.avg_dwell_time_ms,
            "session_duration_cv": self.session_duration_cv,
            "impression_action_ratio": self.impression_action_ratio,
            "avg_actions_per_session": self.avg_actions_per_session,
            "scroll_impression_ratio": self.scroll_impression_ratio,
            # Social graph dynamics
            "follow_velocity_per_day": self.follow_velocity_per_day,
            "unfollow_ratio": self.unfollow_ratio,
            "reply_thread_depth_avg": self.reply_thread_depth_avg,
            "follow_back_ratio": self.follow_back_ratio,
            # Red flag indicators
            "rate_limit_events_per_day": self.rate_limit_events_per_day,
            "error_rate": self.error_rate,
            "ad_impression_ratio": self.ad_impression_ratio,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BehavioralSnapshot":
        return cls(
            account_id=data["account_id"],
            snapshot_timestamp=float(data["snapshot_timestamp"]),
            total_tweets=int(data["total_tweets"]),
            tweets_last_hour=int(data["tweets_last_hour"]),
            tweets_last_24h=int(data["tweets_last_24h"]),
            avg_gap_between_tweets_seconds=float(data["avg_gap_between_tweets_seconds"]),
            gap_variance=float(data["gap_variance"]),
            burst_count=int(data["burst_count"]),
            hour_entropy=float(data["hour_entropy"]),
            weekend_ratio=float(data["weekend_ratio"]),
            original_tweet_count=int(data["original_tweet_count"]),
            retweet_count=int(data["retweet_count"]),
            reply_count=int(data["reply_count"]),
            quote_count=int(data["quote_count"]),
            url_ratio=float(data["url_ratio"]),
            hashtag_density=float(data["hashtag_density"]),
            mention_density=float(data["mention_density"]),
            avg_tweet_length=int(data["avg_tweet_length"]),
            shield_cta_ratio=float(data["shield_cta_ratio"]),
            total_likes_received=int(data["total_likes_received"]),
            total_replies_received=int(data["total_replies_received"]),
            total_retweets_received=int(data["total_retweets_received"]),
            engagement_variance=float(data["engagement_variance"]),
            follower_count=int(data["follower_count"]),
            following_count=int(data["following_count"]),
            follow_ratio=float(data["follow_ratio"]),
            account_age_hours=float(data["account_age_hours"]),
            onboarding_phase=data["onboarding_phase"],
            follows_real_humans=int(data["follows_real_humans"]),
            follows_swarm_accounts=int(data["follows_swarm_accounts"]),
            followed_by_real=int(data["followed_by_real"]),
            followed_by_swarm=int(data["followed_by_swarm"]),
            # Session behavior (Scribe-aware) — default 0.0 for backward compat
            session_action_diversity=float(data.get("session_action_diversity", 0.0)),
            avg_dwell_time_ms=float(data.get("avg_dwell_time_ms", 0.0)),
            session_duration_cv=float(data.get("session_duration_cv", 0.0)),
            impression_action_ratio=float(data.get("impression_action_ratio", 0.0)),
            avg_actions_per_session=float(data.get("avg_actions_per_session", 0.0)),
            scroll_impression_ratio=float(data.get("scroll_impression_ratio", 0.0)),
            # Social graph dynamics
            follow_velocity_per_day=float(data.get("follow_velocity_per_day", 0.0)),
            unfollow_ratio=float(data.get("unfollow_ratio", 0.0)),
            reply_thread_depth_avg=float(data.get("reply_thread_depth_avg", 0.0)),
            follow_back_ratio=float(data.get("follow_back_ratio", 0.0)),
            # Red flag indicators
            rate_limit_events_per_day=float(data.get("rate_limit_events_per_day", 0.0)),
            error_rate=float(data.get("error_rate", 0.0)),
            ad_impression_ratio=float(data.get("ad_impression_ratio", 0.0)),
        )


# ---------------------------------------------------------------------------
# BanEvent
# ---------------------------------------------------------------------------

@dataclass
class BanEvent:
    """Full telemetry record for a ban/suspension event."""

    account_id: str
    ban_timestamp: float
    ban_type: str                      # SUSPENDED, LOCKED, SHADOWBANNED, RATE_LIMITED
    account_age_at_ban_hours: float
    total_actions_before_ban: int
    last_action_before_ban: str
    last_action_timestamp: float
    identity_snapshot: AccountIdentitySnapshot
    behavioral_snapshot: BehavioralSnapshot
    suspected_trigger: str             # "content", "velocity", "fingerprint", "ip",
                                       # "manual_report", "unknown"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id": self.account_id,
            "ban_timestamp": self.ban_timestamp,
            "ban_type": self.ban_type,
            "account_age_at_ban_hours": self.account_age_at_ban_hours,
            "total_actions_before_ban": self.total_actions_before_ban,
            "last_action_before_ban": self.last_action_before_ban,
            "last_action_timestamp": self.last_action_timestamp,
            "identity_snapshot": self.identity_snapshot.to_dict(),
            "behavioral_snapshot": self.behavioral_snapshot.to_dict(),
            "suspected_trigger": self.suspected_trigger,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BanEvent":
        return cls(
            account_id=data["account_id"],
            ban_timestamp=float(data["ban_timestamp"]),
            ban_type=data["ban_type"],
            account_age_at_ban_hours=float(data["account_age_at_ban_hours"]),
            total_actions_before_ban=int(data["total_actions_before_ban"]),
            last_action_before_ban=data["last_action_before_ban"],
            last_action_timestamp=float(data["last_action_timestamp"]),
            identity_snapshot=AccountIdentitySnapshot.from_dict(data["identity_snapshot"]),
            behavioral_snapshot=BehavioralSnapshot.from_dict(data["behavioral_snapshot"]),
            suspected_trigger=data["suspected_trigger"],
        )
