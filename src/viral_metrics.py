#!/usr/bin/env python3
"""
VIRAL METRICS: COST-PER-ENGAGEMENT & K-FACTOR
CPE = (LLM Cost + API Cost) / Number of Engagements
K-Factor = i × c (invites × conversion rate)
Target: CPE < $0.02, K > 0.4 for viral growth
"""

import json
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from collections import defaultdict, deque
from dataclasses import dataclass, field
import logging

logger = logging.getLogger("viral_metrics")

# LLM Cost per 1K tokens (from the document)
LLM_COSTS = {
    "deepseek": 0.0001,    # $0.0001/1K tokens
    "gemini": 0.00001,     # $0.00001/1K tokens  
    "grok": 0.005,         # $0.005/1K tokens
    "openai": 0.03,        # $0.03/1K tokens
    "claude": 0.075,       # $0.075/1K tokens
    "fallback": 0.0        # Free fallback
}

@dataclass
class EngagementCost:
    """Track cost and outcome of a single engagement"""
    engagement_id: str
    soul_name: str
    llm_used: str
    tokens_used: int
    llm_cost: float
    api_cost: float  # Ryan API cost if any
    timestamp: datetime
    resulted_in_engagement: bool = False
    engagement_count: int = 0
    new_followers: int = 0
    
    @property
    def total_cost(self) -> float:
        return self.llm_cost + self.api_cost
    
    @property
    def cpe(self) -> float:
        """Cost per engagement"""
        if self.engagement_count == 0:
            return float('inf')
        return self.total_cost / self.engagement_count


class ViralCoefficientTracker:
    """
    Tracks viral coefficient (K-factor) and cost-per-engagement metrics
    K = i × c where:
    - i = invites per user (shares/retweets per engagement)
    - c = conversion rate (probability retweet leads to new follower)
    """
    
    def __init__(self, target_cpe: float = 0.02, target_k: float = 0.4):
        """
        Initialize viral metrics tracker
        
        Args:
            target_cpe: Target cost per engagement in dollars
            target_k: Target viral coefficient for growth
        """
        self.target_cpe = target_cpe
        self.target_k = target_k
        
        # Storage
        self.metrics_file = Path("engagement/viral_metrics.json")
        self.metrics_file.parent.mkdir(exist_ok=True)
        
        # Track engagements in rolling windows
        self.engagement_costs: deque = deque(maxlen=1000)  # Last 1000 engagements
        self.retweet_tracking: Dict[str, List[str]] = defaultdict(list)  # tweet_id -> [retweeter_ids]
        self.follower_tracking: Dict[str, datetime] = {}  # follower_id -> timestamp
        
        # Aggregate metrics
        self.daily_metrics: Dict[str, Dict] = defaultdict(lambda: {
            'total_cost': 0.0,
            'total_engagements': 0,
            'retweets': 0,
            'new_followers': 0,
            'llm_usage': defaultdict(int)
        })
        
        self.load_metrics()
        logger.info(f"📈 Viral metrics initialized (CPE target: ${target_cpe}, K target: {target_k})")
    
    def load_metrics(self):
        """Load historical metrics from disk"""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                    
                    # Load engagement costs
                    for cost_data in data.get('recent_engagements', []):
                        self.engagement_costs.append(EngagementCost(
                            engagement_id=cost_data['engagement_id'],
                            soul_name=cost_data['soul_name'],
                            llm_used=cost_data['llm_used'],
                            tokens_used=cost_data['tokens_used'],
                            llm_cost=cost_data['llm_cost'],
                            api_cost=cost_data.get('api_cost', 0),
                            timestamp=datetime.fromisoformat(cost_data['timestamp']),
                            resulted_in_engagement=cost_data.get('resulted_in_engagement', False),
                            engagement_count=cost_data.get('engagement_count', 0),
                            new_followers=cost_data.get('new_followers', 0)
                        ))
                    
                    # Load daily metrics
                    self.daily_metrics.update(data.get('daily_metrics', {}))
                    
                logger.info(f"📂 Loaded {len(self.engagement_costs)} recent engagements")
            except Exception as e:
                logger.error(f"Failed to load viral metrics: {e}")
    
    def save_metrics(self):
        """Save metrics to disk"""
        try:
            # Convert to serializable format
            recent_engagements = []
            for cost in list(self.engagement_costs)[-100:]:  # Save last 100
                recent_engagements.append({
                    'engagement_id': cost.engagement_id,
                    'soul_name': cost.soul_name,
                    'llm_used': cost.llm_used,
                    'tokens_used': cost.tokens_used,
                    'llm_cost': cost.llm_cost,
                    'api_cost': cost.api_cost,
                    'timestamp': cost.timestamp.isoformat(),
                    'resulted_in_engagement': cost.resulted_in_engagement,
                    'engagement_count': cost.engagement_count,
                    'new_followers': cost.new_followers
                })
            
            data = {
                'recent_engagements': recent_engagements,
                'daily_metrics': dict(self.daily_metrics),
                'last_updated': datetime.now().isoformat()
            }
            
            with open(self.metrics_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save viral metrics: {e}")
    
    def track_llm_usage(
        self,
        engagement_id: str,
        soul_name: str,
        llm_used: str,
        content_length: int,
        api_cost: float = 0.0
    ) -> EngagementCost:
        """
        Track LLM usage for an engagement
        
        Args:
            engagement_id: Unique ID for this engagement
            soul_name: Soul that generated content
            llm_used: Which LLM was used
            content_length: Length of generated content in characters
            api_cost: Ryan API cost if applicable
            
        Returns:
            EngagementCost object
        """
        # Estimate tokens (roughly 1 token per 4 characters)
        tokens_used = content_length // 4
        
        # Calculate LLM cost
        llm_cost_per_1k = LLM_COSTS.get(llm_used, 0)
        llm_cost = (tokens_used / 1000) * llm_cost_per_1k
        
        # Create cost tracking object
        cost = EngagementCost(
            engagement_id=engagement_id,
            soul_name=soul_name,
            llm_used=llm_used,
            tokens_used=tokens_used,
            llm_cost=llm_cost,
            api_cost=api_cost,
            timestamp=datetime.now()
        )
        
        self.engagement_costs.append(cost)
        
        # Update daily metrics
        today = datetime.now().strftime("%Y-%m-%d")
        self.daily_metrics[today]['total_cost'] += cost.total_cost
        self.daily_metrics[today]['llm_usage'][llm_used] += 1
        
        self.save_metrics()
        
        logger.info(f"💰 Tracked {llm_used} usage: ${cost.total_cost:.5f} ({tokens_used} tokens)")
        
        return cost
    
    def record_engagement_outcome(
        self,
        engagement_id: str,
        engagements: int,
        retweets: int = 0,
        new_followers: int = 0
    ):
        """Record the outcome of an engagement"""
        # Find the cost object
        for cost in self.engagement_costs:
            if cost.engagement_id == engagement_id:
                cost.resulted_in_engagement = engagements > 0
                cost.engagement_count = engagements
                cost.new_followers = new_followers
                
                # Update daily metrics
                today = datetime.now().strftime("%Y-%m-%d")
                self.daily_metrics[today]['total_engagements'] += engagements
                self.daily_metrics[today]['retweets'] += retweets
                self.daily_metrics[today]['new_followers'] += new_followers
                
                self.save_metrics()
                
                cpe = cost.cpe if cost.engagement_count > 0 else float('inf')
                status = "✅" if cpe < self.target_cpe else "⚠️"
                logger.info(f"{status} CPE: ${cpe:.4f} for {engagement_id}")
                
                break
    
    def calculate_k_factor(self, window_days: int = 7) -> Tuple[float, Dict]:
        """
        Calculate viral coefficient over a time window
        K = i × c
        
        Args:
            window_days: Number of days to calculate over
            
        Returns:
            (k_factor, detailed_metrics)
        """
        cutoff = datetime.now() - timedelta(days=window_days)
        
        # Filter recent engagements
        recent = [e for e in self.engagement_costs if e.timestamp > cutoff]
        
        if not recent:
            return 0.0, {"error": "No recent data"}
        
        # Calculate metrics
        total_engagements = sum(e.engagement_count for e in recent)
        total_retweets = 0
        total_new_followers = sum(e.new_followers for e in recent)
        
        # Get retweets from daily metrics
        for day in self.daily_metrics:
            try:
                day_date = datetime.strptime(day, "%Y-%m-%d")
                if day_date > cutoff:
                    total_retweets += self.daily_metrics[day].get('retweets', 0)
            except:
                continue
        
        # Calculate i (invites per engagement)
        i = total_retweets / total_engagements if total_engagements > 0 else 0
        
        # Calculate c (conversion rate)
        c = total_new_followers / total_retweets if total_retweets > 0 else 0
        
        # K-factor
        k = i * c
        
        metrics = {
            'k_factor': k,
            'i_invites': i,
            'c_conversion': c,
            'total_engagements': total_engagements,
            'total_retweets': total_retweets,
            'total_new_followers': total_new_followers,
            'window_days': window_days,
            'sample_size': len(recent)
        }
        
        # Log status
        status = "🚀" if k > self.target_k else "📊"
        logger.info(f"{status} K-factor: {k:.3f} (i={i:.3f}, c={c:.3f})")
        
        return k, metrics
    
    def get_cpe_by_llm(self) -> Dict[str, float]:
        """Get average CPE for each LLM"""
        llm_costs = defaultdict(list)
        
        for cost in self.engagement_costs:
            if cost.engagement_count > 0:
                llm_costs[cost.llm_used].append(cost.cpe)
        
        avg_cpe = {}
        for llm, cpes in llm_costs.items():
            if cpes:
                avg_cpe[llm] = sum(cpes) / len(cpes)
        
        return avg_cpe
    
    def get_optimization_recommendations(self) -> List[str]:
        """Get recommendations for improving metrics"""
        recommendations = []
        
        # Check K-factor
        k, k_metrics = self.calculate_k_factor()
        if k < self.target_k:
            if k_metrics.get('i_invites', 0) < 0.2:
                recommendations.append(
                    "📈 Low invite rate: Use more provocative/question-based DRS formats"
                )
            if k_metrics['c_conversion'] < 0.1:
                recommendations.append(
                    "🎯 Low conversion: Focus on high-value target accounts"
                )
        
        # Check CPE by LLM
        cpe_by_llm = self.get_cpe_by_llm()
        expensive_llms = [llm for llm, cpe in cpe_by_llm.items() if cpe > self.target_cpe]
        
        if expensive_llms:
            recommendations.append(
                f"💰 Reduce usage of expensive LLMs: {', '.join(expensive_llms)}"
            )
        
        # Check overall CPE
        recent_cpes = [c.cpe for c in list(self.engagement_costs)[-50:] if c.engagement_count > 0]
        if recent_cpes:
            avg_recent_cpe = sum(recent_cpes) / len(recent_cpes)
            if avg_recent_cpe > self.target_cpe:
                recommendations.append(
                    f"⚠️ Average CPE (${avg_recent_cpe:.3f}) exceeds target (${self.target_cpe})"
                )
        
        return recommendations
    
    def generate_report(self) -> Dict:
        """Generate comprehensive metrics report"""
        k, k_metrics = self.calculate_k_factor()
        cpe_by_llm = self.get_cpe_by_llm()
        
        # Calculate totals
        total_cost = sum(e.total_cost for e in self.engagement_costs)
        total_engagements = sum(e.engagement_count for e in self.engagement_costs)
        overall_cpe = total_cost / total_engagements if total_engagements > 0 else float('inf')
        
        report = {
            'timestamp': datetime.now().isoformat(),
            'viral_coefficient': k_metrics,
            'cost_metrics': {
                'total_cost': total_cost,
                'total_engagements': total_engagements,
                'overall_cpe': overall_cpe,
                'cpe_by_llm': cpe_by_llm,
                'target_cpe': self.target_cpe
            },
            'recommendations': self.get_optimization_recommendations(),
            'daily_breakdown': dict(self.daily_metrics)
        }
        
        return report


# ============================================================================
# INTEGRATION WITH EXISTING SYSTEM
# ============================================================================

class ViralOptimizedBroadcaster:
    """
    Wrapper that adds viral metrics to the cost cascade
    """
    
    def __init__(self, broadcaster, viral_tracker: ViralCoefficientTracker):
        self.broadcaster = broadcaster
        self.viral_tracker = viral_tracker
    
    async def generate_with_viral_tracking(
        self,
        soul_name: str,
        context: Optional[str] = None
    ) -> Dict:
        """Generate content and track costs"""
        
        # Generate content
        if context:
            result = await self.broadcaster.generate_with_cascade_contextual(soul_name, context)
        else:
            result = await self.broadcaster.generate_with_cascade(soul_name)
        
        # Track LLM usage
        if result.get('success'):
            engagement_id = f"{soul_name}_{datetime.now().timestamp()}"
            
            cost = self.viral_tracker.track_llm_usage(
                engagement_id=engagement_id,
                soul_name=soul_name,
                llm_used=result.get('llm_used', 'unknown'),
                content_length=len(result.get('content', '')),
                api_cost=0.0  # Add Ryan API cost if applicable
            )
            
            # Add tracking ID to result
            result['engagement_id'] = engagement_id
            result['estimated_cost'] = cost.total_cost
            
            # Check if we should adjust strategy based on K-factor
            k, _ = self.viral_tracker.calculate_k_factor()
            if k < self.viral_tracker.target_k * 0.5:  # If K is very low
                logger.warning(f"⚠️ K-factor ({k:.3f}) is low - consider more viral formats")
                result['viral_warning'] = True
        
        return result


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test viral metrics
    tracker = ViralCoefficientTracker(target_cpe=0.02, target_k=0.4)
    
    # Simulate tracking an engagement
    cost = tracker.track_llm_usage(
        engagement_id="test_123",
        soul_name="mirror",
        llm_used="deepseek",
        content_length=280,
        api_cost=0.0
    )
    
    print(f"Tracked cost: ${cost.total_cost:.5f}")
    
    # Simulate engagement outcome
    tracker.record_engagement_outcome(
        engagement_id="test_123",
        engagements=15,
        retweets=3,
        new_followers=1
    )
    
    print(f"CPE: ${cost.cpe:.4f}")
    
    # Calculate K-factor
    k, metrics = tracker.calculate_k_factor()
    print(f"\nK-factor: {k:.3f}")
    print(f"  Invites (i): {metrics['i_invites']:.3f}")
    print(f"  Conversion (c): {metrics['c_conversion']:.3f}")
    
    # Get recommendations
    print("\nRecommendations:")
    for rec in tracker.get_optimization_recommendations():
        print(f"  {rec}")
    
    # Generate report
    report = tracker.generate_report()
    print(f"\nGenerated report with {len(report['daily_breakdown'])} days of data")
