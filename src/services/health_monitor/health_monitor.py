"""
Account Health Monitor for Reflexion soul accounts.

Probes account status via API calls and maintains a health history in Redis.
Detects suspension, shadowban, rate-limiting, and account locks.
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

import aiohttp
import redis.asyncio as aioredis

logger = logging.getLogger("health_monitor")

TWEETAPI_BASE = "https://api.tweetapi.com/2"
TWEETAPI_KEY = os.getenv("TWEETAPI_KEY", "")


# ---------------------------------------------------------------------------
# Enums & data models
# ---------------------------------------------------------------------------

class AccountStatus(Enum):
    HEALTHY = "healthy"
    RATE_LIMITED = "rate_limited"
    SHADOWBANNED = "shadowbanned"
    SUSPENDED = "suspended"
    LOCKED = "locked"
    UNKNOWN = "unknown"


@dataclass
class HealthCheck:
    account_id: str
    status: AccountStatus
    checked_at: datetime
    details: dict
    response_code: Optional[int]

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "status": self.status.value,
            "checked_at": self.checked_at.isoformat(),
            "details": self.details,
            "response_code": self.response_code,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "HealthCheck":
        return cls(
            account_id=data["account_id"],
            status=AccountStatus(data["status"]),
            checked_at=datetime.fromisoformat(data["checked_at"]),
            details=data.get("details", {}),
            response_code=data.get("response_code"),
        )


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

_PREFIX = "health"


def _status_key(account_id: str) -> str:
    return f"{_PREFIX}:status:{account_id}"


def _history_key(account_id: str) -> str:
    return f"{_PREFIX}:history:{account_id}"


def _accounts_key() -> str:
    return f"{_PREFIX}:accounts"


# ---------------------------------------------------------------------------
# Health Monitor
# ---------------------------------------------------------------------------

class AccountHealthMonitor:
    """Monitors health of Reflexion soul accounts."""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    async def register_account(self, account_id: str, auth_token: str) -> None:
        """Register an account for health monitoring."""
        await self.redis.hset(_accounts_key(), account_id, auth_token)
        logger.info("Registered account %s for health monitoring", account_id)

    async def unregister_account(self, account_id: str) -> None:
        """Remove an account from health monitoring."""
        await self.redis.hdel(_accounts_key(), account_id)
        logger.info("Unregistered account %s from health monitoring", account_id)

    async def get_registered_accounts(self) -> Dict[str, str]:
        """Get all registered accounts with their auth tokens."""
        return await self.redis.hgetall(_accounts_key())

    async def check_health(
        self, account_id: str, auth_token: str
    ) -> HealthCheck:
        """
        Check account health via API probe.
        Detect: suspension, shadowban, rate limit, lock.
        """
        now = datetime.now(timezone.utc)
        details: dict = {}
        response_code: Optional[int] = None

        try:
            async with aiohttp.ClientSession() as session:
                # Probe: attempt to fetch the account's own profile
                headers = {
                    "x-api-key": TWEETAPI_KEY,
                    "Content-Type": "application/json",
                }

                # Use the user lookup endpoint
                async with session.get(
                    f"{TWEETAPI_BASE}/user/by/username/{account_id}",
                    headers=headers,
                    timeout=aiohttp.ClientTimeout(total=15),
                ) as resp:
                    response_code = resp.status
                    body = await resp.text()

                    try:
                        data = json.loads(body)
                    except json.JSONDecodeError:
                        data = {"raw": body[:500]}

                    details["probe_response"] = data

            status = self._interpret_response(response_code, data)

        except aiohttp.ClientError as e:
            status = AccountStatus.UNKNOWN
            details["error"] = str(e)
            logger.warning("Health check failed for %s: %s", account_id, e)

        except Exception as e:
            status = AccountStatus.UNKNOWN
            details["error"] = str(e)
            logger.exception("Unexpected error checking %s", account_id)

        check = HealthCheck(
            account_id=account_id,
            status=status,
            checked_at=now,
            details=details,
            response_code=response_code,
        )

        await self.record_health(check)
        return check

    async def record_health(self, check: HealthCheck) -> None:
        """Store health check result in Redis."""
        pipe = self.redis.pipeline()
        # Current status
        pipe.set(_status_key(check.account_id), json.dumps(check.to_dict()))
        # History (sorted set scored by timestamp)
        score = check.checked_at.timestamp()
        pipe.zadd(
            _history_key(check.account_id),
            {json.dumps(check.to_dict()): score},
        )
        # Trim history to last 7 days (604800 seconds)
        cutoff = time.time() - 604800
        pipe.zremrangebyscore(_history_key(check.account_id), "-inf", cutoff)
        await pipe.execute()

    async def get_current_status(self, account_id: str) -> HealthCheck | None:
        """Get the most recent health check for an account."""
        raw = await self.redis.get(_status_key(account_id))
        if raw is None:
            return None
        return HealthCheck.from_dict(json.loads(raw))

    async def get_health_history(
        self, account_id: str, hours: int = 24
    ) -> List[HealthCheck]:
        """Get recent health checks for an account."""
        cutoff = time.time() - (hours * 3600)
        raw_entries = await self.redis.zrangebyscore(
            _history_key(account_id), cutoff, "+inf"
        )
        return [HealthCheck.from_dict(json.loads(entry)) for entry in raw_entries]

    async def get_unhealthy_accounts(self) -> List[HealthCheck]:
        """Get all accounts with non-healthy status."""
        accounts = await self.get_registered_accounts()
        unhealthy = []
        for account_id in accounts:
            check = await self.get_current_status(account_id)
            if check is not None and check.status != AccountStatus.HEALTHY:
                unhealthy.append(check)
        return unhealthy

    async def get_status_summary(self) -> dict:
        """Summary: {healthy: N, suspended: N, shadowbanned: N, ...}"""
        accounts = await self.get_registered_accounts()
        summary: Dict[str, int] = {s.value: 0 for s in AccountStatus}
        summary["total"] = len(accounts)
        summary["unchecked"] = 0

        for account_id in accounts:
            check = await self.get_current_status(account_id)
            if check is None:
                summary["unchecked"] += 1
            else:
                summary[check.status.value] += 1

        return summary

    # -- response interpretation -----------------------------------------

    @staticmethod
    def _interpret_response(status_code: int | None, data: dict) -> AccountStatus:
        """Map API response to an AccountStatus."""
        if status_code is None:
            return AccountStatus.UNKNOWN

        if status_code == 429:
            return AccountStatus.RATE_LIMITED

        if status_code == 403:
            return AccountStatus.SUSPENDED

        if status_code == 401:
            return AccountStatus.LOCKED

        if status_code == 200:
            # Check for suspension/shadowban markers in the response body
            if isinstance(data, dict):
                user_data = data.get("data", data)

                # Twitter returns suspended flag
                if user_data.get("suspended", False):
                    return AccountStatus.SUSPENDED

                # Protected/locked account
                if user_data.get("protected", False):
                    # Not necessarily bad, but track it
                    pass

                # Withheld = shadowban indicator
                if "withheld" in user_data:
                    return AccountStatus.SHADOWBANNED

                # Empty tweet results can indicate shadowban
                # (but we'd need a separate search probe for that)

            return AccountStatus.HEALTHY

        if 500 <= status_code < 600:
            return AccountStatus.UNKNOWN

        return AccountStatus.UNKNOWN
