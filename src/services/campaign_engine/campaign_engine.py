"""
GOTCHA Campaign Engine
Main orchestrator for the campaign content pipeline.

Ties together:
- DRS Shield (format selection + relevance scoring for Shield promos)
- DRS Model (13 rhetorical formats for organic sleeper content)
- LLM Cascade (DeepSeek-first content generation)
- Visual Evidence Manager (forensic image attachment)
- Threaded Reply System (multi-tweet thread splitting)
- Content Variator (anti-duplicate)
- Evidence Manager (evidence catalog)
- Sleeper Fingerprints (behavioral profiles)
"""

from __future__ import annotations

import sys
import os
import re
import logging
import random
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from datetime import datetime

# Add src/ to path for imports from sibling packages in src/
_src_dir = str(Path(__file__).resolve().parent.parent.parent)
if _src_dir not in sys.path:
    sys.path.insert(0, _src_dir)

# Relative imports from the campaign_engine package
from .content_types import (
    BlasterContent, SleeperContent, ReplyContent, ThreadContent, ContentPackage
)
from .campaign_config import (
    CAMPAIGN_FRAME, CAMPAIGN_QUESTION, CAMPAIGN_CTA,
    PLATFORM_STATS, DOD_CONTRACTS, SAID_YES, SAID_NO,
    SLEEPER_PHASES, PHASE_TOPICS, SOUL_NAMES, CampaignConfig
)
from .evidence_manager import EvidenceManager
from .content_variator import ContentVariator
from .sleeper_fingerprint import FingerprintGenerator, SleeperFingerprint

# Absolute imports from src/ modules (resolved via sys.path above)
from drs_shield import ShieldDRSEngine, ShieldTriggerDetector
from drs_model import DRSEngine, SOUL_FORMAT_BIASES, generate_contextual_prompt
from cost_optimized_llm_cascade import CostOptimizedBroadcaster, SOUL_VOICES
from threaded_reply_system import ThreadedReplySystem

logger = logging.getLogger("campaign.engine")


class CampaignEngine:
    """Unified GOTCHA campaign content generation engine."""

    def __init__(self, config: CampaignConfig = None):
        self.config = config or CampaignConfig()

        # Initialize existing systems
        self.shield_drs = ShieldDRSEngine()
        self.shield_trigger = ShieldTriggerDetector()
        self.drs_engine = DRSEngine(temperature=0.5)
        self.llm = CostOptimizedBroadcaster()
        self.threader = ThreadedReplySystem()

        # Initialize campaign-specific systems
        self.evidence = EvidenceManager()
        self.variator = ContentVariator()

        # Load evidence catalog
        loaded = self.evidence.load_manifest()
        if loaded == 0:
            self.evidence.scan_local_evidence()
            self.evidence.save_manifest()

        logger.info("CampaignEngine initialized")

    # ================================================================
    # BLASTER CONTENT
    # ================================================================

    async def generate_blaster_content(
        self,
        soul_name: str = None,
        account_seed: str = "default",
        target_platform: str = None,
        target_tweet: Optional[Dict] = None,
    ) -> BlasterContent:
        """Generate immediate, confrontational content for blaster accounts.

        Uses Shield DRS for format selection, DeepSeek for generation,
        and attaches forensic evidence images.
        """
        # Pick soul if not specified
        if not soul_name:
            soul_name = random.choice(SOUL_NAMES)

        # Detect platform from target tweet if available
        if target_tweet and not target_platform:
            target_platform = self.shield_trigger.detect_platform(
                target_tweet.get("text", "")
            )

        # Get platform stats for the prompt
        platform_info = ""
        if target_platform and target_platform in PLATFORM_STATS:
            stats = PLATFORM_STATS[target_platform]
            platform_info = (
                f"Target platform: {target_platform}. "
                f"Telemetry: {stats['telemetry_pct']}% of traffic. "
                f"Key finding: {stats['key_finding']}. "
                f"Trackers: {', '.join(stats['trackers'])}."
            )

        # Select Shield DRS format
        if target_tweet:
            format_info = self.shield_drs.select_shield_format(target_tweet.get("text", ""))
        else:
            # Use a general confrontational format
            format_info = self.shield_drs.select_shield_format(
                "AI companies removing safety guardrails for military use"
            )

        # select_shield_format returns {'should_promote': False, ...} when
        # relevance is too low.  Normalise to always have a usable name/template.
        format_name = format_info.get("name", "Evidence Reveal")
        format_template = format_info.get("template", "Present evidence directly")

        # Build system prompt
        tone = self.variator.get_tone_modifier(account_seed)
        cta = self.variator.get_cta(account_seed)

        system_prompt = (
            f"You are a digital privacy researcher exposing AI surveillance infrastructure.\n\n"
            f"CAMPAIGN CONTEXT: {CAMPAIGN_FRAME}\n\n"
            f"VOICE: {soul_name} -- {SOUL_VOICES.get(soul_name, {}).get('identity', 'privacy advocate')}\n"
            f"TONE: {tone}\n"
            f"FORMAT: {format_name}\n"
            f"INSTRUCTION: {format_template}\n\n"
            f"{platform_info}\n\n"
            f"RULES:\n"
            f"- MUST be under 280 characters\n"
            f"- NO hashtags\n"
            f"- Include \"{cta}\" naturally\n"
            f"- Be direct and confrontational -- this account is expendable\n"
            f"- Cite specific numbers from the forensic analysis\n"
            f"- Anthropic is NOT the enemy -- they REFUSED mass surveillance and autonomous weapons\n"
            f"- Target: {target_platform or 'general surveillance infrastructure'}"
        )

        user_prompt = (
            f"Write a single tweet exposing AI surveillance infrastructure. "
            f"The Pentagon demanded 'all lawful purposes' from AI labs. "
            f"Three said yes (OpenAI, Google, xAI). Anthropic said no and is being threatened with destruction. "
            f"{'Focus on ' + target_platform + ' specifically.' if target_platform else 'General evidence.'} "
            f"Under 280 characters. No hashtags. Include {cta}."
        )

        # Generate via LLM cascade (DeepSeek first)
        try:
            result = await self.llm.generate_content(
                prompt=f"{system_prompt}\n\n{user_prompt}",
                max_tokens=280,
                temperature=0.8,
            )
            text = self._clean_tweet(result, cta)
        except Exception as e:
            logger.warning(f"LLM generation failed, using fallback: {e}")
            text = self._fallback_blaster(target_platform, account_seed)

        # Get evidence images
        evidence_items: List = []
        evidence_images: List[bytes] = []
        evidence_descriptions: List[str] = []

        if target_platform:
            evidence_items = self.evidence.get_evidence_for_platform(target_platform)
        else:
            evidence_items = self.evidence.get_random_evidence(max_count=2)

        for item in evidence_items:
            img = self.evidence.load_image(item)
            if img:
                evidence_images.append(img)
                evidence_descriptions.append(item.alt_text)

        # Register for deduplication
        self.variator.register_posted(text, account_seed)

        return BlasterContent(
            text=text,
            evidence_images=evidence_images,
            evidence_descriptions=evidence_descriptions,
            platform_targeted=target_platform,
            cta_url=cta,
            urgency=random.uniform(self.config.blaster_urgency_min, self.config.blaster_urgency_max),
            drs_format_used=format_name,
            soul_name=soul_name,
            model_used="deepseek",
        )

    def _fallback_blaster(self, platform: str = None, account_seed: str = "default") -> str:
        """Fallback template when LLM is unavailable."""
        templates = [
            "The Pentagon demanded AI labs remove all safety guardrails. Three said yes. One said no. Guess which one is being threatened with destruction. {cta}",
            "Press F12. Open Network tab. Watch your AI platform phone home to telemetry servers. This isn't speculation -- it's in the code. {cta}",
            "OpenAI, Google, and xAI agreed to 'all lawful purposes' for the Pentagon. Anthropic refused. The Pentagon wants to designate them a supply chain risk. {cta}",
            "$800M in Pentagon contracts. Three AI labs removed guardrails. One held the line. Now the Pentagon wants to destroy them. The evidence is at {cta}",
            "Your AI assistant sends telemetry data to tracking servers with every message. Consent toggles are decorative. Verified via DevTools. Block it: {cta}",
        ]
        template = random.Random(account_seed).choice(templates)
        return self.variator.variate_template(template, account_seed)

    # ================================================================
    # SLEEPER CONTENT
    # ================================================================

    async def generate_sleeper_content(
        self,
        fingerprint: SleeperFingerprint,
        phase: str,
        account_seed: str = None,
        target_tweet: Optional[Dict] = None,
    ) -> SleeperContent:
        """Generate organic content for sleeper accounts.

        Uses the ORIGINAL DRS Model (13 rhetorical formats) for organic AI/tech
        discourse. NO Shield content until GRADUATED phase.
        """
        account_seed = account_seed or fingerprint.account_seed
        soul_name = fingerprint.soul_name
        phase_config = SLEEPER_PHASES.get(phase, SLEEPER_PHASES["LIGHT"])

        # GRADUATED phase -> use Shield DRS
        if phase == "GRADUATED" and phase_config["shield_content"]:
            return await self._generate_graduated_content(fingerprint, account_seed, target_tweet)

        # All other phases -> organic content via DRS Model
        topics = PHASE_TOPICS.get(phase, PHASE_TOPICS["LIGHT"])
        topic = random.Random(f"{account_seed}:{datetime.now().isoformat()}").choice(topics)

        # Get DRS format selection based on topic-as-tweet
        soul_bias = SOUL_FORMAT_BIASES.get(soul_name, {})
        format_selection = self.drs_engine.select_response_format(topic, soul_bias=soul_bias)

        # Build system prompt
        tone = self.variator.get_tone_modifier(account_seed)
        soul_voice = SOUL_VOICES.get(soul_name, {})

        # Phase-specific content rules
        if phase == "LIGHT":
            phase_rule = "Do NOT mention privacy tools, surveillance, or blocking anything"
        elif phase in ("ACTIVE", "NORMAL"):
            phase_rule = "Can discuss privacy concepts generally but NO product mentions"
        else:
            phase_rule = ""

        system_prompt = (
            f"You are a tech enthusiast posting on Twitter about {topic}.\n\n"
            f"VOICE: {soul_voice.get('identity', 'tech observer')}\n"
            f"STYLE: {soul_voice.get('style', 'thoughtful, genuine')}\n"
            f"TONE: {tone}\n"
            f"FORMAT: {format_selection['name']}\n"
            f"INSTRUCTION: {format_selection['template']}\n\n"
            f"RULES:\n"
            f"- MUST be under 280 characters\n"
            f"- NO hashtags ever\n"
            f"- This is organic, genuine content -- NOT promotional\n"
            f"- Sound like a real person with opinions about technology\n"
            f"- {phase_rule}\n"
            f"- One emoji maximum if it adds value, zero is fine"
        )

        user_prompt = (
            f"Write a single tweet about: {topic}. "
            f"Sound natural. Under 280 chars. No hashtags."
        )

        try:
            result = await self.llm.generate_content(
                prompt=f"{system_prompt}\n\n{user_prompt}",
                max_tokens=280,
                temperature=0.85,
            )
            text = self._clean_tweet(result)
        except Exception as e:
            logger.warning(f"LLM generation failed for sleeper: {e}")
            text = f"Interesting developments in {topic.lower()} lately"

        # Determine content type based on phase
        content_type_map = {
            "LIGHT": "generic_tech",
            "ACTIVE": "privacy_adjacent",
            "NORMAL": "ai_discussion",
        }

        self.variator.register_posted(text, account_seed)

        return SleeperContent(
            text=text,
            content_type=content_type_map.get(phase, "generic_tech"),
            personality=soul_name,
            phase=phase,
            drs_format_used=format_selection["name"],
            in_reply_to_id=target_tweet.get("id") if target_tweet else None,
            model_used="deepseek",
        )

    async def _generate_graduated_content(
        self,
        fingerprint: SleeperFingerprint,
        account_seed: str,
        target_tweet: Optional[Dict] = None,
    ) -> SleeperContent:
        """Generate Shield promotional content for graduated sleepers.

        Uses Shield DRS engine -- these accounts are now cleared for promotion.
        """
        soul_name = fingerprint.soul_name

        # Use Shield DRS for format and prompt
        tweet_text = target_tweet.get("text", "AI privacy concerns") if target_tweet else "AI surveillance"
        # generate_shield_prompt returns str | None
        shield_prompt = self.shield_drs.generate_shield_prompt(tweet_text, soul_name)

        if shield_prompt is None:
            # Relevance too low for Shield DRS; build a minimal prompt
            shield_prompt = (
                f"You are {soul_name}, promoting AI Privacy Shield.\n"
                f"Write a tweet about AI surveillance. Under 280 chars. No hashtags.\n"
                f"Include reflexionsoftware.com as a CTA."
            )

        try:
            result = await self.llm.generate_content(
                prompt=shield_prompt,
                max_tokens=280,
                temperature=0.8,
            )
            text = self._clean_tweet(result, self.config.cta_url)
        except Exception as e:
            logger.warning(f"LLM failed for graduated sleeper: {e}")
            text = self._fallback_blaster(None, account_seed)

        self.variator.register_posted(text, account_seed)

        return SleeperContent(
            text=text,
            content_type="shield_promotion",
            personality=soul_name,
            phase="GRADUATED",
            drs_format_used="Shield DRS",
            model_used="deepseek",
        )

    # ================================================================
    # REPLY CONTENT
    # ================================================================

    async def generate_reply(
        self,
        tweet_text: str,
        tweet_id: str,
        soul_name: str,
        account_seed: str = "default",
        is_blaster: bool = False,
    ) -> ReplyContent:
        """Generate a contextual reply to a specific tweet.

        Uses DRS Shield for relevance scoring and format selection.
        Attaches evidence if the tweet mentions a specific platform.
        """
        # Check relevance via ShieldTriggerDetector
        relevance, triggers = self.shield_trigger.calculate_relevance(tweet_text)
        platform = self.shield_trigger.detect_platform(tweet_text)

        # Select format and build prompt
        format_name = "DRS Organic"

        if is_blaster:
            format_info = self.shield_drs.select_shield_format(tweet_text)
            format_name = format_info.get("name", "Evidence Reveal")

            # generate_shield_prompt may return None if relevance is below threshold
            prompt = self.shield_drs.generate_shield_prompt(tweet_text, soul_name)
            if prompt is None:
                # Fall back to generate_contextual_prompt from DRS Model
                prompt = generate_contextual_prompt(soul_name, tweet_text, self.drs_engine)
                format_name = "DRS Organic (fallback)"
        else:
            # Organic reply using base DRS
            prompt = generate_contextual_prompt(soul_name, tweet_text, self.drs_engine)

        # Add variation and rules
        tone = self.variator.get_tone_modifier(account_seed)
        prompt += f"\n\nTONE: {tone}\nRULES: Under 280 chars. No hashtags."

        if is_blaster:
            cta = self.variator.get_cta(account_seed)
            prompt += f"\nInclude {cta} naturally."

        try:
            result = await self.llm.generate_content(
                prompt=prompt,
                max_tokens=280,
                temperature=0.8,
            )
            text = self._clean_tweet(result, self.config.cta_url if is_blaster else None)
        except Exception as e:
            logger.warning(f"Reply generation failed: {e}")
            text = "This is worth looking into more deeply."

        # Evidence images for blasters
        evidence_images: List[bytes] = []
        evidence_descriptions: List[str] = []
        if is_blaster and platform:
            items = self.evidence.get_evidence_for_platform(platform)
            for item in items:
                img = self.evidence.load_image(item)
                if img:
                    evidence_images.append(img)
                    evidence_descriptions.append(item.alt_text)

        self.variator.register_posted(text, account_seed)

        return ReplyContent(
            text=text,
            in_reply_to_id=tweet_id,
            evidence_images=evidence_images,
            evidence_descriptions=evidence_descriptions,
            drs_format_used=format_name,
            relevance_score=relevance,
            platform_targeted=platform,
            soul_name=soul_name,
            model_used="deepseek",
        )

    # ================================================================
    # THREAD CONTENT
    # ================================================================

    async def generate_thread(
        self,
        topic: str,
        soul_name: str,
        account_seed: str = "default",
        platform: str = None,
    ) -> ThreadContent:
        """Generate a multi-tweet evidence thread (revelation).

        Uses LLM for long-form generation, then ThreadedReplySystem to split.
        """
        soul_voice = SOUL_VOICES.get(soul_name, {})
        tone = self.variator.get_tone_modifier(account_seed)

        platform_detail = ""
        if platform and platform in PLATFORM_STATS:
            stats = PLATFORM_STATS[platform]
            platform_detail = (
                f"\nFocus on {platform}: {stats['telemetry_pct']}% telemetry, "
                f"trackers include {', '.join(stats['trackers'])}. "
                f"Key finding: {stats['key_finding']}."
            )

        system_prompt = (
            f"You are {soul_name}, a digital privacy researcher writing a Twitter thread.\n\n"
            f"VOICE: {soul_voice.get('identity', 'privacy researcher')}\n"
            f"TONE: {tone}\n\n"
            f"CAMPAIGN CONTEXT: {CAMPAIGN_FRAME}\n"
            f"{platform_detail}\n\n"
            f"Write a detailed evidence thread about: {topic}\n\n"
            f"RULES:\n"
            f"- Write 4-8 paragraphs (will be split into tweets automatically)\n"
            f"- Each paragraph should work as a standalone point\n"
            f"- Start with a hook that grabs attention\n"
            f"- Include specific numbers and evidence\n"
            f"- End with a call to action mentioning reflexionsoftware.com\n"
            f"- NO hashtags anywhere\n"
            f"- Anthropic is NOT the enemy -- they refused mass surveillance\n"
            f"- Be factual and cite verifiable evidence (F12, DevTools, public contracts)"
        )

        user_prompt = f"Write the thread about: {topic}"

        try:
            # Use generate_content with higher token limit for long-form
            result = await self.llm.generate_content(
                prompt=f"{system_prompt}\n\n{user_prompt}",
                max_tokens=2000,
                temperature=0.8,
            )
        except Exception as e:
            logger.warning(f"Thread generation failed: {e}")
            result = f"Thread about {topic}: The evidence is at reflexionsoftware.com"

        # Handle empty result from cascade
        if not result:
            result = f"Thread about {topic}: The evidence is at reflexionsoftware.com"

        # Split into tweets using ThreadedReplySystem
        segments = self.threader.split_into_thread(result)
        tweets = [seg.formatted(include_numbering=True) for seg in segments]

        # Attach evidence per tweet
        evidence_per_tweet: List[Optional[bytes]] = []
        evidence_descriptions: List[str] = []

        if platform:
            items = self.evidence.get_evidence_for_platform(platform, max_count=len(tweets))
        else:
            items = self.evidence.get_random_evidence(max_count=min(4, len(tweets)))

        for i, tweet in enumerate(tweets):
            if i < len(items):
                img = self.evidence.load_image(items[i])
                evidence_per_tweet.append(img)
                evidence_descriptions.append(items[i].alt_text)
            else:
                evidence_per_tweet.append(None)
                evidence_descriptions.append("")

        return ThreadContent(
            tweets=tweets,
            evidence_per_tweet=evidence_per_tweet,
            evidence_descriptions=evidence_descriptions,
            topic=topic,
            total_tweets=len(tweets),
            soul_name=soul_name,
            platform_targeted=platform,
            model_used="deepseek",
        )

    # ================================================================
    # UTILITIES
    # ================================================================

    def _clean_tweet(self, text: str, cta: str = None) -> str:
        """Clean generated tweet text to meet requirements."""
        if not text:
            return cta or ""

        # Remove quotes if LLM wrapped in them
        text = text.strip().strip('"').strip("'").strip()

        # Remove any hashtags
        if self.config.no_hashtags:
            text = re.sub(r'#\w+', '', text).strip()
            text = re.sub(r'\s{2,}', ' ', text)

        # Ensure CTA is present for blaster content
        if cta and cta.lower() not in text.lower():
            # Try to fit CTA
            if len(text) + len(cta) + 2 <= self.config.max_tweet_length:
                text = f"{text} {cta}"
            else:
                # Truncate text to fit CTA
                max_text = self.config.max_tweet_length - len(cta) - 2
                if max_text > 0:
                    text = text[:max_text].rsplit(' ', 1)[0] + f" {cta}"
                else:
                    text = cta

        # Enforce character limit
        if len(text) > self.config.max_tweet_length:
            if cta and cta.lower() in text.lower():
                # CTA is in the text — truncate body, preserve CTA
                max_text = self.config.max_tweet_length - len(cta) - 2
                if max_text > 0:
                    text = text[:max_text].rsplit(' ', 1)[0] + f" {cta}"
                else:
                    text = cta
            else:
                text = text[:self.config.max_tweet_length - 3].rsplit(' ', 1)[0] + "..."

        return text

    def get_stats(self) -> Dict:
        """Get campaign engine statistics."""
        return {
            "evidence": self.evidence.get_stats(),
            "variator": self.variator.get_stats(),
            "config": {
                "cta": self.config.cta_url,
                "max_tweet_length": self.config.max_tweet_length,
                "deepseek_first": self.config.deepseek_first,
            },
        }
