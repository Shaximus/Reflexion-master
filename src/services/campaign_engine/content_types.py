"""
GOTCHA Campaign Content Types
Dataclass definitions for all campaign content outputs.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List
from datetime import datetime


@dataclass
class BlasterContent:
    """Immediate, confrontational, expendable content for blaster accounts."""
    text: str                                    # Tweet text (≤280 chars)
    evidence_images: List[bytes] = field(default_factory=list)  # Forensic screenshots
    evidence_descriptions: List[str] = field(default_factory=list)  # Alt text
    platform_targeted: Optional[str] = None      # 'chatgpt'|'claude'|'gemini'|'grok'
    cta_url: str = "reflexionsoftware.com"
    urgency: float = 0.8                         # 0-1, how confrontational
    drs_format_used: str = ""                     # Which Shield format was selected
    soul_name: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    model_used: str = "deepseek"                 # Which LLM generated this


@dataclass
class SleeperContent:
    """Organic, phase-appropriate content for sleeper accounts."""
    text: str                                    # Tweet text (≤280 chars)
    content_type: str = "generic_tech"           # "generic_tech"|"privacy_adjacent"|"ai_discussion"|"shield_promotion"
    personality: str = ""                        # Soul voice name
    phase: str = "LIGHT"                         # Current onboarding phase
    drs_format_used: str = ""                    # Which DRS rhetorical format
    media: Optional[List[bytes]] = None          # Optional images (NORMAL+ only)
    in_reply_to_id: Optional[str] = None         # If responding to a real tweet
    generated_at: datetime = field(default_factory=datetime.now)
    model_used: str = "deepseek"


@dataclass
class ReplyContent:
    """Contextual reply to a specific tweet about AI/privacy/surveillance."""
    text: str                                    # Reply text (≤280 chars)
    in_reply_to_id: str = ""                     # Tweet being replied to
    evidence_images: List[bytes] = field(default_factory=list)
    evidence_descriptions: List[str] = field(default_factory=list)
    drs_format_used: str = ""
    relevance_score: float = 0.0                 # From ShieldTriggerDetector
    platform_targeted: Optional[str] = None
    soul_name: str = ""
    generated_at: datetime = field(default_factory=datetime.now)
    model_used: str = "deepseek"


@dataclass
class ThreadContent:
    """Multi-tweet evidence thread (revelation)."""
    tweets: List[str] = field(default_factory=list)     # Ordered tweet texts
    evidence_per_tweet: List[Optional[bytes]] = field(default_factory=list)  # Image per tweet
    evidence_descriptions: List[str] = field(default_factory=list)
    topic: str = ""
    total_tweets: int = 0
    soul_name: str = ""
    platform_targeted: Optional[str] = None
    generated_at: datetime = field(default_factory=datetime.now)
    model_used: str = "deepseek"


@dataclass
class ContentPackage:
    """Wrapper for any content type with posting metadata."""
    content: BlasterContent | SleeperContent | ReplyContent | ThreadContent
    account_id: str = ""                         # Which account posts this
    scheduled_time: Optional[datetime] = None    # When to post (None = immediate)
    priority: int = 5                            # 1-10, higher = more urgent
    retry_count: int = 0
    max_retries: int = 3
