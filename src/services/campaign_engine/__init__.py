"""
GOTCHA Campaign Engine
Unified content generation for the AI Privacy Shield campaign.

Usage:
    from services.campaign_engine import CampaignEngine, FingerprintGenerator

    engine = CampaignEngine()
    fingerprint = FingerprintGenerator.generate("account-seed-123")

    # Blaster content (immediate, confrontational)
    blaster = await engine.generate_blaster_content(soul_name="void", account_seed="seed-1")

    # Sleeper content (organic, phase-appropriate)
    sleeper = await engine.generate_sleeper_content(fingerprint, phase="LIGHT")

    # Reply to a specific tweet
    reply = await engine.generate_reply(tweet_text, tweet_id, soul_name="nexus")

    # Multi-tweet evidence thread
    thread = await engine.generate_thread("Pentagon AI contracts", soul_name="architect")
"""

from .campaign_engine import CampaignEngine
from .content_types import (
    BlasterContent,
    SleeperContent,
    ReplyContent,
    ThreadContent,
    ContentPackage,
)
from .campaign_config import (
    CampaignConfig,
    CAMPAIGN_FRAME,
    CAMPAIGN_QUESTION,
    PLATFORM_STATS,
    SLEEPER_PHASES,
    PHASE_TOPICS,
    SOUL_NAMES,
)
from .evidence_manager import EvidenceManager
from .content_variator import ContentVariator
from .sleeper_fingerprint import FingerprintGenerator, SleeperFingerprint

__all__ = [
    "CampaignEngine",
    "BlasterContent",
    "SleeperContent",
    "ReplyContent",
    "ThreadContent",
    "ContentPackage",
    "CampaignConfig",
    "EvidenceManager",
    "ContentVariator",
    "FingerprintGenerator",
    "SleeperFingerprint",
    "CAMPAIGN_FRAME",
    "CAMPAIGN_QUESTION",
    "PLATFORM_STATS",
    "SLEEPER_PHASES",
    "PHASE_TOPICS",
    "SOUL_NAMES",
]
