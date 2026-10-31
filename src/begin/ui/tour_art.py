"""The pictures of a tour of duty [E]: the patrol chart, your ships lit and turning, the officers' cards.

Everything is drawn in code, so a tour you write yourself gets a chart of its own:

- the chart: a deep field of nebulae and stars made from the tour's id (the same tour always
  looks the same), a faint sector grid, the route between the stops glowing where you have
  been and dashed where you are going, and the flagship gliding along it;
- a ship: the heavy cruiser's baked sprite where there is one, otherwise the class's hull drawn
  from hulls.toml, filled and shaded, lit from the same side whatever her heading, with scorch
  marks that spread as her hull is damaged;
- an officer's card: a portrait in their department's colour, their name and post.
"""

from __future__ import annotations

import math
import random
import zlib
from functools import lru_cache

import pygame

from ..content.schema import ShipClass
from ..tour.model import TourDef
from . import theme
from .hulls import ellipse_points, transform
from .showpiece import KLINGON_SPRITE, SHIP_DIR, ship_image

NEBULA_COLOURS = ((60, 40, 120), (30, 90, 140), (120, 40, 90), (30, 110, 110), (90, 70, 30))
HULL_PAINT = {"federation": (176, 186, 202), "klingon": (120, 132, 112), "romulan": (122, 158, 132),
              "orion": (150, 138, 118)}
ENGINE_GLOW = {"federation": (110, 190, 255), "klingon": (255, 120, 70), "romulan": (120, 255, 150),
               "orion": (255, 200, 90)}
DEPARTMENT = {"helm": (66, 112, 196), "tactical": (196, 152, 56), "engineering": (196, 152, 56),
              "science": (120, 140, 168)}
OFFICER_COLOUR = {"spock": (66, 112, 196), "worf": (196, 152, 56), "geordi": (196, 152, 56),
                  "seven": (120, 140, 168)}
CHART_MARGIN = 0.06       # share of the chart kept clear round the edge
ART_STEP = 3              # degrees: a turning ship is drawn at this step (each drawing is kept)
GLIDE_SECONDS = 4.0       # how long the flagship takes to fly a leg of the route on the chart
HC_SPRITE_SCALE = 1.15 / 700.0     # sprite scale per pixel of ship length (7 sprite px per hull unit, ~100 units, a little trim)


def _seed(s: str) -> int:
    return zlib.crc32(s.encode())


# ------------------------------------------------------------------ the chart

@lru_cache(maxsize=6)
def chart_background(tour_id: str, w: int, h: int) -> pygame.Surface:
    """Nebulae, stars and a faint grid, the same for the same tour."""
    rng = random.Random(_seed(tour_id))
    bg = pygame.Surface((w, h))
    for y in range(h):                     # a deep wash, darker at the top
        t = y / max(1, h - 1)
        pygame.draw.line(bg, theme.mix((5, 9, 20), (12, 18, 36), t), (0, y), (w, y))
    small = pygame.Surface((max(1, w // 4), max(1, h // 4)), pygame.SRCALPHA)
    for _ in range(9):                     # nebulae: soft blobs, blurred together at quarter size
        col = rng.choice(NEBULA_COLOURS)
        cx, cy = rng.uniform(0, small.get_width()), rng.uniform(0, small.get_height())
        for _ in range(rng.randint(3, 6)):
            r = rng.uniform(0.06, 0.18) * small.get_width()
            ox, oy = rng.gauss(0, r), rng.gauss(0, r * 0.6)
            pygame.draw.circle(small, (*col, rng.randint(40, 90)), (int(cx + ox), int(cy + oy)), int(r))
    small = pygame.transform.gaussian_blur(small, 18)
    bg.blit(pygame.transform.smoothscale(small, (w, h)), (0, 0))
    for _ in range(w * h // 1800):         # stars
        x, y = rng.randrange(w), rng.randrange(h)
        lvl = rng.random() ** 2
        c = theme.mix((40, 50, 70), rng.choice(((220, 230, 255), (255, 240, 220))), lvl)
        bg.set_at((x, y), c)
        if lvl > 0.8:
            pygame.draw.circle(bg, theme.dim(c, 0.5), (x, y), 1)
    grid = pygame.Surface((w, h), pygame.SRCALPHA)
    step = max(60, w // 12)
    for x in range(0, w, step):
        pygame.draw.line(grid, (*theme.GRID_MAJOR, 70), (x, 0), (x, h))
    for y in range(0, h, step):
        pygame.draw.line(grid, (*theme.GRID_MAJOR, 70), (0, y), (w, y))
    bg.blit(grid, (0, 0))
    return bg


def chart_point(rect: pygame.Rect, p: tuple[float, float]) -> tuple[float, float]:
    m = CHART_MARGIN
    return (rect.x + rect.width * (m + (1 - 2 * m) * p[0]), rect.y + rect.height * (m + (1 - 2 * m) * p[1]))


def departure(tour: TourDef) -> tuple[float, float]:
    """Where the patrol starts on the chart: a little short of the first stop."""
    if not tour.stops:
        return (0.05, 0.5)
    x, y = tour.stops[0].chart
    return (max(0.0, x - 0.1), min(1.0, y + 0.08))


def _glow_line(overlay: pygame.Surface, col: theme.Color, a: tuple[float, float], b: tuple[float, float],
               strength: float) -> None:
    for w, alpha in ((14, 26), (8, 50), (4, 110)):
        pygame.draw.line(overlay, (*col, int(alpha * strength)), a, b, w)


def _dashes(surf: pygame.Surface, col: tuple[int, ...], a: tuple[float, float], b: tuple[float, float],
            on: float = 9.0, off: float = 7.0, phase: float = 0.0, width: int = 2) -> None:
    dx, dy = b[0] - a[0], b[1] - a[1]
    n = math.hypot(dx, dy)
    if n < 1:
        return
    ux, uy = dx / n, dy / n
    t = -(phase % (on + off))
    while t < n:
        s, e = max(0.0, t), min(n, t + on)
        if e > s:
            pygame.draw.line(surf, col, (a[0] + ux * s, a[1] + uy * s), (a[0] + ux * e, a[1] + uy * e), width)
        t += on + off


def draw_chart(surf: pygame.Surface, rect: pygame.Rect, tour: TourDef, done: list[str], outcomes: list[str],
               current: int, glide: float, t: float, dim: float = 0.0) -> tuple[float, float]:
    """The patrol chart in `rect`. `done` are the stops fought (with their `outcomes`), `current` the next
    stop's index, `glide` 0..1 how far the flagship has flown the leg to it. Returns where she is drawn."""
    surf.blit(chart_background(tour.id, rect.width, rect.height), rect.topleft)
    overlay = pygame.Surface(rect.size, pygame.SRCALPHA)
    pts = [chart_point(pygame.Rect(0, 0, rect.width, rect.height), s.chart) for s in tour.stops]
    start = chart_point(pygame.Rect(0, 0, rect.width, rect.height), departure(tour))
    route = [start] + pts
    for i in range(len(route) - 1):
        a, b = route[i], route[i + 1]
        if i < current:                                 # flown: a steady glow
            _glow_line(overlay, theme.FRIEND, a, b, 0.8)
        elif i == current:                              # the leg ahead: lit as far as she has flown, dashes beyond
            mid = (a[0] + (b[0] - a[0]) * glide, a[1] + (b[1] - a[1]) * glide)
            _glow_line(overlay, theme.FRIEND, a, mid, 0.9)
            _dashes(overlay, (*theme.CAUTION, 200), mid, b, phase=-t * 30.0)
        else:
            _dashes(overlay, (*theme.TEXT_FAINT, 150), a, b, 5, 7)
    # the stops: a star and its glow; fought stops ringed in their outcome's colour
    for i, (p, s) in enumerate(zip(pts, tour.stops)):
        fought = i < len(outcomes)
        ahead = i == current
        pulse = 0.5 + 0.5 * math.sin(t * 2.4) if ahead else 0.0
        for r, alpha in ((22, 20), (13, 45), (7, 120)):
            pygame.draw.circle(overlay, (255, 230, 190, int(alpha * (1.0 + pulse))), (int(p[0]), int(p[1])), r + int(4 * pulse))
        pygame.draw.circle(overlay, (255, 250, 235, 255), (int(p[0]), int(p[1])), 3)
        if fought:
            col = {"victory": theme.GOOD, "withdrew": theme.CAUTION}.get(outcomes[i], theme.ALERT)
            pygame.draw.circle(overlay, (*col, 230), (int(p[0]), int(p[1])), 12, 2)
        elif ahead:
            pygame.draw.circle(overlay, (*theme.CAUTION, int(150 + 100 * pulse)), (int(p[0]), int(p[1])), 15, 1)
        if s.finale:
            pygame.draw.rect(overlay, (*theme.FRIEND, 200), pygame.Rect(int(p[0]) - 6, int(p[1]) - 30, 12, 12), 1)
    surf.blit(overlay, rect.topleft)
    for i, (p, s) in enumerate(zip(pts, tour.stops)):
        col = theme.TEXT if i == current else theme.TEXT_DIM if i < len(outcomes) else theme.TEXT_FAINT
        theme.text(surf, f"{i + 1}  {s.system.upper()}", (rect.x + p[0] + 18, rect.y + p[1] - 9), col, 11, "display")
        theme.text(surf, s.title, (rect.x + p[0] + 18, rect.y + p[1] + 6), theme.dim(col, 0.8), 11)
    # the flagship, gliding along the leg ahead (or at rest at the last stop)
    a = route[min(current, len(route) - 1)]
    b = route[min(current + 1, len(route) - 1)]
    k = 1.0 - (1.0 - glide) ** 2
    sx, sy = a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k
    heading = math.degrees(math.atan2(b[0] - a[0], -(b[1] - a[1]))) % 360.0 if b != a else 90.0
    sx += math.sin(t * 1.3) * 1.5 * (glide >= 1.0)
    sy += math.cos(t * 1.1) * 1.5 * (glide >= 1.0)
    img = ship_image(round(heading) % 360, 0.075)
    x, y = rect.x + sx, rect.y + sy
    if img is not None:
        halo = pygame.Surface((60, 60), pygame.SRCALPHA)
        for r, al in ((26, 18), (16, 36)):
            pygame.draw.circle(halo, (*theme.FRIEND, al), (30, 30), r)
        surf.blit(halo, (x - 30, y - 30))
        surf.blit(img, img.get_rect(center=(int(x), int(y))))
    else:
        pygame.draw.circle(surf, theme.FRIEND, (int(x), int(y)), 5)
    if dim > 0:
        shade = pygame.Surface(rect.size, pygame.SRCALPHA)
        shade.fill((*theme.BG, int(255 * dim)))
        surf.blit(shade, rect.topleft)
    return x, y


# ------------------------------------------------------------------ ships

@lru_cache(maxsize=4)
def _light(size: int) -> pygame.Surface:
    """A soft light from the upper left: multiplied over a ship so the shading stays put as she turns."""
    s = pygame.Surface((size, size))
    for y in range(0, size, 2):
        for x in range(0, size, 2):
            d = ((x - size * 0.25) ** 2 + (y - size * 0.2) ** 2) ** 0.5 / size
            v = int(max(95, min(255, 285 - d * 230)))
            pygame.draw.rect(s, (v, v, v), (x, y, 2, 2))
    return s


_CLASSES: dict[str, ShipClass] = {}


@lru_cache(maxsize=64)
def _hull_base(cls_id: str, length: int, scorch: int, seed: int) -> pygame.Surface:
    """The class's hull, bow up, `length` pixels long, painted, with `scorch` marks of battle damage."""
    cls = _CLASSES[cls_id]
    paint = HULL_PAINT.get(cls.faction, (170, 170, 176))
    engine = ENGINE_GLOW.get(cls.faction, (160, 200, 255))
    size = int(length * 1.5)
    base = pygame.Surface((size, size), pygame.SRCALPHA)
    k = length / 100.0
    c = size / 2
    hull = cls.hull
    for shp in hull.shapes:
        pts = shp.points if shp.kind == "poly" else ellipse_points(shp.center[0], shp.center[1], shp.radii[0], shp.radii[1], 24)
        pts = transform(pts, c, c, 0.0, k)
        if len(pts) < 3:
            continue
        if shp.role == "hull":
            pygame.draw.polygon(base, paint, pts)
            pygame.draw.polygon(base, theme.dim(paint, 0.55), pts, max(1, length // 90))
        elif shp.role == "nacelle":
            pygame.draw.polygon(base, theme.mix(paint, engine, 0.35), pts)
            pygame.draw.polygon(base, engine, pts, max(1, length // 80))
        else:
            pygame.draw.polygon(base, theme.dim(paint, 0.7), pts, 1)
    if scorch:
        rng = random.Random(seed)
        mask = pygame.mask.from_surface(base)
        marks = pygame.Surface((size, size), pygame.SRCALPHA)
        for _ in range(scorch):
            for _try in range(12):
                x, y = rng.randrange(size), rng.randrange(size)
                if mask.get_at((x, y)):
                    r = rng.randint(max(2, length // 40), max(3, length // 14))
                    pygame.draw.circle(marks, (20, 14, 10, rng.randint(120, 200)), (x, y), r)
                    pygame.draw.circle(marks, (255, 120, 40, 90), (x, y), max(1, r // 3))
                    break
        marks = pygame.transform.gaussian_blur(marks, max(1, length // 70))
        clip = mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
        marks.blit(clip, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        base.blit(marks, (0, 0))
    return base


@lru_cache(maxsize=4)
def _klingon() -> pygame.Surface | None:
    try:
        return pygame.image.load(str(SHIP_DIR / KLINGON_SPRITE))
    except (FileNotFoundError, pygame.error, OSError):
        return None


def ship_art(cls: ShipClass, length: int, heading: float, hull: float = 1.0, seed: int = 0) -> pygame.Surface:
    """A ship for the squadron screens: `length` pixels bow to stern at `heading` (degrees clockwise from up),
    lit from the upper left, scorched as her `hull` (0..1) is damaged, with a glow of her engines beneath."""
    scorch = int(round((1.0 - max(0.0, min(1.0, hull))) * 14))
    _CLASSES[cls.id] = cls
    return _ship_art(cls.id, length, int(round(heading / ART_STEP)) * ART_STEP % 360, scorch, seed)


@lru_cache(maxsize=360)
def _ship_art(cls_id: str, length: int, heading: int, scorch: int, seed: int) -> pygame.Surface:
    cls = _CLASSES[cls_id]
    engine = ENGINE_GLOW.get(cls.faction, (160, 200, 255))
    img: pygame.Surface | None = None
    if cls.id == "federation.hc":
        img = ship_image(round(heading / 2) * 2 % 360, round(length * HC_SPRITE_SCALE, 3))
    elif cls.id == "klingon.bc" and _klingon() is not None:
        k = _klingon()
        assert k is not None
        img = pygame.transform.rotozoom(k, -heading, length / max(1, k.get_height()))
    if img is None:
        base = _hull_base(cls.id, length, scorch, seed)
        img = pygame.transform.rotozoom(base, -heading, 1.0)
        lit = img.copy()
        lit.blit(pygame.transform.smoothscale(_light(256), img.get_size()), (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        img = lit
    elif scorch:
        img = img.copy()
        dark = pygame.Surface(img.get_size(), pygame.SRCALPHA)
        rng = random.Random(seed)
        mask = pygame.mask.from_surface(img)
        w, h = img.get_size()
        for _ in range(scorch * 2):
            for _try in range(12):
                x, y = rng.randrange(w), rng.randrange(h)
                if mask.get_at((x, y)):
                    pygame.draw.circle(dark, (16, 10, 8, rng.randint(110, 180)), (x, y), rng.randint(2, max(3, length // 16)))
                    break
        dark = pygame.transform.gaussian_blur(dark, 2)
        clip = mask.to_surface(setcolor=(255, 255, 255, 255), unsetcolor=(0, 0, 0, 0))
        dark.blit(clip, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
        img.blit(dark, (0, 0))
    w, h = img.get_size()
    out = pygame.Surface((w + 40, h + 40), pygame.SRCALPHA)
    glow = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    glow.blit(img, (20, 20))
    glow.fill((*engine, 255), special_flags=pygame.BLEND_RGBA_MULT)
    glow = pygame.transform.gaussian_blur(glow, 8)
    glow.fill((255, 255, 255, 110), special_flags=pygame.BLEND_RGBA_MULT)
    out.blit(glow, (0, 0))
    out.blit(img, (20, 20))
    return out


# ------------------------------------------------------------------ officers

@lru_cache(maxsize=16)
def portrait(officer_id: str, size: int) -> pygame.Surface:
    """An officer's portrait card: a lit silhouette against their department's colour."""
    col = OFFICER_COLOUR.get(officer_id, (120, 140, 168))
    s = pygame.Surface((size, size), pygame.SRCALPHA)
    for y in range(size):
        pygame.draw.line(s, theme.mix(theme.dim(col, 0.5), theme.dim(col, 0.18), y / size), (0, y), (size, y))
    body = theme.mix(col, (20, 24, 34), 0.55)
    face = (40, 48, 66)
    pygame.draw.ellipse(s, body, pygame.Rect(size * 0.12, size * 0.66, size * 0.76, size * 0.6))       # shoulders
    pygame.draw.rect(s, theme.dim(col, 0.9), pygame.Rect(size * 0.12, size * 0.82, size * 0.76, size * 0.06))   # the tunic's band
    pygame.draw.circle(s, face, (size // 2, int(size * 0.42)), int(size * 0.2))                         # head
    rim = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.circle(rim, (*theme.mix(col, (255, 255, 255), 0.5), 90), (size // 2 - 2, int(size * 0.42) - 2), int(size * 0.2), 2)
    s.blit(rim, (0, 0))
    mask = pygame.Surface((size, size), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=max(4, size // 10))
    s.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    pygame.draw.rect(s, theme.mix(col, (255, 255, 255), 0.3), s.get_rect(), 1, border_radius=max(4, size // 10))
    return s


# ------------------------------------------------------------------ text

def wrap(s: str, size: int, width: int, family: str = "ui") -> list[str]:
    """Lines of `s` that fit `width` pixels; blank lines in `s` are kept."""
    out: list[str] = []
    for para in s.split("\n"):
        line = ""
        for word in para.split(" "):
            trial = f"{line} {word}" if line else word
            if line and theme.text_width(trial, size, family) > width:
                out.append(line)
                line = word
            else:
                line = trial
        out.append(line)
    return out


def glass(surf: pygame.Surface, rect: pygame.Rect, title: str | None = None, accent: theme.Color = theme.FRIEND,
          alpha: int = 200) -> int:
    """A translucent panel over the chart; returns the y where its content starts."""
    pane = pygame.Surface(rect.size, pygame.SRCALPHA)
    pygame.draw.rect(pane, (*theme.BG_PANEL, alpha), pane.get_rect(), border_radius=6)
    pygame.draw.rect(pane, (*theme.BORDER_HI, 160), pane.get_rect(), 1, border_radius=6)
    surf.blit(pane, rect.topleft)
    if title:
        pygame.draw.line(surf, accent, (rect.x + 12, rect.y + 1), (rect.x + 44, rect.y + 1), 2)
        theme.text(surf, title.upper(), (rect.x + 12, rect.y + 8), theme.TEXT_DIM, 12, "display", weight="medium")
        return rect.y + 32
    return rect.y + 12


__all__ = ["GLIDE_SECONDS", "chart_background", "chart_point", "departure", "draw_chart", "glass", "portrait",
           "ship_art", "wrap"]
