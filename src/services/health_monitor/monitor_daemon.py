"""
Health Monitor Daemon -- background process that periodically checks all accounts.

Detects status changes and publishes alerts via Redis pub/sub.
Logs all checks to logs/health_monitor.log.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import signal
from datetime import datetime, timezone
from pathlib import Path

import redis.asyncio as aioredis

from .health_monitor import AccountHealthMonitor, AccountStatus
from .alerts import AlertManager

logger = logging.getLogger("health_monitor.daemon")

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "ShaxAGI2025")

# Log directory
LOG_DIR = Path(__file__).parent.parent.parent.parent / "logs"


def _setup_file_logging() -> None:
    """Set up file logging for health checks."""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    handler = logging.FileHandler(LOG_DIR / "health_monitor.log")
    handler.setFormatter(
        logging.Formatter("%(asctime)s [%(name)s] %(levelname)s %(message)s")
    )
    logging.getLogger("health_monitor").addHandler(handler)


class MonitorDaemon:
    """Background daemon that periodically checks all registered accounts."""

    def __init__(
        self,
        monitor: AccountHealthMonitor,
        alert_manager: AlertManager | None = None,
        check_interval: int = 300,  # 5 minutes
    ):
        self.monitor = monitor
        self.alerts = alert_manager or AlertManager(monitor.redis)
        self.check_interval = check_interval
        self._running = False
        self._task: asyncio.Task | None = None
        # Cache of last-known status per account for change detection
        self._last_status: dict[str, str] = {}

    async def run(self) -> None:
        """Main loop. Blocks until stopped."""
        self._running = True
        _setup_file_logging()

        logger.info(
            "Health monitor daemon starting (check every %ds)", self.check_interval
        )

        # Load last-known statuses from Redis
        accounts = await self.monitor.get_registered_accounts()
        for account_id in accounts:
            check = await self.monitor.get_current_status(account_id)
            if check:
                self._last_status[account_id] = check.status.value

        self._task = asyncio.create_task(self._check_loop(), name="health_check_loop")

        try:
            await self._task
        except asyncio.CancelledError:
            logger.info("Health monitor daemon cancelled")

    async def stop(self) -> None:
        """Graceful shutdown."""
        self._running = False
        if self._task:
            self._task.cancel()
        logger.info("Health monitor daemon stopped")

    async def _check_loop(self) -> None:
        """Periodically check all registered accounts."""
        while self._running:
            try:
                accounts = await self.monitor.get_registered_accounts()
                if not accounts:
                    logger.debug("No accounts registered for health monitoring")
                else:
                    await self._check_all(accounts)
            except Exception:
                logger.exception("Error in health check loop")

            await asyncio.sleep(self.check_interval)

    async def _check_all(self, accounts: dict[str, str]) -> None:
        """Check all accounts, detect status changes, publish alerts."""
        logger.info("Running health checks on %d accounts", len(accounts))

        for account_id, auth_token in accounts.items():
            try:
                check = await self.monitor.check_health(account_id, auth_token)
                new_status = check.status.value
                old_status = self._last_status.get(account_id)

                if old_status is not None and old_status != new_status:
                    logger.info(
                        "Status change for %s: %s -> %s",
                        account_id, old_status, new_status,
                    )
                    await self.alerts.record_status_change(
                        account_id=account_id,
                        old_status=old_status,
                        new_status=new_status,
                    )

                self._last_status[account_id] = new_status

                logger.debug(
                    "Health check %s: %s (HTTP %s)",
                    account_id, new_status, check.response_code,
                )

                # Brief pause between checks to avoid hammering the API
                await asyncio.sleep(1)

            except Exception:
                logger.exception("Error checking account %s", account_id)

        summary = await self.monitor.get_status_summary()
        logger.info("Health summary: %s", json.dumps(summary))


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

    monitor = AccountHealthMonitor(redis_client)
    alert_manager = AlertManager(redis_client)
    daemon = MonitorDaemon(monitor, alert_manager)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, lambda: asyncio.create_task(daemon.stop()))

    try:
        await daemon.run()
    finally:
        await redis_client.close()


if __name__ == "__main__":
    asyncio.run(main())
