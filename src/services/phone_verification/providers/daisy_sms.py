"""DaisySMS provider implementation.

DaisySMS uses the SMS-Activate compatible API format.
"""

import logging

from .sms_activate import SMSActivateProvider, SMSActivateError

logger = logging.getLogger(__name__)

# DaisySMS uses SMS-Activate compatible API with different base URL
DAISY_BASE_URL = "https://daisysms.com/stubs/handler_api.php"


class DaisySMSError(SMSActivateError):
    """DaisySMS-specific error."""
    pass


class DaisySMSProvider(SMSActivateProvider):
    """
    DaisySMS provider. Inherits from SMSActivateProvider since
    DaisySMS uses the same API format as SMS-Activate.
    """

    def __init__(self, api_key: str):
        super().__init__(api_key)

    async def _request(self, params: dict) -> str:
        """Override to use DaisySMS base URL."""
        from .sms_activate import ERRORS
        client = await self._get_client()
        params["api_key"] = self.api_key
        resp = await client.get(DAISY_BASE_URL, params=params)
        resp.raise_for_status()
        text = resp.text.strip()
        if text in ERRORS:
            raise DaisySMSError(text)
        return text

    async def get_prices(self, service: str = "tw", country: str | None = None) -> dict:
        """Get prices - DaisySMS returns JSON format."""
        params = {"action": "getPrices", "service": service}
        if country is not None:
            params["country"] = country
        client = await self._get_client()
        params["api_key"] = self.api_key
        resp = await client.get(DAISY_BASE_URL, params=params)
        resp.raise_for_status()
        return resp.json()
