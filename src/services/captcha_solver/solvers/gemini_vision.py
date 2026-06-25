"""Tier 2: Gemini Vision API CAPTCHA solver.

Uses Google's Gemini 2.5 Pro with vision for image-based CAPTCHA solving.

Cost: ~$0.001-0.003 per solve (API pricing)
Speed: 2-5 seconds
Reliability: Good for image recognition tasks
"""

import base64
import logging
import time

import httpx

logger = logging.getLogger(__name__)

# Gemini REST API (avoids heavy google-generativeai SDK dependency)
GEMINI_API_URL = "https://generativelanguage.googleapis.com/v1beta/models"
DEFAULT_MODEL = "gemini-2.5-pro-preview-06-05"

DEFAULT_PROMPTS = {
    "funcaptcha": (
        "This is a CAPTCHA challenge. The object in the image needs to be "
        "rotated to its correct upright orientation. What angle in degrees "
        "(0-360) should it be rotated clockwise to appear correct? "
        "Respond with ONLY the number, nothing else."
    ),
    "recaptcha_v2": (
        "This is a CAPTCHA image grid. Identify which squares contain the "
        "requested object. List the positions as comma-separated numbers "
        "(1-based, left-to-right, top-to-bottom). Respond with ONLY the numbers."
    ),
    "text": (
        "This image contains distorted text used as a CAPTCHA. "
        "What text does it show? Respond with ONLY the text."
    ),
    "default": (
        "This is a CAPTCHA challenge image. Analyze it and provide the answer. "
        "Respond with ONLY the answer, no explanation."
    ),
}


class GeminiVisionError(Exception):
    pass


class GeminiVisionSolver:
    """Solve CAPTCHAs using Google Gemini vision API."""

    def __init__(self, api_key: str, model: str = DEFAULT_MODEL):
        self.api_key = api_key
        self.model = model
        self._client: httpx.AsyncClient | None = None

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(timeout=30.0)
        return self._client

    @property
    def name(self) -> str:
        return "gemini"

    @property
    def cost_per_solve(self) -> float:
        return 0.002  # Rough estimate

    async def is_available(self) -> bool:
        """Check if API key is set."""
        return bool(self.api_key)

    async def solve(self, image_data: bytes, challenge_type: str = "funcaptcha", prompt: str | None = None) -> str:
        """
        Send image to Gemini for solving.

        Args:
            image_data: Raw image bytes
            challenge_type: For prompt selection
            prompt: Custom prompt override

        Returns:
            Answer string

        Raises:
            GeminiVisionError on API failure
        """
        if prompt is None:
            prompt = DEFAULT_PROMPTS.get(challenge_type, DEFAULT_PROMPTS["default"])

        b64_image = base64.b64encode(image_data).decode("utf-8")

        # Detect MIME type
        if image_data[:8] == b'\x89PNG\r\n\x1a\n':
            mime = "image/png"
        elif image_data[:2] == b'\xff\xd8':
            mime = "image/jpeg"
        elif image_data[:4] == b'RIFF' and image_data[8:12] == b'WEBP':
            mime = "image/webp"
        else:
            mime = "image/png"

        payload = {
            "contents": [
                {
                    "parts": [
                        {
                            "inline_data": {
                                "mime_type": mime,
                                "data": b64_image,
                            }
                        },
                        {"text": prompt},
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.1,
                "maxOutputTokens": 100,
            },
        }

        url = f"{GEMINI_API_URL}/{self.model}:generateContent?key={self.api_key}"

        try:
            client = await self._get_client()
            start = time.monotonic()
            resp = await client.post(url, json=payload)
            latency_ms = int((time.monotonic() - start) * 1000)

            if resp.status_code == 429:
                raise GeminiVisionError("Rate limited by Gemini API")
            if resp.status_code == 403:
                raise GeminiVisionError("Gemini API key invalid or quota exceeded")
            if resp.status_code != 200:
                raise GeminiVisionError(f"Gemini API error {resp.status_code}: {resp.text[:300]}")

            data = resp.json()
            candidates = data.get("candidates", [])
            if not candidates:
                raise GeminiVisionError("No candidates in Gemini response")

            content = candidates[0].get("content", {})
            parts = content.get("parts", [])
            if not parts:
                raise GeminiVisionError("Empty response from Gemini")

            answer = parts[0].get("text", "").strip()
            logger.info(f"Gemini solved in {latency_ms}ms: '{answer[:50]}'")
            return answer

        except httpx.HTTPError as e:
            raise GeminiVisionError(f"HTTP error calling Gemini: {e}")

    async def close(self):
        if self._client and not self._client.is_closed:
            await self._client.aclose()
            self._client = None

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        await self.close()
