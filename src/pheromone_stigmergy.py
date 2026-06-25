#!/usr/bin/env python3
"""
PHEROMONE STIGMERGY SYSTEM
Prevents souls from over-engaging the same targets using decay trails
Mathematical foundation: P(t) = P₀ * e^(-λt) with 6-hour half-life
"""

import json
import math
import asyncio
from datetime import datetime
from pathlib import Path
import logging

logger = logging.getLogger("pheromone_system")

class PheromoneTrailSystem:
    """
    Stigmergy-based coordination to prevent swarm pile-ons.
    Each user/topic has a pheromone value that decays over time.
    """
    
    def __init__(self, half_life_hours: float = 6.0, max_pheromone: float = 5.0):
        """
        Initialize pheromone system
        
        Args:
            half_life_hours: Time for pheromone to decay by 50%
            max_pheromone: Threshold above which souls skip engagement
        """
        self.half_life = half_life_hours * 3600  # Convert to seconds
        self.decay_lambda = math.log(2) / self.half_life
        self.max_pheromone = max_pheromone
        
        # Storage
        self.pheromone_file = Path("engagement/pheromone_trails.json")
        self.pheromone_file.parent.mkdir(exist_ok=True)
        
        # In-memory cache: {target_id: (pheromone_value, last_update_time)}
        self.trails: dict[str, tuple[float, datetime]] = {}
        
        # Load existing trails
        self.load_trails()
        
        logger.info(f"🐜 Pheromone system initialized (λ={self.decay_lambda:.6f}, half-life={half_life_hours}h)")
    
    def load_trails(self) -> None:
        """Load pheromone trails from disk"""
        if self.pheromone_file.exists():
            try:
                with open(self.pheromone_file, 'r') as f:
                    data = json.load(f)
                    for target_id, info in data.items():
                        self.trails[target_id] = (
                            info['pheromone'],
                            datetime.fromisoformat(info['timestamp'])
                        )
                logger.info(f"📂 Loaded {len(self.trails)} pheromone trails")
            except (json.JSONDecodeError, KeyError, OSError) as e:
                logger.error(f"Failed to load pheromone trails: {e}")

    def save_trails(self) -> None:
        """Persist pheromone trails to disk"""
        try:
            data = {}
            for target_id, (pheromone, timestamp) in self.trails.items():
                # Only save trails with significant pheromone (> 0.1)
                current_p = self.get_current_pheromone(target_id)
                if current_p > 0.1:
                    data[target_id] = {
                        'pheromone': current_p,
                        'timestamp': datetime.now().isoformat()
                    }

            with open(self.pheromone_file, 'w') as f:
                json.dump(data, f, indent=2)

        except OSError as e:
            logger.error(f"Failed to save pheromone trails: {e}")
    
    def get_current_pheromone(self, target_id: str) -> float:
        """
        Get current pheromone level after decay
        
        Formula: P(t) = P₀ * e^(-λt)
        """
        if target_id not in self.trails:
            return 0.0
        
        pheromone, last_update = self.trails[target_id]
        time_elapsed = (datetime.now() - last_update).total_seconds()
        
        # Apply exponential decay
        current_pheromone = pheromone * math.exp(-self.decay_lambda * time_elapsed)
        
        # Clean up if decayed to near-zero
        if current_pheromone < 0.01:
            del self.trails[target_id]
            return 0.0
        
        return current_pheromone
    
    def deposit_pheromone(self, target_id: str, amount: float = 1.0):
        """
        Deposit pheromone when a soul engages with a target
        
        Args:
            target_id: User handle or topic being engaged
            amount: Amount of pheromone to deposit (default 1.0)
        """
        current = self.get_current_pheromone(target_id)
        new_pheromone = current + amount
        
        self.trails[target_id] = (new_pheromone, datetime.now())
        
        logger.info(f"💧 Deposited {amount:.2f} pheromone on {target_id} (now {new_pheromone:.2f})")
        
        # Auto-save every deposit
        self.save_trails()
    
    def should_engage(self, target_id: str, threshold_override: float | None = None) -> tuple[bool, float]:
        """
        Check if a soul should engage with a target based on pheromone level
        
        Args:
            target_id: User handle or topic to check
            threshold_override: Optional custom threshold (default: max_pheromone)
            
        Returns:
            (should_engage, current_pheromone_level)
        """
        current = self.get_current_pheromone(target_id)
        threshold = threshold_override or self.max_pheromone
        
        should = current < threshold
        
        if not should:
            logger.warning(f"🚫 Skipping {target_id} - pheromone too high ({current:.2f} >= {threshold})")
        
        return should, current
    
    def get_engagement_probability(self, target_id: str) -> float:
        """
        Get probability of engagement based on pheromone level
        Uses sigmoid function for smooth falloff
        
        P(engage) = 1 / (1 + e^(k*(pheromone - threshold)))
        """
        current = self.get_current_pheromone(target_id)
        
        # Sigmoid parameters
        k = 2.0  # Steepness
        threshold = self.max_pheromone * 0.7  # Start reducing at 70% of max
        
        probability = 1.0 / (1.0 + math.exp(k * (current - threshold)))
        
        return probability
    
    def decay_all_trails(self) -> None:
        """
        Perform decay on all trails and clean up expired ones
        Called periodically to maintain the system
        """
        expired = []
        for target_id in list(self.trails.keys()):
            current = self.get_current_pheromone(target_id)
            if current < 0.01:
                expired.append(target_id)
        
        logger.info(f"🧹 Cleaned up {len(expired)} expired trails")
        self.save_trails()
    
    def get_hot_targets(self, top_n: int = 10) -> list:
        """
        Get targets with highest pheromone levels (most engaged)
        
        Returns:
            List of (target_id, pheromone_level) tuples
        """
        targets = []
        for target_id in self.trails:
            current = self.get_current_pheromone(target_id)
            if current > 0.1:
                targets.append((target_id, current))
        
        targets.sort(key=lambda x: x[1], reverse=True)
        return targets[:top_n]
    
    def get_stats(self) -> dict:
        """Get system statistics"""
        active_trails = sum(1 for t in self.trails if self.get_current_pheromone(t) > 0.1)
        hot_targets = self.get_hot_targets(5)
        
        return {
            "total_trails": len(self.trails),
            "active_trails": active_trails,
            "hot_targets": hot_targets,
            "decay_lambda": self.decay_lambda,
            "half_life_hours": self.half_life / 3600,
            "max_pheromone": self.max_pheromone
        }


# ============================================================================
# INTEGRATION WITH RYAN API
# ============================================================================

class PheromoneAwareRyanAPI:
    """
    Wrapper that adds pheromone checking to Ryan API calls
    """
    
    def __init__(self, ryan_api, pheromone_system: PheromoneTrailSystem):
        self.ryan_api = ryan_api
        self.pheromone = pheromone_system
    
    async def reply_to_tweet_with_pheromone(
        self,
        soul_name: str,
        tweet_id: str,
        content: str,
        target_handle: str
    ) -> dict:
        """
        Reply to tweet with pheromone checking
        
        Args:
            soul_name: Soul making the reply
            tweet_id: Tweet to reply to
            content: Reply content
            target_handle: Handle of the user being replied to
            
        Returns:
            Result dict with pheromone info added
        """
        # Check pheromone level
        should_engage, pheromone_level = self.pheromone.should_engage(target_handle)
        
        if not should_engage:
            return {
                "success": False,
                "error": f"Pheromone too high ({pheromone_level:.2f})",
                "pheromone_blocked": True,
                "pheromone_level": pheromone_level
            }
        
        # Check probability-based engagement for borderline cases
        if pheromone_level > self.pheromone.max_pheromone * 0.5:
            import random
            engage_prob = self.pheromone.get_engagement_probability(target_handle)
            if random.random() > engage_prob:
                logger.info(f"🎲 Probabilistically skipping {target_handle} (P={engage_prob:.2%})")
                return {
                    "success": False,
                    "error": f"Probabilistic skip (P={engage_prob:.2%})",
                    "pheromone_blocked": True,
                    "pheromone_level": pheromone_level
                }
        
        # Proceed with reply
        result = await self.ryan_api.reply_to_tweet(soul_name, tweet_id, content)
        
        # Deposit pheromone if successful
        if result.get("success"):
            self.pheromone.deposit_pheromone(target_handle, amount=1.0)
            result["pheromone_deposited"] = 1.0
            result["pheromone_level"] = pheromone_level + 1.0
        
        return result


# ============================================================================
# BACKGROUND DECAY TASK
# ============================================================================

async def pheromone_decay_loop(pheromone_system: PheromoneTrailSystem, interval_minutes: int = 30):
    """
    Background task to decay pheromone trails periodically
    
    Args:
        pheromone_system: The pheromone system instance
        interval_minutes: How often to run decay (default 30 min)
    """
    while True:
        await asyncio.sleep(interval_minutes * 60)
        pheromone_system.decay_all_trails()
        stats = pheromone_system.get_stats()
        logger.info(f"🔄 Pheromone decay complete. Active trails: {stats['active_trails']}")


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    import asyncio
    
    async def test_pheromone():
        # Initialize system
        pheromone = PheromoneTrailSystem(half_life_hours=0.1)  # Fast decay for testing
        
        # Test deposition
        target = "@test_user"
        pheromone.deposit_pheromone(target, 3.0)
        
        # Check immediately
        should, level = pheromone.should_engage(target)
        print(f"Immediately after deposit: should_engage={should}, level={level:.2f}")
        
        # Wait and check decay
        await asyncio.sleep(6)  # 1 minute = 10 half-lives with 0.1h setting
        should, level = pheromone.should_engage(target)
        print(f"After 1 minute: should_engage={should}, level={level:.2f}")
        
        # Test probability
        pheromone.deposit_pheromone(target, 4.0)
        prob = pheromone.get_engagement_probability(target)
        print(f"Engagement probability at level {pheromone.get_current_pheromone(target):.2f}: {prob:.2%}")
        
        # Show stats
        print("\nSystem stats:", json.dumps(pheromone.get_stats(), indent=2, default=str))
    
    asyncio.run(test_pheromone())
