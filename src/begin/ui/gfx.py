"""Drawing at any pixel density: the UI lays itself out in logical pixels, a `Canvas` keeps the real ones [E].

On a high-density screen (a Mac's Retina display, a 4K monitor at 200%) a window that is 1600 × 900 to the
layout has 3200 × 1800 pixels. Drawing at 1600 × 900 and letting the system stretch it makes every line
and letter soft. Instead, every surface the UI draws on is a `Canvas`: it stores `SCALE` times the pixels
but answers in logical ones (its size, its clip, the rects it returns), so the layout code never changes.

`draw` and `transform` stand in for `pygame.draw` and `pygame.transform`: on a Canvas they scale the
coordinates, radii and widths; on an ordinary surface they are pygame's own, so at `SCALE` 1 nothing at all
is different. `Surface(...)` makes a Canvas when `SCALE` is above 1 and a plain surface otherwise.

An ordinary surface blitted onto a Canvas (art loaded from disk, art built pixel by pixel) is stretched
smoothly to fit, so it is soft but the right size; hot paths should hand over a Canvas instead (`adopt`,
`hires`).
"""

from __future__ import annotations

import math
from typing import Any, Sequence

import pygame

SCALE = 1.0            # physical pixels per logical pixel for new surfaces; 1 = draw as pygame always has
LIGHTING = True        # weapon light on hulls, shadows under cards, and (on the GPU) bloom: the Display page's switch

Point = Sequence[float]


def set_scale(s: float) -> None:
    """Set the density for every surface made from now on (the presenter calls it when the window opens)."""
    global SCALE
    SCALE = max(1.0, float(s))


def set_lighting(on: bool) -> None:
    global LIGHTING
    LIGHTING = bool(on)


def _ceil(v: float) -> int:
    return int(math.ceil(v - 1e-6))


class Canvas(pygame.Surface):
    """A surface with `s` times the pixels of its logical size, drawn on in logical coordinates."""

    def __init__(self, size: Point, flags: int = 0, s: float | None = None) -> None:
        self._s = float(s if s is not None else SCALE)
        self._lw, self._lh = max(0, int(size[0])), max(0, int(size[1]))
        super().__init__((_ceil(self._lw * self._s), _ceil(self._lh * self._s)), flags, 32)

    # ---------------------------------------------------------------- logical ↔ physical

    @property
    def density(self) -> float:
        return self._s

    def phys(self, v: float) -> int:
        return int(round(v * self._s))

    def phys_pt(self, p: Point) -> tuple[int, int]:
        return int(round(p[0] * self._s)), int(round(p[1] * self._s))

    def phys_rect(self, r: Any) -> pygame.Rect:
        r = pygame.Rect(r)
        s = self._s
        x0, y0 = math.floor(r.x * s + 1e-6), math.floor(r.y * s + 1e-6)
        return pygame.Rect(x0, y0, _ceil(r.right * s) - x0, _ceil(r.bottom * s) - y0)

    def logical_rect(self, r: pygame.Rect) -> pygame.Rect:
        s = self._s
        x0, y0 = math.floor(r.x / s), math.floor(r.y / s)
        return pygame.Rect(x0, y0, _ceil(r.right / s) - x0, _ceil(r.bottom / s) - y0)

    # ---------------------------------------------------------------- size

    def get_size(self) -> tuple[int, int]:
        return self._lw, self._lh

    def get_width(self) -> int:
        return self._lw

    def get_height(self) -> int:
        return self._lh

    def get_rect(self, **kw: Any) -> pygame.Rect:
        r = pygame.Rect(0, 0, self._lw, self._lh)
        for k, v in kw.items():
            setattr(r, k, v)
        return r

    def get_physical_size(self) -> tuple[int, int]:
        return pygame.Surface.get_size(self)

    # ---------------------------------------------------------------- drawing

    def blit(self, source: pygame.Surface, dest: Any = (0, 0), area: Any = None, special_flags: int = 0) -> pygame.Rect:
        x, y = (dest.x, dest.y) if isinstance(dest, pygame.Rect) else (dest[0], dest[1])
        src: pygame.Surface = source
        parea = None
        if isinstance(source, Canvas):
            if source._s != self._s:
                src = _restretch(source, self._s)
            if area is not None:
                parea = src.phys_rect(area) if isinstance(src, Canvas) else None
        else:
            if area is not None:
                a = pygame.Rect(area).clip(source.get_rect())
                source = source.subsurface(a)
            src = hires(source, self._s)
        got = pygame.Surface.blit(self, src, self.phys_pt((x, y)), parea, special_flags)
        return self.logical_rect(got)

    def blits(self, seq: Any, doreturn: bool = True) -> list[pygame.Rect] | None:  # type: ignore[override]
        out = [self.blit(*item) for item in seq]
        return out if doreturn else None

    def fill(self, color: Any, rect: Any = None, special_flags: int = 0) -> pygame.Rect:
        got = pygame.Surface.fill(self, color, self.phys_rect(rect) if rect is not None else None, special_flags)
        return self.logical_rect(got)

    def set_clip(self, rect: Any = None) -> None:  # type: ignore[override]
        pygame.Surface.set_clip(self, self.phys_rect(rect) if rect is not None else None)

    def get_clip(self) -> pygame.Rect:
        return self.logical_rect(pygame.Surface.get_clip(self))

    def get_bounding_rect(self, min_alpha: int = 1) -> pygame.Rect:
        return self.logical_rect(pygame.Surface.get_bounding_rect(self, min_alpha))

    def set_at(self, pos: Point, color: Any) -> None:  # type: ignore[override]
        pygame.Surface.fill(self, color, self.phys_rect((int(pos[0]), int(pos[1]), 1, 1)))

    def get_at(self, pos: Point) -> pygame.Color:  # type: ignore[override]
        return pygame.Surface.get_at(self, self.phys_pt((int(pos[0]) + 0.5, int(pos[1]) + 0.5)))

    def copy(self) -> Canvas:
        out = Canvas((self._lw, self._lh), self.get_flags() & pygame.SRCALPHA, self._s)
        _copy_pixels(out, self)
        return out

    def convert(self, *a: Any) -> Canvas:  # type: ignore[override]
        return self

    def convert_alpha(self, *a: Any) -> Canvas:  # type: ignore[override]
        return self

    def subsurface(self, *rect: Any) -> Canvas:  # type: ignore[override]
        """A copy of the area, not a window onto it (pygame can't make a Canvas share pixels)."""
        r = pygame.Rect(*rect)
        pr = self.phys_rect(r).clip(pygame.Rect((0, 0), self.get_physical_size()))
        out = Canvas(r.size, self.get_flags() & pygame.SRCALPHA, self._s)
        _copy_pixels(out, pygame.Surface.subsurface(self, pr))
        return out


def _copy_pixels(dst: pygame.Surface, src: pygame.Surface) -> None:
    """Exact pixels, alpha and all (an ordinary blit would blend them onto the destination)."""
    pygame.Surface.fill(dst, (0, 0, 0, 0))
    pygame.Surface.blit(dst, src, (0, 0), None, pygame.BLEND_RGBA_MAX)


def adopt(phys: pygame.Surface, s: float | None = None) -> pygame.Surface:
    """A surface already drawn at full density, as a Canvas of its logical size (no resampling)."""
    s = SCALE if s is None else s
    if s <= 1.0:
        return phys
    w, h = phys.get_size()
    out = Canvas((_ceil(w / s), _ceil(h / s)), pygame.SRCALPHA, s)   # rounded up: no pixel column is lost
    _copy_pixels(out, phys)
    return out


def hires(img: pygame.Surface, s: float | None = None) -> pygame.Surface:
    """An ordinary (logical-size) surface stretched smoothly to `s` density, for blitting onto a Canvas."""
    s = SCALE if s is None else s
    if s <= 1.0 or isinstance(img, Canvas):
        return img
    w, h = img.get_size()
    size = (_ceil(w * s), _ceil(h * s))
    if img.get_bitsize() not in (24, 32):
        img = img.convert_alpha() if pygame.display.get_surface() is not None else img.convert(32, pygame.SRCALPHA)
    return pygame.transform.smoothscale(img, size) if w and h else pygame.Surface(size, pygame.SRCALPHA)


def _restretch(c: Canvas, s: float) -> pygame.Surface:
    w, h = c.get_size()
    out = Canvas((w, h), pygame.SRCALPHA, s)
    pygame.Surface.blit(out, pygame.transform.smoothscale(c, out.get_physical_size()), (0, 0))
    return out


def Surface(size: Point, flags: int = 0, *rest: Any) -> pygame.Surface:  # noqa: N802 - stands in for pygame.Surface
    """A new surface to draw on: a Canvas on a high-density screen, pygame's own otherwise."""
    if SCALE > 1.0:
        return Canvas(size, flags)
    return pygame.Surface((int(size[0]), int(size[1])), flags, *rest)


# -------------------------------------------------------------------- dirty tracking

_DIRTY: dict[int, pygame.Rect | None] = {}     # id(layer) -> union of what was drawn on it since the last take


def track(layer: pygame.Surface) -> None:
    """Remember where things are drawn on `layer` (a mostly empty overlay), so only that part is cleared and
    composited. Everything drawn through `draw` is noted; a blit is noted with `mark`."""
    _DIRTY.setdefault(id(layer), None)


def mark(layer: pygame.Surface, rect: Any) -> pygame.Rect:
    """Note that `rect` (logical) of `layer` was drawn on; returns the rect."""
    if id(layer) in _DIRTY:
        r = pygame.Rect(rect)
        if r.w > 0 and r.h > 0:
            had = _DIRTY[id(layer)]
            _DIRTY[id(layer)] = r if had is None else had.union(r)
    return rect


def take_dirty(layer: pygame.Surface) -> pygame.Rect | None:
    """What was drawn on `layer` since the last call (None if nothing), and start over."""
    got = _DIRTY.get(id(layer))
    if id(layer) in _DIRTY:
        _DIRTY[id(layer)] = None
    return got


# -------------------------------------------------------------------- light, for a presenter that can bloom it

_LIGHT: list[tuple[pygame.Surface, pygame.Rect]] = []
_STAGE: list[pygame.Rect] = []


def offer_light(layer: pygame.Surface, rect: Any) -> None:
    """`rect` (logical, in screen coordinates) of `layer`, a screen-sized surface of added light (weapon glow),
    was lit this frame. A GPU presenter blurs it into a soft bloom; the software one ignores it, and the light
    has already been added to the frame either way."""
    r = pygame.Rect(rect)
    if r.w > 0 and r.h > 0:
        _LIGHT.append((layer, r))


def set_stage(rect: Any) -> None:
    """The area of the screen that is the view of space this frame (the map), where a presenter may darken
    the edges a little. Nothing else is touched. The map sets it as it starts drawing, which also drops light
    from a frame no presenter took (so nothing piles up when frames are drawn without being shown)."""
    r = pygame.Rect(rect)
    if r.w > 0:
        _LIGHT.clear()
    _STAGE[:] = [r]


def take_light() -> tuple[list[tuple[pygame.Surface, pygame.Rect]], pygame.Rect | None]:
    """What was offered since the last call, and start over."""
    light, stage = list(_LIGHT), (_STAGE[0] if _STAGE else None)
    _LIGHT.clear()
    _STAGE.clear()
    return light, stage


# -------------------------------------------------------------------- pygame.draw, density-aware

def _w(c: Canvas, width: int) -> int:
    return 0 if width == 0 else max(1, int(round(width * c._s)))


def _pts(c: Canvas, pts: Sequence[Point]) -> list[tuple[int, int]]:
    s = c._s
    return [(int(round(p[0] * s)), int(round(p[1] * s))) for p in pts]


class _Draw:
    """`pygame.draw` that understands a Canvas: same calls, same arguments, logical coordinates."""

    @staticmethod
    def rect(surf: pygame.Surface, color: Any, rect: Any, width: int = 0, border_radius: int = 0, *a: Any, **kw: Any) -> pygame.Rect:
        if not isinstance(surf, Canvas):
            return pygame.draw.rect(surf, color, rect, width, border_radius, *a, **kw)
        kw = {k: int(round(v * surf._s)) if k.startswith("border_") and v > 0 else v for k, v in kw.items()}
        got = pygame.draw.rect(surf, color, surf.phys_rect(rect), _w(surf, width),
                               int(round(border_radius * surf._s)) if border_radius > 0 else border_radius, **kw)
        return surf.logical_rect(got)

    @staticmethod
    def line(surf: pygame.Surface, color: Any, start: Point, end: Point, width: int = 1) -> pygame.Rect:
        if not isinstance(surf, Canvas):
            return pygame.draw.line(surf, color, start, end, width)
        return surf.logical_rect(pygame.draw.line(surf, color, surf.phys_pt(start), surf.phys_pt(end), _w(surf, width)))

    @staticmethod
    def lines(surf: pygame.Surface, color: Any, closed: bool, points: Sequence[Point], width: int = 1) -> pygame.Rect:
        if not isinstance(surf, Canvas):
            return pygame.draw.lines(surf, color, closed, points, width)
        return surf.logical_rect(pygame.draw.lines(surf, color, closed, _pts(surf, points), _w(surf, width)))

    @staticmethod
    def aaline(surf: pygame.Surface, color: Any, start: Point, end: Point, width: float = 1) -> pygame.Rect:
        """A smooth straight line at sub-pixel positions, `width` wide: what beams and trails are drawn with."""
        if not isinstance(surf, Canvas):
            return pygame.draw.aaline(surf, color, start, end, max(1, round(width)))
        s = surf._s
        return surf.logical_rect(pygame.draw.aaline(surf, color, (start[0] * s, start[1] * s), (end[0] * s, end[1] * s),
                                                    max(1, round(width * s))))

    @staticmethod
    def aalines(surf: pygame.Surface, color: Any, closed: bool, points: Sequence[Point], *a: Any) -> pygame.Rect:
        if not isinstance(surf, Canvas):
            return pygame.draw.aalines(surf, color, closed, points, *a)
        s = surf._s
        return surf.logical_rect(pygame.draw.aalines(surf, color, closed, [(x * s, y * s) for x, y in points]))

    @staticmethod
    def aacircle(surf: pygame.Surface, color: Any, center: Point, radius: float, width: int = 0) -> pygame.Rect:
        """A smooth round disc (or ring) centred at a sub-pixel position."""
        if not isinstance(surf, Canvas):
            return pygame.draw.aacircle(surf, color, center, max(0.5, radius), width)
        s = surf._s
        return surf.logical_rect(pygame.draw.aacircle(surf, color, (center[0] * s, center[1] * s), max(0.5, radius * s),
                                                      _w(surf, width) if width else 0))

    @staticmethod
    def circle(surf: pygame.Surface, color: Any, center: Point, radius: float, width: int = 0, *a: Any, **kw: Any) -> pygame.Rect:
        if not isinstance(surf, Canvas):
            return pygame.draw.circle(surf, color, center, radius, width, *a, **kw)
        return surf.logical_rect(pygame.draw.circle(surf, color, surf.phys_pt(center), radius * surf._s, _w(surf, width),
                                                    *a, **kw))

    @staticmethod
    def polygon(surf: pygame.Surface, color: Any, points: Sequence[Point], width: int = 0) -> pygame.Rect:
        if not isinstance(surf, Canvas):
            return pygame.draw.polygon(surf, color, points, width)
        return surf.logical_rect(pygame.draw.polygon(surf, color, _pts(surf, points), _w(surf, width)))

    @staticmethod
    def arc(surf: pygame.Surface, color: Any, rect: Any, start: float, stop: float, width: int = 1) -> pygame.Rect:
        if not isinstance(surf, Canvas):
            return pygame.draw.arc(surf, color, rect, start, stop, width)
        return surf.logical_rect(pygame.draw.arc(surf, color, surf.phys_rect(rect), start, stop, _w(surf, width)))

    @staticmethod
    def ellipse(surf: pygame.Surface, color: Any, rect: Any, width: int = 0) -> pygame.Rect:
        if not isinstance(surf, Canvas):
            return pygame.draw.ellipse(surf, color, rect, width)
        return surf.logical_rect(pygame.draw.ellipse(surf, color, surf.phys_rect(rect), _w(surf, width)))


def _marking(fn: Any) -> Any:
    def drawn(surf: pygame.Surface, *a: Any, **kw: Any) -> pygame.Rect:
        got = fn(surf, *a, **kw)
        if _DIRTY and id(surf) in _DIRTY:
            mark(surf, got.inflate(2, 2))
        return got
    drawn.__doc__ = fn.__doc__
    return staticmethod(drawn)


for _name in ("rect", "line", "lines", "aaline", "aalines", "aacircle", "circle", "polygon", "arc", "ellipse"):
    setattr(_Draw, _name, _marking(getattr(_Draw, _name)))

draw = _Draw()


# -------------------------------------------------------------------- pygame.transform, density-aware

class _Transform:
    """`pygame.transform` that keeps a Canvas a Canvas (worked on at full density)."""

    @staticmethod
    def rotozoom(surf: pygame.Surface, angle: float, scale: float) -> pygame.Surface:
        if not isinstance(surf, Canvas):
            return pygame.transform.rotozoom(surf, angle, scale)
        return adopt(pygame.transform.rotozoom(surf, angle, scale), surf._s)

    @staticmethod
    def rotate(surf: pygame.Surface, angle: float) -> pygame.Surface:
        if not isinstance(surf, Canvas):
            return pygame.transform.rotate(surf, angle)
        return adopt(pygame.transform.rotate(surf, angle), surf._s)

    @staticmethod
    def smoothscale(surf: pygame.Surface, size: Point, *a: Any) -> pygame.Surface:
        if not isinstance(surf, Canvas):
            return pygame.transform.smoothscale(surf, (int(size[0]), int(size[1])), *a)
        s = surf._s
        phys = pygame.transform.smoothscale(surf, (max(1, _ceil(size[0] * s)), max(1, _ceil(size[1] * s))))
        return adopt(phys, s)

    @staticmethod
    def scale(surf: pygame.Surface, size: Point, *a: Any) -> pygame.Surface:
        if not isinstance(surf, Canvas):
            return pygame.transform.scale(surf, (int(size[0]), int(size[1])), *a)
        s = surf._s
        return adopt(pygame.transform.scale(surf, (max(1, _ceil(size[0] * s)), max(1, _ceil(size[1] * s)))), s)

    @staticmethod
    def gaussian_blur(surf: pygame.Surface, radius: int, *a: Any) -> pygame.Surface:
        if not isinstance(surf, Canvas):
            return pygame.transform.gaussian_blur(surf, radius, *a)
        return adopt(pygame.transform.gaussian_blur(surf, max(1, int(round(radius * surf._s))), *a), surf._s)

    @staticmethod
    def rotozoom_hires(img: pygame.Surface, angle: float, scale: float) -> pygame.Surface:
        """Ordinary (high-resolution) art turned and sized for the screen: at full density, so it stays sharp."""
        s = SCALE
        if s <= 1.0:
            return pygame.transform.rotozoom(img, angle, scale)
        return adopt(pygame.transform.rotozoom(img, angle, scale * s), s)


transform = _Transform()


__all__ = ["Canvas", "SCALE", "Surface", "adopt", "draw", "hires", "mark", "offer_light", "set_lighting", "set_scale", "set_stage",
           "take_dirty", "take_light", "track", "transform"]
