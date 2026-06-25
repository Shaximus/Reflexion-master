"""
Profile Manager - Browser fingerprint profile generation, storage, and management.
Each profile is an internally-consistent fingerprint spanning UA, GPU, screen, timezone,
language, fonts, and hardware specs.
"""

import json
import os
import random
import hashlib
import uuid
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import List, Optional, Dict, Any

import redis

PROFILES_DIR = Path(__file__).parent / "profiles"
TEMPLATES_DIR = PROFILES_DIR / "templates"


@dataclass
class BrowserProfile:
    profile_id: str
    name: str
    user_agent: str
    screen: Dict[str, int]          # width, height, colorDepth, pixelDepth
    viewport: Dict[str, int]        # width, height
    timezone: str                   # IANA timezone, must match proxy geo
    languages: List[str]            # must match timezone region
    geolocation: Dict[str, float]   # lat, lon, accuracy - must match proxy
    webgl_vendor: str               # must match claimed device
    webgl_renderer: str             # must match claimed device
    device_memory: int              # 4, 8, or 16
    hardware_concurrency: int       # 2, 4, 8
    platform: str                   # Win32, MacIntel, Linux x86_64
    fonts: List[str]                # must match claimed OS
    proxy: Dict[str, str] = field(default_factory=dict)  # server, username, password
    # Client Hints fields
    ua_brands: List[Dict[str, str]] = field(default_factory=list)
    ua_platform: str = ""
    ua_platform_version: str = ""
    ua_architecture: str = "x86"
    ua_full_version_list: List[Dict[str, str]] = field(default_factory=list)
    vendor: str = "Google Inc."
    canvas_seed: int = 0

    def __post_init__(self):
        if not self.canvas_seed:
            self.canvas_seed = int(hashlib.md5(self.profile_id.encode()).hexdigest()[:8], 16)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "BrowserProfile":
        return cls(**{k: v for k, v in data.items() if k in cls.__dataclass_fields__})

    def validate_consistency(self) -> List[str]:
        """Check internal consistency. Returns list of warnings."""
        warnings = []
        ua_lower = self.user_agent.lower()

        # UA <-> platform
        if "windows" in ua_lower and self.platform != "Win32":
            warnings.append(f"UA says Windows but platform is {self.platform}")
        if "macintosh" in ua_lower and self.platform != "MacIntel":
            warnings.append(f"UA says Mac but platform is {self.platform}")
        if "linux" in ua_lower and "Linux" not in self.platform:
            warnings.append(f"UA says Linux but platform is {self.platform}")

        # WebGL vendor <-> platform
        if self.platform == "MacIntel" and "Apple" not in self.webgl_vendor:
            warnings.append(f"Mac platform but WebGL vendor is {self.webgl_vendor}")

        # Screen >= viewport
        if self.viewport["width"] > self.screen["width"]:
            warnings.append("Viewport width exceeds screen width")
        if self.viewport["height"] > self.screen["height"]:
            warnings.append("Viewport height exceeds screen height")

        # Device memory in valid set
        if self.device_memory not in (2, 4, 8, 16):
            warnings.append(f"Unusual device_memory: {self.device_memory}")

        return warnings


# =============================================================================
# BUILT-IN PROFILE TEMPLATES
# =============================================================================

PROFILE_TEMPLATES: List[Dict[str, Any]] = [
    # ---- WINDOWS 10 / CHROME ----
    {
        "name": "Win10 Chrome 1080p GTX1650",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "screen": {"width": 1920, "height": 1080, "colorDepth": 24, "pixelDepth": 24},
        "viewport": {"width": 1920, "height": 969},
        "timezone": "America/New_York",
        "languages": ["en-US", "en"],
        "geolocation": {"lat": 40.7128, "lon": -74.0060, "accuracy": 100},
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1650 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "device_memory": 8,
        "hardware_concurrency": 8,
        "platform": "Win32",
        "fonts": ["Arial", "Calibri", "Cambria", "Consolas", "Courier New", "Georgia", "Segoe UI", "Tahoma", "Times New Roman", "Verdana"],
        "vendor": "Google Inc.",
        "ua_brands": [{"brand": "Chromium", "version": "131"}, {"brand": "Google Chrome", "version": "131"}, {"brand": "Not_A Brand", "version": "24"}],
        "ua_platform": "Windows",
        "ua_platform_version": "10.0.0",
        "ua_architecture": "x86",
        "ua_full_version_list": [{"brand": "Chromium", "version": "131.0.6778.86"}, {"brand": "Google Chrome", "version": "131.0.6778.86"}, {"brand": "Not_A Brand", "version": "24.0.0.0"}],
    },
    {
        "name": "Win10 Chrome 768p UHD620",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "screen": {"width": 1366, "height": 768, "colorDepth": 24, "pixelDepth": 24},
        "viewport": {"width": 1366, "height": 657},
        "timezone": "America/Chicago",
        "languages": ["en-US", "en"],
        "geolocation": {"lat": 41.8781, "lon": -87.6298, "accuracy": 150},
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11-27.20.100.8681)",
        "device_memory": 8,
        "hardware_concurrency": 4,
        "platform": "Win32",
        "fonts": ["Arial", "Calibri", "Cambria", "Consolas", "Courier New", "Georgia", "Segoe UI", "Tahoma", "Times New Roman", "Verdana"],
        "vendor": "Google Inc.",
        "ua_brands": [{"brand": "Chromium", "version": "131"}, {"brand": "Google Chrome", "version": "131"}, {"brand": "Not_A Brand", "version": "24"}],
        "ua_platform": "Windows",
        "ua_platform_version": "10.0.0",
        "ua_architecture": "x86",
        "ua_full_version_list": [{"brand": "Chromium", "version": "131.0.6778.86"}, {"brand": "Google Chrome", "version": "131.0.6778.86"}, {"brand": "Not_A Brand", "version": "24.0.0.0"}],
    },
    # ---- WINDOWS 11 / CHROME ----
    {
        "name": "Win11 Chrome 1440p RTX4070",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "screen": {"width": 2560, "height": 1440, "colorDepth": 24, "pixelDepth": 24},
        "viewport": {"width": 2560, "height": 1329},
        "timezone": "America/Los_Angeles",
        "languages": ["en-US", "en"],
        "geolocation": {"lat": 34.0522, "lon": -118.2437, "accuracy": 100},
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 4070 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "device_memory": 16,
        "hardware_concurrency": 8,
        "platform": "Win32",
        "fonts": ["Arial", "Calibri", "Cambria", "Consolas", "Courier New", "Georgia", "Segoe UI", "Segoe UI Variable", "Tahoma", "Times New Roman", "Verdana"],
        "vendor": "Google Inc.",
        "ua_brands": [{"brand": "Chromium", "version": "132"}, {"brand": "Google Chrome", "version": "132"}, {"brand": "Not_A Brand", "version": "24"}],
        "ua_platform": "Windows",
        "ua_platform_version": "15.0.0",
        "ua_architecture": "x86",
        "ua_full_version_list": [{"brand": "Chromium", "version": "132.0.6834.57"}, {"brand": "Google Chrome", "version": "132.0.6834.57"}, {"brand": "Not_A Brand", "version": "24.0.0.0"}],
    },
    # ---- WINDOWS 11 / EDGE ----
    {
        "name": "Win11 Edge 1080p AMD RX580",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36 Edg/131.0.2903.86",
        "screen": {"width": 1920, "height": 1080, "colorDepth": 24, "pixelDepth": 24},
        "viewport": {"width": 1920, "height": 969},
        "timezone": "America/Denver",
        "languages": ["en-US", "en"],
        "geolocation": {"lat": 39.7392, "lon": -104.9903, "accuracy": 100},
        "webgl_vendor": "Google Inc. (AMD)",
        "webgl_renderer": "ANGLE (AMD, AMD Radeon RX 580 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "device_memory": 8,
        "hardware_concurrency": 8,
        "platform": "Win32",
        "fonts": ["Arial", "Calibri", "Cambria", "Consolas", "Courier New", "Georgia", "Segoe UI", "Tahoma", "Times New Roman", "Verdana"],
        "vendor": "Google Inc.",
        "ua_brands": [{"brand": "Chromium", "version": "131"}, {"brand": "Microsoft Edge", "version": "131"}, {"brand": "Not_A Brand", "version": "24"}],
        "ua_platform": "Windows",
        "ua_platform_version": "15.0.0",
        "ua_architecture": "x86",
        "ua_full_version_list": [{"brand": "Chromium", "version": "131.0.6778.86"}, {"brand": "Microsoft Edge", "version": "131.0.2903.86"}, {"brand": "Not_A Brand", "version": "24.0.0.0"}],
    },
    # ---- WINDOWS 10 / CHROME / 4GB budget laptop ----
    {
        "name": "Win10 Chrome Budget Laptop",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "screen": {"width": 1366, "height": 768, "colorDepth": 24, "pixelDepth": 24},
        "viewport": {"width": 1366, "height": 657},
        "timezone": "America/New_York",
        "languages": ["en-US", "en"],
        "geolocation": {"lat": 42.3601, "lon": -71.0589, "accuracy": 200},
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "ANGLE (Intel, Intel(R) HD Graphics 520 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "device_memory": 4,
        "hardware_concurrency": 4,
        "platform": "Win32",
        "fonts": ["Arial", "Calibri", "Cambria", "Consolas", "Courier New", "Georgia", "Segoe UI", "Tahoma", "Times New Roman", "Verdana"],
        "vendor": "Google Inc.",
        "ua_brands": [{"brand": "Chromium", "version": "130"}, {"brand": "Google Chrome", "version": "130"}, {"brand": "Not_A Brand", "version": "24"}],
        "ua_platform": "Windows",
        "ua_platform_version": "10.0.0",
        "ua_architecture": "x86",
        "ua_full_version_list": [{"brand": "Chromium", "version": "130.0.6723.92"}, {"brand": "Google Chrome", "version": "130.0.6723.92"}, {"brand": "Not_A Brand", "version": "24.0.0.0"}],
    },
    # ---- macOS / CHROME ----
    {
        "name": "macOS Chrome M1 Pro",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "screen": {"width": 2560, "height": 1600, "colorDepth": 30, "pixelDepth": 30},
        "viewport": {"width": 1440, "height": 821},
        "timezone": "America/Los_Angeles",
        "languages": ["en-US", "en"],
        "geolocation": {"lat": 37.7749, "lon": -122.4194, "accuracy": 100},
        "webgl_vendor": "Google Inc. (Apple)",
        "webgl_renderer": "ANGLE (Apple, Apple M1 Pro, OpenGL 4.1)",
        "device_memory": 8,
        "hardware_concurrency": 10,
        "platform": "MacIntel",
        "fonts": ["Arial", "Courier", "Courier New", "Geneva", "Georgia", "Helvetica", "Helvetica Neue", "Lucida Grande", "Monaco", "Palatino", "San Francisco", "Times", "Times New Roman", "Trebuchet MS", "Verdana"],
        "vendor": "Google Inc.",
        "ua_brands": [{"brand": "Chromium", "version": "131"}, {"brand": "Google Chrome", "version": "131"}, {"brand": "Not_A Brand", "version": "24"}],
        "ua_platform": "macOS",
        "ua_platform_version": "14.7.0",
        "ua_architecture": "arm",
        "ua_full_version_list": [{"brand": "Chromium", "version": "131.0.6778.86"}, {"brand": "Google Chrome", "version": "131.0.6778.86"}, {"brand": "Not_A Brand", "version": "24.0.0.0"}],
    },
    {
        "name": "macOS Chrome Intel iMac",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
        "screen": {"width": 2560, "height": 1440, "colorDepth": 30, "pixelDepth": 30},
        "viewport": {"width": 1440, "height": 821},
        "timezone": "America/New_York",
        "languages": ["en-US", "en"],
        "geolocation": {"lat": 40.7128, "lon": -74.0060, "accuracy": 100},
        "webgl_vendor": "Google Inc. (AMD)",
        "webgl_renderer": "ANGLE (AMD, AMD Radeon Pro 5500 XT OpenGL Engine, OpenGL 4.1)",
        "device_memory": 8,
        "hardware_concurrency": 8,
        "platform": "MacIntel",
        "fonts": ["Arial", "Courier", "Courier New", "Geneva", "Georgia", "Helvetica", "Helvetica Neue", "Lucida Grande", "Monaco", "Palatino", "San Francisco", "Times", "Times New Roman", "Trebuchet MS", "Verdana"],
        "vendor": "Google Inc.",
        "ua_brands": [{"brand": "Chromium", "version": "130"}, {"brand": "Google Chrome", "version": "130"}, {"brand": "Not_A Brand", "version": "24"}],
        "ua_platform": "macOS",
        "ua_platform_version": "14.5.0",
        "ua_architecture": "x86",
        "ua_full_version_list": [{"brand": "Chromium", "version": "130.0.6723.92"}, {"brand": "Google Chrome", "version": "130.0.6723.92"}, {"brand": "Not_A Brand", "version": "24.0.0.0"}],
    },
    # ---- macOS / SAFARI ----
    {
        "name": "macOS Safari M2",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_7_1) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.1 Safari/605.1.15",
        "screen": {"width": 2560, "height": 1664, "colorDepth": 30, "pixelDepth": 30},
        "viewport": {"width": 1440, "height": 821},
        "timezone": "America/Chicago",
        "languages": ["en-US", "en"],
        "geolocation": {"lat": 41.8781, "lon": -87.6298, "accuracy": 100},
        "webgl_vendor": "Apple Inc.",
        "webgl_renderer": "Apple M2",
        "device_memory": 8,
        "hardware_concurrency": 8,
        "platform": "MacIntel",
        "fonts": ["Arial", "Courier", "Courier New", "Geneva", "Georgia", "Helvetica", "Helvetica Neue", "Lucida Grande", "Monaco", "Palatino", "San Francisco", "Times", "Times New Roman", "Trebuchet MS", "Verdana"],
        "vendor": "Apple Computer, Inc.",
        "ua_brands": [],
        "ua_platform": "macOS",
        "ua_platform_version": "14.7.1",
        "ua_architecture": "arm",
        "ua_full_version_list": [],
    },
    # ---- WINDOWS 11 / CHROME / 16GB Desktop ----
    {
        "name": "Win11 Chrome RTX3080 1440p",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "screen": {"width": 2560, "height": 1440, "colorDepth": 24, "pixelDepth": 24},
        "viewport": {"width": 2560, "height": 1329},
        "timezone": "America/Phoenix",
        "languages": ["en-US", "en"],
        "geolocation": {"lat": 33.4484, "lon": -112.0740, "accuracy": 100},
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce RTX 3080 Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "device_memory": 16,
        "hardware_concurrency": 16,
        "platform": "Win32",
        "fonts": ["Arial", "Calibri", "Cambria", "Consolas", "Courier New", "Georgia", "Segoe UI", "Segoe UI Variable", "Tahoma", "Times New Roman", "Verdana"],
        "vendor": "Google Inc.",
        "ua_brands": [{"brand": "Chromium", "version": "131"}, {"brand": "Google Chrome", "version": "131"}, {"brand": "Not_A Brand", "version": "24"}],
        "ua_platform": "Windows",
        "ua_platform_version": "15.0.0",
        "ua_architecture": "x86",
        "ua_full_version_list": [{"brand": "Chromium", "version": "131.0.6778.86"}, {"brand": "Google Chrome", "version": "131.0.6778.86"}, {"brand": "Not_A Brand", "version": "24.0.0.0"}],
    },
    # ---- WINDOWS 10 / CHROME / Canada ----
    {
        "name": "Win10 Chrome Canada GTX1060",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "screen": {"width": 1920, "height": 1080, "colorDepth": 24, "pixelDepth": 24},
        "viewport": {"width": 1920, "height": 969},
        "timezone": "America/Toronto",
        "languages": ["en-CA", "en-US", "en"],
        "geolocation": {"lat": 43.6532, "lon": -79.3832, "accuracy": 100},
        "webgl_vendor": "Google Inc. (NVIDIA)",
        "webgl_renderer": "ANGLE (NVIDIA, NVIDIA GeForce GTX 1060 6GB Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "device_memory": 8,
        "hardware_concurrency": 8,
        "platform": "Win32",
        "fonts": ["Arial", "Calibri", "Cambria", "Consolas", "Courier New", "Georgia", "Segoe UI", "Tahoma", "Times New Roman", "Verdana"],
        "vendor": "Google Inc.",
        "ua_brands": [{"brand": "Chromium", "version": "131"}, {"brand": "Google Chrome", "version": "131"}, {"brand": "Not_A Brand", "version": "24"}],
        "ua_platform": "Windows",
        "ua_platform_version": "10.0.0",
        "ua_architecture": "x86",
        "ua_full_version_list": [{"brand": "Chromium", "version": "131.0.6778.86"}, {"brand": "Google Chrome", "version": "131.0.6778.86"}, {"brand": "Not_A Brand", "version": "24.0.0.0"}],
    },
    # ---- WINDOWS 10 / CHROME / UK ----
    {
        "name": "Win10 Chrome UK Intel Iris",
        "user_agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "screen": {"width": 1920, "height": 1080, "colorDepth": 24, "pixelDepth": 24},
        "viewport": {"width": 1536, "height": 754},
        "timezone": "Europe/London",
        "languages": ["en-GB", "en"],
        "geolocation": {"lat": 51.5074, "lon": -0.1278, "accuracy": 100},
        "webgl_vendor": "Google Inc. (Intel)",
        "webgl_renderer": "ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11 vs_5_0 ps_5_0, D3D11)",
        "device_memory": 8,
        "hardware_concurrency": 8,
        "platform": "Win32",
        "fonts": ["Arial", "Calibri", "Cambria", "Consolas", "Courier New", "Georgia", "Segoe UI", "Tahoma", "Times New Roman", "Verdana"],
        "vendor": "Google Inc.",
        "ua_brands": [{"brand": "Chromium", "version": "131"}, {"brand": "Google Chrome", "version": "131"}, {"brand": "Not_A Brand", "version": "24"}],
        "ua_platform": "Windows",
        "ua_platform_version": "10.0.0",
        "ua_architecture": "x86",
        "ua_full_version_list": [{"brand": "Chromium", "version": "131.0.6778.86"}, {"brand": "Google Chrome", "version": "131.0.6778.86"}, {"brand": "Not_A Brand", "version": "24.0.0.0"}],
    },
    # ---- macOS / CHROME / Germany ----
    {
        "name": "macOS Chrome M3 Germany",
        "user_agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/132.0.0.0 Safari/537.36",
        "screen": {"width": 2560, "height": 1600, "colorDepth": 30, "pixelDepth": 30},
        "viewport": {"width": 1440, "height": 821},
        "timezone": "Europe/Berlin",
        "languages": ["de-DE", "de", "en-US", "en"],
        "geolocation": {"lat": 52.5200, "lon": 13.4050, "accuracy": 100},
        "webgl_vendor": "Google Inc. (Apple)",
        "webgl_renderer": "ANGLE (Apple, Apple M3, OpenGL 4.1)",
        "device_memory": 8,
        "hardware_concurrency": 8,
        "platform": "MacIntel",
        "fonts": ["Arial", "Courier", "Courier New", "Geneva", "Georgia", "Helvetica", "Helvetica Neue", "Lucida Grande", "Monaco", "Palatino", "San Francisco", "Times", "Times New Roman", "Trebuchet MS", "Verdana"],
        "vendor": "Google Inc.",
        "ua_brands": [{"brand": "Chromium", "version": "132"}, {"brand": "Google Chrome", "version": "132"}, {"brand": "Not_A Brand", "version": "24"}],
        "ua_platform": "macOS",
        "ua_platform_version": "15.0.0",
        "ua_architecture": "arm",
        "ua_full_version_list": [{"brand": "Chromium", "version": "132.0.6834.57"}, {"brand": "Google Chrome", "version": "132.0.6834.57"}, {"brand": "Not_A Brand", "version": "24.0.0.0"}],
    },
]

# Region-specific data for profile generation
_REGION_DATA = {
    "US": {
        "timezones": ["America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles", "America/Phoenix"],
        "geolocations": [
            {"lat": 40.7128, "lon": -74.0060},   # NYC
            {"lat": 34.0522, "lon": -118.2437},   # LA
            {"lat": 41.8781, "lon": -87.6298},    # Chicago
            {"lat": 33.4484, "lon": -112.0740},   # Phoenix
            {"lat": 29.7604, "lon": -95.3698},    # Houston
            {"lat": 47.6062, "lon": -122.3321},   # Seattle
        ],
        "languages": [["en-US", "en"]],
    },
    "CA": {
        "timezones": ["America/Toronto", "America/Vancouver", "America/Edmonton"],
        "geolocations": [
            {"lat": 43.6532, "lon": -79.3832},   # Toronto
            {"lat": 49.2827, "lon": -123.1207},   # Vancouver
            {"lat": 45.5017, "lon": -73.5673},    # Montreal
        ],
        "languages": [["en-CA", "en-US", "en"], ["fr-CA", "en-CA", "en"]],
    },
    "UK": {
        "timezones": ["Europe/London"],
        "geolocations": [
            {"lat": 51.5074, "lon": -0.1278},    # London
            {"lat": 53.4808, "lon": -2.2426},    # Manchester
            {"lat": 52.4862, "lon": -1.8904},    # Birmingham
        ],
        "languages": [["en-GB", "en"]],
    },
    "DE": {
        "timezones": ["Europe/Berlin"],
        "geolocations": [
            {"lat": 52.5200, "lon": 13.4050},    # Berlin
            {"lat": 48.1351, "lon": 11.5820},    # Munich
            {"lat": 50.1109, "lon": 8.6821},     # Frankfurt
        ],
        "languages": [["de-DE", "de", "en-US", "en"]],
    },
}


class ProfileManager:
    """Manages browser fingerprint profiles with Redis-backed storage."""

    def __init__(self, redis_url: str = "redis://localhost:6379", redis_password: str = "ShaxAGI2025"):
        self._redis: Optional[redis.Redis] = None
        self._redis_url = redis_url
        self._redis_password = redis_password
        PROFILES_DIR.mkdir(parents=True, exist_ok=True)
        TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)
        self._ensure_templates()

    def _get_redis(self) -> redis.Redis:
        if self._redis is None:
            self._redis = redis.Redis.from_url(
                self._redis_url,
                password=self._redis_password,
                decode_responses=True,
            )
        return self._redis

    def _ensure_templates(self):
        """Write built-in templates to disk if not already present."""
        for tmpl in PROFILE_TEMPLATES:
            pid = hashlib.md5(tmpl["name"].encode()).hexdigest()[:12]
            path = TEMPLATES_DIR / f"{pid}.json"
            if not path.exists():
                data = {**tmpl, "profile_id": f"template_{pid}"}
                path.write_text(json.dumps(data, indent=2))

    def create_profile(self, region: str = "US") -> BrowserProfile:
        """Generate a new internally-consistent profile for the given region."""
        region_data = _REGION_DATA.get(region, _REGION_DATA["US"])
        template = random.choice(PROFILE_TEMPLATES)

        tz = random.choice(region_data["timezones"])
        geo = random.choice(region_data["geolocations"])
        langs = random.choice(region_data["languages"])

        # Jitter geo slightly so profiles aren't identical
        geo_jittered = {
            "lat": geo["lat"] + random.uniform(-0.05, 0.05),
            "lon": geo["lon"] + random.uniform(-0.05, 0.05),
            "accuracy": random.choice([50, 100, 150, 200]),
        }

        profile_id = f"profile_{uuid.uuid4().hex[:12]}"

        profile = BrowserProfile(
            profile_id=profile_id,
            name=f"{template['name']} ({region})",
            user_agent=template["user_agent"],
            screen=dict(template["screen"]),
            viewport=dict(template["viewport"]),
            timezone=tz,
            languages=langs,
            geolocation=geo_jittered,
            webgl_vendor=template["webgl_vendor"],
            webgl_renderer=template["webgl_renderer"],
            device_memory=template["device_memory"],
            hardware_concurrency=template["hardware_concurrency"],
            platform=template["platform"],
            fonts=list(template["fonts"]),
            ua_brands=list(template.get("ua_brands", [])),
            ua_platform=template.get("ua_platform", "Windows"),
            ua_platform_version=template.get("ua_platform_version", "10.0.0"),
            ua_architecture=template.get("ua_architecture", "x86"),
            ua_full_version_list=list(template.get("ua_full_version_list", [])),
            vendor=template.get("vendor", "Google Inc."),
        )

        # Validate before returning
        warnings = profile.validate_consistency()
        if warnings:
            import logging
            logger = logging.getLogger(__name__)
            for w in warnings:
                logger.warning(f"Profile consistency: {w}")

        return profile

    def save_profile(self, profile: BrowserProfile):
        """Save profile to both disk and Redis."""
        # Disk
        path = PROFILES_DIR / f"{profile.profile_id}.json"
        path.write_text(json.dumps(profile.to_dict(), indent=2))

        # Redis
        try:
            r = self._get_redis()
            r.hset(
                "browser_stealth:profiles",
                profile.profile_id,
                json.dumps(profile.to_dict()),
            )
        except Exception:
            pass  # Redis is optional, disk is primary

    def load_profile(self, profile_id: str) -> Optional[BrowserProfile]:
        """Load profile by ID from disk or Redis."""
        # Try disk first
        path = PROFILES_DIR / f"{profile_id}.json"
        if path.exists():
            data = json.loads(path.read_text())
            return BrowserProfile.from_dict(data)

        # Try templates
        for tmpl_path in TEMPLATES_DIR.glob("*.json"):
            data = json.loads(tmpl_path.read_text())
            if data.get("profile_id") == profile_id:
                return BrowserProfile.from_dict(data)

        # Try Redis
        try:
            r = self._get_redis()
            raw = r.hget("browser_stealth:profiles", profile_id)
            if raw:
                return BrowserProfile.from_dict(json.loads(raw))
        except Exception:
            pass

        return None

    def list_profiles(self) -> List[BrowserProfile]:
        """List all saved profiles (disk + templates)."""
        profiles = []
        seen = set()

        for path in PROFILES_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                p = BrowserProfile.from_dict(data)
                if p.profile_id not in seen:
                    profiles.append(p)
                    seen.add(p.profile_id)
            except Exception:
                continue

        for path in TEMPLATES_DIR.glob("*.json"):
            try:
                data = json.loads(path.read_text())
                p = BrowserProfile.from_dict(data)
                if p.profile_id not in seen:
                    profiles.append(p)
                    seen.add(p.profile_id)
            except Exception:
                continue

        return profiles

    def delete_profile(self, profile_id: str) -> bool:
        """Delete a profile from disk and Redis."""
        deleted = False
        path = PROFILES_DIR / f"{profile_id}.json"
        if path.exists():
            path.unlink()
            deleted = True

        try:
            r = self._get_redis()
            r.hdel("browser_stealth:profiles", profile_id)
            deleted = True
        except Exception:
            pass

        return deleted

    def get_random_template(self) -> BrowserProfile:
        """Get a random pre-built template as a BrowserProfile."""
        tmpl = random.choice(PROFILE_TEMPLATES)
        pid = hashlib.md5(tmpl["name"].encode()).hexdigest()[:12]
        return BrowserProfile.from_dict({**tmpl, "profile_id": f"template_{pid}"})
