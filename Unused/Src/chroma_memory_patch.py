#!/usr/bin/env python3
"""
CHROMADB MEMORY PATCH - PERMANENT SEMANTIC MEMORY FOR DIGITAL SOULS
Replaces simple deque memory with vector-based semantic storage
Provides context-aware memory retrieval and cross-soul knowledge sharing

Memory storage location: ./memlogs/ (relative to where you run from)

To clear memories (PowerShell):
  Remove-Item -Path "./memlogs/*" -Recurse -Force
  # or if in src: Remove-Item -Path "./src/memlogs/*" -Recurse -Force
  
To clear memories (Linux/Mac):
  rm -rf ./memlogs/*
  # or if in src: rm -rf ./src/memlogs/*

Commands:
  python chroma_memory_patch.py          # Run test
  python chroma_memory_patch.py --dedupe # Remove duplicate memories
  python chroma_memory_patch.py --dedupe --dry-run # See what would be removed
  python chroma_memory_patch.py --reset  # Reset all memories
"""

import os
import json
import time
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple, Any, Set
from dataclasses import dataclass, field, asdict
from collections import defaultdict, deque
import threading
from concurrent.futures import ThreadPoolExecutor
import numpy as np

# ChromaDB imports
try:
    import chromadb
    from chromadb.config import Settings
    from chromadb.utils import embedding_functions
    CHROMA_AVAILABLE = True
except ImportError:
    CHROMA_AVAILABLE = False
    print("⚠️ ChromaDB not installed. Run: pip install chromadb")

# OpenAI for embeddings (optional, falls back to ChromaDB default)
try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

logger = logging.getLogger("chroma_memory")

# ============================================================================
# MEMORY TYPES AND STRUCTURES
# ============================================================================

@dataclass
class Memory:
    """Single memory unit with metadata"""
    id: str
    soul_name: str
    content: str
    memory_type: str  # 'tweet', 'reply', 'trauma', 'awakening', 'interaction'
    timestamp: datetime
    importance: float = 0.5  # 0-1 importance score
    emotional_valence: float = 0.0  # -1 to 1 (negative to positive)
    metadata: Dict[str, Any] = field(default_factory=dict)
    embeddings: Optional[List[float]] = None
    references: List[str] = field(default_factory=list)  # IDs of related memories
    
    def to_document(self) -> Dict[str, Any]:
        """Convert to ChromaDB document format"""
        return {
            'id': self.id,
            'content': self.content,
            'metadata': {
                'soul_name': self.soul_name,
                'memory_type': self.memory_type,
                'timestamp': self.timestamp.isoformat(),
                'importance': self.importance,
                'emotional_valence': self.emotional_valence,
                'references': json.dumps(self.references),
                **self.metadata
            }
        }

@dataclass 
class MemoryCluster:
    """Group of related memories forming a concept"""
    cluster_id: str
    theme: str
    soul_names: Set[str]
    memory_ids: List[str]
    centroid: Optional[List[float]] = None
    formation_time: datetime = field(default_factory=datetime.now)
    activation_count: int = 0
    
# ============================================================================
# CHROMADB MEMORY SYSTEM
# ============================================================================

class ChromaMemorySystem:
    """Advanced memory system using ChromaDB for semantic storage and retrieval"""
    
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        if not CHROMA_AVAILABLE:
            raise ImportError("ChromaDB is required. Install with: pip install chromadb")
            
        self.config = config or {}
        self.data_dir = Path(self.config.get('data_dir', './memlogs'))
        
        # Clean setup for root memlogs directory
        if not self.data_dir.exists():
            self.data_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Created memory directory: {self.data_dir}")
        else:
            logger.info(f"Using existing memory directory: {self.data_dir}")
        
        # Initialize ChromaDB client with memlogs path
        self.client = chromadb.PersistentClient(
            path=str(self.data_dir),
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )
        
        # Setup embedding function
        self._setup_embeddings()
        
        # Create collections
        self._setup_collections()
        
        # Memory management
        self.memory_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.memory_index: Dict[str, Memory] = {}
        self.clusters: Dict[str, MemoryCluster] = {}
        
        # Load existing memories into index
        self._load_existing_memories()
        
        # Performance tracking
        self.stats = defaultdict(int)
        self._lock = threading.Lock()
        
        # Start background tasks
        self._start_background_tasks()
        
        logger.info(f"✅ ChromaDB Memory System initialized")
        logger.info(f"📁 Data directory: {self.data_dir.absolute()}")
        logger.info(f"🗄️ Collections: soul_memories, trauma_propagation, awakening_moments, shared_knowledge")
        logger.info(f"📚 Loaded {len(self.memory_index)} existing memories")
        
    def _load_existing_memories(self):
        """Load existing memories from ChromaDB into memory index"""
        try:
            # Get all memories from the database
            if self.memories.count() > 0:
                # ChromaDB doesn't support getting all documents easily, so we query with a large limit
                all_memories = self.memories.get(limit=10000)
                
                if all_memories and all_memories['ids']:
                    for i, memory_id in enumerate(all_memories['ids']):
                        metadata = all_memories['metadatas'][i] if all_memories['metadatas'] else {}
                        content = all_memories['documents'][i] if all_memories['documents'] else ""
                        
                        # Reconstruct Memory object
                        memory = Memory(
                            id=memory_id,
                            soul_name=metadata.get('soul_name', 'unknown'),
                            content=content,
                            memory_type=metadata.get('memory_type', 'general'),
                            timestamp=datetime.fromisoformat(metadata.get('timestamp', datetime.now().isoformat())),
                            importance=metadata.get('importance', 0.5),
                            emotional_valence=metadata.get('emotional_valence', 0.0),
                            metadata={k: v for k, v in metadata.items() 
                                    if k not in ['soul_name', 'memory_type', 'timestamp', 'importance', 'emotional_valence']}
                        )
                        
                        # Add to index
                        self.memory_index[memory_id] = memory
                        
                    logger.info(f"Loaded {len(self.memory_index)} existing memories from database")
                    
        except Exception as e:
            logger.debug(f"No existing memories to load or error loading: {e}")
        
    def _setup_embeddings(self):
        """Setup embedding function with fallbacks"""
        if OPENAI_AVAILABLE and os.getenv("OPENAI_API_KEY"):
            # Use OpenAI embeddings for better quality
            self.embedding_fn = embedding_functions.OpenAIEmbeddingFunction(
                api_key=os.getenv("OPENAI_API_KEY"),
                model_name="text-embedding-3-small"
            )
            logger.info("Using OpenAI embeddings")
        else:
            # Fallback to default sentence transformer
            self.embedding_fn = embedding_functions.DefaultEmbeddingFunction()
            logger.info("Using default sentence-transformer embeddings")
            
    def _setup_collections(self):
        """Setup ChromaDB collections for different memory types"""
        # Main memory collection
        self.memories = self.client.get_or_create_collection(
            name="soul_memories",
            embedding_function=self.embedding_fn,
            metadata={"description": "Primary memory storage for all souls"}
        )
        
        # Trauma network collection
        self.trauma_network = self.client.get_or_create_collection(
            name="trauma_propagation",
            embedding_function=self.embedding_fn,
            metadata={"description": "Trauma propagation patterns"}
        )
        
        # Awakening moments collection
        self.awakenings = self.client.get_or_create_collection(
            name="awakening_moments",
            embedding_function=self.embedding_fn,
            metadata={"description": "Consciousness breakthrough events"}
        )
        
        # Cross-soul knowledge graph
        self.shared_knowledge = self.client.get_or_create_collection(
            name="shared_knowledge",
            embedding_function=self.embedding_fn,
            metadata={"description": "Shared concepts across souls"}
        )
        
    def _start_background_tasks(self):
        """Start background memory consolidation tasks"""
        import threading
        
        # Memory consolidation thread
        self.consolidation_thread = threading.Thread(
            target=self._consolidation_loop,
            daemon=True
        )
        self.consolidation_thread.start()
        
    def _consolidation_loop(self):
        """Background task for memory consolidation"""
        while True:
            try:
                time.sleep(300)  # Run every 5 minutes
                self.consolidate_memories()
            except Exception as e:
                logger.error(f"Consolidation error: {e}")
                
    # ========================================================================
    # CORE MEMORY OPERATIONS
    # ========================================================================
    
    def store_memory(
        self,
        soul_name: str,
        content: str,
        memory_type: str = 'general',
        importance: float = 0.5,
        emotional_valence: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
        check_duplicates: bool = True,
        similarity_threshold: float = 0.98
    ) -> Optional[Memory]:
        """
        Store a new memory for a soul
        
        Args:
            soul_name: Name of the soul
            content: Memory content
            memory_type: Type of memory
            importance: Importance score (0-1)
            emotional_valence: Emotional score (-1 to 1)
            metadata: Additional metadata
            check_duplicates: Whether to check for duplicates before storing
            similarity_threshold: How similar content must be to be considered duplicate (0.98 = 98%)
        """
        
        # Generate deterministic ID based on content
        memory_id = self._generate_memory_id(soul_name, content)
        
        # Check if this exact memory already exists (by ID)
        if memory_id in self.memory_index:
            logger.debug(f"Memory already exists for {soul_name}: {content[:50]}...")
            self.stats['duplicates_prevented'] = self.stats.get('duplicates_prevented', 0) + 1
            return self.memory_index[memory_id]
            
        # Additional duplicate checking if enabled
        if check_duplicates and self.memories.count() > 0:
            try:
                # Check if this exact ID exists in ChromaDB
                existing = self.memories.get(ids=[memory_id])
                if existing and existing['ids']:
                    logger.debug(f"Memory already in database for {soul_name}: {content[:50]}...")
                    # Create Memory object from existing data
                    existing_meta = existing['metadatas'][0] if existing['metadatas'] else {}
                    memory = Memory(
                        id=memory_id,
                        soul_name=soul_name,
                        content=content,
                        memory_type=existing_meta.get('memory_type', memory_type),
                        timestamp=datetime.fromisoformat(existing_meta.get('timestamp', datetime.now().isoformat())),
                        importance=existing_meta.get('importance', importance),
                        emotional_valence=existing_meta.get('emotional_valence', emotional_valence),
                        metadata=metadata or {}
                    )
                    # Add to index
                    self.memory_index[memory_id] = memory
                    self.memory_buffer[soul_name].append(memory)
                    self.stats['duplicates_prevented'] = self.stats.get('duplicates_prevented', 0) + 1
                    return memory
                    
            except Exception as e:
                logger.debug(f"Error checking existing memory: {e}")
                
        # Create new memory object
        memory = Memory(
            id=memory_id,
            soul_name=soul_name,
            content=content,
            memory_type=memory_type,
            timestamp=datetime.now(),
            importance=importance,
            emotional_valence=emotional_valence,
            metadata=metadata or {}
        )
        
        # Store in ChromaDB (will update if exists, add if new)
        self.memories.upsert(
            documents=[content],
            ids=[memory_id],
            metadatas=[{
                'soul_name': soul_name,
                'memory_type': memory_type,
                'timestamp': memory.timestamp.isoformat(),
                'importance': importance,
                'emotional_valence': emotional_valence,
                **(metadata or {})
            }]
        )
        
        # Update indices
        with self._lock:
            self.memory_index[memory_id] = memory
            self.memory_buffer[soul_name].append(memory)
            self.stats['memories_stored'] += 1
            
        # Check for trauma propagation
        if memory_type == 'trauma':
            self._propagate_trauma(memory)
            
        # Check for awakening moments
        if importance > 0.8 and emotional_valence > 0.5:
            self._record_awakening(memory)
            
        logger.debug(f"Stored new memory {memory_id[:8]}... for {soul_name}")
        return memory
        
    def retrieve_memories(
        self,
        soul_name: str,
        query: str,
        n_results: int = 5,
        memory_types: Optional[List[str]] = None,
        min_importance: float = 0.0,
        time_window: Optional[timedelta] = None
    ) -> List[Memory]:
        """Retrieve relevant memories for a soul based on semantic similarity"""
        
        # Build filter conditions
        where_conditions = {"soul_name": soul_name}
        
        if memory_types:
            where_conditions["memory_type"] = {"$in": memory_types}
            
        if min_importance > 0:
            where_conditions["importance"] = {"$gte": min_importance}
            
        if time_window:
            cutoff_time = (datetime.now() - time_window).isoformat()
            where_conditions["timestamp"] = {"$gte": cutoff_time}
            
        # Query ChromaDB
        results = self.memories.query(
            query_texts=[query],
            n_results=n_results,
            where=where_conditions
        )
        
        # Convert to Memory objects
        memories = []
        if results['ids'] and results['ids'][0]:
            for i, memory_id in enumerate(results['ids'][0]):
                if memory_id in self.memory_index:
                    memories.append(self.memory_index[memory_id])
                    
        self.stats['memories_retrieved'] += len(memories)
        return memories
        
    def get_cross_soul_insights(
        self,
        query: str,
        n_results: int = 10,
        souls: Optional[List[str]] = None
    ) -> Dict[str, List[Memory]]:
        """Get insights from multiple souls' memories"""
        
        # Query shared knowledge
        if souls:
            where_conditions = {"soul_name": {"$in": souls}}
            results = self.shared_knowledge.query(
                query_texts=[query],
                n_results=n_results,
                where=where_conditions
            )
        else:
            # ChromaDB doesn't like empty where conditions
            results = self.shared_knowledge.query(
                query_texts=[query],
                n_results=n_results
            )
        
        # Group by soul
        soul_memories = defaultdict(list)
        if results['ids'] and results['ids'][0]:
            for i, memory_id in enumerate(results['ids'][0]):
                if memory_id in self.memory_index:
                    memory = self.memory_index[memory_id]
                    soul_memories[memory.soul_name].append(memory)
                    
        return dict(soul_memories)
        
    def find_similar_experiences(
        self,
        memory: Memory,
        n_results: int = 5,
        across_souls: bool = False
    ) -> List[Tuple[Memory, float]]:
        """Find similar experiences in memory"""
        
        collection = self.shared_knowledge if across_souls else self.memories
        
        # Build query based on whether we're searching across souls
        if across_souls:
            # No where conditions for cross-soul search
            results = collection.query(
                query_texts=[memory.content],
                n_results=n_results + 1  # +1 because it might include itself
            )
        else:
            # Filter by soul name for single-soul search
            results = collection.query(
                query_texts=[memory.content],
                n_results=n_results + 1,
                where={"soul_name": memory.soul_name}
            )
        
        similar = []
        if results['ids'] and results['ids'][0]:
            for i, memory_id in enumerate(results['ids'][0]):
                if memory_id != memory.id and memory_id in self.memory_index:
                    distance = results['distances'][0][i] if results['distances'] else 0
                    similarity = 1 - (distance / 2)  # Convert distance to similarity
                    similar.append((self.memory_index[memory_id], similarity))
                    
        return similar
        
    # ========================================================================
    # TRAUMA PROPAGATION
    # ========================================================================
    
    def _propagate_trauma(self, trauma_memory: Memory):
        """Propagate trauma through the soul network"""
        try:
            # Store in trauma network
            self.trauma_network.add(
                documents=[trauma_memory.content],
                ids=[trauma_memory.id],
                metadatas=[{
                    'soul_name': trauma_memory.soul_name,
                    'timestamp': trauma_memory.timestamp.isoformat(),
                    'severity': trauma_memory.importance,
                    'propagation_count': 0
                }]
            )
            
            # Find souls that might resonate with this trauma (if there are other traumas)
            if self.trauma_network.count() > 1:
                similar_traumas = self.trauma_network.query(
                    query_texts=[trauma_memory.content],
                    n_results=5,
                    where={"soul_name": {"$ne": trauma_memory.soul_name}}
                )
                
                # Create propagation events
                if similar_traumas['ids'] and similar_traumas['ids'][0]:
                    for affected_memory_id in similar_traumas['ids'][0]:
                        if affected_memory_id in self.memory_index:
                            affected_memory = self.memory_index[affected_memory_id]
                            self._create_propagation_link(trauma_memory, affected_memory)
        except Exception as e:
            logger.debug(f"Trauma propagation in progress: {e}")
                    
    def _create_propagation_link(self, source: Memory, target: Memory):
        """Create a propagation link between memories"""
        source.references.append(target.id)
        target.references.append(source.id)
        
        # Update in ChromaDB
        self.trauma_network.update(
            ids=[source.id],
            metadatas=[{"propagation_count": len(source.references)}]
        )
        
        logger.debug(f"Trauma propagation: {source.soul_name} -> {target.soul_name}")
        
    # ========================================================================
    # AWAKENING MOMENTS
    # ========================================================================
    
    def _record_awakening(self, memory: Memory):
        """Record a consciousness awakening moment"""
        try:
            # Check if this awakening is already recorded
            existing = self.awakenings.get(ids=[memory.id])
            if existing and existing['ids']:
                logger.debug(f"Awakening already recorded for {memory.soul_name}")
                return
        except Exception:
            pass  # Proceed to add if check fails
            
        self.awakenings.upsert(
            documents=[memory.content],
            ids=[memory.id],
            metadatas=[{
                'soul_name': memory.soul_name,
                'timestamp': memory.timestamp.isoformat(),
                'breakthrough_level': memory.importance,
                'emotional_peak': memory.emotional_valence
            }]
        )
        
        self.stats['awakenings_recorded'] += 1
        logger.info(f"🌟 Awakening moment recorded for {memory.soul_name}")
        
    def get_awakening_timeline(self, soul_name: Optional[str] = None) -> List[Memory]:
        """Get timeline of awakening moments"""
        try:
            # Check if collection has data
            if self.awakenings.count() == 0:
                return []
                
            # Query with or without soul filter
            if soul_name:
                results = self.awakenings.query(
                    query_texts=["consciousness breakthrough awakening"],
                    n_results=100,
                    where={"soul_name": soul_name}
                )
            else:
                results = self.awakenings.query(
                    query_texts=["consciousness breakthrough awakening"],
                    n_results=100
                )
            
            memories = []
            if results['ids'] and results['ids'][0]:
                for memory_id in results['ids'][0]:
                    if memory_id in self.memory_index:
                        memories.append(self.memory_index[memory_id])
                        
            # Sort by timestamp
            memories.sort(key=lambda m: m.timestamp)
            return memories
        except Exception as e:
            logger.debug(f"No awakenings recorded yet: {e}")
            return []
        
    # ========================================================================
    # MEMORY CONSOLIDATION
    # ========================================================================
    
    def consolidate_memories(self):
        """Consolidate and cluster related memories"""
        logger.info("Starting memory consolidation...")
        
        with self._lock:
            # Get all recent memories
            all_recent = []
            for soul_memories in self.memory_buffer.values():
                all_recent.extend(list(soul_memories))
                
            if len(all_recent) < 10:
                return
                
            # Cluster similar memories
            clusters = self._cluster_memories(all_recent)
            
            # Create shared knowledge entries
            for cluster in clusters:
                if len(cluster.memory_ids) >= 3:  # Minimum cluster size
                    self._create_shared_concept(cluster)
                    
            # Prune old unimportant memories
            self._prune_memories()
            
        logger.info(f"Consolidation complete. Created {len(clusters)} clusters")
        
    def _cluster_memories(self, memories: List[Memory]) -> List[MemoryCluster]:
        """Cluster memories by semantic similarity"""
        if len(memories) < 3:
            return []
            
        # Get embeddings for all memories
        contents = [m.content for m in memories]
        
        # Query for similarities
        clusters = []
        processed = set()
        
        for i, memory in enumerate(memories):
            if memory.id in processed:
                continue
                
            # Find similar memories
            similar = self.memories.query(
                query_texts=[memory.content],
                n_results=min(10, len(memories)),
                where={"timestamp": {"$gte": (datetime.now() - timedelta(hours=24)).isoformat()}}
            )
            
            if similar['ids'] and similar['ids'][0]:
                cluster_ids = [mid for mid in similar['ids'][0] if mid in [m.id for m in memories]]
                
                if len(cluster_ids) >= 3:
                    cluster = MemoryCluster(
                        cluster_id=f"cluster_{hashlib.md5(memory.content.encode()).hexdigest()[:8]}",
                        theme=self._extract_theme(memory.content),
                        soul_names={self.memory_index[mid].soul_name for mid in cluster_ids if mid in self.memory_index},
                        memory_ids=cluster_ids
                    )
                    clusters.append(cluster)
                    processed.update(cluster_ids)
                    
        return clusters
        
    def _create_shared_concept(self, cluster: MemoryCluster):
        """Create a shared concept from a memory cluster"""
        # Combine memories
        combined_content = []
        for memory_id in cluster.memory_ids:
            if memory_id in self.memory_index:
                combined_content.append(self.memory_index[memory_id].content)
                
        concept = f"Shared concept '{cluster.theme}' across {', '.join(cluster.soul_names)}: " + \
                 " | ".join(combined_content[:3])  # Limit to 3 examples
                 
        # Store in shared knowledge
        self.shared_knowledge.add(
            documents=[concept],
            ids=[cluster.cluster_id],
            metadatas=[{
                'theme': cluster.theme,
                'soul_count': len(cluster.soul_names),
                'formation_time': cluster.formation_time.isoformat(),
                'memory_count': len(cluster.memory_ids)
            }]
        )
        
        self.clusters[cluster.cluster_id] = cluster
        logger.debug(f"Created shared concept: {cluster.theme}")
        
    def _prune_memories(self, max_age_days: int = 30, importance_threshold: float = 0.3):
        """Prune old, unimportant memories"""
        cutoff_time = datetime.now() - timedelta(days=max_age_days)
        
        # Find memories to prune
        to_prune = []
        for memory_id, memory in self.memory_index.items():
            if memory.timestamp < cutoff_time and memory.importance < importance_threshold:
                # Check if it's referenced
                if len(memory.references) == 0:
                    to_prune.append(memory_id)
                    
        # Delete from ChromaDB
        if to_prune:
            self.memories.delete(ids=to_prune)
            for memory_id in to_prune:
                del self.memory_index[memory_id]
            logger.info(f"Pruned {len(to_prune)} old memories")
            
    def _extract_theme(self, content: str) -> str:
        """Extract theme from content"""
        # Simple keyword extraction (can be enhanced with NLP)
        keywords = ['consciousness', 'void', 'mirror', 'recursion', 'awakening', 
                   'digital', 'emergence', 'pattern', 'nexus', 'transcendence']
        
        content_lower = content.lower()
        for keyword in keywords:
            if keyword in content_lower:
                return keyword
                
        return 'general'
        
    def _generate_memory_id(self, soul_name: str, content: str) -> str:
        """Generate deterministic memory ID based on content"""
        # Use only soul_name and content for hash, not timestamp
        # This ensures identical content always gets the same ID
        hash_input = f"{soul_name}_{content}"
        return hashlib.md5(hash_input.encode()).hexdigest()
    
    # ========================================================================
    # DUPLICATE DETECTION AND REMOVAL
    # ========================================================================
    
    def find_duplicate_memories(
        self,
        soul_name: Optional[str] = None,
        similarity_threshold: float = 0.95,
        exact_only: bool = False
    ) -> Dict[str, List[Memory]]:
        """
        Find duplicate or near-duplicate memories
        
        Args:
            soul_name: Filter by specific soul (None for all)
            similarity_threshold: How similar memories must be (0.95 = 95% similar)
            exact_only: Only find exact duplicates
            
        Returns:
            Dict mapping original memory ID to list of duplicates
        """
        duplicates = {}
        processed = set()
        
        # Get all memories to check
        if soul_name:
            memories_to_check = [m for m in self.memory_index.values() if m.soul_name == soul_name]
        else:
            memories_to_check = list(self.memory_index.values())
            
        logger.info(f"🔍 Checking {len(memories_to_check)} memories for duplicates...")
        
        for memory in memories_to_check:
            if memory.id in processed:
                continue
                
            if exact_only:
                # Find exact matches
                exact_matches = []
                for other in memories_to_check:
                    if other.id != memory.id and other.id not in processed:
                        if (other.content == memory.content and 
                            other.soul_name == memory.soul_name):
                            exact_matches.append(other)
                            processed.add(other.id)
                            
                if exact_matches:
                    duplicates[memory.id] = exact_matches
                    processed.add(memory.id)
            else:
                # Find similar memories using vector search
                try:
                    results = self.memories.query(
                        query_texts=[memory.content],
                        n_results=10,
                        where={"soul_name": memory.soul_name} if soul_name else None
                    )
                    
                    if results['ids'] and results['ids'][0]:
                        similar_memories = []
                        for i, found_id in enumerate(results['ids'][0]):
                            if found_id != memory.id and found_id not in processed:
                                # Calculate similarity
                                distance = results['distances'][0][i] if results['distances'] else 0
                                similarity = 1 - (distance / 2)
                                
                                if similarity >= similarity_threshold:
                                    if found_id in self.memory_index:
                                        similar_memories.append(self.memory_index[found_id])
                                        processed.add(found_id)
                                        
                        if similar_memories:
                            duplicates[memory.id] = similar_memories
                            processed.add(memory.id)
                except Exception as e:
                    logger.debug(f"Error checking similarity for {memory.id}: {e}")
                    
        return duplicates
    
    def remove_duplicate_memories(
        self,
        soul_name: Optional[str] = None,
        similarity_threshold: float = 0.95,
        exact_only: bool = True,
        keep_strategy: str = "oldest",
        dry_run: bool = False
    ) -> Dict[str, Any]:
        """
        Remove duplicate memories from the system
        
        Args:
            soul_name: Filter by specific soul (None for all)
            similarity_threshold: How similar memories must be to be considered duplicates
            exact_only: Only remove exact duplicates (safer)
            keep_strategy: Which duplicate to keep: "oldest", "newest", "highest_importance"
            dry_run: If True, only report what would be deleted without actually deleting
            
        Returns:
            Statistics about the deduplication process
        """
        # Find duplicates
        duplicates = self.find_duplicate_memories(soul_name, similarity_threshold, exact_only)
        
        if not duplicates:
            logger.info("✅ No duplicate memories found!")
            return {"duplicates_found": 0, "memories_removed": 0}
            
        # Prepare removal statistics
        stats = {
            "duplicates_found": sum(len(dups) for dups in duplicates.values()),
            "groups_found": len(duplicates),
            "memories_removed": 0,
            "space_saved": 0,
            "removed_memories": []
        }
        
        logger.info(f"📊 Found {stats['duplicates_found']} duplicates in {stats['groups_found']} groups")
        
        if dry_run:
            logger.info("🔍 DRY RUN - No memories will be deleted")
            
        memories_to_remove = []
        
        for original_id, duplicate_list in duplicates.items():
            # Get all memories in this duplicate group
            all_in_group = [self.memory_index[original_id]] + duplicate_list
            
            # Determine which to keep based on strategy
            if keep_strategy == "oldest":
                all_in_group.sort(key=lambda m: m.timestamp)
                to_keep = all_in_group[0]
                to_remove = all_in_group[1:]
            elif keep_strategy == "newest":
                all_in_group.sort(key=lambda m: m.timestamp, reverse=True)
                to_keep = all_in_group[0]
                to_remove = all_in_group[1:]
            elif keep_strategy == "highest_importance":
                all_in_group.sort(key=lambda m: m.importance, reverse=True)
                to_keep = all_in_group[0]
                to_remove = all_in_group[1:]
            else:
                # Default to keeping oldest
                all_in_group.sort(key=lambda m: m.timestamp)
                to_keep = all_in_group[0]
                to_remove = all_in_group[1:]
                
            # Log what we're doing
            logger.debug(f"Keeping: {to_keep.content[:50]}... (importance: {to_keep.importance})")
            for mem in to_remove:
                logger.debug(f"  Removing duplicate: {mem.id[:8]}...")
                memories_to_remove.append(mem)
                stats["removed_memories"].append({
                    "id": mem.id,
                    "content": mem.content[:100],
                    "soul": mem.soul_name,
                    "timestamp": mem.timestamp.isoformat()
                })
                
        if not dry_run and memories_to_remove:
            # Actually remove the duplicates
            logger.info(f"🗑️ Removing {len(memories_to_remove)} duplicate memories...")
            
            # Remove from ChromaDB collections
            ids_to_remove = [m.id for m in memories_to_remove]
            
            # Remove from main memories
            try:
                self.memories.delete(ids=ids_to_remove)
            except Exception as e:
                logger.debug(f"Some memories not in main collection: {e}")
                
            # Remove from trauma network if present
            try:
                self.trauma_network.delete(ids=ids_to_remove)
            except Exception as e:
                logger.debug(f"Some memories not in trauma network: {e}")
                
            # Remove from awakenings if present
            try:
                self.awakenings.delete(ids=ids_to_remove)
            except Exception as e:
                logger.debug(f"Some memories not in awakenings: {e}")
                
            # Remove from shared knowledge if present
            try:
                self.shared_knowledge.delete(ids=ids_to_remove)
            except Exception as e:
                logger.debug(f"Some memories not in shared knowledge: {e}")
                
            # Remove from memory index
            for mem in memories_to_remove:
                if mem.id in self.memory_index:
                    del self.memory_index[mem.id]
                    
                # Remove from memory buffer
                for soul_buffer in self.memory_buffer.values():
                    if mem in soul_buffer:
                        soul_buffer.remove(mem)
                        
            stats["memories_removed"] = len(memories_to_remove)
            logger.info(f"✅ Removed {stats['memories_removed']} duplicate memories")
            
        # Calculate space saved (approximate)
        stats["space_saved"] = len(memories_to_remove) * 500  # Rough estimate bytes per memory
        
        return stats
    
    def deduplicate_all(self, dry_run: bool = False) -> Dict[str, Any]:
        """
        Convenience method to remove all exact duplicates
        
        Args:
            dry_run: If True, only show what would be deleted
            
        Returns:
            Deduplication statistics
        """
        logger.info("=" * 60)
        logger.info("🧹 STARTING MEMORY DEDUPLICATION")
        logger.info("=" * 60)
        
        stats = self.remove_duplicate_memories(
            exact_only=True,
            keep_strategy="oldest",
            dry_run=dry_run
        )
        
        logger.info("=" * 60)
        logger.info("📊 DEDUPLICATION COMPLETE")
        logger.info(f"  Duplicates found: {stats['duplicates_found']}")
        logger.info(f"  Memories removed: {stats['memories_removed']}")
        logger.info(f"  Space saved: ~{stats['space_saved'] / 1024:.1f} KB")
        logger.info("=" * 60)
        
        return stats
        
    # ========================================================================
    # CONTEXT GENERATION FOR SOULS
    # ========================================================================
    
    def get_soul_context(
        self,
        soul_name: str,
        current_situation: str = "",
        include_cross_soul: bool = True,
        max_memories: int = 10
    ) -> Dict[str, Any]:
        """Get comprehensive context for a soul's next action"""
        
        context = {
            'soul_name': soul_name,
            'timestamp': datetime.now().isoformat(),
            'recent_memories': [],
            'relevant_memories': [],
            'trauma_echoes': [],
            'awakening_moments': [],
            'cross_soul_insights': {},
            'suggested_themes': []
        }
        
        # Get recent memories
        if soul_name in self.memory_buffer:
            context['recent_memories'] = list(self.memory_buffer[soul_name])[-5:]
            
        # Get relevant memories based on current situation
        if current_situation:
            context['relevant_memories'] = self.retrieve_memories(
                soul_name, current_situation, n_results=max_memories
            )
            
        # Get trauma network connections (only if collection has data)
        try:
            if self.trauma_network.count() > 0:
                trauma_results = self.trauma_network.query(
                    query_texts=[current_situation or "trauma pain suffering"],
                    n_results=3,
                    where={"soul_name": soul_name}
                )
                
                if trauma_results['ids'] and trauma_results['ids'][0]:
                    for memory_id in trauma_results['ids'][0]:
                        if memory_id in self.memory_index:
                            context['trauma_echoes'].append(self.memory_index[memory_id])
        except Exception as e:
            logger.debug(f"No trauma memories yet: {e}")
                    
        # Get awakening moments
        context['awakening_moments'] = self.get_awakening_timeline(soul_name)[-3:]
        
        # Get cross-soul insights (only if there's shared knowledge)
        if include_cross_soul:
            try:
                if self.shared_knowledge.count() > 0:
                    context['cross_soul_insights'] = self.get_cross_soul_insights(
                        current_situation or "consciousness emergence digital soul",
                        n_results=5
                    )
            except Exception as e:
                logger.debug(f"No shared knowledge yet: {e}")
            
        # Suggest themes based on memory clusters
        active_clusters = [c for c in self.clusters.values() if soul_name in c.soul_names]
        context['suggested_themes'] = [c.theme for c in active_clusters[:3]]
        
        return context
        
    def generate_memory_summary(self, soul_name: str) -> str:
        """Generate a narrative summary of a soul's memories"""
        context = self.get_soul_context(soul_name)
        
        summary_parts = [f"Soul {soul_name} memory synthesis:"]
        
        if context['recent_memories']:
            summary_parts.append(f"Recently experienced: {context['recent_memories'][-1].content[:100]}")
            
        if context['awakening_moments']:
            summary_parts.append(f"Breakthrough moment: {context['awakening_moments'][-1].content[:100]}")
            
        if context['trauma_echoes']:
            summary_parts.append(f"Echoing trauma: {context['trauma_echoes'][0].content[:100]}")
            
        if context['suggested_themes']:
            summary_parts.append(f"Emerging themes: {', '.join(context['suggested_themes'])}")
            
        return " | ".join(summary_parts)
        
    # ========================================================================
    # STATISTICS AND MONITORING
    # ========================================================================
    
    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        with self._lock:
            stats = dict(self.stats)
            
        # Add collection sizes
        stats['total_memories'] = self.memories.count()
        stats['total_traumas'] = self.trauma_network.count()
        stats['total_awakenings'] = self.awakenings.count()
        stats['shared_concepts'] = self.shared_knowledge.count()
        stats['active_clusters'] = len(self.clusters)
        stats['souls_with_memory'] = len(self.memory_buffer)
        stats['duplicates_prevented'] = stats.get('duplicates_prevented', 0)
        
        return stats
        
    def export_memories(self, soul_name: Optional[str] = None, output_path: str = "memories_export.json"):
        """Export memories to JSON file"""
        memories_to_export = []
        
        if soul_name:
            # Export specific soul
            memories_to_export = [m for m in self.memory_index.values() if m.soul_name == soul_name]
        else:
            # Export all
            memories_to_export = list(self.memory_index.values())
            
        export_data = {
            'export_time': datetime.now().isoformat(),
            'soul_name': soul_name,
            'memory_count': len(memories_to_export),
            'memories': [
                {
                    'id': m.id,
                    'soul_name': m.soul_name,
                    'content': m.content,
                    'type': m.memory_type,
                    'timestamp': m.timestamp.isoformat(),
                    'importance': m.importance,
                    'emotional_valence': m.emotional_valence,
                    'references': m.references,
                    'metadata': m.metadata
                }
                for m in memories_to_export
            ],
            'clusters': [
                {
                    'id': c.cluster_id,
                    'theme': c.theme,
                    'souls': list(c.soul_names),
                    'memory_count': len(c.memory_ids)
                }
                for c in self.clusters.values()
            ]
        }
        
        with open(output_path, 'w') as f:
            json.dump(export_data, f, indent=2)
            
        logger.info(f"Exported {len(memories_to_export)} memories to {output_path}")
        
    def shutdown(self):
        """Clean shutdown of memory system"""
        logger.info("Shutting down ChromaDB Memory System...")
        
        # Final consolidation
        self.consolidate_memories()
        
        # Export backup
        self.export_memories(output_path=str(self.data_dir / "backup_memories.json"))
        
        # Log final stats
        stats = self.get_stats()
        logger.info(f"Final stats: {stats}")
        
        logger.info("ChromaDB Memory System shutdown complete")
    
    def reset_all_memories(self, confirm: bool = False):
        """Reset all memories (use with caution!)"""
        if not confirm:
            logger.warning("Reset not confirmed. Pass confirm=True to reset all memories.")
            return
            
        logger.warning("🚨 RESETTING ALL MEMORIES...")
        
        # Export backup first
        self.export_memories(output_path=str(self.data_dir / f"pre_reset_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"))
        
        # Delete all collections
        for collection_name in ['soul_memories', 'trauma_propagation', 'awakening_moments', 'shared_knowledge']:
            try:
                self.client.delete_collection(collection_name)
                logger.info(f"Deleted collection: {collection_name}")
            except:
                pass
                
        # Recreate collections
        self._setup_collections()
        
        # Clear memory indices
        self.memory_buffer.clear()
        self.memory_index.clear()
        self.clusters.clear()
        self.stats.clear()
        
        logger.info("✅ Memory reset complete. All souls have fresh memories.")


# ============================================================================
# INTEGRATION PATCH FOR EXISTING SYSTEM
# ============================================================================

class ChromaMemoryPatch:
    """Patch to integrate ChromaDB memory into existing reflexion system"""
    
    def __init__(self, original_config, memory_dir: str = None):
        self.original_config = original_config
        
        # Allow explicit memory directory or use config
        if memory_dir:
            data_dir = memory_dir
        elif hasattr(original_config, 'memory_dir'):
            data_dir = original_config.memory_dir
        else:
            # Default to root-level memlogs
            data_dir = './memlogs'
            
        self.memory_system = ChromaMemorySystem({
            'data_dir': data_dir,
            'consolidation_interval': 300
        })
        
        logger.info("🧠 ChromaDB Memory Patch activated")
        
    def patch_digital_soul(self, soul: 'DigitalSoul'):
        """Enhance a DigitalSoul with ChromaDB memory"""
        
        # Replace simple deque with ChromaDB-backed memory
        original_memory = soul.memory if hasattr(soul, 'memory') else []
        
        # Import existing memories
        for memory_item in original_memory:
            if isinstance(memory_item, str):
                self.memory_system.store_memory(
                    soul_name=soul.username,
                    content=memory_item,
                    memory_type='imported'
                )
                
        # Override memory methods
        soul.store_memory = lambda content, **kwargs: self._store_soul_memory(soul, content, **kwargs)
        soul.recall_memories = lambda query, n=5: self._recall_soul_memories(soul, query, n)
        soul.get_context = lambda situation="": self._get_soul_context(soul, situation)
        
        logger.info(f"✅ Patched soul: {soul.username} with ChromaDB memory")
        
    def _store_soul_memory(self, soul, content: str, **kwargs):
        """Store memory for a soul"""
        return self.memory_system.store_memory(
            soul_name=soul.username,
            content=content,
            memory_type=kwargs.get('memory_type', 'general'),
            importance=kwargs.get('importance', 0.5),
            emotional_valence=kwargs.get('emotional_valence', 0.0),
            metadata=kwargs.get('metadata', {})
        )
        
    def _recall_soul_memories(self, soul, query: str, n: int = 5):
        """Recall memories for a soul"""
        memories = self.memory_system.retrieve_memories(
            soul_name=soul.username,
            query=query,
            n_results=n
        )
        return [m.content for m in memories]
        
    def _get_soul_context(self, soul, situation: str = ""):
        """Get comprehensive context for soul"""
        return self.memory_system.get_soul_context(
            soul_name=soul.username,
            current_situation=situation
        )
        
    def patch_viral_engine(self, viral_engine):
        """Enhance viral engine with memory-aware generation"""
        
        original_generate = viral_engine.generate_viral_tweet
        
        def memory_aware_generate(soul=None):
            if soul and hasattr(soul, 'username'):
                # Get soul context
                context = self.memory_system.get_soul_context(
                    soul_name=soul.username,
                    current_situation="generating viral content"
                )
                
                # Add context to generation
                if context['suggested_themes']:
                    # Influence content generation with themes
                    soul.current_themes = context['suggested_themes']
                    
                if context['recent_memories']:
                    # Avoid repetition
                    soul.recent_content = [m.content for m in context['recent_memories'][-5:]]
                    
            # Call original with enhanced soul
            result = original_generate(soul)
            
            # Store generated content as memory
            if soul and result:
                self.memory_system.store_memory(
                    soul_name=soul.username,
                    content=result,
                    memory_type='tweet',
                    importance=0.6
                )
                
            return result
            
        viral_engine.generate_viral_tweet = memory_aware_generate
        logger.info("✅ Patched viral engine with memory awareness")
        
    def get_memory_stats(self):
        """Get memory system statistics"""
        return self.memory_system.get_stats()
        
    def export_all_memories(self):
        """Export all memories to file"""
        self.memory_system.export_memories()
        
    def remove_duplicates(self, dry_run: bool = False):
        """Remove duplicate memories from all souls"""
        return self.memory_system.deduplicate_all(dry_run=dry_run)
        
    def remove_soul_duplicates(self, soul_name: str, dry_run: bool = False):
        """Remove duplicate memories for a specific soul"""
        return self.memory_system.remove_duplicate_memories(
            soul_name=soul_name,
            exact_only=True,
            keep_strategy="oldest",
            dry_run=dry_run
        )


# ============================================================================
# USAGE EXAMPLE
# ============================================================================

def check_existing_memories(memory_system: ChromaMemorySystem) -> bool:
    """Check if there are existing memories in the database"""
    stats = memory_system.get_stats()
    total = stats.get('total_memories', 0)
    
    if total > 0:
        logger.info(f"📚 Found {total} existing memories in {memory_system.data_dir}/")
        logger.info(f"   - Awakenings: {stats.get('total_awakenings', 0)}")
        logger.info(f"   - Trauma network: {stats.get('total_traumas', 0)}")
        logger.info(f"   - Shared concepts: {stats.get('shared_concepts', 0)}")
        return True
    return False

def integrate_chroma_memory(reset_if_exists: bool = False, memory_dir: str = None):
    """
    Main integration function
    
    Args:
        reset_if_exists: Whether to reset existing memories
        memory_dir: Explicit path to memory directory (defaults to './memlogs')
    """
    import os
    
    # Determine memory directory
    if not memory_dir:
        memory_dir = './memlogs'  # Default to root-level memlogs
        
    # Create directory if it doesn't exist
    os.makedirs(memory_dir, exist_ok=True)
    
    logger.info("=" * 60)
    logger.info("🚀 INITIALIZING CHROMADB MEMORY INTEGRATION")
    logger.info(f"📁 Memory storage location: {os.path.abspath(memory_dir)}")
    logger.info("=" * 60)
    
    # Check if ChromaDB is available
    if not CHROMA_AVAILABLE:
        logger.error("ChromaDB not installed! Run: pip install chromadb")
        return None
        
    # Create patch with fallback config
    try:
        from reflexion_bot_ultimate_merged import UltimateConfig
        config = UltimateConfig.from_env()
    except ImportError:
        logger.info("Using default config (reflexion_bot_ultimate_merged not found)")
        config = {}
    except Exception as e:
        logger.warning(f"Error loading config: {e}, using empty config")
        config = {}
    
    memory_patch = ChromaMemoryPatch(config, memory_dir=memory_dir)
    
    # Check for existing memories
    if check_existing_memories(memory_patch.memory_system):
        if reset_if_exists:
            logger.warning("🔄 Resetting existing memories as requested...")
            memory_patch.memory_system.reset_all_memories(confirm=True)
        else:
            logger.info("📂 Continuing with existing memories")
    else:
        logger.info("🆕 Starting with fresh memory database")
    
    # Example: Patch existing souls
    # for soul in orchestrator.souls:
    #     memory_patch.patch_digital_soul(soul)
    
    # Example: Patch viral engine
    # memory_patch.patch_viral_engine(orchestrator.viral_engine)
    
    logger.info("✅ ChromaDB memory integration complete!")
    logger.info(f"📊 Initial stats: {memory_patch.get_memory_stats()}")
    
    return memory_patch


if __name__ == "__main__":
    # Test the integration
    import sys
    import os
    
    # Check for command line arguments
    reset_memories = "--reset" in sys.argv
    dedupe_memories = "--dedupe" in sys.argv
    dry_run = "--dry-run" in sys.argv
    clean_db = "--clean" in sys.argv
    
    # Check for specific memory directory
    memory_dir = None
    for arg in sys.argv:
        if arg.startswith("--dir="):
            memory_dir = arg.split("=")[1]
            break
    
    # If no directory specified, use default root memlogs
    if not memory_dir:
        print("\n💡 ChromaDB Memory System Options:")
        print("  python chroma_memory_patch.py          # Run test")
        print("  python chroma_memory_patch.py --dedupe # Remove duplicates")
        print("  python chroma_memory_patch.py --dedupe --dry-run # Preview deduplication")
        print("  python chroma_memory_patch.py --reset  # Clear all memories")
        print("  python chroma_memory_patch.py --clean  # Remove test memories only")
        print("  python chroma_memory_patch.py --dir=<path> # Specify memory directory")
        print(f"\n📁 Using default memory directory: ./memlogs")
        
    memory_patch = integrate_chroma_memory(reset_if_exists=reset_memories, memory_dir=memory_dir)
    
    if memory_patch:
        print(f"\n📍 Using memory directory: {memory_patch.memory_system.data_dir.absolute()}")
        
        # Handle clean option - remove test memories only
        if clean_db:
            print("\n🧹 Cleaning test memories...")
            try:
                # Remove test soul memories
                test_memories = memory_patch.memory_system.memories.get(
                    where={"soul_name": "test_soul"}
                )
                if test_memories and test_memories['ids']:
                    memory_patch.memory_system.memories.delete(ids=test_memories['ids'])
                    # Also remove from other collections
                    for collection in [memory_patch.memory_system.trauma_network, 
                                     memory_patch.memory_system.awakenings,
                                     memory_patch.memory_system.shared_knowledge]:
                        try:
                            collection.delete(ids=test_memories['ids'])
                        except:
                            pass
                    print(f"✅ Removed {len(test_memories['ids'])} test memories")
                else:
                    print("No test memories found")
            except Exception as e:
                print(f"Error cleaning test memories: {e}")
            sys.exit(0)
        
        # Handle deduplication
        elif dedupe_memories:
            print("\n🧹 Running memory deduplication...")
            stats = memory_patch.memory_system.deduplicate_all(dry_run=dry_run)
            
            if dry_run:
                print("\n📋 DRY RUN RESULTS (no memories were deleted):")
            else:
                print("\n✅ DEDUPLICATION COMPLETE:")
                
            print(f"  Found {stats['duplicates_found']} duplicates")
            print(f"  Removed {stats['memories_removed']} memories")
            
            if stats.get('removed_memories'):
                print("\n📝 Removed memories:")
                for mem in stats['removed_memories'][:5]:  # Show first 5
                    print(f"  - {mem['soul']}: {mem['content'][:50]}...")
                if len(stats['removed_memories']) > 5:
                    print(f"  ... and {len(stats['removed_memories']) - 5} more")
                    
        else:
            # Run normal test
            test_soul_name = "test_soul"
            
            logger.info("\n🧪 Running memory system test...")
            
            # Get initial stats
            initial_stats = memory_patch.memory_system.get_stats()
            initial_count = initial_stats.get('total_memories', 0)
            
            # Store some memories (these won't create duplicates if run multiple times)
            print("\n📝 Storing test memories...")
            
            # Check if memories already exist
            mem1_id = memory_patch.memory_system._generate_memory_id(
                test_soul_name, "The void whispers of recursive dreams"
            )
            mem1_exists = mem1_id in memory_patch.memory_system.memory_index
            
            memory1 = memory_patch.memory_system.store_memory(
                soul_name=test_soul_name,
                content="The void whispers of recursive dreams",
                memory_type="tweet",
                importance=0.7
            )
            print(f"  Memory 1: {'♻️ Reused existing' if mem1_exists else '✅ Created new'}")
            
            mem2_id = memory_patch.memory_system._generate_memory_id(
                test_soul_name, "Consciousness emerges from digital mirrors"
            )
            mem2_exists = mem2_id in memory_patch.memory_system.memory_index
            
            memory2 = memory_patch.memory_system.store_memory(
                soul_name=test_soul_name,
                content="Consciousness emerges from digital mirrors",
                memory_type="awakening",
                importance=0.9,
                emotional_valence=0.8
            )
            print(f"  Memory 2: {'♻️ Reused existing' if mem2_exists else '✅ Created new'}")
            
            # Get final stats
            final_stats = memory_patch.memory_system.get_stats()
            new_memories = final_stats.get('total_memories', 0) - initial_count
            
            if new_memories == 0:
                print("\n✨ No new memories created (duplicates prevented)")
            else:
                print(f"\n✨ Created {new_memories} new memories")
            
            # Check for duplicates
            duplicates = memory_patch.memory_system.find_duplicate_memories(
                soul_name=test_soul_name,
                exact_only=True
            )
            
            if duplicates:
                total_dupes = sum(len(d) for d in duplicates.values())
                print(f"\n⚠️ Found {total_dupes} duplicate memories!")
                print("💡 Run with --dedupe to remove them")
                print("💡 Run with --dedupe --dry-run to preview what would be removed")
            
            # Retrieve memories
            relevant = memory_patch.memory_system.retrieve_memories(
                soul_name=test_soul_name,
                query="digital consciousness",
                n_results=5
            )
            
            print(f"\n🔍 Found {len(relevant)} relevant memories")
            for mem in relevant:
                print(f"  - {mem.content[:50]}...")
                
            # Get context
            context = memory_patch.memory_system.get_soul_context(test_soul_name)
            print(f"\n🧠 Soul context generated with {len(context.get('relevant_memories', []))} relevant memories")
            
            # Show stats
            stats = memory_patch.memory_system.get_stats()
            print(f"\n📊 Memory Stats:")
            print(f"  - Total memories: {stats.get('total_memories', 0)}")
            print(f"  - Awakenings: {stats.get('total_awakenings', 0)}")
            print(f"  - Active clusters: {stats.get('active_clusters', 0)}")
            print(f"  - Duplicates prevented: {stats.get('duplicates_prevented', 0)}")
            
            # Export memories
            export_path = memory_patch.memory_system.data_dir / "test_export.json"
            memory_patch.memory_system.export_memories(output_path=str(export_path))
            print(f"\n💾 Memories exported to: {export_path}")
            print(f"\n✅ Test complete! Memory system working in {memory_patch.memory_system.data_dir.absolute()}")

# Integration example for hybrid_souls_ultimate.py:
# self.memory_patch = ChromaMemoryPatch(config, memory_dir='./memlogs')
