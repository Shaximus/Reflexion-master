"""Tier 4: 2Captcha human-powered CAPTCHA solver (last resort).

Uses human workers to solve CAPTCHAs. Slowest but most reliable.

Cost: $1-3 per 1000 solves
Speed: 20-60 seconds (human workers)
Reliability: Very high (human accuracy)
"""

import asyncio
import logging
import time

import httpx

logger = logging.getLogger(__name__)

SUBMIT_URL = "https://2captcha.com/in.php"
RESULT_URL = "https://2captcha.com/res.php"

ERRORS = {
    "ERROR_WRONG_USER_KEY": "Invalid API key",
    "ERROR_KEY_DOES_NOT_EXIST": "API key does not exist",
    "ERROR_ZERO_BALANCE": "Zero balance",
    "ERROR_NO_SLOT_AVAILABLE": "No workers available, try later",
    "ERROR_CAPTCHA_UNSOLVABLE": "CAPTCHA could not be solved",
    "ERROR_TOO_BIG_CAPTCHA_FILESIZE": "Image file too large",
    "ERROR_WRONG_FILE_EXTENSION": "Wrong image format",
    "IP_BANNED": "IP address banned",
}


class TwoCaptchaError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or ERRORS.get(code, f"2Captcha error: {code}"))


class TwoCaptchaSolver:
    """Async client for 2Captcha.com API (human-powered solving)."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    @property
    def name(self) -> str:
        return "2captcha"

    @property
    def cost_per_solve(self) -> float:
        return 0.003  # ~$3/1000

    async def is_available(self) -> bool:
        return bool(self.api_key)

    def _check_error(self, text: str):
        """Check if response is an error."""
        text = text.strip()
        if text.startswith("ERROR_") or text in ERRORS:
            raise TwoCaptchaError(text)

    async def _submit(self, params: dict) -> str:
        """Submit CAPTCHA and return request ID."""
        client = await self._get_client()
        params["key"] = self.api_key
        params["json"] = "0"  # Plain text responses
        resp = await client.post(SUBMIT_URL, data=params)
        text = resp.text.strip()
        self._check_error(text)

        if not text.startswith("OK|"):
            raise TwoCaptchaError("UNEXPECTED", f"Unexpected submit response: {text}")

        request_id = text.split("|", 1)[1]
        return request_id

    async def _poll_result(self, request_id: str, max_wait: int = 180, poll_interval: float = 5.0) -> str:
        """Poll for result. Returns solution token/text."""
        client = await self._get_client()
        deadline = time.monotonic() + max_wait

        # Initial delay — humans need time
        await asyncio.sleep(10)

        while time.monotonic() < deadline:
            resp = await client.get(RESULT_URL, params={
                "key": self.api_key,
                "action": "get",
                "id": request_id,
            })
            text = resp.text.strip()

            if text == "CAPCHA_NOT_READY":
                await asyncio.sleep(poll_interval)
                continue

            self._check_error(text)

            if text.startswith("OK|"):
                return text.split("|", 1)[1]

            raise TwoCaptchaError("UNEXPECTED", f"Unexpected result: {text}")

        raise TwoCaptchaError("TIMEOUT", f"Not solved within {max_wait}s")

    async def solve(self, image_data: bytes = None, challenge_type: str = "funcaptcha",
                    public_key: str = None, page_url: str = "", **kwargs) -> str:
        """Unified solve interface for the tier chain."""
        if public_key:
            if challenge_type == "funcaptcha":
                return await self.solve_funcaptcha(public_key, page_url)
            elif challenge_type.startswith("recaptcha"):
                return await self.solve_recaptcha(public_key, page_url)
            elif challenge_type == "hcaptcha":
                return await self.solve_hcaptcha(public_key, page_url)
            elif challenge_type == "turnstile":
                return await self.solve_turnstile(public_key, page_url)

        if image_data:
            return await self.solve_image(image_data, challenge_type)

        raise TwoCaptchaError("UNSUPPORTED", f"No handler for type={challenge_type}")

    async def solve_funcaptcha(self, public_key: str, page_url: str) -> str:
        """Solve FunCaptcha via human workers."""
        start = time.monotonic()
        request_id = await self._submit({
            "method": "funcaptcha",
            "publickey": public_key,
            "pageurl": page_url,
        })
        logger.info(f"2Captcha FunCaptcha submitted (id={request_id})")
        token = await self._poll_result(request_id)
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"2Captcha FunCaptcha solved in {latency_ms}ms")
        return token

    async def solve_recaptcha(self, site_key: str, page_url: str) -> str:
        """Solve reCAPTCHA v2 via human workers."""
        start = time.monotonic()
        request_id = await self._submit({
            "method": "userrecaptcha",
            "googlekey": site_key,
            "pageurl": page_url,
        })
        logger.info(f"2Captcha reCAPTCHA submitted (id={request_id})")
        token = await self._poll_result(request_id)
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"2Captcha reCAPTCHA solved in {latency_ms}ms")
        return token

    async def solve_hcaptcha(self, site_key: str, page_url: str) -> str:
        """Solve hCaptcha via human workers."""
        start = time.monotonic()
        request_id = await self._submit({
            "method": "hcaptcha",
            "sitekey": site_key,
            "pageurl": page_url,
        })
        logger.info(f"2Captcha hCaptcha submitted (id={request_id})")
        token = await self._poll_result(request_id)
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"2Captcha hCaptcha solved in {latency_ms}ms")
        return token

    async def solve_turnstile(self, site_key: str, page_url: str) -> str:
        """Solve Cloudflare Turnstile via human workers."""
        start = time.monotonic()
        request_id = await self._submit({
            "method": "turnstile",
            "sitekey": site_key,
            "pageurl": page_url,
        })
        logger.info(f"2Captcha Turnstile submitted (id={request_id})")
        token = await self._poll_result(request_id)
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"2Captcha Turnstile solved in {latency_ms}ms")
        return token

    async def solve_image(self, image_data: bytes, challenge_type: str = "text") -> str:
        """Solve image-based CAPTCHA (text recognition, etc)."""
        import base64
        b64 = base64.b64encode(image_data).decode("utf-8")
        start = time.monotonic()
        request_id = await self._submit({
            "method": "base64",
            "body": b64,
        })
        logger.info(f"2Captcha image submitted (id={request_id})")
        answer = await self._poll_result(request_id)
        latency_ms = int((time.monotonic() - start) * 1000)
        logger.info(f"2Captcha image solved in {latency_ms}ms: '{answer[:30]}'")
        return answer

    async def get_balance(self) -> float:
        """Check account balance."""
        client = await self._get_client()
        resp = await client.get(RESULT_URL, params={
            "key": self.api_key,
            "action": "getbalance",
        })
        return float(resp.text.strip())

    async def report_good(self, request_id: str):
        """Report correct answer (improves priority)."""
        client = await self._get_client()
        await client.get(RESULT_URL, params={
            "key": self.api_key,
            "action": "reportgood",
            "id": request_id,
        })

    async def report_bad(self, request_id: str):
        """Report incorrect answer (may get refund)."""
        client = await self._get_client()
        await client.get(RESULT_URL, params={
            "key": self.api_key,
            "action": "reportbad",
            "id": request_id,
        })

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
