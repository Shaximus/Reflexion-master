"""Tier 1: Local vision model CAPTCHA solver.

Uses a local OpenAI-compatible vision API (Qwen3-VL, LLaVA, etc.)
running on llama-server, vLLM, or similar.

Cost: $0 (local inference)
Speed: Fast (local GPU)
Reliability: Depends on model quality and availability
"""

import base64
import logging
import time

import httpx

logger = logging.getLogger(__name__)

DEFAULT_PROMPTS = {
    "funcaptcha": (
        "This is a CAPTCHA challenge image. The object needs to be rotated "
        "to the correct upright orientation. What angle in degrees (0-360) "
        "should it be rotated clockwise? Respond with ONLY the number."
    ),
    "recaptcha_v2": (
        "This is a CAPTCHA grid image. Identify which squares contain the "
        "requested object. List the square positions (1-9 for 3x3, 1-16 for 4x4) "
        "as comma-separated numbers. Respond with ONLY the numbers."
    ),
    "text": (
        "This image contains distorted text (CAPTCHA). "
        "What text does it show? Respond with ONLY the text, no explanation."
    ),
    "default": (
        "This is a CAPTCHA challenge. Describe what you see and provide "
        "the answer. Be concise — respond with ONLY the answer."
    ),
}


class LocalVisionError(Exception):
    pass


class LocalVisionSolver:
    """Solve CAPTCHAs using a local vision model."""

    def __init__(self, api_url: str = "http://localhost:8080/v1", model: str = None):
        self.api_url = api_url.rstrip("/")
        self.model = model  # None = use whatever the server has loaded
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=60.0)  # Vision inference can be slow
        return self._client

    @property
    def name(self) -> str:
        return "local"

    @property
    def cost_per_solve(self) -> float:
        return 0.0

    async def is_available(self) -> bool:
        """Check if the local model server is reachable."""
        try:
            client = await self._get_client()
            resp = await client.get(f"{self.api_url}/models", timeout=5.0)
            return resp.status_code == 200
        except (httpx.ConnectError, httpx.ConnectTimeout, OSError):
            return False

    async def solve(self, image_data: bytes, challenge_type: str = "funcaptcha", prompt: str | None = None) -> str:
        """
        Send image to local vision model for solving.

        Args:
            image_data: Raw image bytes (PNG/JPEG)
            challenge_type: Type of CAPTCHA for prompt selection
            prompt: Custom prompt (overrides default for challenge_type)

        Returns:
            Solver's answer string

        Raises:
            LocalVisionError: If the model is unavailable or returns an error
        """
        if prompt is None:
            prompt = DEFAULT_PROMPTS.get(challenge_type, DEFAULT_PROMPTS["default"])

        b64_image = base64.b64encode(image_data).decode("utf-8")

        # Detect image type from magic bytes
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            media_type = "image/png"
        elif image_data[:2] == b'\xff\xd8':
            media_type = "image/jpeg"
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            media_type = "image/webp"
        else:
            media_type = "image/png"  # Default assumption

        payload = {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:{media_type};base64,{b64_image}"
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        },
                    ],
                }
            ],
            "max_tokens": 100,
            "temperature": 0.1,  # Low temperature for deterministic answers
        }
        if self.model:
            payload["model"] = self.model

        try:
            client = await self._get_client()
            start = time.monotonic()
            resp = await client.post(
                f"{self.api_url}/chat/completions",
                json=payload,
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code != 200:
                raise LocalVisionError(f"Model returned {resp.status_code}: {resp.text[:200]}")

            data = resp.json()
            answer = data["choices"][0]["message"]["content"].strip()
            logger.info(f"Local vision solved in {latency_ms}ms: '{answer[:50]}'")
            return answer

        except (httpx.ConnectError, httpx.ConnectTimeout, OSError) as e:
            raise LocalVisionError(f"Local model unavailable: {e}")
        except (KeyError, IndexError) as e:
            raise LocalVisionError(f"Unexpected response format: {e}")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
