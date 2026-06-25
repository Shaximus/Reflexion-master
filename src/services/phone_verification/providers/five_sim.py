"""5SIM.net provider implementation.

Async wrapper for the 5SIM.net phone number rental API.
Used for renting temporary phone numbers and receiving SMS verification codes.

API Reference: https://5sim.net/v1
Auth: Bearer token in Authorization header.
"""

import logging
from datetime import datetime, timezone

import httpx

logger = logging.getLogger(__name__)

BASE_URL = "https://5sim.net/v1"


class FiveSimError(Exception):
    """Raised when the 5SIM API returns an error response."""

    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"5SIM error ({status_code}): {message}")


class FiveSimProvider:
    """Async wrapper for 5SIM.net API.

    Usage::

        async with FiveSimProvider(api_key="...") as provider:
            balance = await provider.get_balance()
            activation_id, phone = await provider.get_number("twitter")
            status, code = await provider.get_status(activation_id)
            if code:
                await provider.complete(activation_id)
    """

    def __init__(self, api_key: str):
        self.api_key = api_key
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        """Lazily initialize and return the HTTP client."""
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                timeout=30.0,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Accept": "application/json",
                },
            )
        return self._client

    async def _request(self, method: str, path: str, **kwargs) -> dict | str:
        """Make an authenticated request to the 5SIM API.

        Args:
            method: HTTP method (GET, POST, etc.).
            path: API path (appended to BASE_URL).
            **kwargs: Passed through to httpx.AsyncClient.request.

        Returns:
            Parsed JSON dict or raw text depending on content-type.

        Raises:
            FiveSimError: If the API returns a 4xx/5xx status code.
        """
        client = await self._get_client()
        resp = await client.request(method, f"{BASE_URL}{path}", **kwargs)

        if resp.status_code >= 400:
            raise FiveSimError(resp.status_code, resp.text)

        content_type = resp.headers.get("content-type", "")
        if content_type.startswith("application/json"):
            return resp.json()
        return resp.text.strip()

    async def get_balance(self) -> float:
        """Fetch account balance.

        Returns:
            Current balance as a float.
        """
        data = await self._request("GET", "/user/profile")
        return float(data.get("balance", 0))

    async def get_number(
        self,
        product: str = "twitter",
        country: str = "any",
        operator: str = "any",
    ) -> tuple[str, str]:
        """Buy an activation number.

        Args:
            product: Service name (e.g. "twitter", "google", "telegram").
            country: Country code or "any".
            operator: Mobile operator or "any".

        Returns:
            Tuple of (activation_id, phone_number).

        Raises:
            FiveSimError: If purchase fails (no stock, insufficient balance, etc.).
        """
        data = await self._request(
            "GET", f"/user/buy/activation/{country}/{operator}/{product}"
        )
        activation_id = str(data["id"])
        phone = data["phone"]
        logger.info(
            "5SIM: Rented number ***%s (id=%s, product=%s)",
            phone[-4:],
            activation_id,
            product,
        )
        return activation_id, phone

    async def get_status(self, activation_id: str) -> tuple[str, str | None]:
        """Check activation status and retrieve SMS code if received.

        Args:
            activation_id: The activation ID returned by get_number().

        Returns:
            Tuple of (normalized_status, code_or_none).
            Normalized statuses: "waiting", "received", "cancelled", "expired", "completed".
            Code is only populated when status is "received".
        """
        data = await self._request("GET", f"/user/check/{activation_id}")
        status = data.get("status", "PENDING")

        if status == "RECEIVED" and data.get("sms"):
            # Return the latest SMS code
            latest_sms = data["sms"][-1]
            code = latest_sms.get("code", "")
            return "received", code

        status_map = {
            "PENDING": "waiting",
            "CANCELED": "cancelled",
            "TIMEOUT": "expired",
            "FINISHED": "completed",
        }
        return status_map.get(status, status), None

    async def complete(self, activation_id: str):
        """Mark activation as finished (code was used successfully).

        Args:
            activation_id: The activation ID to finish.
        """
        await self._request("GET", f"/user/finish/{activation_id}")
        logger.info("5SIM: Marked activation %s as finished", activation_id)

    async def cancel(self, activation_id: str):
        """Cancel an activation (no SMS received / don't want the number).

        Args:
            activation_id: The activation ID to cancel.
        """
        await self._request("GET", f"/user/cancel/{activation_id}")
        logger.info("5SIM: Cancelled activation %s", activation_id)

    async def ban(self, activation_id: str):
        """Ban/report a number as bad (received wrong code, recycled number, etc.).

        Args:
            activation_id: The activation ID to report.
        """
        await self._request("GET", f"/user/ban/{activation_id}")
        logger.info("5SIM: Banned/reported activation %s", activation_id)

    async def get_prices(
        self, product: str = "twitter", country: str = "any"
    ) -> dict:
        """Get available products and prices for a country.

        Args:
            product: Service name to query prices for.
            country: Country code or "any".

        Returns:
            Dict of operator -> product pricing info.
        """
        return await self._request("GET", f"/guest/products/{country}/any")

    async def close(self):
        """Close the underlying HTTP client."""
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
