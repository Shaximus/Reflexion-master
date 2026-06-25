"""
Tests for the Account Health Monitor and Alert system.

Uses local Redis DB 15 for isolation.
"""

import asyncio
import json
import pytest
import pytest_asyncio
from datetime import datetime, timedelta, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import redis.asyncio as aioredis

from services.health_monitor.health_monitor import (
    AccountHealthMonitor,
    AccountStatus,
    HealthCheck,
)
from services.health_monitor.alerts import AlertManager
from services.health_monitor.monitor_daemon import MonitorDaemon

pytestmark = pytest.mark.asyncio


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest_asyncio.fixture
async def redis_client():
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
async def monitor(redis_client):
    return AccountHealthMonitor(redis_client)


@pytest_asyncio.fixture
async def alert_manager(redis_client):
    return AlertManager(redis_client)


# ---------------------------------------------------------------------------
# Health Check Recording
# ---------------------------------------------------------------------------

class TestHealthRecording:

    @pytest.mark.asyncio
    async def test_record_and_retrieve(self, monitor):
        check = HealthCheck(
            account_id="test_soul",
            status=AccountStatus.HEALTHY,
            checked_at=datetime.now(timezone.utc),
            details={"probe": "ok"},
            response_code=200,
        )
        await monitor.record_health(check)

        retrieved = await monitor.get_current_status("test_soul")
        assert retrieved is not None
        assert retrieved.status == AccountStatus.HEALTHY
        assert retrieved.account_id == "test_soul"

    @pytest.mark.asyncio
    async def test_health_history(self, monitor):
        now = datetime.now(timezone.utc)

        for i in range(5):
            check = HealthCheck(
                account_id="history_soul",
                status=AccountStatus.HEALTHY,
                checked_at=now - timedelta(hours=i),
                details={"check_num": i},
                response_code=200,
            )
            await monitor.record_health(check)

        history = await monitor.get_health_history("history_soul", hours=24)
        assert len(history) == 5

    @pytest.mark.asyncio
    async def test_history_filtering_by_time(self, monitor):
        now = datetime.now(timezone.utc)

        # One check within range
        recent = HealthCheck(
            account_id="filter_soul",
            status=AccountStatus.HEALTHY,
            checked_at=now - timedelta(hours=1),
            details={},
            response_code=200,
        )
        await monitor.record_health(recent)

        # One check outside range (manually insert old timestamp)
        old = HealthCheck(
            account_id="filter_soul",
            status=AccountStatus.SUSPENDED,
            checked_at=now - timedelta(hours=48),
            details={},
            response_code=403,
        )
        await monitor.record_health(old)

        history = await monitor.get_health_history("filter_soul", hours=24)
        assert len(history) == 1
        assert history[0].status == AccountStatus.HEALTHY


# ---------------------------------------------------------------------------
# Response Interpretation
# ---------------------------------------------------------------------------

class TestResponseInterpretation:

    def test_200_healthy(self):
        status = AccountHealthMonitor._interpret_response(200, {"data": {"id": "123"}})
        assert status == AccountStatus.HEALTHY

    def test_429_rate_limited(self):
        status = AccountHealthMonitor._interpret_response(429, {})
        assert status == AccountStatus.RATE_LIMITED

    def test_403_suspended(self):
        status = AccountHealthMonitor._interpret_response(403, {})
        assert status == AccountStatus.SUSPENDED

    def test_401_locked(self):
        status = AccountHealthMonitor._interpret_response(401, {})
        assert status == AccountStatus.LOCKED

    def test_200_with_suspended_flag(self):
        status = AccountHealthMonitor._interpret_response(
            200, {"data": {"suspended": True}}
        )
        assert status == AccountStatus.SUSPENDED

    def test_200_with_withheld(self):
        status = AccountHealthMonitor._interpret_response(
            200, {"data": {"withheld": {"country_codes": ["US"]}}}
        )
        assert status == AccountStatus.SHADOWBANNED

    def test_500_unknown(self):
        status = AccountHealthMonitor._interpret_response(500, {})
        assert status == AccountStatus.UNKNOWN

    def test_none_code_unknown(self):
        status = AccountHealthMonitor._interpret_response(None, {})
        assert status == AccountStatus.UNKNOWN


# ---------------------------------------------------------------------------
# Account Registration
# ---------------------------------------------------------------------------

class TestAccountRegistration:

    @pytest.mark.asyncio
    async def test_register_and_list(self, monitor):
        await monitor.register_account("soul_a", "token_a")
        await monitor.register_account("soul_b", "token_b")

        accounts = await monitor.get_registered_accounts()
        assert "soul_a" in accounts
        assert "soul_b" in accounts
        assert accounts["soul_a"] == "token_a"

    @pytest.mark.asyncio
    async def test_unregister(self, monitor):
        await monitor.register_account("to_remove", "token_x")
        await monitor.unregister_account("to_remove")

        accounts = await monitor.get_registered_accounts()
        assert "to_remove" not in accounts


# ---------------------------------------------------------------------------
# Unhealthy Accounts
# ---------------------------------------------------------------------------

class TestUnhealthyAccounts:

    @pytest.mark.asyncio
    async def test_get_unhealthy(self, monitor):
        await monitor.register_account("healthy_soul", "tok1")
        await monitor.register_account("sick_soul", "tok2")

        await monitor.record_health(HealthCheck(
            account_id="healthy_soul",
            status=AccountStatus.HEALTHY,
            checked_at=datetime.now(timezone.utc),
            details={},
            response_code=200,
        ))
        await monitor.record_health(HealthCheck(
            account_id="sick_soul",
            status=AccountStatus.SUSPENDED,
            checked_at=datetime.now(timezone.utc),
            details={},
            response_code=403,
        ))

        unhealthy = await monitor.get_unhealthy_accounts()
        assert len(unhealthy) == 1
        assert unhealthy[0].account_id == "sick_soul"


# ---------------------------------------------------------------------------
# Status Summary
# ---------------------------------------------------------------------------

class TestStatusSummary:

    @pytest.mark.asyncio
    async def test_summary(self, monitor):
        await monitor.register_account("s1", "t1")
        await monitor.register_account("s2", "t2")
        await monitor.register_account("s3", "t3")

        await monitor.record_health(HealthCheck(
            "s1", AccountStatus.HEALTHY, datetime.now(timezone.utc), {}, 200
        ))
        await monitor.record_health(HealthCheck(
            "s2", AccountStatus.SUSPENDED, datetime.now(timezone.utc), {}, 403
        ))

        summary = await monitor.get_status_summary()
        assert summary["healthy"] == 1
        assert summary["suspended"] == 1
        assert summary["unchecked"] == 1
        assert summary["total"] == 3


# ---------------------------------------------------------------------------
# Alert Manager
# ---------------------------------------------------------------------------

class TestAlertManager:

    @pytest.mark.asyncio
    async def test_record_and_get_alerts(self, alert_manager):
        await alert_manager.record_alert({
            "account_id": "alert_soul",
            "old_status": "healthy",
            "new_status": "suspended",
        })

        alerts = await alert_manager.get_recent_alerts(hours=1)
        assert len(alerts) == 1
        assert alerts[0]["account_id"] == "alert_soul"

    @pytest.mark.asyncio
    async def test_status_change_publishes(self, alert_manager, redis_client):
        """Verify status change records an alert and we can retrieve it."""
        await alert_manager.record_status_change(
            account_id="pub_soul",
            old_status="healthy",
            new_status="suspended",
        )

        alerts = await alert_manager.get_recent_alerts(hours=1)
        assert len(alerts) == 1
        assert alerts[0]["new_status"] == "suspended"

    @pytest.mark.asyncio
    async def test_replacement_needed(self, alert_manager, monitor):
        # Register accounts and set statuses
        await monitor.register_account("good_soul", "tok1")
        await monitor.register_account("dead_soul", "tok2")

        await monitor.record_health(HealthCheck(
            "good_soul", AccountStatus.HEALTHY, datetime.now(timezone.utc), {}, 200
        ))
        await monitor.record_health(HealthCheck(
            "dead_soul", AccountStatus.SUSPENDED, datetime.now(timezone.utc), {}, 403
        ))

        needs_replacement = await alert_manager.get_replacement_needed()
        assert "dead_soul" in needs_replacement
        assert "good_soul" not in needs_replacement

    @pytest.mark.asyncio
    async def test_ban_rate(self, alert_manager, redis_client):
        # Register 10 accounts
        for i in range(10):
            await redis_client.hset("health:accounts", f"soul_{i}", f"tok_{i}")

        # Ban 2 of them
        await alert_manager.record_status_change("soul_0", "healthy", "suspended")
        await alert_manager.record_status_change("soul_1", "healthy", "locked")

        rate = await alert_manager.get_ban_rate(days=7)
        assert rate == 20.0  # 2/10 = 20%


# ---------------------------------------------------------------------------
# Monitor Daemon (unit test with mocked health checks)
# ---------------------------------------------------------------------------

class TestMonitorDaemon:

    @pytest.mark.asyncio
    async def test_detects_status_change(self, monitor, alert_manager):
        """Daemon should detect and publish when status changes."""
        await monitor.register_account("daemon_soul", "tok")

        # Seed initial healthy status
        await monitor.record_health(HealthCheck(
            "daemon_soul", AccountStatus.HEALTHY, datetime.now(timezone.utc), {}, 200
        ))

        daemon = MonitorDaemon(monitor, alert_manager, check_interval=1)
        daemon._last_status["daemon_soul"] = "healthy"

        # Mock check_health to return SUSPENDED
        async def mock_check(account_id, auth_token):
            check = HealthCheck(
                account_id=account_id,
                status=AccountStatus.SUSPENDED,
                checked_at=datetime.now(timezone.utc),
                details={"mocked": True},
                response_code=403,
            )
            await monitor.record_health(check)
            return check

        with patch.object(monitor, "check_health", side_effect=mock_check):
            accounts = await monitor.get_registered_accounts()
            await daemon._check_all(accounts)

        # Verify the status change was detected
        assert daemon._last_status["daemon_soul"] == "suspended"

        # Verify alert was recorded
        alerts = await alert_manager.get_recent_alerts(hours=1)
        assert len(alerts) >= 1
        assert any(a["new_status"] == "suspended" for a in alerts)
