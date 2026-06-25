"""
Email Verification Receiver - FastAPI webhook + query API.

Receives POSTed email data from the Cloudflare Email Worker,
stores verification codes in Redis, and serves them via API.

Run: uvicorn email_receiver:app --host 127.0.0.1 --port 3010
"""

import asyncio
import logging
import os
import re
import time
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

import redis.asyncio as aioredis
from fastapi import FastAPI, Header, HTTPException, Query, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "ShaxAGI2025")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
CODE_TTL = 600        # 10 minutes
FULL_EMAIL_TTL = 3600 # 1 hour
POLL_INTERVAL = 0.5   # seconds between Redis checks during long-poll

# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

log_dir = Path(__file__).parent / "logs"
log_dir.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(log_dir / "email_receiver.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("email_receiver")

# ---------------------------------------------------------------------------
# Redis
# ---------------------------------------------------------------------------

_redis: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            REDIS_URL, password=REDIS_PASSWORD, decode_responses=True
        )
    return _redis


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------


class EmailPayload(BaseModel):
    to: str
    sender: Optional[str] = None
    subject: Optional[str] = None
    code: Optional[str] = None
    raw_body: Optional[str] = None
    received_at: Optional[str] = None


class CodeResponse(BaseModel):
    email: str
    code: str
    received_at: Optional[str] = None
    subject: Optional[str] = None


# ---------------------------------------------------------------------------
# Additional code extraction (fallback if worker didn't find one)
# ---------------------------------------------------------------------------

CODE_PATTERNS = [
    re.compile(
        r"(?:verification|confirm(?:ation)?|security|auth(?:entication)?)"
        r"\s*code\s*(?:is\s*:?|:)\s*(\d{6})\b",
        re.I,
    ),
    re.compile(r"(?:your|the)\s*code\s*(?:is\s*:?|:)\s*(\d{6})\b", re.I),
    re.compile(r"(?:enter|use|input)\s+(?:this\s+)?code\s*:?\s*(\d{6})\b", re.I),
    re.compile(
        r"(?:one[- ]time\s*(?:pass(?:code|word)?|code)|OTP|PIN)\s*(?:is\s*:?|:)\s*(\d{6})\b",
        re.I,
    ),
    re.compile(r"^\s*(\d{6})\s*$", re.M),
]


def extract_code(text: str) -> Optional[str]:
    for pattern in CODE_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(1)
    return None


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------


@asynccontextmanager
async def lifespan(app: FastAPI):
    r = await get_redis()
    await r.ping()
    logger.info("Connected to Redis, email receiver ready")
    yield
    if _redis:
        await _redis.close()


app = FastAPI(
    title="Email Verification Service",
    version="1.0.0",
    lifespan=lifespan,
)


# ---------------------------------------------------------------------------
# Webhook endpoint
# ---------------------------------------------------------------------------


@app.post("/webhook")
async def receive_email(request: Request):
    """Receive email data from Cloudflare Worker."""
    # Verify webhook secret if configured
    if WEBHOOK_SECRET:
        secret = request.headers.get("x-webhook-secret", "")
        if secret != WEBHOOK_SECRET:
            raise HTTPException(status_code=401, detail="Invalid webhook secret")

    body = await request.json()
    # Map 'from' (JS field name) to 'sender' (Python-safe field name)
    if "from" in body:
        body["sender"] = body.pop("from")
    payload = EmailPayload(**body)

    recipient = payload.to.lower().strip()
    r = await get_redis()

    # Try worker-extracted code first, then our own extraction
    code = payload.code
    if not code and payload.raw_body:
        code = extract_code(payload.raw_body)

    logger.info(
        "Email received: to=%s from=%s subject=%s code=%s",
        recipient,
        payload.sender,
        payload.subject,
        code or "(none)",
    )

    if code:
        # Store code with metadata
        code_key = f"email:code:{recipient}"
        await r.hset(
            code_key,
            mapping={
                "code": code,
                "from": payload.sender or "",
                "subject": payload.subject or "",
                "received_at": payload.received_at or "",
            },
        )
        await r.expire(code_key, CODE_TTL)

        # Publish for long-poll waiters
        await r.publish(f"email:notify:{recipient}", code)

    # Store full email body regardless
    if payload.raw_body:
        full_key = f"email:full:{recipient}"
        await r.set(full_key, payload.raw_body, ex=FULL_EMAIL_TTL)

    return {"status": "ok", "code_extracted": code is not None}


# ---------------------------------------------------------------------------
# Query API
# ---------------------------------------------------------------------------


@app.get("/code/{email_address:path}")
async def get_code(
    email_address: str,
    wait: bool = Query(False),
    timeout: int = Query(120, ge=1, le=300),
):
    """
    Get verification code for an email address.

    With wait=true, long-polls until a code arrives or timeout is reached.
    """
    email_address = email_address.lower().strip()
    r = await get_redis()

    # Check if code already exists
    code_key = f"email:code:{email_address}"
    data = await r.hgetall(code_key)
    if data and "code" in data:
        return CodeResponse(
            email=email_address,
            code=data["code"],
            received_at=data.get("received_at"),
            subject=data.get("subject"),
        )

    if not wait:
        raise HTTPException(status_code=404, detail="No code found")

    # Long-poll: subscribe to notification channel and wait
    pubsub = r.pubsub()
    channel = f"email:notify:{email_address}"
    await pubsub.subscribe(channel)

    try:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                break

            # Wait for pub/sub message
            message = await asyncio.wait_for(
                pubsub.get_message(ignore_subscribe_messages=True, timeout=POLL_INTERVAL),
                timeout=min(remaining, POLL_INTERVAL + 0.1),
            )

            if message and message["type"] == "message":
                # Code arrived via pub/sub
                data = await r.hgetall(code_key)
                if data and "code" in data:
                    return CodeResponse(
                        email=email_address,
                        code=data["code"],
                        received_at=data.get("received_at"),
                        subject=data.get("subject"),
                    )

            # Also check Redis directly (in case pub/sub message was missed)
            data = await r.hgetall(code_key)
            if data and "code" in data:
                return CodeResponse(
                    email=email_address,
                    code=data["code"],
                    received_at=data.get("received_at"),
                    subject=data.get("subject"),
                )
    except asyncio.TimeoutError:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await pubsub.close()

    raise HTTPException(status_code=408, detail="Timeout waiting for code")


@app.delete("/code/{email_address:path}")
async def clear_code(email_address: str):
    """Clear a used verification code."""
    email_address = email_address.lower().strip()
    r = await get_redis()

    code_key = f"email:code:{email_address}"
    full_key = f"email:full:{email_address}"

    deleted = await r.delete(code_key, full_key)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="No code found")

    logger.info("Code cleared for %s", email_address)
    return {"status": "cleared", "email": email_address}


@app.get("/health")
async def health():
    """Service health check."""
    try:
        r = await get_redis()
        await r.ping()
        return {"status": "ok", "redis": "connected"}
    except Exception as e:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "redis": str(e)},
        )


# ---------------------------------------------------------------------------
# Run directly
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=3010, log_level="info")
