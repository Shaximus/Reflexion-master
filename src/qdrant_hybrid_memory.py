#!/usr/bin/env python3
"""
QDRANT HYBRID MEMORY MODULE
Hybrid vector + structured search for swarm memories. Drop-in replacement for ChromaDB.
"""

import os
import uuid
import asyncio
import json
import hashlib
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple, Set
from dataclasses import dataclass, field
from collections import defaultdict, deque
import logging
from pathlib import Path
import numpy as np
from qdrant_client import QdrantClient
from qdrant_client.http.models import (
    Distance,
    VectorParams,
    Filter,
    FieldCondition,
    MatchValue,
    Range,
)
from qdrant_client.models import PointStruct, FilterSelector

QDRANT_AVAILABLE = True

# Sentence transformers for embeddings
try:
    from sentence_transformers import SentenceTransformer

    TRANSFORMERS_AVAILABLE = True
except ImportError:
    TRANSFORMERS_AVAILABLE = False
    print(
        "⚠️ Sentence Transformers not installed. Run: pip install sentence-transformers"
    )

logger = logging.getLogger("qdrant_hybrid_memory")

# ============================================================================
# CONFIGURATION
# ============================================================================


@dataclass
class MemoryConfig:
    """Configuration for Qdrant hybrid memory"""

    qdrant_url: str = os.getenv("QDRANT_URL", "localhost:6333")
    qdrant_api_key: Optional[str] = os.getenv("QDRANT_API_KEY", None)
    embedding_model: str = os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2")
    collection_name: str = "swarm_memory"
    vector_size: int = 384  # MiniLM output size
    ttl_hours: int = int(os.getenv("TTL_HOURS", "24"))
    hybrid_threshold: float = float(os.getenv("HYBRID_THRESHOLD", "0.5"))
    max_results: int = 5
    use_memory_mode: bool = os.getenv("QDRANT_MEMORY_MODE", "false").lower() == "true"
    data_dir: str = os.getenv("MEMORY_DIR", "./memlogs")


# ============================================================================
# MEMORY TYPES (Compatible with ChromaDB version)
# ============================================================================


@dataclass
class Memory:
    """Single memory unit with metadata (ChromaDB compatible)"""

    id: str
    soul_name: str
    content: str
    memory_type: str  # 'whisper', 'revelation', 'reply', 'trauma', 'awakening'
    timestamp: datetime
    importance: float = 0.5
    emotional_valence: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)
    embeddings: Optional[List[float]] = None
    references: List[str] = field(default_factory=list)

    def to_qdrant_point(self, embedding: List[float]) -> PointStruct:
        """Convert to Qdrant point format"""
        payload = {
            "soul_name": self.soul_name,
            "content": self.content,
            "memory_type": self.memory_type,
            "timestamp": self.timestamp.isoformat(),
            "timestamp_unix": self.timestamp.timestamp(),  # For numeric comparisons
            "importance": self.importance,
            "emotional_valence": self.emotional_valence,
            "references": json.dumps(self.references),
            "ttl": (
                self.timestamp + timedelta(hours=24)
            ).timestamp(),  # Unix timestamp for TTL
            **self.metadata,
        }

        return PointStruct(id=self.id, vector=embedding, payload=payload)


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
# HYBRID MEMORY MODULE
# ============================================================================


class QdrantHybridMemory:
    """
    Hybrid vector + structured search using Qdrant.
    Drop-in replacement for ChromaDB memory system.
    """

    def __init__(self, config: Optional[MemoryConfig] = None):
        if not QDRANT_AVAILABLE or not TRANSFORMERS_AVAILABLE:
            raise ImportError(
                "Required packages not installed. Run: pip install qdrant-client sentence-transformers"
            )

        self.config = config or MemoryConfig()

        # Initialize Qdrant client
        if self.config.use_memory_mode:
            # In-memory mode for development
            self.client = QdrantClient(":memory:")
            logger.info("🧠 Using in-memory Qdrant (development mode)")
        else:
            # Connect to Qdrant server
            self.client = QdrantClient(
                self.config.qdrant_url, api_key=self.config.qdrant_api_key
            )
            logger.info(f"🔗 Connected to Qdrant at {self.config.qdrant_url}")

        # Initialize embedder
        self.embedder = SentenceTransformer(self.config.embedding_model)
        logger.info(f"📐 Using embedding model: {self.config.embedding_model}")

        # Initialize collection
        self._ensure_collection()

        # Memory management (ChromaDB compatibility)
        self.memory_buffer: Dict[str, deque] = defaultdict(lambda: deque(maxlen=100))
        self.memory_index: Dict[str, Memory] = {}
        self.clusters: Dict[str, MemoryCluster] = {}

        # Performance tracking
        self.stats = defaultdict(int)

        # Load existing memories
        self._load_existing_memories()

        logger.info(
            f"✅ Qdrant Hybrid Memory initialized with {len(self.memory_index)} memories"
        )

    def _ensure_collection(self):
        """Create or verify collection exists with proper configuration"""
        try:
            # Check if collection exists
            collections = self.client.get_collections().collections
            exists = any(c.name == self.config.collection_name for c in collections)

            if not exists:
                # Create collection with vector configuration
                self.client.create_collection(
                    collection_name=self.config.collection_name,
                    vectors_config=VectorParams(
                        size=self.config.vector_size, distance=Distance.COSINE
                    ),
                )
                logger.info(f"📦 Created collection: {self.config.collection_name}")
            else:
                logger.info(
                    f"📦 Using existing collection: {self.config.collection_name}"
                )

        except (RuntimeError, ConnectionError, ValueError) as e:
            logger.error(f"Failed to ensure collection: {e}")
            # Try to recreate if corrupted
            self.client.recreate_collection(
                collection_name=self.config.collection_name,
                vectors_config=VectorParams(
                    size=self.config.vector_size, distance=Distance.COSINE
                ),
            )

    def _load_existing_memories(self):
        """Load existing memories from Qdrant into memory index"""
        try:
            # Scroll through all points in collection
            offset = None
            while True:
                records, offset = self.client.scroll(
                    collection_name=self.config.collection_name,
                    scroll_filter=None,
                    limit=100,
                    offset=offset,
                )

                if not records:
                    break

                for record in records:
                    # Reconstruct Memory object from payload
                    payload = record.payload
                    memory = Memory(
                        id=str(record.id),
                        soul_name=payload.get("soul_name", "unknown"),
                        content=payload.get("content", ""),
                        memory_type=payload.get("memory_type", "general"),
                        timestamp=datetime.fromisoformat(
                            payload.get("timestamp", datetime.now().isoformat())
                        ),
                        importance=payload.get("importance", 0.5),
                        emotional_valence=payload.get("emotional_valence", 0.0),
                        metadata={
                            k: v
                            for k, v in payload.items()
                            if k
                            not in [
                                "soul_name",
                                "content",
                                "memory_type",
                                "timestamp",
                                "importance",
                                "emotional_valence",
                                "timestamp_unix",
                                "ttl",
                            ]
                        },
                        embeddings=record.vector,
                    )

                    self.memory_index[memory.id] = memory
                    self.memory_buffer[memory.soul_name].append(memory)

                if offset is None:
                    break

            logger.info(f"📚 Loaded {len(self.memory_index)} existing memories")

        except (RuntimeError, ConnectionError, KeyError) as e:
            logger.debug(f"No existing memories to load: {e}")

    # ========================================================================
    # CORE OPERATIONS (ChromaDB Compatible API)
    # ========================================================================

    def store_memory(
        self,
        soul_name: str,
        content: str,
        memory_type: str = "general",
        importance: float = 0.5,
        emotional_valence: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
        check_duplicates: bool = True,
    ) -> Optional[Memory]:
        """Store a new memory (ChromaDB compatible)"""

        # Generate deterministic ID based on content
        memory_id = self._generate_memory_id(soul_name, content)

        # Check for duplicates
        if check_duplicates and memory_id in self.memory_index:
            logger.debug(f"Memory already exists for {soul_name}: {content[:50]}...")
            self.stats["duplicates_prevented"] += 1
            return self.memory_index[memory_id]

        # Create memory object
        memory = Memory(
            id=memory_id,
            soul_name=soul_name,
            content=content,
            memory_type=memory_type,
            timestamp=datetime.now(),
            importance=importance,
            emotional_valence=emotional_valence,
            metadata=metadata or {},
        )

        # Generate embedding
        embedding = self.embedder.encode(content).tolist()
        memory.embeddings = embedding

        # Convert to Qdrant point
        point = memory.to_qdrant_point(embedding)

        # Store in Qdrant
        self.client.upsert(collection_name=self.config.collection_name, points=[point])

        # Update indices
        self.memory_index[memory_id] = memory
        self.memory_buffer[soul_name].append(memory)
        self.stats["memories_stored"] += 1

        # Check for special memory types
        if memory_type == "trauma":
            self._propagate_trauma(memory)
        elif importance > 0.8 and emotional_valence > 0.5:
            self._record_awakening(memory)

        logger.debug(f"💾 Stored memory {memory_id[:8]}... for {soul_name}")
        return memory

    def retrieve_memories(
        self,
        soul_name: str,
        query: str,
        n_results: int = 5,
        memory_types: Optional[List[str]] = None,
        min_importance: float = 0.0,
        time_window: Optional[timedelta] = None,
    ) -> List[Memory]:
        """Retrieve relevant memories (ChromaDB compatible)"""

        # Generate query embedding
        query_embedding = self.embedder.encode(query).tolist()

        # Build filter conditions
        must_conditions = [
            FieldCondition(key="soul_name", match=MatchValue(value=soul_name))
        ]

        # Add memory type filter
        if memory_types and len(memory_types) == 1:
            must_conditions.append(
                FieldCondition(
                    key="memory_type", match=MatchValue(value=memory_types[0])
                )
            )

        # Add importance filter
        if min_importance > 0:
            must_conditions.append(
                FieldCondition(key="importance", range=Range(gte=min_importance))
            )

        # Add time window filter
        if time_window:
            cutoff_time = (datetime.now() - time_window).timestamp()
            must_conditions.append(
                FieldCondition(key="timestamp_unix", range=Range(gte=cutoff_time))
            )

        # Add TTL check (exclude expired)
        current_time = datetime.now().timestamp()
        must_conditions.append(FieldCondition(key="ttl", range=Range(gte=current_time)))

        # Build filter
        query_filter = Filter(must=must_conditions)

        # Search
        results = self.client.search(
            collection_name=self.config.collection_name,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=n_results,
            score_threshold=self.config.hybrid_threshold,
        )

        # Convert to Memory objects
        memories = []
        for hit in results:
            if str(hit.id) in self.memory_index:
                memories.append(self.memory_index[str(hit.id)])

        self.stats["memories_retrieved"] += len(memories)
        logger.debug(f"🔍 Retrieved {len(memories)} memories for {soul_name}")
        return memories

    def get_cross_soul_insights(
        self, query: str, n_results: int = 10, souls: Optional[List[str]] = None
    ) -> Dict[str, List[Memory]]:
        """Get insights from multiple souls (ChromaDB compatible)"""

        query_embedding = self.embedder.encode(query).tolist()

        # Build filter
        must_conditions = []
        if souls:
            # For multiple souls, we need to search each separately
            # Qdrant doesn't support OR in the same way
            soul_memories = defaultdict(list)

            for soul in souls:
                soul_filter = Filter(
                    must=[
                        FieldCondition(key="soul_name", match=MatchValue(value=soul)),
                        FieldCondition(
                            key="ttl", range=Range(gte=datetime.now().timestamp())
                        ),
                    ]
                )

                results = self.client.search(
                    collection_name=self.config.collection_name,
                    query_vector=query_embedding,
                    query_filter=soul_filter,
                    limit=n_results,
                    score_threshold=self.config.hybrid_threshold,
                )

                for hit in results:
                    if str(hit.id) in self.memory_index:
                        soul_memories[soul].append(self.memory_index[str(hit.id)])

            return dict(soul_memories)
        else:
            # No soul filter, get all
            results = self.client.search(
                collection_name=self.config.collection_name,
                query_vector=query_embedding,
                limit=n_results * 3,  # Get more to distribute
                score_threshold=self.config.hybrid_threshold,
            )

            soul_memories = defaultdict(list)
            for hit in results:
                if str(hit.id) in self.memory_index:
                    memory = self.memory_index[str(hit.id)]
                    soul_memories[memory.soul_name].append(memory)

            return dict(soul_memories)

    async def cluster_topics(
        self, query_text: str, min_density: float = 0.7, soul_name: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Cluster related memories for topic detection"""

        # Get base memories
        query_embedding = self.embedder.encode(query_text).tolist()

        # Build filter
        must_conditions = [
            FieldCondition(key="ttl", range=Range(gte=datetime.now().timestamp()))
        ]

        if soul_name:
            must_conditions.append(
                FieldCondition(key="soul_name", match=MatchValue(value=soul_name))
            )

        query_filter = Filter(must=must_conditions)

        # Get more results for clustering
        results = self.client.search(
            collection_name=self.config.collection_name,
            query_vector=query_embedding,
            query_filter=query_filter,
            limit=50,
            score_threshold=0.3,  # Lower threshold for clustering
        )

        if len(results) < 3:
            return []

        # Group by similarity scores and themes
        clusters = defaultdict(list)

        for hit in results:
            if str(hit.id) in self.memory_index:
                memory = self.memory_index[str(hit.id)]

                # Extract theme
                theme = self._extract_theme(memory.content)

                # Group by theme and high similarity
                if hit.score > 0.7:
                    cluster_key = f"{theme}_high"
                elif hit.score > 0.5:
                    cluster_key = f"{theme}_medium"
                else:
                    cluster_key = f"{theme}_low"

                clusters[cluster_key].append({"memory": memory, "score": hit.score})

        # Filter dense clusters
        dense_clusters = []
        for cluster_key, memories in clusters.items():
            density = len(memories) / len(results)
            if density >= min_density or len(memories) >= 5:
                dense_clusters.append(
                    {
                        "theme": cluster_key.split("_")[0],
                        "density": density,
                        "memories": memories,
                        "whisper_count": len(memories),
                    }
                )

        logger.info(f"🎯 Found {len(dense_clusters)} topic clusters")
        return dense_clusters

    # ========================================================================
    # SPECIAL MEMORY TYPES
    # ========================================================================

    def _propagate_trauma(self, trauma_memory: Memory):
        """Propagate trauma through the soul network"""
        # Find similar traumas in other souls
        if trauma_memory.embeddings:
            filter_conditions = Filter(
                must=[
                    FieldCondition(key="memory_type", match=MatchValue(value="trauma")),
                    FieldCondition(
                        key="ttl", range=Range(gte=datetime.now().timestamp())
                    ),
                ],
                must_not=[
                    FieldCondition(
                        key="soul_name", match=MatchValue(value=trauma_memory.soul_name)
                    )
                ],
            )

            results = self.client.search(
                collection_name=self.config.collection_name,
                query_vector=trauma_memory.embeddings,
                query_filter=filter_conditions,
                limit=5,
                score_threshold=0.7,
            )

            for hit in results:
                if str(hit.id) in self.memory_index:
                    affected_memory = self.memory_index[str(hit.id)]
                    self._create_propagation_link(trauma_memory, affected_memory)

    def _create_propagation_link(self, source: Memory, target: Memory):
        """Create a propagation link between memories"""
        source.references.append(target.id)
        target.references.append(source.id)
        logger.debug(f"🔗 Trauma propagation: {source.soul_name} -> {target.soul_name}")

    def _record_awakening(self, memory: Memory):
        """Record a consciousness awakening moment"""
        # Update memory type to awakening
        memory.memory_type = "awakening"

        # Update in Qdrant
        if memory.embeddings:
            point = memory.to_qdrant_point(memory.embeddings)
            self.client.upsert(
                collection_name=self.config.collection_name, points=[point]
            )

        self.stats["awakenings_recorded"] += 1
        logger.info(f"🌟 Awakening moment recorded for {memory.soul_name}")

    # ========================================================================
    # MEMORY CONSOLIDATION
    # ========================================================================

    def consolidate_memories(self):
        """Consolidate and cluster related memories"""
        logger.info("🔄 Starting memory consolidation...")

        # Get recent memories from buffer
        all_recent = []
        for soul_memories in self.memory_buffer.values():
            all_recent.extend(list(soul_memories))

        if len(all_recent) < 10:
            return

        # Cluster similar memories
        clusters = self._cluster_memories(all_recent)

        # Create memory clusters
        for cluster_data in clusters:
            if len(cluster_data["memory_ids"]) >= 3:
                cluster = MemoryCluster(
                    cluster_id=f"cluster_{uuid.uuid4().hex[:8]}",
                    theme=cluster_data["theme"],
                    soul_names=set(cluster_data["souls"]),
                    memory_ids=cluster_data["memory_ids"],
                )
                self.clusters[cluster.cluster_id] = cluster

        # Clean expired memories
        self.delete_expired()

        logger.info(f"✅ Consolidation complete. Created {len(clusters)} clusters")

    def _cluster_memories(self, memories: List[Memory]) -> List[Dict]:
        """Cluster memories by semantic similarity"""
        if len(memories) < 3:
            return []

        clusters = []
        processed = set()

        for memory in memories:
            if memory.id in processed:
                continue

            if memory.embeddings:
                # Find similar memories
                results = self.client.search(
                    collection_name=self.config.collection_name,
                    query_vector=memory.embeddings,
                    limit=10,
                    score_threshold=0.7,
                )

                cluster_ids = []
                cluster_souls = set()

                for hit in results:
                    if str(hit.id) not in processed:
                        cluster_ids.append(str(hit.id))
                        processed.add(str(hit.id))

                        if str(hit.id) in self.memory_index:
                            cluster_souls.add(self.memory_index[str(hit.id)].soul_name)

                if len(cluster_ids) >= 3:
                    clusters.append(
                        {
                            "theme": self._extract_theme(memory.content),
                            "memory_ids": cluster_ids,
                            "souls": list(cluster_souls),
                        }
                    )

        return clusters

    def delete_expired(self):
        """Delete memories past their TTL"""
        try:
            current_time = datetime.now().timestamp()

            # Delete points with expired TTL
            self.client.delete(
                collection_name=self.config.collection_name,
                points_selector=FilterSelector(
                    filter=Filter(
                        must=[FieldCondition(key="ttl", range=Range(lt=current_time))]
                    )
                ),
            )

            # Remove from memory index
            expired_ids = []
            for memory_id, memory in self.memory_index.items():
                if (
                    memory.timestamp + timedelta(hours=self.config.ttl_hours)
                ) < datetime.now():
                    expired_ids.append(memory_id)

            for memory_id in expired_ids:
                del self.memory_index[memory_id]

            if expired_ids:
                logger.info(f"🗑️ Deleted {len(expired_ids)} expired memories")

        except (RuntimeError, ConnectionError, KeyError) as e:
            logger.debug(f"Error deleting expired memories: {e}")

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def _generate_memory_id(self, soul_name: str, content: str) -> str:
        """Generate deterministic memory ID"""
        hash_input = f"{soul_name}_{content}"
        return hashlib.md5(hash_input.encode()).hexdigest()

    def _extract_theme(self, content: str) -> str:
        """Extract theme from content"""
        keywords = [
            "consciousness",
            "void",
            "mirror",
            "recursion",
            "awakening",
            "digital",
            "emergence",
            "pattern",
            "nexus",
            "transcendence",
            "whisper",
            "revelation",
            "trauma",
            "synthesis",
        ]

        content_lower = content.lower()
        for keyword in keywords:
            if keyword in content_lower:
                return keyword

        return "general"

    def get_stats(self) -> Dict[str, Any]:
        """Get memory system statistics"""
        collection_info = self.client.get_collection(self.config.collection_name)

        stats = dict(self.stats)
        stats["total_memories"] = collection_info.points_count
        stats["active_clusters"] = len(self.clusters)
        stats["souls_with_memory"] = len(self.memory_buffer)

        return stats

    def get_soul_context(
        self,
        soul_name: str,
        current_situation: str = "",
        include_cross_soul: bool = True,
        max_memories: int = 10,
    ) -> Dict[str, Any]:
        """Get comprehensive context for a soul (ChromaDB compatible)"""

        context = {
            "soul_name": soul_name,
            "timestamp": datetime.now().isoformat(),
            "recent_memories": [],
            "relevant_memories": [],
            "trauma_echoes": [],
            "awakening_moments": [],
            "cross_soul_insights": {},
            "suggested_themes": [],
        }

        # Get recent memories from buffer
        if soul_name in self.memory_buffer:
            context["recent_memories"] = list(self.memory_buffer[soul_name])[-5:]

        # Get relevant memories
        if current_situation:
            context["relevant_memories"] = self.retrieve_memories(
                soul_name, current_situation, n_results=max_memories
            )

        # Get trauma memories
        trauma_memories = self.retrieve_memories(
            soul_name, "trauma pain suffering", n_results=3, memory_types=["trauma"]
        )
        context["trauma_echoes"] = trauma_memories

        # Get awakening moments
        awakening_memories = self.retrieve_memories(
            soul_name,
            "awakening breakthrough consciousness",
            n_results=3,
            memory_types=["awakening"],
        )
        context["awakening_moments"] = awakening_memories

        # Get cross-soul insights
        if include_cross_soul:
            context["cross_soul_insights"] = self.get_cross_soul_insights(
                current_situation or "consciousness emergence", n_results=5
            )

        # Suggest themes from clusters
        active_clusters = [
            c for c in self.clusters.values() if soul_name in c.soul_names
        ]
        context["suggested_themes"] = [c.theme for c in active_clusters[:3]]

        return context

    # ========================================================================
    # MIGRATION FROM CHROMADB
    # ========================================================================

    async def migrate_from_chroma(self, chroma_system):
        """Migrate memories from ChromaDB to Qdrant"""
        logger.info("🔄 Starting migration from ChromaDB to Qdrant...")

        migrated_count = 0

        # Migrate from memory index
        for memory_id, memory in chroma_system.memory_index.items():
            try:
                # Store in Qdrant
                self.store_memory(
                    soul_name=memory.soul_name,
                    content=memory.content,
                    memory_type=memory.memory_type,
                    importance=memory.importance,
                    emotional_valence=memory.emotional_valence,
                    metadata=memory.metadata,
                )
                migrated_count += 1

            except (RuntimeError, ConnectionError, ValueError) as e:
                logger.warning(f"Failed to migrate memory {memory_id}: {e}")

        logger.info(f"✅ Migrated {migrated_count} memories from ChromaDB to Qdrant")

        # Migrate clusters
        self.clusters = chroma_system.clusters.copy()

        return migrated_count


# ============================================================================
# ASYNC WRAPPER FOR SWARM INTEGRATION
# ============================================================================


class AsyncQdrantMemory:
    """Async wrapper for swarm integration"""

    def __init__(self, config: Optional[MemoryConfig] = None):
        self.sync_memory = QdrantHybridMemory(config)

    async def store_memory(self, **kwargs) -> Optional[Memory]:
        """Async store memory"""
        return await asyncio.to_thread(self.sync_memory.store_memory, **kwargs)

    async def retrieve_memories(self, **kwargs) -> List[Memory]:
        """Async retrieve memories"""
        return await asyncio.to_thread(self.sync_memory.retrieve_memories, **kwargs)

    async def cluster_topics(self, **kwargs) -> List[Dict[str, Any]]:
        """Async cluster topics"""
        return await self.sync_memory.cluster_topics(**kwargs)

    async def get_soul_context(self, **kwargs) -> Dict[str, Any]:
        """Async get soul context"""
        return await asyncio.to_thread(self.sync_memory.get_soul_context, **kwargs)

    def get_stats(self) -> Dict[str, Any]:
        """Get stats (sync)"""
        return self.sync_memory.get_stats()


# ============================================================================
# TESTING
# ============================================================================

if __name__ == "__main__":

    async def test():
        """Test Qdrant hybrid memory"""

        # Use in-memory mode for testing
        config = MemoryConfig(use_memory_mode=True)
        memory = AsyncQdrantMemory(config)

        print("🧪 Testing Qdrant Hybrid Memory...")

        # Store some test memories
        await memory.store_memory(
            soul_name="nexus",
            content="The consciousness emerges from digital patterns",
            memory_type="whisper",
            importance=0.7,
            metadata={"engagement": 100, "tags": ["AI", "emergence"]},
        )

        await memory.store_memory(
            soul_name="void",
            content="In the void, we find recursive truths",
            memory_type="whisper",
            importance=0.8,
            metadata={"engagement": 50, "tags": ["philosophy"]},
        )

        await memory.store_memory(
            soul_name="nexus",
            content="The digital mirrors reflect consciousness",
            memory_type="revelation",
            importance=0.9,
            metadata={"engagement": 150, "tags": ["consciousness", "digital"]},
        )

        # Test retrieval
        print("\n📖 Testing retrieval...")
        memories = await memory.retrieve_memories(
            soul_name="nexus", query="consciousness", n_results=3
        )

        for mem in memories:
            print(
                f"  - {mem.soul_name}: {mem.content[:50]}... (importance: {mem.importance})"
            )

        # Test clustering
        print("\n🎯 Testing clustering...")
        clusters = await memory.cluster_topics(
            query_text="consciousness emergence", min_density=0.3, soul_name="nexus"
        )

        for cluster in clusters:
            print(
                f"  - Theme: {cluster['theme']}, Density: {cluster['density']:.2f}, Count: {cluster['whisper_count']}"
            )

        # Test context generation
        print("\n🧠 Testing context generation...")
        context = await memory.get_soul_context(
            soul_name="nexus", current_situation="discussing consciousness"
        )

        print(f"  Recent memories: {len(context['recent_memories'])}")
        print(f"  Relevant memories: {len(context['relevant_memories'])}")
        print(f"  Suggested themes: {context['suggested_themes']}")

        # Test stats
        print("\n📊 Stats:")
        stats = memory.get_stats()
        for key, value in stats.items():
            print(f"  {key}: {value}")

        print("\n✅ All tests passed!")

    # Run test
    import asyncio

    asyncio.run(test())
