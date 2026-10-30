"""HUD numbers that ease to a new value instead of jumping, and flash briefly when they change."""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from . import theme

EASE = 7.0          # per second: how fast a shown number closes on the real one
FLASH = 0.7         # seconds a changed number stays highlighted


@dataclass
class _Shown:
    value: float           # what is on screen
    target: float          # the real value it is easing toward
    flash: float = 0.0
    up: bool = True


@dataclass
class Tweens:
    """Shown values by key. `get` each frame with the real value; `update` once a frame with the time step."""

    shown: dict[str, _Shown] = field(default_factory=dict)

    def get(self, key: str, value: float, step: float = 0.5) -> float:
        """The number to show for `key`. A change of at least `step` sets off the flash."""
        s = self.shown.get(key)
        if s is None:
            self.shown[key] = _Shown(value, value)
            return value
        if abs(value - s.target) >= step:
            s.flash = FLASH
            s.up = value > s.value
        s.target = value
        return s.value

    def colour(self, key: str, base: theme.Color) -> theme.Color:
        """`base`, lit up while the number has just changed: brighter for a rise, warmer for a fall."""
        s = self.shown.get(key)
        if s is None or s.flash <= 0:
            return base
        hot = (210, 255, 230) if s.up else (255, 200, 150)
        return theme.mix(base, hot, 0.8 * s.flash / FLASH)

    def update(self, dt: float) -> None:
        k = 1 - math.exp(-EASE * dt)
        for s in self.shown.values():
            s.value += (s.target - s.value) * k
            if abs(s.target - s.value) < 0.05:
                s.value = s.target
            s.flash = max(0.0, s.flash - dt)


__all__ = ["Tweens"]
