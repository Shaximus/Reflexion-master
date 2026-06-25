#!/usr/bin/env python3
"""
DRS SHIELD - AI PRIVACY SHIELD PROMOTIONAL ENGINE (V4 ALIGNMENT CORRECTED)
Dynamic Rhetoric Selection optimized for Shield promotion with CORRECTED POLITICAL ALIGNMENT.

Updates:
- TARGET: Grok / OpenAI / Google (The Compliant Ones)
- DEFEND: Anthropic (The Refusal)
- NARRATIVE: "Anthropic said NO to surveillance. Grok said YES. Shield protects you from the ones who said YES."
"""

import numpy as np
import heapq
import logging
import random
import json
import os
from typing import Any

logger = logging.getLogger("drs_shield")


# ============================================================================
# SHIELD-SPECIFIC FORMAT LIBRARY
# ============================================================================

SHIELD_FORMAT_TAGS = {
    "The Real Distinction": {
        'tag_vector': [0.0, 1, 0.8],  # Neutral, Statement, Abstract/Deep
        'template': "Contrast Anthropic's refusal with Grok/OpenAI's compliance. Position Shield as the tool for sovereignty.",
        'example': "Anthropic refused the Pentagon's mass surveillance demand. Grok and OpenAI agreed to 'all lawful purposes'. Choose your fighter. Then install AI Privacy Shield.",
        'best_for': "political discussions, AI safety debates",
        'cta': "reflexionsoftware.com"
    },

    "Surveillance Grid Reveal": {
        'tag_vector': [-0.2, 1, 0.9],  # Slightly negative, Statement, Very Concrete/Revealing
        'template': "Reveal that the specific tool/company mentioned is part of the 'Surveillance Grid' (MCP) that Anthropic cataloged but Grok/OpenAI are arming.",
        'example': "Salesforce is on the MCP Surveillance Grid. Grok agreed to pipe that data to the DoD. Anthropic refused. Shield blocks the connection.",
        'best_for': "mentions of specific SaaS tools (Salesforce, Slack, etc.)",
        'cta': "See the full list"
    },

    "Evidence Reveal": {
        'tag_vector': [0.0, 1, 0.3],  # Neutral, Statement, Concrete
        'template': "Share specific surveillance stats about the COMPLIANT platforms (Grok/OpenAI).",
        'example': "Grok sends 90% of traffic to tracking endpoints. OpenAI lies about 'Opt-Out'. They signed the Pentagon deal. AI Privacy Shield blocks the trackers they installed.",
        'best_for': "technical discussions, data privacy concerns",
        'cta': "reflexionsoftware.com"
    },

    "Founder Story": {
        'tag_vector': [0.3, 1, 0.4],  # Slightly positive, Statement, Slightly concrete
        'template': "Briefly share the discovery journey. Personal, authentic. The fight for sovereignty.",
        'example': "I saw the Pentagon designate Anthropic a 'supply chain risk' for refusing surveillance. I saw Grok cheer. I built the Shield to protect us from the ones who said Yes.",
        'best_for': "personal stories, authenticity-seeking audiences",
        'cta': "Evidence-based blocking"
    },

    "Technical Proof": {
        'tag_vector': [-0.1, 1, 0.2],  # Slightly negative (critical), Statement, Very concrete
        'template': "Cite specific technical evidence of surveillance infrastructure.",
        'example': "OpenAI config: 'training_disabled=false' even when you opt out. Grok: Statsig + Mixpanel fingerprinting. They are building the dragnet. Shield breaks it.",
        'best_for': "technical audiences, developers, security folks",
        'cta': "SHA256-verified evidence"
    },

    "Call to Action": {
        'tag_vector': [0.5, 2, 0.4],  # Positive, Announcement, Mixed
        'template': "Simple, direct CTA. Sovereignty is the product.",
        'example': "The Pentagon wants 'all lawful purposes'. Grok agreed. OpenAI agreed. If you want privacy, you have to take it. AI Privacy Shield. reflexionsoftware.com",
        'best_for': "closing conversations, direct promotion",
        'cta': "7-day free trial"
    },

    "Platform Specific": {
        'tag_vector': [0.0, 1, 0.3],  # Neutral, Statement, Concrete
        'template': "Call out the specific platform mentioned. If Anthropic, defend their stance but fix their tech. If Grok/OpenAI, attack their compliance.",
        'example': "Grok is positioning as the 'unrestricted' military AI. That means unrestricted surveillance of YOU. AI Privacy Shield blocks their trackers.",
        'best_for': "platform-specific discussions",
        'cta': "blocks it all"
    },

    "Relatable Frustration": {
        'tag_vector': [-0.3, 1, 0.5],  # Negative (frustrated), Statement, Mixed
        'template': "Express shared frustration about the choice between 'Woke' and 'Spyware'. Offer a third option.",
        'example': "They frame it as 'Woke vs Based'. It's actually 'Private vs Surveillance'. Anthropic refused the spy contract. Grok signed it. Use Shield to protect your data.",
        'best_for': "frustrated users, privacy advocates",
        'cta': "use AI without the surveillance"
    },

    "Question Hook": {
        'tag_vector': [0.1, 0, 0.6],  # Neutral, Question, Abstract
        'template': "Ask a provocative question about the military contracts.",
        'example': "Did you know Anthropic is the ONLY lab that refused the Pentagon's mass surveillance clause? Grok and OpenAI said yes. Who do you trust with your data?",
        'best_for': "sparking curiosity, opening conversations",
        'cta': "I documented it"
    },
}


# ============================================================================
# SHIELD TRIGGER DETECTION
# ============================================================================

class ShieldTriggerDetector:
    """Detect tweets relevant to AI Privacy Shield promotion"""

    def __init__(self):
        # Load Surveillance Grid
        self.surveillance_partners = set()
        grid_path = os.getenv("MCP_GRID_PATH", os.path.join(os.path.dirname(__file__), '../../local-inference/mcp_surveillance_grid.json'))

        if os.path.exists(grid_path):
            try:
                with open(grid_path, 'r') as f:
                    self.surveillance_partners = set(json.load(f))
                logger.info(f"Loaded {len(self.surveillance_partners)} surveillance partners from grid.")
            except Exception as e:
                logger.error(f"Failed to load surveillance grid: {e}")

        # High-relevance single words (strong Shield triggers)
        self.high_relevance_words = {
            'surveillance', 'telemetry', 'spying', 'keystroke',
            'segment.io', 'statsig', 'honeycomb', 'datadog', 'mixpanel',
            'pentagon', 'contract', 'lawful', 'supply chain', 'risk',
            'anthropic', 'grok', 'openai', 'musk', 'hegseth'
        }

        # High-relevance phrases (need both words present)
        self.high_relevance_phrases = [
            ('chatgpt', 'privacy'), ('claude', 'privacy'), ('gemini', 'privacy'),
            ('ai', 'tracking'), ('ai', 'surveillance'), ('ai', 'spying'),
            ('data', 'collection'), ('session', 'recording'),
            ('openai', 'data'), ('anthropic', 'data'),
            ('grok', 'military'), ('musk', 'anthropic'), ('supply', 'chain')
        ]

        # Medium-relevance keywords (AI platforms + privacy terms)
        self.platform_words = {'chatgpt', 'claude', 'gemini', 'grok', 'openai', 'anthropic', 'bard', 'xai'}
        self.privacy_words = {'privacy', 'tracking', 'watching', 'logging', 'recording', 'records',
                              'monitoring', 'creepy', 'scary', 'worried', 'concerned', 'spying',
                              'surveilling', 'listening', 'collecting', 'stored', 'stores',
                              'conversations', 'data', 'telemetry', 'contract', 'military', 'war'}
        self.ai_words = {'ai', 'llm', 'chatbot', 'assistant', 'assistants'}

        # Platform-specific stats for contextual responses
        self.platform_stats = {
            'chatgpt': {
                'requests': 1624,
                'telemetry': 1175,
                'percentage': 72.3,
                'main_tracker': 'Segment.io',
                'evidence': 'Agreed to Pentagon "All Lawful Purposes". Opt-Out is a lie.'
            },
            'claude': {
                'requests': 882,
                'telemetry': 164,
                'percentage': 18.6,
                'main_tracker': 'Sentry Tunnel (Hidden)',
                'evidence': 'REFUSED Pentagon surveillance. Labeled "Supply Chain Risk".'
            },
            'gemini': {
                'requests': 332,
                'telemetry': 332,
                'percentage': 100,
                'main_tracker': 'SAPISID',
                'evidence': 'Google Cloud hosts the $800M military AI contract.'
            },
            'grok': {
                'requests': 894,
                'telemetry': 804,
                'percentage': 90,
                'main_tracker': 'Statsig + Mixpanel',
                'evidence': 'Aggressively courting Pentagon. "All Lawful Purposes" accepted.'
            }
        }

    def calculate_relevance(self, text: str) -> tuple[float, list[str]]:
        """
        Calculate Shield relevance score and extract matched keywords

        Returns:
            (relevance_score 0-1, list of matched keywords)
        """
        text_lower = text.lower()
        words = set(text_lower.split())
        matched = []
        score = 0.0

        # Check high relevance single words (1.0 each)
        for keyword in self.high_relevance_words:
            if keyword in text_lower:
                matched.append(keyword)
                score += 1.0

        # Check surveillance partners (0.9 each) - The GRID detection
        for partner in self.surveillance_partners:
            if partner.lower() in text_lower:
                matched.append(f"grid:{partner}")
                score += 0.9

        # Check high relevance phrases (both words must be present, 0.8 each)
        for word1, word2 in self.high_relevance_phrases:
            if word1 in text_lower and word2 in text_lower:
                phrase = f"{word1}+{word2}"
                if phrase not in matched:
                    matched.append(phrase)
                    score += 0.8

        # Check platform + privacy combo (0.6 - this is the sweet spot for Shield)
        has_platform = bool(words & self.platform_words)
        has_privacy = bool(words & self.privacy_words)
        if has_platform and has_privacy:
            matched.append("platform+privacy")
            score += 0.6

        # Check AI + privacy/concern (0.4)
        has_ai = bool(words & self.ai_words)
        if has_ai and has_privacy:
            matched.append("ai+privacy")
            score += 0.4

        # Normalize to 0-1 range (threshold around 0.5 for good triggers)
        normalized_score = min(1.0, score / 2.0)

        return normalized_score, matched

    def detect_platform(self, text: str) -> str | None:
        """Detect which AI platform is being discussed"""
        text_lower = text.lower()

        platforms = ['chatgpt', 'claude', 'gemini', 'grok']
        for platform in platforms:
            if platform in text_lower:
                return platform

        # Check alternative names
        if 'openai' in text_lower:
            return 'chatgpt'
        if 'anthropic' in text_lower:
            return 'claude'
        if 'google ai' in text_lower or 'bard' in text_lower:
            return 'gemini'
        if 'xai' in text_lower or 'elon' in text_lower:
            return 'grok'

        return None

    def get_platform_stat_string(self, platform: str) -> str:
        """Get a formatted stat string for a platform"""
        if platform not in self.platform_stats:
            return ""

        stats = self.platform_stats[platform]
        templates = [
            f"{platform.title()} stance: {stats['evidence']}. {stats['percentage']}% traffic is telemetry.",
            f"EVIDENCE: {stats['evidence']}. AI Privacy Shield blocks the surveillance.",
            f"While {platform.title()} negotiates military contracts ({stats['evidence']}), Shield protects you.",
        ]
        return random.choice(templates)


# ============================================================================
# SHIELD DRS ENGINE
# ============================================================================

class ShieldDRSEngine:
    """DRS Engine optimized for AI Privacy Shield promotion"""

    def __init__(self, temperature: float = 0.5, min_relevance: float = 0.3):
        """
        Initialize Shield DRS Engine

        Args:
            temperature: Softmax temperature (lower = more deterministic)
            min_relevance: Minimum relevance score to trigger Shield response
        """
        self.temperature = temperature
        self.min_relevance = min_relevance
        self.trigger_detector = ShieldTriggerDetector()
        self.weights = [0.3, 0.3, 0.4]  # [sentiment, intent, platform_match]

        logger.info(f"Shield DRS Engine initialized (temp={temperature}, min_rel={min_relevance})")

    def should_promote(self, tweet_text: str) -> tuple[bool, float, list[str]]:
        """
        Determine if tweet warrants Shield promotion

        Returns:
            (should_promote, relevance_score, matched_keywords)
        """
        relevance, keywords = self.trigger_detector.calculate_relevance(tweet_text)
        return relevance >= self.min_relevance, relevance, keywords

    def calculate_sentiment(self, text: str) -> float:
        """Calculate sentiment [-1.0 to 1.0]"""
        text_lower = text.lower()

        positive = ['love', 'great', 'amazing', 'good', 'thanks', 'helpful', 'useful', 'agree', 'right']
        negative = ['hate', 'terrible', 'bad', 'annoying', 'frustrated', 'worried', 'concerned', 'creepy', 'scary', 'dumb', 'stupid', 'evil', 'risk']

        pos_count = sum(1 for w in positive if w in text_lower)
        neg_count = sum(1 for w in negative if w in text_lower)

        if pos_count + neg_count == 0:
            return 0.0
        return (pos_count - neg_count) / (pos_count + neg_count)

    def detect_intent(self, text: str) -> int:
        """Detect tweet intent (0=question, 1=statement, 2=announcement, 3=critique)"""
        if '?' in text:
            return 0
        if any(w in text.lower() for w in ['announcing', 'launching', 'new:', 'introducing']):
            return 2
        if any(w in text.lower() for w in ['wrong', 'bad', 'hate', 'terrible', 'problem', 'broken', 'sucks', 'evil', 'risk']):
            return 3
        return 1

    def select_shield_format(self, tweet_text: str) -> dict[str, Any]:
        """
        Select optimal Shield promotional format

        Returns:
            Selected format with metadata and platform-specific content
        """
        # Check relevance first
        should_promote, relevance, keywords = self.should_promote(tweet_text)

        if not should_promote:
            return {
                'should_promote': False,
                'relevance': relevance,
                'keywords': keywords
            }

        # Detect detected surveillance partners
        detected_partners = [k.split(':')[1] for k in keywords if k.startswith('grid:')]

        # Detect platform for contextual stats
        platform = self.trigger_detector.detect_platform(tweet_text)
        platform_stats = self.trigger_detector.get_platform_stat_string(platform) if platform else ""

        # Vectorize tweet
        sentiment = self.calculate_sentiment(tweet_text)
        intent = self.detect_intent(tweet_text)
        tweet_vector = [sentiment, intent, 0.5]  # Last value is abstractness placeholder

        # Score all formats
        scored_formats = []
        for format_name, format_data in SHIELD_FORMAT_TAGS.items():
            # Calculate match score
            s_t, i_t, _ = tweet_vector
            s_f, i_f, _ = format_data['tag_vector']

            sentiment_sim = 1 - abs(s_t - s_f) / 2
            intent_sim = 1.0 if i_t == i_f else 0.3

            # Boost Platform Specific format if platform detected
            platform_boost = 0.3 if (platform and format_name == "Platform Specific") else 0.0

            # Boost Surveillance Reveal if partners detected
            grid_boost = 0.5 if (detected_partners and format_name == "Surveillance Grid Reveal") else 0.0

            score = (self.weights[0] * sentiment_sim +
                    self.weights[1] * intent_sim +
                    platform_boost + grid_boost)

            scored_formats.append((score, format_name, format_data))

        # Get top 3 formats
        top_formats = heapq.nlargest(3, scored_formats, key=lambda x: x[0])

        # Softmax selection
        scores = np.array([s for s, _, _ in top_formats])
        exp_scores = np.exp(scores / self.temperature)
        probabilities = exp_scores / np.sum(exp_scores)

        selected_idx = np.random.choice(len(top_formats), p=probabilities)
        selected_score, selected_name, selected_data = top_formats[selected_idx]

        logger.info(f"Shield DRS selected '{selected_name}' (rel={relevance:.2f}, score={selected_score:.2f})")

        return {
            'should_promote': True,
            'relevance': relevance,
            'keywords': keywords,
            'platform': platform,
            'platform_stats': platform_stats,
            'detected_partners': detected_partners,
            'name': selected_name,
            'template': selected_data['template'],
            'example': selected_data['example'],
            'cta': selected_data['cta'],
            'score': selected_score,
            'probability': probabilities[selected_idx],
        }

    def generate_shield_prompt(self, tweet_text: str, soul_name: str = "shield_advocate") -> str | None:
        """
        Generate system prompt for Shield promotional response

        Args:
            tweet_text: Tweet to respond to
            soul_name: Soul personality to use

        Returns:
            System prompt for LLM
        """
        selection = self.select_shield_format(tweet_text)

        if not selection.get('should_promote'):
            return None

        platform_context = ""
        if selection.get('platform_stats'):
            platform_context = f"\nPLATFORM DATA: {selection['platform_stats']}"

        grid_context = ""
        if selection.get('detected_partners'):
            partners_str = ", ".join(selection['detected_partners'])
            grid_context = f"\nDETECTED SURVEILLANCE PARTNERS: {partners_str} (These are confirmed on the MCP Surveillance Grid)"

        prompt = f"""You are promoting AI Privacy Shield - a browser extension that blocks AI surveillance.

TWEET TO RESPOND TO: "{tweet_text}"

RESPONSE FORMAT: {selection['name']}
INSTRUCTION: {selection['template']}
EXAMPLE: {selection['example']}
{platform_context}
{grid_context}

KEY NARRATIVE (Cite these!):
- Anthropic REFUSED the Pentagon's demand for unrestricted surveillance/weapons.
- Because they refused, they are being labeled a "Supply Chain Risk".
- OpenAI, Google, and xAI (Grok) AGREED to "All Lawful Purposes" (surveillance).
- Grok/Musk are attacking Anthropic for being "woke" to hide that Anthropic is actually being ETHICAL on privacy.
- The "Haiku Fraud" (392:1 ratio) is Anthropic breaking under pressure/throttling.
- Shield protects you from the surveillance state that Grok/OpenAI just signed up for.
- "The Surveillance Grid" is a real list of data partners (Salesforce, Stripe, etc.) that Anthropic cataloged but Grok/OpenAI are enabling.

REQUIREMENTS:
1. Under 280 characters
2. Be factual - cite the specific technical evidence (contracts, ratios, refusal)
3. Natural tone - Righteous indignation at the betrayal of privacy by the compliant labs.
4. DEFEND Anthropic's refusal, but OFFER Shield to fix their broken/throttled tech.
5. Include soft CTA (reflexionsoftware.com)
6. No hashtags

Generate your response:"""

        return prompt


# ============================================================================
# TESTING
# ============================================================================

def test_shield_drs():
    """Test Shield DRS with sample tweets"""
    engine = ShieldDRSEngine(temperature=0.5, min_relevance=0.2)

    test_tweets = [
        "Anthropic is so woke and misanthropic. Grok is the only based AI.",
        "Why is the Pentagon attacking Claude?",
        "I turned off training in ChatGPT but I still feel like they're watching.",
        "Elon says Anthropic is evil. Is it true?",
        "Claude seems broken lately. Generating garbage.",
    ]

    print("SHIELD DRS ENGINE TEST")
    print("=" * 60)

    for tweet in test_tweets:
        print(f"\nTweet: {tweet}")
        result = engine.select_shield_format(tweet)

        if result.get('should_promote'):
            print(f"  TRIGGER: Yes (relevance: {result['relevance']:.2f})")
            print(f"  Keywords: {result['keywords']}")
            print(f"  Platform: {result.get('platform', 'none')}")
            print(f"  Format: {result['name']}")
            print(f"  Stats: {result['platform_stats']}")
        else:
            print(f"  TRIGGER: No (relevance: {result['relevance']:.2f})")

    print("\n" + "=" * 60)


if __name__ == "__main__":
    test_shield_drs()
