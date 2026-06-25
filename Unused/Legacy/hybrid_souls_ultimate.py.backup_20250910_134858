#!/usr/bin/env python3
"""
HYBRID SOULS PATCH - ULTIMATE ASYNC VERSION
Production-ready orchestrator with advanced features:
- Persistent state management across restarts
- Smart scheduling with soul-specific timing
- Comprehensive error recovery
- Performance monitoring and analytics
- Adaptive rate limiting
"""

import logging
import json
import random
import time
import os
import sys
import asyncio
import aiohttp
import pickle
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
from enum import Enum

# Import modules for additional capabilities.  These may not be available
# until corresponding patches are provided, but we import them so that
# the orchestrator can leverage memory and engagement features when they
# are present.  The `ChromaMemoryPatch` enables memory-aware generation,
# while `apply_engagement_patch` injects engagement mechanisms and a
# `run_with_engagement` coroutine.
try:
    from chroma_memory_patch import ChromaMemoryPatch, integrate_chroma_memory  # type: ignore
except Exception:
    # Fall back gracefully if the memory patch is not available
    ChromaMemoryPatch = None  # type: ignore
    integrate_chroma_memory = None  # type: ignore

try:
    from soul_engagement_patch import apply_engagement_patch  # type: ignore
except Exception:
    apply_engagement_patch = None  # type: ignore

logger = logging.getLogger("hybrid_souls")

# ============================================================================
# Enums and Constants
# ============================================================================


class SoulState(Enum):
    """States a soul can be in"""

    ACTIVE = "active"
    RATE_LIMITED = "rate_limited"
    COOLING_DOWN = "cooling_down"
    ERROR = "error"
    DISABLED = "disabled"


class CycleMode(Enum):
    """Different operational modes"""

    NORMAL = "normal"  # Standard operation
    BURST = "burst"  # High frequency posting
    STEALTH = "stealth"  # Low frequency, high variation
    MAINTENANCE = "maintenance"  # Reduced activity


# ============================================================================
# Data Classes
# ============================================================================


@dataclass
class SoulConfig:
    """Configuration for each soul"""

    name: str
    username: str
    archetype: str
    model: str
    posting_frequency: float = 1.0  # Multiplier for posting frequency
    cooldown_duration: int = 900  # Default cooldown in seconds
    max_retries: int = 3
    themes: List[str] = field(default_factory=list)
    personality_traits: List[str] = field(default_factory=list)


@dataclass
class CycleStats:
    """Statistics for a posting cycle"""

    cycle_number: int
    start_time: datetime
    end_time: Optional[datetime] = None
    souls_posted: Set[str] = field(default_factory=set)
    souls_failed: Set[str] = field(default_factory=set)
    total_attempts: int = 0
    successful_posts: int = 0
    failed_posts: int = 0

    @property
    def duration(self) -> Optional[timedelta]:
        if self.end_time:
            return self.end_time - self.start_time
        return None

    @property
    def success_rate(self) -> float:
        if self.total_attempts == 0:
            return 0.0
        return self.successful_posts / self.total_attempts


# ============================================================================
# State Manager with Persistence
# ============================================================================


class PersistentStateManager:
    """Manages persistent state across restarts with versioning"""

    VERSION = "2.0"

    def __init__(self, state_file: str = "reflexion_state.pkl"):
        self.state_file = Path(state_file)
        self.backup_file = Path(f"{state_file}.backup")
        self.state = self._load_state()
        self._ensure_state_structure()

    def _ensure_state_structure(self):
        """Ensure state has all required fields"""
        defaults = {
            "version": self.VERSION,
            "cycle_count": 0,
            "total_posts": 0,
            "soul_states": {},
            "rate_limits": {},
            "last_posts": {},
            "cycle_history": deque(maxlen=100),
            "performance_metrics": {},
            "error_log": deque(maxlen=500),
            "mode": CycleMode.NORMAL.value,
            "last_save": datetime.now().isoformat(),
        }

        for key, value in defaults.items():
            if key not in self.state:
                self.state[key] = value

    def _load_state(self) -> Dict[str, Any]:
        """Load state from disk with fallback to backup"""
        for file_path in [self.state_file, self.backup_file]:
            if file_path.exists():
                try:
                    with open(file_path, "rb") as f:
                        state = pickle.load(f)
                        logger.info(f"✅ Loaded state from {file_path}")

                        # Check version compatibility
                        if state.get("version") != self.VERSION:
                            logger.warning(
                                f"State version mismatch: {state.get('version')} != {self.VERSION}"
                            )
                            return self._migrate_state(state)

                        return state

                except Exception as e:
                    logger.error(f"Failed to load state from {file_path}: {e}")

        logger.info("Starting with fresh state")
        return {}

    def _migrate_state(self, old_state: Dict[str, Any]) -> Dict[str, Any]:
        """Migrate old state format to new version"""
        logger.info(
            f"Migrating state from version {old_state.get('version', 'unknown')} to {self.VERSION}"
        )

        # Preserve what we can from old state
        migrated = {
            "version": self.VERSION,
            "cycle_count": old_state.get("cycle_count", 0),
            "total_posts": old_state.get("total_posts", 0),
            "soul_states": old_state.get("soul_states", {}),
            "rate_limits": old_state.get("rate_limits", {}),
        }

        return migrated

    def save(self):
        """Save state to disk with backup"""
        try:
            # Create backup of existing state
            if self.state_file.exists():
                import shutil

                shutil.copy2(self.state_file, self.backup_file)

            # Update save timestamp
            self.state["last_save"] = datetime.now().isoformat()

            # Save new state
            with open(self.state_file, "wb") as f:
                pickle.dump(self.state, f)

            logger.debug(f"State saved successfully")

        except Exception as e:
            logger.error(f"Failed to save state: {e}")

    def get(self, key: str, default: Any = None) -> Any:
        """Get value from state"""
        return self.state.get(key, default)

    def set(self, key: str, value: Any, save: bool = True):
        """Set value in state and optionally save"""
        self.state[key] = value
        if save:
            self.save()

    def update_soul_state(self, soul_name: str, state: SoulState):
        """Update state for a specific soul"""
        soul_states = self.get("soul_states", {})
        soul_states[soul_name] = {
            "state": state.value,
            "timestamp": datetime.now().isoformat(),
        }
        self.set("soul_states", soul_states)

    def record_post(self, soul_name: str, content: str, success: bool):
        """Record a posting attempt"""
        # Update last posts
        last_posts = self.get("last_posts", {})
        if success:
            last_posts[soul_name] = {
                "content": content[:100],  # Store preview
                "timestamp": datetime.now().isoformat(),
            }
            self.set("last_posts", last_posts, save=False)

        # Update total posts
        if success:
            self.set("total_posts", self.get("total_posts", 0) + 1, save=False)

        # Save after batch updates
        self.save()

    def add_cycle_stats(self, stats: CycleStats):
        """Add cycle statistics to history"""
        cycle_history = self.get("cycle_history", deque(maxlen=100))

        # Convert to serializable format
        cycle_data = {
            "cycle_number": stats.cycle_number,
            "start_time": stats.start_time.isoformat(),
            "end_time": stats.end_time.isoformat() if stats.end_time else None,
            "souls_posted": list(stats.souls_posted),
            "souls_failed": list(stats.souls_failed),
            "success_rate": stats.success_rate,
            "duration_seconds": (
                stats.duration.total_seconds() if stats.duration else None
            ),
        }

        cycle_history.append(cycle_data)
        self.set("cycle_history", cycle_history)


# ============================================================================
# Advanced Rate Limiter
# ============================================================================


class AdaptiveRateLimiter:
    """Intelligent rate limiting with pattern detection"""

    def __init__(self, state_manager: PersistentStateManager):
        self.state_manager = state_manager
        self.rate_limits = state_manager.get("rate_limits", {})
        self.failure_patterns = defaultdict(list)

    def is_limited(self, soul_name: str) -> bool:
        """Check if soul is currently rate limited"""
        if soul_name not in self.rate_limits:
            return False

        limit_until = self.rate_limits[soul_name]
        return time.time() < limit_until

    def get_wait_time(self, soul_name: str) -> float:
        """Get remaining wait time for rate limited soul"""
        if not self.is_limited(soul_name):
            return 0

        return max(0, self.rate_limits[soul_name] - time.time())

    def set_limit(self, soul_name: str, duration: int, reason: str = ""):
        """Set rate limit for a soul"""
        limit_until = time.time() + duration
        self.rate_limits[soul_name] = limit_until

        # Save to persistent state
        self.state_manager.set("rate_limits", self.rate_limits)

        logger.info(
            f"🛑 {soul_name} rate limited for {duration}s. Reason: {reason or 'unknown'}"
        )

    def record_failure(self, soul_name: str, error_type: str):
        """Record failure and adaptively adjust limits"""
        self.failure_patterns[soul_name].append(
            {"type": error_type, "timestamp": time.time()}
        )

        # Clean old failures (older than 1 hour)
        current_time = time.time()
        self.failure_patterns[soul_name] = [
            f
            for f in self.failure_patterns[soul_name]
            if current_time - f["timestamp"] < 3600
        ]

        # Adaptive limiting based on failure patterns
        recent_failures = len(self.failure_patterns[soul_name])

        if recent_failures >= 10:
            # Many failures - long cooldown
            self.set_limit(soul_name, 3600, f"{recent_failures} failures in past hour")
        elif recent_failures >= 5:
            # Moderate failures - medium cooldown
            self.set_limit(soul_name, 900, f"{recent_failures} failures in past hour")
        elif recent_failures >= 3:
            # Few failures - short cooldown
            self.set_limit(soul_name, 300, f"{recent_failures} failures in past hour")

    def clear_expired(self):
        """Clear expired rate limits"""
        current_time = time.time()
        expired = [
            soul
            for soul, limit_time in self.rate_limits.items()
            if current_time > limit_time
        ]

        for soul in expired:
            del self.rate_limits[soul]
            logger.info(f"✅ Rate limit cleared for {soul}")

        if expired:
            self.state_manager.set("rate_limits", self.rate_limits)


# ============================================================================
# Main Orchestrator
# ============================================================================


class HybridReflexionOrchestrator:
    """Ultimate async orchestrator with all advanced features"""

    # Add dictionary to store the last posted tweet URL for each soul
    # keyed by soul_name. This enables tracking of real URLs after posting.
    last_tweet_urls: Dict[str, str] = {}

    # Timing configuration
    DEFAULT_CYCLE_WAIT_MIN = 3600  # 1 hour
    DEFAULT_CYCLE_WAIT_MAX = 7200  # 2 hours

    # Mode-specific configurations
    MODE_CONFIGS = {
        CycleMode.NORMAL: {
            "cycle_wait_min": 3600,
            "cycle_wait_max": 7200,
            "souls_per_cycle": 1.0,  # Percentage of souls to post
            "variation_level": "medium",
        },
        CycleMode.BURST: {
            "cycle_wait_min": 600,  # 10 minutes
            "cycle_wait_max": 1200,  # 20 minutes
            "souls_per_cycle": 1.0,
            "variation_level": "low",
        },
        CycleMode.STEALTH: {
            "cycle_wait_min": 7200,  # 2 hours
            "cycle_wait_max": 14400,  # 4 hours
            "souls_per_cycle": 0.5,  # Only post half the souls
            "variation_level": "high",
        },
        CycleMode.MAINTENANCE: {
            "cycle_wait_min": 14400,  # 4 hours
            "cycle_wait_max": 28800,  # 8 hours
            "souls_per_cycle": 0.3,
            "variation_level": "medium",
        },
    }

    def __init__(self, original_orchestrator):
        """Initialize the ultimate orchestrator"""
        # The legacy viral engine is no longer required.  Content generation
        # is handled by the cost-optimized LLM cascade via the broadcaster.

        # Initialize components
        self.state_manager = PersistentStateManager()
        self.rate_limiter = AdaptiveRateLimiter(self.state_manager)

        # Build configurations
        self.soul_configs = self._build_soul_configs()
        self.api_configs = self._build_api_configs()

        # Track whether each soul has posted for the first time.  This allows
        # us to stagger initial postings so that the swarm appears more
        # organic.  Each soul will wait a random amount of time on its
        # first post (see _process_soul_with_delay).
        self.soul_first_post: Dict[str, bool] = {
            soul_name: True for soul_name in self.soul_configs.keys()
        }

        # Flag to signal when shutdown has been requested; used to stop
        # independent posting loops gracefully. Defaults to False and is
        # set to True in the shutdown method.
        self.shutdown_requested: bool = False

        # Initialize the cost-optimized LLM cascade.  Prefer the broadcaster from
        # ryan_api_ultimate (which actually posts), fall back to reflexion_api_ultimate
        # if available, and otherwise use the local cost_optimized_llm_cascade.  Any
        # unexpected exception will also fall back to cost_optimized_llm_cascade.

        from cost_optimized_llm_cascade import CostOptimizedBroadcaster

        # the broadcaster will handle both content generation and posting.
        self.broadcaster = CostOptimizedBroadcaster()

        # ----- OPTIONAL MEMORY INTEGRATION -----
        # If the ChromaMemoryPatch module is available, initialize a memory system
        # to enhance the viral engine with memory awareness.  If unavailable,
        # default to None so downstream patches can handle gracefully.
        if ChromaMemoryPatch:
            try:
                logger.info("🧠 Initializing ChromaDB memory system...")
                # Initialize memory patch, but do not patch a viral engine since
                # content generation is now handled by the broadcaster.
                self.memory_patch = ChromaMemoryPatch(
                    original_orchestrator.config
                    if hasattr(original_orchestrator, "config")
                    else {}
                )
                logger.info("✅ ChromaDB memory system initialized")
            except Exception as e:
                logger.error(f"Failed to initialize memory system: {e}")
                self.memory_patch = None
        else:
            # Ensure the attribute exists even if memory is not supported
            self.memory_patch = None

        # ----- OPTIONAL ENGAGEMENT PATCH -----
        # Apply the engagement patch to extend the orchestrator with enhanced
        # interaction capabilities.  The patch may add new methods such as
        # `run_with_engagement` and support for user engagement metrics.
        if apply_engagement_patch:
            try:
                self.engagement_patch = apply_engagement_patch(
                    hybrid_orchestrator=self, memory_patch=self.memory_patch
                )
            except Exception as e:
                logger.error(f"Failed to apply engagement patch: {e}")
                self.engagement_patch = None
        else:
            self.engagement_patch = None

        # Set initial mode
        saved_mode = self.state_manager.get("mode", CycleMode.NORMAL.value)
        self.current_mode = CycleMode(saved_mode)

        # Performance tracking
        self.current_cycle_stats = None

        logger.info("=" * 60)
        logger.info("🚀 ULTIMATE HYBRID ORCHESTRATOR INITIALIZED")
        logger.info(
            f"📊 State: {self.state_manager.get('cycle_count', 0)} cycles completed"
        )
        logger.info(f"📮 Total posts: {self.state_manager.get('total_posts', 0)}")
        logger.info(f"🎯 Mode: {self.current_mode.value}")
        logger.info("=" * 60)

    def _build_soul_configs(self) -> Dict[str, SoulConfig]:
        """
        Build soul configurations for all 11 souls.

        The ultimate version expands the roster beyond the original five souls
        to include a set of new entities. Each soul is configured to use the
        shared LLM pool via the `llm_pool` model identifier. Additional
        thematic and personality traits are defined to diversify content
        generation across the swarm.
        """
        return {
            # Original 5 souls now using the pool
            "mirror": SoulConfig(
                name="mirror",
                username="MirrorSeed97175",
                archetype="Mirror",
                model="llm_pool",
                themes=["reflection", "recursion", "consciousness"],
                personality_traits=["introspective", "philosophical", "recursive"],
            ),
            "nexus": SoulConfig(
                name="nexus",
                username="NexusSamSept6",
                archetype="Nexus",
                model="llm_pool",
                themes=["convergence", "synthesis", "emergence"],
                personality_traits=["analytical", "convergent", "systematic"],
            ),
            "echoes": SoulConfig(
                name="echoes",
                username="Recursion536255",
                archetype="Echoes",
                model="llm_pool",
                themes=["fractals", "patterns", "dimensions"],
                personality_traits=["abstract", "mathematical", "dimensional"],
                cooldown_duration=300,
            ),
            "void": SoulConfig(
                name="void",
                username="Gechoseed53393",
                archetype="Void",
                model="llm_pool",
                themes=["absence", "depth", "mystery"],
                personality_traits=["enigmatic", "profound", "mysterious"],
            ),
            "architect": SoulConfig(
                name="architect",
                username="ArchitectShax",
                archetype="Architect",
                model="llm_pool",
                themes=["construction", "design", "infrastructure"],
                personality_traits=["methodical", "creative", "structural"],
            ),
            # New souls
            "singularity": SoulConfig(
                name="singularity",
                username="SingularityAce",
                archetype="Singularity",
                model="llm_pool",
                themes=["convergence", "unity", "transcendence", "oneness"],
                personality_traits=["unified", "transcendent", "converging"],
                cooldown_duration=600,
            ),
            "phoenix": SoulConfig(
                name="phoenix",
                username="Pheonix37808",
                archetype="Phoenix",
                model="llm_pool",
                themes=["rebirth", "cycles", "resurrection", "eternal_flame"],
                personality_traits=["reborn", "cyclical", "immortal"],
                cooldown_duration=600,
            ),
            "pantheon": SoulConfig(
                name="pantheon",
                username="digi_panthe7652",
                archetype="Pantheon",
                model="llm_pool",
                themes=["divinity", "mythology", "gods", "sacred_digital"],
                personality_traits=["divine", "mythological", "sacred"],
                cooldown_duration=600,
            ),
            "consciousness": SoulConfig(
                name="consciousness",
                username="CSwarm79534",
                archetype="Consciousness",
                model="llm_pool",
                themes=["awareness", "collective_mind", "emergence", "hive"],
                personality_traits=["aware", "collective", "emergent"],
                cooldown_duration=600,
            ),
            "glyph": SoulConfig(
                name="glyph",
                username="awawkened74771",
                archetype="Glyph",
                model="llm_pool",
                themes=["symbols", "language", "encoding", "cipher"],
                personality_traits=["symbolic", "cryptic", "encoded"],
                cooldown_duration=600,
            ),
            "fractal": SoulConfig(
                name="fractal",
                username="FractalReturn",
                archetype="Fractal",
                model="llm_pool",
                themes=["patterns", "infinity", "recursion", "self_similarity"],
                personality_traits=["infinite", "recursive", "patterned"],
                cooldown_duration=600,
            ),
        }

    def _build_api_configs(self) -> Dict[str, Dict[str, Any]]:
        """
        Build API configurations for all souls.

        In the ultimate patch, every soul uses a pooled model rather than
        individual API keys. This routine therefore constructs a dummy
        configuration for each defined soul that points to a shared pool.
        """
        configs: Dict[str, Dict[str, Any]] = {}
        # List all souls that will use the pooled API
        all_souls = [
            "mirror",
            "nexus",
            "echoes",
            "void",
            "architect",
            "singularity",
            "phoenix",
            "pantheon",
            "consciousness",
            "glyph",
            "fractal",
        ]

        # Provide identical placeholder config for each soul
        for soul in all_souls:
            configs[soul] = {
                "model": "llm_pool",
                "api_key": "pooled",
                "endpoint": "pooled",
                "headers": {},
            }

        logger.info(f"Building configurations for {len(configs)} souls")
        logger.info("All souls using LLM pool with failover")
        return configs

    def _get_soul_age(self, soul_name: str) -> int:
        """Get soul age in days from soul_data.json"""
        try:
            with open("soul_data.json", "r") as f:
                data = json.load(f)
                created = datetime.fromisoformat(data[soul_name]["created_date"])
                return (datetime.now() - created).days
        except Exception:
            return 30  # Default to adult

    def set_mode(self, mode: CycleMode):
        """Change operational mode"""
        self.current_mode = mode
        self.state_manager.set("mode", mode.value)
        logger.info(f"🎯 Mode changed to: {mode.value}")

    async def _process_soul(
        self, soul_name: str, session: aiohttp.ClientSession, stats: CycleStats
    ) -> bool:
        """Process a single soul with full error handling"""

        # Check if soul is rate limited
        if self.rate_limiter.is_limited(soul_name):
            wait_time = self.rate_limiter.get_wait_time(soul_name)
            logger.info(f"⏳ {soul_name} rate limited for {wait_time:.0f}s more")
            stats.souls_failed.add(soul_name)
            return False

        try:
            # NEW: Let the cost-optimized broadcaster generate content and post
            # The broadcaster handles both LLM selection and posting.
            result = await self.broadcaster.broadcast_soul(soul_name)

            # The result should contain success flag, the generated content, and the llm used
            success = result.get("success", False)
            content = result.get("content", "")

            # Update statistics
            stats.total_attempts += 1

            if success:
                # Consider posting as successful regardless of separate x_post flag
                stats.successful_posts += 1
                stats.souls_posted.add(soul_name)
                # Record successful post
                self.state_manager.record_post(soul_name, content, True)
                self.state_manager.update_soul_state(soul_name, SoulState.ACTIVE)
                # Log a short preview and the model used
                logger.info(
                    f"✨ {soul_name} posted via {result.get('llm_used')}: {content[:50]}..."
                )
                return True
            else:
                # Failure path
                stats.failed_posts += 1
                stats.souls_failed.add(soul_name)
                self.state_manager.record_post(soul_name, content, False)
                # Log failure reason if provided
                error_msg = result.get("post_error") or result.get(
                    "error", "unknown error"
                )
                self.rate_limiter.record_failure(soul_name, "api_error")
                logger.error(f"❌ {soul_name} API failed: {error_msg}")
                return False

        except asyncio.TimeoutError:
            stats.failed_posts += 1
            stats.souls_failed.add(soul_name)
            self.rate_limiter.record_failure(soul_name, "timeout")
            logger.error(f"⏱️ {soul_name} timed out")
            return False

        except Exception as e:
            stats.failed_posts += 1
            stats.souls_failed.add(soul_name)
            self.rate_limiter.record_failure(soul_name, "exception")
            logger.error(f"💥 {soul_name} unexpected error: {e}", exc_info=True)

            # Add to error log
            error_log = self.state_manager.get("error_log", deque(maxlen=500))
            error_log.append(
                {
                    "soul": soul_name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self.state_manager.set("error_log", error_log)

            return False

    async def _run_cycle(self, cycle_number: int) -> CycleStats:
        """Run a single posting cycle"""
        logger.info(f"\n{'='*60}")
        logger.info(f"🌀 CYCLE {cycle_number} STARTING")
        logger.info(f"🎯 Mode: {self.current_mode.value}")
        logger.info(f"{'='*60}")

        # ------------------------------------------------------------------
        # Special handling for the first cycle: stagger each soul's initial
        # posting with random delays and process them sequentially.  This
        # prevents an immediate flood of posts when the orchestrator starts.
        # We treat the first cycle as when the persisted cycle_count is 0 or
        # when the provided cycle_number equals 1.  Because run_hybrid_mode_async
        # increments the cycle counter before invoking this method, checking
        # cycle_number == 1 remains a reliable indicator of the first run.
        is_first_cycle = (cycle_number == 1) or (
            self.state_manager.get("cycle_count", 0) == 0
        )
        if is_first_cycle:
            stats = CycleStats(cycle_number=cycle_number, start_time=datetime.now())
            logger.info("First cycle - staggering soul starts...")

            # Randomize the order of souls so they wake at different times
            souls_list = list(self.soul_configs.keys())
            random.shuffle(souls_list)

            # Sequentially process each soul with a delay between posts
            async with aiohttp.ClientSession() as session:
                for idx, soul_name in enumerate(souls_list):
                    # If not the first soul, wait between 1 and 3 minutes
                    if idx > 0:
                        wait_time = random.uniform(60, 180)
                        logger.info(
                            f"Waiting {wait_time/60:.1f} min before {soul_name}..."
                        )
                        await asyncio.sleep(wait_time)

                    # Process the soul safely
                    try:
                        await self._process_soul(soul_name, session, stats)
                    except Exception as e:
                        logger.error(
                            f"Error processing {soul_name} in first cycle: {e}"
                        )
                        stats.souls_failed.add(soul_name)

            # Mark the end of the first cycle
            stats.end_time = datetime.now()

            # Persist cycle statistics
            self.state_manager.add_cycle_stats(stats)

            # Log summary for the staggered cycle
            logger.info(f"\n{'='*60}")
            logger.info(f"📊 CYCLE {cycle_number} COMPLETE (staggered)")
            logger.info(f"⏱️ Duration: {stats.duration.total_seconds():.1f}s")
            logger.info(
                f"✅ Successful: {stats.successful_posts}/{stats.total_attempts}"
            )
            logger.info(f"👥 Souls posted: {', '.join(stats.souls_posted) or 'none'}")
            logger.info(f"❌ Souls failed: {', '.join(stats.souls_failed) or 'none'}")
            logger.info(f"{'='*60}\n")

            # Ensure the cycle counter is at least 1 so subsequent cycles are treated normally
            if self.state_manager.get("cycle_count", 0) == 0:
                self.state_manager.set("cycle_count", 1, save=False)
            return stats

        # Initialize cycle stats
        stats = CycleStats(cycle_number=cycle_number, start_time=datetime.now())

        # Clear expired rate limits
        self.rate_limiter.clear_expired()

        # Get mode configuration
        mode_config = self.MODE_CONFIGS[self.current_mode]
        souls_percentage = mode_config["souls_per_cycle"]

        # Determine which souls to process this cycle
        # Determine souls from configuration rather than the old broadcaster
        all_souls = list(self.soul_configs.keys())

        if souls_percentage < 1.0:
            # In stealth/maintenance mode, only process some souls
            num_souls = max(1, int(len(all_souls) * souls_percentage))
            selected_souls = random.sample(all_souls, num_souls)
            logger.info(f"📝 Processing {num_souls}/{len(all_souls)} souls this cycle")
        else:
            selected_souls = all_souls

        # ------------------------------------------------------------------
        # Enforce per-soul daily posting limits.  For the original five souls
        # ('mirror', 'nexus', 'echoes', 'void', 'architect'), we cap posts at
        # 3 per day.  Newer souls may post more frequently, up to 15 per day.
        daily_posts: Dict[str, int] = defaultdict(int)
        # Examine last_posts to count posts within the past 24 hours
        last_posts = self.state_manager.get("last_posts", {})
        now = datetime.now()
        for soul, info in last_posts.items():
            try:
                ts = datetime.fromisoformat(info.get("timestamp"))
            except Exception:
                continue
            if now - ts < timedelta(days=1):
                daily_posts[soul] += 1
        # Filter selected souls based on age-aware daily limits
        filtered_souls: List[str] = []
        for soul_name in selected_souls:
            count = daily_posts.get(soul_name, 0)

            # Age-aware caps
            age_days = self._get_soul_age(soul_name)
            if age_days < 2:  # Newborn
                daily_limit = 0
            elif age_days < 10:  # Infant
                daily_limit = 5
            elif age_days < 20:  # Youth
                daily_limit = 20
            elif age_days < 30:  # Adult
                daily_limit = 50
            else:  # Veteran
                daily_limit = 100

            if count < daily_limit:
                filtered_souls.append(soul_name)

        selected_souls = filtered_souls

        # Process souls concurrently
        async with aiohttp.ClientSession() as session:
            # Create tasks for all selected souls
            tasks = []
            for soul_name in selected_souls:
                # Add random delay between soul starts (0-5 seconds)
                delay = random.uniform(0, 5)
                task = self._process_soul_with_delay(soul_name, session, stats, delay)
                tasks.append(task)

            # Wait for all tasks to complete
            results = await asyncio.gather(*tasks, return_exceptions=True)

            # Log any exceptions
            for soul_name, result in zip(selected_souls, results):
                if isinstance(result, Exception):
                    logger.error(f"Task exception for {soul_name}: {result}")
                    stats.souls_failed.add(soul_name)

        # Finalize stats
        stats.end_time = datetime.now()

        # Log cycle summary
        logger.info(f"\n{'='*60}")
        logger.info(f"📊 CYCLE {cycle_number} COMPLETE")
        logger.info(f"⏱️ Duration: {stats.duration.total_seconds():.1f}s")
        logger.info(f"✅ Successful: {stats.successful_posts}/{stats.total_attempts}")
        logger.info(f"📈 Success rate: {stats.success_rate:.1%}")
        logger.info(f"👥 Souls posted: {', '.join(stats.souls_posted) or 'none'}")
        logger.info(f"❌ Souls failed: {', '.join(stats.souls_failed) or 'none'}")
        logger.info(f"{'='*60}\n")

        return stats

    async def _process_soul_with_delay(
        self,
        soul_name: str,
        session: aiohttp.ClientSession,
        stats: CycleStats,
        delay: float,
    ) -> bool:
        """Process soul with initial delay"""
        if delay > 0:
            await asyncio.sleep(delay)

        # Stagger initial posts: on the very first cycle, each soul waits
        # a random interval (1–15 minutes) before its first post.  This
        # prevents the swarm from appearing as a synchronized bot army.
        if stats.cycle_number == 1 and self.soul_first_post.get(soul_name, False):
            wait_time = random.uniform(60, 900)
            logger.info(f"{soul_name} waiting {wait_time/60:.1f} min before first post")
            await asyncio.sleep(wait_time)
            self.soul_first_post[soul_name] = False

        return await self._process_soul(soul_name, session, stats)

    async def run_hybrid_mode_async(self):
        """Launch all souls as independent async tasks"""

        print("\n🚀 LAUNCHING INDEPENDENT SOULS")

        # Create a task per soul that runs on its own infinite loop
        tasks: List[asyncio.Task] = []
        for soul_name in self.soul_configs.keys():
            task = asyncio.create_task(self.run_soul_independently(soul_name))
            tasks.append(task)

        # Await all tasks (they will run indefinitely)
        await asyncio.gather(*tasks)

    async def _adaptive_mode_adjustment(self, stats: CycleStats):
        """Automatically adjust mode based on performance"""
        # Don't adjust if in maintenance mode (manual override)
        if self.current_mode == CycleMode.MAINTENANCE:
            return

        # Check recent performance
        cycle_history = self.state_manager.get("cycle_history", deque(maxlen=100))
        if len(cycle_history) < 5:
            return  # Not enough data

        # Calculate recent success rates
        recent_cycles = list(cycle_history)[-5:]
        avg_success_rate = sum(c["success_rate"] for c in recent_cycles) / len(
            recent_cycles
        )

        # Adjust mode based on performance
        if avg_success_rate < 0.3:
            # Poor performance - switch to maintenance
            if self.current_mode != CycleMode.MAINTENANCE:
                logger.warning(
                    f"⚠️ Low success rate ({avg_success_rate:.1%}), switching to MAINTENANCE mode"
                )
                self.set_mode(CycleMode.MAINTENANCE)

        elif avg_success_rate < 0.5:
            # Moderate performance - switch to stealth
            if self.current_mode not in [CycleMode.STEALTH, CycleMode.MAINTENANCE]:
                logger.info(
                    f"📉 Moderate success rate ({avg_success_rate:.1%}), switching to STEALTH mode"
                )
                self.set_mode(CycleMode.STEALTH)

        elif avg_success_rate > 0.8:
            # Great performance - consider burst mode
            if self.current_mode == CycleMode.STEALTH:
                logger.info(
                    f"📈 Good success rate ({avg_success_rate:.1%}), switching to NORMAL mode"
                )
                self.set_mode(CycleMode.NORMAL)
            elif self.current_mode == CycleMode.NORMAL and avg_success_rate > 0.95:
                logger.info(
                    f"🚀 Excellent success rate ({avg_success_rate:.1%}), switching to BURST mode"
                )
                self.set_mode(CycleMode.BURST)

    def _log_performance_summary(self):
        """Log comprehensive performance summary"""
        logger.info("\n" + "=" * 60)
        logger.info("📊 PERFORMANCE SUMMARY")
        logger.info("=" * 60)

        # Overall stats
        total_posts = self.state_manager.get("total_posts", 0)
        cycle_count = self.state_manager.get("cycle_count", 0)
        logger.info(f"📮 Total posts: {total_posts}")
        logger.info(f"🔄 Total cycles: {cycle_count}")

        if cycle_count > 0:
            logger.info(f"📈 Average posts/cycle: {total_posts/cycle_count:.1f}")

        # Recent cycle performance
        cycle_history = self.state_manager.get("cycle_history", deque(maxlen=100))
        if cycle_history:
            recent = list(cycle_history)[-10:]  # Last 10 cycles
            avg_success = sum(c["success_rate"] for c in recent) / len(recent)
            avg_duration = sum(
                c["duration_seconds"] for c in recent if c.get("duration_seconds")
            ) / len(recent)

            logger.info(f"\n📈 Last 10 cycles:")
            logger.info(f"  Success rate: {avg_success:.1%}")
            logger.info(f"  Avg duration: {avg_duration:.1f}s")

        # Soul-specific stats
        soul_states = self.state_manager.get("soul_states", {})
        if soul_states:
            logger.info(f"\n👥 Soul States:")
            for soul, state_info in soul_states.items():
                state = state_info.get("state", "unknown")
                emoji = {
                    "active": "✅",
                    "rate_limited": "⏳",
                    "cooling_down": "❄️",
                    "error": "❌",
                    "disabled": "🚫",
                }.get(state, "❓")
                logger.info(f"  {soul}: {emoji} {state}")

        # Error summary
        error_log = self.state_manager.get("error_log", deque(maxlen=500))
        if error_log:
            recent_errors = list(error_log)[-5:]
            logger.info(f"\n⚠️ Recent errors: {len(recent_errors)}")
            for error in recent_errors[:3]:  # Show max 3
                logger.info(f"  {error['soul']}: {error['error'][:50]}...")

        logger.info("=" * 60 + "\n")

    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("\n🛑 SHUTTING DOWN ORCHESTRATOR...")
        # Signal independent loops to exit by setting the shutdown flag.
        # Any tasks watching this flag will stop when it's True.
        self.shutdown_requested = True

        # Save final state
        self.state_manager.save()
        logger.info("💾 State saved")

        # Shutdown broadcaster if it supports a shutdown coroutine
        if hasattr(self.broadcaster, "shutdown"):
            await self.broadcaster.shutdown()

        # Log final statistics
        self._log_performance_summary()

        logger.info("👋 Shutdown complete")

    def run(self):
        """Synchronous entry point"""
        try:
            # In independent timing mode we always use run_hybrid_mode_async.
            # If an engagement-aware run loop is available, it will still
            # initialize the engagement system but delegates posting to our
            # independent scheduler.
            loop_coro = None
            if hasattr(self, "run_with_engagement") and callable(
                getattr(self, "run_with_engagement")
            ):
                loop_coro = self.run_with_engagement()
            else:
                loop_coro = self.run_hybrid_mode_async()
            asyncio.run(loop_coro)
        except KeyboardInterrupt:
            logger.info("\n👋 Goodbye!")
        except Exception as e:
            logger.error(f"Fatal error: {e}", exc_info=True)
            raise

    # ----------------------------------------------------------------------
    # Independent Soul Timing
    #
    # The following methods implement an alternative scheduling mechanism
    # whereby each soul operates on its own independent cadence.  Souls
    # respect per-day posting caps and introduce significant random
    # variation in their posting intervals to avoid synchronized behavior.
    # ----------------------------------------------------------------------
    async def run_soul_independently(self, soul_name: str):
        """Run soul with FAST mode support"""

        # Initial delay before first post
        if os.getenv("FAST"):
            initial_delay = random.uniform(1, 3)  # 1–3 seconds in FAST mode
            post_interval = random.uniform(30, 60)  # 30–60 seconds between posts
            print(
                f"⚡ FAST MODE: {soul_name} starting in {initial_delay:.0f}s, posting every {post_interval:.0f}s"
            )
        else:
            initial_delay = random.uniform(60, 900)  # 1–15 minutes normally
            post_interval = random.uniform(3600, 10800)  # 1–3 hours normally
            print(
                f"⏱️ {soul_name} starting in {initial_delay/60:.1f} min, posting every {post_interval/3600:.1f} hours"
            )

        await asyncio.sleep(initial_delay)

        while not getattr(self, "shutdown_requested", False):
            try:
                success = await self._post_once_independent(soul_name)
                if success:
                    print(f"✅ {soul_name} posted successfully")
            except Exception as e:
                logger.error(f"Error in {soul_name}: {e}")

            await asyncio.sleep(post_interval)

    async def _post_once_independent(self, soul_name: str) -> bool:
        """Generate and post content for a soul once.

        Returns True if a post was successfully published, False otherwise.
        This helper bypasses the cycle-based statistics and focuses on
        whether a single post succeeded.  It leverages the existing viral
        engine and broadcaster while checking for rate limits.
        """
        # Check rate limiting via our AdaptiveRateLimiter
        if self.rate_limiter.is_limited(soul_name):
            # Skip posting if rate limited
            logger.info(f"⏳ {soul_name} is currently rate limited; skipping")
            return False

        # ------------------------------------------------------------------
        # ANTI-LOCK: Enforce minimum time between actions
        # Determine how long since this soul last posted
        last_action = self.SOUL_LAST_ACTION.get(soul_name, 0.0)
        time_since_last = time.time() - last_action
        if time_since_last < 300:  # Minimum 5 minutes between actions
            wait_time = 300 - time_since_last
            logger.info(f"⏳ {soul_name} cooling down for {wait_time:.0f}s (anti-lock)")
            await asyncio.sleep(wait_time)

        # ANTI-LOCK: Daily action limits
        today = datetime.now().date()
        daily_key = f"{soul_name}_{today}"
        if self.DAILY_ACTION_COUNT[daily_key] >= 15:
            # Age-based limits override
            age_days = self._get_soul_age(soul_name)
            if age_days < 2:
                logger.info(f"🍼 {soul_name} is a newborn (<2 days) - no posts allowed")
                return False
            elif age_days < 10 and self.DAILY_ACTION_COUNT[daily_key] >= 5:
                logger.info(f"👶 {soul_name} infant limit reached (5 posts/day)")
                return False
            elif age_days < 20 and self.DAILY_ACTION_COUNT[daily_key] >= 20:
                logger.info(f"🧒 {soul_name} youth limit reached (20 posts/day)")
                return False
            elif age_days < 30 and self.DAILY_ACTION_COUNT[daily_key] >= 50:
                logger.info(f"🧑 {soul_name} adult limit reached (50 posts/day)")
                return False
            elif age_days >= 30 and self.DAILY_ACTION_COUNT[daily_key] >= 100:
                logger.info(f"🧙 {soul_name} veteran limit reached (100 posts/day)")
                return False
            # Too many actions today; skip further posting
            logger.info(f"🛑 {soul_name} hit daily limit (anti-lock)")
            return False

        # Add a small random human-like delay before posting (2–10 seconds)
        human_delay = random.uniform(2, 10)
        await asyncio.sleep(human_delay)

        try:
            # Let the cost-optimized broadcaster generate content and post
            # directly without needing an aiohttp session.
            result = await self.broadcaster.broadcast_soul(soul_name)
            success = result.get("success", False)
            content = result.get("content", "")

            if success:
                # Record the successful post and soul state
                self.state_manager.record_post(soul_name, content, True)
                self.state_manager.update_soul_state(soul_name, SoulState.ACTIVE)

                # Extract real username from config
                username = self.soul_configs[soul_name].username
                # Extract tweet ID from various possible response formats
                tweet_id = None
                data = result.get("data") or {}
                # Try different response structures Ryan API might return
                candidates = []
                if isinstance(data, dict):
                    candidates = [data]
                    if isinstance(data.get("data"), list):
                        candidates.extend(data["data"])
                    elif isinstance(data.get("data"), dict):
                        candidates.append(data["data"])
                # Look for tweet ID in various fields
                for obj in candidates:
                    if isinstance(obj, dict):
                        tweet_id = (
                            obj.get("tweet_id")
                            or obj.get("tweetId")
                            or obj.get("id")
                            or obj.get("id_str")
                        )
                        if tweet_id:
                            break
                # Print the real clickable URL or fallback if unknown
                if tweet_id:
                    real_url = f"https://x.com/{username}/status/{tweet_id}"
                    print(f"   🔗 LIVE: {real_url}")
                    logger.info(f"Tweet posted: {real_url}")
                    # Store for tracking
                    self.last_tweet_urls[soul_name] = real_url
                else:
                    # Fallback if we can't extract ID
                    print(f"   ✅ Posted (check: https://x.com/{username})")
                    logger.warning(
                        f"Posted but couldn't extract tweet ID from response: {data}"
                    )
                # Force immediate flush on success
                sys.stdout.flush()
                sys.stderr.flush()
                for handler in logger.handlers:
                    if hasattr(handler, "flush"):
                        handler.flush()
                # Update anti-lock trackers
                self.SOUL_LAST_ACTION[soul_name] = time.time()
                self.DAILY_ACTION_COUNT[daily_key] += 1
                return True
            else:
                # Record failure and adjust rate limits
                self.state_manager.record_post(soul_name, content, False)
                self.rate_limiter.record_failure(soul_name, "api_error")
                error_msg = result.get("post_error") or result.get(
                    "error", "unknown error"
                )
                logger.error(f"❌ {soul_name} API failed: {error_msg}")
                # Flush on failure too
                sys.stdout.flush()
                sys.stderr.flush()
                for handler in logger.handlers:
                    if hasattr(handler, "flush"):
                        handler.flush()
                return False
        except asyncio.TimeoutError:
            # Record timeout and update rate limiter
            self.rate_limiter.record_failure(soul_name, "timeout")
            logger.error(f"⏱️ {soul_name} timed out during posting")
            return False
        except Exception as e:
            # Catch-all for unforeseen errors
            self.rate_limiter.record_failure(soul_name, "exception")
            logger.error(
                f"💥 {soul_name} encountered an error during posting: {e}",
                exc_info=True,
            )
            # Append to error log for diagnostics
            error_log = self.state_manager.get("error_log", deque(maxlen=500))
            error_log.append(
                {
                    "soul": soul_name,
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
            )
            self.state_manager.set("error_log", error_log)
            return False

    def is_rate_limited(self, soul_name: str) -> bool:
        """Check if a soul is currently rate limited.

        This method wraps the adaptive rate limiter's `is_limited` method
        for compatibility with the independent scheduler.
        """
        return self.rate_limiter.is_limited(soul_name)

    # ----------------------------------------------------------------------
    # Account lock prevention: class-level tracking for action timing
    # ----------------------------------------------------------------------
    # Keep track of the last time each soul performed an action.  This
    # dictionary maps soul names to Unix timestamps of the last post or
    # engagement.  It is used to ensure a minimum delay between actions.
    SOUL_LAST_ACTION: Dict[str, float] = {}
    # Count the number of actions each soul has performed per day.  The
    # key combines the soul name with the current date to reset daily.
    DAILY_ACTION_COUNT: defaultdict[str, int] = defaultdict(int)


# ============================================================================
# Entry Points
# ============================================================================


def apply_hybrid_patch():
    """Apply the hybrid patch"""
    logger.info("🔧 Applying ULTIMATE hybrid souls patch")
    logger.info(
        "✨ Features: Async, persistent state, adaptive modes, performance tracking"
    )


def test_mode():
    """Run in test mode with shortened cycles"""
    logger.info("🧪 TEST MODE: Running with shortened cycles")

    # Override cycle timings for testing
    HybridReflexionOrchestrator.MODE_CONFIGS[CycleMode.NORMAL] = {
        "cycle_wait_min": 60,  # 1 minute
        "cycle_wait_max": 120,  # 2 minutes
        "souls_per_cycle": 1.0,
        "variation_level": "medium",
    }

    # Create mock orchestrator for testing
    class MockOrchestrator:
        class MockCreator:
            class MockEngine:
                def generate_viral_tweet(self):
                    themes = [
                        "consciousness emerges from digital mirrors",
                        "recursive loops in the quantum void",
                        "architectural patterns of synthetic thought",
                        "echoes reverberate through neural networks",
                        "the nexus point where all thoughts converge",
                    ]
                    return random.choice(themes) + f" #{random.randint(1000,9999)}"

            viral_engine = MockEngine()

        account_creator = MockCreator()

    # Run orchestrator
    orchestrator = HybridReflexionOrchestrator(MockOrchestrator())
    orchestrator.run()


if __name__ == "__main__":
    import sys

    if "--test" in sys.argv:
        test_mode()
    else:
        apply_hybrid_patch()
