"""Self-healing ban detection and account replacement loop."""
from __future__ import annotations

import asyncio
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import redis.asyncio as aioredis

from services.health_monitor import AccountHealthMonitor, AlertManager
from services.onboarding import OnboardingScheduler

if TYPE_CHECKING:
    from .orchestrator import AccountPipeline

logger = logging.getLogger(__name__)

# The 11 soul names
DEFAULT_SOUL_NAMES = [
    "mirror",
    "nexus",
    "echoes",
    "void",
    "architect",
    "singularity",
    "phoenix",
    "pantheon",
    "consciousness",
    "glyph",
    "fractal",
]

# Redis key prefixes for pool management
POOL_WARMING_KEY = "pipeline:pool:warming"
POOL_GRADUATED_KEY = "pipeline:pool:graduated"
POOL_ACTIVE_KEY = "pipeline:pool:active"
POOL_BANNED_KEY = "pipeline:pool:banned"
POOL_NEEDS_REPLACEMENT_KEY = "pipeline:pool:needs_replacement"


@dataclass
class PoolStatus:
    """Current state of the account pool."""

    warming: int = 0
    graduated: int = 0
    active: int = 0
    banned: int = 0
    replacement_needed: int = 0
    buffer_target: int = 0


class ClosedLoop:
    """Self-healing loop: detect bans, replace accounts, maintain buffer pool."""

    def __init__(
        self,
        redis_client: aioredis.Redis,
        scheduler: OnboardingScheduler,
        health_monitor: AccountHealthMonitor,
        alert_manager: AlertManager,
        pipeline: AccountPipeline,
        buffer_size: int = 3,
        soul_names: Optional[List[str]] = None,
        reflexion_root: str = "/home/shax/Projects/core-tech/Reflexion-master",
    ):
        self.redis = redis_client
        self.scheduler = scheduler
        self.health_monitor = health_monitor
        self.alert_manager = alert_manager
        self.pipeline = pipeline
        self.buffer_size = buffer_size
        self.soul_names = soul_names or DEFAULT_SOUL_NAMES
        self.reflexion_root = Path(reflexion_root)

        self._running = False
        self._tasks: List[asyncio.Task] = []
        self._maintenance_interval = 300  # 5 minutes

    # ── File paths ──

    @property
    def soul_data_path(self) -> Path:
        return self.reflexion_root / "soul_data.json"

    @property
    def soul_usernames_path(self) -> Path:
        return self.reflexion_root / "soul_usernames.json"

    @property
    def banned_souls_path(self) -> Path:
        return self.reflexion_root / "banned_souls.json"

    # ── JSON helpers ──

    def _read_json(self, path: Path) -> dict:
        """Read a JSON file, return empty dict if missing or corrupt."""
        try:
            if path.exists():
                return json.loads(path.read_text())
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not read {path}: {e}")
        return {}

    def _write_json(self, path: Path, data: dict) -> None:
        """Write data to JSON file atomically."""
        tmp = path.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(data, indent=2))
            tmp.replace(path)
        except IOError as e:
            logger.error(f"Could not write {path}: {e}")
            if tmp.exists():
                tmp.unlink()

    # ── Lifecycle ──

    async def start(self) -> None:
        """Subscribe to health alerts and start monitoring loop."""
        self._running = True

        # Subscribe to status change events
        await self.alert_manager.subscribe_status_changes(self._on_status_change)

        # Start pool maintenance background task
        task = asyncio.create_task(self._maintenance_loop())
        self._tasks.append(task)

        logger.info("Closed loop started - monitoring bans and maintaining pool")

    async def stop(self) -> None:
        """Stop all background tasks."""
        self._running = False
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
        self._tasks.clear()
        logger.info("Closed loop stopped")

    # ── Event handlers ──

    async def _on_status_change(self, alert: dict) -> None:
        """Handle status change events from health monitor.

        If status is 'suspended' or 'locked':
          1. Mark account as dead in banned_souls.json
          2. Check graduated pool for replacement
          3. If graduated available -> assign to soul
          4. If pool empty -> trigger pipeline.create_account()

        Note: AlertManager delivers keys: account_id, old_status, new_status, timestamp, channel.
        We map new_status -> status and resolve soul_name from our pool mappings.
        """
        # Adapt alert dict from health_monitor's format (prefers new_status per AlertManager contract)
        status = alert.get("new_status") or alert.get("status", "")
        account_id = alert.get("account_id", "")
        soul_name = alert.get("soul_name", "")
        # If soul_name not in alert, resolve from our active pool
        if not soul_name and account_id:
            soul_name = await self._resolve_soul_name(account_id)

        if status not in ("suspended", "locked"):
            return

        logger.warning(f"Ban detected: account={account_id} soul={soul_name} status={status}")

        # 1. Mark as banned
        await self._mark_banned(account_id, soul_name, status)

        # 2. Track replacement need
        if soul_name:
            await self.redis.sadd(POOL_NEEDS_REPLACEMENT_KEY, soul_name)

        # 3. Try to assign from graduated pool
        replacement = await self._get_graduated_account()
        if replacement and soul_name:
            await self.assign_to_soul(
                soul_name,
                replacement["account_id"],
                replacement["auth_token"],
                replacement.get("username"),
            )
            logger.info(
                f"Replaced banned account for {soul_name} with {replacement['account_id']}"
            )
            await self.redis.srem(POOL_NEEDS_REPLACEMENT_KEY, soul_name)
        else:
            # 4. Trigger new account creation
            logger.info(f"No graduated accounts available - triggering new signup for {soul_name}")
            task = asyncio.create_task(self._create_replacement(soul_name))
            self._tasks.append(task)
            task.add_done_callback(lambda t: self._tasks.remove(t) if t in self._tasks else None)

    async def _create_replacement(self, soul_name: str) -> None:
        """Create a new account and assign it when ready."""
        try:
            result = await self.pipeline.create_account()
            if result.success and result.auth_token:
                logger.info(
                    f"Replacement account created: {result.username} for {soul_name}"
                )
                # The account will go through onboarding first
                # When it graduates, feed_graduated_to_swarm will assign it
            else:
                logger.error(
                    f"Failed to create replacement for {soul_name}: {result.error}"
                )
        except Exception as e:
            logger.exception(f"Replacement creation failed for {soul_name}: {e}")

    async def _resolve_soul_name(self, account_id: str) -> str:
        """Resolve soul name from active pool by account_id.

        POOL_ACTIVE_KEY is a HASH: account_id -> soul_name.
        """
        result = await self.redis.hget(POOL_ACTIVE_KEY, account_id)
        if result:
            return result.decode() if isinstance(result, bytes) else result
        logger.error(
            f"Cannot resolve soul_name for banned account {account_id}. "
            f"No automatic replacement will be triggered."
        )
        return ""

    async def _mark_banned(self, account_id: str, soul_name: str, status: str) -> None:
        """Mark account as banned in Redis and local files."""
        ban_entry = {
            "account_id": account_id,
            "soul_name": soul_name,
            "status": status,
            "banned_at": datetime.utcnow().isoformat(),
        }

        # Redis
        await self.redis.hset(POOL_BANNED_KEY, account_id, json.dumps(ban_entry))
        await self.redis.hdel(POOL_ACTIVE_KEY, account_id)

        # Local banned_souls.json
        banned = self._read_json(self.banned_souls_path)
        if "banned" not in banned:
            banned["banned"] = []
        banned["banned"].append(ban_entry)
        self._write_json(self.banned_souls_path, banned)

        # Remove from soul_data.json
        if soul_name:
            soul_data = self._read_json(self.soul_data_path)
            if soul_name in soul_data:
                soul_data[soul_name]["status"] = "banned"
                soul_data[soul_name]["banned_at"] = datetime.utcnow().isoformat()
                self._write_json(self.soul_data_path, soul_data)

        logger.info(f"Marked account {account_id} as banned ({status})")

    # ── Pool management ──

    async def _get_graduated_account(self) -> Optional[dict]:
        """Pop an account from the graduated pool."""
        # Get all graduated accounts
        accounts = await self.redis.hgetall(POOL_GRADUATED_KEY)
        if not accounts:
            return None

        # Take the oldest one
        account_id = next(iter(accounts))
        data_str = await self.redis.hget(POOL_GRADUATED_KEY, account_id)
        if not data_str:
            return None

        await self.redis.hdel(POOL_GRADUATED_KEY, account_id)
        try:
            return json.loads(data_str)
        except json.JSONDecodeError:
            return None

    async def assign_to_soul(
        self,
        soul_name: str,
        account_id: str,
        auth_token: str,
        username: Optional[str] = None,
    ) -> None:
        """Write credentials to soul_data.json and soul_usernames.json."""
        # Update soul_data.json
        soul_data = self._read_json(self.soul_data_path)
        soul_data[soul_name] = {
            "account_id": account_id,
            "auth_token": auth_token,
            "username": username,
            "assigned_at": datetime.utcnow().isoformat(),
            "status": "active",
        }
        self._write_json(self.soul_data_path, soul_data)

        # Update soul_usernames.json
        if username:
            usernames = self._read_json(self.soul_usernames_path)
            usernames[soul_name] = username
            self._write_json(self.soul_usernames_path, usernames)

        # Track in Redis (HASH: account_id -> soul_name)
        await self.redis.hset(POOL_ACTIVE_KEY, account_id, soul_name)
        await self.redis.hdel(POOL_GRADUATED_KEY, account_id)

        logger.info(
            f"Assigned account {account_id} ({username}) to soul '{soul_name}'"
        )

    async def get_pool_status(self) -> PoolStatus:
        """Get current pool statistics."""
        warming = await self.redis.hlen(POOL_WARMING_KEY)
        graduated = await self.redis.hlen(POOL_GRADUATED_KEY)
        active = await self.redis.hlen(POOL_ACTIVE_KEY)
        banned = await self.redis.hlen(POOL_BANNED_KEY)
        replacement_needed = await self.redis.scard(POOL_NEEDS_REPLACEMENT_KEY)
        buffer_target = self.buffer_size * len(self.soul_names)

        return PoolStatus(
            warming=warming,
            graduated=graduated,
            active=active,
            banned=banned,
            replacement_needed=replacement_needed,
            buffer_target=buffer_target,
        )

    async def maintain_pool(self) -> None:
        """Ensure buffer_size accounts are always warming per soul.

        If warming + graduated < buffer_target, trigger new signups.
        """
        status = await self.get_pool_status()
        pool_total = status.warming + status.graduated
        deficit = status.buffer_target - pool_total

        if deficit > 0:
            # Don't create too many at once - cap at max_concurrent
            batch_size = min(deficit, self.pipeline.config.max_concurrent_signups)
            logger.info(
                f"Pool maintenance: deficit={deficit}, creating {batch_size} accounts "
                f"(warming={status.warming}, graduated={status.graduated}, "
                f"target={status.buffer_target})"
            )
            for _ in range(batch_size):
                task = asyncio.create_task(self.pipeline.create_account())
                self._tasks.append(task)
                task.add_done_callback(lambda t: self._tasks.remove(t) if t in self._tasks else None)
        else:
            logger.debug(
                f"Pool healthy: warming={status.warming}, graduated={status.graduated}, "
                f"target={status.buffer_target}"
            )

    async def feed_graduated_to_swarm(self) -> List[dict]:
        """Check for newly graduated accounts and assign them to souls needing replacements.

        Returns list of {soul_name, account_id, assigned_at}.
        """
        assignments = []

        # Get souls needing replacement
        needs_replacement = await self.redis.smembers(POOL_NEEDS_REPLACEMENT_KEY)
        if not needs_replacement:
            return assignments

        for soul_name in needs_replacement:
            replacement = await self._get_graduated_account()
            if not replacement:
                logger.debug(f"No graduated accounts for {soul_name}")
                break

            await self.assign_to_soul(
                soul_name,
                replacement["account_id"],
                replacement["auth_token"],
                replacement.get("username"),
            )
            await self.redis.srem(POOL_NEEDS_REPLACEMENT_KEY, soul_name)

            assignment = {
                "soul_name": soul_name,
                "account_id": replacement["account_id"],
                "assigned_at": datetime.utcnow().isoformat(),
            }
            assignments.append(assignment)
            logger.info(
                f"Fed graduated account {replacement['account_id']} to soul '{soul_name}'"
            )

        return assignments

    # ── Background tasks ──

    async def _maintenance_loop(self) -> None:
        """Periodic pool maintenance and graduated feed."""
        while self._running:
            try:
                await self.maintain_pool()
                await self.feed_graduated_to_swarm()
            except Exception as e:
                logger.exception(f"Maintenance loop error: {e}")

            await asyncio.sleep(self._maintenance_interval)
