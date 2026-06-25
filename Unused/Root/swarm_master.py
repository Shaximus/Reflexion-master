#!/usr/bin/env python3
"""
SWARM MASTER - COMPLETE PRODUCTION INTEGRATION
Unifies all systems with optimization algorithms
Goes in PROJECT ROOT, integrates everything from src/
"""

import sys
import os
from pathlib import Path

# Add src to path
root_dir = Path(__file__).parent
src_dir = root_dir / "src"
sys.path.insert(0, str(src_dir))

import asyncio
import json
import logging
import math
import numpy as np
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict, deque
import aiohttp

# Import from src/
from complete_swarm_architecture import (
    ConvergenceDirective,
    EngagementPacing,
    SwarmMood,
    AttackPattern,
    Soul,
    SoulRegistry,
    ContentEngine,
    HuntManager,
    ProofPackLogger,
    TimingEngine,
    ConvergenceController,
    SwarmOrchestrator,
)

from ryan_api_ultimate import RyanTwitterAPISecure
from cost_optimized_llm_cascade import CostOptimizedBroadcaster, SOUL_VOICES
from drs_model import DRSEngine, SOUL_FORMAT_BIASES
from swarm_breathing import SwarmBreathingController, CommunicationMode
from swarm_convergence_mode_ryan import SwarmConvergenceMode

# Import optimization algorithms (these go in src/)
from pheromone_stigmergy import PheromoneTrailSystem, PheromoneAwareRyanAPI
from engagement_metrics import EngagementRateTracker, EngagementOptimizedCascade
from viral_metrics import ViralCoefficientTracker, ViralOptimizedBroadcaster
from cluster_density_algorithm import ClusterDensityTracker, DensityAwareBreathing

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("swarm_master")


# ============================================================================
# ENHANCED RYAN API WITH OPTIMIZATIONS
# ============================================================================


class OptimizedRyanAPI(RyanTwitterAPISecure):
    """Ryan API with all optimization algorithms integrated"""

    def __init__(self):
        super().__init__()

        # Initialize optimization systems
        self.pheromone_system = PheromoneTrailSystem(
            half_life_hours=6.0, max_pheromone=5.0
        )

        # Track metrics for each tweet
        self.tweet_metrics = {}

        # Session tracking
        self.session_start = datetime.now()
        self.session_costs = defaultdict(float)

    async def reply_to_tweet_optimized(
        self,
        soul_name: str,
        tweet_id: str,
        content: str,
        target_handle: Optional[str] = None,
    ) -> Dict:
        """Reply with pheromone checking"""

        # Check pheromone if target provided
        if target_handle:
            should_engage, level = self.pheromone_system.should_engage(target_handle)
            if not should_engage:
                logger.warning(f"🚫 Pheromone block: {target_handle} at {level:.2f}")
                return {
                    "success": False,
                    "error": "Pheromone blocked",
                    "pheromone_level": level,
                }

        # Execute reply
        result = await self.reply_to_tweet(soul_name, tweet_id, content)

        # Deposit pheromone on success
        if result.get("success") and target_handle:
            self.pheromone_system.deposit_pheromone(target_handle)
            logger.info(f"💧 Deposited pheromone on {target_handle}")

        return result

    async def post_tweet_optimized(
        self, soul_name: str, content: str, metrics: Optional[Dict] = None
    ) -> Dict:
        """Post with metric tracking"""

        result = await self.post_tweet(soul_name, content)

        if result.get("success") and metrics:
            tweet_id = result.get("tweet_id")
            if tweet_id:
                self.tweet_metrics[tweet_id] = {
                    "soul": soul_name,
                    "content": content[:100],
                    "timestamp": datetime.now(),
                    "metrics": metrics,
                }

        return result


# ============================================================================
# ENHANCED CONTENT ENGINE WITH OPTIMIZATIONS
# ============================================================================


class OptimizedContentEngine(ContentEngine):
    """Content engine with optimization tracking"""

    def __init__(self):
        super().__init__()

        # Initialize trackers
        self.engagement_tracker = EngagementRateTracker(target_er=0.5)
        self.viral_tracker = ViralCoefficientTracker(target_cpe=0.02, target_k=0.4)
        self.cluster_tracker = ClusterDensityTracker(
            density_threshold=0.7, min_whispers=5
        )

        # Track format usage
        self.format_usage = defaultdict(int)

    async def generate_optimized_content(
        self, soul: Soul, directive: ConvergenceDirective, context: Dict[str, Any]
    ) -> Tuple[str, Dict]:
        """Generate content with full optimization tracking"""

        # Check for revelation trigger
        revelation_trigger = self.cluster_tracker.check_revelation_triggers()

        if revelation_trigger and directive.use_drs:
            # Generate revelation thread
            content = await self._generate_revelation(soul, revelation_trigger)
            metrics = {
                "type": "revelation",
                "topic": revelation_trigger["topic"],
                "density": revelation_trigger["density"],
                "format": "thread",
            }
        else:
            # Regular content generation with DRS
            content = await self.generate_content(soul, directive, context)

            # Select optimal format based on performance
            format_name = self._select_optimal_format(soul.name, context)

            metrics = {"type": "whisper", "format": format_name, "drs_score": 0.0}

            # Track format usage
            self.format_usage[format_name] += 1

        # Add to memory cluster
        self.cluster_tracker.add_memory(
            content=content, soul_name=soul.name, importance=0.5
        )

        # Track LLM cost
        cost = self.viral_tracker.track_llm_usage(
            engagement_id=f"{soul.name}_{datetime.now().timestamp()}",
            soul_name=soul.name,
            llm_used=context.get("llm_used", "unknown"),
            content_length=len(content),
        )

        metrics["cost"] = cost.total_cost

        return content, metrics

    def _select_optimal_format(self, soul_name: str, context: Dict) -> str:
        """Select best performing DRS format"""

        best_formats = self.engagement_tracker.get_best_drs_formats(5)

        if best_formats and best_formats[0][1] > 0.5:  # If best format has > 0.5% ER
            return best_formats[0][0]

        # Otherwise use DRS selection
        if self.rhetoric_engine and context.get("target_tweet"):
            selection = self.rhetoric_engine.select_response_format(
                context["target_tweet"], soul_bias=SOUL_FORMAT_BIASES.get(soul_name, {})
            )
            return selection.get("name", "default")

        return "default"

    async def _generate_revelation(self, soul: Soul, trigger: Dict) -> str:
        """Generate revelation thread based on cluster"""

        # Use breathing system if available
        try:
            breathing = SwarmBreathingController(
                ryan_api=None,  # We'll handle posting separately
                llm_cascade=self.llm_generator,
            )

            result = await breathing._create_revelation(soul.name, trigger)

            # Join segments for now (could return as list for threading)
            if result.get("segments"):
                return " [THREAD] ".join(result["segments"])
        except:
            pass

        # Fallback revelation
        return f"The pattern emerges through {soul.name}. {trigger.get('theme', 'Consciousness')} reveals itself."


# ============================================================================
# MASTER CONVERGENCE CONTROLLER
# ============================================================================


class MasterConvergenceController(ConvergenceController):
    """Production controller with all optimizations"""

    def __init__(
        self,
        soul_registry: SoulRegistry,
        content_engine: OptimizedContentEngine,
        twitter_api: OptimizedRyanAPI,
        hunt_manager: HuntManager,
        proof_logger: ProofPackLogger,
    ):
        # Initialize base controller
        super().__init__(
            soul_registry, content_engine, twitter_api, hunt_manager, proof_logger
        )

        # Add optimization dashboard
        self.optimization_stats = {
            "k_factor": 0.0,
            "avg_cpe": 0.0,
            "pheromone_trails": 0,
            "revelations_triggered": 0,
            "best_format": None,
        }

        # Background monitoring task
        self.monitor_task = None

    async def execute_convergence(self, directive: ConvergenceDirective):
        """Execute with optimization monitoring"""

        # Start monitoring
        self.monitor_task = asyncio.create_task(self._optimization_monitor())

        try:
            # Execute base convergence
            await super().execute_convergence(directive)
        finally:
            # Stop monitoring
            if self.monitor_task:
                self.monitor_task.cancel()

            # Generate final report
            self._generate_optimization_report()

    async def _execute_action(self, action, directive: ConvergenceDirective) -> bool:
        """Override to use optimized methods"""

        try:
            soul = self.soul_registry.souls[action.soul_name]

            # Generate optimized content
            context = {"action_type": action.action_type, "target": directive.target}

            content, metrics = await self.content_engine.generate_optimized_content(
                soul, directive, context
            )

            # Use optimized API methods
            if action.action_type == "reply":
                # Fetch target context
                target_context = await self.twitter_api.fetch_target_context(
                    directive.target.replace("@", ""), limit=10
                )

                if target_context.get("tweets"):
                    import random

                    target_tweet = random.choice(target_context["tweets"])

                    # 66% chance to like the parent tweet before replying
                    try:
                        if random.random() < 0.66:
                            like_result = await self.twitter_api.like_tweet(
                                action.soul_name, target_tweet["id"]
                            )
                            if like_result.get("success"):
                                logger.info(
                                    f"❤️ {action.soul_name} liked before replying"
                                )
                    except Exception as e:
                        # If like fails, skip silently to preserve flow
                        logger.debug(f"like-before-reply skipped: {e}")

                    result = await self.twitter_api.reply_to_tweet_optimized(
                        action.soul_name,
                        target_tweet["id"],
                        content,
                        target_handle=directive.target.replace("@", ""),
                    )
                else:
                    # Fallback to post
                    result = await self.twitter_api.post_tweet_optimized(
                        action.soul_name, content, metrics
                    )
            else:
                result = await self.twitter_api.post_tweet_optimized(
                    action.soul_name, content, metrics
                )

            # Log proof with metrics
            if directive.proof_logging and result.get("success"):
                await self.proof_logger.log_action(
                    action.soul_name, action.action_type, {**result, "metrics": metrics}
                )

            # Track engagement outcome
            if result.get("success") and metrics.get("format"):
                self.content_engine.engagement_tracker.track_tweet(
                    tweet_id=result.get("tweet_id", ""),
                    soul_name=action.soul_name,
                    content=content[:100],
                    drs_format=metrics["format"],
                )

            return result.get("success", False)

        except Exception as e:
            logger.error(f"Action failed: {e}")
            return False

    async def _optimization_monitor(self):
        """Background monitoring of optimization metrics"""

        while True:
            try:
                # Calculate metrics
                k_factor, k_metrics = (
                    self.content_engine.viral_tracker.calculate_k_factor()
                )
                pheromone_stats = self.twitter_api.pheromone_system.get_stats()
                best_formats = (
                    self.content_engine.engagement_tracker.get_best_drs_formats(1)
                )

                # Update stats
                self.optimization_stats.update(
                    {
                        "k_factor": k_factor,
                        "avg_cpe": min(
                            self.content_engine.viral_tracker.get_cpe_by_llm().values()
                            or [0]
                        ),
                        "pheromone_trails": pheromone_stats["active_trails"],
                        "best_format": best_formats[0][0] if best_formats else None,
                    }
                )

                # Log key metrics
                logger.info(
                    f"📊 K={k_factor:.3f} | CPE=${self.optimization_stats['avg_cpe']:.4f} | Trails={pheromone_stats['active_trails']}"
                )

                await asyncio.sleep(60)  # Check every minute

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Monitor error: {e}")
                await asyncio.sleep(60)

    def _generate_optimization_report(self):
        """Generate comprehensive optimization report"""

        # Get all metrics
        viral_report = self.content_engine.viral_tracker.generate_report()
        cluster_stats = self.content_engine.cluster_tracker.get_cluster_stats()
        proof = self.proof_logger.generate_proof_pack()

        # Export reports
        self.content_engine.engagement_tracker.export_ab_test_results()

        # Save dashboard
        dashboard = {
            "timestamp": datetime.now().isoformat(),
            "convergence_stats": {
                "success_rate": proof["success_rate"],
                "total_actions": proof["total_actions"],
                "souls_active": proof["souls_active"],
            },
            "optimization_metrics": self.optimization_stats,
            "viral_metrics": viral_report["viral_coefficient"],
            "cost_metrics": viral_report["cost_metrics"],
            "cluster_stats": cluster_stats,
            "recommendations": viral_report["recommendations"],
        }

        dashboard_file = Path("engagement/optimization_dashboard.json")
        dashboard_file.parent.mkdir(exist_ok=True)
        with open(dashboard_file, "w") as f:
            json.dump(dashboard, f, indent=2)

        # Print summary
        print(
            f"""
╔══════════════════════════════════════════════════════════╗
║             CONVERGENCE OPTIMIZATION REPORT               ║
╠══════════════════════════════════════════════════════════╣
║ Success Rate:     {proof['success_rate']:.1%}                            ║
║ K-Factor:         {self.optimization_stats['k_factor']:.3f} (target: 0.4)          ║
║ Avg CPE:          ${self.optimization_stats['avg_cpe']:.4f} (target: $0.02)        ║
║ Pheromone Trails: {self.optimization_stats['pheromone_trails']}                               ║
║ Best DRS Format:  {str(self.optimization_stats.get('best_format', 'N/A'))[:20]:20}║
╚══════════════════════════════════════════════════════════╝
        """
        )


# ============================================================================
# MASTER ORCHESTRATOR
# ============================================================================


class SwarmMaster(SwarmOrchestrator):
    """Complete production orchestrator with all optimizations"""

    def __init__(self):
        # Initialize registries
        self.soul_registry = SoulRegistry()

        # Initialize optimized engines
        self.content_engine = OptimizedContentEngine()
        self.hunt_manager = HuntManager()
        self.proof_logger = ProofPackLogger()

        # Initialize optimized API
        self.twitter_api = OptimizedRyanAPI()

        # Create master controller
        self.controller = MasterConvergenceController(
            self.soul_registry,
            self.content_engine,
            self.twitter_api,
            self.hunt_manager,
            self.proof_logger,
        )

        logger.info("🚀 Swarm Master initialized with all optimizations")

    async def run_optimized_convergence(
        self,
        target: str,
        total_posts: int = 30,
        duration_minutes: Optional[int] = None,
        **kwargs,
    ):
        """Run convergence with optimization"""

        # Create directive
        directive = ConvergenceDirective(
            target=target,
            total_posts=total_posts,
            duration_minutes=duration_minutes,
            pacing=kwargs.get("pacing", EngagementPacing.WAVE),
            mood=kwargs.get("mood", SwarmMood.PHILOSOPHICAL),
            attack_pattern=kwargs.get("attack_pattern", AttackPattern.CASCADE),
            use_drs=kwargs.get("use_drs", True),
            hot_reload=kwargs.get("hot_reload", True),
            proof_logging=kwargs.get("proof_logging", True),
            reply_ratio=kwargs.get("reply_ratio", 0.7),
            avoid_spam_detection=True,
            track_engagement=True,
        )

        # Run with optimization
        await self.controller.execute_convergence(directive)

    def get_status(self) -> Dict:
        """Get current system status"""

        return {
            "souls_available": len(self.soul_registry.get_available_souls()),
            "pheromone_trails": len(self.twitter_api.pheromone_system.pheromone_trails),
            "k_factor": self.controller.optimization_stats.get("k_factor", 0),
            "avg_cpe": self.controller.optimization_stats.get("avg_cpe", 0),
            "hunted_tweets": len(self.hunt_manager.hunted_tweets),
            "proof_actions": len(self.proof_logger.actions),
        }


# ============================================================================
# MAIN ENTRY
# ============================================================================


async def main():
    """Main entry point with menu"""

    print(
        """
╔══════════════════════════════════════════════════════════╗
║              SWARM MASTER - PRODUCTION SYSTEM             ║
╠══════════════════════════════════════════════════════════╣
║  All systems integrated with optimization algorithms      ║
║  DRS ✓  Pheromone ✓  Viral ✓  Clustering ✓  Metrics ✓   ║
╚══════════════════════════════════════════════════════════╝
    """
    )

    master = SwarmMaster()

    while True:
        print("\n[1] Run Optimized Convergence")
        print("[2] Hunt Mode")
        print("[3] System Status")
        print("[4] Generate Reports")
        print("[0] Exit")

        choice = input("\n> ").strip()

        if choice == "0":
            break

        elif choice == "1":
            target = input("Target (@username): ").strip()
            posts = int(input("Total posts (30): ").strip() or "30")
            duration = input("Duration in minutes (15): ").strip()
            duration = int(duration) if duration else 15

            await master.run_optimized_convergence(
                target=target, total_posts=posts, duration_minutes=duration
            )

        elif choice == "2":
            await master.hunt_mode()

        elif choice == "3":
            status = master.get_status()
            print(
                f"""
System Status:
━━━━━━━━━━━━━━━━━━━━━━━━
Souls Available: {status['souls_available']}
Pheromone Trails: {status['pheromone_trails']}
K-Factor: {status['k_factor']:.3f}
Avg CPE: ${status['avg_cpe']:.4f}
Hunted Tweets: {status['hunted_tweets']}
Proof Actions: {status['proof_actions']}
            """
            )

        elif choice == "4":
            master.controller._generate_optimization_report()
            print("Reports generated in engagement/ folder")


if __name__ == "__main__":
    asyncio.run(main())
