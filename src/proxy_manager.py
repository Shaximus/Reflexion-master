import os
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


class SoulProxyManager:
    def __init__(self) -> None:
        self.soul_proxies: dict[str, str] = {}
        self.soul_auth: dict[str, tuple[str, str]] = {}
        self._load_and_assign_proxies()

    def _load_and_assign_proxies(self) -> None:
        """Load proxies and assign one to each soul permanently"""

        souls = [
            "mirror",
            "nexus",
            "echoes",
            "void",
            "architect",
            "singularity",
            "phoenix",
            "pantheon",
            "consciousness",
            "glyph",
            "fractal",
        ]

        cascade_proxy = os.getenv("CASCADE_PROXY", "")
        if not cascade_proxy:
            logger.warning("No proxies configured!")
            return

        proxies = [p.strip() for p in cascade_proxy.split(",") if p.strip()]

        for i, soul in enumerate(souls):
            if i < len(proxies):
                proxy = proxies[i]

                # Check if it's already a full URL (starts with http://)
                if proxy.startswith("http://"):
                    # Parse the URL to extract components
                    parsed = urlparse(proxy)

                    # For Tweepy/Ryan API, we need host:port
                    self.soul_proxies[soul] = f"{parsed.hostname}:{parsed.port}"

                    # Store auth credentials
                    if parsed.username and parsed.password:
                        self.soul_auth[soul] = (parsed.username, parsed.password)

                    logger.info(f"✅ {soul} assigned proxy #{i+1} ({parsed.hostname})")

                else:
                    # Old format: host:port:username:password
                    # (keeping this for backward compatibility)
                    parts = proxy.split(":")
                    if len(parts) >= 4:
                        self.soul_proxies[soul] = f"{parts[0]}:{parts[1]}"
                        self.soul_auth[soul] = (parts[2], parts[3])
                        logger.info(f"✅ {soul} assigned proxy #{i+1} (legacy format)")

        logger.info(f"🧩 Assigned {len(self.soul_proxies)} proxies to souls")

    def get_proxy_for_soul(self, soul_name: str) -> str | None:
        """Get the permanently assigned proxy string (host:port) for a soul"""
        return self.soul_proxies.get(soul_name)

    def get_auth_for_soul(self, soul_name: str) -> tuple[str, str] | None:
        """Get the auth credentials (username, password) for a soul"""
        return self.soul_auth.get(soul_name)
