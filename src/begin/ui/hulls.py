"""Procedural hull silhouettes from the hull definitions in hulls.toml."""

from __future__ import annotations

import math
from functools import lru_cache

import pygame

from ..content.schema import HullDef
from . import theme
from .theme import Color

MIN_HULL_PX = 30.0  # tactical exaggeration: ships never shrink below this on screen


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


@lru_cache(maxsize=1024)
def _ellipse(cx: float, cy: float, rx: float, ry: float, n: int) -> tuple[tuple[float, float], ...]:
    return tuple((cx + math.cos(a) * rx, cy + math.sin(a) * ry) for a in (2 * math.pi * i / n for i in range(n)))


def ellipse_points(cx: float, cy: float, rx: float, ry: float, n: int = 18) -> list[tuple[float, float]]:
    return list(_ellipse(cx, cy, rx, ry, n))


ICON_MAX_PX = 96.0     # below this span a hull is drawn as one smoothed silhouette, not a stack of outlines
ICON_SS = 4            # supersampling of those silhouettes
ICON_TURN = 3.0
ICON_DETAIL_PX = 56.0  # smaller than this, panel details are only noise        # their headings are cached every few degrees


_SPANS: dict[str, float] = {}
_HULLS: dict[str, HullDef] = {}


def _span(hull: HullDef) -> float:
    """The farthest any of the hull's shapes reaches from its origin, design units."""
    r = _SPANS.get(hull.class_id)
    if r is not None and _HULLS.get(hull.class_id) is hull:
        return r
    r = 0.0
    for shp in hull.shapes:
        if shp.kind == "poly":
            r = max(r, max(math.hypot(x, y) for x, y in shp.points))
        else:
            r = max(r, math.hypot(shp.center[0], shp.center[1]) + max(shp.radii))
    _SPANS[hull.class_id] = r
    _HULLS[hull.class_id] = hull
    return r


def _shape_pts(shp, sx: float, sy: float, course: float, k: float) -> list[tuple[float, float]]:
    if shp.kind == "poly":
        return transform(shp.points, sx, sy, course, k)
    return transform(_ellipse(shp.center[0], shp.center[1], shp.radii[0], shp.radii[1], 18), sx, sy, course, k)


def _eroded(m: pygame.mask.Mask, t: int) -> pygame.mask.Mask:
    """The mask shrunk by `t` pixels each way: what stays clear of its edge."""
    inner = m.copy()
    for dx, dy in ((t, 0), (-t, 0), (0, t), (0, -t)):
        inner = inner.overlap_mask(m, (dx, dy))
    return inner


def hull_icon(hull: HullDef, course: float, k: float, color: Color, fill_alpha: float,
              engine: Color | None = None) -> tuple[pygame.Surface, float]:
    """A small hull as one clean silhouette (see `_icon`), cached by class, heading, scale and colours."""
    _span(hull)                       # registers the hull under its class id
    return _icon(hull.class_id, id(hull), course, k, tuple(color), fill_alpha, tuple(engine) if engine else None)


@lru_cache(maxsize=2048)
def _icon(class_id: str, _hull_id: int, course: float, k: float, color: Color, fill_alpha: float,
          engine: Color | None) -> tuple[pygame.Surface, float]:
    """A small hull as one clean silhouette: a single smoothed outline round the whole ship, the
    interior filled, nacelles in the engine tint and details faint, supersampled and scaled down.
    Overlapping shapes no longer each draw their own edge, which at map scale turned a ship into
    a knot of lines. Returns the image and the offset of its centre (the hull origin)."""
    hull = _HULLS[class_id]
    fill = theme.dim(color, min(0.75, fill_alpha * 1.8))   # small, she reads as a solid shape, not a wireframe
    eng = engine or theme.mix(color, (255, 255, 255), 0.25)
    kk = k * ICON_SS
    half = math.ceil(_span(hull) * kk) + 2 * ICON_SS
    size = 2 * half
    c = float(half)
    big = pygame.Surface((size, size), pygame.SRCALPHA)
    solid = pygame.Surface((size, size), pygame.SRCALPHA)
    nacelles = [s for s in hull.shapes if s.role == "nacelle"]
    for shp in hull.shapes:
        if shp.role in ("hull", "nacelle"):
            pts = _shape_pts(shp, c, c, course, kk)
            if len(pts) >= 3:
                pygame.draw.polygon(solid, (255, 255, 255, 255), pts)
    m = pygame.mask.from_surface(solid)
    t = ICON_SS                       # a one-pixel line once scaled down
    m.to_surface(big, setcolor=(*color, 255), unsetcolor=None)
    _eroded(m, t).to_surface(big, setcolor=(*fill, 255), unsetcolor=None)
    for shp in nacelles:
        pts = _shape_pts(shp, c, c, course, kk)
        if len(pts) < 3:
            continue
        ns = pygame.Surface((size, size), pygame.SRCALPHA)
        pygame.draw.polygon(ns, (255, 255, 255, 255), pts)
        nm = pygame.mask.from_surface(ns)
        nm.to_surface(big, setcolor=(*eng, 255), unsetcolor=None)
        _eroded(nm, t).to_surface(big, setcolor=(*theme.dim(eng, 0.45), 255), unsetcolor=None)
    for shp in hull.shapes if _span(hull) * 2 * k >= ICON_DETAIL_PX else ():
        if shp.role == "detail":
            pts = _shape_pts(shp, c, c, course, kk)
            dcol = (*theme.dim(color, 0.6), 255)
            if len(pts) >= 3:
                pygame.draw.polygon(big, dcol, pts, max(1, t - 1))
            elif len(pts) == 2:
                pygame.draw.line(big, dcol, pts[0], pts[1], max(1, t - 1))
    small = pygame.transform.smoothscale(big, (size // ICON_SS, size // ICON_SS))
    return small, half / ICON_SS


def draw_hull(surf: pygame.Surface, hull: HullDef, sx: float, sy: float, course: float, k: float,
              color: Color, fill_alpha: float = 0.28, engine: Color | None = None, outline: int = 1) -> None:
    if outline == 1 and _span(hull) * 2 * k <= ICON_MAX_PX:
        turn = round(course / ICON_TURN) * ICON_TURN % 360.0
        img, off = hull_icon(hull, turn, round(k, 3), color, round(fill_alpha, 2), engine)
        surf.blit(img, (round(sx - off), round(sy - off)))
        return
    fill = theme.dim(color, fill_alpha)
    eng = engine or theme.mix(color, (255, 255, 255), 0.25)
    for shp in hull.shapes:
        if shp.kind == "poly":
            pts = transform(shp.points, sx, sy, course, k)
        else:
            pts = transform(_ellipse(shp.center[0], shp.center[1], shp.radii[0], shp.radii[1], 18), sx, sy, course, k)
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


__all__ = ["MIN_HULL_PX", "draw_hull", "hull_icon", "ellipse_points", "hull_pixel_scale", "transform"]
