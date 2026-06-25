"""
Alert Manager for account health events.

Subscribes to Redis pub/sub health channels and provides query methods
for recent alerts, ban rates, and replacement needs.
"""

from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Callable, Coroutine, Dict, List, Optional

import redis.asyncio as aioredis

from .health_monitor import AccountStatus

logger = logging.getLogger("health_monitor.alerts")

# Redis keys
_PREFIX = "health:alerts"
ALERTS_SORTED_SET = f"{_PREFIX}:recent"
BAN_HISTORY_KEY = f"{_PREFIX}:bans"

# Pub/sub channels
CHAN_STATUS_CHANGED = "health:status_changed"
CHAN_SUSPENDED = "health:suspended"
CHAN_SHADOWBANNED = "health:shadowbanned"


class AlertManager:
    """Manages health alerts and provides query access to alert history."""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client
        self._subscriber: Optional[aioredis.client.PubSub] = None
        self._listen_task: Optional[asyncio.Task] = None

    # -- alert recording -------------------------------------------------

    async def record_alert(self, alert: dict) -> None:
        """Store an alert in the sorted set (scored by timestamp)."""
        now = time.time()
        alert.setdefault("timestamp", datetime.now(timezone.utc).isoformat())

        pipe = self.redis.pipeline()
        pipe.zadd(ALERTS_SORTED_SET, {json.dumps(alert): now})
        # Trim to last 30 days
        cutoff = now - (30 * 86400)
        pipe.zremrangebyscore(ALERTS_SORTED_SET, "-inf", cutoff)

        # Track bans separately for ban-rate calculation
        status = alert.get("new_status", "")
        if status in ("suspended", "locked"):
            pipe.zadd(BAN_HISTORY_KEY, {json.dumps(alert): now})
            pipe.zremrangebyscore(BAN_HISTORY_KEY, "-inf", cutoff)

        await pipe.execute()

    async def record_status_change(
        self,
        account_id: str,
        old_status: str,
        new_status: str,
    ) -> dict:
        """Record a status change and publish to appropriate channels."""
        alert = {
            "account_id": account_id,
            "old_status": old_status,
            "new_status": new_status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        await self.record_alert(alert)

        # Publish to channels
        await self.redis.publish(CHAN_STATUS_CHANGED, json.dumps(alert))

        if new_status == AccountStatus.SUSPENDED.value:
            await self.redis.publish(CHAN_SUSPENDED, json.dumps(alert))
            logger.warning("CRITICAL: Account %s SUSPENDED", account_id)

        if new_status == AccountStatus.SHADOWBANNED.value:
            await self.redis.publish(CHAN_SHADOWBANNED, json.dumps(alert))
            logger.warning("WARNING: Account %s shadowbanned", account_id)

        return alert

    # -- subscriptions ---------------------------------------------------

    async def subscribe_status_changes(
        self,
        callback: Callable[[dict], Coroutine],
    ) -> None:
        """Subscribe to account status change events. Runs until cancelled."""
        self._subscriber = self.redis.pubsub()
        await self._subscriber.subscribe(
            CHAN_STATUS_CHANGED,
            CHAN_SUSPENDED,
            CHAN_SHADOWBANNED,
        )

        logger.info("Subscribed to health alert channels")

        async for message in self._subscriber.listen():
            if message["type"] != "message":
                continue
            try:
                data = json.loads(message["data"])
                data["channel"] = message["channel"]
                await callback(data)
            except Exception:
                logger.exception("Error in alert callback")

    async def stop_listening(self) -> None:
        """Unsubscribe and clean up."""
        if self._subscriber:
            await self._subscriber.unsubscribe()
            await self._subscriber.close()
            self._subscriber = None

    # -- queries ---------------------------------------------------------

    async def get_recent_alerts(self, hours: int = 24) -> List[dict]:
        """Get alerts from the last N hours."""
        cutoff = time.time() - (hours * 3600)
        raw = await self.redis.zrangebyscore(ALERTS_SORTED_SET, cutoff, "+inf")
        return [json.loads(entry) for entry in raw]

    async def get_ban_rate(self, days: int = 7) -> float:
        """Percentage of accounts banned in last N days.

        Returns a float 0.0-100.0 representing the ban rate.
        """
        cutoff = time.time() - (days * 86400)
        ban_count = await self.redis.zcount(BAN_HISTORY_KEY, cutoff, "+inf")

        # Get total registered accounts from health monitor
        total = await self.redis.hlen("health:accounts")
        if total == 0:
            return 0.0

        # Unique banned account IDs
        raw_bans = await self.redis.zrangebyscore(BAN_HISTORY_KEY, cutoff, "+inf")
        banned_ids = set()
        for entry in raw_bans:
            data = json.loads(entry)
            banned_ids.add(data.get("account_id", ""))

        return (len(banned_ids) / total) * 100.0

    async def get_replacement_needed(self) -> List[str]:
        """List account_ids that need replacement (suspended/locked)."""
        # Check current status of all registered accounts
        accounts = await self.redis.hkeys("health:accounts")
        needs_replacement = []

        for account_id in accounts:
            raw = await self.redis.get(f"health:status:{account_id}")
            if raw is None:
                continue
            data = json.loads(raw)
            status = data.get("status", "")
            if status in (AccountStatus.SUSPENDED.value, AccountStatus.LOCKED.value):
                needs_replacement.append(account_id)

        return needs_replacement
