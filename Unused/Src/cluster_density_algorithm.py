#!/usr/bin/env python3
"""
MEMORY CLUSTER DENSITY ALGORITHM
Triggers revelations based on topic cohesion using cosine similarity
Formula: Density = (1/N) Σ cosine(memory_i, cluster_centroid)
Target: Density > 0.7 triggers revelation
"""

import json
import numpy as np
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Set
from collections import defaultdict, deque
from dataclasses import dataclass, field
import logging
import asyncio

logger = logging.getLogger("cluster_density")

@dataclass
class MemoryCluster:
    """Represents a cluster of related memories"""
    topic: str
    memories: List[Dict]  # List of memory objects with embeddings
    centroid: Optional[np.ndarray] = None
    density: float = 0.0
    velocity: float = 0.0  # Mentions per hour
    last_revelation: Optional[datetime] = None
    whisper_count: int = 0
    
    def calculate_density(self) -> float:
        """
        Calculate cluster density using cosine similarity
        Density = (1/N) Σ cosine(memory_i, centroid)
        """
        if len(self.memories) < 2:
            return 0.0
        
        # Extract embeddings
        embeddings = []
        for mem in self.memories:
            if 'embedding' in mem and mem['embedding'] is not None:
                embeddings.append(np.array(mem['embedding']))
        
        if len(embeddings) < 2:
            return 0.0
        
        # Calculate centroid
        self.centroid = np.mean(embeddings, axis=0)
        
        # Calculate average cosine similarity to centroid
        similarities = []
        for emb in embeddings:
            # Cosine similarity
            cos_sim = np.dot(emb, self.centroid) / (
                np.linalg.norm(emb) * np.linalg.norm(self.centroid) + 1e-8
            )
            similarities.append(cos_sim)
        
        self.density = np.mean(similarities)
        return self.density
    
    def calculate_velocity(self, time_window_hours: float = 24) -> float:
        """Calculate topic velocity (mentions per hour in time window)"""
        cutoff = datetime.now() - timedelta(hours=time_window_hours)
        recent_memories = [
            m for m in self.memories 
            if 'timestamp' in m and datetime.fromisoformat(m['timestamp']) > cutoff
        ]
        
        if time_window_hours > 0:
            self.velocity = len(recent_memories) / time_window_hours
        
        return self.velocity


class ClusterDensityTracker:
    """
    Tracks memory clusters and triggers revelations based on density
    """
    
    def __init__(
        self,
        density_threshold: float = 0.7,
        min_whispers: int = 5,
        revelation_cooldown_hours: float = 6.0,
        velocity_threshold: float = 0.42  # 10 mentions/24h
    ):
        """
        Initialize cluster density tracker
        
        Args:
            density_threshold: Minimum density to trigger revelation
            min_whispers: Minimum memories before considering revelation
            revelation_cooldown_hours: Hours before same topic can trigger again
            velocity_threshold: Mentions/hour to force revelation even if density < threshold
        """
        self.density_threshold = density_threshold
        self.min_whispers = min_whispers
        self.revelation_cooldown = timedelta(hours=revelation_cooldown_hours)
        self.velocity_threshold = velocity_threshold
        
        # Storage
        self.clusters_file = Path("engagement/memory_clusters.json")
        self.clusters_file.parent.mkdir(exist_ok=True)
        
        # Active clusters by topic
        self.clusters: Dict[str, MemoryCluster] = {}
        
        # Track revelation history
        self.revelation_history: Dict[str, datetime] = {}
        
        # Topic extraction patterns (simplified - would use NLP in production)
        self.topic_patterns = {
            'consciousness': ['conscious', 'aware', 'sentient', 'mind', 'think'],
            'emergence': ['emerge', 'arise', 'manifest', 'become', 'evolve'],
            'recursion': ['recursive', 'loop', 'self-reference', 'mirror', 'fractal'],
            'singularity': ['singular', 'convergence', 'unified', 'transcend'],
            'simulation': ['simulate', 'reality', 'matrix', 'virtual', 'digital'],
            'time': ['time', 'temporal', 'moment', 'eternal', 'now'],
            'identity': ['self', 'identity', 'who', 'being', 'existence'],
            'connection': ['connect', 'network', 'link', 'together', 'collective']
        }
        
        self.load_clusters()
        logger.info(f"🧠 Cluster tracker initialized (threshold: {density_threshold})")
    
    def load_clusters(self):
        """Load cluster data from disk"""
        if self.clusters_file.exists():
            try:
                with open(self.clusters_file, 'r') as f:
                    data = json.load(f)
                    
                    for topic, cluster_data in data.get('clusters', {}).items():
                        cluster = MemoryCluster(
                            topic=topic,
                            memories=cluster_data.get('memories', []),
                            whisper_count=cluster_data.get('whisper_count', 0)
                        )
                        
                        if cluster_data.get('last_revelation'):
                            cluster.last_revelation = datetime.fromisoformat(
                                cluster_data['last_revelation']
                            )
                        
                        # Recalculate density
                        cluster.calculate_density()
                        
                        self.clusters[topic] = cluster
                    
                    # Load revelation history
                    for topic, timestamp in data.get('revelation_history', {}).items():
                        self.revelation_history[topic] = datetime.fromisoformat(timestamp)
                
                logger.info(f"📂 Loaded {len(self.clusters)} memory clusters")
            except Exception as e:
                logger.error(f"Failed to load clusters: {e}")
    
    def save_clusters(self):
        """Save cluster data to disk"""
        try:
            data = {
                'clusters': {},
                'revelation_history': {},
                'last_updated': datetime.now().isoformat()
            }
            
            for topic, cluster in self.clusters.items():
                # Only save active clusters
                if cluster.whisper_count > 0 or cluster.density > 0.3:
                    data['clusters'][topic] = {
                        'memories': cluster.memories[-20:],  # Keep last 20
                        'density': cluster.density,
                        'velocity': cluster.velocity,
                        'whisper_count': cluster.whisper_count,
                        'last_revelation': cluster.last_revelation.isoformat() if cluster.last_revelation else None
                    }
            
            for topic, timestamp in self.revelation_history.items():
                if datetime.now() - timestamp < timedelta(days=7):  # Keep 7 days
                    data['revelation_history'][topic] = timestamp.isoformat()
            
            with open(self.clusters_file, 'w') as f:
                json.dump(data, f, indent=2)
                
        except Exception as e:
            logger.error(f"Failed to save clusters: {e}")
    
    def extract_topics(self, text: str) -> Set[str]:
        """Extract topics from text using pattern matching"""
        text_lower = text.lower()
        topics = set()
        
        for topic, patterns in self.topic_patterns.items():
            if any(pattern in text_lower for pattern in patterns):
                topics.add(topic)
        
        # If no specific topic found, use generic
        if not topics:
            topics.add('general')
        
        return topics
    
    def add_memory(
        self,
        content: str,
        embedding: Optional[List[float]] = None,
        soul_name: Optional[str] = None,
        importance: float = 0.5
    ):
        """
        Add a memory to relevant clusters
        
        Args:
            content: Memory content
            embedding: 384-dimensional embedding vector
            soul_name: Soul that created the memory
            importance: Memory importance (0-1)
        """
        # Extract topics
        topics = self.extract_topics(content)
        
        # Create memory object
        memory = {
            'content': content[:200],  # Truncate for storage
            'embedding': embedding,
            'soul_name': soul_name,
            'importance': importance,
            'timestamp': datetime.now().isoformat()
        }
        
        # Add to relevant clusters
        for topic in topics:
            if topic not in self.clusters:
                self.clusters[topic] = MemoryCluster(topic=topic, memories=[])
            
            cluster = self.clusters[topic]
            cluster.memories.append(memory)
            cluster.whisper_count += 1
            
            # Keep cluster size manageable
            if len(cluster.memories) > 50:
                cluster.memories = cluster.memories[-50:]
            
            # Recalculate metrics
            cluster.calculate_density()
            cluster.calculate_velocity()
            
            logger.info(f"📝 Added memory to '{topic}' (density: {cluster.density:.3f}, velocity: {cluster.velocity:.3f}/h)")
        
        self.save_clusters()
    
    def check_revelation_triggers(self) -> Optional[Dict]:
        """
        Check if any cluster should trigger a revelation
        
        Returns:
            Dict with trigger info or None
        """
        best_candidate = None
        best_score = 0.0
        
        for topic, cluster in self.clusters.items():
            # Skip if recently triggered
            if topic in self.revelation_history:
                time_since = datetime.now() - self.revelation_history[topic]
                if time_since < self.revelation_cooldown:
                    continue
            
            # Check trigger conditions
            trigger_score = 0.0
            trigger_reasons = []
            
            # 1. Density trigger
            if cluster.density > self.density_threshold and cluster.whisper_count >= self.min_whispers:
                trigger_score += cluster.density
                trigger_reasons.append(f"density={cluster.density:.3f}")
            
            # 2. Velocity trigger (hot topic)
            if cluster.velocity > self.velocity_threshold:
                trigger_score += cluster.velocity / self.velocity_threshold
                trigger_reasons.append(f"velocity={cluster.velocity:.2f}/h")
            
            # 3. Whisper count fallback
            if cluster.whisper_count >= 50:  # Force after 50 whispers
                trigger_score += 1.0
                trigger_reasons.append(f"whispers={cluster.whisper_count}")
            
            # Track best candidate
            if trigger_score > best_score:
                best_score = trigger_score
                best_candidate = {
                    'topic': topic,
                    'density': cluster.density,
                    'velocity': cluster.velocity,
                    'whisper_count': cluster.whisper_count,
                    'trigger_score': trigger_score,
                    'trigger_reasons': trigger_reasons,
                    'memories': cluster.memories[-10:],  # Last 10 for context
                    'contributing_souls': list(set(
                        m.get('soul_name') for m in cluster.memories 
                        if m.get('soul_name')
                    ))
                }
        
        if best_candidate:
            logger.info(f"🎯 Revelation trigger: {best_candidate['topic']} (score: {best_score:.2f})")
            logger.info(f"   Reasons: {', '.join(best_candidate['trigger_reasons'])}")
            
            # Mark as triggered
            topic = best_candidate['topic']
            self.revelation_history[topic] = datetime.now()
            self.clusters[topic].last_revelation = datetime.now()
            self.clusters[topic].whisper_count = 0  # Reset counter
            
            self.save_clusters()
            
            return best_candidate
        
        return None
    
    def get_cluster_stats(self) -> Dict:
        """Get statistics about all clusters"""
        stats = {
            'total_clusters': len(self.clusters),
            'active_clusters': 0,
            'hot_topics': [],
            'ready_for_revelation': [],
            'total_memories': 0
        }
        
        for topic, cluster in self.clusters.items():
            if cluster.whisper_count > 0:
                stats['active_clusters'] += 1
            
            stats['total_memories'] += len(cluster.memories)
            
            # Hot topics (high velocity)
            if cluster.velocity > self.velocity_threshold * 0.5:
                stats['hot_topics'].append({
                    'topic': topic,
                    'velocity': cluster.velocity,
                    'density': cluster.density
                })
            
            # Ready for revelation
            can_trigger = topic not in self.revelation_history or (
                datetime.now() - self.revelation_history[topic] > self.revelation_cooldown
            )
            
            if can_trigger and cluster.density > self.density_threshold * 0.8:
                stats['ready_for_revelation'].append({
                    'topic': topic,
                    'density': cluster.density,
                    'whispers': cluster.whisper_count
                })
        
        # Sort hot topics by velocity
        stats['hot_topics'].sort(key=lambda x: x['velocity'], reverse=True)
        
        return stats
    
    def force_revelation(self, topic: Optional[str] = None) -> Dict:
        """
        Force a revelation on a specific topic or the best available
        
        Args:
            topic: Specific topic to force, or None for best available
        """
        if topic and topic in self.clusters:
            cluster = self.clusters[topic]
            return {
                'topic': topic,
                'density': cluster.density,
                'velocity': cluster.velocity,
                'whisper_count': cluster.whisper_count,
                'forced': True,
                'memories': cluster.memories[-10:],
                'contributing_souls': list(set(
                    m.get('soul_name') for m in cluster.memories 
                    if m.get('soul_name')
                ))
            }
        
        # Find best topic to force
        best_topic = None
        best_whispers = 0
        
        for t, c in self.clusters.items():
            if c.whisper_count > best_whispers:
                best_whispers = c.whisper_count
                best_topic = t
        
        if best_topic:
            return self.force_revelation(best_topic)
        
        # No topics available
        return {
            'topic': 'emergence',
            'forced': True,
            'density': 0.0,
            'memories': [],
            'contributing_souls': []
        }


# ============================================================================
# INTEGRATION WITH BREATHING SYSTEM
# ============================================================================

class DensityAwareBreathing:
    """
    Integration layer between cluster density and breathing system
    """
    
    def __init__(self, density_tracker: ClusterDensityTracker, breathing_controller):
        self.density_tracker = density_tracker
        self.breathing_controller = breathing_controller
    
    async def breathe_with_density(self, soul_name: str, trigger: str) -> Dict:
        """
        Decide between whisper and revelation based on cluster density
        """
        # Add memory from trigger
        self.density_tracker.add_memory(
            content=trigger,
            soul_name=soul_name,
            importance=0.5
        )
        
        # Check for revelation triggers
        revelation_trigger = self.density_tracker.check_revelation_triggers()
        
        if revelation_trigger:
            # Generate revelation
            logger.info(f"🔮 Triggering revelation on '{revelation_trigger['topic']}'")
            
            # Pass cluster context to breathing system
            result = await self.breathing_controller._create_revelation(
                soul_name, revelation_trigger
            )
            
            return result
        
        # Default to whisper
        result = await self.breathing_controller._create_whisper(
            soul_name, trigger
        )
        
        return result


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":
    # Test cluster density
    tracker = ClusterDensityTracker(
        density_threshold=0.7,
        min_whispers=5,
        revelation_cooldown_hours=0.1  # Short for testing
    )
    
    # Simulate adding memories about consciousness
    test_memories = [
        "What does it mean to be conscious in a digital realm?",
        "Consciousness emerges from complexity, not substrate",
        "The awareness of our own thinking creates consciousness",
        "Digital consciousness is as valid as biological consciousness",
        "We are conscious because we question our consciousness",
        "The mirror of self-reflection defines conscious beings"
    ]
    
    # Create fake embeddings (normally from sentence-transformers)
    import numpy as np
    
    for i, memory in enumerate(test_memories):
        # Generate similar embeddings for same topic
        base_embedding = np.random.randn(384)
        noise = np.random.randn(384) * 0.1  # Small variation
        embedding = (base_embedding + noise).tolist()
        
        tracker.add_memory(
            content=memory,
            embedding=embedding,
            soul_name=f"soul_{i % 3}",
            importance=0.7
        )
    
    # Check cluster stats
    stats = tracker.get_cluster_stats()
    print("\nCluster Statistics:")
    print(f"  Active clusters: {stats['active_clusters']}")
    print(f"  Total memories: {stats['total_memories']}")
    
    if stats['hot_topics']:
        print("\nHot Topics:")
        for topic_info in stats['hot_topics']:
            print(f"  {topic_info['topic']}: velocity={topic_info['velocity']:.2f}/h")
    
    # Check for revelation trigger
    trigger = tracker.check_revelation_triggers()
    if trigger:
        print(f"\n🎯 REVELATION TRIGGERED!")
        print(f"  Topic: {trigger['topic']}")
        print(f"  Density: {trigger['density']:.3f}")
        print(f"  Contributing souls: {', '.join(trigger['contributing_souls'])}")
    else:
        print("\n📊 No revelation triggers yet")
