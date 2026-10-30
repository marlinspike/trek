"""The main menu's showpiece: the player's heavy cruiser flying past, now and then firing [E].

The ship is a pre-rendered sprite (baked by `tools/render_ship.py`, one per 30° of heading
so the light stays put on screen while she turns). `Flybys` plans passes from varied
directions, sizes and speeds, with quiet gaps between, and sometimes has her fire phasers
or a torpedo salvo at something off screen. No enemy is ever shown.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from typing import Callable

import pygame

from . import theme

SPRITE_PX = 7.0           # sprite pixels per hull unit at scale 1 (tools/render_ship.py PX)
SPRITE_CENTRE_Y = -1.0    # hull-unit y at the sprite's centre
BAKED = 12                # sprites, one per 30° of heading
PHASER_COL = (255, 160, 74)
TORPEDO_COL = (255, 94, 58)
SHIP_DIR = Path(__file__).resolve().parent.parent / "assets" / "ships"
TORP_SPEED = 420.0        # pixels a second at scale 1: slow enough to watch the salvo go
SCALE_NEAR = 0.86         # the largest she is drawn on a pass (sprite scale)
SCALE_FAR = 0.22          # the smallest
TRAIL = 0.9               # seconds of trail behind a torpedo
TORP_LIFE = 4.5           # seconds before a torpedo is forgotten (long gone off screen by then)
BEAM_TIME = 0.75          # seconds a phaser shot lasts
# hull-unit emitters (x right, y forward): phaser banks around the saucer, the torpedo launch at the bow
EMITTERS = ((-10.0, 34.0), (10.0, 34.0), (-22.0, 24.0), (22.0, 24.0), (-14.0, 8.0), (14.0, 8.0))
LAUNCH = ((-2.0, 46.0), (2.0, 46.0))


@lru_cache(maxsize=None)
def sprite(i: int) -> pygame.Surface | None:
    """Baked sprite number i (heading i × 30°), or None if the art is missing."""
    try:
        img = pygame.image.load(str(SHIP_DIR / f"heavy-cruiser-{i * 360 // BAKED:03d}.png"))
        return img.convert_alpha() if pygame.display.get_surface() is not None else img
    except (FileNotFoundError, pygame.error, OSError):
        return None


@lru_cache(maxsize=64)
def halo(radius: int, col: tuple[int, int, int]) -> pygame.Surface:
    """A soft round light (black outside), for adding onto the scene: brightest at the centre."""
    d = radius * 2 + 1
    g = pygame.Surface((d, d))
    g.fill((0, 0, 0))
    for r in range(radius, 0, -1):
        k = (1.0 - r / radius) ** 2.2
        pygame.draw.circle(g, (int(col[0] * k), int(col[1] * k), int(col[2] * k)), (radius, radius), r)
    return g


@lru_cache(maxsize=96)
def ship_image(heading: float, scale: float) -> pygame.Surface | None:
    """The ship at a heading (degrees clockwise from up) and scale, lit from the same side whatever her heading."""
    i = round(heading / (360.0 / BAKED)) % BAKED
    img = sprite(i)
    if img is None:
        return None
    return pygame.transform.rotozoom(img, -heading, scale)


def hull_to_screen(cx: float, cy: float, heading: float, scale: float, hx: float, hy: float) -> tuple[float, float]:
    """Where a hull-unit point of the ship lands on screen."""
    a = math.radians(heading)
    fx, fy = math.sin(a), -math.cos(a)        # forward
    rx, ry = math.cos(a), math.sin(a)         # starboard
    k = SPRITE_PX * scale
    f = hy - SPRITE_CENTRE_Y
    return cx + (hx * rx + f * fx) * k, cy + (hx * ry + f * fy) * k


@dataclass
class Shot:
    kind: str                        # "phaser" | "torpedo"
    t: float                         # seconds since it started
    bearing: float                   # screen bearing it goes off along
    emitter: tuple[float, float]     # hull-unit point it leaves from
    pos: tuple[float, float] = (0.0, 0.0)
    scale: float = 1.0                # the pass's scale, so a distant ship's shots are small too
    trail: list[tuple[float, float, float]] = field(default_factory=list)


@dataclass
class Pass:
    start: tuple[float, float]
    mid: tuple[float, float]
    end: tuple[float, float]
    duration: float
    scale: float
    fires: list[tuple[float, str, float]]     # (fraction of the pass, "phaser"|"torpedo", bearing off her heading)
    t: float = 0.0

    @property
    def heading(self) -> float:
        """Her one heading for the whole pass, in whole degrees so the sprite is turned once."""
        (x0, y0), (x2, y2) = self.start, self.end
        return float(round(math.degrees(math.atan2(x2 - x0, -(y2 - y0)))) % 360)

    def at(self, u: float) -> tuple[float, float, float]:
        """(x, y, heading) a fraction u along a straight line: no turning, so nothing twitches."""
        (x0, y0), (x2, y2) = self.start, self.end
        return x0 + (x2 - x0) * u, y0 + (y2 - y0) * u, self.heading


class Flybys:
    """Plans and draws the passes. `sound(name, pan, level)` is called when she fires, if given."""

    def __init__(self, seed: int = 1701, sound: Callable[[str, float, float], None] | None = None) -> None:
        self.rng = random.Random(seed)
        self.sound = sound
        self.current: Pass | None = None
        self.wait = 1.2                       # a moment of empty stars before the first pass
        self.shots: list[Shot] = []
        self.next_kind = "torpedo"            # firing passes take turns to lead with torpedoes and phasers
        self.size = (1600, 900)

    # ------------------------------------------------------------ planning

    def _plan(self) -> Pass:
        w, h = self.size
        r = self.rng
        # a different vantage point each pass, from close by to far off; even odds of near and far
        scale = math.exp(r.uniform(math.log(SCALE_FAR), math.log(SCALE_NEAR)))
        reach = 420 * scale + 60                                   # far enough that she is wholly off screen
        travel = r.uniform(0, 360)
        tx, ty = math.sin(math.radians(travel)), -math.cos(math.radians(travel))
        mid = (r.uniform(0.42, 0.86) * w, r.uniform(0.25, 0.75) * h)
        # how far along the line to either edge, plus the sprite's reach
        def to_edge(sx: float, sy: float) -> float:
            ts = []
            for d, p, lim in ((sx, mid[0], w), (sy, mid[1], h)):
                if abs(d) > 1e-6:
                    ts.append(((lim - p) / d) if d > 0 else (-p / d))
            return min(ts) + reach
        a_len, b_len = to_edge(-tx, -ty), to_edge(tx, ty)
        start = (mid[0] - tx * a_len, mid[1] - ty * a_len)
        end = (mid[0] + tx * b_len, mid[1] + ty * b_len)
        speed = r.uniform(100, 130) * math.sqrt(scale)            # a stately glide; farther off looks slower
        duration = (a_len + b_len) / speed
        fires: list[tuple[float, str, float]] = []
        roll = r.random()
        if roll < 0.85:
            for n in range(r.choice((1, 1, 2))):
                kind = self.next_kind if n == 0 else r.choice(("phaser", "torpedo"))
                off = r.choice((-1, 1)) * r.uniform(35, 110) if kind == "phaser" else r.uniform(-12, 12)
                fires.append((r.uniform(0.35, 0.62), kind, off))
        if fires:
            self.next_kind = "phaser" if self.next_kind == "torpedo" else "torpedo"
        return Pass(start, mid, end, duration, scale, sorted(fires))

    # ------------------------------------------------------------ running

    def update(self, dt: float, size: tuple[int, int]) -> None:
        self.size = size
        p = self.current
        at = p.at(min(1.0, p.t / p.duration)) if p is not None else None
        for s in self.shots:
            s.t += dt
            if s.kind != "torpedo" or s.t < 0:
                continue
            a = math.radians(s.bearing)
            if not s.trail:
                if at is None:
                    s.t = 99.0          # her pass ended before this one left the tube
                    continue
                s.pos = hull_to_screen(at[0], at[1], at[2], p.scale, *s.emitter)   # type: ignore[union-attr]
            else:
                v = TORP_SPEED * s.scale
                s.pos = (s.pos[0] + math.sin(a) * v * dt, s.pos[1] - math.cos(a) * v * dt)
            s.trail.append((s.pos[0], s.pos[1], s.t))
            s.trail = [q for q in s.trail if s.t - q[2] <= TRAIL]
        self.shots = [s for s in self.shots if (s.t < BEAM_TIME if s.kind == "phaser" else s.t < TORP_LIFE)]
        if self.current is None:
            self.wait -= dt
            if self.wait <= 0:
                self.current = self._plan()
            return
        p = self.current
        before = p.t / p.duration
        p.t += dt
        u = p.t / p.duration
        for when, kind, off in p.fires:
            if before < when <= u:
                self._fire(p, kind, off)
        if u >= 1.0:
            self.current = None
            self.wait = self.rng.uniform(2.5, 7.0)

    def _fire(self, p: Pass, kind: str, off: float) -> None:
        x, y, hdg = p.at(min(1.0, p.t / p.duration))
        bearing = (hdg + off) % 360.0
        pan = max(-1.0, min(1.0, (x / max(1, self.size[0])) * 2 - 1))
        if kind == "phaser":
            # the banks that face the target, two or three shots a moment apart
            rel = math.radians(off)
            ranked = sorted(EMITTERS, key=lambda e: -(e[0] * math.sin(rel) + e[1] * math.cos(rel)))
            for k, em in enumerate(ranked[: self.rng.choice((2, 3))]):
                self.shots.append(Shot("phaser", -0.12 * k, bearing + self.rng.uniform(-2, 2), em, scale=p.scale))
            if self.sound:
                self.sound("phaser", pan, 0.35)
        else:
            n = self.rng.choice((2, 3, 4))
            for k in range(n):
                em = LAUNCH[k % 2]
                shot = Shot("torpedo", -0.16 * k, bearing + (k - (n - 1) / 2) * 3.0, em, scale=p.scale)
                self.shots.append(shot)
            if self.sound:
                self.sound("launch", pan, 0.4)

    # ------------------------------------------------------------ drawing

    def draw(self, surf: pygame.Surface) -> None:
        p = self.current
        w, h = surf.get_size()
        glow = pygame.Surface((w, h))            # light, added onto the scene
        glow.fill((0, 0, 0))
        ship_at = p.at(min(1.0, p.t / p.duration)) if p is not None else None
        ship_scale = p.scale if p is not None else 1.0
        for s in self.shots:
            if s.t < 0:
                continue
            if s.kind == "phaser" and ship_at is not None:
                self._beam(glow, s, ship_at, ship_scale, w, h)
            elif s.kind == "torpedo":
                self._torpedo(glow, s)
        if ship_at is not None:
            x, y, hdg = ship_at
            img = ship_image(hdg, ship_scale)
            if img is not None:
                surf.blit(img, img.get_rect(center=(round(x), round(y))))
        surf.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)

    @staticmethod
    def _light(col: tuple[int, int, int], k: float) -> tuple[int, int, int]:
        return (int(col[0] * k), int(col[1] * k), int(col[2] * k))

    def _beam(self, glow: pygame.Surface, s: Shot, at: tuple[float, float, float], scale: float, w: int, h: int) -> None:
        x, y, hdg = at
        p0 = hull_to_screen(x, y, hdg, scale, *s.emitter)
        a = math.radians(s.bearing)
        reach = math.hypot(w, h)
        p1 = (p0[0] + math.sin(a) * reach, p0[1] - math.cos(a) * reach)
        k = max(0.0, 1.0 - s.t / BEAM_TIME)
        k = k * k * (3 - 2 * k)
        core = theme.mix(PHASER_COL, (255, 255, 255), 0.55)
        g = 0.4 + 0.6 * scale                  # a distant ship's beams are finer
        for width, level in ((17, 0.10), (9, 0.22), (5, 0.45)):
            pygame.draw.line(glow, self._light(PHASER_COL, level * k), p0, p1, max(1, round(width * g)))
        pygame.draw.line(glow, self._light(core, 0.95 * k), p0, p1, 2)
        flash = halo(max(4, int(26 * scale)), self._light(core, k))
        glow.blit(flash, flash.get_rect(center=(int(p0[0]), int(p0[1]))), special_flags=pygame.BLEND_RGB_ADD)

    def _torpedo(self, glow: pygame.Surface, s: Shot) -> None:
        if not s.trail:
            return
        for (x0, y0, t0), (x1, y1, _) in zip(s.trail, s.trail[1:]):
            k = 1.0 - (s.t - t0) / TRAIL
            g = 0.4 + 0.6 * s.scale
            pygame.draw.line(glow, self._light(TORPEDO_COL, 0.3 * k * k), (x0, y0), (x1, y1),
                             max(1, int(12 * k * g)))                       # soft glow around the trail
            pygame.draw.line(glow, self._light(TORPEDO_COL, 0.9 * k * k), (x0, y0), (x1, y1),
                             max(1, int(4 * k * g)))
        pulse = 0.8 + 0.2 * math.sin(s.t * 30.0)
        px, py = int(s.pos[0]), int(s.pos[1])
        g = 0.4 + 0.6 * s.scale
        big = halo(max(10, round(40 * g)), self._light(TORPEDO_COL, pulse))
        glow.blit(big, big.get_rect(center=(px, py)), special_flags=pygame.BLEND_RGB_ADD)
        hot = halo(max(4, round(13 * g)), theme.mix(TORPEDO_COL, (255, 255, 255), 0.8))
        glow.blit(hot, hot.get_rect(center=(px, py)), special_flags=pygame.BLEND_RGB_ADD)

__all__ = ["Flybys", "Pass", "hull_to_screen", "ship_image", "sprite"]
