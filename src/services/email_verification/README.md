# Email Verification Service

Receives emails via Cloudflare Email Workers, extracts verification codes, stores them in Redis, and serves them via API.

## Architecture

```
Incoming Email → Cloudflare Email Worker → POST /webhook → Redis (TTL) → GET /code/{email}
```

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Start the receiver

```bash
# Direct
python email_receiver.py

# Or with uvicorn
uvicorn email_receiver:app --host 127.0.0.1 --port 3010
```

### 3. Deploy the Cloudflare Worker

```bash
# In your wrangler project:
# 1. Copy email_worker.js as your worker entry point
# 2. Set environment variables:
wrangler secret put WEBHOOK_URL    # e.g. https://hannah.reflexionsoftware.com/email/webhook
wrangler secret put WEBHOOK_SECRET # shared secret for auth

# 3. Configure email routing in Cloudflare dashboard:
#    - Add your domain's MX records
#    - Create a catch-all route pointing to this worker
```

### 4. Environment variables (receiver)

| Variable | Default | Description |
|----------|---------|-------------|
| `REDIS_URL` | `redis://localhost:6379` | Redis connection URL |
| `REDIS_PASSWORD` | `ShaxAGI2025` | Redis auth password |
| `WEBHOOK_SECRET` | (empty) | Shared secret for webhook auth |

## API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/webhook` | Receive email data from CF Worker |
| `GET` | `/code/{email}` | Get latest code (404 if none) |
| `GET` | `/code/{email}?wait=true&timeout=120` | Long-poll for code |
| `DELETE` | `/code/{email}` | Clear used code |
| `GET` | `/health` | Service health check |

## Client Usage

```python
from email_verification import EmailVerificationClient

async with EmailVerificationClient() as client:
    # Wait for a code (blocks up to 120s)
    code = await client.wait_for_code("user@domain.com", timeout=120)

    # Or check without waiting
    code = await client.get_code("user@domain.com")

    # Clean up after use
    await client.clear_code("user@domain.com")
```
