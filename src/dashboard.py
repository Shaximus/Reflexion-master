#!/usr/bin/env python3
"""
REFLEXION SHIELD -- WAR ROOM v5.0
Comprehensive TUI dashboard for the Reflexion Twitter swarm system.

Replaces the legacy PowerShell menu with a proper Rich-based command center.
Single-file, self-contained. Requires: rich, redis, asyncio.

Usage:
    python3 src/dashboard.py              # Interactive war room
    python3 src/dashboard.py --quick-status   # Print status and exit
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import platform
import shutil
import signal
import subprocess
import sys
import time
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ---------------------------------------------------------------------------
# Rich imports
# ---------------------------------------------------------------------------
from rich.align import Align
from rich.columns import Columns
from rich.console import Console
from rich.layout import Layout
from rich.live import Live
from rich.markup import escape
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TextColumn
from rich.prompt import Confirm, IntPrompt, Prompt
from rich.rule import Rule
from rich.style import Style
from rich.table import Table
from rich.text import Text

# ---------------------------------------------------------------------------
# Redis (optional -- degrade gracefully)
# ---------------------------------------------------------------------------
try:
    import redis.asyncio as aioredis

    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

# ---------------------------------------------------------------------------
# Optional: aiohttp for HTTP health checks
# ---------------------------------------------------------------------------
try:
    import aiohttp

    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
SRC_DIR = PROJECT_ROOT / "src"
VENV_DIR = PROJECT_ROOT / "venv"

REDIS_HOST = "localhost"
REDIS_PORT = 6379
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD")

VERSION = "5.0"

# LLM env-var names
LLM_KEYS = {
    "DeepSeek": "DEEPSEEK_API_KEY",
    "Gemini": "GEMINI_API_KEY",
    "Grok": "GROK_LLM_API_KEY",
    "OpenAI": "OPENAI_API_KEY",
    "Claude": "CLAUDE_API_KEY",
}

# Service env-var names
SERVICE_KEYS = {
    "Ryan API (TweetAPI)": "TWEETAPI_KEY",
    "SMS Activate": "SMS_ACTIVATE_API_KEY",
    "5SIM": "FIVESIM_API_KEY",
    "CapSolver": "CAPSOLVER_API_KEY",
    "2Captcha": "TWOCAPTCHA_API_KEY",
}

# Onboarding phases (matches OnboardingPhase enum in onboarding_scheduler.py)
ONBOARDING_PHASES = ["SETUP", "OBSERVATION", "LIGHT", "ACTIVE", "NORMAL", "GRADUATED"]

# Health statuses
HEALTH_STATUSES = ["HEALTHY", "SUSPENDED", "SHADOWBANNED", "LOCKED", "RATE_LIMITED", "UNKNOWN"]

CLOUDFLARE_STATS_URL = "https://api.reflexionsoftware.com/rules/live-stats"

console = Console()

# ---------------------------------------------------------------------------
# Load .env if present (best-effort)
# ---------------------------------------------------------------------------
try:
    from dotenv import load_dotenv

    env_path = PROJECT_ROOT / ".env"
    if env_path.exists():
        load_dotenv(env_path)
    else:
        load_dotenv()
except ImportError:
    pass  # dotenv not required


# ===========================================================================
# REDIS HELPERS
# ===========================================================================

async def get_redis() -> Optional[aioredis.Redis]:
    """Return a connected async Redis client or None."""
    if not REDIS_AVAILABLE:
        return None
    try:
        r = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD,
            decode_responses=True,
            socket_connect_timeout=3,
        )
        await r.ping()
        return r
    except (ConnectionError, OSError, TimeoutError, Exception) as e:
        if "NOAUTH" in str(e) or "Authentication" in str(e):
            console.print("[yellow]WARNING: Redis auth failed — check REDIS_PASSWORD env var[/]")
        return None


async def redis_ping() -> bool:
    r = await get_redis()
    if r:
        await r.close()
        return True
    return False


async def redis_scan_keys(pattern: str) -> List[str]:
    """Scan Redis for keys matching *pattern*."""
    r = await get_redis()
    if not r:
        return []
    try:
        keys: List[str] = []
        async for key in r.scan_iter(match=pattern, count=200):
            keys.append(key)
        return keys
    except (ConnectionError, OSError, TimeoutError):
        return []
    finally:
        await r.close()


async def redis_get_json(key: str) -> Optional[dict]:
    r = await get_redis()
    if not r:
        return None
    try:
        raw = await r.get(key)
        if raw:
            return json.loads(raw)
    except (ConnectionError, OSError, json.JSONDecodeError):
        pass
    finally:
        await r.close()
    return None


async def redis_hgetall(key: str) -> Dict[str, str]:
    r = await get_redis()
    if not r:
        return {}
    try:
        return await r.hgetall(key)
    except (ConnectionError, OSError, TimeoutError):
        return {}
    finally:
        await r.close()


# ===========================================================================
# BANNER
# ===========================================================================

def render_banner() -> Panel:
    banner_text = Text(justify="center")
    banner_text.append("REFLEXION SHIELD", style="bold bright_red")
    banner_text.append(" -- ", style="dim")
    banner_text.append("WAR ROOM v{}\n".format(VERSION), style="bold bright_white")
    banner_text.append("30-50 Souls  |  5 LLM Cascade  |  Adversarial ML\n", style="cyan")
    banner_text.append(datetime.now().strftime("%Y-%m-%d %H:%M:%S"), style="dim white")
    return Panel(
        Align.center(banner_text),
        border_style="bright_red",
        padding=(1, 2),
    )


# ===========================================================================
# MAIN MENU
# ===========================================================================

def render_menu() -> Panel:
    menu = Table.grid(padding=(0, 3))
    menu.add_column(style="bold bright_white", width=6)
    menu.add_column(style="bright_white", min_width=22)
    menu.add_column(style="dim white")

    # Section: OPERATIONS
    menu.add_row("", Text("OPERATIONS", style="bold yellow underline"), "")
    menu.add_row("[1]", "NORMAL MODE", "1-2 tweets/hour per soul")
    menu.add_row("[2]", "STEALTH MODE", "Slow cycles, low profile")
    menu.add_row("[3]", "BURST MODE", "Rapid posting (monitor limits!)")
    menu.add_row("[4]", "TEST MODE", "Single post per soul")
    menu.add_row()

    # Section: CAMPAIGN
    menu.add_row("", Text("CAMPAIGN", style="bold magenta underline"), "")
    menu.add_row("[5]", "BLASTER DEPLOY", "Create & fire disposable accounts")
    menu.add_row("[6]", "SLEEPER ACTIVATE", "Wake graduated sleeper accounts")
    menu.add_row("[7]", "CONVERGENCE", "All souls target one account")
    menu.add_row("[8]", "ENGAGEMENT ONLY", "Likes/replies, no new posts")
    menu.add_row()

    # Section: PIPELINE
    menu.add_row("", Text("PIPELINE", style="bold green underline"), "")
    menu.add_row("[9]", "CREATE ACCOUNTS", "Batch account creation")
    menu.add_row("[10]", "ACCOUNT INVENTORY", "View all accounts by status")
    menu.add_row("[11]", "WARM SLEEPERS", "Start onboarding daemon")
    menu.add_row()

    # Section: INTELLIGENCE
    menu.add_row("", Text("INTELLIGENCE", style="bold cyan underline"), "")
    menu.add_row("[12]", "SYSTEM STATUS", "Full infrastructure check")
    menu.add_row("[13]", "LIVE MONITOR", "Real-time activity dashboard")
    menu.add_row("[14]", "BAN ANALYTICS", "Ban rates, patterns, BotRGCN status")
    menu.add_row("[15]", "API & COSTS", "Usage stats, LLM costs, budget")
    menu.add_row()

    menu.add_row("[Q]", Text("EXIT", style="bold red"), "")

    return Panel(
        menu,
        title="[bold bright_white]COMMAND CENTER[/]",
        border_style="bright_cyan",
        padding=(1, 2),
    )


# ===========================================================================
# OPTION 12 -- SYSTEM STATUS
# ===========================================================================

async def check_system_status(quick: bool = False) -> Panel:
    """Full infrastructure check."""
    table = Table(
        title="System Status" if not quick else None,
        show_header=True,
        header_style="bold bright_white",
        border_style="cyan",
        expand=True,
    )
    table.add_column("Component", style="bright_white", min_width=28)
    table.add_column("Status", justify="center", min_width=14)
    table.add_column("Details", style="dim")

    def ok(msg: str = "OK") -> Text:
        return Text(msg, style="bold green")

    def warn(msg: str = "WARNING") -> Text:
        return Text(msg, style="bold yellow")

    def fail(msg: str = "MISSING") -> Text:
        return Text(msg, style="bold red")

    def info(msg: str) -> Text:
        return Text(msg, style="cyan")

    # 1. Python version
    py_ver = platform.python_version()
    py_status = ok() if tuple(int(x) for x in py_ver.split(".")[:2]) >= (3, 10) else warn("OLD")
    table.add_row("Python", py_status, py_ver)

    # 2. Redis
    redis_ok = await redis_ping()
    table.add_row(
        "Redis",
        ok("CONNECTED") if redis_ok else fail("DISCONNECTED"),
        "{}:{}".format(REDIS_HOST, REDIS_PORT) if redis_ok else "Cannot connect",
    )

    # 3. LLM API keys
    for name, env_var in LLM_KEYS.items():
        val = os.getenv(env_var, "")
        if val:
            masked = val[:4] + "..." + val[-4:] if len(val) > 10 else "****"
            table.add_row("LLM: {}".format(name), ok("CONFIGURED"), masked)
        else:
            table.add_row("LLM: {}".format(name), fail("MISSING"), "${} not set".format(env_var))

    # 4. Service keys
    for name, env_var in SERVICE_KEYS.items():
        val = os.getenv(env_var, "")
        if val:
            masked = val[:4] + "..." + val[-4:] if len(val) > 10 else "****"
            table.add_row(name, ok("CONFIGURED"), masked)
        else:
            table.add_row(name, warn("MISSING"), "${} not set".format(env_var))

    # 5. Cloudflare Workers
    cf_status_text = "UNKNOWN"
    cf_detail = ""
    if AIOHTTP_AVAILABLE:
        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(CLOUDFLARE_STATS_URL, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                    if resp.status == 200:
                        cf_status_text = "ONLINE"
                        cf_detail = "HTTP {}".format(resp.status)
                    else:
                        cf_status_text = "ERROR"
                        cf_detail = "HTTP {}".format(resp.status)
        except (aiohttp.ClientError, asyncio.TimeoutError, OSError) as e:
            cf_status_text = "OFFLINE"
            cf_detail = str(e)[:50]
    else:
        cf_detail = "aiohttp not installed"

    cf_style = ok("ONLINE") if cf_status_text == "ONLINE" else (
        warn(cf_status_text) if cf_status_text in ("UNKNOWN", "ERROR") else fail("OFFLINE")
    )
    table.add_row("Cloudflare Workers", cf_style, cf_detail)

    # 6. Proxy count
    proxy_count = 0
    proxy_file = PROJECT_ROOT / "proxies.txt"
    if proxy_file.exists():
        with open(proxy_file) as f:
            proxy_count = sum(1 for line in f if line.strip() and not line.startswith("#"))
    proxy_env = os.getenv("PROXY_LIST", "")
    if proxy_env:
        proxy_count += len([p for p in proxy_env.split(",") if p.strip()])
    table.add_row(
        "Proxies",
        ok(str(proxy_count)) if proxy_count > 0 else warn("NONE"),
        "proxies.txt + $PROXY_LIST" if proxy_count else "No proxies configured",
    )

    # 7. Playwright
    pw_installed = shutil.which("playwright") is not None
    table.add_row(
        "Playwright",
        ok("INSTALLED") if pw_installed else warn("NOT FOUND"),
        "Browser automation ready" if pw_installed else "pip install playwright && playwright install",
    )

    # 8. Service daemons (check Redis keys)
    if redis_ok:
        onboarding_keys = await redis_scan_keys("onboarding:daemon:*")
        health_keys = await redis_scan_keys("health:daemon:*")
        table.add_row(
            "Onboarding Daemon",
            ok("RUNNING") if onboarding_keys else warn("STOPPED"),
            "{} key(s)".format(len(onboarding_keys)) if onboarding_keys else "No daemon heartbeat",
        )
        table.add_row(
            "Health Daemon",
            ok("RUNNING") if health_keys else warn("STOPPED"),
            "{} key(s)".format(len(health_keys)) if health_keys else "No daemon heartbeat",
        )
    else:
        table.add_row("Onboarding Daemon", info("N/A"), "Redis offline")
        table.add_row("Health Daemon", info("N/A"), "Redis offline")

    # 9. .env file
    env_exists = (PROJECT_ROOT / ".env").exists()
    table.add_row(
        ".env File",
        ok("FOUND") if env_exists else warn("MISSING"),
        str(PROJECT_ROOT / ".env") if env_exists else "No .env in project root",
    )

    return Panel(table, border_style="cyan", title="[bold cyan]INFRASTRUCTURE STATUS[/]")


# ===========================================================================
# OPTION 10 -- ACCOUNT INVENTORY
# ===========================================================================

async def show_account_inventory() -> Panel:
    """Display account inventory from Redis and local JSON files."""

    # -- Phase distribution --
    phase_table = Table(title="By Onboarding Phase", border_style="green", expand=True)
    phase_table.add_column("Phase", style="bright_white", min_width=14)
    phase_table.add_column("Count", justify="right", style="bold")
    phase_table.add_column("Bar", min_width=20)

    phase_counts: Dict[str, int] = {p: 0 for p in ONBOARDING_PHASES}
    total_accounts = 0

    r = await get_redis()
    if r:
        try:
            account_keys = []
            async for key in r.scan_iter(match="onboarding:account:*", count=500):
                account_keys.append(key)

            for key in account_keys:
                try:
                    raw = await r.get(key)
                    if raw:
                        data = json.loads(raw)
                        phase = data.get("current_phase", "UNKNOWN").upper()
                        if phase in phase_counts:
                            phase_counts[phase] += 1
                        total_accounts += 1
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            await r.close()

    # Check local account JSON files
    accounts_dir = PROJECT_ROOT / "data" / "souls"
    if accounts_dir.exists():
        for fp in accounts_dir.glob("*.json"):
            try:
                with open(fp) as f:
                    data = json.load(f)
                if isinstance(data, dict):
                    total_accounts += 1
                elif isinstance(data, list):
                    total_accounts += len(data)
            except Exception:
                continue

    max_phase = max(phase_counts.values()) if phase_counts.values() else 1
    phase_colors = {
        "SETUP": "dim white",
        "OBSERVATION": "blue",
        "LIGHT": "cyan",
        "ACTIVE": "yellow",
        "NORMAL": "green",
        "GRADUATED": "bold bright_green",
    }
    for phase, count in phase_counts.items():
        bar_len = int((count / max(max_phase, 1)) * 20) if count > 0 else 0
        bar = Text("█" * bar_len + "░" * (20 - bar_len), style=phase_colors.get(phase, "white"))
        phase_table.add_row(phase, str(count), bar)

    # -- Health distribution --
    health_table = Table(title="By Health Status", border_style="green", expand=True)
    health_table.add_column("Status", style="bright_white", min_width=14)
    health_table.add_column("Count", justify="right", style="bold")
    health_table.add_column("Indicator", min_width=10)

    health_counts: Dict[str, int] = {s: 0 for s in HEALTH_STATUSES}

    r = await get_redis()
    if r:
        try:
            async for key in r.scan_iter(match="health:status:*", count=500):
                try:
                    raw = await r.get(key)
                    if raw:
                        data = json.loads(raw)
                        status = data.get("status", "unknown").upper()
                        if status in health_counts:
                            health_counts[status] += 1
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            await r.close()

    health_styles = {
        "HEALTHY": ("bold green", "LIVE"),
        "SUSPENDED": ("bold red", "DEAD"),
        "SHADOWBANNED": ("bold yellow", "SHAD"),
        "LOCKED": ("bold red", "LOCK"),
        "RATE_LIMITED": ("yellow", "RATE"),
        "UNKNOWN": ("dim", "  ? "),
    }
    for status, count in health_counts.items():
        style, icon = health_styles.get(status, ("white", "?"))
        health_table.add_row(status, str(count), Text(icon, style=style))

    # -- Tier distribution --
    tier_table = Table(title="By Tier", border_style="green", expand=True)
    tier_table.add_column("Tier", style="bright_white", min_width=12)
    tier_table.add_column("Count", justify="right", style="bold")

    tier_counts: Dict[str, int] = {"BLASTER": 0, "SLEEPER": 0, "UNKNOWN": 0}
    r = await get_redis()
    if r:
        try:
            async for key in r.scan_iter(match="onboarding:account:*", count=500):
                try:
                    raw = await r.get(key)
                    if raw:
                        data = json.loads(raw)
                        tier = data.get("tier", "unknown").upper()
                        if tier in tier_counts:
                            tier_counts[tier] += 1
                        else:
                            tier_counts["UNKNOWN"] += 1
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            await r.close()

    for tier, count in tier_counts.items():
        tier_table.add_row(tier, str(count))

    # Summary
    summary = Text(justify="center")
    summary.append("\nTotal Accounts Tracked: ", style="bright_white")
    summary.append(str(total_accounts) + "\n", style="bold bright_green")

    # Compose everything
    grid = Table.grid(expand=True, padding=1)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_column(ratio=1)
    grid.add_row(phase_table, health_table, tier_table)

    outer = Table.grid(expand=True)
    outer.add_row(grid)
    outer.add_row(Align.center(summary))

    return Panel(outer, border_style="green", title="[bold green]ACCOUNT INVENTORY[/]")


# ===========================================================================
# OPTION 13 -- LIVE MONITOR
# ===========================================================================

async def live_monitor():
    """Real-time activity dashboard with auto-refresh."""
    console.print(
        "\n[bold cyan]LIVE MONITOR[/] -- Press [bold]Ctrl+C[/] to return to menu\n",
        style="cyan",
    )

    r = await get_redis()
    if not r:
        console.print("[bold red]Redis is not available. Cannot start live monitor.[/]")
        Prompt.ask("\nPress Enter to return")
        return

    activity_log: List[Tuple[str, str, str]] = []  # (timestamp, type, message)
    stats = {"posts": 0, "engagements": 0, "bans": 0, "transitions": 0, "active": 0}

    def build_display() -> Table:
        layout_table = Table.grid(expand=True, padding=1)
        layout_table.add_column(ratio=2)
        layout_table.add_column(ratio=1)

        # Left: activity log
        log_table = Table(
            title="Recent Activity",
            border_style="cyan",
            expand=True,
            show_lines=False,
        )
        log_table.add_column("Time", style="dim", width=10)
        log_table.add_column("Type", width=12)
        log_table.add_column("Details", ratio=1)

        for ts, evt_type, msg in activity_log[-20:]:
            type_style = "green"
            if "ban" in evt_type.lower() or "suspend" in evt_type.lower():
                type_style = "bold red"
            elif "transition" in evt_type.lower() or "phase" in evt_type.lower():
                type_style = "bold yellow"
            elif "engage" in evt_type.lower():
                type_style = "cyan"
            elif "error" in evt_type.lower():
                type_style = "red"
            log_table.add_row(ts, Text(evt_type, style=type_style), msg)

        if not activity_log:
            log_table.add_row("--", "WAITING", "No activity yet...")

        # Right: stats
        stats_table = Table(
            title="Metrics",
            border_style="bright_white",
            expand=True,
        )
        stats_table.add_column("Metric", style="bright_white")
        stats_table.add_column("Value", justify="right", style="bold")

        stats_table.add_row("Active Accounts", Text(str(stats["active"]), style="green"))
        stats_table.add_row("Posts/Hour", Text(str(stats["posts"]), style="cyan"))
        stats_table.add_row("Engagements", Text(str(stats["engagements"]), style="cyan"))
        stats_table.add_row(
            "Ban Events",
            Text(str(stats["bans"]), style="bold red" if stats["bans"] else "green"),
        )
        stats_table.add_row("Phase Transitions", Text(str(stats["transitions"]), style="yellow"))
        stats_table.add_row("", "")
        stats_table.add_row("Last Refresh", Text(datetime.now().strftime("%H:%M:%S"), style="dim"))

        layout_table.add_row(log_table, stats_table)
        return layout_table

    async def poll_activity():
        """Pull activity from Redis streams/lists/pubsub."""
        nonlocal activity_log, stats

        try:
            # Check for recent activity in common Redis keys
            activity_keys = []
            async for key in r.scan_iter(match="activity:*", count=100):
                activity_keys.append(key)
            async for key in r.scan_iter(match="swarm:activity:*", count=100):
                activity_keys.append(key)

            for key in activity_keys[-20:]:
                try:
                    raw = await r.get(key)
                    if raw:
                        data = json.loads(raw) if raw.startswith("{") else {"msg": raw}
                        ts = data.get("timestamp", datetime.now().strftime("%H:%M:%S"))
                        evt = data.get("type", data.get("event", "INFO"))
                        msg = data.get("message", data.get("msg", str(data)))
                        entry = (str(ts)[-8:], str(evt).upper()[:12], str(msg)[:80])
                        if entry not in activity_log:
                            activity_log.append(entry)
                except Exception:
                    continue

            # Count active accounts
            active_count = 0
            async for _ in r.scan_iter(match="health:status:*", count=500):
                active_count += 1
            stats["active"] = active_count

            # Count recent posts (last hour)
            post_keys = []
            async for key in r.scan_iter(match="post:*", count=500):
                post_keys.append(key)
            async for key in r.scan_iter(match="swarm:post:*", count=500):
                post_keys.append(key)
            stats["posts"] = len(post_keys)

            # Count ban events
            ban_keys = []
            async for key in r.scan_iter(match="ban:*", count=500):
                ban_keys.append(key)
            async for key in r.scan_iter(match="health:ban:*", count=500):
                ban_keys.append(key)
            stats["bans"] = len(ban_keys)

        except Exception:
            activity_log.append(
                (datetime.now().strftime("%H:%M:%S"), "ERROR", "Failed to poll Redis")
            )

        # Cap log
        activity_log = activity_log[-50:]

    try:
        with Live(build_display(), console=console, refresh_per_second=0.5, screen=False) as live:
            while True:
                await poll_activity()
                live.update(
                    Panel(
                        build_display(),
                        title="[bold cyan]LIVE MONITOR[/] [dim](Ctrl+C to exit)[/]",
                        border_style="cyan",
                    )
                )
                await asyncio.sleep(5)
    except (KeyboardInterrupt, asyncio.CancelledError):
        pass
    finally:
        await r.close()
        console.print("\n[dim]Monitor stopped.[/]")


# ===========================================================================
# OPTION 14 -- BAN ANALYTICS
# ===========================================================================

async def show_ban_analytics() -> Panel:
    """Ban rates, patterns, and BotRGCN status."""
    table = Table(
        show_header=True,
        header_style="bold bright_white",
        border_style="red",
        expand=True,
    )
    table.add_column("Metric", style="bright_white", min_width=30)
    table.add_column("Value", justify="right", style="bold", min_width=20)

    total_bans = 0
    bans_24h = 0
    bans_7d = 0
    bans_30d = 0
    lifespans: List[float] = []

    r = await get_redis()
    if r:
        try:
            now = datetime.now(timezone.utc)
            async for key in r.scan_iter(match="ban:*", count=1000):
                try:
                    raw = await r.get(key)
                    if raw:
                        data = json.loads(raw)
                        total_bans += 1
                        ban_ts = data.get("banned_at", data.get("timestamp", ""))
                        created_ts = data.get("created_at", "")
                        if ban_ts:
                            try:
                                ban_dt = datetime.fromisoformat(ban_ts.replace("Z", "+00:00"))
                                delta = now - ban_dt
                                if delta.days < 1:
                                    bans_24h += 1
                                if delta.days < 7:
                                    bans_7d += 1
                                if delta.days < 30:
                                    bans_30d += 1
                                if created_ts:
                                    created_dt = datetime.fromisoformat(
                                        created_ts.replace("Z", "+00:00")
                                    )
                                    lifespans.append(
                                        (ban_dt - created_dt).total_seconds() / 86400
                                    )
                            except Exception:
                                pass
                except Exception:
                    continue

            # Also check health:ban:* keys
            async for key in r.scan_iter(match="health:ban:*", count=1000):
                try:
                    raw = await r.get(key)
                    if raw:
                        total_bans += 1
                except Exception:
                    continue
        except Exception:
            pass
        finally:
            await r.close()

    table.add_row("Total Bans (All Time)", str(total_bans))
    table.add_row(
        "Bans (Last 24h)",
        Text(str(bans_24h), style="bold red" if bans_24h > 0 else "green"),
    )
    table.add_row(
        "Bans (Last 7d)",
        Text(str(bans_7d), style="yellow" if bans_7d > 0 else "green"),
    )
    table.add_row("Bans (Last 30d)", str(bans_30d))

    if lifespans:
        avg_lifespan = sum(lifespans) / len(lifespans)
        table.add_row("Avg Account Lifespan", "{:.1f} days".format(avg_lifespan))
    else:
        table.add_row("Avg Account Lifespan", "No data")

    table.add_row("", "")
    table.add_row(
        Text("BotRGCN Model", style="bold bright_white"),
        Text("", style="dim"),
    )

    # BotRGCN status
    botrgcn_spec = await redis_get_json("botrgcn:sleeper_spec:latest")
    botrgcn_model = await redis_get_json("botrgcn:model:status")

    if botrgcn_model:
        trained = botrgcn_model.get("trained", False)
        last_train = botrgcn_model.get("last_trained", "N/A")
        table.add_row(
            "  Model Status",
            Text("TRAINED" if trained else "UNTRAINED", style="green" if trained else "yellow"),
        )
        table.add_row("  Last Training", str(last_train))
    else:
        table.add_row("  Model Status", Text("NO DATA", style="dim"))
        table.add_row("  Last Training", "N/A")

    if botrgcn_spec:
        table.add_row("  Sleeper Spec", Text("ACTIVE", style="green"))
        for k, v in list(botrgcn_spec.items())[:5]:
            table.add_row("    {}".format(k), str(v))
    else:
        table.add_row("  Sleeper Spec", Text("NOT SET", style="dim"))

    # Replacement queue
    r = await get_redis()
    queue_depth = 0
    if r:
        try:
            queue_depth = await r.llen("replacement:queue") or 0
        except Exception:
            pass
        finally:
            await r.close()
    table.add_row("", "")
    table.add_row("Replacement Queue Depth", str(queue_depth))

    return Panel(table, border_style="red", title="[bold red]BAN ANALYTICS[/]")


# ===========================================================================
# OPTION 15 -- API & COSTS
# ===========================================================================

async def show_api_costs() -> Panel:
    """API usage stats and LLM costs."""
    table = Table(
        show_header=True,
        header_style="bold bright_white",
        border_style="magenta",
        expand=True,
    )
    table.add_column("Category", style="bright_white", min_width=24)
    table.add_column("Value", justify="right", min_width=18)

    # Ryan API stats
    table.add_row(
        Text("RYAN API (TweetAPI)", style="bold yellow underline"),
        "",
    )

    ryan_stats = await redis_get_json("ryan:api:stats")
    if ryan_stats:
        table.add_row("  Requests Today", str(ryan_stats.get("requests_today", 0)))
        table.add_row("  Requests This Month", str(ryan_stats.get("requests_month", 0)))
        rl = ryan_stats.get("rate_limit_remaining", "N/A")
        table.add_row("  Rate Limit Remaining", str(rl))
    else:
        # Try reading from local file
        stats_file = PROJECT_ROOT / "engagement" / "soul_api_usage.json"
        if stats_file.exists():
            try:
                with open(stats_file) as f:
                    usage = json.load(f)
                total_reads = sum(
                    d.get("reads_used", 0) for d in usage.values() if isinstance(d, dict)
                )
                total_writes = sum(
                    d.get("writes_used", 0) for d in usage.values() if isinstance(d, dict)
                )
                table.add_row("  Total Reads", str(total_reads))
                table.add_row("  Total Writes", str(total_writes))
            except Exception:
                table.add_row("  Stats", Text("Error reading file", style="red"))
        else:
            table.add_row("  Stats", Text("No data", style="dim"))

    table.add_row("", "")
    table.add_row(
        Text("LLM COSTS BY PROVIDER", style="bold yellow underline"),
        "",
    )

    # LLM costs from Redis
    llm_cost_data = await redis_get_json("llm:costs:session")
    total_spend = 0.0
    if llm_cost_data:
        for provider, data in llm_cost_data.items():
            calls = data.get("calls", 0)
            cost = data.get("total_cost", 0.0)
            total_spend += cost
            table.add_row(
                "  {}".format(provider),
                "{} calls / ${:.4f}".format(calls, cost),
            )
    else:
        # Fallback: check if CostOptimizedBroadcaster has session costs
        table.add_row("  DeepSeek", Text("No tracking data", style="dim"))
        table.add_row("  Gemini", Text("No tracking data", style="dim"))
        table.add_row("  Grok", Text("No tracking data", style="dim"))
        table.add_row("  OpenAI", Text("No tracking data", style="dim"))
        table.add_row("  Claude", Text("No tracking data", style="dim"))

    table.add_row("", "")
    table.add_row(
        Text("COST SUMMARY", style="bold yellow underline"),
        "",
    )

    # Costs by period
    cost_today = await redis_get_json("costs:today")
    cost_week = await redis_get_json("costs:week")
    cost_month = await redis_get_json("costs:month")

    table.add_row(
        "  Total Spend Today",
        "${:.4f}".format(cost_today.get("total", 0.0)) if cost_today else "$0.0000",
    )
    table.add_row(
        "  Total Spend This Week",
        "${:.4f}".format(cost_week.get("total", 0.0)) if cost_week else "$0.0000",
    )
    table.add_row(
        "  Total Spend This Month",
        "${:.4f}".format(cost_month.get("total", 0.0)) if cost_month else "$0.0000",
    )

    # CPE
    engagements = 0
    r = await get_redis()
    if r:
        try:
            async for _ in r.scan_iter(match="engagement:*", count=1000):
                engagements += 1
        except Exception:
            pass
        finally:
            await r.close()

    if engagements > 0 and total_spend > 0:
        cpe = total_spend / engagements
        table.add_row("  Cost Per Engagement (CPE)", "${:.6f}".format(cpe))
    else:
        table.add_row("  Cost Per Engagement (CPE)", Text("N/A", style="dim"))

    return Panel(table, border_style="magenta", title="[bold magenta]API & COSTS[/]")


# ===========================================================================
# OPERATION LAUNCHERS (Options 1-4)
# ===========================================================================

async def launch_mode(mode: str):
    """Launch the swarm in the specified mode."""
    mode_map = {
        "normal": ("--normal", "NORMAL MODE", "green", "1-2 hours between cycles"),
        "stealth": ("--stealth", "STEALTH MODE", "blue", "30-60 minute cycles"),
        "burst": ("--burst", "BURST MODE", "red", "10-20 minute cycles -- MONITOR LIMITS"),
        "test": ("--test", "TEST MODE", "yellow", "Single post per soul"),
    }

    flag, title, color, desc = mode_map[mode]

    rule = "=" * 60
    console.print("\n[bold {}]{}[/]".format(color, rule))
    console.print("[bold {}]  {}[/]".format(color, title))
    console.print("[bold {}]  {}[/]".format(color, desc))
    console.print("[bold {}]{}[/]\n".format(color, rule))

    if not Confirm.ask("Launch {}?".format(title), default=True):
        return

    console.print("[dim]Starting in 3 seconds... Ctrl+C to cancel[/]")
    await asyncio.sleep(3)

    launch_script = PROJECT_ROOT / "launch.py"
    if not launch_script.exists():
        console.print("[bold red]launch.py not found at {}[/]".format(launch_script))
        return

    console.print("[bold green]Launching: python3 {} {}[/]\n".format(launch_script, flag))
    try:
        proc = await asyncio.create_subprocess_exec(
            sys.executable,
            str(launch_script),
            flag,
            cwd=str(PROJECT_ROOT),
            stdout=None,  # inherit
            stderr=None,  # inherit
        )
        await proc.wait()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation interrupted.[/]")
    except Exception as e:
        console.print("[bold red]Launch error: {}[/]".format(e))

    Prompt.ask("\nPress Enter to return to menu")


# ===========================================================================
# CAMPAIGN CONTROLS (Options 5-8)
# ===========================================================================

async def blaster_deploy():
    """Option 5: Create & fire disposable blaster accounts."""
    console.print(
        Panel(
            "[bold magenta]BLASTER DEPLOY[/]\n\n"
            "Creates disposable accounts and immediately begins posting.\n"
            "These accounts are expected to be burned quickly.\n"
            "Use for high-impact, short-duration campaigns.",
            border_style="magenta",
        )
    )

    count = IntPrompt.ask("How many blaster accounts?", default=3)
    if not Confirm.ask("Deploy {} blaster accounts?".format(count), default=False):
        console.print("[dim]Cancelled.[/]")
        return

    console.print("[bold magenta]Deploying {} blasters...[/]".format(count))

    pipeline_script = SRC_DIR / "services" / "account_pipeline" / "orchestrator.py"
    if pipeline_script.exists():
        bootstrap = (
            "import sys; "
            "sys.path.insert(0, '{}'); "
            "sys.path.insert(0, '{}'); "
            "import asyncio; "
            "from account_pipeline.orchestrator import AccountPipelineOrchestrator; "
            "o = AccountPipelineOrchestrator(); "
            "asyncio.run(o.create_accounts({}, tier='blaster'))"
        ).format(SRC_DIR, SRC_DIR / "services", count)
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                bootstrap,
                cwd=str(PROJECT_ROOT),
                stdout=None,
                stderr=None,
            )
            await proc.wait()
        except Exception as e:
            console.print("[red]Pipeline error: {}[/]".format(e))
    else:
        console.print("[yellow]Account pipeline not found at {}[/]".format(pipeline_script))
        console.print("[dim]Blaster deploy requires the account_pipeline service.[/]")

    Prompt.ask("\nPress Enter to return to menu")


async def sleeper_activate():
    """Option 6: Wake graduated sleeper accounts."""
    console.print(
        Panel(
            "[bold magenta]SLEEPER ACTIVATE[/]\n\n"
            "Transitions graduated (fully onboarded) accounts to campaign mode.\n"
            "These are aged, high-trust accounts ready for deployment.",
            border_style="magenta",
        )
    )

    r = await get_redis()
    graduated_count = 0
    if r:
        try:
            async for key in r.scan_iter(match="onboarding:account:*", count=500):
                raw = await r.get(key)
                if raw:
                    data = json.loads(raw)
                    if data.get("current_phase", "").upper() == "GRADUATED":
                        graduated_count += 1
        except Exception:
            pass
        finally:
            await r.close()

    console.print("[cyan]Found {} graduated sleeper accounts.[/]".format(graduated_count))

    if graduated_count == 0:
        console.print("[yellow]No graduated accounts available to activate.[/]")
        Prompt.ask("\nPress Enter to return to menu")
        return

    if not Confirm.ask(
        "Activate {} sleepers?".format(graduated_count), default=True
    ):
        console.print("[dim]Cancelled.[/]")
        return

    console.print("[bold magenta]Activating {} sleepers...[/]".format(graduated_count))

    r = await get_redis()
    if r:
        try:
            activated = 0
            async for key in r.scan_iter(match="onboarding:account:*", count=500):
                raw = await r.get(key)
                if raw:
                    data = json.loads(raw)
                    if data.get("current_phase", "").upper() == "GRADUATED":
                        data["campaign_active"] = True
                        data["activated_at"] = datetime.now(timezone.utc).isoformat()
                        await r.set(key, json.dumps(data))
                        activated += 1
            console.print("[bold green]Activated {} sleeper accounts.[/]".format(activated))
        except Exception as e:
            console.print("[red]Activation error: {}[/]".format(e))
        finally:
            await r.close()

    Prompt.ask("\nPress Enter to return to menu")


async def convergence_mode():
    """Option 7: All souls converge on one target."""
    console.print(
        Panel(
            "[bold red]CONVERGENCE MODE[/]\n\n"
            "All souls target a single account simultaneously.\n"
            "Coordinated engagement: replies, likes, quote tweets.\n"
            "[bold yellow]USE WITH CAUTION.[/]",
            border_style="red",
        )
    )

    target = Prompt.ask("Enter target handle (without @)")
    if not target:
        console.print("[dim]Cancelled.[/]")
        return

    target = target.lstrip("@")
    console.print("\n[bold red]TARGET: @{}[/]".format(target))
    console.print("[yellow]Duration: ~30 minutes[/]")
    console.print("[yellow]All souls will engage.[/]\n")

    if not Confirm.ask(
        "Confirm convergence on @{}?".format(target), default=False
    ):
        console.print("[dim]Cancelled.[/]")
        return

    launch_script = PROJECT_ROOT / "launch.py"
    if launch_script.exists():
        console.print("[bold red]Launching convergence on @{}...[/]\n".format(target))
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(launch_script),
                "--converge",
                target,
                cwd=str(PROJECT_ROOT),
                stdout=None,
                stderr=None,
            )
            await proc.wait()
        except KeyboardInterrupt:
            console.print("\n[yellow]Convergence cancelled.[/]")
        except Exception as e:
            console.print("[red]Convergence error: {}[/]".format(e))
    else:
        console.print("[red]launch.py not found at {}[/]".format(launch_script))

    Prompt.ask("\nPress Enter to return to menu")


async def engagement_only():
    """Option 8: Engagement only mode (likes/replies, no new posts)."""
    console.print(
        Panel(
            "[bold cyan]ENGAGEMENT ONLY[/]\n\n"
            "Runs likes, replies, and retweets without creating new posts.\n"
            "Safe mode for maintaining account activity.",
            border_style="cyan",
        )
    )

    if not Confirm.ask("Start engagement-only mode?", default=True):
        return

    launch_script = PROJECT_ROOT / "launch.py"
    if launch_script.exists():
        console.print("[bold cyan]Launching engagement-only mode...[/]\n")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(launch_script),
                "--engage-only",
                cwd=str(PROJECT_ROOT),
                stdout=None,
                stderr=None,
            )
            await proc.wait()
        except KeyboardInterrupt:
            console.print("\n[yellow]Engagement mode stopped.[/]")
        except Exception as e:
            console.print("[red]Error: {}[/]".format(e))
    else:
        console.print("[red]launch.py not found at {}[/]".format(launch_script))

    Prompt.ask("\nPress Enter to return to menu")


# ===========================================================================
# PIPELINE CONTROLS (Options 9, 11)
# ===========================================================================

async def create_accounts():
    """Option 9: Batch account creation."""
    console.print(
        Panel(
            "[bold green]ACCOUNT CREATION PIPELINE[/]\n\n"
            "Creates new Twitter/X accounts through the automated pipeline.\n"
            "Uses browser stealth, SMS verification, and CAPTCHA solving.",
            border_style="green",
        )
    )

    count = IntPrompt.ask("How many accounts?", default=5)

    tier_choice = Prompt.ask(
        "Tier",
        choices=["blaster", "sleeper", "both"],
        default="sleeper",
    )

    # Proxy info
    proxy_count = 0
    proxy_file = PROJECT_ROOT / "proxies.txt"
    if proxy_file.exists():
        with open(proxy_file) as f:
            proxy_count = sum(1 for line in f if line.strip() and not line.startswith("#"))
    proxy_env = os.getenv("PROXY_LIST", "")
    if proxy_env:
        proxy_count += len([p for p in proxy_env.split(",") if p.strip()])

    use_proxies = False
    if proxy_count > 0:
        console.print("[cyan]Available proxies: {}[/]".format(proxy_count))
        use_proxies = Confirm.ask("Use proxies?", default=True)
    else:
        console.print("[yellow]No proxies configured.[/]")

    console.print("\n[bright_white]Summary:[/]")
    console.print("  Accounts: {}".format(count))
    console.print("  Tier: {}".format(tier_choice))
    console.print("  Proxies: {}".format("Yes" if use_proxies else "No"))

    if not Confirm.ask("\nProceed with account creation?", default=True):
        console.print("[dim]Cancelled.[/]")
        return

    pipeline_script = SRC_DIR / "services" / "account_pipeline" / "orchestrator.py"
    if pipeline_script.exists():
        console.print(
            "\n[bold green]Starting pipeline for {} accounts...[/]\n".format(count)
        )
        bootstrap = (
            "import sys; "
            "sys.path.insert(0, '{}'); "
            "sys.path.insert(0, '{}'); "
            "import asyncio; "
            "from account_pipeline.orchestrator import AccountPipelineOrchestrator; "
            "o = AccountPipelineOrchestrator(); "
            "asyncio.run(o.create_accounts({}, tier='{}'))"
        ).format(SRC_DIR, SRC_DIR / "services", count, tier_choice)
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                bootstrap,
                cwd=str(PROJECT_ROOT),
                stdout=None,
                stderr=None,
            )
            await proc.wait()
        except KeyboardInterrupt:
            console.print("\n[yellow]Account creation interrupted.[/]")
        except Exception as e:
            console.print("[red]Pipeline error: {}[/]".format(e))
    else:
        console.print("[yellow]Pipeline not found at {}[/]".format(pipeline_script))
        console.print("[dim]Account creation requires the account_pipeline service.[/]")

    Prompt.ask("\nPress Enter to return to menu")


async def warm_sleepers():
    """Option 11: Start onboarding daemon."""
    console.print(
        Panel(
            "[bold green]SLEEPER ONBOARDING DAEMON[/]\n\n"
            "Starts the gradual onboarding scheduler that transitions\n"
            "new accounts through progressive activity phases over 30 days.\n\n"
            "Phases: SETUP -> OBSERVATION -> LIGHT -> ACTIVE -> NORMAL -> GRADUATED",
            border_style="green",
        )
    )

    if not Confirm.ask("Start onboarding daemon?", default=True):
        return

    daemon_script = SRC_DIR / "services" / "onboarding" / "scheduler_daemon.py"
    if daemon_script.exists():
        console.print("[bold green]Starting onboarding daemon...[/]\n")
        try:
            proc = await asyncio.create_subprocess_exec(
                sys.executable,
                str(daemon_script),
                cwd=str(PROJECT_ROOT),
                stdout=None,
                stderr=None,
            )
            await proc.wait()
        except KeyboardInterrupt:
            console.print("\n[yellow]Daemon stopped.[/]")
        except Exception as e:
            console.print("[red]Daemon error: {}[/]".format(e))
    else:
        console.print("[yellow]Daemon not found at {}[/]".format(daemon_script))

    Prompt.ask("\nPress Enter to return to menu")


# ===========================================================================
# QUICK STATUS (--quick-status)
# ===========================================================================

async def quick_status():
    """Print system status and exit."""
    console.print(render_banner())
    status_panel = await check_system_status(quick=True)
    console.print(status_panel)


# ===========================================================================
# MAIN LOOP
# ===========================================================================

async def main_menu():
    """Interactive main menu loop."""
    while True:
        console.clear()
        console.print(render_banner())
        console.print(render_menu())

        choice = Prompt.ask(
            "[bold bright_white]Select[/]",
            default="q",
        ).strip().lower()

        if choice in ("q", "quit", "exit", "0"):
            console.print("\n[bold red]War Room shutting down.[/]\n")
            break

        elif choice == "1":
            await launch_mode("normal")

        elif choice == "2":
            await launch_mode("stealth")

        elif choice == "3":
            await launch_mode("burst")

        elif choice == "4":
            await launch_mode("test")

        elif choice == "5":
            await blaster_deploy()

        elif choice == "6":
            await sleeper_activate()

        elif choice == "7":
            await convergence_mode()

        elif choice == "8":
            await engagement_only()

        elif choice == "9":
            await create_accounts()

        elif choice == "10":
            console.clear()
            console.print(render_banner())
            panel = await show_account_inventory()
            console.print(panel)
            Prompt.ask("\nPress Enter to return to menu")

        elif choice == "11":
            await warm_sleepers()

        elif choice == "12":
            console.clear()
            console.print(render_banner())
            with console.status("[bold cyan]Checking infrastructure...[/]", spinner="dots"):
                panel = await check_system_status()
            console.print(panel)
            Prompt.ask("\nPress Enter to return to menu")

        elif choice == "13":
            console.clear()
            await live_monitor()

        elif choice == "14":
            console.clear()
            console.print(render_banner())
            with console.status("[bold red]Analyzing ban data...[/]", spinner="dots"):
                panel = await show_ban_analytics()
            console.print(panel)
            Prompt.ask("\nPress Enter to return to menu")

        elif choice == "15":
            console.clear()
            console.print(render_banner())
            with console.status("[bold magenta]Loading cost data...[/]", spinner="dots"):
                panel = await show_api_costs()
            console.print(panel)
            Prompt.ask("\nPress Enter to return to menu")

        else:
            console.print("[bold red]Unknown option: {}[/]".format(choice))
            await asyncio.sleep(1)


# ===========================================================================
# ENTRY POINT
# ===========================================================================

def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Reflexion Shield -- War Room v5.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--quick-status",
        action="store_true",
        help="Print system status and exit (no interactive menu)",
    )
    return parser.parse_args()


def main():
    args = parse_args()

    # Handle SIGINT gracefully
    def handle_sigint(sig, frame):
        console.print("\n[bold red]War Room terminated.[/]")
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_sigint)

    if args.quick_status:
        asyncio.run(quick_status())
    else:
        try:
            asyncio.run(main_menu())
        except KeyboardInterrupt:
            console.print("\n[bold red]War Room terminated.[/]")


if __name__ == "__main__":
    main()
