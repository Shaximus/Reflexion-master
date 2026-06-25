"""Generate fake identities for account creation using Faker."""
from __future__ import annotations

import logging
import random
import string
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Optional

from faker import Faker

logger = logging.getLogger(__name__)

# Pre-written bio pool for fallback when local LLM is unavailable
BIO_POOL = [
    "exploring the intersection of tech and creativity",
    "software dev by day, stargazer by night",
    "passionate about open source and good coffee",
    "building things that make people's lives easier",
    "music lover | code writer | perpetual learner",
    "fascinated by neural networks and the human brain",
    "digital artist finding beauty in algorithms",
    "science nerd with a love for sci-fi novels",
    "full-stack developer & weekend photographer",
    "into AI, robotics, and the future of everything",
    "maker of things, breaker of bugs",
    "design thinker | data enthusiast | tea addict",
    "amateur astronomer, professional problem solver",
    "electronic music producer & python enthusiast",
    "reading about quantum physics so you don't have to",
    "minimalist. coder. occasional poet.",
    "building the future one commit at a time",
    "art + math = my happy place",
    "indie game dev | pixel art lover | cat person",
    "curious about everything, expert in nothing (yet)",
    "retro tech collector and modern web developer",
    "vinyl enthusiast who also streams on spotify",
]

REGIONS = ["US", "CA", "UK", "DE"]

LOCALE_MAP = {
    "US": "en_US",
    "CA": "en_CA",
    "UK": "en_GB",
    "DE": "de_DE",
}


@dataclass
class AccountIdentity:
    """Complete identity for account creation."""

    profile_id: str
    full_name: str
    email: str
    password: str
    date_of_birth: str  # YYYY-MM-DD
    bio: str
    avatar_url: str
    username: str
    region: str

    @property
    def dob_parts(self) -> dict:
        """Return DOB as {month, day, year} integers for form filling."""
        dt = datetime.strptime(self.date_of_birth, "%Y-%m-%d")
        return {"month": dt.month, "day": dt.day, "year": dt.year}


class ProfileGenerator:
    """Generate fake but realistic identities for account creation."""

    def __init__(
        self,
        email_domain: str = "reflexion.software",
        regions: Optional[List[str]] = None,
        local_llm_url: Optional[str] = None,
    ):
        self.email_domain = email_domain
        self.regions = regions or REGIONS
        self.local_llm_url = local_llm_url

        # Create locale-specific Faker instances
        self._fakers = {}
        for region in self.regions:
            locale = LOCALE_MAP.get(region, "en_US")
            self._fakers[region] = Faker(locale)

        # Seed for reproducibility in testing (can be overridden)
        self._rng = random.Random()

    def _generate_password(self) -> str:
        """Generate a password 8-16 chars with letters, numbers, and specials."""
        length = self._rng.randint(8, 16)
        # Ensure at least one of each category
        chars = [
            self._rng.choice(string.ascii_uppercase),
            self._rng.choice(string.ascii_lowercase),
            self._rng.choice(string.digits),
            self._rng.choice("!@#$%^&*_+-="),
        ]
        # Fill remaining length
        remaining = length - len(chars)
        pool = string.ascii_letters + string.digits + "!@#$%^&*_+-="
        chars.extend(self._rng.choice(pool) for _ in range(remaining))
        self._rng.shuffle(chars)
        return "".join(chars)

    def _generate_username(self, full_name: str) -> str:
        """Generate a username 3-15 chars, alphanumeric with underscores."""
        parts = full_name.lower().split()
        base = ""
        strategy = self._rng.randint(0, 3)

        if strategy == 0 and len(parts) >= 2:
            # first_last
            base = f"{parts[0]}_{parts[-1]}"
        elif strategy == 1 and len(parts) >= 2:
            # firstlast + digits
            base = f"{parts[0]}{parts[-1]}"
        elif strategy == 2 and parts:
            # first + random digits
            base = parts[0]
        else:
            # random alphanumeric
            base = "".join(self._rng.choices(string.ascii_lowercase, k=6))

        # Clean to alphanumeric + underscore
        base = "".join(c for c in base if c.isalnum() or c == "_")

        # Add random digits for uniqueness
        suffix = str(self._rng.randint(10, 9999))
        username = f"{base}{suffix}"

        # Enforce 3-15 char limit
        username = username[:15]
        if len(username) < 3:
            username = username + "".join(self._rng.choices(string.digits, k=3 - len(username)))

        return username

    def _generate_email(self, username: str) -> str:
        """Generate email using catch-all domain format."""
        random_digits = str(self._rng.randint(100, 9999))
        # Clean username for email use
        email_user = "".join(c for c in username if c.isalnum())
        return f"{email_user}{random_digits}@{self.email_domain}"

    def _generate_dob(self) -> str:
        """Generate DOB for someone aged 18-45."""
        today = datetime.utcnow()
        min_age = 18
        max_age = 45

        # Random age in days
        min_days = min_age * 365
        max_days = max_age * 365
        age_days = self._rng.randint(min_days, max_days)
        dob = today - timedelta(days=age_days)

        return dob.strftime("%Y-%m-%d")

    def _generate_bio(self) -> str:
        """Generate bio - tries local LLM first, falls back to pool."""
        if self.local_llm_url:
            try:
                return self._generate_bio_llm()
            except Exception as e:
                logger.debug(f"LLM bio generation failed, using pool: {e}")

        return self._rng.choice(BIO_POOL)

    def _generate_bio_llm(self) -> str:
        """Generate bio using local LLM."""
        import httpx

        response = httpx.post(
            f"{self.local_llm_url}/chat/completions",
            json={
                "model": "local",
                "messages": [
                    {
                        "role": "system",
                        "content": "Generate a short Twitter bio (under 160 chars). "
                        "Make it casual and about tech, science, art, or music. "
                        "No hashtags. No emojis. Just text.",
                    },
                    {"role": "user", "content": "Generate a bio."},
                ],
                "max_tokens": 60,
                "temperature": 1.0,
            },
            timeout=10.0,
        )
        response.raise_for_status()
        bio = response.json()["choices"][0]["message"]["content"].strip().strip('"')
        # Truncate to 160 chars if needed
        return bio[:160]

    def _generate_avatar_url(self, full_name: str) -> str:
        """Generate avatar placeholder URL using ui-avatars.com."""
        encoded_name = full_name.replace(" ", "+")
        bg_color = f"{self._rng.randint(0, 0xFFFFFF):06x}"
        return (
            f"https://ui-avatars.com/api/?name={encoded_name}"
            f"&background={bg_color}&color=fff&size=200&bold=true"
        )

    def generate(self, region: Optional[str] = None) -> AccountIdentity:
        """Generate a single account identity."""
        if region is None:
            region = self._rng.choice(self.regions)

        if region not in self._fakers:
            logger.warning(f"No Faker for region '{region}', falling back to en_US")
            faker = Faker("en_US")
        else:
            faker = self._fakers[region]

        full_name = faker.name()
        username = self._generate_username(full_name)
        email = self._generate_email(username)
        password = self._generate_password()
        dob = self._generate_dob()
        bio = self._generate_bio()
        avatar_url = self._generate_avatar_url(full_name)
        profile_id = uuid.uuid4().hex[:12]

        identity = AccountIdentity(
            profile_id=profile_id,
            full_name=full_name,
            email=email,
            password=password,
            date_of_birth=dob,
            bio=bio,
            avatar_url=avatar_url,
            username=username,
            region=region,
        )

        logger.info(f"Generated identity: {identity.username} ({identity.region}) [{identity.profile_id}]")
        return identity

    def generate_batch(self, count: int, region: Optional[str] = None) -> List[AccountIdentity]:
        """Generate multiple identities."""
        identities = [self.generate(region=region) for _ in range(count)]
        logger.info(f"Generated batch of {count} identities")
        return identities
