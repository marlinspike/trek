"""The main menu's second showpiece fight: a Borg cube comes out of a transwarp conduit beside her [E].

`showpiece.Flybys` plans a pass that sails close by an empty patch of stars on the right of the screen
and, once she is well in view, hands it to `CubeBattle`. The scene is a few salvos each way:

1. A green conduit opens and the cube slides out of it, growing as it comes, then the conduit closes.
   She raises her shields.
2. The cube drags a pale green cutting beam across her shields.
3. She answers with phasers and a torpedo salvo. Its shields flare green and hold.
4. It fires a caged Borg torpedo and cuts at her again; her shields hold.
5. She fires phasers again, and the cube adapts: a square ripple runs out from it and her beams die
   on its shields at once.
6. She fires a heavier spread. Two rounds flare on its shields, which flicker and fail; the last two
   reach the hull. Fires break out inside, its green lights stutter and go dark, and it blows apart in
   stages (`blast.Blast`, torn from the cube's own sprite) with a green flash and shockwave of its own.

Every time is in seconds from the conduit opening, so the whole fight reads the same at any frame rate.
Everything is in screen pixels; the cube stands still while she glides past it.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable

import pygame

from . import gfx, theme
from .blast import SHIELD, Blast, HullHit, ShieldFlare, add_light, level, ring
from .fleet_art import art_px, fleet_image
from .showpiece import (BEAM_TIME, EMITTERS, HER_BUBBLE, LAUNCH, PHASER_COL, SPRITE_PX, TORP_SPEED, TORPEDO_COL,
                        TRAIL, hull_to_screen)

CUBE = "borg.cu"
CUBE_LENGTH = 900.0       # world units (hulls.toml): sets the baked sprite's pixels per hull unit
CUBE_HALF = 44.0          # hull units from the cube's centre to a face
CUBE_SIDE = 1.35          # the cube's side on screen, in lengths of her (she is about 102 hull units long)
HER_LENGTH = 102.0        # her length in her own hull units
BUBBLE = 1.5              # the cube's shield radius, in half-sides (just clear of its corners)
CUTTER_COL = (156, 255, 138)     # the Borg's colours, as in factions.toml
BORG_TORP_COL = (93, 255, 122)
HIVE = theme.HIVE
ARMS = 5                  # spiral arms of the transwarp conduit
FIRE = (255, 150, 60)     # fires burning inside it once it is hit
# banks at the middle of each face and either side of it (hull units, x right, y forward)
BANKS = ((0.0, 44.0), (-22.0, 44.0), (22.0, 44.0), (44.0, 0.0), (44.0, 22.0), (44.0, -22.0),
         (0.0, -44.0), (22.0, -44.0), (-22.0, -44.0), (-44.0, 0.0), (-44.0, -22.0), (-44.0, 22.0))

# the fight, in seconds from the conduit opening
OPEN = 0.6                # the conduit opens
ARRIVE = (0.35, 2.2)      # the cube slides out of it
CLOSE = (1.9, 2.8)        # and the conduit closes behind it
SHIELDS_UP = 1.2          # she raises her shields
CUT_1 = 2.9               # its first cutting beam ...
CUT_HOLD = 1.9            # ... held this long, dragged across her shields
PHASERS_1 = 4.9           # her phasers
TORPS_1 = 5.7             # her first salvo: three rounds, all stopped by its shields
BORG_TORP = 7.3           # its torpedo
CUT_2 = 7.7               # and a second cut
PHASERS_2 = 9.5           # her phasers again: it has adapted
FINAL = 10.6              # her last spread: two rounds on the shields, which fail, and two on the hull
CHAIN = (0.35, 0.6, 0.85, 1.05, 1.3, 1.5)    # fires inside it, seconds after the first round reaches the hull
BOOM = 1.85               # ... and it breaks up
SHIELD_FAIL = 0.45        # seconds its shields flicker before they are gone
ADAPT_RIPPLE = 1.1        # seconds the adaptation ripple runs out


@dataclass
class _Round:
    """One of her torpedoes, homing on a point of the cube."""
    t: float                                    # when it leaves the tube
    emitter: tuple[float, float]
    aim: tuple[float, float]                    # the point it homes on, hull units of the cube
    hull: bool                                  # it gets through to the hull (the shields are down by then)
    pos: tuple[float, float] | None = None
    trail: list[tuple[float, float, float]] = field(default_factory=list)
    done: bool = False


@dataclass
class _Cut:
    """A Borg cutting beam, held on her shields and dragged across them."""
    t: float
    bank: tuple[float, float]
    side: float                                 # which way it drags first


@dataclass
class _Cage:
    """A Borg torpedo, homing on her."""
    t: float
    pos: tuple[float, float] | None = None
    trail: list[tuple[float, float, float]] = field(default_factory=list)
    done: bool = False


@dataclass
class _Shot:
    """Her phaser beam at the cube."""
    t: float
    emitter: tuple[float, float]
    life: float = BEAM_TIME
    landed: bool = False                        # it has reached the cube's shields


class CubeBattle:
    """A Borg cube at (x, y), whose side is `side` pixels; she flies past at `her_scale` (sprite scale).

    The same calls as `showpiece.Encounter`: `update(dt, ship, ship_scale)` each frame with where she
    is, `draw(surf, glow, ship, ship_scale)`, and `done` once the wreck has burned out."""

    def __init__(self, x: float, y: float, her_scale: float, rng: random.Random,
                 sound: Callable[[str, float, float], None] | None, width: int, heading: float = 0.0) -> None:
        self.x, self.y = x, y
        self.side = cube_side(her_scale)
        self.k = self.side / (2 * CUBE_HALF)                       # pixels per hull unit of the cube
        self.sprite_scale = self.k / art_px(CUBE_LENGTH)
        self.heading = heading
        self.scale = her_scale
        self.rng = rng
        self.sound = sound
        self.width = width
        self.t = 0.0
        self.alive = True
        self.her_bubble = HER_BUBBLE * SPRITE_PX * her_scale
        self.her_v = (0.0, 0.0)
        self._her_last: tuple[float, float] | None = None
        self.cuts = [_Cut(CUT_1, (0.0, 0.0), 1.0), _Cut(CUT_2, (0.0, 0.0), -1.0)]
        self.cage = _Cage(BORG_TORP)
        self.shots: list[_Shot] = []
        self.rounds: list[_Round] = []
        self.flares: list[ShieldFlare] = []         # on the cube's shields
        self.her_flares: list[ShieldFlare] = []     # on hers, which move with her
        self.hits: list[HullHit] = []
        self.chain: list[tuple[float, float, float, float]] = []    # (time, hx, hy, size): blasts inside it
        self.fires: list[tuple[float, float, float]] = []            # (since, hx, hy): and the fires they leave
        self.adapted_at: float | None = None
        self.shields_fail: float | None = None      # when its shields began to fail
        self.hull_hit: float | None = None          # when the first round reached the hull
        self.blast: Blast | None = None
        self._fired: set[str] = set()
        self._cut_flare = 0.0                       # when a cutting beam last lit her shields
        self._dark: pygame.Surface | None = None

    # ------------------------------------------------------------ geometry

    @property
    def bubble(self) -> float:
        return BUBBLE * CUBE_HALF * self.k

    @property
    def done(self) -> bool:
        return not self.alive and self.blast is not None and self.blast.done

    def point(self, hx: float, hy: float) -> tuple[float, float]:
        """A point on the cube, in its hull units, on screen."""
        a = math.radians(self.heading)
        fx, fy, rx, ry = math.sin(a), -math.cos(a), math.cos(a), math.sin(a)
        return self.x + (hx * rx + hy * fx) * self.k, self.y + (hx * ry + hy * fy) * self.k

    def _facing(self, at: tuple[float, float], n: int = 3) -> list[tuple[float, float]]:
        """The banks on the face that looks at a point, best first."""
        dx, dy = at[0] - self.x, at[1] - self.y

        def toward(b: tuple[float, float]) -> float:
            px, py = self.point(*b)
            return (px - self.x) * dx + (py - self.y) * dy
        return sorted(BANKS, key=toward, reverse=True)[:n]

    def _arrived(self) -> float:
        """0..1: how far the cube has come out of the conduit (eased, so it slows as it arrives)."""
        u = (self.t - ARRIVE[0]) / (ARRIVE[1] - ARRIVE[0])
        u = max(0.0, min(1.0, u))
        return 1 - (1 - u) ** 3

    def _local(self, at: tuple[float, float]) -> tuple[float, float]:
        """A point on screen, in the cube's hull units."""
        a = math.radians(self.heading)
        dx, dy = (at[0] - self.x) / self.k, (at[1] - self.y) / self.k
        return dx * math.cos(a) + dy * math.sin(a), dx * math.sin(a) - dy * math.cos(a)

    def _image(self) -> pygame.Surface | None:
        return fleet_image(CUBE, round(self.heading) % 360, round(self.sprite_scale, 3))

    # ------------------------------------------------------------ sound

    def _play(self, name: str, lvl: float) -> None:
        if self.sound:
            self.sound(name, max(-1.0, min(1.0, self.x / max(1, self.width) * 2 - 1)), lvl)

    def _once(self, key: str, at: float) -> bool:
        """True the first frame the fight reaches `at`, once."""
        if key in self._fired or self.t < at:
            return False
        self._fired.add(key)
        return True

    # ------------------------------------------------------------ running

    def update(self, dt: float, ship: tuple[float, float, float] | None, ship_scale: float) -> None:
        self.t += dt
        self.her_bubble = HER_BUBBLE * SPRITE_PX * ship_scale
        if ship is not None:
            if self._her_last is not None and dt > 0:
                self.her_v = ((ship[0] - self._her_last[0]) / dt, (ship[1] - self._her_last[1]) / dt)
            self._her_last = (ship[0], ship[1])
        if self._once("open", 0.0):
            self._play("hive", 0.5)
        if self._once("shields", SHIELDS_UP):
            self._play("shield", 0.25)
        if ship is not None and self.alive:
            self._script(ship)
        self._cutting(ship)
        self._phasers_land(ship)
        self._cage_flight(dt, ship, ship_scale)
        self._her_rounds(dt, ship, ship_scale)
        self._inside()
        for f in self.flares:
            f.t += dt
        self.flares = [f for f in self.flares if f.t < f.life]
        for f in self.her_flares:
            f.t += dt
            if ship is not None:
                f.x, f.y = ship[0], ship[1]
        self.her_flares = [f for f in self.her_flares if f.t < f.life]
        for h in self.hits:
            h.update(dt)
        self.hits = [h for h in self.hits if h.t < h.life]
        if self.blast is not None:
            self.blast.update(dt)

    def _script(self, ship: tuple[float, float, float]) -> None:
        """Who fires what, and when."""
        here = (ship[0], ship[1])
        for cut in self.cuts:
            if self._once(f"cut{cut.t}", cut.t):
                cut.bank = self._facing(here, 3)[0 if cut.t == CUT_1 else 1]
                self._play("cutter", 0.45)
        if self._once("cage", BORG_TORP):
            self._play("launch", 0.4)
        for key, at, adapted in (("ph1", PHASERS_1, False), ("ph2", PHASERS_2, True)):
            if self._once(key, at):
                rel = math.radians((_bearing(ship[0], ship[1], self.x, self.y) - ship[2]) % 360.0)
                ranked = sorted(EMITTERS, key=lambda e: -(e[0] * math.sin(rel) + e[1] * math.cos(rel)))
                for n, em in enumerate(ranked[:3 if adapted else 2]):
                    self.shots.append(_Shot(at + 0.14 * n, em, BEAM_TIME * (0.55 if adapted else 1.0)))
                self._play("phaser", 0.4)
                if adapted:
                    self.adapted_at = at + 0.25
        if self._once("t1", TORPS_1):
            for n in range(3):
                self.rounds.append(_Round(TORPS_1 + 0.22 * n, LAUNCH[n % 2], (0.0, 0.0), hull=False))
            self._play("launch", 0.45)
        if self._once("t2", FINAL):
            # where the last two land: on the face that looks at her, a little apart
            face = self._facing(here, 1)[0]
            ux, uy = (1.0, 0.0) if face[0] == 0 else (0.0, 1.0)            # along that face
            spots = [(face[0] * 0.8 + ux * s, face[1] * 0.8 + uy * s) for s in (-14.0, 12.0)]
            for n in range(4):
                hull = n >= 2
                self.rounds.append(_Round(FINAL + 0.2 * n, LAUNCH[n % 2], spots[n - 2] if hull else (0.0, 0.0), hull))
            self._play("launch", 0.5)

    def _cutting(self, ship: tuple[float, float, float] | None) -> None:
        """While a cutting beam is held on her shields, it lights them where it drags."""
        if ship is None or not self.alive:
            return
        for cut in self.cuts:
            age = self.t - cut.t
            if 0.12 <= age < CUT_HOLD and self.t - self._cut_flare >= 0.12:
                self._cut_flare = self.t
                end = self._cut_end(cut, ship, age)
                ang = math.atan2(end[1] - ship[1], end[0] - ship[0])
                self.her_flares.append(ShieldFlare(ship[0], ship[1], self.her_bubble, self.her_bubble, ang, 0.5,
                                                   life=0.55, color=theme.mix(SHIELD, CUTTER_COL, 0.25)))

    def _phasers_land(self, ship: tuple[float, float, float] | None) -> None:
        """Each of her beams lights its shields where it lands (a short, faint flare once it has adapted)."""
        if ship is None or not self.alive:
            return
        for s in self.shots:
            if not s.landed and self.t - s.t >= 0.07:
                s.landed = True
                ang = math.atan2(ship[1] - self.y, ship[0] - self.x)
                self.flares.append(ShieldFlare(self.x, self.y, self.bubble, self.bubble, ang, 0.55,
                                               life=s.life + 0.25, color=HIVE))

    def _cut_end(self, cut: _Cut, ship: tuple[float, float, float], age: float) -> tuple[float, float]:
        """Where a cutting beam meets her shields: the near side of the bubble, dragged back and forth."""
        p0 = self.point(*cut.bank)
        base = math.atan2(p0[1] - ship[1], p0[0] - ship[0])
        ang = base + cut.side * 0.42 * math.sin(age * math.tau * 0.42)
        return ship[0] + math.cos(ang) * self.her_bubble, ship[1] + math.sin(ang) * self.her_bubble

    def _cage_flight(self, dt: float, ship: tuple[float, float, float] | None, ship_scale: float) -> None:
        c = self.cage
        if c.done or self.t < c.t:
            return
        if c.pos is None:
            if ship is None or not self.alive:
                c.done = True
                return
            c.pos = self.point(*self._facing((ship[0], ship[1]), 1)[0])
        if ship is None:
            c.done = True
            return
        dx, dy = ship[0] - c.pos[0], ship[1] - c.pos[1]
        d = math.hypot(dx, dy) or 1.0
        speed = TORP_SPEED * max(ship_scale, 0.3) * 1.25          # slower than hers: heavy, deliberate
        c.pos = (c.pos[0] + dx / d * speed * dt, c.pos[1] + dy / d * speed * dt)
        c.trail.append((c.pos[0], c.pos[1], self.t))
        c.trail = [q for q in c.trail if self.t - q[2] <= TRAIL]
        if d <= self.her_bubble:
            c.done = True
            self.her_flares.append(ShieldFlare(ship[0], ship[1], self.her_bubble, self.her_bubble,
                                               math.atan2(-dy, -dx), 1.0, life=1.0))
            self._play("shield", 0.45)

    def _her_rounds(self, dt: float, ship: tuple[float, float, float] | None, ship_scale: float) -> None:
        speed = TORP_SPEED * max(ship_scale, 0.3) * 1.8
        for r in self.rounds:
            if r.done or self.t < r.t:
                continue
            if r.pos is None:
                if ship is None:
                    r.done = True
                    continue
                r.pos = hull_to_screen(ship[0], ship[1], ship[2], ship_scale, *r.emitter)
            tx, ty = self.point(*r.aim)
            dx, dy = tx - r.pos[0], ty - r.pos[1]
            d = math.hypot(dx, dy) or 1.0
            step = min(d, speed * dt)
            r.pos = (r.pos[0] + dx / d * step, r.pos[1] + dy / d * step)
            r.trail.append((r.pos[0], r.pos[1], self.t))
            r.trail = [q for q in r.trail if self.t - q[2] <= TRAIL]
            ang = math.atan2(r.pos[1] - self.y, r.pos[0] - self.x)
            if r.hull:
                if d - step <= 1.0 and self.alive:
                    r.done = True
                    self.hits.append(_hull_hit(r.pos, 24 * self.k, self.rng))
                    self.fires.append((self.t, *self._local(r.pos)))
                    self._play("hull", 0.5)
                    if self.hull_hit is None:
                        self.hull_hit = self.t
                        self._plan_chain()
            elif math.hypot(r.pos[0] - self.x, r.pos[1] - self.y) <= self.bubble and self.alive:
                r.done = True
                self.flares.append(ShieldFlare(self.x, self.y, self.bubble, self.bubble, ang, 1.0, life=1.0, color=HIVE))
                self._play("shield", 0.4)
                if r.t >= FINAL and self.shields_fail is None and sum(
                        1 for q in self.rounds if q.t >= FINAL and q.done and not q.hull) == 2:
                    self.shields_fail = self.t
                    self._play("collapse", 0.45)

    def _plan_chain(self) -> None:
        """Fires break out through the cube, one after another, until it goes up."""
        rng = self.rng
        for at in CHAIN:
            self.chain.append((self.t + at, rng.uniform(-34, 34), rng.uniform(-34, 34), rng.uniform(14, 22)))

    def _inside(self) -> None:
        for at, hx, hy, size in self.chain:
            if self._once(f"chain{at}", at):
                self.hits.append(_hull_hit(self.point(hx, hy), size * self.k, self.rng))
                self.fires.append((self.t, hx, hy))
                self._play("blast", 0.25)
        if self.hull_hit is not None and self.alive and self.t >= self.hull_hit + BOOM:
            self.alive = False
            self.blast = Blast(self.x, self.y, self.side * 0.42, seed=self.rng.randrange(1 << 30), shock=3.6)
            self.blast.life = 4.6
            self.blast.start(self._image())
            self._play("breakup", 0.75)

    # ------------------------------------------------------------ drawing

    def draw(self, surf: pygame.Surface, glow: pygame.Surface, ship: tuple[float, float, float] | None,
             ship_scale: float) -> None:
        self._conduit(glow)
        if self.alive:
            self._cube(surf, glow)
        if self.blast is not None:
            self.blast.draw_pieces(surf)
            self.blast.draw(glow)
            self._green_flash(glow)
        self._cube_shields(glow)
        self._adaptation(glow)
        if ship is not None:
            self._her_shields(glow, ship)
            if self.alive:
                for cut in self.cuts:
                    age = self.t - cut.t
                    if 0 <= age < CUT_HOLD + 0.25:
                        self._cutter(glow, cut, ship, age)
            for s in self.shots:
                age = self.t - s.t
                if 0 <= age < s.life:
                    self._phaser(glow, s, ship, ship_scale, age)
        if self.cage.pos is not None and not self.cage.done:
            self._cage(glow, ship_scale)
        for r in self.rounds:
            if r.pos is not None and not r.done:
                self._round(glow, r, ship_scale)
        for f in self.flares:
            f.draw(glow)
        for f in self.her_flares:
            f.draw(glow)
        for h in self.hits:
            h.draw(glow)

    def _conduit(self, glow: pygame.Surface) -> None:
        """A transwarp conduit opens where the cube will be, lets it out, and closes."""
        t = self.t
        if t >= CLOSE[1]:
            return
        opening = min(1.0, t / OPEN)
        closing = max(0.0, min(1.0, (t - CLOSE[0]) / (CLOSE[1] - CLOSE[0])))
        u = (1 - (1 - opening) ** 2) * (1 - closing ** 1.5)
        r = self.bubble * 1.15 * u
        if r < 2:
            return
        add_light(glow, self.x, self.y, r * 1.1, HIVE, 0.3 * u)                    # its mouth, faintly lit
        add_light(glow, self.x, self.y, r * 0.35, (200, 255, 210), 0.35 * u)
        ring(glow, self.x, self.y, r, r, HIVE, 0.3 * u, 1)                          # its rim
        for arm in range(ARMS):                                                     # a vortex, turning
            base = t * 1.4 + arm * math.tau / ARMS
            pts = []
            for q in range(25):
                f = 0.12 + 0.88 * q / 24                                            # from near the middle out to the rim
                a = base + 2.4 * math.log(f)                                        # a spiral arm
                pts.append((self.x + math.cos(a) * r * f, self.y + math.sin(a) * r * f))
            for (p0, p1), q in zip(zip(pts, pts[1:]), range(24)):
                k = u * (1 - q / 24) ** 0.8                                         # bright at the heart, fading out
                gfx.draw.aaline(glow, level(HIVE, 0.16 * k), p0, p1, 7)
                gfx.draw.aaline(glow, level(HIVE, 0.6 * k), p0, p1, 1.5)
        if t < OPEN + 0.3:                                                         # a flash as it opens
            add_light(glow, self.x, self.y, r * 0.6, (220, 255, 225), 0.6 * (1 - t / (OPEN + 0.3)))

    def _cube(self, surf: pygame.Surface, glow: pygame.Surface) -> None:
        img = self._image()
        a = self._arrived()
        if a <= 0:
            return
        if img is not None:
            if a < 1.0:
                grown = gfx.transform.rotozoom(img, 0.0, 0.25 + 0.75 * a)
                grown.set_alpha(int(255 * min(1.0, a * 1.6)))
                surf.blit(grown, grown.get_rect(center=(round(self.x), round(self.y))))
            else:
                surf.blit(img, img.get_rect(center=(round(self.x), round(self.y))))
                if self.hull_hit is not None:
                    self._stutter(surf, img)
        # its own green light, faint all over, breathing slowly; it dies with the cube
        dying = 0.0 if self.hull_hit is None else min(1.0, (self.t - self.hull_hit) / BOOM)
        breathe = 0.85 + 0.15 * math.sin(self.t * 1.3)
        add_light(glow, self.x, self.y, self.side * 0.72 * (0.25 + 0.75 * a), HIVE, 0.16 * a * breathe * (1 - dying))
        for since, hx, hy in self.fires:                       # fires burning through it, flickering, spreading
            age = self.t - since
            x, y = self.point(hx, hy)
            flick = 0.75 + 0.25 * math.sin(self.t * 23.0 + hx) * math.sin(self.t * 9.0 + hy)
            grow = min(1.0, 0.4 + age * 0.8)
            add_light(glow, x, y, 9 * self.k * grow, FIRE, 0.55 * flick)
            add_light(glow, x, y, 3 * self.k, (255, 230, 190), 0.6 * flick)

    def _stutter(self, surf: pygame.Surface, img: pygame.Surface) -> None:
        """Once it is hit, its lights stutter and fail: a darker copy laid over it, more often as it dies."""
        assert self.hull_hit is not None
        if self._dark is None or self._dark.get_size() != img.get_size():
            self._dark = img.copy()
            self._dark.fill((70, 70, 70), special_flags=pygame.BLEND_RGB_MULT)
        u = min(1.0, (self.t - self.hull_hit) / BOOM)
        flick = random.Random(int(self.t * 14)).random()            # steady within a frame or two, not a strobe
        if flick < 0.25 + 0.75 * u:
            dark = self._dark.copy() if u < 1 else self._dark
            if u < 1:
                dark.set_alpha(int(150 + 105 * u))
            surf.blit(dark, dark.get_rect(center=(round(self.x), round(self.y))))

    def _green_flash(self, glow: pygame.Surface) -> None:
        """As it goes, a hard green flash and a ring of green light: the hive's own fire."""
        assert self.blast is not None
        t = self.blast.t
        if t < 0.7:
            k = 1 - t / 0.7
            add_light(glow, self.x, self.y, self.side * 1.1, HIVE, 0.5 * k * k)
        u = (t - 0.12) / 1.7
        if 0 <= u < 1:
            rr = self.side * (0.45 + 1.5 * u ** 0.7)
            ring(glow, self.x, self.y, rr, rr * 0.3, HIVE, 0.7 * (1 - u) ** 1.5, 2, self.blast.tilt + 0.25)

    def _cube_shields(self, glow: pygame.Surface) -> None:
        """Its shields flicker and fail when the last spread breaks them."""
        if self.shields_fail is None or not self.alive:
            return
        u = (self.t - self.shields_fail) / SHIELD_FAIL
        if 0 <= u < 1 and int(u * 7) % 2 == 0:
            ring(glow, self.x, self.y, self.bubble, self.bubble, HIVE, 0.5 * (1 - u), 1)

    def _adaptation(self, glow: pygame.Surface) -> None:
        """It adapts: a square ripple runs out from it, the shape of the hive."""
        if self.adapted_at is None or not self.alive:
            return
        u = (self.t - self.adapted_at) / ADAPT_RIPPLE
        if not 0 <= u < 1:
            return
        half = CUBE_HALF * self.k * (1.05 + 1.1 * u ** 0.6)
        a = math.radians(self.heading)
        c, s = math.cos(a), math.sin(a)
        pts = [(self.x + (hx * c - hy * s) * half, self.y + (hx * s + hy * c) * half)
               for hx, hy in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        k = (1 - u) ** 1.4
        for width, share in ((7, 0.15), (3, 0.35), (1, 0.9)):
            gfx.draw.lines(glow, level(HIVE, k * share), True, pts, width)

    def _her_shields(self, glow: pygame.Surface, ship: tuple[float, float, float]) -> None:
        """Her shields snap up as the conduit opens and hold a faint shimmer until it is over."""
        u = self.t - SHIELDS_UP
        if u < 0:
            return
        end = self.hull_hit + BOOM + 1.5 if self.hull_hit is not None else 1e9
        fade = 1.0 if self.t < end else max(0.0, 1.0 - (self.t - end) / 0.8)
        if fade <= 0:
            return
        snap = max(0.0, 1.0 - u / 0.5)
        r = self.her_bubble * (0.85 + 0.15 * min(1.0, u / 0.25))
        ring(glow, ship[0], ship[1], r, r, SHIELD, (0.18 + 0.6 * snap) * fade, 1)
        if snap > 0:
            add_light(glow, ship[0], ship[1], r * 1.1, SHIELD, 0.25 * snap)

    def _cutter(self, glow: pygame.Surface, cut: _Cut, ship: tuple[float, float, float], age: float) -> None:
        """A pale green beam, held: it races out to her shields, drags across them, then pulls in."""
        p0 = self.point(*cut.bank)
        end = self._cut_end(cut, ship, age)
        reach = min(1.0, age / 0.12)
        p1 = (p0[0] + (end[0] - p0[0]) * reach, p0[1] + (end[1] - p0[1]) * reach)
        fade = 1.0 if age < CUT_HOLD else max(0.0, 1 - (age - CUT_HOLD) / 0.25)
        if age >= CUT_HOLD:                                                       # the tail pulls in to her
            u = 1 - fade
            p0 = (p0[0] + (p1[0] - p0[0]) * u, p0[1] + (p1[1] - p0[1]) * u)
        shimmer = 0.85 + 0.15 * math.sin(self.t * 37.0)
        g = 0.4 + 0.6 * self.scale
        core = theme.mix(CUTTER_COL, (255, 255, 255), 0.55)
        for width, lvl in ((22, 0.10), (12, 0.24), (6, 0.5)):
            gfx.draw.aaline(glow, level(CUTTER_COL, lvl * fade * shimmer), p0, p1, max(1.0, width * g))
        gfx.draw.aaline(glow, level(core, 0.95 * fade), p0, p1, 2)
        add_light(glow, p0[0], p0[1], max(5, 24 * self.scale), CUTTER_COL, 0.8 * fade)
        if reach >= 1:
            add_light(glow, p1[0], p1[1], max(6, 26 * self.scale), (225, 255, 230), 0.7 * fade * shimmer)

    def _phaser(self, glow: pygame.Surface, s: _Shot, ship: tuple[float, float, float], scale: float, age: float) -> None:
        """Her phasers, stopped on its shields (or on its hull once they are down)."""
        p0 = hull_to_screen(ship[0], ship[1], ship[2], scale, *s.emitter)
        dx, dy = self.x - p0[0], self.y - p0[1]
        d = math.hypot(dx, dy) or 1.0
        stop = max(0.0, d - self.bubble) if self.alive else d
        reach = min(1.0, age / 0.07)
        p1 = (p0[0] + dx / d * stop * reach, p0[1] + dy / d * stop * reach)
        k = max(0.0, 1.0 - age / s.life)
        k = k * k * (3 - 2 * k)
        g = 0.4 + 0.6 * scale
        core = theme.mix(PHASER_COL, (255, 255, 255), 0.55)
        for width, lvl in ((17, 0.10), (9, 0.22), (5, 0.45)):
            gfx.draw.aaline(glow, level(PHASER_COL, lvl * k), p0, p1, max(1.0, width * g))
        gfx.draw.aaline(glow, level(core, 0.95 * k), p0, p1, 2)
        add_light(glow, p0[0], p0[1], max(4, 26 * scale), core, k)
        if reach >= 1:
            add_light(glow, p1[0], p1[1], max(6, 30 * scale), (220, 255, 225), k)

    def _cage(self, glow: pygame.Surface, scale: float) -> None:
        """Its torpedo: a hard green core in a tumbling square cage, with a cold green trail."""
        c = self.cage
        assert c.pos is not None
        g = 0.4 + 0.6 * scale
        for (x0, y0, t0), (x1, y1, _) in zip(c.trail, c.trail[1:]):
            k = 1.0 - (self.t - t0) / TRAIL
            gfx.draw.aaline(glow, level(BORG_TORP_COL, 0.22 * k * k), (x0, y0), (x1, y1), max(1.0, 10 * k * g))
            gfx.draw.aaline(glow, level(BORG_TORP_COL, 0.7 * k * k), (x0, y0), (x1, y1), max(1.0, 3 * k * g))
        x, y = c.pos
        add_light(glow, x, y, max(10, 36 * g), BORG_TORP_COL, 0.6)
        add_light(glow, x, y, max(4, 12 * g), theme.mix(BORG_TORP_COL, (255, 255, 255), 0.6), 1.0)
        for j, (spin, reach, lvl) in enumerate(((1.6, 2.4, 0.75), (-1.1, 1.7, 0.5))):     # two cages turning against each other
            a0 = self.t * spin + j * math.pi / 4
            r = max(4.0, 9 * g) * reach
            pts = [(x + math.cos(a0 + q * math.pi / 2) * r, y + math.sin(a0 + q * math.pi / 2) * r) for q in range(4)]
            gfx.draw.lines(glow, level(BORG_TORP_COL, lvl), True, pts, 1)

    def _round(self, glow: pygame.Surface, r: _Round, scale: float) -> None:
        g = 0.4 + 0.6 * scale
        for (x0, y0, t0), (x1, y1, _) in zip(r.trail, r.trail[1:]):
            k = 1.0 - (self.t - t0) / TRAIL
            gfx.draw.aaline(glow, level(TORPEDO_COL, 0.3 * k * k), (x0, y0), (x1, y1), max(1.0, 12 * k * g))
            gfx.draw.aaline(glow, level(TORPEDO_COL, 0.9 * k * k), (x0, y0), (x1, y1), max(1.0, 4 * k * g))
        assert r.pos is not None
        pulse = 0.8 + 0.2 * math.sin(self.t * 30.0)
        add_light(glow, r.pos[0], r.pos[1], max(10, 40 * g), TORPEDO_COL, pulse)
        add_light(glow, r.pos[0], r.pos[1], max(4, 13 * g), theme.mix(TORPEDO_COL, (255, 255, 255), 0.8), 1.0)


def cube_side(her_scale: float) -> float:
    """The cube's side on screen, pixels, beside her drawn at `her_scale`."""
    return CUBE_SIDE * HER_LENGTH * SPRITE_PX * her_scale


def _hull_hit(at: tuple[float, float], size: float, rng: random.Random) -> HullHit:
    hit = HullHit(at[0], at[1], size)
    hit.start(rng)
    return hit


def _bearing(x0: float, y0: float, x1: float, y1: float) -> float:
    return math.degrees(math.atan2(x1 - x0, -(y1 - y0))) % 360.0


__all__ = ["CubeBattle", "cube_side"]
