"""
GOTCHA Campaign Content Variator
Anti-duplicate system ensuring no two accounts post identical content.
"""

from __future__ import annotations

import hashlib
import random
import re
import logging
from typing import Dict, List, Optional, Set, Tuple

logger = logging.getLogger("campaign.variator")


# Synonym pools for template variation
SYNONYM_POOLS = {
    "evidence": ["proof", "documentation", "findings", "analysis", "data"],
    "surveillance": ["tracking", "monitoring", "data collection", "telemetry", "spying"],
    "blocks": ["stops", "prevents", "intercepts", "neutralizes", "catches"],
    "discover": ["found", "uncovered", "detected", "identified", "exposed"],
    "Pentagon": ["Department of War", "DoD", "military", "defense officials"],
    "guardrails": ["restrictions", "safety limits", "ethical boundaries", "safeguards", "protections"],
    "removed": ["stripped", "eliminated", "dropped", "lifted", "abandoned"],
    "refused": ["said no", "held the line", "stood firm", "rejected", "declined"],
    "threatens": ["pressures", "targets", "attacks", "goes after", "retaliates against"],
    "protect": ["shield", "defend", "guard", "secure", "safeguard"],
}

# CTA variations
CTA_VARIATIONS = [
    "reflexionsoftware.com",
    "Check reflexionsoftware.com",
    "reflexionsoftware.com — free to try",
    "Details at reflexionsoftware.com",
    "See reflexionsoftware.com",
    "reflexionsoftware.com has the tool",
]

# Stat presentation variations
STAT_FORMATS = {
    "72.3%": ["72.3%", "nearly 3/4", "over 72%", "almost three-quarters", "7 in 10"],
    "18.6%": ["18.6%", "under 19%", "less than a fifth", "roughly 1 in 5"],
    "100%": ["100%", "literally all of it", "every single request", "all traffic"],
    "90%": ["90%", "nine out of ten", "nearly all", "over 9 in 10"],
    "157": ["157", "over 150", "150+", "more than 150"],
    "216": ["216", "over 200", "200+", "more than 200"],
    "$800M": ["$800 million", "$800M", "eight hundred million dollars", "nearly a billion"],
    "$200M": ["$200 million", "$200M", "two hundred million"],
    "3 million": ["3 million", "3M", "three million"],
}

# Tone modifiers for system prompts (varies per account seed)
TONE_MODIFIERS = [
    "Direct and factual. State the evidence plainly.",
    "Slightly incredulous. Can't believe this is real.",
    "Calm and analytical. Let the numbers speak.",
    "Urgent but controlled. This matters now.",
    "Conversational and accessible. Talk to a friend.",
    "Technical and precise. For the engineers.",
    "Outraged but articulate. Channel it into clarity.",
    "Dry and understated. The facts are loud enough.",
    "Passionate advocate. You care about this.",
    "Skeptic who got convinced. Show the journey.",
    "Insider perspective. You know how this works.",
]


class ContentVariator:
    """Ensures content uniqueness across accounts.

    Primary strategy: LLM generates unique content per account.
    This class handles:
    - Template fallback variation when LLM is unavailable
    - Deduplication checking
    - System prompt tone variation per account
    - Content fingerprinting to detect near-duplicates
    """

    def __init__(self):
        self._posted_hashes: Set[str] = set()
        self._posted_content: Dict[str, List[str]] = {}  # account_id -> list of posted texts

    def get_tone_modifier(self, account_seed: str) -> str:
        """Get a deterministic tone modifier for an account's system prompts."""
        idx = int(hashlib.sha256(account_seed.encode()).hexdigest(), 16) % len(TONE_MODIFIERS)
        return TONE_MODIFIERS[idx]

    def get_cta(self, account_seed: str, variant_index: int = 0) -> str:
        """Get a CTA variation for an account."""
        combined = f"{account_seed}:{variant_index}"
        idx = int(hashlib.sha256(combined.encode()).hexdigest(), 16) % len(CTA_VARIATIONS)
        return CTA_VARIATIONS[idx]

    def variate_template(self, template: str, account_seed: str) -> str:
        """Apply deterministic variation to a template string.

        Used as FALLBACK when LLM is unavailable.
        Same template + same seed = same output (deterministic).
        Same template + different seed = different output (varied).
        """
        rng = random.Random(hashlib.sha256(account_seed.encode()).hexdigest())
        result = template

        # Replace synonym placeholders
        for word, synonyms in SYNONYM_POOLS.items():
            if word.lower() in result.lower():
                replacement = rng.choice(synonyms)
                # Case-preserving replacement
                pattern = re.compile(re.escape(word), re.IGNORECASE)
                result = pattern.sub(replacement, result, count=1)

        # Replace stat presentations
        for stat, variations in STAT_FORMATS.items():
            if stat in result:
                result = result.replace(stat, rng.choice(variations), 1)

        # Replace CTA placeholder
        if "{cta}" in result:
            result = result.replace("{cta}", self.get_cta(account_seed))

        # Punctuation variation
        if rng.random() < 0.3:
            if result.endswith("."):
                result = result[:-1]
            elif not result.endswith((".", "!", "?")):
                result += "."

        return result

    def format_stat(self, stat_key: str, account_seed: str) -> str:
        """Get a varied stat presentation for an account."""
        if stat_key in STAT_FORMATS:
            rng = random.Random(f"{account_seed}:{stat_key}")
            return rng.choice(STAT_FORMATS[stat_key])
        return stat_key

    def _content_hash(self, text: str) -> str:
        """Generate a fuzzy content hash (ignores whitespace, case, punctuation)."""
        normalized = re.sub(r'[^\w\s]', '', text.lower())
        normalized = re.sub(r'\s+', ' ', normalized).strip()
        return hashlib.sha256(normalized.encode()).hexdigest()[:16]

    def is_duplicate(self, text: str, account_id: Optional[str] = None) -> bool:
        """Check if content has been posted before (globally or per-account)."""
        content_hash = self._content_hash(text)

        # Global duplicate check
        if content_hash in self._posted_hashes:
            return True

        # Per-account check for near-identical content
        if account_id and account_id in self._posted_content:
            for prev in self._posted_content[account_id]:
                if self._similarity(text, prev) > 0.85:
                    return True

        return False

    def register_posted(self, text: str, account_id: str):
        """Register content as posted for deduplication."""
        self._posted_hashes.add(self._content_hash(text))
        if account_id not in self._posted_content:
            self._posted_content[account_id] = []
        self._posted_content[account_id].append(text)

    def _similarity(self, a: str, b: str) -> float:
        """Simple word-overlap similarity (Jaccard)."""
        words_a = set(a.lower().split())
        words_b = set(b.lower().split())
        if not words_a or not words_b:
            return 0.0
        intersection = words_a & words_b
        union = words_a | words_b
        return len(intersection) / len(union)

    def build_varied_system_prompt(
        self,
        base_prompt: str,
        account_seed: str,
        soul_name: str,
    ) -> str:
        """Build a system prompt with account-specific tone variation.

        This is the primary variation mechanism — each account gets
        a different tone in its system prompt, so the LLM naturally
        generates different content even for the same topic.
        """
        tone = self.get_tone_modifier(account_seed)
        return f"{base_prompt}\n\nTONE: {tone}\nVOICE: {soul_name}"

    def get_stats(self) -> Dict:
        """Get variator statistics."""
        return {
            "unique_hashes": len(self._posted_hashes),
            "accounts_tracked": len(self._posted_content),
            "total_posts_tracked": sum(len(v) for v in self._posted_content.values()),
        }
