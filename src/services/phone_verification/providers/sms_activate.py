"""SMS-Activate.org provider implementation."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://api.sms-activate.org/stubs/handler_api.php"

# Common error responses
ERRORS = {
    "NO_NUMBERS": "No numbers available for this service/country",
    "NO_BALANCE": "Insufficient balance",
    "BAD_KEY": "Invalid API key",
    "BAD_ACTION": "Invalid action",
    "BAD_STATUS": "Invalid status transition",
    "WRONG_EXCEPTION_PHONE": "Invalid phone exception",
}


class SMSActivateError(Exception):
    def __init__(self, code: str, message: str = ""):
        self.code = code
        super().__init__(message or ERRORS.get(code, f"Unknown error: {code}"))


class SMSActivateProvider:
    """Async wrapper for SMS-Activate.org API."""

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    async def _request(self, params: dict) -> str:
        """Make API request, return raw text response."""
        client = await self._get_client()
        params["api_key"] = self.api_key
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        text = resp.text.strip()
        # Check for known errors
        if text in ERRORS:
            raise SMSActivateError(text)
        return text

    async def get_number(self, service: str = "tw", country: str = "0") -> tuple[str, str]:
        """
        Rent a number. Returns (activation_id, phone_number).
        Response format: ACCESS_NUMBER:{id}:{phone}
        """
        text = await self._request({
            "action": "getNumber",
            "service": service,
            "country": country,
        })
        if not text.startswith("ACCESS_NUMBER:"):
            raise SMSActivateError("UNEXPECTED", f"Unexpected response: {text}")
        parts = text.split(":")
        activation_id = parts[1]
        phone = parts[2]
        logger.info(f"Rented number: ***{phone[-4:]} (id={activation_id}, service={service})")
        return activation_id, phone

    async def get_status(self, activation_id: str) -> tuple[str, str | None]:
        """
        Check SMS status. Returns (status, code_or_none).
        STATUS_WAIT_CODE -> ("waiting", None)
        STATUS_OK:{code} -> ("received", "12345")
        STATUS_CANCEL -> ("cancelled", None)
        """
        text = await self._request({
            "action": "getStatus",
            "id": activation_id,
        })
        if text == "STATUS_WAIT_CODE":
            return "waiting", None
        if text == "STATUS_WAIT_RETRY":
            return "waiting_retry", None
        if text == "STATUS_WAIT_RESEND":
            return "waiting_resend", None
        if text.startswith("STATUS_OK:"):
            code = text.split(":", 1)[1]
            return "received", code
        if text == "STATUS_CANCEL":
            return "cancelled", None
        return text, None

    async def set_status(self, activation_id: str, status: int):
        """
        Set activation status.
        1 = ready (inform that SMS has been sent)
        3 = request another SMS
        6 = complete successfully
        8 = cancel
        """
        await self._request({
            "action": "setStatus",
            "id": activation_id,
            "status": str(status),
        })

    async def complete(self, activation_id: str):
        """Mark activation as successfully completed."""
        await self.set_status(activation_id, 6)

    async def cancel(self, activation_id: str):
        """Cancel activation."""
        await self.set_status(activation_id, 8)

    async def get_balance(self) -> float:
        """Get account balance. Response: ACCESS_BALANCE:{amount}"""
        text = await self._request({"action": "getBalance"})
        if text.startswith("ACCESS_BALANCE:"):
            return float(text.split(":")[1])
        raise SMSActivateError("UNEXPECTED", f"Unexpected balance response: {text}")

    async def get_prices(self, service: str = "tw", country: str | None = None) -> dict:
        """Get prices for a service. Returns JSON with country->price mapping."""
        params = {"action": "getPrices", "service": service}
        if country is not None:
            params["country"] = country
        client = await self._get_client()
        params["api_key"] = self.api_key
        resp = await client.get(BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()

    async def close(self):
        """Close the HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
