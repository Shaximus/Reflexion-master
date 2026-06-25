"""CAPTCHA Solver — tiered fallback chain.

Tries solvers in order of cost (cheapest first):
  Tier 1: Local Vision Model (free)
  Tier 2: Gemini Vision API (~$0.002)
  Tier 3: CapSolver (~$0.002)
  Tier 4: 2Captcha (~$0.003)

Falls through to next tier on failure.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Optional

from .solvers.local_vision import LocalVisionSolver, LocalVisionError
from .solvers.gemini_vision import GeminiVisionSolver, GeminiVisionError
from .solvers.capsolver import CapSolverClient, CapSolverError
from .solvers.twocaptcha import TwoCaptchaSolver, TwoCaptchaError

logger = logging.getLogger(__name__)


@dataclass
class CAPTCHAConfig:
    """Configuration for available solvers."""
    local_vision_url: Optional[str] = None      # e.g., "http://localhost:8080/v1"
    local_vision_model: Optional[str] = None
    gemini_api_key: Optional[str] = None
    capsolver_api_key: Optional[str] = None
    twocaptcha_api_key: Optional[str] = None


@dataclass
class CAPTCHAChallenge:
    """Represents a CAPTCHA challenge to solve."""
    type: str                                    # "funcaptcha", "recaptcha_v2", "turnstile", "hcaptcha", "text"
    image_data: Optional[bytes] = None           # Screenshot of challenge (for vision solvers)
    public_key: Optional[str] = None             # Site key (for token-based solvers)
    page_url: str = ""
    prompt: Optional[str] = None                 # Custom prompt for vision solvers
    metadata: dict = field(default_factory=dict)


@dataclass
class CAPTCHASolution:
    """Result from a successful solve."""
    answer: str
    solver_used: str                             # "local", "gemini", "capsolver", "2captcha"
    confidence: float                            # 0.0-1.0
    cost: float                                  # Estimated cost in USD
    latency_ms: int


class AllSolversFailedError(Exception):
    """All solver tiers failed."""
    def __init__(self, errors: list):
        self.errors = errors
        detail = "; ".join(f"{e[0]}: {e[1]}" for e in errors)
        super().__init__(f"All solvers failed: {detail}")


class CAPTCHASolver:
    """Main solver with tiered fallback chain."""

    def __init__(self, config: CAPTCHAConfig):
        self.config = config
        self._solvers = []
        self._init_solvers()

    def _init_solvers(self):
        """Initialize available solvers in tier order."""
        # Tier 1: Local Vision
        if self.config.local_vision_url:
            self._solvers.append(
                LocalVisionSolver(
                    api_url=self.config.local_vision_url,
                    model=self.config.local_vision_model,
                )
            )

        # Tier 2: Gemini Vision
        if self.config.gemini_api_key:
            self._solvers.append(
                GeminiVisionSolver(api_key=self.config.gemini_api_key)
            )

        # Tier 3: CapSolver
        if self.config.capsolver_api_key:
            self._solvers.append(
                CapSolverClient(api_key=self.config.capsolver_api_key)
            )

        # Tier 4: 2Captcha
        if self.config.twocaptcha_api_key:
            self._solvers.append(
                TwoCaptchaSolver(api_key=self.config.twocaptcha_api_key)
            )

    def _can_handle(self, solver, challenge: CAPTCHAChallenge) -> bool:
        """Check if a solver can handle this challenge type."""
        # Vision solvers need image data
        if isinstance(solver, (LocalVisionSolver, GeminiVisionSolver)):
            return challenge.image_data is not None
        # Token-based solvers need public_key or image_data
        if isinstance(solver, (CapSolverClient, TwoCaptchaSolver)):
            return challenge.public_key is not None or challenge.image_data is not None
        return False

    # Confidence heuristics per solver
    _CONFIDENCE = {
        "local": 0.5,      # Local models are hit or miss on CAPTCHAs
        "gemini": 0.7,     # Good vision model
        "capsolver": 0.9,  # Commercial service, high reliability
        "2captcha": 0.95,  # Human workers, highest reliability
    }

    async def solve(self, challenge: CAPTCHAChallenge) -> CAPTCHASolution:
        """
        Try solvers in order of cost (cheapest first).
        Falls through to next tier on failure.

        Args:
            challenge: CAPTCHAChallenge with image_data and/or public_key

        Returns:
            CAPTCHASolution with answer and metadata

        Raises:
            AllSolversFailedError: If all configured solvers fail
        """
        errors = []

        for solver in self._solvers:
            if not self._can_handle(solver, challenge):
                continue

            name = solver.name
            try:
                # Check availability
                if hasattr(solver, "is_available"):
                    available = await solver.is_available()
                    if not available:
                        errors.append((name, "not available"))
                        logger.debug(f"Solver {name} not available, skipping")
                        continue

                logger.info(f"Trying solver: {name}")
                start = time.monotonic()

                # Build kwargs based on what the challenge provides
                kwargs = {}
                if challenge.image_data is not None:
                    kwargs["image_data"] = challenge.image_data
                kwargs["challenge_type"] = challenge.type
                if challenge.prompt:
                    kwargs["prompt"] = challenge.prompt
                if challenge.public_key:
                    kwargs["public_key"] = challenge.public_key
                if challenge.page_url:
                    kwargs["page_url"] = challenge.page_url
                kwargs.update(challenge.metadata)

                answer = await solver.solve(**kwargs)
                latency_ms = int((time.monotonic() - start) * 1000)

                if not answer:
                    errors.append((name, "empty answer"))
                    continue

                solution = CAPTCHASolution(
                    answer=answer,
                    solver_used=name,
                    confidence=self._CONFIDENCE.get(name, 0.5),
                    cost=solver.cost_per_solve,
                    latency_ms=latency_ms,
                )
                logger.info(
                    f"Solved by {name} in {latency_ms}ms "
                    f"(cost=${solution.cost:.4f}, confidence={solution.confidence})"
                )
                return solution

            except (LocalVisionError, GeminiVisionError, CapSolverError, TwoCaptchaError) as e:
                errors.append((name, str(e)))
                logger.warning(f"Solver {name} failed: {e}")
                continue
            except Exception as e:
                errors.append((name, str(e)))
                logger.error(f"Unexpected error from {name}: {e}")
                continue

        raise AllSolversFailedError(errors)

    async def solve_image(self, image_path: str, challenge_type: str = "funcaptcha") -> str:
        """
        Convenience: solve from image file.

        Args:
            image_path: Path to CAPTCHA image file
            challenge_type: Type of CAPTCHA

        Returns:
            Answer string
        """
        with open(image_path, "rb") as f:
            image_data = f.read()

        challenge = CAPTCHAChallenge(
            type=challenge_type,
            image_data=image_data,
        )
        solution = await self.solve(challenge)
        return solution.answer

    async def solve_arkose(self, public_key: str, page_url: str) -> str:
        """
        Convenience: solve Arkose FunCaptcha token-based.

        Only uses token-based solvers (CapSolver, 2Captcha).
        """
        challenge = CAPTCHAChallenge(
            type="funcaptcha",
            public_key=public_key,
            page_url=page_url,
        )
        solution = await self.solve(challenge)
        return solution.answer

    async def get_available_solvers(self) -> list[str]:
        """List currently available solver names."""
        available = []
        for solver in self._solvers:
            if hasattr(solver, "is_available") and await solver.is_available():
                available.append(solver.name)
            elif not hasattr(solver, "is_available"):
                available.append(solver.name)
        return available

    async def close(self):
        """Close all solver clients."""
        for solver in self._solvers:
            try:
                await solver.close()
            except Exception:
                pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
