"""Tier 3: CapSolver.com commercial CAPTCHA solver.

Token-based solving for FunCaptcha, reCAPTCHA, hCaptcha, Turnstile.

Cost: $0.5-3.0 per 1000 solves depending on type
Speed: 5-30 seconds
Reliability: High (commercial service with SLA)
"""

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.capsolver.com"

TASK_TYPES = {
    "funcaptcha": "FunCaptchaTaskProxyLess",
    "recaptcha_v2": "ReCaptchaV2TaskProxyLess",
    "recaptcha_v3": "ReCaptchaV3TaskProxyLess",
    "hcaptcha": "HCaptchaTaskProxyLess",
    "turnstile": "AntiTurnstileTaskProxyLess",
}

# Approximate cost per solve in USD
COST_ESTIMATES = {
    "funcaptcha": 0.002,
    "recaptcha_v2": 0.001,
    "recaptcha_v3": 0.002,
    "hcaptcha": 0.001,
    "turnstile": 0.001,
}


class CapSolverError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        super().__init__(f"CapSolver [{code}]: {message}")


class CapSolverClient:
    """Async client for CapSolver.com API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    @property
    def name(self) -> str:
        return "capsolver"

    @property
    def cost_per_solve(self) -> float:
        return 0.002  # Average

    async def is_available(self) -> bool:
        return bool(self.api_key)

    async def _create_task(self, task: dict) -> str:
        """Create a solving task. Returns task ID."""
        client = await self._get_client()
        resp = await client.post(
            f"{BASE_URL}/createTask",
            json={"clientKey": self.api_key, "task": task},
        )
        data = resp.json()
        if data.get("errorId", 0) != 0:
            raise CapSolverError(
                data.get("errorCode", "UNKNOWN"),
                data.get("errorDescription", "Unknown error"),
            )
        task_id = data.get("taskId")
        if not task_id:
            # Some tasks return solution immediately
            if data.get("solution"):
                return data
            raise CapSolverError("NO_TASK_ID", "No taskId in response")
        return task_id

    async def _get_result(self, task_id: str, max_wait: int = 120, poll_interval: float = 3.0) -> dict:
        """Poll for task result."""
        client = await self._get_client()
        deadline = time.monotonic() + max_wait

        while time.monotonic() < deadline:
            resp = await client.post(
                f"{BASE_URL}/getTaskResult",
                json={"clientKey": self.api_key, "taskId": task_id},
            )
            data = resp.json()

            if data.get("errorId", 0) != 0:
                raise CapSolverError(
                    data.get("errorCode", "UNKNOWN"),
                    data.get("errorDescription", "Unknown error"),
                )

            status = data.get("status", "")
            if status == "ready":
                return data.get("solution", {})
            if status == "failed":
                raise CapSolverError("TASK_FAILED", "Task failed")

            await asyncio.sleep(poll_interval)

        raise CapSolverError("TIMEOUT", f"Task not completed within {max_wait}s")

    async def solve(self, image_data: bytes = None, challenge_type: str = "funcaptcha",
                    public_key: str = None, page_url: str = "", **kwargs) -> str:
        """
        Unified solve interface for the tier chain.
        Uses token-based solving when public_key is provided.
        """
        if public_key:
            if challenge_type == "funcaptcha":
                return await self.solve_funcaptcha(public_key, page_url, **kwargs)
            elif challenge_type in ("recaptcha_v2", "recaptcha_v3"):
                return await self.solve_recaptcha(public_key, page_url, challenge_type, **kwargs)
            elif challenge_type == "hcaptcha":
                return await self.solve_hcaptcha(public_key, page_url, **kwargs)
            elif challenge_type == "turnstile":
                return await self.solve_turnstile(public_key, page_url, **kwargs)
        raise CapSolverError("UNSUPPORTED", f"No handler for type={challenge_type} with given params")

    async def solve_funcaptcha(self, public_key: str, page_url: str, **kwargs) -> str:
        """Solve Arkose FunCaptcha token-based."""
        task = {
            "type": "FunCaptchaTaskProxyLess",
            "websitePublicKey": public_key,
            "websiteURL": page_url,
        }
        if kwargs.get("subdomain"):
            task["funcaptchaApiJSSubdomain"] = kwargs["subdomain"]
        if kwargs.get("data"):
            task["data"] = kwargs["data"]

        start = time.monotonic()
        result = await self._create_task(task)

        # Check if instant solution
        if isinstance(result, dict) and result.get("solution"):
            solution = result["solution"]
        else:
            solution = await self._get_result(result)

        token = solution.get("token", "")
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"CapSolver FunCaptcha solved in {latency_ms}ms")
        return token

    async def solve_recaptcha(self, site_key: str, page_url: str,
                               captcha_type: str = "recaptcha_v2", **kwargs) -> str:
        """Solve reCAPTCHA v2 or v3."""
        task_type = TASK_TYPES.get(captcha_type, "ReCaptchaV2TaskProxyLess")
        task = {
            "type": task_type,
            "websiteKey": site_key,
            "websiteURL": page_url,
        }
        if captcha_type == "recaptcha_v3":
            task["pageAction"] = kwargs.get("action", "verify")
            task["minScore"] = kwargs.get("min_score", 0.7)

        start = time.monotonic()
        result = await self._create_task(task)
        if isinstance(result, dict) and result.get("solution"):
            solution = result["solution"]
        else:
            solution = await self._get_result(result)

        token = solution.get("gRecaptchaResponse", "")
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"CapSolver reCAPTCHA solved in {latency_ms}ms")
        return token

    async def solve_hcaptcha(self, site_key: str, page_url: str, **kwargs) -> str:
        """Solve hCaptcha."""
        task = {
            "type": "HCaptchaTaskProxyLess",
            "websiteKey": site_key,
            "websiteURL": page_url,
        }

        start = time.monotonic()
        result = await self._create_task(task)
        if isinstance(result, dict) and result.get("solution"):
            solution = result["solution"]
        else:
            solution = await self._get_result(result)

        token = solution.get("gRecaptchaResponse", solution.get("token", ""))
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"CapSolver hCaptcha solved in {latency_ms}ms")
        return token

    async def solve_turnstile(self, site_key: str, page_url: str, **kwargs) -> str:
        """Solve Cloudflare Turnstile."""
        task = {
            "type": "AntiTurnstileTaskProxyLess",
            "websiteKey": site_key,
            "websiteURL": page_url,
        }

        start = time.monotonic()
        result = await self._create_task(task)
        if isinstance(result, dict) and result.get("solution"):
            solution = result["solution"]
        else:
            solution = await self._get_result(result)

        token = solution.get("token", "")
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"CapSolver Turnstile solved in {latency_ms}ms")
        return token

    async def get_balance(self) -> float:
        """Check account balance."""
        client = await self._get_client()
        resp = await client.post(
            f"{BASE_URL}/getBalance",
            json={"clientKey": self.api_key},
        )
        data = resp.json()
        return float(data.get("balance", 0))

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
