"""
Scheduler Daemon -- background process that manages onboarding lifecycle.

Responsibilities:
  - Advance account phases hourly
  - Reset daily action counters at midnight UTC
  - Publish events to Redis pub/sub for downstream consumers
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone

import redis.asyncio as aioredis

from .onboarding_scheduler import OnboardingScheduler

logger = logging.getLogger("onboarding.daemon")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "ShaxAGI2025")

# Pub/sub channels
CHAN_PHASE_CHANGED = "onboarding:phase_changed"
CHAN_GRADUATED = "onboarding:graduated"
CHAN_DAILY_RESET = "onboarding:daily_reset"


class SchedulerDaemon:
    """Background daemon that drives the onboarding lifecycle."""

    def __init__(
        self,
        scheduler: OnboardingScheduler,
        phase_check_interval: int = 3600,   # 1 hour
    ):
        self.scheduler = scheduler
        self.phase_check_interval = phase_check_interval
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def run(self) -> None:
        """Start both loops. Blocks until stopped."""
        self._running = True
        logger.info(
            "Scheduler daemon starting (phase check every %ds)",
            self.phase_check_interval,
        )

        self._tasks = [
            asyncio.create_task(self._phase_loop(), name="phase_loop"),
            asyncio.create_task(self._daily_reset_loop(), name="daily_reset_loop"),
        ]

        try:
            await asyncio.gather(*self._tasks)
        except asyncio.CancelledError:
            logger.info("Scheduler daemon tasks cancelled")

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        for t in self._tasks:
            t.cancel()
        logger.info("Scheduler daemon stopped")

    # -- loops -----------------------------------------------------------

    async def _phase_loop(self) -> None:
        """Advance phases every `phase_check_interval` seconds."""
        while self._running:
            try:
                transitions = await self.scheduler.advance_phases()
                for t in transitions:
                    await self._publish(CHAN_PHASE_CHANGED, t)
                    if t["new_phase"] == "graduated":
                        await self._publish(CHAN_GRADUATED, {
                            "account_id": t["account_id"],
                            "timestamp": t["timestamp"],
                        })
                if transitions:
                    logger.info("Phase check: %d transitions", len(transitions))
            except Exception:
                logger.exception("Error in phase advancement loop")

            await asyncio.sleep(self.phase_check_interval)

    async def _daily_reset_loop(self) -> None:
        """Reset daily counters at midnight UTC."""
        while self._running:
            now = datetime.now(timezone.utc)
            # Seconds until next midnight UTC
            tomorrow = now.replace(
                hour=0, minute=0, second=0, microsecond=0
            )
            if tomorrow <= now:
                tomorrow = tomorrow.replace(day=now.day + 1)
            wait_seconds = (tomorrow - now).total_seconds()

            logger.info("Daily reset in %.0f seconds", wait_seconds)
            await asyncio.sleep(wait_seconds)

            try:
                count = await self.scheduler.reset_daily_counters()
                await self._publish(CHAN_DAILY_RESET, {
                    "accounts_reset": count,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                })
                logger.info("Daily reset complete: %d accounts", count)
            except Exception:
                logger.exception("Error in daily reset loop")

    # -- pub/sub ---------------------------------------------------------

    async def _publish(self, channel: str, data: dict) -> None:
        """Publish an event to Redis pub/sub."""
        try:
            await self.scheduler.redis.publish(channel, json.dumps(data))
        except Exception:
            logger.exception("Failed to publish to %s", channel)


# ---------------------------------------------------------------------------
# Standalone entry point
# ---------------------------------------------------------------------------

async def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s %(message)s",
    )

    redis_client = aioredis.from_url(
        REDIS_URL, password=REDIS_PASSWORD, decode_responses=True,
    )
    await redis_client.ping()
    logger.info("Connected to Redis")

    scheduler = OnboardingScheduler(redis_client)
    daemon = SchedulerDaemon(scheduler)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())
