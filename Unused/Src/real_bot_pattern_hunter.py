#!/usr/bin/env python3
"""
BOT PATTERN HUNTER - BASED ON GROK'S ACTUAL RESEARCH
Real patterns from 2024-2025 bot farms on X/Twitter
80% of Elon fakes use these patterns according to FTC data
"""

import re
from typing import List, Dict, Set, Tuple, Optional
from datetime import datetime
import hashlib
import logging

logger = logging.getLogger("bot_pattern_hunter")


class RealBotPatternHunter:
    """Pattern hunter based on Grok's 2024-2025 research"""

    def __init__(self):
        # REAL PATTERNS FROM GROK'S RESEARCH

        # 80% of Elon fakes use base + numbers
        self.high_prevalence_patterns = {
            "base_numbers": {
                "regex": r"(.+?)(\d{3,8})$",
                "examples": ["elonmusk123", "elonx0648", "CEO7914"],
                "prevalence": 0.80,
                "description": "Base name + random/sequential digits",
            },
            "company_prefix": {
                "regex": r"(tesla|spacex|xai|neuralink)_(.+)",
                "examples": ["tesla_elon", "spacex_ceo", "xai_musk"],
                "prevalence": 0.60,
                "description": "Company name prefix mimicking roles",
            },
        }

        # Medium prevalence patterns
        self.medium_prevalence_patterns = {
            "private_fan_suffix": {
                "suffixes": ["_private", "_fanpage", "_official", "_real", "_support"],
                "examples": ["elonmusk_private", "elonmuskfanpage"],
                "description": "Claims official/private status",
            },
            "crypto_giveaway": {
                "keywords": ["giveaway", "crypto", "airdrop", "btc", "eth", "doge"],
                "examples": ["elonmusk_giveaway", "muskcrypto", "elonxcat"],
                "description": "Crypto scam indicators",
            },
        }

        # Unicode obfuscation (20% increase in 2024 per Akamai)
        self.unicode_substitutions = {
            # Cyrillic lookalikes
            "e": ["е", "ё"],  # Cyrillic e
            "o": ["о", "ο"],  # Cyrillic/Greek o
            "a": ["а", "α"],  # Cyrillic/Greek a
            "p": ["р"],  # Cyrillic r looks like p
            "c": ["с"],  # Cyrillic s looks like c
            "x": ["х"],  # Cyrillic h looks like x
            "y": ["у"],  # Cyrillic u looks like y
            "k": ["к"],  # Cyrillic k
            "n": ["п"],  # Cyrillic p looks like n
            "m": ["м"],  # Cyrillic m
            "t": ["т"],  # Cyrillic t
            "s": ["ş", "š"],  # Dotted s variants
            "u": ["ü", "ù"],  # Accented u
        }

        # Batch creation patterns (from DataDome/BlackHat research)
        self.batch_patterns = {
            "user_random": r"User\d{7,10}",  # User8473629
            "sequential": r"(.+?)(\d{3,4})$",  # botfarm001-100
            "random_jumble": r"[A-Z][a-z]+[A-Z][a-z]+\d{4,8}",  # JamesSmith9739
            "aged_hijack_indicators": {
                "creation_before": 2020,
                "dormant_period": 365,  # days
                "sudden_activity": True,
            },
        }

        # Network naming tactics (45-55% bot activity on Musk posts)
        self.network_patterns = {
            "incremental": lambda base, start, count: [
                f"{base}{i:03d}" for i in range(start, start + count)
            ],
            "random_cluster": lambda base, count: [
                f"{base}{hash(i)%10000:04d}" for i in range(count)
            ],
            "support_variants": lambda name: [
                f"{name}_support",
                f"{name}_help",
                f"{name}_team",
                f"{name}_hq",
            ],
        }

    def generate_hunt_list(self, seed: str, limit: int = 100) -> List[Dict[str, any]]:
        """Generate prioritized list of usernames to check based on research"""

        results = []
        seed_clean = seed.replace("@", "").strip()

        # Extract base pattern from seed
        base_match = re.match(r"(.+?)([_\-])?(\d*)$", seed_clean)
        if base_match:
            base_name = base_match.group(1)
            separator = base_match.group(2) or ""
            base_num = int(base_match.group(3)) if base_match.group(3) else 0
        else:
            base_name = seed_clean
            separator = ""
            base_num = 0

        # PRIORITY 1: High prevalence patterns (80% of fakes)
        logger.info(
            "🎯 Generating HIGH PREVALENCE patterns (80% of Elon fakes use these)"
        )

        # Base + Numbers (most common)
        for i in range(min(limit // 2, 50)):
            # Sequential from seed
            if base_num > 0:
                num = base_num + i
                results.append(
                    {
                        "username": f"{base_name}{separator}{num:04d}",
                        "pattern": "base_numbers_sequential",
                        "confidence": 0.80,
                        "source": "FTC data: 80% prevalence",
                    }
                )

            # Common number patterns
            results.append(
                {
                    "username": f"{base_name}{i:03d}",
                    "pattern": "base_numbers_3digit",
                    "confidence": 0.75,
                    "source": "Common bot pattern",
                }
            )

            # X-number pattern (like elonx0648)
            results.append(
                {
                    "username": f"{base_name}_x{i:04d}",
                    "pattern": "x_number_pattern",
                    "confidence": 0.70,
                    "source": "@elonx0648 confirmed bot",
                }
            )

        # PRIORITY 2: Company prefixes (high prevalence)
        companies = ["tesla", "spacex", "xai", "neuralink", "boring"]
        for company in companies[:3]:
            results.append(
                {
                    "username": f"{company}_{base_name}",
                    "pattern": "company_prefix",
                    "confidence": 0.60,
                    "source": "Deepfake scam pattern",
                }
            )
            results.append(
                {
                    "username": f"{company}{base_name}",
                    "pattern": "company_prefix_direct",
                    "confidence": 0.55,
                    "source": "Company mimic pattern",
                }
            )

        # PRIORITY 3: Private/Fan suffixes (medium prevalence)
        for suffix in ["_private", "_official", "_real", "fanpage"]:
            results.append(
                {
                    "username": f"{base_name}{suffix}",
                    "pattern": "authority_suffix",
                    "confidence": 0.50,
                    "source": "Parody evasion tactic",
                }
            )

        # PRIORITY 4: Crypto scam patterns
        for crypto_suffix in ["_giveaway", "crypto", "_btc", "_eth"]:
            results.append(
                {
                    "username": f"{base_name}{crypto_suffix}",
                    "pattern": "crypto_scam",
                    "confidence": 0.45,
                    "source": "Kaspersky: $12B+ in scams",
                }
            )

        # PRIORITY 5: Unicode obfuscation (rising 20% in 2024)
        logger.info("🔤 Adding Unicode obfuscation variants (20% increase in 2024)")
        unicode_variants = self._generate_unicode_variants(base_name, 10)
        for variant in unicode_variants:
            results.append(
                {
                    "username": variant,
                    "pattern": "unicode_obfuscation",
                    "confidence": 0.40,
                    "source": "Akamai: 20% increase 2024",
                }
            )

        # PRIORITY 6: Batch patterns (bot farms)
        batch_results = []
        for i in range(5):
            batch_results.append(
                {
                    "username": f"{base_name[:4] if len(base_name) >= 4 else base_name}{base_name[-4:] if len(base_name) >= 4 else ''}{i:04d}",
                    "pattern": "batch_jumble",
                    "confidence": 0.30,
                    "source": "BlackHat forum pattern",
                }
            )
        results.extend(batch_results)

        results.append(
            {
                "username": f"User{abs(hash(base_name))%10000000:07d}",
                "pattern": "batch_user_random",
                "confidence": 0.35,
                "source": "DataDome bot farm pattern",
            }
        )

        # Sort by confidence and limit
        results.sort(key=lambda x: x["confidence"], reverse=True)

        logger.info(f"📊 Generated {len(results[:limit])} targets:")
        high_conf = len([r for r in results[:limit] if r["confidence"] > 0.7])
        med_conf = len([r for r in results[:limit] if 0.4 <= r["confidence"] <= 0.7])
        low_conf = len([r for r in results[:limit] if r["confidence"] < 0.4])
        logger.info(f"  • High confidence (>0.7): {high_conf}")
        logger.info(f"  • Medium confidence (0.4-0.7): {med_conf}")
        logger.info(f"  • Low confidence (<0.4): {low_conf}")

        return results[:limit]

    def _generate_unicode_variants(self, text: str, limit: int = 5) -> List[str]:
        """Generate Unicode obfuscation variants"""
        variants = []
        text_lower = text.lower()

        # Generate different combinations
        for char, replacements in self.unicode_substitutions.items():
            if char in text_lower:
                for replacement in replacements[:2]:  # Max 2 per char
                    variant = text_lower.replace(
                        char, replacement, 1
                    )  # Replace only first occurrence
                    if variant not in variants:
                        variants.append(variant)
                        if len(variants) >= limit:
                            return variants

        return variants

    def analyze_pattern_match(self, username: str) -> Dict[str, any]:
        """Analyze which bot pattern a username matches"""

        analysis = {
            "username": username,
            "matched_patterns": [],
            "risk_score": 0.0,
            "evidence": [],
        }

        # Check high prevalence patterns
        if re.match(r".+\d{3,8}$", username):
            analysis["matched_patterns"].append("base_numbers")
            analysis["risk_score"] += 0.80
            analysis["evidence"].append("Matches 80% prevalence number pattern")

        # Check company prefixes
        if any(company in username.lower() for company in ["tesla", "spacex", "xai"]):
            analysis["matched_patterns"].append("company_mimic")
            analysis["risk_score"] += 0.60
            analysis["evidence"].append("Contains company name (deepfake indicator)")

        # Check crypto indicators
        crypto_terms = ["giveaway", "crypto", "btc", "eth", "airdrop"]
        if any(term in username.lower() for term in crypto_terms):
            analysis["matched_patterns"].append("crypto_scam")
            analysis["risk_score"] += 0.50
            analysis["evidence"].append("Contains crypto scam keywords")

        # Check for Unicode
        for char in username:
            if ord(char) > 127:  # Non-ASCII
                analysis["matched_patterns"].append("unicode_obfuscation")
                analysis["risk_score"] += 0.40
                analysis["evidence"].append(
                    f"Contains Unicode char: {char} (U+{ord(char):04X})"
                )
                break

        # Check batch patterns
        if re.match(r"User\d{7,10}", username):
            analysis["matched_patterns"].append("batch_creation")
            analysis["risk_score"] += 0.35
            analysis["evidence"].append("Matches bot farm batch pattern")

        # Cap risk score at 1.0
        analysis["risk_score"] = min(analysis["risk_score"], 1.0)

        return analysis
