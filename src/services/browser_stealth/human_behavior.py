"""
Human Behavior Simulator - Realistic mouse movement, typing, scrolling, and form interaction.
Uses bezier curves for mouse paths, variable delays per character class for typing,
and natural reading-pause patterns for scrolling.
"""

import asyncio
import math
import random
from typing import Optional, List, Dict, Tuple, Union

from playwright.async_api import ElementHandle, Page


class HumanSimulator:
    """Simulates human-like browser interaction on a Playwright page."""

    def __init__(self, page: Page):
        self.page = page
        self._last_mouse_x: float = random.uniform(200, 800)
        self._last_mouse_y: float = random.uniform(200, 500)

    # =========================================================================
    # TYPING
    # =========================================================================

    async def type_text(self, selector_or_element: Union[str, ElementHandle], text: str, typo_chance: float = 0.01):
        """
        Type text into an element with human-like timing.

        Accepts either a CSS selector string or a Playwright ElementHandle.

        Delays per character class:
          - Lowercase:    30-120ms
          - Uppercase:    80-150ms  (shift key overhead)
          - Punctuation:  100-300ms (hand repositioning)
          - Space:        50-200ms
          - Digits:       50-130ms

        Occasional typo → backspace → retype cycle.
        """
        if isinstance(selector_or_element, str):
            element = await self.page.wait_for_selector(selector_or_element, timeout=15000)
            if not element:
                raise RuntimeError(f"Element not found: {selector_or_element}")
            await element.click()
        elif isinstance(selector_or_element, ElementHandle):
            element = selector_or_element
            await element.click()
        else:
            raise TypeError(f"Expected str or ElementHandle, got {type(selector_or_element).__name__}")
        await asyncio.sleep(random.uniform(0.15, 0.35))

        # Clear existing content
        await element.evaluate("el => { el.value = ''; el.dispatchEvent(new Event('input', {bubbles: true})); }")

        for i, char in enumerate(text):
            # Typo simulation
            if random.random() < typo_chance:
                nearby = self._nearby_key(char)
                await self.page.keyboard.press(nearby)
                await asyncio.sleep(random.uniform(0.08, 0.2))
                # Notice the typo
                await asyncio.sleep(random.uniform(0.15, 0.4))
                await self.page.keyboard.press("Backspace")
                await asyncio.sleep(random.uniform(0.05, 0.12))

            # Type the actual character
            await self.page.keyboard.press(char if len(char) == 1 else char)

            # Delay based on character class
            delay = self._char_delay(char)
            await asyncio.sleep(delay / 1000)

            # Occasional thinking pause (every ~20-40 chars)
            if random.random() < 0.03:
                await asyncio.sleep(random.uniform(0.4, 1.2))

    def _char_delay(self, char: str) -> float:
        """Return delay in milliseconds based on character type."""
        if char == " ":
            return random.uniform(50, 200)
        if char in ".,;:!?'\"()-":
            return random.uniform(100, 300)
        if char.isupper():
            return random.uniform(80, 150)
        if char.isdigit():
            return random.uniform(50, 130)
        return random.uniform(30, 120)

    def _nearby_key(self, char: str) -> str:
        """Return a plausible typo character (adjacent key on QWERTY)."""
        neighbors = {
            "a": "sq", "b": "vn", "c": "xv", "d": "sf", "e": "wr",
            "f": "dg", "g": "fh", "h": "gj", "i": "uo", "j": "hk",
            "k": "jl", "l": "k;", "m": "n,", "n": "bm", "o": "ip",
            "p": "o[", "q": "wa", "r": "et", "s": "ad", "t": "ry",
            "u": "yi", "v": "cb", "w": "qe", "x": "zc", "y": "tu",
            "z": "x",
        }
        lower = char.lower()
        pool = neighbors.get(lower, "abcdefghijklmnopqrstuvwxyz")
        typo = random.choice(pool)
        return typo.upper() if char.isupper() else typo

    # =========================================================================
    # CLICKING
    # =========================================================================

    async def click(self, selector: str):
        """
        Click an element with human-like mouse movement.

        - Moves mouse along a bezier curve (not teleport)
        - Random offset within element bounds (30-70% of width/height)
        - Pre-click hover delay (100-300ms)
        """
        element = await self.page.wait_for_selector(selector, timeout=15000)
        if not element:
            raise RuntimeError(f"Element not found: {selector}")

        box = await element.bounding_box()
        if not box:
            # Fallback to basic click if no bounding box
            await element.click()
            return

        # Target with random offset within element
        target_x = box["x"] + box["width"] * random.uniform(0.3, 0.7)
        target_y = box["y"] + box["height"] * random.uniform(0.3, 0.7)

        # Move mouse along bezier curve
        await self._bezier_move(target_x, target_y)

        # Pre-click hover
        await asyncio.sleep(random.uniform(0.1, 0.3))

        # Human click: down + small delay + up
        await self.page.mouse.down()
        await asyncio.sleep(random.uniform(0.04, 0.12))
        await self.page.mouse.up()

        self._last_mouse_x = target_x
        self._last_mouse_y = target_y

    async def _bezier_move(self, target_x: float, target_y: float):
        """
        Move mouse from current position to target along a cubic bezier curve.
        Uses 2-3 control points with slight randomization for natural movement.
        """
        sx, sy = self._last_mouse_x, self._last_mouse_y
        tx, ty = target_x, target_y

        distance = math.hypot(tx - sx, ty - sy)
        steps = max(8, min(30, int(distance / 15)))

        # Generate 2 random control points
        cp1_x = sx + (tx - sx) * random.uniform(0.1, 0.4) + random.uniform(-50, 50)
        cp1_y = sy + (ty - sy) * random.uniform(0.1, 0.4) + random.uniform(-50, 50)
        cp2_x = sx + (tx - sx) * random.uniform(0.6, 0.9) + random.uniform(-30, 30)
        cp2_y = sy + (ty - sy) * random.uniform(0.6, 0.9) + random.uniform(-30, 30)

        for i in range(steps + 1):
            t = i / steps
            # Cubic bezier formula
            x = (
                (1 - t) ** 3 * sx
                + 3 * (1 - t) ** 2 * t * cp1_x
                + 3 * (1 - t) * t ** 2 * cp2_x
                + t ** 3 * tx
            )
            y = (
                (1 - t) ** 3 * sy
                + 3 * (1 - t) ** 2 * t * cp1_y
                + 3 * (1 - t) * t ** 2 * cp2_y
                + t ** 3 * ty
            )

            await self.page.mouse.move(x, y)
            # Variable speed - slower at start and end (ease in/out)
            base_delay = 0.008 + 0.012 * math.sin(t * math.pi)
            await asyncio.sleep(base_delay * random.uniform(0.7, 1.4))

        # Occasional overshoot and correction (~20% chance)
        if random.random() < 0.2:
            overshoot_x = tx + random.uniform(-8, 8)
            overshoot_y = ty + random.uniform(-8, 8)
            await self.page.mouse.move(overshoot_x, overshoot_y)
            await asyncio.sleep(random.uniform(0.05, 0.15))
            await self.page.mouse.move(tx, ty)

        self._last_mouse_x = tx
        self._last_mouse_y = ty

    # =========================================================================
    # SCROLLING
    # =========================================================================

    async def scroll(self, direction: str = "down", amount: Optional[int] = None):
        """
        Scroll with human-like behavior.

        - Variable step sizes (50-150px)
        - Pauses between steps (100-400ms)
        - Occasional long pause simulating reading (1-3s, 15% chance)
        """
        if amount is None:
            amount = random.randint(300, 800)

        sign = 1 if direction == "down" else -1
        scrolled = 0

        while scrolled < amount:
            step = random.randint(50, 150)
            step = min(step, amount - scrolled)

            await self.page.mouse.wheel(0, sign * step)
            scrolled += step

            # Inter-step pause
            await asyncio.sleep(random.uniform(0.1, 0.4))

            # Occasional reading pause
            if random.random() < 0.15:
                await asyncio.sleep(random.uniform(1.0, 3.0))

    async def scroll_to_element(self, selector: str):
        """Scroll element into view with human-like scrolling."""
        element = await self.page.wait_for_selector(selector, timeout=15000)
        if not element:
            return

        # Get element position
        box = await element.bounding_box()
        if not box:
            await element.scroll_into_view_if_needed()
            return

        viewport = self.page.viewport_size
        if not viewport:
            await element.scroll_into_view_if_needed()
            return

        # Calculate scroll distance
        target_y = box["y"]
        visible_top = 0
        visible_bottom = viewport["height"]

        if target_y < visible_top or target_y > visible_bottom:
            distance = int(target_y - viewport["height"] * 0.3)
            direction = "down" if distance > 0 else "up"
            await self.scroll(direction=direction, amount=abs(distance))

    # =========================================================================
    # WAITING
    # =========================================================================

    async def wait(self, min_sec: float = 0.5, max_sec: float = 2.0):
        """Human thinking delay."""
        await asyncio.sleep(random.uniform(min_sec, max_sec))

    async def wait_and_observe(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """
        Wait while doing small mouse movements (simulating reading/observing).
        More convincing than a completely still cursor.
        """
        duration = random.uniform(min_sec, max_sec)
        elapsed = 0.0

        while elapsed < duration:
            # Small idle mouse drift
            drift_x = self._last_mouse_x + random.uniform(-15, 15)
            drift_y = self._last_mouse_y + random.uniform(-10, 10)
            await self.page.mouse.move(drift_x, drift_y)
            self._last_mouse_x = drift_x
            self._last_mouse_y = drift_y

            pause = random.uniform(0.3, 0.8)
            await asyncio.sleep(pause)
            elapsed += pause

    # =========================================================================
    # FORM FILLING
    # =========================================================================

    async def fill_form(self, fields: Dict[str, str]):
        """
        Fill form fields with human-like behavior.

        Args:
            fields: Dict mapping CSS selectors to values.
                    e.g. {"#email": "user@example.com", "#password": "s3cret"}

        Behavior:
          - Tab between fields ~40% of the time, click the rest
          - Read delay before typing each field (0.3-1.0s)
          - Occasional scroll between fields
        """
        selectors = list(fields.keys())

        for i, (selector, value) in enumerate(fields.items()):
            # Navigate to field: tab or click
            if i > 0 and random.random() < 0.4:
                # Tab to next field
                await self.page.keyboard.press("Tab")
                await asyncio.sleep(random.uniform(0.2, 0.5))
            else:
                # Click to field
                await self.click(selector)

            # Read/think delay before typing
            await asyncio.sleep(random.uniform(0.3, 1.0))

            # Type the value
            await self.type_text(selector, value, typo_chance=0.008)

            # Occasional scroll between fields
            if random.random() < 0.2:
                await self.scroll(direction="down", amount=random.randint(50, 150))
                await asyncio.sleep(random.uniform(0.2, 0.5))

    # =========================================================================
    # COMPLEX INTERACTIONS
    # =========================================================================

    async def click_and_wait_navigation(self, selector: str, timeout: int = 30000):
        """Click an element and wait for navigation to complete."""
        async with self.page.expect_navigation(timeout=timeout, wait_until="domcontentloaded"):
            await self.click(selector)

    async def select_option(self, selector_or_element: Union[str, ElementHandle], value: str):
        """Select a dropdown option with human-like behavior.

        Accepts either a CSS selector string or a Playwright ElementHandle.
        """
        if isinstance(selector_or_element, str):
            await self.click(selector_or_element)
            await asyncio.sleep(random.uniform(0.3, 0.7))
            await self.page.select_option(selector_or_element, value)
        elif isinstance(selector_or_element, ElementHandle):
            await selector_or_element.click()
            await asyncio.sleep(random.uniform(0.3, 0.7))
            await selector_or_element.select_option(value)
        else:
            raise TypeError(f"Expected str or ElementHandle, got {type(selector_or_element).__name__}")
        await asyncio.sleep(random.uniform(0.1, 0.3))

    async def move_mouse_randomly(self, count: int = 3):
        """Make random mouse movements (simulating idle behavior)."""
        viewport = self.page.viewport_size or {"width": 1920, "height": 1080}
        for _ in range(count):
            x = random.uniform(100, viewport["width"] - 100)
            y = random.uniform(100, viewport["height"] - 100)
            await self._bezier_move(x, y)
            await asyncio.sleep(random.uniform(0.2, 0.6))
