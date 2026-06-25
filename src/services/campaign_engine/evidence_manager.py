"""
GOTCHA Campaign Evidence Manager
Manages forensic evidence images from local disk and GitHub CDN.
"""

from __future__ import annotations

import os
import json
import hashlib
import logging
from pathlib import Path
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger("campaign.evidence")

# Evidence categories
EVIDENCE_CATEGORIES = {
    "har_analysis": "HAR/Network analysis showing telemetry endpoints",
    "consent_bypass": "Proof tracking fires despite consent denial",
    "behavioral_biometrics": "Sift/fingerprinting evidence",
    "dod_contracts": "Pentagon contract documentation",
    "pentagon_memo": "Signed Hegseth memorandum pages",
    "platform_comparison": "Cross-platform telemetry comparison",
    "devtools_capture": "Browser DevTools network tab screenshots",
    "code_forensics": "JS bundle analysis findings",
}

# Platform-specific evidence mapping (what to attach when targeting a platform)
PLATFORM_EVIDENCE_TAGS = {
    "chatgpt": ["har_analysis", "consent_bypass", "behavioral_biometrics"],
    "claude": ["har_analysis", "platform_comparison"],  # Defender narrative — lowest telemetry
    "gemini": ["har_analysis", "consent_bypass", "behavioral_biometrics"],
    "grok": ["har_analysis", "behavioral_biometrics", "dod_contracts"],
    "general": ["platform_comparison", "dod_contracts", "pentagon_memo"],
}


@dataclass
class EvidenceItem:
    """A single piece of forensic evidence."""
    id: str                          # Hash-based unique ID
    filename: str
    path: str                        # Local path or CDN URL
    source: str                      # "local" | "cdn"
    category: str                    # From EVIDENCE_CATEGORIES
    platform: Optional[str] = None   # Which AI platform this targets
    description: str = ""
    alt_text: str = ""
    width: int = 0
    height: int = 0


class EvidenceManager:
    """Catalogs and serves forensic evidence for campaign content."""

    def __init__(
        self,
        screenshots_dir: str = "/home/shax/Pictures/Screenshots",
        evidence_dir: str = "/home/shax/Projects/core-tech/Reflexion-master/evidence",
        manifest_path: Optional[str] = None,
    ):
        self.screenshots_dir = Path(screenshots_dir)
        self.evidence_dir = Path(evidence_dir)
        self.manifest_path = Path(manifest_path) if manifest_path else self.evidence_dir / "manifest.json"
        self.catalog: Dict[str, EvidenceItem] = {}
        self._image_cache: Dict[str, bytes] = {}
        self._max_cache_size: int = 50  # Max images in memory (~25MB at 500KB avg)

        # CDN evidence URLs (from drs_shield_visual.py)
        self.cdn_base = "https://raw.githubusercontent.com"

        # Ensure evidence directory structure exists
        self._ensure_dirs()

    def _ensure_dirs(self):
        """Create evidence directory structure if needed."""
        for subdir in ["screenshots", "slides", "documents"]:
            (self.evidence_dir / subdir).mkdir(parents=True, exist_ok=True)

    def _generate_id(self, path: str) -> str:
        """Generate deterministic ID from path."""
        return hashlib.sha256(path.encode()).hexdigest()[:12]

    def scan_local_evidence(self) -> int:
        """Scan screenshots directory and catalog relevant evidence.

        Returns number of new items cataloged.
        """
        count = 0

        # Scan main screenshots dir
        if self.screenshots_dir.exists():
            for f in self.screenshots_dir.iterdir():
                if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp'):
                    item_id = self._generate_id(str(f))
                    if item_id not in self.catalog:
                        # Auto-categorize based on filename keywords
                        category = self._auto_categorize(f.name)
                        platform = self._auto_detect_platform(f.name)
                        self.catalog[item_id] = EvidenceItem(
                            id=item_id,
                            filename=f.name,
                            path=str(f),
                            source="local",
                            category=category,
                            platform=platform,
                            description=f"Screenshot: {f.stem}",
                            alt_text=f"Forensic evidence: {f.stem}",
                        )
                        count += 1

        # Scan curated evidence dir
        for subdir in ["screenshots", "slides", "documents"]:
            subpath = self.evidence_dir / subdir
            if subpath.exists():
                for f in subpath.iterdir():
                    if f.suffix.lower() in ('.png', '.jpg', '.jpeg', '.webp', '.pdf'):
                        item_id = self._generate_id(str(f))
                        if item_id not in self.catalog:
                            category = self._auto_categorize(f.name)
                            platform = self._auto_detect_platform(f.name)
                            self.catalog[item_id] = EvidenceItem(
                                id=item_id,
                                filename=f.name,
                                path=str(f),
                                source="local",
                                category=category,
                                platform=platform,
                                description=f"Evidence: {f.stem}",
                                alt_text=f"Forensic evidence: {f.stem}",
                            )
                            count += 1

        logger.info(f"Scanned {count} new evidence items, {len(self.catalog)} total")
        return count

    def _auto_categorize(self, filename: str) -> str:
        """Auto-categorize evidence based on filename."""
        name_lower = filename.lower()
        if any(k in name_lower for k in ['har', 'network', 'traffic', 'telemetry']):
            return "har_analysis"
        elif any(k in name_lower for k in ['consent', 'cookie', 'opt-out', 'bypass']):
            return "consent_bypass"
        elif any(k in name_lower for k in ['sift', 'fingerprint', 'biometric']):
            return "behavioral_biometrics"
        elif any(k in name_lower for k in ['dod', 'pentagon', 'contract', 'military']):
            return "dod_contracts"
        elif any(k in name_lower for k in ['memo', 'hegseth', 'war']):
            return "pentagon_memo"
        elif any(k in name_lower for k in ['devtools', 'f12', 'inspector', 'network-tab']):
            return "devtools_capture"
        elif any(k in name_lower for k in ['bundle', 'forensic', 'js_', 'code']):
            return "code_forensics"
        elif any(k in name_lower for k in ['comparison', 'cross-platform', 'vs']):
            return "platform_comparison"
        return "devtools_capture"  # Default

    def _auto_detect_platform(self, filename: str) -> Optional[str]:
        """Detect which platform evidence targets from filename."""
        name_lower = filename.lower()
        for platform in ['chatgpt', 'openai', 'gpt']:
            if platform in name_lower:
                return "chatgpt"
        for platform in ['claude', 'anthropic']:
            if platform in name_lower:
                return "claude"
        for platform in ['gemini', 'google', 'bard']:
            if platform in name_lower:
                return "gemini"
        for platform in ['grok', 'xai', 'twitter']:
            if platform in name_lower:
                return "grok"
        return None

    def get_evidence_for_platform(self, platform: str, max_count: int = 2) -> List[EvidenceItem]:
        """Get evidence items relevant to a specific platform."""
        relevant_categories = PLATFORM_EVIDENCE_TAGS.get(platform, PLATFORM_EVIDENCE_TAGS["general"])

        matches = []
        for item in self.catalog.values():
            if item.platform == platform or item.category in relevant_categories:
                matches.append(item)

        # Prioritize platform-specific over category-matched
        matches.sort(key=lambda x: (x.platform == platform, x.source == "local"), reverse=True)
        return matches[:max_count]

    def get_evidence_by_category(self, category: str, max_count: int = 3) -> List[EvidenceItem]:
        """Get evidence items by category."""
        return [
            item for item in self.catalog.values()
            if item.category == category
        ][:max_count]

    def get_random_evidence(self, max_count: int = 2, exclude_ids: List[str] = None) -> List[EvidenceItem]:
        """Get random evidence items, avoiding duplicates."""
        import random
        exclude = set(exclude_ids or [])
        available = [item for item in self.catalog.values() if item.id not in exclude]
        return random.sample(available, min(max_count, len(available)))

    def _cache_image(self, item_id: str, data: bytes):
        """Cache image bytes with eviction."""
        if len(self._image_cache) >= self._max_cache_size:
            oldest_key = next(iter(self._image_cache))
            del self._image_cache[oldest_key]
        self._image_cache[item_id] = data

    def load_image(self, item: EvidenceItem) -> Optional[bytes]:
        """Load image bytes from an evidence item."""
        if item.id in self._image_cache:
            return self._image_cache[item.id]

        if item.source == "local":
            try:
                with open(item.path, "rb") as f:
                    data = f.read()
                self._cache_image(item.id, data)
                return data
            except FileNotFoundError:
                logger.warning(f"Evidence file not found: {item.path}")
                return None
        elif item.source == "cdn":
            try:
                import httpx
                resp = httpx.get(item.path, timeout=15)
                if resp.status_code == 200:
                    self._cache_image(item.id, resp.content)
                    return resp.content
            except Exception as e:
                logger.warning(f"Failed to fetch CDN evidence: {e}")
                return None
        return None

    def save_manifest(self):
        """Save evidence catalog to manifest.json."""
        manifest = {
            item_id: {
                "filename": item.filename,
                "path": item.path,
                "source": item.source,
                "category": item.category,
                "platform": item.platform,
                "description": item.description,
                "alt_text": item.alt_text,
            }
            for item_id, item in self.catalog.items()
        }
        with open(self.manifest_path, "w") as f:
            json.dump(manifest, f, indent=2)
        logger.info(f"Saved manifest with {len(manifest)} items to {self.manifest_path}")

    def load_manifest(self) -> int:
        """Load evidence catalog from manifest.json. Returns item count."""
        if not self.manifest_path.exists():
            return 0
        try:
            with open(self.manifest_path) as f:
                manifest = json.load(f)
            for item_id, data in manifest.items():
                self.catalog[item_id] = EvidenceItem(id=item_id, **data)
            logger.info(f"Loaded {len(self.catalog)} items from manifest")
            return len(self.catalog)
        except (json.JSONDecodeError, TypeError) as e:
            logger.warning(f"Failed to load manifest: {e}")
            return 0

    def get_stats(self) -> Dict:
        """Get evidence catalog statistics."""
        by_category = {}
        by_platform = {}
        by_source = {"local": 0, "cdn": 0}

        for item in self.catalog.values():
            by_category[item.category] = by_category.get(item.category, 0) + 1
            if item.platform:
                by_platform[item.platform] = by_platform.get(item.platform, 0) + 1
            by_source[item.source] = by_source.get(item.source, 0) + 1

        return {
            "total": len(self.catalog),
            "by_category": by_category,
            "by_platform": by_platform,
            "by_source": by_source,
        }
