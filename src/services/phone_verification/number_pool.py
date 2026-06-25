"""Number Pool Manager — tracks phone number reuse and cooling periods.

Uses Redis to persist usage history across sessions. Prevents over-using
numbers on specific services and enforces cooling periods between uses.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

# Redis key prefixes
PREFIX = "phonepool"
USAGE_KEY = f"{PREFIX}:usage"         # Hash: number:service → JSON usage data
COOLDOWN_KEY = f"{PREFIX}:cooldown"   # Hash: number → last_used timestamp
NUMBERS_KEY = f"{PREFIX}:numbers"     # Set: all known numbers


class NumberPoolManager:
    """Tracks phone number usage history and cooling periods via Redis."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    @classmethod
    async def create(
        cls,
        redis_url: str = "redis://localhost:6379",
        redis_password: str = "ShaxAGI2025",
    ) -> "NumberPoolManager":
        """Factory method to create with a new Redis connection."""
        client = redis.from_url(
            redis_url,
            password=redis_password,
            decode_responses=True,
        )
        return cls(client)

    def _usage_key(self, number: str, service: str) -> str:
        return f"{USAGE_KEY}:{number}:{service}"

    async def record_usage(self, number: str, service: str, success: bool):
        """
        Record that a number was used for a service.

        Args:
            number: Phone number (full format)
            service: Service name (e.g., "twitter")
            success: Whether verification succeeded
        """
        key = self._usage_key(number, service)
        now = datetime.now(timezone.utc).isoformat()

        # Get existing usage data
        existing = await self.redis.get(key)
        if existing:
            data = json.loads(existing)
        else:
            data = {"count": 0, "successes": 0, "failures": 0, "history": []}

        data["count"] += 1
        if success:
            data["successes"] += 1
        else:
            data["failures"] += 1
        data["history"].append({"timestamp": now, "success": success})
        data["last_used"] = now

        # Keep only last 50 history entries
        if len(data["history"]) > 50:
            data["history"] = data["history"][-50:]

        await self.redis.set(key, json.dumps(data))

        # Update cooldown timestamp
        await self.redis.hset(COOLDOWN_KEY, number, now)

        # Track number in the known set
        await self.redis.sadd(NUMBERS_KEY, number)

        logger.debug(f"Recorded usage: ***{number[-4:]} on {service} (success={success}, total={data['count']})")

    async def get_usage_count(self, number: str, service: str) -> int:
        """How many times has this number been used for this service?"""
        key = self._usage_key(number, service)
        data = await self.redis.get(key)
        if not data:
            return 0
        return json.loads(data).get("count", 0)

    async def get_usage_stats(self, number: str, service: str) -> Optional[dict]:
        """Get full usage stats for a number+service combo."""
        key = self._usage_key(number, service)
        data = await self.redis.get(key)
        if not data:
            return None
        return json.loads(data)

    async def is_cooled_down(self, number: str, min_hours: float = 4.0) -> bool:
        """Has enough time passed since this number was last used anywhere?"""
        last_used = await self.redis.hget(COOLDOWN_KEY, number)
        if not last_used:
            return True  # Never used = cooled down

        last_dt = datetime.fromisoformat(last_used)
        elapsed = datetime.now(timezone.utc) - last_dt
        return elapsed >= timedelta(hours=min_hours)

    async def get_cooldown_remaining(self, number: str, min_hours: float = 4.0) -> timedelta:
        """How much cooldown time remains for this number?"""
        last_used = await self.redis.hget(COOLDOWN_KEY, number)
        if not last_used:
            return timedelta(0)

        last_dt = datetime.fromisoformat(last_used)
        elapsed = datetime.now(timezone.utc) - last_dt
        required = timedelta(hours=min_hours)
        remaining = required - elapsed
        return max(remaining, timedelta(0))

    async def get_available_numbers(self, service: str, max_uses: int = 8, min_cooldown_hours: float = 4.0) -> list[str]:
        """
        Get numbers that can still be reused for a service.

        Returns numbers that:
        1. Have been used fewer than max_uses times for this service
        2. Have cooled down (min_cooldown_hours since last use)
        """
        all_numbers = await self.redis.smembers(NUMBERS_KEY)
        available = []

        for number in all_numbers:
            # Check usage count
            usage_count = await self.get_usage_count(number, service)
            if usage_count >= max_uses:
                continue

            # Check cooldown
            if not await self.is_cooled_down(number, min_cooldown_hours):
                continue

            available.append(number)

        return available

    async def get_all_numbers(self) -> set[str]:
        """Get all known numbers in the pool."""
        return await self.redis.smembers(NUMBERS_KEY)

    async def get_number_summary(self, number: str) -> dict:
        """Get a summary of all usage for a number across services."""
        pattern = f"{USAGE_KEY}:{number}:*"
        summary = {"number": number, "services": {}}

        async for key in self.redis.scan_iter(match=pattern):
            service = key.rsplit(":", 1)[-1]
            data = await self.redis.get(key)
            if data:
                parsed = json.loads(data)
                summary["services"][service] = {
                    "count": parsed["count"],
                    "successes": parsed["successes"],
                    "failures": parsed["failures"],
                    "last_used": parsed.get("last_used"),
                }

        # Add cooldown info
        cooldown_remaining = await self.get_cooldown_remaining(number)
        summary["cooldown_remaining_seconds"] = cooldown_remaining.total_seconds()
        summary["is_cooled_down"] = cooldown_remaining.total_seconds() == 0

        return summary

    async def remove_number(self, number: str):
        """Remove a number from the pool (does not delete usage history)."""
        await self.redis.srem(NUMBERS_KEY, number)
        await self.redis.hdel(COOLDOWN_KEY, number)
        logger.info(f"Removed ***{number[-4:]} from pool")

    async def close(self):
        """Close Redis connection."""
        await self.redis.aclose()
