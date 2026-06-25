"""Main orchestrator - wires all service modules into the account creation pipeline."""
from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

from .profile_generator import ProfileGenerator
from .signup_flow import SignupFlow, SignupResult

logger = logging.getLogger(__name__)


@dataclass
class PipelineConfig:
    """Configuration for the full account creation pipeline."""

    # Email
    email_service_url: str = "http://localhost:3010"
    email_domain: str = "reflexion.software"

    # Browser
    goLogin_api_token: Optional[str] = None
    headless: bool = False

    # SMS providers
    sms_activate_key: Optional[str] = None
    five_sim_key: Optional[str] = None
    daisy_sms_key: Optional[str] = None

    # CAPTCHA
    local_vision_url: Optional[str] = None  # e.g. http://localhost:8080/v1
    local_vision_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    capsolver_api_key: Optional[str] = None
    twocaptcha_api_key: Optional[str] = None

    # Redis
    redis_url: str = "redis://localhost:6379"
    redis_password: str = "ShaxAGI2025"

    # Pipeline
    buffer_per_soul: int = 3
    max_concurrent_signups: int = 2

    # Paths
    reflexion_root: str = "/home/shax/Projects/core-tech/Reflexion-master"

    @classmethod
    def from_env(cls) -> PipelineConfig:
        """Load configuration from environment variables."""
        return cls(
            email_service_url=os.getenv("EMAIL_SERVICE_URL", "http://localhost:3010"),
            email_domain=os.getenv("EMAIL_DOMAIN", "reflexion.software"),
            goLogin_api_token=os.getenv("GOLOGIN_API_TOKEN"),
            headless=os.getenv("PIPELINE_HEADLESS", "").lower() in ("1", "true"),
            sms_activate_key=os.getenv("SMS_ACTIVATE_KEY"),
            five_sim_key=os.getenv("FIVE_SIM_KEY"),
            daisy_sms_key=os.getenv("DAISY_SMS_KEY"),
            local_vision_url=os.getenv("LOCAL_VISION_URL"),
            local_vision_model=os.getenv("LOCAL_VISION_MODEL"),
            gemini_api_key=os.getenv("GEMINI_API_KEY"),
            capsolver_api_key=os.getenv("CAPSOLVER_API_KEY"),
            twocaptcha_api_key=os.getenv("TWOCAPTCHA_API_KEY"),
            redis_url=os.getenv("REDIS_URL", "redis://localhost:6379"),
            redis_password=os.getenv("REDIS_PASSWORD", "ShaxAGI2025"),
            buffer_per_soul=int(os.getenv("BUFFER_PER_SOUL", "3")),
            max_concurrent_signups=int(os.getenv("MAX_CONCURRENT_SIGNUPS", "2")),
            reflexion_root=os.getenv(
                "REFLEXION_ROOT",
                "/home/shax/Projects/core-tech/Reflexion-master",
            ),
        )


class AccountPipeline:
    """Main orchestrator wiring all service modules together.

    Usage:
        pipeline = AccountPipeline(PipelineConfig.from_env())
        await pipeline.initialize()
        result = await pipeline.create_account(region="US")
        await pipeline.start_daemons()  # background monitoring
        ...
        await pipeline.shutdown()
    """

    def __init__(self, config: Optional[PipelineConfig] = None):
        self.config = config or PipelineConfig.from_env()
        self.redis = None
        self.profile_gen: Optional[ProfileGenerator] = None
        self.profile_manager = None
        self.email_client = None
        self.captcha_solver = None
        self.phone_service = None
        self.scheduler = None
        self.health_monitor = None
        self.alert_manager = None
        self.scheduler_daemon = None
        self.monitor_daemon = None
        self.closed_loop = None
        self._running = False
        self._semaphore: Optional[asyncio.Semaphore] = None
        self.logger = logging.getLogger("account_pipeline")

    async def initialize(self) -> None:
        """Initialize all services. Must be called before any operations."""
        # 1. Connect Redis (async)
        import redis.asyncio as aioredis

        self.redis = aioredis.from_url(
            self.config.redis_url,
            password=self.config.redis_password,
            decode_responses=True,
        )
        await self.redis.ping()
        self.logger.info("Redis connected")

        # 2. Profile generator
        self.profile_gen = ProfileGenerator(email_domain=self.config.email_domain)

        # 3. Profile manager (browser profiles via stealth module)
        from services.browser_stealth import ProfileManager

        self.profile_manager = ProfileManager(
            redis_url=self.config.redis_url,
            redis_password=self.config.redis_password,
        )

        # 4. Email client
        from services.email_verification import EmailVerificationClient

        self.email_client = EmailVerificationClient(self.config.email_service_url)

        # 5. CAPTCHA solver
        from services.captcha_solver import CAPTCHAConfig, CAPTCHASolver

        self.captcha_solver = CAPTCHASolver(
            CAPTCHAConfig(
                local_vision_url=self.config.local_vision_url,
                local_vision_model=self.config.local_vision_model,
                gemini_api_key=self.config.gemini_api_key,
                capsolver_api_key=self.config.capsolver_api_key,
                twocaptcha_api_key=self.config.twocaptcha_api_key,
            )
        )

        # 6. Phone verification
        from services.phone_verification import PhoneVerificationService, SMSProvider

        providers = {}
        if self.config.sms_activate_key:
            providers[SMSProvider.SMS_ACTIVATE] = {
                "api_key": self.config.sms_activate_key
            }
        if self.config.five_sim_key:
            providers[SMSProvider.FIVE_SIM] = {"api_key": self.config.five_sim_key}
        if self.config.daisy_sms_key:
            providers[SMSProvider.DAISY_SMS] = {"api_key": self.config.daisy_sms_key}
        self.phone_service = (
            PhoneVerificationService(providers) if providers else None
        )

        # 7. Onboarding scheduler
        from services.onboarding import OnboardingScheduler, SchedulerDaemon

        self.scheduler = OnboardingScheduler(self.redis)
        self.scheduler_daemon = SchedulerDaemon(self.scheduler)

        # 8. Health monitor
        from services.health_monitor import (
            AccountHealthMonitor,
            AlertManager,
            MonitorDaemon,
        )

        self.health_monitor = AccountHealthMonitor(self.redis)
        self.alert_manager = AlertManager(self.redis)
        self.monitor_daemon = MonitorDaemon(self.health_monitor, self.alert_manager)

        # 9. Closed loop
        from .closed_loop import ClosedLoop

        self.closed_loop = ClosedLoop(
            redis_client=self.redis,
            scheduler=self.scheduler,
            health_monitor=self.health_monitor,
            alert_manager=self.alert_manager,
            pipeline=self,
            buffer_size=self.config.buffer_per_soul,
            reflexion_root=self.config.reflexion_root,
        )

        # 10. Concurrency semaphore
        self._semaphore = asyncio.Semaphore(self.config.max_concurrent_signups)

        self.logger.info("Pipeline initialized - all services wired")

    async def create_account(self, region: Optional[str] = None) -> SignupResult:
        """Create a single account end-to-end.

        1. Generate identity
        2. Create browser profile
        3. Launch stealth browser
        4. Run signup flow
        5. On success: register with onboarding + health monitor
        6. Return result
        """
        async with self._semaphore:
            # Generate identity
            identity = self.profile_gen.generate(region=region)
            self.logger.info(f"Creating account: {identity.email}")

            # Create browser profile
            browser_profile = self.profile_manager.create_profile(
                region=identity.region
            )

            # Launch browser
            from services.browser_stealth import HumanSimulator, StealthBrowser

            async with StealthBrowser(browser_profile) as browser:
                if self.config.goLogin_api_token:
                    page = await browser.connect_goLogin(
                        self.config.goLogin_api_token
                    )
                else:
                    page = await browser.connect_direct(
                        headless=self.config.headless
                    )

                human = HumanSimulator(page)

                # Run signup flow
                flow = SignupFlow(
                    browser=browser,
                    human=human,
                    email_client=self.email_client,
                    captcha_solver=self.captcha_solver,
                    phone_service=self.phone_service,
                )

                result = await flow.execute(identity)

            # Post-signup: register if successful
            if result.success and result.auth_token:
                # Register with onboarding scheduler
                await self.scheduler.register_account(
                    result.account_id,
                    metadata={
                        "email": identity.email,
                        "username": result.username,
                        "auth_token": result.auth_token,
                        "ct0": result.ct0,
                        "region": identity.region,
                        "created_at": datetime.utcnow().isoformat(),
                    },
                )

                # Register with health monitor
                await self.health_monitor.register_account(
                    result.account_id,
                    result.auth_token,
                )

                self.logger.info(
                    f"Account created and registered: "
                    f"{result.username} ({result.account_id})"
                )
            else:
                self.logger.warning(
                    f"Account creation failed at stage '{result.stage_reached}': "
                    f"{result.error}"
                )

            return result

    async def create_batch(
        self, count: int, region: Optional[str] = None
    ) -> List[SignupResult]:
        """Create multiple accounts concurrently (respecting semaphore)."""
        tasks = [self.create_account(region=region) for _ in range(count)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Convert exceptions to failed SignupResults
        processed = []
        for r in results:
            if isinstance(r, Exception):
                self.logger.error(f"Batch account creation exception: {r}")
                processed.append(
                    SignupResult(
                        success=False,
                        account_id="unknown",
                        identity=None,
                        error=str(r),
                        stage_reached="exception",
                    )
                )
            else:
                processed.append(r)
        return processed

    async def start_daemons(self) -> None:
        """Start background daemons (scheduler, health monitor, closed loop)."""
        self._running = True
        asyncio.create_task(self.scheduler_daemon.run())
        asyncio.create_task(self.monitor_daemon.run())
        await self.closed_loop.start()
        self.logger.info("All daemons started")

    async def stop_daemons(self) -> None:
        """Stop all background daemons."""
        self._running = False
        if self.scheduler_daemon:
            await self.scheduler_daemon.stop()
        if self.monitor_daemon:
            await self.monitor_daemon.stop()
        if self.closed_loop:
            await self.closed_loop.stop()
        self.logger.info("All daemons stopped")

    async def shutdown(self) -> None:
        """Graceful shutdown - stop daemons, close connections."""
        self.logger.info("Shutting down pipeline...")
        await self.stop_daemons()

        if self.email_client:
            await self.email_client.close()
        if self.captcha_solver:
            await self.captcha_solver.close()
        if self.phone_service:
            await self.phone_service.close()
        if self.redis:
            await self.redis.close()

        self.logger.info("Pipeline shut down")

    async def get_status(self) -> dict:
        """Get full pipeline status including all subsystems."""
        pool = (
            await self.closed_loop.get_pool_status() if self.closed_loop else None
        )
        health = (
            await self.health_monitor.get_status_summary()
            if self.health_monitor
            else None
        )
        solvers = (
            await self.captcha_solver.get_available_solvers()
            if self.captcha_solver
            else []
        )
        balances = (
            await self.phone_service.get_all_balances()
            if self.phone_service
            else {}
        )
        email_ok = (
            await self.email_client.health() if self.email_client else False
        )

        return {
            "running": self._running,
            "email_service": email_ok,
            "captcha_solvers": solvers,
            "sms_balances": {str(k): v for k, v in balances.items()},
            "pool": pool.__dict__ if pool else None,
            "health": health,
            "config": {
                "email_domain": self.config.email_domain,
                "headless": self.config.headless,
                "buffer_per_soul": self.config.buffer_per_soul,
                "max_concurrent_signups": self.config.max_concurrent_signups,
            },
        }
