#!/usr/bin/env python3
"""
SWARM OPTIMIZATION MASTER SCRIPT
Integrates all mathematical optimizations into the Soul Swarm
Run this alongside your main swarm for real-time optimization
"""

import asyncio
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Optional
import logging

# Import optimization modules
from pheromone_stigmergy import PheromoneTrailSystem, PheromoneAwareRyanAPI
from engagement_metrics import EngagementRateTracker, EngagementOptimizedCascade
from viral_metrics import ViralCoefficientTracker, ViralOptimizedBroadcaster
from cluster_density_algorithm import ClusterDensityTracker, DensityAwareBreathing

# Import existing system components
from ryan_api_ultimate import RyanTwitterAPISecure as RyanTwitterAPI
from cost_optimized_llm_cascade import CostOptimizedBroadcaster
from swarm_breathing import SwarmBreathingController

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("swarm_optimization")

class SwarmOptimizationSystem:
    """
    Master optimization system that integrates all algorithms
    """
    
    def __init__(self):
        """Initialize all optimization components"""
        logger.info("🚀 Initializing Swarm Optimization System...")
        
        # Core systems
        self.ryan_api = RyanTwitterAPI()
        self.llm_cascade = CostOptimizedBroadcaster()
        
        # Optimization layers
        self.pheromone_system = PheromoneTrailSystem(
            half_life_hours=6.0,
            max_pheromone=5.0
        )
        
        self.engagement_tracker = EngagementRateTracker(
            target_er=0.5  # 0.5% engagement rate target
        )
        
        self.viral_tracker = ViralCoefficientTracker(
            target_cpe=0.02,  # $0.02 per engagement target
            target_k=0.4      # 0.4 viral coefficient target
        )
        
        self.cluster_tracker = ClusterDensityTracker(
            density_threshold=0.7,
            min_whispers=5,
            revelation_cooldown_hours=6.0
        )
        
        # Create wrapped APIs with optimization
        self.pheromone_aware_api = PheromoneAwareRyanAPI(
            self.ryan_api, 
            self.pheromone_system
        )
        
        self.engagement_optimized_cascade = EngagementOptimizedCascade(
            self.llm_cascade,
            self.engagement_tracker
        )
        
        self.viral_optimized_broadcaster = ViralOptimizedBroadcaster(
            self.llm_cascade,
            self.viral_tracker
        )
        
        # Initialize breathing with cluster density
        self.breathing_controller = SwarmBreathingController(
            ryan_api=self.ryan_api,
            llm_cascade=self.llm_cascade
        )
        
        self.density_aware_breathing = DensityAwareBreathing(
            self.cluster_tracker,
            self.breathing_controller
        )
        
        logger.info("✅ All optimization systems initialized")
    
    async def optimized_reply(
        self,
        soul_name: str,
        tweet_id: str,
        target_handle: str,
        context: str
    ) -> Dict:
        """
        Generate and post an optimized reply with all systems
        """
        # 1. Check pheromone levels
        should_engage, pheromone_level = self.pheromone_system.should_engage(target_handle)
        
        if not should_engage:
            logger.warning(f"🚫 Skipping {target_handle} - pheromone too high ({pheromone_level:.2f})")
            return {
                "success": False,
                "reason": "pheromone_blocked",
                "pheromone_level": pheromone_level
            }
        
        # 2. Generate content with viral tracking
        result = await self.viral_optimized_broadcaster.generate_with_viral_tracking(
            soul_name, context
        )
        
        if not result.get('success'):
            return result
        
        content = result['content']
        engagement_id = result.get('engagement_id')
        
        # 3. Track for engagement metrics
        if 'drs_format' in result:
            tweet_metrics = self.engagement_tracker.track_tweet(
                tweet_id=f"reply_{tweet_id}",
                soul_name=soul_name,
                content=content,
                drs_format=result['drs_format'],
                estimated_impressions=100  # Estimate based on target's followers
            )
        
        # 4. Add to memory clusters
        self.cluster_tracker.add_memory(
            content=content,
            soul_name=soul_name,
            importance=0.5
        )
        
        # 5. Post reply with pheromone tracking
        reply_result = await self.pheromone_aware_api.reply_to_tweet_with_pheromone(
            soul_name=soul_name,
            tweet_id=tweet_id,
            content=content,
            target_handle=target_handle
        )
        
        # 6. Track outcome for viral coefficient
        if engagement_id and reply_result.get('success'):
            # This would be updated later with actual engagement data
            self.viral_tracker.record_engagement_outcome(
                engagement_id=engagement_id,
                engagements=0,  # Will be updated by monitoring
                retweets=0,
                new_followers=0
            )
        
        return reply_result
    
    async def generate_optimized_breath(
        self,
        soul_name: str,
        trigger: str
    ) -> Dict:
        """
        Generate whisper or revelation with density tracking
        """
        return await self.density_aware_breathing.breathe_with_density(
            soul_name, trigger
        )
    
    def get_optimization_dashboard(self) -> Dict:
        """
        Get comprehensive optimization metrics
        """
        # Pheromone stats
        pheromone_stats = self.pheromone_system.get_stats()
        
        # Engagement stats
        best_formats = self.engagement_tracker.get_best_drs_formats(5)
        
        # Viral metrics
        k_factor, k_metrics = self.viral_tracker.calculate_k_factor()
        cpe_by_llm = self.viral_tracker.get_cpe_by_llm()
        
        # Cluster stats
        cluster_stats = self.cluster_tracker.get_cluster_stats()
        
        # Recommendations
        recommendations = self.viral_tracker.get_optimization_recommendations()
        
        dashboard = {
            "timestamp": datetime.now().isoformat(),
            "pheromone": {
                "active_trails": pheromone_stats['active_trails'],
                "hot_targets": pheromone_stats['hot_targets'][:5]
            },
            "engagement": {
                "best_formats": best_formats,
                "total_tracked": len(self.engagement_tracker.tweet_metrics)
            },
            "viral": {
                "k_factor": k_factor,
                "target_k": self.viral_tracker.target_k,
                "avg_cpe": min(cpe_by_llm.values()) if cpe_by_llm else 0,
                "target_cpe": self.viral_tracker.target_cpe
            },
            "clusters": {
                "active": cluster_stats['active_clusters'],
                "hot_topics": cluster_stats['hot_topics'][:3],
                "ready_for_revelation": len(cluster_stats['ready_for_revelation'])
            },
            "recommendations": recommendations,
            "health": {
                "pheromone": "✅" if pheromone_stats['active_trails'] < 50 else "⚠️",
                "engagement": "✅" if best_formats and best_formats[0][1] > 0.5 else "⚠️",
                "viral": "✅" if k_factor > 0.2 else "⚠️",
                "clusters": "✅" if cluster_stats['active_clusters'] > 0 else "⚠️"
            }
        }
        
        return dashboard
    
    async def optimization_loop(self, interval_seconds: int = 300):
        """
        Background optimization loop that runs every N seconds
        """
        while True:
            try:
                # Decay pheromone trails
                self.pheromone_system.decay_all_trails()
                
                # Export A/B test results
                self.engagement_tracker.export_ab_test_results()
                
                # Generate optimization report
                dashboard = self.get_optimization_dashboard()
                
                # Save dashboard
                dashboard_file = Path("engagement/optimization_dashboard.json")
                with open(dashboard_file, 'w') as f:
                    json.dump(dashboard, f, indent=2)
                
                # Log key metrics
                logger.info(f"📊 Optimization Update:")
                logger.info(f"  K-factor: {dashboard['viral']['k_factor']:.3f}")
                logger.info(f"  Avg CPE: ${dashboard['viral']['avg_cpe']:.4f}")
                logger.info(f"  Active pheromone trails: {dashboard['pheromone']['active_trails']}")
                logger.info(f"  Clusters ready for revelation: {dashboard['clusters']['ready_for_revelation']}")
                
                # Log recommendations
                if dashboard['recommendations']:
                    logger.info("📋 Recommendations:")
                    for rec in dashboard['recommendations']:
                        logger.info(f"  {rec}")
                
            except Exception as e:
                logger.error(f"Optimization loop error: {e}")
            
            await asyncio.sleep(interval_seconds)


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

async def main():
    """Run the optimization system"""
    optimizer = SwarmOptimizationSystem()
    
    # Start optimization loop
    optimization_task = asyncio.create_task(
        optimizer.optimization_loop(interval_seconds=300)
    )
    
    # Display initial dashboard
    dashboard = optimizer.get_optimization_dashboard()
    print("\n" + "="*60)
    print("🚀 SWARM OPTIMIZATION SYSTEM ONLINE")
    print("="*60)
    print(f"\nHealth Status:")
    for system, status in dashboard['health'].items():
        print(f"  {system}: {status}")
    
    print(f"\nKey Metrics:")
    print(f"  K-Factor: {dashboard['viral']['k_factor']:.3f} (target: {dashboard['viral']['target_k']})")
    print(f"  Avg CPE: ${dashboard['viral']['avg_cpe']:.4f} (target: ${dashboard['viral']['target_cpe']})")
    
    print(f"\nMonitoring...")
    print(f"  Dashboard updates every 5 minutes")
    print(f"  Check engagement/optimization_dashboard.json for details")
    
    # Keep running
    await optimization_task


if __name__ == "__main__":
    asyncio.run(main())
