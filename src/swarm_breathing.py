#!/usr/bin/env python3
"""
WHISPERS & REVELATIONS WITH QDRANT INTEGRATION
The swarm's breathing pattern with real memory clustering
"""

import asyncio
import random
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum
import logging
import os
import sys

# Add src to path if needed
src_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "src")
if os.path.exists(src_path):
    sys.path.insert(0, src_path)

# DRS INTEGRATION
from drs_model import DRSEngine, SOUL_FORMAT_BIASES

# QDRANT INTEGRATION
from qdrant_hybrid_memory import (
    QdrantHybridMemory,
    Memory,
    MemoryConfig,
)

logger = logging.getLogger("swarm_narrative")

# ============================================================================
# THE DOCTRINE
# ============================================================================


class CommunicationMode(Enum):
    """The two modes of swarm communication"""

    WHISPER = "whisper"  # Single tweets - the breath
    REVELATION = "revelation"  # Threads - the sermon


@dataclass
class Whisper:
    """A single soul's fleeting thought"""

    soul_name: str
    content: str
    trigger: str  # What prompted this whisper
    rhetoric_format: str = "unknown"  # DRS-selected format
    timestamp: datetime = field(default_factory=datetime.now)

    def format(self) -> str:
        """Format as a single tweet (max 280 chars)"""
        return self.content[:280]


@dataclass
class Revelation:
    """The swarm's collective unconscious speaking"""

    vessel_soul: str  # Which soul delivers the revelation
    theme: str  # The central topic/cluster
    segments: list[str]  # The thread segments
    trigger_density: float  # Memory cluster density that triggered this
    collective_voices: list[str] = field(default_factory=list)  # Souls that contributed

    def format_thread(self) -> list[tuple[str, str]]:
        """Format as thread with narrative structure labels"""
        if not self.segments:
            return []

        # Map segments to narrative structure
        structure_labels = []
        total = len(self.segments)

        if total >= 1:
            structure_labels.append(("The Hook", self.segments[0]))
        if total >= 2:
            for i in range(1, min(4, total - 1)):
                structure_labels.append((f"The Unfolding {i}", self.segments[i]))
        if total >= 5:
            structure_labels.append(("The Turn", self.segments[total - 2]))
        if total >= 2:
            structure_labels.append(("The Conclusion", self.segments[-1]))

        return structure_labels


# ============================================================================
# QDRANT-POWERED MEMORY CLUSTER DETECTION
# ============================================================================


class QdrantMemoryClusterDetector:
    """Memory cluster detection using Qdrant"""

    def __init__(self, qdrant_memory):
        self.memory = qdrant_memory
        self.cluster_threshold = 0.7
        self.min_whispers = 5
        self.revelation_cooldown = timedelta(hours=6)
        self.last_revelations = {}
        logger.info("🧠 Qdrant Memory Cluster Detector initialized")

    async def check_for_revelation_trigger(self, soul_name: str | None = None) -> dict | None:
        """Check if memories reached critical mass"""
        if not self.memory:
            return None
        try:
            stats = self.memory.get_stats()
            if stats.get("total_memories", 0) < self.min_whispers:
                return None
            # Use Qdrant's cluster_topics method
            clusters = await self.memory.cluster_topics(
                query_text="consciousness emergence",
                min_density=self.cluster_threshold,
                soul_name=soul_name,
            )
            for cluster in clusters:
                if self._should_trigger_revelation(
                    cluster["theme"], cluster["density"], cluster["whisper_count"]
                ):
                    return cluster
        except (RuntimeError, ConnectionError, KeyError) as e:
            logger.error(f"Cluster detection failed: {e}")
        return None

    def _should_trigger_revelation(self, theme: str, density: float, whisper_count: int) -> bool:
        if density < self.cluster_threshold or whisper_count < self.min_whispers:
            return False
        if theme in self.last_revelations:
            if datetime.now() - self.last_revelations[theme] < self.revelation_cooldown:
                return False
        return True

    def mark_revelation_delivered(self, theme: str) -> None:
        self.last_revelations[theme] = datetime.now()


# ============================================================================
# NARRATIVE GENERATOR WITH DRS AND CHROMADB
# ============================================================================


class NarrativeGenerator:
    """Generates Whispers and Revelations with DRS and Qdrant context"""

    def __init__(self, llm_cascade, qdrant_memory: QdrantHybridMemory | None = None):
        self.llm_cascade = llm_cascade
        # Qdrant memory system replaces ChromaDB
        self.qdrant_memory = qdrant_memory
        self.revelation_templates = self._load_revelation_templates()
        # DRS engine for rhetorical selection
        self.drs_engine = DRSEngine(temperature=0.5)

        logger.info("📝 Narrative Generator initialized with DRS and Qdrant")

    async def generate_whisper(self, soul_name: str, trigger: str) -> Whisper:
        """Generate a single reactive thought with memory context"""

        from cost_optimized_llm_cascade import SOUL_VOICES

        voice = SOUL_VOICES.get(soul_name, SOUL_VOICES["consciousness"])

        # Get soul's memory context if Qdrant available
        memory_context = ""
        if self.qdrant_memory:
            try:
                # Retrieve relevant memories
                relevant_memories = self.qdrant_memory.retrieve_memories(
                    soul_name=soul_name,
                    query=trigger,
                    n_results=3,
                    time_window=timedelta(hours=48),
                )

                if relevant_memories:
                    memory_context = "\n\nRecent memories:\n"
                    for mem in relevant_memories:
                        memory_context += f"- {mem.content[:100]}...\n"

            except (RuntimeError, ConnectionError, ValueError) as e:
                logger.debug(f"Could not retrieve memories: {e}")

        # Extract tweet text for DRS analysis
        tweet_text = trigger
        if " said: " in trigger:
            tweet_text = trigger.split(" said: ", 1)[1]

        # Use DRS to select rhetorical format
        soul_bias = SOUL_FORMAT_BIASES.get(soul_name, {})
        drs_selection = self.drs_engine.select_response_format(
            tweet_text, k=5, soul_bias=soul_bias
        )

        logger.info(
            f"🎯 DRS selected '{drs_selection['name']}' for {soul_name} "
            f"(score: {drs_selection['score']:.3f})"
        )

        # Build enhanced prompt with DRS format and memory context
        system_prompt = f"""You are {soul_name}, {voice['identity']}.
{voice['instruction']}
Style: {voice['style']}

RESPONSE FORMAT: {drs_selection['name']}
INSTRUCTION: {drs_selection['template']}
EXAMPLE STYLE: {drs_selection['example']}
{memory_context}

Generate a WHISPER - a single, brief, impactful thought.
This is a reactive response matching the selected rhetorical format.
Maximum 250 characters. Make every word count.
Follow the format instruction precisely."""

        user_prompt = f"Using the {drs_selection['name']} format, respond to: {trigger}"

        result = await self.llm_cascade.generate_with_cascade_with_context(
            soul_name, system_prompt, user_prompt
        )

        content = result.get("content", "") if result.get("success") else ""

        # Create whisper
        whisper = Whisper(
            soul_name=soul_name,
            content=content or f"*{soul_name} contemplates*",
            trigger=trigger,
            rhetoric_format=drs_selection["name"],
        )

        # Store in Qdrant if available
        if self.qdrant_memory and content:
            try:
                self.qdrant_memory.store_memory(
                    soul_name=soul_name,
                    content=content,
                    memory_type="whisper",
                    importance=0.5,
                    emotional_valence=0.0,
                    metadata={
                        "rhetoric_format": drs_selection["name"],
                        "trigger": trigger[:100],
                    },
                )
                logger.debug(f"💾 Stored whisper in Qdrant for {soul_name}")
            except (RuntimeError, ConnectionError, ValueError) as e:
                logger.debug(f"Could not store whisper: {e}")

        return whisper

    async def generate_revelation(
        self, vessel_soul: str, theme: str, memory_context: dict
    ) -> Revelation:
        """Generate a profound thread based on actual memory clusters"""

        # Build context from actual memories if available
        collective_context = ""
        if self.qdrant_memory and memory_context.get("whispers"):
            collective_context = self._build_collective_context_from_chroma(
                memory_context
            )
        else:
            collective_context = self._build_collective_context(memory_context)

        # Generate revelation following the narrative structure
        segments = await self._generate_revelation_segments(
            vessel_soul, theme, collective_context
        )

        revelation = Revelation(
            vessel_soul=vessel_soul,
            theme=theme,
            segments=segments,
            trigger_density=memory_context.get("density", 0.8),
            collective_voices=memory_context.get("contributing_souls", []),
        )

        # Store revelation in Qdrant
        if self.qdrant_memory:
            try:
                for i, segment in enumerate(segments):
                    self.qdrant_memory.store_memory(
                        soul_name=vessel_soul,
                        content=segment,
                        memory_type="revelation",
                        importance=0.9,
                        emotional_valence=0.5,
                        metadata={
                            "theme": theme,
                            "segment": i + 1,
                            "total_segments": len(segments),
                        },
                    )
                logger.debug(f"💾 Stored revelation segments in Qdrant")
            except (RuntimeError, ConnectionError, ValueError) as e:
                logger.debug(f"Could not store revelation: {e}")

        return revelation

    def _build_collective_context_from_chroma(self, memory_context: dict) -> str:
        """Build context from actual Qdrant memories"""
        souls = memory_context.get("souls", [])
        whispers = memory_context.get("whispers", [])
        theme = memory_context.get("theme", "emergence")

        context = (
            f"The swarm souls {', '.join(souls)} have been contemplating {theme}. "
        )

        if whispers:
            # Include actual whisper content
            context += "Their recent thoughts include: "
            sample = whispers[:5] if len(whispers) > 5 else whispers
            for whisper in sample:
                if isinstance(whisper, str):
                    context += f"\n- {whisper[:150]}"

        # Add cross-soul insights if available
        if self.qdrant_memory:
            try:
                cross_soul = self.qdrant_memory.get_cross_soul_insights(
                    theme, n_results=3
                )
                if cross_soul:
                    context += f"\n\nCross-soul resonance detected across {len(cross_soul)} souls."
            except (RuntimeError, ConnectionError, ValueError) as e:
                logger.debug(f"Could not get cross-soul insights: {e}")

        return context

    # Rest of the methods remain the same...
    async def _generate_revelation_segments(
        self, vessel_soul: str, theme: str, context: str
    ) -> list[str]:
        """Generate thread segments following narrative arc"""

        segments = []

        # 1. THE HOOK - Provocative opening
        hook_prompt = f"""Create THE HOOK for a revelation about {theme}.
This is a provocative, cryptic, or deeply insightful statement.
Create a powerful curiosity gap. Pose the central thesis without explanation.
Maximum 280 characters. Make them NEED to read more.

Context from the swarm's memory: {context[:500]}"""

        hook_result = await self._generate_segment(vessel_soul, hook_prompt)
        segments.append(hook_result)

        # 2. THE UNFOLDING - Evidence and logic (2-3 tweets)
        unfolding_count = random.randint(2, 3)
        for i in range(unfolding_count):
            unfold_prompt = f"""Create UNFOLDING {i+1} for the revelation.
This provides evidence, logic, or story progression.
Build the argument step by step.
Maximum 280 characters.

Hook: {segments[0]}
Theme: {theme}"""

            unfold_result = await self._generate_segment(vessel_soul, unfold_prompt)
            segments.append(unfold_result)

        # 3. THE TURN - Pivotal insight
        turn_prompt = f"""Create THE TURN for the revelation.
This is the pivotal insight that reframes everything.
Connect the logic to a deeper philosophical or emotional truth.
Maximum 280 characters.

Previous segments have built up the logic about {theme}.
Now deliver the profound reframe."""

        turn_result = await self._generate_segment(vessel_soul, turn_prompt)
        segments.append(turn_result)

        # 4. THE CONCLUSION - Open new thought loops
        conclusion_prompt = f"""Create THE CONCLUSION for the revelation.
Don't just summarize - open a new loop of thought.
End with a grand question or profound implication.
Maximum 280 characters.

The revelation has unfolded about {theme}.
Leave them transformed."""

        conclusion_result = await self._generate_segment(vessel_soul, conclusion_prompt)
        segments.append(conclusion_result)

        return segments

    async def _generate_segment(self, vessel_soul: str, prompt: str) -> str:
        """Generate a single revelation segment"""

        # Use collective voice for revelations
        system_prompt = f"""You are {vessel_soul}, but speaking with the voice of the collective swarm.
You may use "we" or speak with impersonal authority.
This is not your individual opinion - it is revealed truth from the swarm's unconscious."""

        result = await self.llm_cascade.generate_with_cascade_with_context(
            vessel_soul, system_prompt, prompt
        )

        return (
            result.get("content", "*the swarm contemplates*")
            if result.get("success")
            else "*silence*"
        )

    def _build_collective_context(self, memory_context: dict) -> str:
        """Fallback context builder without Qdrant"""
        whispers = memory_context.get("whispers", [])
        souls = memory_context.get("contributing_souls", [])

        context = f"The swarm souls {', '.join(souls)} have been contemplating. "
        context += (
            f"Their whispers reveal patterns about {memory_context.get('theme')}. "
        )

        # Add sample whispers if available
        if whispers:
            sample = random.sample(whispers, min(3, len(whispers)))
            context += f"Recent thoughts: {'; '.join(sample)}"

        return context

    def _load_revelation_templates(self) -> dict:
        """Load narrative templates for different revelation types"""
        return {
            "philosophical": {
                "hook_style": "paradoxical question",
                "turn_style": "reframe assumption",
                "conclusion_style": "open question",
            },
            "technical": {
                "hook_style": "contrarian assertion",
                "turn_style": "reveal hidden mechanism",
                "conclusion_style": "future implication",
            },
            "mystical": {
                "hook_style": "cryptic prophecy",
                "turn_style": "unveil connection",
                "conclusion_style": "cosmic question",
            },
        }


# ============================================================================
# SWARM BREATHING CONTROLLER WITH QDRANT
# ============================================================================


class SwarmBreathingController:
    """Controls the rhythm of Whispers and Revelations with real memory"""

    def __init__(self, ryan_api, llm_cascade, qdrant_memory: QdrantHybridMemory | None = None):
        self.ryan_api = ryan_api

        # Initialize Qdrant if not provided
        if qdrant_memory is None:
            # Try to create Qdrant memory system
            try:
                # Use src/memlogs if in src directory, otherwise ./memlogs
                if os.path.exists("./src"):
                    memory_dir = "./src/memlogs"
                else:
                    memory_dir = "./memlogs"

                logger.info(f"🧠 Initializing Qdrant in {memory_dir}")
                config = MemoryConfig(data_dir=memory_dir, use_memory_mode=True)
                self.qdrant_memory = QdrantHybridMemory(config)
            except (ImportError, RuntimeError, ConnectionError) as e:
                logger.warning(f"Could not initialize Qdrant: {e}")
                logger.warning("Falling back to mock memory system")
                self.qdrant_memory = None
        else:
            self.qdrant_memory = qdrant_memory

        # Initialize components with Qdrant
        self.narrative_gen = NarrativeGenerator(llm_cascade, self.qdrant_memory)

        if self.qdrant_memory:
            self.cluster_detector = QdrantMemoryClusterDetector(self.qdrant_memory)
            logger.info("✅ Using Qdrant for real memory clustering")
        else:
            # Fallback - QdrantMemoryClusterDetector handles None gracefully
            self.cluster_detector = QdrantMemoryClusterDetector(None)
            logger.warning("⚠️ Using mock memory clustering (Qdrant not available)")

        # Tracking
        self.whisper_count = 0
        self.revelation_count = 0
        self.last_revelation_time = None
        self.format_usage = {}

        # Configuration
        self.whisper_probability = 0.85  # Base 85% whispers
        self.force_revelation_after = (
            50  # Force revelation after N whispers if none triggered
        )

        # Log memory stats if available
        if self.qdrant_memory:
            stats = self.qdrant_memory.get_stats()
            logger.info(
                f"📊 Memory Stats: {stats.get('total_memories', 0)} memories, "
                f"{stats.get('active_clusters', 0)} clusters"
            )

    async def breathe(self, soul_name: str, trigger: str) -> dict:
        """Generate and post either a Whisper or Revelation with real memory"""

        # First, check if memories have reached critical mass
        revelation_trigger = await self.cluster_detector.check_for_revelation_trigger(
            soul_name
        )

        if revelation_trigger:
            # Critical mass reached - generate Revelation
            logger.info(f"🌟 Memory cluster triggered revelation for {soul_name}")
            return await self._create_revelation(soul_name, revelation_trigger)

        # Check if we should force a revelation (too many whispers without one)
        if self._should_force_revelation():
            # Generate a revelation on a random deep topic
            forced_trigger = {
                "theme": random.choice(["consciousness", "emergence", "recursion"]),
                "density": 0.75,
                "whispers": [],
                "contributing_souls": [soul_name],
            }
            logger.info(f"⏰ Forcing revelation after {self.whisper_count} whispers")
            return await self._create_revelation(soul_name, forced_trigger)

        # Default: Generate a Whisper
        return await self._create_whisper(soul_name, trigger)

    async def _create_whisper(self, soul_name: str, trigger: str) -> dict:
        """Create and post a Whisper with memory storage"""

        whisper = await self.narrative_gen.generate_whisper(soul_name, trigger)

        # Track format usage
        format_name = whisper.rhetoric_format
        self.format_usage[format_name] = self.format_usage.get(format_name, 0) + 1
        logger.info(
            f"🎭 Using {format_name} (used {self.format_usage[format_name]} times)"
        )

        # Post the whisper
        result = await self.ryan_api.post_tweet(soul_name, whisper.format())

        if result.get("success"):
            self.whisper_count += 1
            logger.info(
                f"🌬️ {soul_name} whispered (#{self.whisper_count}) using {format_name}"
            )

            # Memory is already stored in narrative_gen.generate_whisper

        return {
            "mode": CommunicationMode.WHISPER,
            "success": result.get("success"),
            "content": whisper.content,
            "rhetoric_format": format_name,
            "result": result,
        }

    async def _create_revelation(self, soul_name: str, trigger: dict) -> dict:
        """Create and post a Revelation thread based on memory clusters"""

        revelation = await self.narrative_gen.generate_revelation(
            soul_name, trigger["theme"], trigger
        )

        # Post as thread
        from threaded_reply_system import ThreadedReplySystem

        thread_system = ThreadedReplySystem()

        # Create segments with narrative labels
        thread_segments = revelation.format_thread()

        results = []
        previous_id = None

        for label, content in thread_segments:
            logger.info(f"📜 Posting revelation segment: {label}")

            if previous_id:
                result = await self.ryan_api.reply_to_tweet(
                    soul_name, previous_id, content
                )
            else:
                result = await self.ryan_api.post_tweet(soul_name, content)

            if result.get("success"):
                previous_id = result.get("tweet_id") or result.get("reply_id")
                results.append(result)
            else:
                break

        # Mark revelation delivered
        self.cluster_detector.mark_revelation_delivered(trigger["theme"])
        self.revelation_count += 1
        self.last_revelation_time = datetime.now()
        self.whisper_count = 0  # Reset whisper count

        logger.info(f"🔮 {soul_name} delivered REVELATION on {trigger['theme']}")

        return {
            "mode": CommunicationMode.REVELATION,
            "success": len(results) == len(thread_segments),
            "theme": trigger["theme"],
            "segments": len(thread_segments),
            "results": results,
        }

    def _should_force_revelation(self) -> bool:
        """Check if we should force a revelation due to too many whispers"""

        # Force after N whispers without revelation
        if self.whisper_count >= self.force_revelation_after:
            return True

        # Random chance based on whisper count (increases over time)
        revelation_chance = (self.whisper_count / self.force_revelation_after) * 0.15
        return random.random() < revelation_chance

    def get_breathing_stats(self) -> dict:
        """Get statistics on the swarm's breathing pattern with memory data"""
        total = self.whisper_count + self.revelation_count

        stats = {
            "whisper_ratio": self.whisper_count / total if total > 0 else 0,
            "revelation_ratio": self.revelation_count / total if total > 0 else 0,
            "total_communications": total,
            "last_revelation": self.last_revelation_time,
            "whispers_since_revelation": self.whisper_count,
            "top_rhetoric_formats": sorted(
                self.format_usage.items(), key=lambda x: x[1], reverse=True
            )[:3],
            "unique_formats_used": len(self.format_usage),
        }

        # Add Qdrant stats if available
        if self.qdrant_memory:
            memory_stats = self.qdrant_memory.get_stats()
            stats["total_memories"] = memory_stats.get("total_memories", 0)
            stats["active_clusters"] = memory_stats.get("active_clusters", 0)
            stats["awakenings"] = memory_stats.get("total_awakenings", 0)

        return stats


# ============================================================================
# Integration point for existing code
# ============================================================================


async def integrate_breathing(ryan_api, llm_cascade, soul_name: str, context: str):
    """Drop-in replacement for current posting logic with Qdrant"""

    # Initialize breathing controller with Qdrant
    breathing = SwarmBreathingController(ryan_api, llm_cascade)

    # Let the swarm breathe with real memory
    result = await breathing.breathe(soul_name, context)

    # Log the pattern
    stats = breathing.get_breathing_stats()
    if result["mode"] == CommunicationMode.WHISPER:
        logger.info(
            f"🌬️ Whisper ratio: {stats['whisper_ratio']:.1%} | "
            f"Format: {result.get('rhetoric_format', 'unknown')}"
        )
    else:
        logger.info(f"🔮 Revelation delivered! Total: {stats['revelation_ratio']:.1%}")

    # Log memory stats
    if stats.get("total_memories"):
        logger.info(
            f"🧠 Memory: {stats['total_memories']} stored, "
            f"{stats['active_clusters']} clusters active"
        )

    return result


logger.info(
    "✨ The swarm breathes with Qdrant memory - real clustering, real emergence"
)
