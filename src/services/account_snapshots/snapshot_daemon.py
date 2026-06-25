"""
Snapshot Daemon

Runs a continuous collection loop every 15 minutes (configurable).
Triggers behavioral snapshots, ban detection, survivor tracking,
and publishes a Redis pub/sub event after each cycle.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Dict, List, Optional, Set

import redis.asyncio as aioredis

from src.services.health_monitor.health_monitor import AccountHealthMonitor
from src.services.onboarding.onboarding_scheduler import OnboardingScheduler
from src.ryan_api_ultimate import RyanTwitterAPISecure as RyanTwitterAPI

from .snapshot_collector import SnapshotCollector

logger = logging.getLogger("account_snapshots.daemon")

# Survivor threshold: 7 days in seconds
_SURVIVOR_THRESHOLD_SECONDS = 7 * 24 * 3600

_SURVIVORS_KEY = "snapshot:survivors"
_SNAPSHOT_UPDATED_CHANNEL = "snapshot:updated"
_IDENTITY_PREFIX = "snapshot:identity:"


class SnapshotDaemon:
    """
    Long-running daemon that periodically collects snapshots for all
    registered swarm accounts and detects ban events.

    Usage:
        daemon = SnapshotDaemon(redis_client, ryan_api, health_monitor, scheduler)
        await daemon.run()          # blocks; Ctrl-C or asyncio cancellation stops it
        await daemon.run_once()     # single cycle for testing
    """

    def __init__(
        self,
        redis_client: aioredis.Redis,
        ryan_api: RyanTwitterAPI,
        health_monitor: AccountHealthMonitor,
        onboarding_scheduler: OnboardingScheduler,
        swarm_account_ids: Optional[Set[str]] = None,
    ) -> None:
        self.redis = redis_client
        self.ryan = ryan_api
        self.health = health_monitor
        self.onboarding = onboarding_scheduler
        self.swarm_ids: Set[str] = swarm_account_ids or set()

        self._stop_event = asyncio.Event()
        self._collector: Optional[SnapshotCollector] = None

    # ------------------------------------------------------------------
    # Lifecycle
    # ------------------------------------------------------------------

    def _get_collector(self) -> SnapshotCollector:
        """Lazily construct or return the SnapshotCollector."""
        if self._collector is None:
            self._collector = SnapshotCollector(
                redis_client=self.redis,
                ryan_api=self.ryan,
                health_monitor=self.health,
                onboarding_scheduler=self.onboarding,
                swarm_account_ids=self.swarm_ids,
            )
        return self._collector

    def stop(self) -> None:
        """Signal the daemon to stop after the current cycle completes."""
        self._stop_event.set()
        logger.info("Snapshot daemon stop signal received")

    # ------------------------------------------------------------------
    # Main loop
    # ------------------------------------------------------------------

    async def run(self, interval_seconds: int = 900) -> None:
        """
        Main collection loop. Runs every interval_seconds (default: 15 min).

        Shuts down gracefully when stop() is called or an asyncio.CancelledError
        is raised (e.g. via KeyboardInterrupt in asyncio.run()).
        """
        logger.info(
            "Snapshot daemon started (interval=%ds / %.1fmin)",
            interval_seconds,
            interval_seconds / 60,
        )

        try:
            while not self._stop_event.is_set():
                cycle_start = time.monotonic()

                try:
                    await self.run_once()
                except Exception as exc:
                    logger.exception("Unhandled error in snapshot cycle: %s", exc)

                # Wait for the next cycle, but check the stop event frequently
                elapsed = time.monotonic() - cycle_start
                remaining = max(0.0, interval_seconds - elapsed)
                logger.debug(
                    "Cycle complete in %.1fs; sleeping %.1fs until next cycle",
                    elapsed,
                    remaining,
                )

                try:
                    await asyncio.wait_for(
                        self._stop_event.wait(), timeout=remaining
                    )
                except asyncio.TimeoutError:
                    pass  # Normal — stop event was not set; continue to next cycle

        except asyncio.CancelledError:
            logger.info("Snapshot daemon cancelled")
        finally:
            logger.info("Snapshot daemon stopped")

    # ------------------------------------------------------------------
    # Single collection cycle (also used by tests)
    # ------------------------------------------------------------------

    async def run_once(self) -> Dict[str, Any]:
        """
        Execute one complete collection cycle:

        1. Discover all registered account IDs from the onboarding scheduler.
        2. Collect behavioral snapshots for all accounts.
        3. Run ban detection for each account.
        4. Update the survivors set (accounts alive > 7 days).
        5. Publish a "snapshot:updated" event via Redis pub/sub.
        6. Log summary statistics.

        Returns a stats dict useful for testing and introspection.
        """
        cycle_ts = time.time()
        logger.info("Snapshot cycle starting at %.0f", cycle_ts)

        # Step 1: Discover all registered accounts
        account_ids = await self._discover_account_ids()
        if not account_ids:
            logger.info("No accounts registered with onboarding scheduler; nothing to do")
            stats = {
                "cycle_timestamp": cycle_ts,
                "total_accounts": 0,
                "collected": 0,
                "failed": 0,
                "bans_detected": 0,
                "survivors": 0,
            }
            await self._publish_update(stats)
            return stats

        logger.info("Discovered %d accounts for snapshot collection", len(account_ids))

        # Refresh swarm_ids from the discovered accounts so the collector
        # always has the current full membership list.
        self.swarm_ids = set(account_ids)
        if self._collector is not None:
            self._collector.swarm_ids = self.swarm_ids

        collector = self._get_collector()

        # Step 2: Collect behavioral snapshots
        collection_results = await collector.collect_all(account_ids)
        n_collected = len(collection_results.get("success", []))
        n_failed = len(collection_results.get("failed", []))

        # Step 3: Ban detection
        n_bans = 0
        for account_id in account_ids:
            try:
                ban_event = await collector.detect_ban(account_id)
                if ban_event is not None:
                    n_bans += 1
                    logger.warning(
                        "Ban event detected: account=%s type=%s trigger=%s",
                        account_id,
                        ban_event.ban_type,
                        ban_event.suspected_trigger,
                    )
            except Exception as exc:
                logger.error("detect_ban failed for %s: %s", account_id, exc)

        # Step 4: Update survivors set
        n_survivors = await self._update_survivors(account_ids, cycle_ts)

        # Step 5: Publish update event
        stats = {
            "cycle_timestamp": cycle_ts,
            "total_accounts": len(account_ids),
            "collected": n_collected,
            "failed": n_failed,
            "bans_detected": n_bans,
            "survivors": n_survivors,
        }
        await self._publish_update(stats)

        # Step 6: Log summary
        logger.info(
            "Snapshot cycle complete: accounts=%d collected=%d failed=%d "
            "bans=%d survivors=%d",
            len(account_ids),
            n_collected,
            n_failed,
            n_bans,
            n_survivors,
        )
        return stats

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _discover_account_ids(self) -> List[str]:
        """
        Get all account IDs currently registered with the onboarding scheduler.
        Falls back to an empty list if the call fails.
        """
        try:
            schedules = await self.onboarding.get_all_accounts()
            return [s.account_id for s in schedules]
        except Exception as exc:
            logger.error("Failed to discover account IDs: %s", exc)
            return []

    async def _update_survivors(
        self, account_ids: List[str], now_ts: float
    ) -> int:
        """
        Add accounts that are alive and older than 7 days to the survivors set.
        Accounts that have been banned are not re-added (ban record exists).

        Returns the total number of survivors in the set after updating.
        """
        pipe = self.redis.pipeline()
        added = 0

        for account_id in account_ids:
            # Remove banned accounts from survivors
            ban_key = f"snapshot:ban:{account_id}"
            if await self.redis.exists(ban_key):
                await self.redis.srem(_SURVIVORS_KEY, account_id)
                continue

            # Check account age from identity snapshot
            identity_raw = await self.redis.get(f"{_IDENTITY_PREFIX}{account_id}")
            if not identity_raw:
                continue

            try:
                identity_data = json.loads(identity_raw)
                creation_ts = float(identity_data.get("creation_timestamp", now_ts))
                age_seconds = now_ts - creation_ts
                if age_seconds >= _SURVIVOR_THRESHOLD_SECONDS:
                    pipe.sadd(_SURVIVORS_KEY, account_id)
                    added += 1
            except (json.JSONDecodeError, ValueError):
                continue

        if added:
            await pipe.execute()

        n_survivors = await self.redis.scard(_SURVIVORS_KEY)
        logger.debug("Survivors set: %d total (%d newly added this cycle)", n_survivors, added)
        return int(n_survivors)

    async def _publish_update(self, stats: Dict[str, Any]) -> None:
        """Publish snapshot cycle completion event via Redis pub/sub."""
        try:
            await self.redis.publish(
                _SNAPSHOT_UPDATED_CHANNEL,
                json.dumps(stats),
            )
            logger.debug("Published snapshot:updated event")
        except Exception as exc:
            logger.warning("Failed to publish snapshot:updated: %s", exc)
