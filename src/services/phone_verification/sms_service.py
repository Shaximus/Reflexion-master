"""Phone Verification Service — unified SMS provider interface.

Wraps multiple SMS provider APIs behind a single async interface.
Handles provider selection, number rental lifecycle, and code waiting.
"""

import asyncio
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone, timedelta
from enum import Enum
from typing import Optional

from .providers.sms_activate import SMSActivateProvider, SMSActivateError
from .providers.five_sim import FiveSimProvider, FiveSimError
from .providers.daisy_sms import DaisySMSProvider, DaisySMSError

logger = logging.getLogger(__name__)


class SMSProvider(Enum):
    SMS_ACTIVATE = "sms_activate"
    FIVE_SIM = "five_sim"
    DAISY_SMS = "daisy_sms"


# Service name mapping between providers (they use different names).
# Key is our canonical name, value is per-provider name.
SERVICE_NAMES = {
    "twitter": {"sms_activate": "tw", "five_sim": "twitter", "daisy_sms": "tw"},
    "google": {"sms_activate": "go", "five_sim": "google", "daisy_sms": "go"},
    "facebook": {"sms_activate": "fb", "five_sim": "facebook", "daisy_sms": "fb"},
    "instagram": {"sms_activate": "ig", "five_sim": "instagram", "daisy_sms": "ig"},
    "whatsapp": {"sms_activate": "wa", "five_sim": "whatsapp", "daisy_sms": "wa"},
    "telegram": {"sms_activate": "tg", "five_sim": "telegram", "daisy_sms": "tg"},
    "discord": {"sms_activate": "ds", "five_sim": "discord", "daisy_sms": "ds"},
    "other": {"sms_activate": "ot", "five_sim": "any", "daisy_sms": "ot"},
}

# 5SIM uses "any" for unspecified country, SMS-Activate/Daisy use "0".
_FIVESIM_DEFAULT_COUNTRY = "any"


@dataclass
class PhoneRental:
    """Represents an active phone number rental."""

    number: str
    country: str
    provider: SMSProvider
    rental_id: str
    rented_at: datetime
    expires_at: datetime
    service: str

    @property
    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) >= self.expires_at

    @property
    def time_remaining(self) -> timedelta:
        remaining = self.expires_at - datetime.now(timezone.utc)
        return max(remaining, timedelta(0))


class PhoneVerificationError(Exception):
    """Base error for phone verification operations."""

    pass


class NoProvidersAvailableError(PhoneVerificationError):
    """No providers have numbers available."""

    pass


class PhoneVerificationService:
    """Unified phone verification service across multiple SMS providers.

    Provides a single async interface for renting phone numbers, polling for
    verification codes, and releasing rentals.  Automatically translates
    service names between provider-specific formats and handles the different
    method signatures of each provider (5SIM uses ``product`` / ``country`` /
    ``operator`` whereas SMS-Activate-compatible providers use ``service`` /
    ``country``).

    Usage::

        configs = {
            SMSProvider.SMS_ACTIVATE: {"api_key": "..."},
            SMSProvider.FIVE_SIM:     {"api_key": "..."},
            SMSProvider.DAISY_SMS:    {"api_key": "..."},
        }
        async with PhoneVerificationService(configs) as svc:
            rental = await svc.rent_number("twitter")
            code   = await svc.wait_for_code(rental, timeout=120)
            await svc.release_number(rental, success=True)
    """

    def __init__(self, providers: dict):
        """Initialize with provider configurations.

        Args:
            providers: Mapping of ``SMSProvider`` enum to config dicts.
                Each config dict must contain at least ``api_key``.

        Example::

            providers = {
                SMSProvider.SMS_ACTIVATE: {"api_key": "abc123"},
                SMSProvider.FIVE_SIM:     {"api_key": "def456"},
                SMSProvider.DAISY_SMS:    {"api_key": "ghi789"},
            }
        """
        self._configs = providers
        self._providers: dict[SMSProvider, object] = {}
        self._init_providers()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _init_providers(self):
        """Initialize provider clients from configs."""
        for provider, config in self._configs.items():
            api_key = config.get("api_key", "")
            if not api_key:
                logger.debug("Skipping %s — no api_key provided", provider.value)
                continue
            if provider == SMSProvider.SMS_ACTIVATE:
                self._providers[provider] = SMSActivateProvider(api_key)
            elif provider == SMSProvider.FIVE_SIM:
                self._providers[provider] = FiveSimProvider(api_key)
            elif provider == SMSProvider.DAISY_SMS:
                self._providers[provider] = DaisySMSProvider(api_key)
            logger.debug("Initialized provider %s", provider.value)

    def _get_service_name(self, service: str, provider: SMSProvider) -> str:
        """Translate a canonical service name to the provider-specific name."""
        canonical = service.lower()
        if canonical in SERVICE_NAMES:
            return SERVICE_NAMES[canonical].get(provider.value, service)
        # Pass through unknown/raw service codes unchanged.
        return service

    def _get_provider(self, provider: SMSProvider):
        """Return an initialized provider client or raise."""
        client = self._providers.get(provider)
        if client is None:
            raise PhoneVerificationError(
                f"Provider {provider.value} not configured or missing API key"
            )
        return client

    @staticmethod
    def _normalize_country_for_fivesim(country: str) -> str:
        """5SIM expects ``'any'`` instead of ``'0'`` for *any country*."""
        return _FIVESIM_DEFAULT_COUNTRY if country in ("0", "") else country

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def rent_number(
        self,
        service: str = "twitter",
        country: str = "0",
        preferred_provider: Optional[SMSProvider] = None,
        rental_minutes: int = 20,
    ) -> PhoneRental:
        """Rent a phone number for verification.

        Iterates over available providers (or a single preferred one) until a
        number is successfully obtained.  Provider-specific call signatures
        are handled transparently.

        Args:
            service: Canonical service name (``twitter``, ``google``, etc.)
                or a raw provider-specific code.
            country: Country code (``"0"`` or ``""`` means *any*).
            preferred_provider: Pin to a specific provider, or ``None`` to
                try all configured providers in order.
            rental_minutes: Tracking duration for the rental (does not
                affect the provider-side expiry).

        Returns:
            A :class:`PhoneRental` describing the rented number.

        Raises:
            NoProvidersAvailableError: If every provider fails.
            PhoneVerificationError: On unexpected failures.
        """
        if preferred_provider:
            providers_to_try = [preferred_provider]
        else:
            providers_to_try = list(self._providers.keys())

        if not providers_to_try:
            raise NoProvidersAvailableError("No providers configured")

        errors: list[str] = []

        for provider in providers_to_try:
            client = self._providers.get(provider)
            if client is None:
                continue

            svc_name = self._get_service_name(service, provider)

            try:
                # 5SIM has a different method signature:
                #   get_number(product, country, operator)
                # SMS-Activate / DaisySMS use:
                #   get_number(service, country)
                if provider == SMSProvider.FIVE_SIM:
                    fivesim_country = self._normalize_country_for_fivesim(country)
                    activation_id, phone = await client.get_number(
                        product=svc_name,
                        country=fivesim_country,
                    )
                else:
                    activation_id, phone = await client.get_number(
                        service=svc_name,
                        country=country,
                    )

                now = datetime.now(timezone.utc)
                rental = PhoneRental(
                    number=phone,
                    country=country,
                    provider=provider,
                    rental_id=activation_id,
                    rented_at=now,
                    expires_at=now + timedelta(minutes=rental_minutes),
                    service=service,
                )
                logger.info(
                    "Rented number ***%s from %s for %s (id=%s, expires=%s)",
                    phone[-4:],
                    provider.value,
                    service,
                    activation_id,
                    rental.expires_at.isoformat(),
                )
                return rental

            except (SMSActivateError, FiveSimError, DaisySMSError) as exc:
                msg = f"{provider.value}: {exc}"
                errors.append(msg)
                logger.warning("Provider %s failed to rent number: %s", provider.value, exc)
                continue
            except Exception as exc:
                msg = f"{provider.value}: unexpected — {exc}"
                errors.append(msg)
                logger.error(
                    "Unexpected error from %s while renting number: %s",
                    provider.value,
                    exc,
                    exc_info=True,
                )
                continue

        raise NoProvidersAvailableError(
            f"No providers could rent a number. Errors: {'; '.join(errors)}"
        )

    async def wait_for_code(
        self,
        rental: PhoneRental,
        timeout: int = 120,
        poll_interval: float = 3.0,
    ) -> str:
        """Poll for an incoming SMS verification code.

        Args:
            rental: An active :class:`PhoneRental` from :meth:`rent_number`.
            timeout: Maximum seconds to wait before giving up.
            poll_interval: Seconds between successive polls.

        Returns:
            The verification code as a string.

        Raises:
            TimeoutError: If no code is received within *timeout* seconds.
            PhoneVerificationError: If the rental is cancelled/expired or a
                provider error occurs.
        """
        client = self._get_provider(rental.provider)
        loop = asyncio.get_event_loop()
        deadline = loop.time() + timeout

        logger.info(
            "Waiting for code on ***%s (provider=%s, timeout=%ds, poll=%.1fs)",
            rental.number[-4:],
            rental.provider.value,
            timeout,
            poll_interval,
        )

        while loop.time() < deadline:
            try:
                status, code = await client.get_status(rental.rental_id)

                if status == "received" and code:
                    logger.info(
                        "Code received on ***%s: %s", rental.number[-4:], code
                    )
                    return code

                if status in ("cancelled", "expired"):
                    raise PhoneVerificationError(
                        f"Rental {rental.rental_id} was {status}"
                    )

                # "waiting", "waiting_retry", "waiting_resend" — keep polling
                logger.debug(
                    "Status for %s: %s (%.0fs remaining)",
                    rental.rental_id,
                    status,
                    deadline - loop.time(),
                )

            except (SMSActivateError, FiveSimError, DaisySMSError) as exc:
                raise PhoneVerificationError(
                    f"Provider error checking status: {exc}"
                ) from exc

            await asyncio.sleep(poll_interval)

        raise TimeoutError(
            f"No code received on ***{rental.number[-4:]} within {timeout}s"
        )

    async def release_number(self, rental: PhoneRental, success: bool = True):
        """Release a number rental.

        Args:
            rental: The :class:`PhoneRental` to release.
            success: ``True`` marks the verification as completed (number
                confirmed working). ``False`` cancels the rental.
        """
        client = self._get_provider(rental.provider)
        try:
            if success:
                await client.complete(rental.rental_id)
                logger.info(
                    "Completed rental %s on %s (success)",
                    rental.rental_id,
                    rental.provider.value,
                )
            else:
                await client.cancel(rental.rental_id)
                logger.info(
                    "Cancelled rental %s on %s",
                    rental.rental_id,
                    rental.provider.value,
                )
        except Exception as exc:
            logger.warning(
                "Error releasing rental %s on %s: %s",
                rental.rental_id,
                rental.provider.value,
                exc,
            )

    async def get_balance(self, provider: SMSProvider) -> float:
        """Check balance on a specific provider.

        Args:
            provider: Which provider to query.

        Returns:
            The current account balance as a float.
        """
        client = self._get_provider(provider)
        return await client.get_balance()

    async def get_all_balances(self) -> dict[SMSProvider, float]:
        """Check balances across all configured providers.

        Returns:
            Mapping of provider to balance.  A balance of ``-1.0`` indicates
            that the balance query failed for that provider.
        """
        results: dict[SMSProvider, float] = {}
        for provider, client in self._providers.items():
            try:
                results[provider] = await client.get_balance()
            except Exception as exc:
                logger.warning(
                    "Failed to get balance for %s: %s", provider.value, exc
                )
                results[provider] = -1.0
        return results

    async def get_prices(self, service: str = "twitter") -> dict[SMSProvider, dict]:
        """Get current prices across all providers for a service.

        Args:
            service: Canonical service name.

        Returns:
            Mapping of provider to its raw pricing dict.
        """
        results: dict[SMSProvider, dict] = {}
        for provider, client in self._providers.items():
            svc_name = self._get_service_name(service, provider)
            try:
                # 5SIM get_prices takes (product, country) with keyword names.
                # SMS-Activate / DaisySMS take (service, country).
                if provider == SMSProvider.FIVE_SIM:
                    prices = await client.get_prices(product=svc_name)
                else:
                    prices = await client.get_prices(service=svc_name)
                results[provider] = prices
            except Exception as exc:
                logger.warning(
                    "Failed to get prices from %s: %s", provider.value, exc
                )
        return results

    async def close(self):
        """Close all provider HTTP clients."""
        for provider, client in self._providers.items():
            try:
                await client.close()
            except Exception as exc:
                logger.debug(
                    "Error closing %s client: %s", provider.value, exc
                )

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
