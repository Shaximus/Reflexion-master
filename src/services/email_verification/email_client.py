"""
Email Verification Client - async interface to the verification service.

Usage:
    from email_verification import EmailVerificationClient

    async with EmailVerificationClient() as client:
        code = await client.wait_for_code("user@example.com", timeout=120)
        print(f"Got code: {code}")
        await client.clear_code("user@example.com")
"""

from typing import Optional

import aiohttp


class EmailVerificationClient:
    """Async client for the email verification service."""

    def __init__(self, base_url: str = "http://localhost:3010"):
        self.base_url = base_url.rstrip("/")
        self._session: Optional[aiohttp.ClientSession] = None

    async def _ensure_session(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession()
        return self._session

    async def __aenter__(self):
        await self._ensure_session()
        return self

    async def __aexit__(self, *exc):
        await self.close()

    async def close(self):
        if self._session and not self._session.closed:
            await self._session.close()
            self._session = None

    async def wait_for_code(self, email_address: str, timeout: int = 120) -> str:
        """
        Wait for a verification code to arrive for the given email.

        Blocks until a code is available or timeout is reached.
        Uses server-side long-polling to avoid hammering the API.

        Args:
            email_address: The recipient email to watch.
            timeout: Maximum seconds to wait (1-300).

        Returns:
            The 6-digit verification code as a string.

        Raises:
            TimeoutError: If no code arrives within the timeout.
            ConnectionError: If the service is unreachable.
        """
        session = await self._ensure_session()
        url = f"{self.base_url}/code/{email_address}"
        params = {"wait": "true", "timeout": str(timeout)}

        try:
            async with session.get(
                url, params=params, timeout=aiohttp.ClientTimeout(total=timeout + 10)
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["code"]
                elif resp.status == 408:
                    raise TimeoutError(
                        f"No verification code received for {email_address} "
                        f"within {timeout}s"
                    )
                elif resp.status == 404:
                    raise TimeoutError(f"No code found for {email_address}")
                else:
                    text = await resp.text()
                    raise RuntimeError(
                        f"Unexpected response {resp.status}: {text}"
                    )
        except aiohttp.ClientError as e:
            raise ConnectionError(
                f"Cannot reach email verification service at {self.base_url}: {e}"
            ) from e

    async def get_code(self, email_address: str) -> Optional[str]:
        """
        Get the current verification code if one exists.

        Returns None if no code is available (does not wait).
        """
        session = await self._ensure_session()
        url = f"{self.base_url}/code/{email_address}"

        try:
            async with session.get(url) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data["code"]
                elif resp.status == 404:
                    return None
                else:
                    text = await resp.text()
                    raise RuntimeError(
                        f"Unexpected response {resp.status}: {text}"
                    )
        except aiohttp.ClientError as e:
            raise ConnectionError(
                f"Cannot reach email verification service at {self.base_url}: {e}"
            ) from e

    async def clear_code(self, email_address: str) -> bool:
        """
        Clear a used verification code.

        Returns True if a code was cleared, False if none existed.
        """
        session = await self._ensure_session()
        url = f"{self.base_url}/code/{email_address}"

        try:
            async with session.delete(url) as resp:
                if resp.status == 200:
                    return True
                elif resp.status == 404:
                    return False
                else:
                    text = await resp.text()
                    raise RuntimeError(
                        f"Unexpected response {resp.status}: {text}"
                    )
        except aiohttp.ClientError as e:
            raise ConnectionError(
                f"Cannot reach email verification service at {self.base_url}: {e}"
            ) from e

    async def health(self) -> bool:
        """Check if the service is healthy."""
        session = await self._ensure_session()
        try:
            async with session.get(f"{self.base_url}/health") as resp:
                return resp.status == 200
        except aiohttp.ClientError:
            return False
