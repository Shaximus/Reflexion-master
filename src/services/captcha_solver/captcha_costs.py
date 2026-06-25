"""CAPTCHA Cost Tracker — Redis-backed spending and success rate tracking.

Tracks costs, success rates, and latency per solver. Provides daily/weekly
cost reports and per-solver performance metrics.
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional

import redis.asyncio as redis

logger = logging.getLogger(__name__)

PREFIX = "captcha:costs"


class CAPTCHACostTracker:
    """Track CAPTCHA solving costs and success rates via Redis."""

    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client

    @classmethod
    async def create(
        cls,
        redis_url: str = "redis://localhost:6379",
        redis_password: str = "ShaxAGI2025",
    ) -> "CAPTCHACostTracker":
        """Factory method with new Redis connection."""
        client = redis.from_url(
            redis_url,
            password=redis_password,
            decode_responses=True,
        )
        return cls(client)

    def _daily_key(self, date: Optional[datetime] = None) -> str:
        """Key for daily cost tracking."""
        d = date or datetime.now(timezone.utc)
        return f"{PREFIX}:daily:{d.strftime('%Y-%m-%d')}"

    def _solver_key(self, solver: str) -> str:
        """Key for per-solver stats."""
        return f"{PREFIX}:solver:{solver}"

    async def record_solve(self, solver: str, cost: float, success: bool,
                           latency_ms: int = 0, challenge_type: str = ""):
        """
        Record a CAPTCHA solve attempt.

        Args:
            solver: Solver name ("local", "gemini", "capsolver", "2captcha")
            cost: Cost in USD
            success: Whether solve was successful
            latency_ms: Time taken in milliseconds
            challenge_type: Type of CAPTCHA solved
        """
        now = datetime.now(timezone.utc)
        daily_key = self._daily_key(now)
        solver_key = self._solver_key(solver)

        # Record to daily list
        entry = json.dumps({
            "solver": solver,
            "cost": cost,
            "success": success,
            "latency_ms": latency_ms,
            "type": challenge_type,
            "timestamp": now.isoformat(),
        })
        await self.redis.rpush(daily_key, entry)
        # Auto-expire daily keys after 30 days
        await self.redis.expire(daily_key, 30 * 86400)

        # Update per-solver running totals
        pipe = self.redis.pipeline()
        pipe.hincrbyfloat(solver_key, "total_cost", cost)
        pipe.hincrby(solver_key, "total_attempts", 1)
        if success:
            pipe.hincrby(solver_key, "total_successes", 1)
        else:
            pipe.hincrby(solver_key, "total_failures", 1)
        pipe.hincrbyfloat(solver_key, "total_latency_ms", latency_ms)
        pipe.hset(solver_key, "last_used", now.isoformat())
        await pipe.execute()

        logger.debug(
            f"Recorded: {solver} cost=${cost:.4f} "
            f"{'OK' if success else 'FAIL'} {latency_ms}ms"
        )

    async def get_daily_spend(self, date: Optional[datetime] = None) -> float:
        """Get total spend for a specific day (default: today)."""
        daily_key = self._daily_key(date)
        entries = await self.redis.lrange(daily_key, 0, -1)
        total = 0.0
        for entry in entries:
            data = json.loads(entry)
            total += data.get("cost", 0)
        return total

    async def get_daily_stats(self, date: Optional[datetime] = None) -> dict:
        """Get detailed stats for a day."""
        daily_key = self._daily_key(date)
        entries = await self.redis.lrange(daily_key, 0, -1)

        stats = {
            "date": (date or datetime.now(timezone.utc)).strftime("%Y-%m-%d"),
            "total_cost": 0.0,
            "total_solves": 0,
            "successes": 0,
            "failures": 0,
            "by_solver": {},
            "by_type": {},
        }

        for raw in entries:
            data = json.loads(raw)
            cost = data.get("cost", 0)
            solver = data.get("solver", "unknown")
            success = data.get("success", False)
            ctype = data.get("type", "unknown")

            stats["total_cost"] += cost
            stats["total_solves"] += 1
            if success:
                stats["successes"] += 1
            else:
                stats["failures"] += 1

            # Per-solver breakdown
            if solver not in stats["by_solver"]:
                stats["by_solver"][solver] = {"cost": 0, "count": 0, "successes": 0}
            stats["by_solver"][solver]["cost"] += cost
            stats["by_solver"][solver]["count"] += 1
            if success:
                stats["by_solver"][solver]["successes"] += 1

            # Per-type breakdown
            if ctype not in stats["by_type"]:
                stats["by_type"][ctype] = {"cost": 0, "count": 0}
            stats["by_type"][ctype]["cost"] += cost
            stats["by_type"][ctype]["count"] += 1

        return stats

    async def get_success_rates(self) -> dict[str, float]:
        """Get per-solver success rates (lifetime)."""
        rates = {}
        solvers = ["local", "gemini", "capsolver", "2captcha"]

        for solver in solvers:
            key = self._solver_key(solver)
            data = await self.redis.hgetall(key)
            if not data:
                continue
            attempts = int(data.get("total_attempts", 0))
            successes = int(data.get("total_successes", 0))
            if attempts > 0:
                rates[solver] = successes / attempts
            else:
                rates[solver] = 0.0

        return rates

    async def get_solver_stats(self, solver: str) -> Optional[dict]:
        """Get detailed lifetime stats for a specific solver."""
        key = self._solver_key(solver)
        data = await self.redis.hgetall(key)
        if not data:
            return None

        attempts = int(data.get("total_attempts", 0))
        successes = int(data.get("total_successes", 0))
        total_latency = float(data.get("total_latency_ms", 0))

        return {
            "solver": solver,
            "total_cost": float(data.get("total_cost", 0)),
            "total_attempts": attempts,
            "total_successes": successes,
            "total_failures": int(data.get("total_failures", 0)),
            "success_rate": successes / attempts if attempts > 0 else 0.0,
            "avg_latency_ms": total_latency / attempts if attempts > 0 else 0.0,
            "last_used": data.get("last_used"),
        }

    async def get_cost_report(self, days: int = 7) -> dict:
        """
        Get cost report for the last N days.

        Returns daily breakdown + totals.
        """
        report = {
            "period_days": days,
            "total_cost": 0.0,
            "total_solves": 0,
            "daily": [],
            "solver_summary": {},
        }

        now = datetime.now(timezone.utc)
        for i in range(days):
            date = now - timedelta(days=i)
            day_stats = await self.get_daily_stats(date)
            report["daily"].append(day_stats)
            report["total_cost"] += day_stats["total_cost"]
            report["total_solves"] += day_stats["total_solves"]

            # Aggregate solver data
            for solver, sdata in day_stats["by_solver"].items():
                if solver not in report["solver_summary"]:
                    report["solver_summary"][solver] = {"cost": 0, "count": 0}
                report["solver_summary"][solver]["cost"] += sdata["cost"]
                report["solver_summary"][solver]["count"] += sdata["count"]

        # Add success rates
        report["success_rates"] = await self.get_success_rates()

        return report

    async def close(self):
        """Close Redis connection."""
        await self.redis.aclose()
