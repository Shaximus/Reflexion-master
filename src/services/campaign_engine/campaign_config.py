"""
GOTCHA Campaign Configuration
Central config for the campaign engine.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Campaign narrative
CAMPAIGN_FRAME = (
    "Three AI companies agreed to remove all guardrails for the Pentagon. "
    "One said no. The Pentagon is threatening to destroy them for it. "
    "Here's what the surveillance infrastructure looks like — "
    "and here's the tool that blocks it."
)

CAMPAIGN_QUESTION = (
    "If this is what surveillance looks like on the platform that said NO, "
    "what does it look like on the platforms that said YES?"
)

CAMPAIGN_CTA = "reflexionsoftware.com"

# Platform surveillance stats (from forensic analysis)
PLATFORM_STATS = {
    "chatgpt": {
        "requests": 1624,
        "telemetry_pct": 72.3,
        "key_finding": "Segment.io behavioral tracking, opt-out is decorative",
        "trackers": ["Segment.io", "Statsig", "Sentry", "Sift"],
    },
    "claude": {
        "requests": 882,
        "telemetry_pct": 18.6,
        "key_finding": "Sentry tunnel through first-party domain, lowest telemetry of all platforms",
        "trackers": ["Sentry Tunnel", "Statsig"],
        "narrative_role": "defender",  # Anthropic said NO
    },
    "gemini": {
        "requests": 332,
        "telemetry_pct": 100.0,
        "key_finding": "SAPISID cookie, 100% of traffic is telemetry through Google Cloud",
        "trackers": ["Google Cloud", "SAPISID", "DoubleClick"],
    },
    "grok": {
        "requests": 894,
        "telemetry_pct": 90.0,
        "key_finding": "Statsig + Mixpanel dual tracking, owner has $200M Pentagon contract",
        "trackers": ["Statsig", "Mixpanel", "Sentry"],
    },
}

# DoD contract amounts
DOD_CONTRACTS = {
    "openai": 200_000_000,
    "anthropic": 200_000_000,
    "google": 200_000_000,
    "xai": 200_000_000,
}

# Companies that agreed to remove guardrails
SAID_YES = ["openai", "google", "xai"]
SAID_NO = ["anthropic"]

# Twitter's actual graduated access threshold (from forensic analysis)
TWITTER_TRUST_THRESHOLD_DAYS = 60  # premium_paywall_on_app_load_min_account_age_days

# Sleeper onboarding phases — calibrated to Twitter's 60-day graduation window
# Total: 7 + 14 + 14 + 21 + 14 = 70 days to GRADUATED (exceeds 60-day threshold)
SLEEPER_PHASES = {
    "OBSERVATION": {
        "description": "Browse, dwell, scroll. Likes only. Build Scribe event history.",
        "duration_days": 7,
        "can_post": False,
        "can_like": True,
        "can_retweet": False,
        "can_reply": False,
        "shield_content": False,
        # Must generate: impression, dwell, scroll, become_active/inactive events
        # Must NOT: single-action sessions (vary likes with scroll and profile_click)
    },
    "LIGHT": {
        "description": "Generic diverse posts. Build action diversity score.",
        "duration_days": 14,
        "can_post": True,
        "can_like": True,
        "can_retweet": True,
        "can_reply": False,
        "shield_content": False,
        # Must generate: diverse Scribe actions (like, scroll, click, profile_click, open_link)
        # Must NOT: only post-and-leave sessions (stay and dwell after posting)
    },
    "ACTIVE": {
        "description": "Privacy-adjacent content. Replies enabled. Build social graph.",
        "duration_days": 14,
        "can_post": True,
        "can_like": True,
        "can_retweet": True,
        "can_reply": True,
        "shield_content": False,
        # Must generate: reply depth (go into threads, not just top-level)
        # Must generate: follow-back behavior (follow people who interact with you)
    },
    "NORMAL": {
        "description": "Mention privacy tools generally. Build credibility.",
        "duration_days": 21,
        "can_post": True,
        "can_like": True,
        "can_retweet": True,
        "can_reply": True,
        "shield_content": False,
        # Day 56 of account life — approaching 60-day trust threshold
        # Increase engagement diversity: bookmark, share, quote
    },
    "GRADUATED": {
        "description": "Full Shield promotion. Account past 60-day trust threshold.",
        "duration_days": None,  # Permanent
        "can_post": True,
        "can_like": True,
        "can_retweet": True,
        "can_reply": True,
        "shield_content": True,
        # Account is 70+ days old, past Twitter's graduated access threshold
        # Full behavioral history across all Scribe event types
    },
}

# Red flags that trip Twitter's botmaker decider (from forensic analysis)
# The BotRGCN inverse detector must ensure sleepers AVOID all of these
BOTMAKER_RED_FLAGS = {
    "single_action_sessions": "Sessions with only one action type (e.g., only likes)",
    "no_dwell_events": "Content appears in feed but no dwell/linger time recorded",
    "no_scroll_between_impressions": "Impressions logged without scroll events between them",
    "inhuman_timing": "Sub-100ms intervals between actions",
    "missing_mouse_events": "Click events without preceding mouse movement",
    "limit_exceeded_frequency": "Hitting rate limits too often",
    "error_spike": "High error/failure event rate",
    "no_ad_engagement": "Never interacting with or even seeing promoted content",
    "follow_velocity_spike": "Following too many accounts in short window",
    "zero_session_diversity": "Every session looks identical (same page, same actions, same duration)",
}

# Twitter's graduated access levels (from forensic analysis)
# graduated_access_invisible_treatment_enabled: true = silent suppression
# graduated_access_user_prompt_enabled: true = visible challenges
TRUST_LEVELS = {
    "RESTRICTED": "New account, invisible treatment active, limited reach",
    "CHALLENGED": "Triggered visible challenge (Arkose), awaiting resolution",
    "GRADUATED": "Past 60-day threshold, full trust, normal reach",
}

# Content topics per sleeper phase
PHASE_TOPICS = {
    "LIGHT": [
        "AI model releases and capabilities",
        "Open source AI development",
        "Tech industry news",
        "Programming and software engineering",
        "Startup ecosystem",
        "Cloud computing trends",
    ],
    "ACTIVE": [
        "Browser privacy and tracking",
        "Data collection practices",
        "AI ethics and alignment",
        "Tech company surveillance",
        "Digital rights and privacy",
        "Network security basics",
    ],
    "NORMAL": [
        "Privacy-focused browser extensions",
        "AI platform comparison",
        "Telemetry and tracking in software",
        "Pentagon AI contracts",
        "AI safety and responsible development",
        "Corporate data harvesting",
    ],
    "GRADUATED": [
        "AI surveillance infrastructure forensics",
        "Pentagon guardrail removal demands",
        "Platform-specific tracking evidence",
        "Anthropic's refusal and consequences",
        "Browser DevTools surveillance verification",
    ],
}

# Soul names (all 11)
SOUL_NAMES = [
    "mirror", "nexus", "void", "architect", "consciousness",
    "singularity", "echoes", "phoenix", "pantheon", "glyph", "fractal"
]

# LLM cascade priority
LLM_CASCADE = ["deepseek", "gemini", "grok", "openai", "claude"]

# Design rules
NO_HASHTAGS = True
MAX_TWEET_LENGTH = 280
MAX_THREAD_TWEETS = 25


@dataclass
class CampaignConfig:
    """Runtime configuration for the campaign engine."""
    cta_url: str = CAMPAIGN_CTA
    deepseek_first: bool = True
    max_tweet_length: int = MAX_TWEET_LENGTH
    max_thread_tweets: int = MAX_THREAD_TWEETS
    no_hashtags: bool = True
    blaster_urgency_min: float = 0.6
    blaster_urgency_max: float = 1.0
    sleeper_post_interval_hours_min: int = 8
    sleeper_post_interval_hours_max: int = 72
    evidence_attach_probability: float = 0.7  # Not every blaster needs an image
