#!/usr/bin/env python3
"""
SECURE ADMIN API FOR SOUL SWARM
Localhost-only binding with header authentication and hot-reload support
"""

import os
import sys
import json
import asyncio
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Set
from fastapi import FastAPI, Header, HTTPException, Body
from fastapi.responses import JSONResponse
import uvicorn

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("admin_api")

# ============================================================================
# ATOMIC FILE OPERATIONS
# ============================================================================


def atomic_write_json(path: Path, data: dict):
    """Write JSON file atomically to prevent corruption"""
    tmp = path.with_suffix(path.suffix + ".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        os.replace(str(tmp), str(path))  # atomic on modern OS
    except Exception as e:
        if tmp.exists():
            tmp.unlink()  # Clean up temp file on error
        raise e


def audit_log(action: str, details: str = "", status: str = "ok"):
    """Log admin actions for audit trail"""
    log_dir = Path("engagement")
    log_dir.mkdir(exist_ok=True)
    log_file = log_dir / "admin_changes.log"

    timestamp = datetime.now().isoformat()
    log_line = f"{timestamp}, actor=local, action={action}, details={details}, status={status}\n"

    with open(log_file, "a", encoding="utf-8") as f:
        f.write(log_line)


# ============================================================================
# TOKEN MANAGER WITH HOT RELOAD
# ============================================================================


class TokenManager:
    """Manages soul tokens with file watching and atomic updates"""

    def __init__(self):
        self.tokens_path = Path("soul_data.json")
        self.banned_path = Path("engagement/banned_souls.json")
        self.tokens: Dict[str, Dict] = {}
        self.banned_souls: Set[str] = set()
        self._tokens_mtime = 0.0
        self._banned_mtime = 0.0
        self._reload_event = asyncio.Event()

        # Initial load
        self.reload_tokens()
        self.reload_banned()

    def reload_tokens(self):
        """Load tokens from disk"""
        if self.tokens_path.exists():
            try:
                with open(self.tokens_path, "r", encoding="utf-8") as f:
                    self.tokens = json.load(f)
                self._tokens_mtime = self.tokens_path.stat().st_mtime
                logger.info(f"Loaded {len(self.tokens)} soul tokens")
            except Exception as e:
                logger.error(f"Failed to load tokens: {e}")

    def reload_banned(self):
        """Load banned souls list"""
        if self.banned_path.exists():
            try:
                with open(self.banned_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    self.banned_souls = set(data.get("banned", []))
                self._banned_mtime = self.banned_path.stat().st_mtime
                logger.info(f"Loaded {len(self.banned_souls)} banned souls")
            except Exception as e:
                logger.error(f"Failed to load banned list: {e}")

    async def check_reload(self):
        """Check if files changed and reload if needed"""
        changed = False

        # Check tokens file
        if self.tokens_path.exists():
            mtime = self.tokens_path.stat().st_mtime
            if mtime > self._tokens_mtime:
                self.reload_tokens()
                changed = True

        # Check banned file
        if self.banned_path.exists():
            mtime = self.banned_path.stat().st_mtime
            if mtime > self._banned_mtime:
                self.reload_banned()
                changed = True

        if changed:
            self._reload_event.set()
            self._reload_event.clear()

    def update_token(self, soul: str, token: str) -> bool:
        """Update a soul's auth token"""
        try:
            # Update in memory
            if soul not in self.tokens:
                self.tokens[soul] = {"created_date": datetime.now().isoformat()}
            self.tokens[soul]["auth_token"] = token

            # Write atomically
            atomic_write_json(self.tokens_path, self.tokens)

            # Log the change
            audit_log("update_token", f"soul={soul}", "ok")
            return True
        except Exception as e:
            audit_log("update_token", f"soul={soul}, error={e}", "failed")
            return False

    def ban_soul(self, soul: str) -> bool:
        """Ban a soul from posting"""
        try:
            self.banned_souls.add(soul)
            self.banned_path.parent.mkdir(exist_ok=True)

            data = {
                "banned": list(self.banned_souls),
                "updated": datetime.now().isoformat(),
            }
            atomic_write_json(self.banned_path, data)

            audit_log("ban_soul", f"soul={soul}", "ok")
            return True
        except Exception as e:
            audit_log("ban_soul", f"soul={soul}, error={e}", "failed")
            return False

    def unban_soul(self, soul: str) -> bool:
        """Remove a soul from the ban list"""
        try:
            self.banned_souls.discard(soul)
            self.banned_path.parent.mkdir(exist_ok=True)

            data = {
                "banned": list(self.banned_souls),
                "updated": datetime.now().isoformat(),
            }
            atomic_write_json(self.banned_path, data)

            audit_log("unban_soul", f"soul={soul}", "ok")
            return True
        except Exception as e:
            audit_log("unban_soul", f"soul={soul}, error={e}", "failed")
            return False


# ============================================================================
# FASTAPI APPLICATION
# ============================================================================

app = FastAPI(title="Soul Swarm Admin API", version="1.0.0")
token_manager = TokenManager()

# Admin key from environment (or generate a strong one)
from dotenv import load_dotenv  # add this import with the others

load_dotenv()  # load .env from project root
ADMIN_KEY = os.getenv("ADMIN_KEY")
if not ADMIN_KEY:
    logger.error("❌ ADMIN_KEY missing in .env – refusing to start.")
    raise SystemExit(1)


def verify_admin(x_admin_key: Optional[str] = Header(None)):
    """Verify admin authentication"""
    if not x_admin_key or x_admin_key != ADMIN_KEY:
        audit_log("auth_failed", "invalid_key_provided", "failed")
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


# ============================================================================
# API ENDPOINTS
# ============================================================================


@app.get("/health")
async def health_check(x_admin_key: Optional[str] = Header(None)):
    """Get system health and status"""
    verify_admin(x_admin_key)

    # Load usage stats if available
    usage_file = Path("engagement/ryan_api_usage.json")
    usage = {}
    if usage_file.exists():
        try:
            with open(usage_file, "r") as f:
                usage = json.load(f)
        except:
            pass

    return {
        "status": "healthy",
        "souls": {
            "total": len(token_manager.tokens),
            "active": len(
                [s for s in token_manager.tokens if s not in token_manager.banned_souls]
            ),
            "banned": len(token_manager.banned_souls),
        },
        "usage": {
            "reads": usage.get("reads", 0),
            "posts": usage.get("posts", 0),
            "month": usage.get("month", datetime.now().month),
        },
        "timestamp": datetime.now().isoformat(),
    }


@app.post("/tokens")
async def update_token(
    soul: str = Body(..., embed=True),
    token: str = Body(..., embed=True),
    x_admin_key: Optional[str] = Header(None),
):
    """Update a soul's authentication token"""
    verify_admin(x_admin_key)

    if not soul or not token:
        raise HTTPException(status_code=400, detail="Soul and token required")

    success = token_manager.update_token(soul, token)

    if success:
        # Trigger reload in running processes
        await token_manager.check_reload()
        return {"success": True, "message": f"Token updated for {soul}"}
    else:
        raise HTTPException(status_code=500, detail="Failed to update token")


@app.post("/ban")
async def ban_soul(
    soul: str = Body(..., embed=True), x_admin_key: Optional[str] = Header(None)
):
    """Ban a soul from posting"""
    verify_admin(x_admin_key)

    if not soul:
        raise HTTPException(status_code=400, detail="Soul name required")

    success = token_manager.ban_soul(soul)

    if success:
        return {"success": True, "message": f"Soul {soul} banned"}
    else:
        raise HTTPException(status_code=500, detail="Failed to ban soul")


@app.post("/unban")
async def unban_soul(
    soul: str = Body(..., embed=True), x_admin_key: Optional[str] = Header(None)
):
    """Remove a soul from the ban list"""
    verify_admin(x_admin_key)

    if not soul:
        raise HTTPException(status_code=400, detail="Soul name required")

    success = token_manager.unban_soul(soul)

    if success:
        return {"success": True, "message": f"Soul {soul} unbanned"}
    else:
        raise HTTPException(status_code=500, detail="Failed to unban soul")


@app.get("/souls")
async def list_souls(x_admin_key: Optional[str] = Header(None)):
    """List all souls and their status"""
    verify_admin(x_admin_key)

    souls = []
    for name, data in token_manager.tokens.items():
        token = data.get("auth_token", "")
        souls.append(
            {
                "name": name,
                "has_token": bool(
                    token
                    and token not in ["GET_FROM_BROWSER", "GET_FROM_BROWSER_COOKIES"]
                ),
                "banned": name in token_manager.banned_souls,
                "created": data.get("created_date", "unknown"),
            }
        )

    return {"souls": souls}


@app.get("/logs/audit")
async def get_audit_logs(limit: int = 100, x_admin_key: Optional[str] = Header(None)):
    """Get recent audit log entries"""
    verify_admin(x_admin_key)

    log_file = Path("engagement/admin_changes.log")
    if not log_file.exists():
        return {"logs": []}

    try:
        with open(log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            # Return last N entries
            recent = lines[-limit:] if len(lines) > limit else lines
            return {"logs": [line.strip() for line in recent]}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to read logs: {e}")


# ============================================================================
# BACKGROUND TASKS
# ============================================================================


async def token_watcher():
    """Background task to watch for file changes"""
    while True:
        try:
            await token_manager.check_reload()
        except Exception as e:
            logger.error(f"Watcher error: {e}")
        await asyncio.sleep(2)  # Check every 2 seconds


@app.on_event("startup")
async def startup_event():
    """Start background tasks"""
    asyncio.create_task(token_watcher())
    logger.info("Token watcher started")
    audit_log("admin_api_started", f"port=8765", "ok")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    audit_log("admin_api_stopped", "", "ok")


# ============================================================================
# MAIN ENTRY POINT
# ============================================================================

if __name__ == "__main__":
    print(
        """
    ╔══════════════════════════════════════════════════════════╗
    ║            SOUL SWARM ADMIN API (SECURE)                 ║
    ╚══════════════════════════════════════════════════════════╝
    
    Starting on http://127.0.0.1:8765 (localhost only)
    
    Required header: X-Admin-Key (set in .env)
    
    Endpoints:
      GET  /health      - System status
      POST /tokens      - Update soul token
      POST /ban         - Ban a soul
      POST /unban       - Unban a soul  
      GET  /souls       - List all souls
      GET  /logs/audit  - View audit logs
    
    SECURITY FEATURES:
      ✓ Localhost-only binding
      ✓ Header authentication required
      ✓ Atomic file writes
      ✓ Audit logging
      ✓ Hot-reload support
    """.format(
            key=ADMIN_KEY[:20] + "..."
        )
    )

    # CRITICAL: Bind to localhost only!
    uvicorn.run(
        app, host="127.0.0.1", port=8765, log_level="info"  # NEVER change to 0.0.0.0
    )
