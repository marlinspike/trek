"""Compass-angle helpers.

Begin uses compass bearings: 0° points along +Y ("north"), 90° along +X.
Relative bearings ("marks") are measured from a ship's bow, clockwise.
"""

from __future__ import annotations

import math

TAU = math.tau
DEG = math.pi / 180.0


def norm360(a: float) -> float:
    """Normalize an angle to [0, 360)."""
    a = math.fmod(a, 360.0)
    if a < 0.0:
        a += 360.0
    return 0.0 if a >= 360.0 else a


def norm180(a: float) -> float:
    """Normalize an angle to (-180, 180]."""
    a = norm360(a)
    return a - 360.0 if a > 180.0 else a


def ang_dist(a: float, b: float) -> float:
    """Unsigned angular distance in [0, 180]."""
    return abs(norm180(a - b))


def turn_delta(current: float, desired: float) -> float:
    """Signed shortest turn from `current` to `desired`, in (-180, 180]."""
    return norm180(desired - current)


def bearing(dx: float, dy: float) -> float:
    """Compass bearing of the vector (dx, dy)."""
    if dx == 0.0 and dy == 0.0:
        return 0.0
    return norm360(math.degrees(math.atan2(dx, dy)))


def heading_vector(course: float) -> tuple[float, float]:
    """Unit vector for a compass course."""
    r = course * DEG
    return math.sin(r), math.cos(r)


def in_arc(rel_bearing: float, arc_center: float, arc_width: float) -> bool:
    """True if `rel_bearing` lies inside an arc of `arc_width` centred on `arc_center`."""
    if arc_width >= 360.0:
        return True
    return ang_dist(rel_bearing, arc_center) <= arc_width / 2.0
