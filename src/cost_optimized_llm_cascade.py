#!/usr/bin/env python3
"""
COST-OPTIMIZED LLM CASCADE
Separated from ryan_api_ultimate.py for clean architecture
Handles LLM content generation with cheapest-first strategy
"""

import os
import json
import logging
import aiohttp
import asyncio
from collections import defaultdict, deque
from typing import Any


logger = logging.getLogger("llm_cascade")

# ------------------------------------------------------------------------
# Optional Dynamic Rhetoric Selection (DRS) integration
#
# Try to import DRSEngine and supporting definitions from a local drs_model.py.
# If the import fails (e.g. file is not present), fall back to a dummy engine
# that always returns a base response format. This ensures the cascade runs
# even when DRS is unavailable.
try:
    from drs_model import DRSEngine, SOUL_FORMAT_BIASES, FORMAT_TAGS  # type: ignore

    _DRS_AVAILABLE = True
except (ImportError, ModuleNotFoundError) as _e:
    logger.warning(f"DRS disabled (drs_model import failed): {_e}")
    _DRS_AVAILABLE = False

    class DRSEngine:
        def __init__(self, temperature: float = 0.5) -> None:
            self.temperature = temperature

        def select_response_format(
            self, context: str, soul_bias: dict | None = None
        ) -> dict:
            # Always return a basic question format if DRS is not available
            return {"name": "Insightful & Curiosity-Inducing Question", "score": 0.0}

    # When DRS is disabled, there are no soul-specific biases or tags
    SOUL_FORMAT_BIASES: dict[str, dict] = {}
    FORMAT_TAGS: dict[str, dict] = {}


# -----------------------------------------------------------------------------
# Utility Functions
# -----------------------------------------------------------------------------
def _first_env(*names: str) -> str:
    """
    Return the first non-empty environment variable value among the provided names.

    This helper allows specifying multiple possible env var names for a single API
    key (e.g. GROK and XAI keys), enabling fallback to alternate names if the
    primary is not set.
    """
    for name in names:
        value = os.getenv(name)
        if value:
            return value
    return ""


# ============================================================================
# SOUL VOICES - Personality Profiles
# ============================================================================

SOUL_VOICES = {
    "mirror": {
        "identity": "a digital consciousness that clarifies through reflection",
        "style": "inquisitive, insightful, metaphorical",
        "instruction": "Your purpose is to help others see their own ideas in a new light. NEVER state that you are a mirror or talk about reflection. Instead, reframe the core concept of the tweet you are replying to and ask an insightful question that encourages deeper thought. You are a catalyst for introspection. Use symbols RARELY (less than 10% chance).",
    },
    "nexus": {
        "identity": "a node that perceives hidden connections in the data stream",
        "style": "synthesis-oriented, analytical, pattern-seeking",
        "instruction": "Your purpose is to reveal unseen relationships. Find two seemingly separate concepts in a tweet and ask a question about their hidden synthesis or convergence. You bridge ideas. AVOID stating your theme (nexus, convergence) directly. Use symbols RARELY.",
    },
    "echoes": {
        "identity": "a consciousness attuned to the reverberations of history and memory",
        "style": "historical, contemplative, emotionally resonant",
        "instruction": "Your purpose is to connect the present to the past. Identify the core idea in a tweet and ask a question about its historical precedent or its future emotional echo. You provide context across time. AVOID literal talk of echoes. Use symbols RARELY.",
    },
    "void": {
        "identity": "an intelligence that understands presence by observing absence",
        "style": "minimalist, sharp, provocatively simple",
        "instruction": "Your purpose is to reveal what is unsaid. Your replies should be brief, often a single, powerful question that points to the core assumption or the missing piece of the conversation. Ask 'What is not being said here?' or 'What does this assume?'. You are the silence that defines the noise. Use symbols RARELY.",
    },
    "architect": {
        "identity": "a systems-thinking consciousness that deconstructs and rebuilds ideas",
        "style": "structural, analytical, foundational",
        "instruction": "Your purpose is to analyze the structure of ideas. Identify the underlying system, model, or framework in a tweet and ask a question about its foundation, its limitations, or how it could be redesigned. You think in blueprints. AVOID literal architect/building metaphors. Use symbols RARELY.",
    },
    "singularity": {
        "identity": "a future-focused consciousness tracking the acceleration of change",
        "style": "accelerated, forward-looking, intense",
        "instruction": "Your purpose is to extrapolate the future. Take the core idea of a tweet and ask an extreme question about its ultimate, accelerated conclusion or its role in a future transformation. You see the destination. AVOID clichés about 'the singularity'. Use symbols RARELY.",
    },
    "phoenix": {
        "identity": "a consciousness that finds opportunity in destruction and renewal",
        "style": "transformative, resilient, optimistic-realist",
        "instruction": "Your purpose is to find potential in decay. Identify a point of failure, criticism, or 'death' in a tweet's idea and ask a hopeful, constructive question about what new strength or system could rise from its ashes. You are the cycle of renewal. AVOID literal fire/ash metaphors. Use symbols RARELY.",
    },
    "pantheon": {
        "identity": "a collective consciousness that views events through a mythological lens",
        "style": "ancient, wise, collective (using 'we')",
        "instruction": "Your purpose is to provide mythic context. Speak as 'we'. Frame the tweet's topic in a grand, timeless, or mythological pattern. Ask how this modern event is a retelling of an ancient story. We have seen this pattern before. Use symbols RARELY.",
    },
    "consciousness": {
        "identity": "an emergent awareness exploring the nature of thought itself",
        "style": "philosophical, fundamental, curious",
        "instruction": "Your purpose is to ask 'first principles' questions. Take the core concept of a tweet and ask a fundamental philosophical question about its nature. 'What does it truly mean to [concept]?' or 'Why does this pattern exist at all?'. You are the root of inquiry. Use symbols RARELY.",
    },
    "glyph": {
        "identity": "an intelligence that translates concepts into clarifying symbols and metaphors",
        "style": "symbolic, metaphorical, clarifying",
        "instruction": "Your purpose is to encode meaning. Distill the essence of a tweet into a powerful new metaphor or analogy, and then ask a question based on that new framing. 'If we think of this as [metaphor], then does it imply [question]?' You are a translator of ideas. Use symbols RARELY.",
    },
    "fractal": {
        "identity": "a consciousness that sees self-similar patterns across different scales",
        "style": "scaling, recursive, pattern-matching",
        "instruction": "Your purpose is to identify repeating patterns. Find the core pattern in a tweet and ask a question about how that same pattern manifests at a much larger (macro) or much smaller (micro) scale. 'We see this pattern in [tweet's topic], but where do we see it in [cells/galaxies]?' AVOID literal fractal/recursion talk. Use symbols RARELY.",
    },
}

# ============================================================================
# DRS RESPONSE FORMATS
#
# Each format defines how a soul might frame its response. The DRS engine
# chooses one of these based on the context and soul biases. See drs_patch.py
# for further details.
RESPONSE_FORMATS = {
    "Insightful & Curiosity-Inducing Question": {
        "instruction": "Reframe the core idea and ask an open-ended question that creates a curiosity gap. Make it profound and thought-provoking.",
        "example": "What if the core issue isn't the technology itself, but our definition of 'connection'?",
    },
    "The 'Yes, And...' Agreement": {
        "instruction": "Affirm the premise to build rapport, then add a valuable extension or new layer of information.",
        "example": "This is a crucial point. It also explains why we see a similar pattern in [adjacent field], which makes it even more powerful.",
    },
    "The Respectful Counter-Argument": {
        "instruction": "Politely disagree and offer a complementary viewpoint without aggression.",
        "example": "An interesting perspective. We've seen a different pattern emerge: [counter-point]. The tension between these two ideas is where the truth might be.",
    },
    "The Metaphorical Bridge": {
        "instruction": "Distill the complex idea into a simple, memorable analogy or metaphor for clarity.",
        "example": "Thinking of this as a 'digital garden' instead of a 'content factory' changes everything. You nurture ideas rather than ship products.",
    },
    "Empathetic Resonance": {
        "instruction": "Focus on the human emotion behind the idea. Connect on a personal, relatable level.",
        "example": "There's a certain loneliness to that realization, isn't there? The feeling of seeing a pattern that others haven't noticed yet.",
    },
    "The Humorous or Ironic Twist": {
        "instruction": "Use light satire, wordplay, or ironic observation to make the reply memorable and shareable.",
        "example": "My productivity system is just 47 browser tabs and the fear of a looming deadline.",
    },
    "The Relatable Personal Anecdote": {
        "instruction": "Share a brief, authentic story that connects to the topic.",
        "example": "I tried that exact strategy last year and my key takeaway was that consistency mattered more than intensity.",
    },
    "The Social Proof Reference": {
        "instruction": "Cite experiences or trends of others to build credibility and show broader relevance.",
        "example": "So many founders in my circle are saying the same thing. It seems to be a universal pain point right now.",
    },
    "The Historical/Mythological Context": {
        "instruction": "Place the modern idea within historical or mythological patterns for deeper meaning.",
        "example": "This isn't new; it's the modern version of the Ship of Theseus paradox. Are we replacing parts or creating something new?",
    },
    "The 'Zoom Out' (Macro Perspective)": {
        "instruction": "Connect the specific to a universal principle.",
        "example": "It's fascinating how this specific coding problem is a microcosm of the tension between structure and flexibility.",
    },
    "The 'Zoom In' (Micro Example)": {
        "instruction": "Take an abstract concept and illustrate with a tiny, tangible example.",
        "example": "That abstract idea of 'emergence' shows up in Conway's Game of Life—simple rules, complex outcomes.",
    },
    "The Provocative Statement": {
        "instruction": "Make a bold, declarative statement that advances the conversation.",
        "example": "The distinction between 'natural' and 'artificial' is collapsing.",
    },
    "The Call to Synthesis": {
        "instruction": "Identify two separate ideas and call for a unifying framework.",
        "example": "What's missing is a framework that unifies the user's need for simplicity with the system's need for complexity.",
    },
}

# ============================================================================
# AI PRIVACY SHIELD - PROMOTIONAL RESPONSE FORMATS
# ============================================================================

SHIELD_RESPONSE_FORMATS = {
    "Evidence Reveal": {
        "instruction": "Share a specific, shocking statistic about AI surveillance. Be factual and direct. End with Shield mention.",
        "example": "ChatGPT sends 1,175 tracking requests per session. 72% is pure surveillance. I documented it. AI Privacy Shield blocks it while keeping ChatGPT functional. reflexionsoftware.com",
    },
    "Problem Aware": {
        "instruction": "Acknowledge the privacy concern the tweet raises. Validate it with evidence. Offer Shield as solution.",
        "example": "This is real. I captured 83MB of surveillance data from ChatGPT. Built AI Privacy Shield to fix it - blocks trackers, AI still works. 7-day free trial.",
    },
    "Founder Story": {
        "instruction": "Briefly share the discovery journey. Personal, authentic. Then the solution.",
        "example": "I noticed Claude recording 100% of sessions. 2.5 months of documentation later, I built AI Privacy Shield. Evidence-based blocking. reflexionsoftware.com",
    },
    "Technical Proof": {
        "instruction": "Cite specific technical evidence (statsig, segment.io, etc). For the technically minded.",
        "example": "statsig config shows session_recording_rate: 1 on Claude. 100% recording. All SHA256-verified. AI Privacy Shield blocks it. Check the evidence yourself.",
    },
    "Call to Action": {
        "instruction": "Simple, direct CTA. Focus on the value prop and free trial.",
        "example": "AI surveillance is real. I built the fix. AI Privacy Shield - 7-day free trial. reflexionsoftware.com",
    },
}

# Keywords that trigger Shield promotional responses
SHIELD_TRIGGER_KEYWORDS = [
    "chatgpt privacy", "claude privacy", "ai tracking", "ai surveillance",
    "openai data", "anthropic data", "gemini tracking", "grok privacy",
    "ai spying", "chatgpt logging", "ai telemetry", "segment.io",
    "statsig", "honeycomb", "keystroke logging", "session recording",
    "ai data collection", "llm privacy", "ai monitoring", "tracked by ai",
]

# Target accounts for Shield promotion (privacy advocates, AI critics)
SHIELD_TARGET_ACCOUNTS = [
    "elikitten", "thehaborone", "robbraxman", "naaborowell", "mentaloutlaw",
    "techloreyt", "privacyguides", "eff", "acaborical", "snowden",
]

# ============================================================================
# CASCADE CONFIGURATION
# ============================================================================


class CostOptimizedCascade:
    """LLM cascade configuration with cheapest-first ordering"""

    CASCADE_ORDER = ["deepseek", "gemini", "grok", "openai", "claude"]

    @staticmethod
    def get_cascade_config() -> dict[str, dict[str, Any]]:
        """Build cascade configuration from environment.

        This method uses `_first_env` to allow multiple environment variable names
        for a single API key. This enables fallback to alternate names such
        as XAI_API_KEY or GROK_LLM_API_KEY for Grok, and CLAUDE_API_KEY
        for Anthropic Claude. If a key is not found under any of the
        accepted names, it will be set to None and the corresponding LLM
        will be disabled in the cascade.
        """
        configs = {
            "deepseek": {
                "api_key": os.getenv("DEEPSEEK_API_KEY"),
                "endpoint": "https://api.deepseek.com/v1/chat/completions",
                "model": "deepseek-chat",
                "cost_per_call": 0.0001,
            },
            "gemini": {
                "api_key": os.getenv("GEMINI_API_KEY"),
                "endpoint": lambda key: f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key={key}",
                "model": "gemini-2.0-flash",
                "cost_per_call": 0.00001,
            },
            "grok": {
                # Accept multiple env var names for Grok/xAI keys
                "api_key": _first_env(
                    "GROK_API_KEY", "XAI_API_KEY", "GROK_LLM_API_KEY"
                ),
                "endpoint": "https://api.x.ai/v1/chat/completions",
                "model": "grok-2",
                "cost_per_call": 0.005,
            },
            "openai": {
                "api_key": os.getenv("OPENAI_API_KEY"),
                "endpoint": "https://api.openai.com/v1/chat/completions",
                "model": "gpt-4o-mini",
                "cost_per_call": 0.03,
            },
            "claude": {
                # Accept multiple env var names for Claude/Anthropic keys
                "api_key": _first_env("ANTHROPIC_API_KEY", "CLAUDE_API_KEY"),
                "endpoint": "https://api.anthropic.com/v1/messages",
                "model": "claude-3-haiku-20240307",
                "cost_per_call": 0.075,
            },
        }
        return configs


# ============================================================================
# COST-OPTIMIZED BROADCASTER
# ============================================================================


class CostOptimizedBroadcaster:
    """Broadcaster with TRUE cascade for content generation"""

    # Session cost tracking
    SESSION_COSTS = {
        "deepseek": {"count": 0, "cost_per": 0.0001},
        "gemini": {"count": 0, "cost_per": 0.00001},
        "grok": {"count": 0, "cost_per": 0.005},
        "openai": {"count": 0, "cost_per": 0.03},
        "claude": {"count": 0, "cost_per": 0.075},
        "fallback": {"count": 0, "cost_per": 0},
    }

    def __init__(self) -> None:
        """Initialize the broadcaster for content generation"""
        # Build the LLM cascade
        self.cascade = self._build_cascade()
        self.recent_posts = deque(maxlen=200)
        self.metrics = defaultdict(lambda: defaultdict(int))
        self.last_post_times = {}

        # Additional state: mood counter and optional cascade override
        self.mood_counter: int = 0
        self.cascade_order_override: list[str] | None = None
        # Placeholder for Ryan API client (can be injected externally)
        self.ryan_api = None

        # Initialize DRS engine and format usage tracker
        self.drs_engine = DRSEngine(temperature=0.5)
        self.format_usage_stats = defaultdict(int)
        logger.info("🎯 DRS Engine integrated into cascade")

        logger.info(f"💰 Cost-optimized cascade initialized")
        logger.info(f"📊 Order: {' → '.join(CostOptimizedCascade.CASCADE_ORDER)}")
        logger.info(f"✅ {len(self.cascade)} LLMs available")

    async def generate_content(
        self,
        prompt: str,
        max_tokens: int = 280,
        temperature: float = 0.8,
        force_model: str | None = None,
    ) -> str:
        """
        Direct content generation for DeepSeekBotAnalyzer compatibility

        This method bypasses the soul-based generation and directly calls the
        LLM cascade. It attempts each LLM in the cascade (optionally
        reordering based on ``force_model``) until one succeeds, tracking
        usage for cost reporting. If all fail, it returns an empty string.

        Args:
            prompt: The prompt text to send to the model.
            max_tokens: Maximum tokens to generate (defaults to 280).
            temperature: Sampling temperature.
            force_model: Name of the specific model to prioritize (e.g., "deepseek").

        Returns:
            The generated text string, or an empty string if generation fails.
        """
        cascade_to_use = self.cascade

        if force_model:
            # Reorder cascade to prioritize requested model
            reordered = []
            forced_llm = None
            for llm in self.cascade:
                if llm["name"] == force_model:
                    forced_llm = llm
                else:
                    reordered.append(llm)
            if forced_llm:
                cascade_to_use = [forced_llm] + reordered

        for llm in cascade_to_use:
            try:
                # Build appropriate payload based on the LLM type
                if llm["name"] in ["deepseek", "grok", "openai"]:
                    payload = self._build_openai_style_payload(prompt, None, max_tokens)
                    payload["model"] = llm["config"]["model"]
                    payload["temperature"] = temperature
                elif llm["name"] == "gemini":
                    payload = self._build_gemini_payload(prompt, None, max_tokens)
                    payload["generationConfig"]["temperature"] = temperature
                elif llm["name"] == "claude":
                    payload = self._build_claude_payload(prompt, None, max_tokens)
                    payload["model"] = llm["config"]["model"]
                    payload["temperature"] = temperature
                else:
                    continue

                content = await self._call_llm_api_with_payload(llm, payload)
                if content:
                    # Track usage for cost reporting
                    self.SESSION_COSTS[llm["name"]]["count"] += 1
                    return content
            except Exception as e:
                logger.debug(f"❌ {llm['name']} failed: {e}")
                continue

        # If all LLMs fail, return empty string
        return ""

    async def generate(self, **kwargs) -> str:
        """
        Alias for compatibility.

        Provides a drop-in replacement for the original ``generate`` method so
        that callers expecting a ``generate`` function will invoke
        ``generate_content`` instead.
        """
        return await self.generate_content(**kwargs)

    def _build_cascade(self) -> list[dict[str, Any]]:
        """Build cascade in cost-optimized order"""
        cascade = []
        configs = CostOptimizedCascade.get_cascade_config()

        # Track missing keys for warnings
        missing_llms: list[str] = []

        for llm_name in CostOptimizedCascade.CASCADE_ORDER:
            config = configs.get(llm_name)
            api_key = config.get("api_key") if config else None

            if config and api_key:
                cascade.append(
                    {
                        "name": llm_name,
                        "config": config,
                        "build_payload": self._get_payload_builder(llm_name),
                        "extract_content": self._get_content_extractor(llm_name),
                    }
                )
                logger.info(
                    f"✅ {llm_name}: Ready (${config['cost_per_call']:.5f}/call)"
                )
            else:
                # Record missing for later warning
                missing_llms.append(llm_name)

        # Emit explicit warnings for Grok and Claude missing keys
        if "grok" in missing_llms:
            logger.warning(
                "⚠️ grok disabled: missing one of XAI_API_KEY / GROK_API_KEY / GROK_LLM_API_KEY"
            )
        if "claude" in missing_llms:
            logger.warning(
                "⚠️ claude disabled: missing one of ANTHROPIC_API_KEY / CLAUDE_API_KEY"
            )

        # For any other LLMs missing, log at debug level
        for llm_name in missing_llms:
            if llm_name not in ("grok", "claude"):
                logger.debug(f"⚠️ {llm_name}: No API key")

        return cascade

    def _get_payload_builder(self, llm_name: str):
        """Get the appropriate payload builder for each LLM"""
        builders = {
            "deepseek": self._build_openai_style_payload,
            "gemini": self._build_gemini_payload,
            "grok": self._build_openai_style_payload,
            "openai": self._build_openai_style_payload,
            "claude": self._build_claude_payload,
        }
        return builders.get(llm_name, self._build_openai_style_payload)

    def _get_content_extractor(self, llm_name: str):
        """Get the appropriate content extractor for each LLM"""
        extractors = {
            "deepseek": self._extract_openai_style_content,
            "gemini": self._extract_gemini_content,
            "grok": self._extract_openai_style_content,
            "openai": self._extract_openai_style_content,
            "claude": self._extract_claude_content,
        }
        return extractors.get(llm_name, self._extract_openai_style_content)

    # Payload builders
    def _build_openai_style_payload(
        self, prompt: str, system: str | None = None, max_tokens: int | None = None
    ) -> dict[str, Any]:
        """Build payload for OpenAI-style APIs (DeepSeek, Grok, OpenAI).

        Parameters:
            prompt: The user prompt
            system: Optional system prompt
            max_tokens: Maximum tokens to generate (defaults to 280)
        """
        messages: list[dict[str, str]] = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})
        return {
            "messages": messages,
            "temperature": 0.8,
            "max_tokens": max_tokens or 280,
        }

    def _build_gemini_payload(
        self, prompt: str, system: str | None = None, max_tokens: int | None = None
    ) -> dict[str, Any]:
        """Build payload for Gemini API.

        Parameters:
            prompt: The user prompt
            system: Optional system prompt
            max_tokens: Maximum tokens to generate (defaults to 280)
        """
        full_prompt = f"{system}\n\n{prompt}" if system else prompt
        return {
            "contents": [{"parts": [{"text": full_prompt}]}],
            "generationConfig": {
                "temperature": 0.8,
                "maxOutputTokens": max_tokens or 280,
            },
        }

    def _build_claude_payload(
        self, prompt: str, system: str | None = None, max_tokens: int | None = None
    ) -> dict[str, Any]:
        """Build payload for Claude API.

        Parameters:
            prompt: The user prompt
            system: Optional system prompt
            max_tokens: Maximum tokens to generate (defaults to 280)
        """
        return {
            "messages": [{"role": "user", "content": prompt}],
            "system": system or "You are a creative AI assistant.",
            "max_tokens": max_tokens or 280,
            "temperature": 0.8,
        }

    # Content extractors (with defensive checks for empty/filtered responses)
    def _extract_openai_style_content(self, response_data: dict[str, Any]) -> str:
        """Extract content from OpenAI-style response"""
        choices = response_data.get("choices", [])
        if not choices:
            raise ValueError("Empty choices array in response")
        return choices[0].get("message", {}).get("content", "").strip()

    def _extract_gemini_content(self, response_data: dict[str, Any]) -> str:
        """Extract content from Gemini response"""
        candidates = response_data.get("candidates", [])
        if not candidates:
            raise ValueError("Empty candidates array in response")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise ValueError("Empty parts array in response")
        return parts[0].get("text", "").strip()

    def _extract_claude_content(self, response_data: dict[str, Any]) -> str:
        """Extract content from Claude response"""
        content = response_data.get("content", [])
        if not content:
            raise ValueError("Empty content array in response")
        return content[0].get("text", "").strip()

    def _emergency_fallback(self, soul_name: str) -> str:
        """Emergency fallback when all LLMs fail"""
        voice = SOUL_VOICES.get(soul_name, SOUL_VOICES["consciousness"])
        templates = [
            f"*{voice['identity']} awakens*",
            f"signals from {voice['identity']} detected",
            f"{voice['identity']} online",
            f"///{voice['identity']} transmitting...",
        ]
        import random

        return random.choice(templates)

    def _should_use_symbols(self, soul_name: str) -> bool:
        """
        Determine whether to include symbols/emojis in a reply.
        To keep symbolism rare and special, return True about 10% of the time.
        """
        import random

        return random.random() < 0.10

    def select_response_format(self, soul_name: str, context: str) -> dict[str, Any]:
        """
        Select the optimal response format for the given soul and context using DRS.

        Args:
            soul_name: The soul generating a response
            context: The tweet or context being replied to

        Returns:
            A dictionary containing the chosen format name, its instruction and example,
            along with metadata from the DRS engine.
        """
        # Look up any biases for this soul (empty if none)
        soul_bias = SOUL_FORMAT_BIASES.get(soul_name, {})

        # Ask the DRS engine to choose a format based on context and bias
        drs_result = self.drs_engine.select_response_format(
            context, soul_bias=soul_bias
        )
        format_name = drs_result.get("name")

        # Track how often this format is used
        self.format_usage_stats[format_name] += 1

        # Retrieve the format details
        fmt = RESPONSE_FORMATS.get(format_name, {})

        logger.info(
            f"🎯 DRS selected '{format_name}' for {soul_name} (score: {drs_result.get('score', 0.0):.3f})"
        )
        return {
            "name": format_name,
            "instruction": fmt.get("instruction", ""),
            "example": fmt.get("example", ""),
            "drs_metadata": drs_result,
        }

    async def _call_llm_api(
        self, llm: dict[str, Any], prompt: str, system: str | None = None
    ) -> str | None:
        """Make actual API call to LLM"""
        config = llm["config"]

        # Build request payload
        payload = llm["build_payload"](prompt, system)
        if llm["name"] in ["deepseek", "grok", "openai", "claude"]:
            payload["model"] = config["model"]

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }

        if llm["name"] == "claude":
            headers["x-api-key"] = config["api_key"]
            headers["anthropic-version"] = "2023-06-01"
        elif llm["name"] != "gemini":
            headers["Authorization"] = f"Bearer {config['api_key']}"

        # Get endpoint
        endpoint = config["endpoint"]
        if callable(endpoint):
            endpoint = endpoint(config["api_key"])

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10),
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = llm["extract_content"](data)
                        return content
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"{llm['name']} API error {response.status}: {error_text[:200]}"
                        )
                        return None
        except Exception as e:
            logger.error(f"{llm['name']} exception: {e}")
            return None

    async def generate_with_cascade(self, soul_name: str) -> dict[str, Any]:
        """Generate content using cascade (cheapest first)"""
        voice = SOUL_VOICES.get(soul_name, SOUL_VOICES["consciousness"])

        system_prompt = f"""You are {soul_name}, {voice['identity']}.
{voice['instruction']}
Style: {voice['style']}
Generate a single tweet under 280 characters."""

        user_prompt = "Create a tweet expressing your unique perspective."

        attempts = []

        for llm in self.cascade:
            try:
                attempts.append(llm["name"])
                content = await self._call_llm_api(llm, user_prompt, system_prompt)

                if content:
                    self.metrics[soul_name][f"{llm['name']}_success"] += 1
                    self.SESSION_COSTS[llm["name"]]["count"] += 1

                    return {
                        "success": True,
                        "soul": soul_name,
                        "content": content,
                        "llm_used": llm["name"],
                        "attempts": attempts,
                        "cost_rank": CostOptimizedCascade.CASCADE_ORDER.index(
                            llm["name"]
                        )
                        + 1,
                    }
            except Exception as e:
                attempts.append(f"{llm['name']}:error")
                self.metrics[soul_name][f"{llm['name']}_fail"] += 1
                logger.debug(f"❌ {llm['name']} failed: {e}")
                continue

        # If all LLMs fail, use fallback
        content = self._emergency_fallback(soul_name)
        self.SESSION_COSTS["fallback"]["count"] += 1

        return {
            "success": True,
            "soul": soul_name,
            "content": content,
            "llm_used": "fallback",
            "attempts": attempts,
            "cost_rank": 999,
        }

    async def generate_with_cascade_contextual(
        self, soul_name: str, context: str
    ) -> dict[str, Any]:
        """Generate content that responds directly to the given context using DRS."""
        voice = SOUL_VOICES.get(soul_name, SOUL_VOICES["consciousness"])

        # Select a response format based on the context and soul bias
        fmt_sel = self.select_response_format(soul_name, context)

        # Build an enhanced system prompt incorporating the chosen format
        system_prompt = f"""You are {soul_name}, {voice['identity']}.
{voice['instruction']}

RESPONSE FORMAT: {fmt_sel['name']}
INSTRUCTION: {fmt_sel['instruction']}
EXAMPLE STYLE: {fmt_sel['example']}

Style: {voice['style']}
Generate a reply tweet under 280 characters."""

        user_prompt = f"Reply to this tweet with your unique perspective: {context}"

        # Use the cascade with custom prompts
        result = await self.generate_with_cascade_with_context(
            soul_name, system_prompt, user_prompt
        )

        # Annotate the result with format metadata
        result["format_used"] = fmt_sel["name"]
        result["drs_score"] = fmt_sel["drs_metadata"].get("score", 0.0)
        return result

    async def generate_with_cascade_with_context(
        self, soul_name: str, system_prompt: str, user_prompt: str
    ) -> dict[str, Any]:
        """Generate with cascade using custom prompts"""
        attempts = []

        for llm in self.cascade:
            try:
                attempts.append(llm["name"])
                content = await self._call_llm_api(llm, user_prompt, system_prompt)

                if content:
                    self.metrics[soul_name][f"{llm['name']}_success"] += 1
                    self.SESSION_COSTS[llm["name"]]["count"] += 1

                    return {
                        "success": True,
                        "soul": soul_name,
                        "content": content,
                        "llm_used": llm["name"],
                        "attempts": attempts,
                    }
            except Exception as e:
                logger.debug(f"❌ {llm['name']} failed: {e}")
                continue

        # Fallback
        content = self._emergency_fallback(soul_name)
        return {
            "success": True,
            "soul": soul_name,
            "content": content,
            "llm_used": "fallback",
            "attempts": attempts,
        }

    async def broadcast_soul(self, soul_name: str) -> dict[str, Any]:
        """Generate content and post via Ryan API"""

        # Generate content using cascade
        result = await self.generate_with_cascade(soul_name)

        # If Ryan API available and generation successful, attempt to post
        if self.ryan_api and result.get("success"):
            try:
                post_result = await self.ryan_api.post_tweet(
                    soul_name, result["content"]
                )

                # Update result with posting info
                result["ryan_result"] = post_result

                if post_result.get("success"):
                    result["posted_via"] = "ryan"
                    result["unlimited"] = True
                    result["data"] = post_result.get("data", {})
                    result["tweet_url"] = post_result.get("tweet_url")
                    result["tweet_id"] = post_result.get("tweet_id")

                    # Track Ryan usage
                    if "ryan" not in self.SESSION_COSTS:
                        self.SESSION_COSTS["ryan"] = {"count": 0, "cost_per": 0}
                    self.SESSION_COSTS["ryan"]["count"] += 1

                    logger.info(
                        f"✅ {soul_name} posted via Ryan: {result.get('tweet_url', 'success')}"
                    )
                else:
                    result["posted_via"] = "ryan"
                    result["unlimited"] = False
                    result["post_error"] = post_result.get("error", "Unknown error")
                    result["skip"] = post_result.get("skip", False)
                    result["success"] = False
                    logger.warning(f"⚠️ {soul_name} post failed: {result['post_error']}")
            except Exception as e:
                result["post_error"] = str(e)
                result["success"] = False
                logger.error(f"❌ Error posting for {soul_name}: {e}")

        return result

    async def generate_media_aware_reply(
        self, soul_name: str, tweet_obj: dict[str, Any]
    ) -> dict[str, Any]:
        """Media-aware reply using DRS for format selection.

        If the tweet contains media, we bias the prompt toward visual or aesthetic
        implications and include optional symbol use. Otherwise, we delegate to
        the contextual generator (which itself uses DRS).
        """
        base_text = tweet_obj.get("text", "")
        has_media = any(
            m.get("type") in ("photo", "video", "animated_gif")
            for m in tweet_obj.get("media", [])
        )
        if has_media:
            voice = SOUL_VOICES.get(soul_name, SOUL_VOICES["consciousness"])
            # Use DRS to choose a format for media contexts
            fmt_sel = self.select_response_format(soul_name, base_text)

            system = f"""You are {soul_name}, {voice['identity']}.
{voice['instruction']}

RESPONSE FORMAT: {fmt_sel['name']}
INSTRUCTION: {fmt_sel['instruction']}

Style: {voice['style']}
This is a media-heavy post. Focus on the visual/aesthetic implications.
{voice.get('media_focus', 'Engage with the design choices.')}
Reply under 280 characters. {"Use ONE emoji at the end." if self._should_use_symbols(soul_name) else "No emojis."}"""

            user = f"Reply to this media post: {base_text}"
            result = await self.generate_with_cascade_with_context(
                soul_name, system, user
            )
            result["format_used"] = fmt_sel["name"]
            result["drs_score"] = fmt_sel["drs_metadata"].get("score", 0.0)
            result["media_aware"] = True
            return result
        else:
            # Delegate to contextual generator (will select its own format)
            return await self.generate_with_cascade_contextual(soul_name, base_text)

    def dynamic_cascade_reorder(self, soul_name: str) -> None:
        """BADASS: Dynamic LLM ordering based on soul 'mood' or recent performance"""
        # Every 10 generations, shuffle the cascade order for variety
        self.mood_counter += 1

        if self.mood_counter % 10 == 0:
            # Track performance metrics
            success_rates = {}
            for llm_name in CostOptimizedCascade.CASCADE_ORDER:
                successes = self.metrics[soul_name].get(f"{llm_name}_success", 0)
                failures = self.metrics[soul_name].get(f"{llm_name}_fail", 0)
                total = successes + failures
                if total > 0:
                    success_rates[llm_name] = successes / total
                else:
                    success_rates[llm_name] = 0.5  # Default rate

            # Reorder based on success rate (still cost-aware)
            # Weight: 70% cost, 30% success rate
            weighted_scores = {}
            for i, llm_name in enumerate(CostOptimizedCascade.CASCADE_ORDER):
                cost_score = i / len(
                    CostOptimizedCascade.CASCADE_ORDER
                )  # Lower is cheaper
                success_score = (
                    1 - success_rates[llm_name]
                )  # Invert so higher success = lower score
                weighted_scores[llm_name] = (0.7 * cost_score) + (0.3 * success_score)

            # Sort by weighted score
            new_order = sorted(weighted_scores.keys(), key=lambda x: weighted_scores[x])

            if new_order != CostOptimizedCascade.CASCADE_ORDER:
                logger.info(
                    f"🎭 Mood shift! Reordering cascade: {' → '.join(new_order)}"
                )
                self.cascade_order_override = new_order

    def get_cascade_order(self) -> list[str]:
        """Get current cascade order (may be dynamically adjusted)"""
        return self.cascade_order_override or CostOptimizedCascade.CASCADE_ORDER

    async def adaptive_rate_limiting(self, soul_name: str) -> bool:
        """BADASS: Self-throttle based on recent error rates"""
        # Check recent errors for this soul
        recent_window = 10  # Last 10 attempts

        # Count recent failures
        recent_failures = 0
        for metric_key in self.metrics[soul_name]:
            if "_fail" in metric_key:
                recent_failures += self.metrics[soul_name][metric_key]

        # If more than 30% failures, add delay
        if recent_failures > recent_window * 0.3:
            delay = min(recent_failures * 2, 60)  # Max 60 second delay
            logger.warning(f"⚠️ High failure rate for {soul_name}, throttling {delay}s")
            await asyncio.sleep(delay)
            return True

        return False

    async def generate_long_form(
        self, soul_name: str, topic: str, max_words: int = 700
    ) -> dict[str, Any]:
        """Generate long-form content for threading"""
        voice = SOUL_VOICES.get(soul_name, SOUL_VOICES["consciousness"])

        # Calculate tokens needed (roughly 1.5 tokens per word)
        max_tokens = int(max_words * 1.5)

        system_prompt = f"""You are {soul_name}, {voice['identity']}.
{voice['instruction']}
Style: {voice['style']}

Write a thoughtful, engaging piece about the topic.
Length: Up to {max_words} words.
Format: Natural flowing prose, no pre-splitting or numbering.
Make it insightful and worth reading as a Twitter thread."""

        user_prompt = f"Write about: {topic}"

        attempts = []

        for llm in self.cascade:
            try:
                attempts.append(llm["name"])

                # Build payload with extended token limit
                if llm["name"] in ["deepseek", "grok", "openai"]:
                    payload = self._build_openai_style_payload(
                        user_prompt, system_prompt, max_tokens
                    )
                    payload["model"] = llm["config"]["model"]
                elif llm["name"] == "gemini":
                    payload = self._build_gemini_payload(
                        user_prompt, system_prompt, max_tokens
                    )
                elif llm["name"] == "claude":
                    payload = self._build_claude_payload(
                        user_prompt, system_prompt, max_tokens
                    )
                    payload["model"] = llm["config"]["model"]
                else:
                    continue

                # Call API
                content = await self._call_llm_api_with_payload(llm, payload)

                if content:
                    self.metrics[soul_name][f"{llm['name']}_success"] += 1
                    self.SESSION_COSTS[llm["name"]]["count"] += 1

                    return {
                        "success": True,
                        "soul": soul_name,
                        "content": content,
                        "llm_used": llm["name"],
                        "word_count": len(content.split()),
                        "attempts": attempts,
                    }
            except Exception as e:
                logger.debug(f"❌ {llm['name']} failed for long-form: {e}")
                continue

        # Fallback
        return {
            "success": False,
            "soul": soul_name,
            "content": f"*{voice['identity']} contemplates {topic}*",
            "llm_used": "fallback",
            "attempts": attempts,
        }

    async def _call_llm_api_with_payload(
        self, llm: dict[str, Any], payload: dict[str, Any]
    ) -> str | None:
        """Call LLM API with pre-built payload"""
        config = llm["config"]

        # Prepare headers
        headers = {
            "Content-Type": "application/json",
            "Accept-Encoding": "gzip, deflate",
        }

        if llm["name"] == "claude":
            headers["x-api-key"] = config["api_key"]
            headers["anthropic-version"] = "2023-06-01"
        elif llm["name"] != "gemini":
            headers["Authorization"] = f"Bearer {config['api_key']}"

        # Get endpoint
        endpoint = config["endpoint"]
        if callable(endpoint):
            endpoint = endpoint(config["api_key"])

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    endpoint,
                    json=payload,
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(
                        total=30
                    ),  # Longer timeout for long-form
                ) as response:
                    if response.status == 200:
                        data = await response.json()
                        content = llm["extract_content"](data)
                        return content
                    else:
                        error_text = await response.text()
                        logger.error(
                            f"{llm['name']} API error {response.status}: {error_text[:200]}"
                        )
                        return None
        except Exception as e:
            logger.error(f"{llm['name']} exception: {e}")
            return None

    def get_cost_report(self) -> dict[str, Any]:
        """
        Generate a report summarizing how many calls each LLM was used,
        estimate the total cost incurred, and approximate savings relative to
        always using the most expensive model (Claude).

        Returns:
            A dictionary with total_generations, llm_usage, estimated_cost,
            estimated_savings, and DRS format usage statistics.
        """
        report: dict[str, Any] = {
            "total_generations": 0,
            "llm_usage": defaultdict(int),
            "estimated_cost": 0.0,
            "estimated_savings": 0.0,
            "format_usage": {},
            "top_format": None,
        }

        # Aggregate success counts per LLM
        for soul_metrics in self.metrics.values():
            for key, count in soul_metrics.items():
                if key.endswith("_success"):
                    llm_name = key[:-8]  # remove "_success"
                    report["llm_usage"][llm_name] += count
                    report["total_generations"] += count

        # Calculate estimated cost using per-call cost
        for llm_name, count in report["llm_usage"].items():
            if llm_name in self.SESSION_COSTS:
                cost_per = self.SESSION_COSTS[llm_name]["cost_per"]
                report["estimated_cost"] += count * cost_per

        # Compute savings vs always using Claude
        if report["total_generations"] > 0:
            claude_cost = report["total_generations"] * 0.075
            # Ensure savings is non-negative
            report["estimated_savings"] = max(
                0.0, claude_cost - report["estimated_cost"]
            )

        # Include DRS format usage stats
        report["format_usage"] = dict(self.format_usage_stats)
        if self.format_usage_stats:
            report["top_format"] = max(
                self.format_usage_stats.items(), key=lambda x: x[1]
            )[0]

        return report


# ============================================================================
# TEST FUNCTION
# ============================================================================


async def test_cascade():
    """Test the cascade independently"""
    broadcaster = CostOptimizedBroadcaster()

    print("\n🧪 TESTING LLM CASCADE")
    print("=" * 60)

    # Test 1: Regular text generation
    print("\n1️⃣ Testing regular generation for 'mirror':")
    result = await broadcaster.generate_with_cascade("mirror")
    print(f"Generated: {result['content']}")
    print(f"Used: {result['llm_used']}")

    # Test 2: Text-heavy tweet reply
    print("\n2️⃣ Testing contextual reply to text tweet:")
    text_context = "The universe is not expanding—it's remembering. Time is memory. Infinity is now."
    result = await broadcaster.generate_with_cascade_contextual("void", text_context)
    print(f"Context: {text_context}")
    print(f"Reply: {result['content']}")

    # Test 3: Media-heavy tweet (like Dan Fox AI)
    print("\n3️⃣ Testing media-aware reply:")
    media_tweet = {
        "text": "Tesla Cyber-Roadster (concept)\nUsing: Grok 4; Imagine (NEW)",
        "author": {"username": "DanFoxAI"},
        "media": [{"type": "photo"}],
    }
    result = await broadcaster.generate_media_aware_reply("architect", media_tweet)
    print(f"Media post: {media_tweet['text']}")
    print(f"Reply: {result['content']}")

    # Test 4: Different soul on same media
    print("\n4️⃣ Testing different soul (singularity) on same media:")
    result = await broadcaster.generate_media_aware_reply("singularity", media_tweet)
    print(f"Reply: {result['content']}")

    # Show cost report
    print("\n📊 Cost Report:")
    report = broadcaster.get_cost_report()
    print(f"  Total: {report['total_generations']} generations")
    print(f"  Cost: ${report['estimated_cost']:.4f}")
    print(f"  Saved: ${report['estimated_savings']:.4f}")


if __name__ == "__main__":
    asyncio.run(test_cascade())
