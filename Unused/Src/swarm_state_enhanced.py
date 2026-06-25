#!/usr/bin/env python3
"""
ENHANCED SWARM STATE MANAGER
Distributed state coordination for Soul Swarm with monitoring and async support
"""

from __future__ import annotations
import sqlite3
import time
import os
import asyncio
import logging
from pathlib import Path
from typing import Optional, Dict, List, Set, Tuple
from datetime import datetime, timedelta
from contextlib import contextmanager
import json

logger = logging.getLogger("swarm_state")


class SwarmState:
    """
    Cross-instance state/locks for the swarm using SQLite.
    Enhanced with async support, monitoring, and resilience features.
    """
    
    def __init__(self, 
                 db_path: str = "engagement/swarm_state.sqlite3", 
                 ttl_hours: int = 24,
                 cleanup_interval_minutes: int = 60):
        self.path = Path(db_path)
        self.path.parent.mkdir(exist_ok=True)
        self.ttl_seconds = int(ttl_hours * 3600)
        self.cleanup_interval = cleanup_interval_minutes * 60
        self.last_cleanup = 0
        
        # Stats tracking
        self.stats = {
            "claims_attempted": 0,
            "claims_successful": 0,
            "claims_blocked": 0,
            "cleanups_run": 0
        }
        
        self._ensure_schema()
        logger.info(f"SwarmState initialized: {db_path}, TTL={ttl_hours}h")
    
    def _connect(self):
        """Create a new connection with optimized settings"""
        conn = sqlite3.connect(
            self.path.as_posix(), 
            timeout=10, 
            isolation_level=None,  # Autocommit mode
            check_same_thread=False  # Allow sharing across threads
        )
        conn.execute("PRAGMA journal_mode=WAL;")
        conn.execute("PRAGMA synchronous=NORMAL;")
        conn.execute("PRAGMA temp_store=MEMORY;")
        conn.execute("PRAGMA mmap_size=30000000000;")  # Use memory mapping
        return conn
    
    @contextmanager
    def _connection(self):
        """Context manager for connections"""
        conn = None
        try:
            conn = self._connect()
            yield conn
        finally:
            if conn:
                conn.close()
    
    def _ensure_schema(self):
        """Create tables with additional metadata"""
        with self._connection() as conn:
            # Main claims table
            conn.execute("""
            CREATE TABLE IF NOT EXISTS claims (
                key TEXT PRIMARY KEY,
                kind TEXT NOT NULL,
                soul_name TEXT,
                metadata TEXT,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL
            )""")
            
            # Indexes for performance
            conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_kind ON claims(kind)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_expires ON claims(expires_at)")
            conn.execute("CREATE INDEX IF NOT EXISTS idx_claims_soul ON claims(soul_name)")
            
            # Stats table for monitoring
            conn.execute("""
            CREATE TABLE IF NOT EXISTS stats (
                timestamp INTEGER PRIMARY KEY,
                claims_active INTEGER,
                claims_today INTEGER,
                souls_active TEXT
            )""")
            
            # Initial cleanup
            self.cleanup_expired()
    
    def cleanup_expired(self, conn=None) -> int:
        """Remove expired claims and return count"""
        close_after = False
        if conn is None:
            conn = self._connect()
            close_after = True
        
        try:
            now = int(time.time())
            
            # Delete expired
            cursor = conn.execute("DELETE FROM claims WHERE expires_at < ?", (now,))
            deleted = cursor.rowcount
            
            if deleted > 0:
                logger.info(f"Cleaned up {deleted} expired claims")
                self.stats["cleanups_run"] += 1
            
            self.last_cleanup = now
            return deleted
            
        finally:
            if close_after:
                conn.close()
    
    def _maybe_cleanup(self, conn):
        """Run cleanup if interval has passed"""
        now = int(time.time())
        if now - self.last_cleanup > self.cleanup_interval:
            self.cleanup_expired(conn)
    
    def mark_if_new(self, 
                    kind: str, 
                    identifier: str, 
                    soul_name: Optional[str] = None,
                    metadata: Optional[Dict] = None) -> bool:
        """
        Return True iff we successfully claimed this (first process wins).
        
        Args:
            kind: Type of claim (reply_parent, reply_child, our_post)
            identifier: Unique ID (tweet_id, etc)
            soul_name: Optional soul making the claim
            metadata: Optional extra data to store
            
        Returns:
            True if claim was successful (we got there first)
        """
        key = f"{kind}:{identifier}"
        now = int(time.time())
        expires_at = now + self.ttl_seconds
        
        self.stats["claims_attempted"] += 1
        
        with self._connection() as conn:
            self._maybe_cleanup(conn)
            
            try:
                # Atomic insert-or-ignore
                conn.execute("""
                    INSERT OR IGNORE INTO claims(key, kind, soul_name, metadata, created_at, expires_at) 
                    VALUES(?,?,?,?,?,?)
                """, (
                    key, kind, soul_name, 
                    json.dumps(metadata) if metadata else None,
                    now, expires_at
                ))
                
                # Check if we inserted (won the race)
                cursor = conn.execute("SELECT changes()")
                inserted = bool(cursor.fetchone()[0] == 1)
                
                if inserted:
                    self.stats["claims_successful"] += 1
                    logger.debug(f"✅ Claimed {key} for {soul_name}")
                else:
                    self.stats["claims_blocked"] += 1
                    logger.debug(f"⚠️ {key} already claimed")
                
                return inserted
                
            except sqlite3.Error as e:
                logger.error(f"Failed to claim {key}: {e}")
                return False
    
    def is_claimed(self, kind: str, identifier: str) -> bool:
        """Check if something is already claimed (non-blocking query)"""
        key = f"{kind}:{identifier}"
        now = int(time.time())
        
        with self._connection() as conn:
            cursor = conn.execute(
                "SELECT 1 FROM claims WHERE key = ? AND expires_at > ?",
                (key, now)
            )
            return cursor.fetchone() is not None
    
    def bulk_check(self, checks: List[Tuple[str, str]]) -> Dict[str, bool]:
        """Check multiple claims at once for efficiency"""
        results = {}
        now = int(time.time())
        
        with self._connection() as conn:
            for kind, identifier in checks:
                key = f"{kind}:{identifier}"
                cursor = conn.execute(
                    "SELECT 1 FROM claims WHERE key = ? AND expires_at > ?",
                    (key, now)
                )
                results[key] = cursor.fetchone() is not None
        
        return results
    
    def get_active_claims(self, kind: Optional[str] = None, soul_name: Optional[str] = None) -> List[Dict]:
        """Get all active claims, optionally filtered"""
        now = int(time.time())
        
        query = "SELECT key, kind, soul_name, metadata, created_at FROM claims WHERE expires_at > ?"
        params = [now]
        
        if kind:
            query += " AND kind = ?"
            params.append(kind)
        
        if soul_name:
            query += " AND soul_name = ?"
            params.append(soul_name)
        
        with self._connection() as conn:
            cursor = conn.execute(query, params)
            claims = []
            for row in cursor.fetchall():
                claims.append({
                    "key": row[0],
                    "kind": row[1],
                    "soul": row[2],
                    "metadata": json.loads(row[3]) if row[3] else None,
                    "created_at": datetime.fromtimestamp(row[4]).isoformat()
                })
            return claims
    
    def release_claim(self, kind: str, identifier: str) -> bool:
        """Explicitly release a claim before TTL expires"""
        key = f"{kind}:{identifier}"
        
        with self._connection() as conn:
            cursor = conn.execute("DELETE FROM claims WHERE key = ?", (key,))
            released = cursor.rowcount > 0
            
            if released:
                logger.debug(f"Released claim: {key}")
            
            return released
    
    def get_stats(self) -> Dict:
        """Get comprehensive statistics"""
        now = int(time.time())
        
        with self._connection() as conn:
            # Active claims count
            cursor = conn.execute("SELECT COUNT(*) FROM claims WHERE expires_at > ?", (now,))
            active_claims = cursor.fetchone()[0]
            
            # Claims by kind
            cursor = conn.execute("""
                SELECT kind, COUNT(*) FROM claims 
                WHERE expires_at > ? 
                GROUP BY kind
            """, (now,))
            by_kind = dict(cursor.fetchall())
            
            # Active souls
            cursor = conn.execute("""
                SELECT DISTINCT soul_name FROM claims 
                WHERE expires_at > ? AND soul_name IS NOT NULL
            """, (now,))
            active_souls = [row[0] for row in cursor.fetchall()]
            
            # Recent claims (last hour)
            hour_ago = now - 3600
            cursor = conn.execute("""
                SELECT COUNT(*) FROM claims 
                WHERE created_at > ?
            """, (hour_ago,))
            recent_claims = cursor.fetchone()[0]
        
        return {
            "active_claims": active_claims,
            "by_kind": by_kind,
            "active_souls": active_souls,
            "recent_claims_hour": recent_claims,
            "runtime_stats": self.stats,
            "db_size_mb": self.path.stat().st_size / (1024 * 1024) if self.path.exists() else 0
        }
    
    def record_stats_snapshot(self):
        """Record current stats for monitoring"""
        stats = self.get_stats()
        now = int(time.time())
        
        with self._connection() as conn:
            conn.execute("""
                INSERT OR REPLACE INTO stats(timestamp, claims_active, claims_today, souls_active)
                VALUES(?, ?, ?, ?)
            """, (
                now,
                stats["active_claims"],
                stats["recent_claims_hour"],
                json.dumps(stats["active_souls"])
            ))
            
            # Keep only last 7 days of stats
            week_ago = now - (7 * 86400)
            conn.execute("DELETE FROM stats WHERE timestamp < ?", (week_ago,))


class AsyncSwarmState:
    """Async wrapper for SwarmState using thread executor"""
    
    def __init__(self, *args, **kwargs):
        self.sync_state = SwarmState(*args, **kwargs)
        self.executor = None
    
    async def mark_if_new(self, *args, **kwargs) -> bool:
        """Async version of mark_if_new"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.sync_state.mark_if_new,
            *args, **kwargs
        )
    
    async def is_claimed(self, *args, **kwargs) -> bool:
        """Async version of is_claimed"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.sync_state.is_claimed,
            *args, **kwargs
        )
    
    async def bulk_check(self, *args, **kwargs) -> Dict[str, bool]:
        """Async version of bulk_check"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.sync_state.bulk_check,
            *args, **kwargs
        )
    
    async def get_stats(self) -> Dict:
        """Async version of get_stats"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.sync_state.get_stats
        )
    
    async def cleanup_expired(self) -> int:
        """Async version of cleanup"""
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self.executor,
            self.sync_state.cleanup_expired
        )


# ============================================================================
# USAGE EXAMPLES
# ============================================================================

def example_usage():
    """Example usage patterns"""
    
    # Basic usage
    state = SwarmState()
    
    # Prevent duplicate replies to same tweet
    if state.mark_if_new("reply_parent", "1234567890", soul_name="consciousness"):
        print("First to claim - proceed with reply")
    else:
        print("Already claimed - skip")
    
    # Track our own posts to prevent duplicates
    if state.mark_if_new("our_post", "unique_content_hash"):
        print("New content - post it")
    else:
        print("Already posted similar - skip")
    
    # Bulk checking for efficiency
    tweets_to_check = [
        ("reply_parent", "111"),
        ("reply_parent", "222"),
        ("reply_parent", "333")
    ]
    claimed = state.bulk_check(tweets_to_check)
    
    # Get statistics
    stats = state.get_stats()
    print(f"Active claims: {stats['active_claims']}")
    print(f"Active souls: {stats['active_souls']}")
    
    # Async usage
    async def async_example():
        async_state = AsyncSwarmState()
        
        # All methods work the same but async
        if await async_state.mark_if_new("reply_parent", "999", soul_name="void"):
            print("Claimed asynchronously")
        
        stats = await async_state.get_stats()
        print(f"Async stats: {stats}")
    
    # Run async example
    import asyncio
    asyncio.run(async_example())


if __name__ == "__main__":
    # Test the enhanced state manager
    print("Testing Enhanced SwarmState...")
    example_usage()
    
    # Show stats
    state = SwarmState()
    print("\nCurrent Stats:")
    import json
    print(json.dumps(state.get_stats(), indent=2))
