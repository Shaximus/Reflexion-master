"""
Gradual Onboarding Scheduler for Reflexion soul accounts.

Manages a 30-day ramp-up protocol that transitions new accounts through
progressive activity phases to avoid platform detection. All state lives
in Redis -- no local files.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

import redis.asyncio as aioredis

logger = logging.getLogger("onboarding.scheduler")

# ---------------------------------------------------------------------------
# Enums & data models
# ---------------------------------------------------------------------------

class OnboardingPhase(Enum):
    SETUP = "setup"             # Days 1-3: Profile completion only
    OBSERVATION = "observation"  # Days 4-7: 5 actions/day, likes only
    LIGHT = "light"             # Days 8-14: 15 actions/day, 1 post
    ACTIVE = "active"           # Days 15-21: 30 actions/day, replies/RTs
    NORMAL = "normal"           # Days 22-30: Full activity
    GRADUATED = "graduated"     # Day 30+: Ready for full deployment


# Ordered list for phase advancement logic
PHASE_ORDER: List[OnboardingPhase] = [
    OnboardingPhase.SETUP,
    OnboardingPhase.OBSERVATION,
    OnboardingPhase.LIGHT,
    OnboardingPhase.ACTIVE,
    OnboardingPhase.NORMAL,
    OnboardingPhase.GRADUATED,
]


PHASE_CONFIG: Dict[OnboardingPhase, dict] = {
    OnboardingPhase.SETUP: {
        "duration_days": 3,
        "max_actions_per_day": 0,
        "allowed_actions": ["profile_update", "avatar_upload", "bio_update"],
        "can_post": False,
        "can_reply": False,
        "can_like": False,
        "can_retweet": False,
        "can_follow": False,
        "can_use_links": False,
        "sub_limits": {},
    },
    OnboardingPhase.OBSERVATION: {
        "duration_days": 4,
        "max_actions_per_day": 5,
        "allowed_actions": ["like", "follow"],
        "can_post": False,
        "can_reply": False,
        "can_like": True,
        "can_retweet": False,
        "can_follow": True,
        "can_use_links": False,
        "sub_limits": {"follow": 3},
    },
    OnboardingPhase.LIGHT: {
        "duration_days": 7,
        "max_actions_per_day": 15,
        "allowed_actions": ["like", "follow", "post"],
        "can_post": True,
        "can_reply": False,
        "can_like": True,
        "can_retweet": False,
        "can_follow": True,
        "can_use_links": False,
        "sub_limits": {"post": 1, "follow": 5},
    },
    OnboardingPhase.ACTIVE: {
        "duration_days": 7,
        "max_actions_per_day": 30,
        "allowed_actions": ["like", "follow", "post", "reply", "retweet"],
        "can_post": True,
        "can_reply": True,
        "can_like": True,
        "can_retweet": True,
        "can_follow": True,
        "can_use_links": False,
        "sub_limits": {"post": 3, "retweet": 5, "follow": 10},
    },
    OnboardingPhase.NORMAL: {
        "duration_days": 9,
        "max_actions_per_day": 50,
        "allowed_actions": ["like", "follow", "post", "reply", "retweet", "quote"],
        "can_post": True,
        "can_reply": True,
        "can_like": True,
        "can_retweet": True,
        "can_follow": True,
        "can_use_links": True,
        "sub_limits": {"post": 5},
    },
    OnboardingPhase.GRADUATED: {
        "duration_days": None,  # Permanent
        "max_actions_per_day": 100,
        "allowed_actions": ["all"],
        "can_post": True,
        "can_reply": True,
        "can_like": True,
        "can_retweet": True,
        "can_follow": True,
        "can_use_links": True,
        "sub_limits": {},
    },
}


@dataclass
class AccountSchedule:
    account_id: str
    created_at: datetime
    current_phase: OnboardingPhase
    actions_today: int
    max_actions_today: int
    last_action_at: Optional[datetime]
    phase_started_at: datetime
    graduated_at: Optional[datetime]
    metadata: dict = field(default_factory=dict)
    action_counts_today: dict = field(default_factory=dict)  # per-type counts

    # -- serialisation helpers -------------------------------------------

    def to_dict(self) -> dict:
        return {
            "account_id": self.account_id,
            "created_at": self.created_at.isoformat(),
            "current_phase": self.current_phase.value,
            "actions_today": self.actions_today,
            "max_actions_today": self.max_actions_today,
            "last_action_at": self.last_action_at.isoformat() if self.last_action_at else None,
            "phase_started_at": self.phase_started_at.isoformat(),
            "graduated_at": self.graduated_at.isoformat() if self.graduated_at else None,
            "metadata": self.metadata,
            "action_counts_today": self.action_counts_today,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "AccountSchedule":
        return cls(
            account_id=data["account_id"],
            created_at=datetime.fromisoformat(data["created_at"]),
            current_phase=OnboardingPhase(data["current_phase"]),
            actions_today=int(data["actions_today"]),
            max_actions_today=int(data["max_actions_today"]),
            last_action_at=(
                datetime.fromisoformat(data["last_action_at"])
                if data.get("last_action_at")
                else None
            ),
            phase_started_at=datetime.fromisoformat(data["phase_started_at"]),
            graduated_at=(
                datetime.fromisoformat(data["graduated_at"])
                if data.get("graduated_at")
                else None
            ),
            metadata=data.get("metadata", {}),
            action_counts_today=data.get("action_counts_today", {}),
        )


# ---------------------------------------------------------------------------
# Redis key helpers
# ---------------------------------------------------------------------------

_PREFIX = "onboarding"


def _account_key(account_id: str) -> str:
    return f"{_PREFIX}:account:{account_id}"


def _index_key() -> str:
    return f"{_PREFIX}:accounts"


def _phase_set_key(phase: OnboardingPhase) -> str:
    return f"{_PREFIX}:phase:{phase.value}"


# ---------------------------------------------------------------------------
# Scheduler
# ---------------------------------------------------------------------------

class OnboardingScheduler:
    """Manages gradual onboarding for Reflexion soul accounts."""

    def __init__(self, redis_client: aioredis.Redis):
        self.redis = redis_client

    # -- account lifecycle -----------------------------------------------

    async def register_account(
        self, account_id: str, metadata: dict | None = None
    ) -> AccountSchedule:
        """Register a new account for onboarding."""
        now = datetime.now(timezone.utc)
        phase = OnboardingPhase.SETUP
        config = PHASE_CONFIG[phase]

        schedule = AccountSchedule(
            account_id=account_id,
            created_at=now,
            current_phase=phase,
            actions_today=0,
            max_actions_today=config["max_actions_per_day"],
            last_action_at=None,
            phase_started_at=now,
            graduated_at=None,
            metadata=metadata or {},
            action_counts_today={},
        )

        pipe = self.redis.pipeline()
        pipe.set(_account_key(account_id), json.dumps(schedule.to_dict()))
        pipe.sadd(_index_key(), account_id)
        pipe.sadd(_phase_set_key(phase), account_id)
        await pipe.execute()

        logger.info("Registered account %s in phase %s", account_id, phase.value)
        return schedule

    async def get_schedule(self, account_id: str) -> AccountSchedule | None:
        """Get current schedule/phase for an account."""
        raw = await self.redis.get(_account_key(account_id))
        if raw is None:
            return None
        return AccountSchedule.from_dict(json.loads(raw))

    async def _save_schedule(self, schedule: AccountSchedule) -> None:
        await self.redis.set(
            _account_key(schedule.account_id),
            json.dumps(schedule.to_dict()),
        )

    # -- action gating ---------------------------------------------------

    async def can_act(self, account_id: str, action_type: str = "like") -> bool:
        """Can this account perform another action of *action_type* right now?"""
        schedule = await self.get_schedule(account_id)
        if schedule is None:
            return False

        config = PHASE_CONFIG[schedule.current_phase]

        # Check global daily cap
        if schedule.actions_today >= config["max_actions_per_day"]:
            return False

        # Check action type is allowed
        allowed = config["allowed_actions"]
        if "all" not in allowed and action_type not in allowed:
            return False

        # Check capability flag
        cap_key = f"can_{action_type}"
        if cap_key in config and not config[cap_key]:
            return False

        # Check per-type sub-limit
        sub_limits = config.get("sub_limits", {})
        if action_type in sub_limits:
            count = schedule.action_counts_today.get(action_type, 0)
            if count >= sub_limits[action_type]:
                return False

        return True

    async def record_action(self, account_id: str, action_type: str) -> None:
        """Record that an action was performed. Raises ValueError if not allowed."""
        schedule = await self.get_schedule(account_id)
        if schedule is None:
            raise ValueError(f"Account {account_id} not registered")

        if not await self.can_act(account_id, action_type):
            raise ValueError(
                f"Account {account_id} cannot perform '{action_type}' in phase "
                f"{schedule.current_phase.value} (budget: {schedule.actions_today}/"
                f"{schedule.max_actions_today})"
            )

        now = datetime.now(timezone.utc)
        schedule.actions_today += 1
        schedule.action_counts_today[action_type] = (
            schedule.action_counts_today.get(action_type, 0) + 1
        )
        schedule.last_action_at = now

        # Track follow ratio in metadata
        if action_type == "follow":
            schedule.metadata.setdefault("total_follows", 0)
            schedule.metadata["total_follows"] += 1

        await self._save_schedule(schedule)
        logger.debug(
            "Recorded %s for %s (%d/%d today)",
            action_type, account_id,
            schedule.actions_today, schedule.max_actions_today,
        )

    # -- phase management ------------------------------------------------

    async def advance_phases(self) -> List[dict]:
        """Check all accounts and advance phases based on age. Returns list of transitions."""
        account_ids = await self.redis.smembers(_index_key())
        transitions = []

        for account_id in account_ids:
            schedule = await self.get_schedule(account_id)
            if schedule is None or schedule.current_phase == OnboardingPhase.GRADUATED:
                continue

            config = PHASE_CONFIG[schedule.current_phase]
            duration = config["duration_days"]
            if duration is None:
                continue

            now = datetime.now(timezone.utc)
            days_in_phase = (now - schedule.phase_started_at).total_seconds() / 86400

            if days_in_phase >= duration:
                old_phase = schedule.current_phase
                new_phase = self._next_phase(old_phase)
                if new_phase is None:
                    continue

                new_config = PHASE_CONFIG[new_phase]

                # Update phase sets
                pipe = self.redis.pipeline()
                pipe.srem(_phase_set_key(old_phase), account_id)
                pipe.sadd(_phase_set_key(new_phase), account_id)
                await pipe.execute()

                schedule.current_phase = new_phase
                schedule.phase_started_at = now
                schedule.max_actions_today = new_config["max_actions_per_day"]

                if new_phase == OnboardingPhase.GRADUATED:
                    schedule.graduated_at = now

                await self._save_schedule(schedule)

                transition = {
                    "account_id": account_id,
                    "old_phase": old_phase.value,
                    "new_phase": new_phase.value,
                    "timestamp": now.isoformat(),
                }
                transitions.append(transition)

                logger.info(
                    "Account %s advanced: %s -> %s",
                    account_id, old_phase.value, new_phase.value,
                )

        return transitions

    async def reset_daily_counters(self) -> int:
        """Reset daily action counters for all accounts. Returns count of accounts reset."""
        account_ids = await self.redis.smembers(_index_key())
        count = 0

        for account_id in account_ids:
            schedule = await self.get_schedule(account_id)
            if schedule is None:
                continue
            schedule.actions_today = 0
            schedule.action_counts_today = {}
            await self._save_schedule(schedule)
            count += 1

        logger.info("Reset daily counters for %d accounts", count)
        return count

    # -- queries ---------------------------------------------------------

    async def get_accounts_by_phase(
        self, phase: OnboardingPhase
    ) -> List[AccountSchedule]:
        """List accounts in a specific phase."""
        account_ids = await self.redis.smembers(_phase_set_key(phase))
        results = []
        for account_id in account_ids:
            schedule = await self.get_schedule(account_id)
            if schedule is not None:
                results.append(schedule)
        return results

    async def get_graduated_accounts(self) -> List[AccountSchedule]:
        """List accounts ready for full deployment."""
        return await self.get_accounts_by_phase(OnboardingPhase.GRADUATED)

    async def get_daily_budget(self, account_id: str) -> dict | None:
        """Get remaining action budget for today."""
        schedule = await self.get_schedule(account_id)
        if schedule is None:
            return None

        config = PHASE_CONFIG[schedule.current_phase]
        sub_limits = config.get("sub_limits", {})

        budget = {
            "account_id": account_id,
            "phase": schedule.current_phase.value,
            "total_remaining": config["max_actions_per_day"] - schedule.actions_today,
            "total_used": schedule.actions_today,
            "total_max": config["max_actions_per_day"],
            "allowed_actions": config["allowed_actions"],
            "per_type": {},
        }

        for action_type in config["allowed_actions"]:
            if action_type == "all":
                continue
            used = schedule.action_counts_today.get(action_type, 0)
            limit = sub_limits.get(action_type)
            budget["per_type"][action_type] = {
                "used": used,
                "limit": limit,  # None means only capped by global max
                "remaining": (limit - used) if limit is not None else None,
            }

        return budget

    async def get_all_accounts(self) -> List[AccountSchedule]:
        """List all registered accounts."""
        account_ids = await self.redis.smembers(_index_key())
        results = []
        for account_id in account_ids:
            schedule = await self.get_schedule(account_id)
            if schedule is not None:
                results.append(schedule)
        return results

    async def unregister_account(self, account_id: str) -> bool:
        """Remove an account from onboarding tracking."""
        schedule = await self.get_schedule(account_id)
        if schedule is None:
            return False

        pipe = self.redis.pipeline()
        pipe.delete(_account_key(account_id))
        pipe.srem(_index_key(), account_id)
        pipe.srem(_phase_set_key(schedule.current_phase), account_id)
        await pipe.execute()

        logger.info("Unregistered account %s", account_id)
        return True

    # -- helpers ---------------------------------------------------------

    @staticmethod
    def _next_phase(current: OnboardingPhase) -> OnboardingPhase | None:
        idx = PHASE_ORDER.index(current)
        if idx + 1 < len(PHASE_ORDER):
            return PHASE_ORDER[idx + 1]
        return None
