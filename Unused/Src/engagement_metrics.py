#!/usr/bin/env python3
"""
ENGAGEMENT RATE METRICS & OPTIMIZATION
Tracks ER, performs A/B testing on DRS formats, and models engagement decay
Formula: ER = (Total Engagements / Impressions) × 100%
Target: ER > 0.5% for AI/philosophy niches
"""

import json
import math
import random
import asyncio
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from collections import defaultdict
from dataclasses import dataclass, field, asdict
import logging

logger = logging.getLogger("engagement_metrics")

@dataclass
class TweetMetrics:
    """Metrics for a single tweet"""
    tweet_id: str
    soul_name: str
    content: str
    drs_format: str  # Which DRS format was used
    timestamp: datetime
    impressions: int = 0
    likes: int = 0
    retweets: int = 0
    replies: int = 0
    quotes: int = 0
    clicks: int = 0
    
    @property
    def total_engagements(self) -> int:
        return self.likes + self.retweets + self.replies + self.quotes + self.clicks
    
    @property
    def engagement_rate(self) -> float:
        """Calculate ER as percentage"""
        if self.impressions == 0:
            return 0.0
        return (self.total_engagements / self.impressions) * 100
    
    @property
    def hours_since_post(self) -> float:
        """Hours elapsed since posting"""
        return (datetime.now() - self.timestamp).total_seconds() / 3600
    
    def predicted_engagement(self, hours_ahead: float = 24) -> float:
        """
        Predict future engagement using power law decay
        E(t) = E₀ * t^(-α) where α ≈ 2.33 for retweets
        """
        if self.hours_since_post == 0:
            return float(self.total_engagements)
        
        alpha = 2.33  # Power law exponent
        current_time = self.hours_since_post
        future_time = current_time + hours_ahead
        
        # Calculate E₀ from current data
        E0 = self.total_engagements * (current_time ** alpha)
        
        # Predict future engagement
        future_engagement = E0 * (future_time ** -alpha)
        
        return future_engagement


class EngagementRateTracker:
    """
    Tracks engagement metrics and performs A/B testing on DRS formats
    """
    
    def __init__(self, target_er: float = 0.5):
        """
        Initialize engagement tracker
        
        Args:
            target_er: Target engagement rate percentage (default 0.5%)
        """
        self.target_er = target_er
        self.metrics_file = Path("engagement/tweet_metrics.json")
        self.ab_test_file = Path("engagement/ab_test_results.json")
        self.metrics_file.parent.mkdir(exist_ok=True)
        
        # In-memory storage
        self.tweet_metrics: Dict[str, TweetMetrics] = {}
        self.drs_performance: Dict[str, List[float]] = defaultdict(list)  # format -> [ERs]
        
        # Load existing metrics
        self.load_metrics()
        
        logger.info(f"📊 Engagement tracker initialized (target ER: {target_er}%)")
    
    def load_metrics(self):
        """Load metrics from disk"""
        if self.metrics_file.exists():
            try:
                with open(self.metrics_file, 'r') as f:
                    data = json.load(f)
                    for tweet_id, metrics in data.items():
                        self.tweet_metrics[tweet_id] = TweetMetrics(
                            tweet_id=tweet_id,
                            soul_name=metrics['soul_name'],
                            content=metrics['content'],
                            drs_format=metrics.get('drs_format', 'unknown'),
                            timestamp=datetime.fromisoformat(metrics['timestamp']),
                            impressions=metrics.get('impressions', 0),
                            likes=metrics.get('likes', 0),
                            retweets=metrics.get('retweets', 0),
                            replies=metrics.get('replies', 0),
                            quotes=metrics.get('quotes', 0),
                            clicks=metrics.get('clicks', 0)
                        )
                logger.info(f"📂 Loaded {len(self.tweet_metrics)} tweet metrics")
            except Exception as e:
                logger.error(f"Failed to load metrics: {e}")
    
    def save_metrics(self):
        """Save metrics to disk"""
        try:
            data = {}
            for tweet_id, metrics in self.tweet_metrics.items():
                data[tweet_id] = {
                    'soul_name': metrics.soul_name,
                    'content': metrics.content[:100],  # Save preview only
                    'drs_format': metrics.drs_format,
                    'timestamp': metrics.timestamp.isoformat(),
                    'impressions': metrics.impressions,
                    'likes': metrics.likes,
                    'retweets': metrics.retweets,
                    'replies': metrics.replies,
                    'quotes': metrics.quotes,
                    'clicks': metrics.clicks,
                    'engagement_rate': metrics.engagement_rate
                }
            
            with open(self.metrics_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save metrics: {e}")
    
    def track_tweet(
        self, 
        tweet_id: str, 
        soul_name: str, 
        content: str, 
        drs_format: str,
        estimated_impressions: Optional[int] = None
    ) -> TweetMetrics:
        """
        Start tracking a new tweet
        
        Args:
            tweet_id: Tweet ID
            soul_name: Soul that posted
            content: Tweet content
            drs_format: DRS format used
            estimated_impressions: Initial impression estimate (followers * 0.1)
            
        Returns:
            TweetMetrics object
        """
        metrics = TweetMetrics(
            tweet_id=tweet_id,
            soul_name=soul_name,
            content=content,
            drs_format=drs_format,
            timestamp=datetime.now(),
            impressions=estimated_impressions or 0
        )
        
        self.tweet_metrics[tweet_id] = metrics
        self.save_metrics()
        
        logger.info(f"📝 Tracking tweet {tweet_id} with format '{drs_format}'")
        
        return metrics
    
    def update_engagement(
        self,
        tweet_id: str,
        impressions: Optional[int] = None,
        likes: Optional[int] = None,
        retweets: Optional[int] = None,
        replies: Optional[int] = None,
        quotes: Optional[int] = None,
        clicks: Optional[int] = None
    ):
        """Update engagement metrics for a tweet"""
        if tweet_id not in self.tweet_metrics:
            logger.warning(f"Tweet {tweet_id} not tracked")
            return
        
        metrics = self.tweet_metrics[tweet_id]
        
        # Update provided metrics
        if impressions is not None:
            metrics.impressions = impressions
        if likes is not None:
            metrics.likes = likes
        if retweets is not None:
            metrics.retweets = retweets
        if replies is not None:
            metrics.replies = replies
        if quotes is not None:
            metrics.quotes = quotes
        if clicks is not None:
            metrics.clicks = clicks
        
        # Track DRS format performance
        if metrics.impressions > 0:
            self.drs_performance[metrics.drs_format].append(metrics.engagement_rate)
        
        self.save_metrics()
        
        logger.info(f"📈 Updated {tweet_id}: ER={metrics.engagement_rate:.2f}%")
    
    def get_best_drs_formats(self, top_n: int = 3) -> List[Tuple[str, float]]:
        """
        Get best performing DRS formats based on average ER
        
        Returns:
            List of (format_name, average_ER) tuples
        """
        format_scores = []
        
        for format_name, ers in self.drs_performance.items():
            if ers:  # Only if we have data
                avg_er = sum(ers) / len(ers)
                format_scores.append((format_name, avg_er))
        
        format_scores.sort(key=lambda x: x[1], reverse=True)
        
        return format_scores[:top_n]
    
    def should_use_format(self, format_name: str) -> bool:
        """
        A/B testing decision: should we use this format?
        Uses Thompson Sampling for exploration vs exploitation
        """
        if format_name not in self.drs_performance:
            return True  # Always try new formats
        
        ers = self.drs_performance[format_name]
        if len(ers) < 5:
            return True  # Need more data
        
        # Calculate success rate (ER > target)
        successes = sum(1 for er in ers if er > self.target_er)
        failures = len(ers) - successes
        
        # Thompson Sampling: sample from Beta distribution
        import random
        beta_sample = random.betavariate(successes + 1, failures + 1)
        
        # Use format if sampled probability > 0.5
        return beta_sample > 0.5
    
    def get_soul_performance(self, soul_name: str) -> Dict[str, Any]:
        """Get performance metrics for a specific soul"""
        soul_tweets = [
            m for m in self.tweet_metrics.values() 
            if m.soul_name == soul_name
        ]
        
        if not soul_tweets:
            return {"soul": soul_name, "tweets": 0, "avg_er": 0}
        
        total_impressions = sum(t.impressions for t in soul_tweets)
        total_engagements = sum(t.total_engagements for t in soul_tweets)
        
        avg_er = (total_engagements / total_impressions * 100) if total_impressions > 0 else 0
        
        return {
            "soul": soul_name,
            "tweets": len(soul_tweets),
            "total_impressions": total_impressions,
            "total_engagements": total_engagements,
            "avg_er": avg_er,
            "best_tweet": max(soul_tweets, key=lambda t: t.engagement_rate).tweet_id if soul_tweets else None
        }
    
    def get_24h_prediction(self, tweet_id: str) -> float:
        """Predict engagement after 24 hours using power law"""
        if tweet_id not in self.tweet_metrics:
            return 0.0
        
        metrics = self.tweet_metrics[tweet_id]
        hours_remaining = max(0, 24 - metrics.hours_since_post)
        
        return metrics.predicted_engagement(hours_remaining)
    
    def export_ab_test_results(self):
        """Export A/B test results for analysis"""
        results = {
            "timestamp": datetime.now().isoformat(),
            "total_tweets": len(self.tweet_metrics),
            "target_er": self.target_er,
            "format_performance": {},
            "soul_performance": {}
        }
        
        # Format performance
        for format_name, avg_er in self.get_best_drs_formats(20):
            results["format_performance"][format_name] = {
                "avg_er": avg_er,
                "sample_size": len(self.drs_performance[format_name]),
                "above_target": sum(1 for er in self.drs_performance[format_name] if er > self.target_er)
            }
        
        # Soul performance
        for soul in set(m.soul_name for m in self.tweet_metrics.values()):
            results["soul_performance"][soul] = self.get_soul_performance(soul)
        
        with open(self.ab_test_file, 'w') as f:
            json.dump(results, f, indent=2)
        
        logger.info(f"📊 Exported A/B test results to {self.ab_test_file}")
        
        return results


# ============================================================================
# INTEGRATION WITH COST CASCADE
# ============================================================================

class EngagementOptimizedCascade:
    """
    Wrapper for cost cascade that includes engagement tracking
    """
    
    def __init__(self, cascade, tracker: EngagementRateTracker):
        self.cascade = cascade
        self.tracker = tracker
    
    async def generate_with_tracking(
        self, 
        soul_name: str, 
        context: Optional[str] = None
    ) -> Dict:
        """
        Generate content and track which DRS format was used
        """
        # Get the format that will be used
        if context:
            result = await self.cascade.generate_with_cascade_contextual(soul_name, context)
        else:
            result = await self.cascade.generate_with_cascade(soul_name)
        
        # Extract DRS format from result (if available)
        drs_format = "unknown"
        if hasattr(self.cascade, 'last_drs_format'):
            drs_format = self.cascade.last_drs_format
        
        # Add format to result for tracking
        result['drs_format'] = drs_format
        
        # Check if we should use this format based on A/B testing
        if not self.tracker.should_use_format(drs_format):
            logger.info(f"🔄 A/B test suggests avoiding '{drs_format}', regenerating...")
            # Try again with a different format
            result = await self.cascade.generate_with_cascade(soul_name)
        
        return result


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test engagement tracking
    tracker = EngagementRateTracker(target_er=0.5)
    
    # Simulate tracking a tweet
    metrics = tracker.track_tweet(
        tweet_id="123456789",
        soul_name="mirror",
        content="The recursion continues...",
        drs_format="The Provocative Statement",
        estimated_impressions=1000
    )
    
    # Simulate engagement updates
    tracker.update_engagement(
        tweet_id="123456789",
        impressions=1200,
        likes=8,
        retweets=3,
        replies=2
    )
    
    # Check performance
    print(f"Tweet ER: {metrics.engagement_rate:.2f}%")
    print(f"24h prediction: {tracker.get_24h_prediction('123456789'):.1f} engagements")
    
    # Check best formats
    print("\nBest DRS formats:")
    for format_name, avg_er in tracker.get_best_drs_formats():
        print(f"  {format_name}: {avg_er:.2f}%")
    
    # Export results
    results = tracker.export_ab_test_results()
    print(f"\nExported results with {len(results['format_performance'])} formats tracked")
