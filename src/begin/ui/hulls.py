"""Procedural hull silhouettes from the hull definitions in hulls.toml."""

from __future__ import annotations

import math

import pygame

from ..content.schema import HullDef
from . import theme
from .theme import Color

MIN_HULL_PX = 26.0  # tactical exaggeration: ships never shrink below this on screen


def hull_pixel_scale(hull: HullDef, zoom: float, min_px: float = MIN_HULL_PX) -> float:
    """Screen pixels per hull design unit (design spans ~100 units)."""
    true_px = hull.length * zoom
    return max(true_px, min_px) / 100.0


def transform(points: tuple[tuple[float, float], ...] | list[tuple[float, float]], sx: float, sy: float,
              course: float, k: float) -> list[tuple[float, float]]:
    r = math.radians(course)
    c, s = math.cos(r), math.sin(r)
    out = []
    for px, py in points:
        # hull frame: +y bow, +x starboard → world (compass) → screen (y down)
        wx = px * c + py * s
        wy = -px * s + py * c
        out.append((sx + wx * k, sy - wy * k))
    return out


def ellipse_points(cx: float, cy: float, rx: float, ry: float, n: int = 18) -> list[tuple[float, float]]:
    return [(cx + math.cos(a) * rx, cy + math.sin(a) * ry) for a in (2 * math.pi * i / n for i in range(n))]


def draw_hull(surf: pygame.Surface, hull: HullDef, sx: float, sy: float, course: float, k: float,
              color: Color, fill_alpha: float = 0.28, engine: Color | None = None, outline: int = 1) -> None:
    fill = theme.dim(color, fill_alpha)
    eng = engine or theme.mix(color, (255, 255, 255), 0.25)
    for shp in hull.shapes:
        if shp.kind == "poly":
            pts = transform(shp.points, sx, sy, course, k)
        else:
            pts = transform(ellipse_points(shp.center[0], shp.center[1], shp.radii[0], shp.radii[1]), sx, sy, course, k)
        if len(pts) < 3:
            continue
        if shp.role == "hull":
            pygame.draw.polygon(surf, fill, pts)
            pygame.draw.polygon(surf, color, pts, outline)
        elif shp.role == "nacelle":
            pygame.draw.polygon(surf, theme.dim(eng, 0.45), pts)
            pygame.draw.polygon(surf, eng, pts, outline)
        else:
            pygame.draw.polygon(surf, theme.dim(color, 0.75), pts, 1)


__all__ = ["MIN_HULL_PX", "draw_hull", "ellipse_points", "hull_pixel_scale", "transform"]
