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
from .blast import Blast, CLOAK, HullHit, ShieldFlare, add_light, halo, level as blast_level, ring

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
ENCOUNTER_ODDS = 0.25     # chance that a distant pass meets a Klingon
ENCOUNTER_FAR = 0.42      # only passes drawn at this scale or smaller (she is far off)
KLINGON_SPRITE = "klingon-battlecruiser.png"
KLINGON_SCALE = 0.9       # the Klingon's scale relative to hers (it is a little smaller)
KLINGON_BUBBLE = 38.0     # shield radius, hull units
KLINGON_SIZE = 30.0       # rough radius of the hull, hull units
DECLOAK = 1.6             # seconds for the cloak to fall
OPEN_FIRE = 2.4           # seconds after decloaking starts that she fires phasers
TORPEDOES = 3.3           # ... and launches torpedoes
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


NAV_PERIOD = 2.4          # seconds between flashes of the navigation lights
NAV_FLASH = 0.22          # how long a flash lasts
ENGINE_PULSE = 0.7        # engine glow pulses per second
# hull-unit positions (tools/render_ship.py): nav lights on the saucer rim, port red and starboard green
NAV_LIGHTS = (((-24.4, 24.0), (255, 50, 40)), ((24.4, 24.0), (60, 255, 110)))
BUSSARDS = ((-17.0, -11.8), (17.0, -11.8))
IMPULSE = ((-3.2, 0.4), (3.2, 0.4))
NACELLE_SPANS = tuple((x, y) for x in (-17.0, 17.0) for y in (-40.0, -33.0, -26.0, -19.0))


def ship_lights(surf: pygame.Surface, cx: float, cy: float, heading: float, scale: float, t: float) -> None:
    """Add the living lights onto a drawn sprite centred at (cx, cy): engines that glow and pulse softly,
    and navigation lights that flash briefly every couple of seconds. Additive, so draw it last."""
    k = SPRITE_PX * scale                     # pixels per hull unit
    pulse = 0.8 + 0.2 * math.sin(t * ENGINE_PULSE * 2 * math.pi)

    def light(hx: float, hy: float, units: float, col: tuple[int, int, int], level: float) -> None:
        c = blast_level(col, level)
        if c == (0, 0, 0):
            return
        img = halo(max(3, round(units * k)), c)
        x, y = hull_to_screen(cx, cy, heading, scale, hx, hy)
        surf.blit(img, img.get_rect(center=(round(x), round(y))), special_flags=pygame.BLEND_RGB_ADD)

    for hx, hy in NACELLE_SPANS:
        light(hx, hy, 6.0, (70, 130, 255), 0.30 * pulse)
    for hx, hy in BUSSARDS:
        light(hx, hy, 7.0, (255, 120, 50), 0.55 * pulse)
        light(hx, hy, 2.6, (255, 200, 150), 0.6 * pulse)
    for hx, hy in IMPULSE:
        light(hx, hy, 4.0, (255, 80, 40), 0.45 * pulse)
    phase = t % NAV_PERIOD
    if phase < NAV_FLASH:
        f = math.sin(math.pi * phase / NAV_FLASH)          # a quick, soft rise and fall
        for (hx, hy), col in NAV_LIGHTS:
            light(hx, hy, 5.5, col, 0.9 * f)
            light(hx, hy, 1.6, (255, 255, 255), 0.7 * f)


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
    klingon: bool = False                     # a distant pass on which a Klingon decloaks and is destroyed
    met: bool = False                         # ... and it has

    @property
    def heading(self) -> float:
        """Her one heading for the whole pass, in whole degrees so the sprite is turned once."""
        (x0, y0), (x2, y2) = self.start, self.end
        return float(round(math.degrees(math.atan2(x2 - x0, -(y2 - y0)))) % 360)

    def at(self, u: float) -> tuple[float, float, float]:
        """(x, y, heading) a fraction u along a straight line: no turning, so nothing twitches."""
        (x0, y0), (x2, y2) = self.start, self.end
        return x0 + (x2 - x0) * u, y0 + (y2 - y0) * u, self.heading

@lru_cache(maxsize=None)
def klingon_sprite() -> pygame.Surface | None:
    """The Klingon battle cruiser (tools/render_klingon.py), pointing up, or None if the art is missing."""
    try:
        img = pygame.image.load(str(SHIP_DIR / KLINGON_SPRITE))
        return img.convert_alpha() if pygame.display.get_surface() is not None else img
    except (FileNotFoundError, pygame.error, OSError):
        return None


@lru_cache(maxsize=16)
def klingon_image(heading: float, scale: float) -> pygame.Surface | None:
    img = klingon_sprite()
    return None if img is None else pygame.transform.rotozoom(img, -heading, scale)


def _bearing(x0: float, y0: float, x1: float, y1: float) -> float:
    """Screen bearing from one point to another, degrees clockwise from up."""
    return math.degrees(math.atan2(x1 - x0, -(y1 - y0))) % 360.0


@dataclass
class _Round:
    """A torpedo of the encounter, homing on the Klingon."""
    t: float
    emitter: tuple[float, float]
    last: bool                                  # the one that gets through
    pos: tuple[float, float] | None = None
    trail: list[tuple[float, float, float]] = field(default_factory=list)
    done: bool = False


class Encounter:
    """A Klingon battle cruiser decloaks off her beam; she answers with phasers, which its shields
    stop, then a torpedo salvo that batters the shields down and breaks it apart."""

    def __init__(self, x: float, y: float, scale: float, rng: random.Random,
                 sound: Callable[[str, float, float], None] | None, width: int) -> None:
        self.x, self.y = x, y
        self.scale = scale * KLINGON_SCALE
        self.k = SPRITE_PX * self.scale           # pixels per hull unit
        self.heading = 0.0
        self.rng = rng
        self.sound = sound
        self.width = width
        self.t = 0.0
        self.alive = True
        self.beams: list[tuple[float, tuple[float, float]]] = []     # (start time, emitter)
        self.rounds: list[_Round] = []
        self.flares: list[ShieldFlare] = []
        self.hits: list[HullHit] = []
        self.blast: Blast | None = None
        self.boom_at: float | None = None
        self.fired = 0                            # 1 phasers, 2 torpedoes

    @property
    def bubble(self) -> float:
        return KLINGON_BUBBLE * self.k

    @property
    def done(self) -> bool:
        return not self.alive and self.blast is not None and self.blast.done

    def _pan(self) -> float:
        return max(-1.0, min(1.0, self.x / max(1, self.width) * 2 - 1))

    def _play(self, name: str, level: float) -> None:
        if self.sound:
            self.sound(name, self._pan(), level)

    def update(self, dt: float, ship: tuple[float, float, float] | None, ship_scale: float) -> None:
        before = self.t
        self.t += dt
        if before == 0.0:
            self._play("cloak", 0.35)
        if ship is not None and self.alive:
            self.heading = _bearing(self.x, self.y, ship[0], ship[1])       # it turns to face her
            rel = math.radians((_bearing(ship[0], ship[1], self.x, self.y) - ship[2]) % 360.0)
            if self.fired == 0 and self.t >= OPEN_FIRE:
                self.fired = 1
                ranked = sorted(EMITTERS, key=lambda e: -(e[0] * math.sin(rel) + e[1] * math.cos(rel)))
                for n, em in enumerate(ranked[:2]):
                    self.beams.append((self.t + 0.14 * n, em))
                self._play("phaser", 0.4)
            elif self.fired == 1 and self.t >= TORPEDOES:
                self.fired = 2
                for n in range(3):
                    self.rounds.append(_Round(self.t + 0.22 * n, LAUNCH[n % 2], last=n == 2))
                self._play("launch", 0.45)
        for t0, _ in self.beams:                                            # each beam lights the shield where it lands
            if before < t0 + 0.02 <= self.t and ship is not None:
                self.flares.append(ShieldFlare(self.x, self.y, self.bubble, self.bubble,
                                               math.atan2(ship[1] - self.y, ship[0] - self.x), 0.6, life=BEAM_TIME + 0.3))
        speed = TORP_SPEED * max(ship_scale, 0.3) * 1.8          # quick enough that the fight reads as one
        for r in self.rounds:
            if r.done or self.t < r.t:
                continue
            if r.pos is None:
                if ship is None:
                    r.done = True
                    continue
                r.pos = hull_to_screen(ship[0], ship[1], ship[2], ship_scale, *r.emitter)
            dx, dy = self.x - r.pos[0], self.y - r.pos[1]
            d = math.hypot(dx, dy) or 1.0
            r.pos = (r.pos[0] + dx / d * speed * dt, r.pos[1] + dy / d * speed * dt)
            r.trail.append((r.pos[0], r.pos[1], self.t))
            r.trail = [q for q in r.trail if self.t - q[2] <= TRAIL]
            reach = KLINGON_SIZE * 0.3 * self.k if r.last else self.bubble
            if d <= reach and self.alive:
                r.done = True
                ang = math.atan2(-dy, -dx)
                if r.last:
                    hit = HullHit(r.pos[0], r.pos[1], 14 * self.k)
                    hit.start(self.rng)
                    self.hits.append(hit)
                    self.flares.append(ShieldFlare(self.x, self.y, self.bubble, self.bubble, ang, 0.5, life=0.5))
                    self.boom_at = self.t + 0.35
                    self._play("blast", 0.5)
                else:
                    self.flares.append(ShieldFlare(self.x, self.y, self.bubble, self.bubble, ang, 1.0))
                    self._play("shield", 0.4)
        if self.boom_at is not None and self.t >= self.boom_at and self.alive:
            self.alive = False
            self.blast = Blast(self.x, self.y, KLINGON_SIZE * self.k, seed=self.rng.randrange(1 << 30))
            self.blast.start(klingon_image(round(self.heading) % 360, round(self.scale, 3)))
            self._play("breakup", 0.7)
        for f in self.flares:
            f.t += dt
        self.flares = [f for f in self.flares if f.t < f.life]
        for h in self.hits:
            h.update(dt)
        self.hits = [h for h in self.hits if h.t < h.life]
        if self.blast is not None:
            self.blast.update(dt)

    def draw(self, surf: pygame.Surface, glow: pygame.Surface, ship: tuple[float, float, float] | None,
             ship_scale: float) -> None:
        if self.alive:
            img = klingon_image(round(self.heading) % 360, round(self.scale, 3))
            if img is not None:
                self._ship(surf, glow, img)
        if self.blast is not None:
            self.blast.draw_pieces(surf)
            self.blast.draw(glow)
        if ship is not None:
            for t0, em in self.beams:
                age = self.t - t0
                if 0 <= age < BEAM_TIME:
                    self._beam(glow, ship, ship_scale, em, age)
        for r in self.rounds:
            if r.pos is not None and not r.done:
                self._round(glow, r, ship_scale)
        for f in self.flares:
            f.draw(glow)
        for h in self.hits:
            h.draw(glow)

    def _ship(self, surf: pygame.Surface, glow: pygame.Surface, img: pygame.Surface) -> None:
        """The cruiser, shimmering into view while the cloak falls."""
        u = min(1.0, self.t / DECLOAK)
        rect = img.get_rect(center=(round(self.x), round(self.y)))
        if u >= 1.0:
            surf.blit(img, rect)
        else:
            ghost = img.copy()
            ghost.set_alpha(int(255 * u ** 1.5))
            amp = 6.0 * (1 - u) * max(1.0, self.k)
            band = 3
            for row in range(0, img.get_height(), band):       # the picture wavers as it resolves
                dx = math.sin(row * 0.18 + self.t * 14.0) * amp
                surf.blit(ghost, (rect.x + dx, rect.y + row), pygame.Rect(0, row, img.get_width(), band))
            ring(glow, self.x, self.y, self.bubble * (0.6 + 0.6 * u), self.bubble * (0.6 + 0.6 * u), CLOAK,
                 0.5 * math.sin(math.pi * u), 1)
        # its nacelles and torpedo launcher glow red, more so once it has fully dropped the cloak
        a = math.radians(self.heading)
        fx, fy, rx, ry = math.sin(a), -math.cos(a), math.cos(a), math.sin(a)
        for hx, hy, rad, col in ((-27.5, -1.5, 5.0, (255, 80, 40)), (27.5, -1.5, 5.0, (255, 80, 40)),
                                 (0.0, 37.6, 4.0, (255, 70, 40))):
            hy -= 5.0                                            # the sprite's centre is 5 units forward of its origin
            px = self.x + (hx * rx + hy * fx) * self.k
            py = self.y + (hx * ry + hy * fy) * self.k
            add_light(glow, px, py, rad * self.k * 1.6, col, 0.5 * u * (0.85 + 0.15 * math.sin(self.t * 5)))

    def _beam(self, glow: pygame.Surface, ship: tuple[float, float, float], scale: float,
              em: tuple[float, float], age: float) -> None:
        p0 = hull_to_screen(ship[0], ship[1], ship[2], scale, *em)
        dx, dy = self.x - p0[0], self.y - p0[1]
        d = math.hypot(dx, dy) or 1.0
        stop = max(0.0, d - self.bubble) if self.alive else d
        p1 = (p0[0] + dx / d * stop, p0[1] + dy / d * stop)
        k = max(0.0, 1.0 - age / BEAM_TIME)
        k = k * k * (3 - 2 * k)
        g = 0.4 + 0.6 * scale
        core = theme.mix(PHASER_COL, (255, 255, 255), 0.55)
        for width, lvl in ((17, 0.10), (9, 0.22), (5, 0.45)):
            pygame.draw.line(glow, blast_level(PHASER_COL, lvl * k), p0, p1, max(1, round(width * g)))
        pygame.draw.line(glow, blast_level(core, 0.95 * k), p0, p1, 2)
        add_light(glow, p0[0], p0[1], max(4, 26 * scale), core, k)
        add_light(glow, p1[0], p1[1], max(6, 30 * scale), (230, 245, 255), k)

    def _round(self, glow: pygame.Surface, r: _Round, scale: float) -> None:
        g = 0.4 + 0.6 * scale
        for (x0, y0, t0), (x1, y1, _) in zip(r.trail, r.trail[1:]):
            k = 1.0 - (self.t - t0) / TRAIL
            pygame.draw.line(glow, blast_level(TORPEDO_COL, 0.3 * k * k), (x0, y0), (x1, y1), max(1, int(12 * k * g)))
            pygame.draw.line(glow, blast_level(TORPEDO_COL, 0.9 * k * k), (x0, y0), (x1, y1), max(1, int(4 * k * g)))
        assert r.pos is not None
        pulse = 0.8 + 0.2 * math.sin(self.t * 30.0)
        add_light(glow, r.pos[0], r.pos[1], max(10, 40 * g), TORPEDO_COL, pulse)
        add_light(glow, r.pos[0], r.pos[1], max(4, 13 * g), theme.mix(TORPEDO_COL, (255, 255, 255), 0.8), 1.0)


class Flybys:
    """Plans and draws the passes. `sound(name, pan, level)` is called when she fires, if given."""

    def __init__(self, seed: int = 1701, sound: Callable[[str, float, float], None] | None = None) -> None:
        self.rng = random.Random(seed)
        self.sound = sound
        self.current: Pass | None = None
        self.wait = 1.2                       # a moment of empty stars before the first pass
        self.shots: list[Shot] = []
        self.next_kind = "torpedo"            # firing passes take turns to lead with torpedoes and phasers
        self.clock = 0.0                      # seconds since the menu opened, for the lights
        self.encounter_odds = ENCOUNTER_ODDS
        self.encounter: Encounter | None = None
        klingon_sprite()                      # loaded now, not in the middle of a pass
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
        if scale <= ENCOUNTER_FAR and r.random() < self.encounter_odds:
            return Pass(start, mid, end, (a_len + b_len) / speed, scale, [], klingon=True)
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
        self.clock += dt
        if self.encounter is not None:
            cur = self.current
            ship = cur.at(min(1.0, cur.t / cur.duration)) if cur is not None else None
            self.encounter.update(dt, ship, cur.scale if cur is not None else 1.0)
            if self.encounter.done:
                self.encounter = None
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
        if p.klingon and not p.met and self.encounter is None:
            self._meet(p, u)
        if u >= 1.0:
            self.current = None
            self.wait = self.rng.uniform(2.5, 7.0)

    def _meet(self, p: Pass, u: float) -> None:
        """Once she is well on screen, a Klingon decloaks off her beam, ahead of her."""
        w, h = self.size
        x, y, hdg = p.at(u)
        if not (0.25 <= u <= 0.6 and 80 < x < w - 80 and 80 < y < h - 80):
            return
        p.met = True                            # one meeting per pass, whether or not there is room for it
        a = math.radians(hdg)
        fx, fy, rx, ry = math.sin(a), -math.cos(a), math.cos(a), math.sin(a)
        reach = 1700.0 * p.scale                # well clear of her, at about her distance
        for side in self.rng.sample((-1, 1), 2):
            kx = x + fx * reach * 0.55 + rx * side * reach
            ky = y + fy * reach * 0.55 + ry * side * reach
            if 470 < kx < w - 90 and 90 < ky < h - 90:      # on screen and clear of the menu buttons
                self.encounter = Encounter(kx, ky, p.scale, self.rng, self.sound, w)
                return

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
        if self.encounter is not None:
            self.encounter.draw(surf, glow, ship_at, ship_scale)
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
                ship_lights(glow, x, y, hdg, ship_scale, self.clock)
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

__all__ = ["Encounter", "Flybys", "Pass", "hull_to_screen", "ship_image", "ship_lights", "sprite"]
