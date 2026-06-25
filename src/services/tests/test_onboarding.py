"""
Tests for the Gradual Onboarding Scheduler.

Uses fakeredis for isolated, in-memory Redis testing.
"""

import asyncio
import json
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, patch

import redis.asyncio as aioredis

from services.onboarding.onboarding_scheduler import (
    OnboardingPhase,
    OnboardingScheduler,
    AccountSchedule,
    PHASE_CONFIG,
    PHASE_ORDER,
)
from services.onboarding.scheduler_daemon import SchedulerDaemon

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def redis_client():
    """Connect to local Redis for testing (uses DB 15 to avoid collisions)."""
    client = aioredis.from_url(
        "redis://localhost:6379/15",
        password="ShaxAGI2025",
        decode_responses=True,
    )
    await client.flushdb()
    yield client
    await client.flushdb()
    await client.close()


@pytest_asyncio.fixture
async def scheduler(redis_client):
    return OnboardingScheduler(redis_client)


# ---------------------------------------------------------------------------
# Registration & Phase Basics
# ---------------------------------------------------------------------------

class TestRegistration:

    @pytest.mark.asyncio
    async def test_register_account(self, scheduler):
        schedule = await scheduler.register_account("test_soul_1", {"platform": "twitter"})

        assert schedule.account_id == "test_soul_1"
        assert schedule.current_phase == OnboardingPhase.SETUP
        assert schedule.actions_today == 0
        assert schedule.max_actions_today == 0  # SETUP has 0 actions
        assert schedule.metadata["platform"] == "twitter"

    @pytest.mark.asyncio
    async def test_get_schedule(self, scheduler):
        await scheduler.register_account("test_soul_2")
        schedule = await scheduler.get_schedule("test_soul_2")

        assert schedule is not None
        assert schedule.account_id == "test_soul_2"
        assert schedule.current_phase == OnboardingPhase.SETUP

    @pytest.mark.asyncio
    async def test_get_nonexistent_returns_none(self, scheduler):
        result = await scheduler.get_schedule("doesnt_exist")
        assert result is None

    @pytest.mark.asyncio
    async def test_unregister(self, scheduler):
        await scheduler.register_account("to_remove")
        assert await scheduler.unregister_account("to_remove") is True
        assert await scheduler.get_schedule("to_remove") is None


# ---------------------------------------------------------------------------
# Action Gating
# ---------------------------------------------------------------------------

class TestActionGating:

    @pytest.mark.asyncio
    async def test_setup_phase_blocks_all_social_actions(self, scheduler):
        await scheduler.register_account("setup_acct")

        # SETUP phase: no likes, posts, follows, etc.
        assert await scheduler.can_act("setup_acct", "like") is False
        assert await scheduler.can_act("setup_acct", "post") is False
        assert await scheduler.can_act("setup_acct", "follow") is False
        assert await scheduler.can_act("setup_acct", "reply") is False

    @pytest.mark.asyncio
    async def test_observation_phase_allows_likes(self, scheduler, redis_client):
        await scheduler.register_account("obs_acct")

        # Manually advance to OBSERVATION
        schedule = await scheduler.get_schedule("obs_acct")
        schedule.current_phase = OnboardingPhase.OBSERVATION
        schedule.max_actions_today = PHASE_CONFIG[OnboardingPhase.OBSERVATION]["max_actions_per_day"]
        await redis_client.set(
            f"onboarding:account:obs_acct",
            json.dumps(schedule.to_dict()),
        )
        await redis_client.srem("onboarding:phase:setup", "obs_acct")
        await redis_client.sadd("onboarding:phase:observation", "obs_acct")

        assert await scheduler.can_act("obs_acct", "like") is True
        assert await scheduler.can_act("obs_acct", "post") is False
        assert await scheduler.can_act("obs_acct", "reply") is False
        assert await scheduler.can_act("obs_acct", "retweet") is False

    @pytest.mark.asyncio
    async def test_daily_budget_enforcement(self, scheduler, redis_client):
        await scheduler.register_account("budget_acct")

        # Advance to OBSERVATION (5 actions/day)
        schedule = await scheduler.get_schedule("budget_acct")
        schedule.current_phase = OnboardingPhase.OBSERVATION
        schedule.max_actions_today = 5
        await redis_client.set(
            f"onboarding:account:budget_acct",
            json.dumps(schedule.to_dict()),
        )

        # Use up the budget
        for i in range(5):
            await scheduler.record_action("budget_acct", "like")

        # 6th action should be blocked
        assert await scheduler.can_act("budget_acct", "like") is False

    @pytest.mark.asyncio
    async def test_sub_limit_enforcement(self, scheduler, redis_client):
        """In OBSERVATION, follow is limited to 3/day even though total is 5."""
        await scheduler.register_account("sublimit_acct")

        schedule = await scheduler.get_schedule("sublimit_acct")
        schedule.current_phase = OnboardingPhase.OBSERVATION
        schedule.max_actions_today = 5
        await redis_client.set(
            f"onboarding:account:sublimit_acct",
            json.dumps(schedule.to_dict()),
        )
        await redis_client.srem("onboarding:phase:setup", "sublimit_acct")
        await redis_client.sadd("onboarding:phase:observation", "sublimit_acct")

        # 3 follows should work
        for _ in range(3):
            await scheduler.record_action("sublimit_acct", "follow")

        # 4th follow should be blocked (sub-limit 3)
        assert await scheduler.can_act("sublimit_acct", "follow") is False
        # But likes should still work (only 3/5 total used)
        assert await scheduler.can_act("sublimit_acct", "like") is True

    @pytest.mark.asyncio
    async def test_record_action_rejects_when_not_allowed(self, scheduler):
        await scheduler.register_account("reject_acct")

        with pytest.raises(ValueError):
            await scheduler.record_action("reject_acct", "like")  # SETUP blocks likes


# ---------------------------------------------------------------------------
# Phase Advancement
# ---------------------------------------------------------------------------

class TestPhaseAdvancement:

    @pytest.mark.asyncio
    async def test_advance_after_duration(self, scheduler, redis_client):
        await scheduler.register_account("advance_acct")

        # Backdate phase_started_at by 4 days (SETUP is 3 days)
        schedule = await scheduler.get_schedule("advance_acct")
        schedule.phase_started_at = datetime.now(timezone.utc) - timedelta(days=4)
        await redis_client.set(
            f"onboarding:account:advance_acct",
            json.dumps(schedule.to_dict()),
        )

        transitions = await scheduler.advance_phases()

        assert len(transitions) == 1
        assert transitions[0]["old_phase"] == "setup"
        assert transitions[0]["new_phase"] == "observation"

        # Verify the schedule was updated
        updated = await scheduler.get_schedule("advance_acct")
        assert updated.current_phase == OnboardingPhase.OBSERVATION

    @pytest.mark.asyncio
    async def test_no_advance_before_duration(self, scheduler):
        await scheduler.register_account("no_advance_acct")

        transitions = await scheduler.advance_phases()
        assert len(transitions) == 0

    @pytest.mark.asyncio
    async def test_full_graduation_path(self, scheduler, redis_client):
        """Simulate full 30-day progression."""
        await scheduler.register_account("grad_acct")

        cumulative_days = 0
        for phase in PHASE_ORDER[:-1]:  # All except GRADUATED
            config = PHASE_CONFIG[phase]
            duration = config["duration_days"]
            if duration is None:
                break

            # Backdate past this phase's duration
            schedule = await scheduler.get_schedule("grad_acct")
            schedule.phase_started_at = datetime.now(timezone.utc) - timedelta(days=duration + 1)
            await redis_client.set(
                f"onboarding:account:grad_acct",
                json.dumps(schedule.to_dict()),
            )

            transitions = await scheduler.advance_phases()
            assert len(transitions) >= 1

            cumulative_days += duration

        final = await scheduler.get_schedule("grad_acct")
        assert final.current_phase == OnboardingPhase.GRADUATED
        assert final.graduated_at is not None


# ---------------------------------------------------------------------------
# Daily Reset
# ---------------------------------------------------------------------------

class TestDailyReset:

    @pytest.mark.asyncio
    async def test_reset_clears_counters(self, scheduler, redis_client):
        await scheduler.register_account("reset_acct")

        # Advance to OBSERVATION and record some actions
        schedule = await scheduler.get_schedule("reset_acct")
        schedule.current_phase = OnboardingPhase.OBSERVATION
        schedule.max_actions_today = 5
        schedule.actions_today = 3
        schedule.action_counts_today = {"like": 2, "follow": 1}
        await redis_client.set(
            f"onboarding:account:reset_acct",
            json.dumps(schedule.to_dict()),
        )

        count = await scheduler.reset_daily_counters()
        assert count >= 1

        updated = await scheduler.get_schedule("reset_acct")
        assert updated.actions_today == 0
        assert updated.action_counts_today == {}


# ---------------------------------------------------------------------------
# Budget Query
# ---------------------------------------------------------------------------

class TestBudgetQuery:

    @pytest.mark.asyncio
    async def test_get_daily_budget(self, scheduler, redis_client):
        await scheduler.register_account("budget_query_acct")

        # Advance to LIGHT phase
        schedule = await scheduler.get_schedule("budget_query_acct")
        schedule.current_phase = OnboardingPhase.LIGHT
        schedule.max_actions_today = 15
        schedule.actions_today = 5
        schedule.action_counts_today = {"like": 3, "post": 1, "follow": 1}
        await redis_client.set(
            f"onboarding:account:budget_query_acct",
            json.dumps(schedule.to_dict()),
        )

        budget = await scheduler.get_daily_budget("budget_query_acct")

        assert budget["total_remaining"] == 10
        assert budget["total_used"] == 5
        assert budget["phase"] == "light"
        assert budget["per_type"]["post"]["used"] == 1
        assert budget["per_type"]["post"]["limit"] == 1
        assert budget["per_type"]["post"]["remaining"] == 0  # 1 post used of 1 max


# ---------------------------------------------------------------------------
# Phase Set Queries
# ---------------------------------------------------------------------------

class TestPhaseQueries:

    @pytest.mark.asyncio
    async def test_get_accounts_by_phase(self, scheduler):
        await scheduler.register_account("phase_a")
        await scheduler.register_account("phase_b")

        results = await scheduler.get_accounts_by_phase(OnboardingPhase.SETUP)
        ids = [r.account_id for r in results]
        assert "phase_a" in ids
        assert "phase_b" in ids

    @pytest.mark.asyncio
    async def test_get_all_accounts(self, scheduler):
        await scheduler.register_account("all_a")
        await scheduler.register_account("all_b")
        await scheduler.register_account("all_c")

        results = await scheduler.get_all_accounts()
        assert len(results) == 3
