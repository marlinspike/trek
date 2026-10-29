"""A small immutable 2D vector."""

from __future__ import annotations

import math
from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Vec2:
    x: float = 0.0
    y: float = 0.0

    def __add__(self, o: Vec2) -> Vec2:
        return Vec2(self.x + o.x, self.y + o.y)

    def __sub__(self, o: Vec2) -> Vec2:
        return Vec2(self.x - o.x, self.y - o.y)

    def __mul__(self, k: float) -> Vec2:
        return Vec2(self.x * k, self.y * k)

    __rmul__ = __mul__

    def __neg__(self) -> Vec2:
        return Vec2(-self.x, -self.y)

    def dot(self, o: Vec2) -> float:
        return self.x * o.x + self.y * o.y

    def length(self) -> float:
        return math.hypot(self.x, self.y)

    def length_sq(self) -> float:
        return self.x * self.x + self.y * self.y

    def normalized(self) -> Vec2:
        n = math.hypot(self.x, self.y)
        return Vec2(self.x / n, self.y / n) if n > 0 else Vec2()

    def rotated(self, course_deg: float) -> Vec2:
        """Rotate a hull-frame vector (+y bow, +x starboard) into world frame for `course_deg`."""
        r = math.radians(course_deg)
        c, s = math.cos(r), math.sin(r)
        # compass rotation: bow (0,1) -> (sin c, cos c); starboard (1,0) -> (cos c, -sin c)
        return Vec2(self.x * c + self.y * s, -self.x * s + self.y * c)

    def as_tuple(self) -> tuple[float, float]:
        return self.x, self.y


def closest_approach(
    px: float, py: float, qx: float, qy: float, tx: float, ty: float
) -> float:
    """Minimum distance from point T to segment P->Q."""
    dx, dy = qx - px, qy - py
    seg2 = dx * dx + dy * dy
    if seg2 <= 1e-12:
        return math.hypot(tx - px, ty - py)
    u = ((tx - px) * dx + (ty - py) * dy) / seg2
    u = 0.0 if u < 0.0 else 1.0 if u > 1.0 else u
    cx, cy = px + dx * u, py + dy * u
    return math.hypot(tx - cx, ty - cy)
