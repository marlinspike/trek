"""Short-lived procedural effects driven by simulation events.

Effects live in world coordinates and real (wall-clock) seconds, so they
read the same at every time scale and keep animating while paused.

Weapons are coloured by the race that fired them (`colors` in
factions.toml) [E]: each race's beams have their own colour and style
(a steady beam or a string of bolts), and its torpedoes and their blasts
their own colour. A ship we can't identify fires in neutral white. A
torpedo set off by a phaser before it reached anything "fizzles": a small
grey flash with a few sparks of debris, nothing like the bright ring and
flash of one that went off where it was meant to.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field

import pygame

from collections.abc import Callable

from ..content.schema import Faction
from ..sim.events import DeflectorPulsed, Detonation, Event, OrdnanceDestroyed, PhaserFired, ShieldHit, ShipStatusChanged
from . import theme
from .camera import Camera


@dataclass
class Beam:
    x0: float
    y0: float
    x1: float
    y1: float
    spread: float
    color: theme.Color
    life: float = 0.38
    age: float = 0.0
    width: float = 2.0
    cone: tuple[float, float, float] | None = None  # (facing, spread, range) for the faint cone
    style: str = "beam"     # "beam" | "pulse" (a string of bolts)


@dataclass
class Ring:
    x: float
    y: float
    radius: float
    color: theme.Color
    life: float = 0.9
    age: float = 0.0
    core: bool = True


@dataclass
class Spark:
    x: float
    y: float
    vx: float
    vy: float
    color: theme.Color
    life: float
    age: float = 0.0


@dataclass
class Pop:
    """A round shot down: a small grey star of debris, the same size on screen at any zoom."""
    x: float
    y: float
    life: float = 0.7
    age: float = 0.0
    spin: float = 0.0


@dataclass
class Debris:
    """A piece of a ship that broke up: a short bright shard, tumbling and dimming as it drifts."""
    x: float
    y: float
    vx: float
    vy: float
    angle: float
    spin: float
    length: float          # pixels
    color: theme.Color
    life: float
    age: float = 0.0


@dataclass
class Glow:
    """The soft light of a ship's reactor letting go, under the blast ring."""
    x: float
    y: float
    radius: float          # world units
    color: theme.Color
    life: float = 0.6
    age: float = 0.0


@dataclass
class Ripple:
    """A cloak engaging or failing: the space around the ship shivers in a wavering ring."""
    x: float
    y: float
    vanishing: bool
    life: float = 1.1
    age: float = 0.0
    phase: float = 0.0


@dataclass
class Effects:
    beams: list[Beam] = field(default_factory=list)
    rings: list[Ring] = field(default_factory=list)
    sparks: list[Spark] = field(default_factory=list)
    pops: list[Pop] = field(default_factory=list)
    debris: list[Debris] = field(default_factory=list)
    glows: list[Glow] = field(default_factory=list)
    embers: list[Spark] = field(default_factory=list)
    ripples: list[Ripple] = field(default_factory=list)
    rng: random.Random = field(default_factory=lambda: random.Random(7))

    def ingest(self, events: list[Event], player_side: int, visible: set[int], friendly: set[int],
               faction_of: Callable[[int | None], Faction | None] = lambda sid: None) -> None:
        for ev in events:
            if isinstance(ev, PhaserFired):
                if ev.ship_id not in visible:
                    continue
                f = faction_of(ev.ship_id)
                col = f.phaser_color if f is not None else UNKNOWN_WEAPON
                self.beams.append(Beam(ev.origin[0], ev.origin[1], ev.end[0], ev.end[1], ev.spread, col,
                                       width=1.5 if ev.defensive else 2.2, cone=(ev.facing, ev.spread, ev.range),
                                       style=f.phaser_style if f is not None else "beam"))
            elif isinstance(ev, Detonation) and ev.cause == "intercepted":
                # an armed round set off by a beam still blasts, but dully: a faint grey ring, no flash
                self.rings.append(Ring(ev.x, ev.y, ev.radius, theme.dim(FIZZLE, 0.6), life=0.5, core=False))
            elif isinstance(ev, Detonation):
                if ev.source in ("torpedo", "probe"):
                    f = faction_of(ev.owner)
                    col = theme.mix(f.torpedo_color if f is not None else UNKNOWN_WEAPON, (255, 255, 255), 0.25)
                else:
                    col = theme.BLAST if ev.source != "ship" else (255, 230, 190)
                big = ev.source in ("ship", "destruct")      # a ship's flash is its own soft glow, not a hard disc
                self.rings.append(Ring(ev.x, ev.y, max(ev.radius, 150.0), col, life=1.1 if big else 0.8, core=not big))
                if ev.source in ("ship", "destruct"):
                    self._breakup(ev.x, ev.y, max(ev.radius, 300.0))
                n = 26 if ev.source in ("ship", "destruct") else 12
                for _ in range(n):
                    a = self.rng.uniform(0, math.tau)
                    sp = self.rng.uniform(0.3, 1.0) * max(ev.radius, 200.0) * 1.2
                    self.sparks.append(Spark(ev.x, ev.y, math.sin(a) * sp, math.cos(a) * sp, col,
                                             self.rng.uniform(0.4, 1.2)))
            elif isinstance(ev, DeflectorPulsed):
                a = math.radians(ev.facing)
                self.beams.append(Beam(ev.x, ev.y, ev.x + math.sin(a) * ev.range, ev.y + math.cos(a) * ev.range,
                                       ev.arc, theme.CREW, life=1.4, width=1.0, cone=(ev.facing, ev.arc, ev.range)))
            elif isinstance(ev, OrdnanceDestroyed):
                self._fizzle(ev.x, ev.y, 90.0)
            elif isinstance(ev, ShipStatusChanged) and ev.status == "destroyed":
                pass  # the breakup Detonation carries the visuals

    def _breakup(self, x: float, y: float, radius: float) -> None:
        """A ship coming apart: a flash, a ring of shards flung outward, and embers that linger."""
        self.glows.append(Glow(x, y, radius * 0.6, (255, 236, 200), life=0.7))
        hull = (205, 208, 218)
        for _ in range(self.rng.randint(9, 14)):
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(0.25, 0.7) * radius
            self.debris.append(Debris(x, y, math.sin(a) * sp, math.cos(a) * sp, self.rng.uniform(0, math.tau),
                                      self.rng.uniform(-6, 6), self.rng.uniform(3, 8), hull, self.rng.uniform(2.2, 3.6)))
        for _ in range(18):
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(0.05, 0.4) * radius
            self.embers.append(Spark(x + math.sin(a) * radius * 0.1, y + math.cos(a) * radius * 0.1,
                                     math.sin(a) * sp, math.cos(a) * sp, EMBER, self.rng.uniform(1.4, 3.0)))

    def ripple(self, x: float, y: float, vanishing: bool) -> None:
        self.ripples.append(Ripple(x, y, vanishing, phase=self.rng.uniform(0, math.tau)))

    def smoulder(self, x: float, y: float, hull: float, dt: float, zoom: float) -> None:
        """A badly hurt ship sheds the odd spark: more of them the worse the damage."""
        rate = 1.0 + 7.0 * max(0.0, 0.5 - hull) / 0.5      # sparks per second
        if self.rng.random() >= rate * dt or len(self.sparks) > 400:
            return
        a = self.rng.uniform(0, math.tau)
        sp = self.rng.uniform(15.0, 45.0) / max(zoom, 1e-4)      # a few pixels a second at any zoom
        off = self.rng.uniform(2.0, 9.0) / max(zoom, 1e-4)
        self.sparks.append(Spark(x + math.sin(a) * off, y + math.cos(a) * off, math.sin(a) * sp, math.cos(a) * sp,
                                 self.rng.choice((EMBER, (255, 214, 140), (255, 240, 220))), self.rng.uniform(0.25, 0.6)))

    def _fizzle(self, x: float, y: float, radius: float) -> None:
        """A round shot down: a small dull flash and a puff of grey debris, no fireball."""
        self.rings.append(Ring(x, y, radius, FIZZLE, life=0.4, core=False))
        self.pops.append(Pop(x, y, spin=self.rng.uniform(0, math.pi / 4)))
        for _ in range(6):
            a = self.rng.uniform(0, math.tau)
            sp = self.rng.uniform(60.0, 220.0)
            self.sparks.append(Spark(x, y, math.sin(a) * sp, math.cos(a) * sp, FIZZLE, self.rng.uniform(0.3, 0.7)))

    def update(self, dt: float) -> None:
        for b in self.beams:
            b.age += dt
        for r in self.rings:
            r.age += dt
        for pp in self.pops:
            pp.age += dt
        self.pops = [pp for pp in self.pops if pp.age < pp.life]
        for s in self.sparks:
            s.age += dt
            s.x += s.vx * dt
            s.y += s.vy * dt
            s.vx *= 0.96
            s.vy *= 0.96
        for d in self.debris:
            d.age += dt
            d.x += d.vx * dt
            d.y += d.vy * dt
            d.angle += d.spin * dt
        for g in self.glows:
            g.age += dt
        for rp in self.ripples:
            rp.age += dt
        self.ripples = [rp for rp in self.ripples if rp.age < rp.life]
        for e in self.embers:
            e.age += dt
            e.x += e.vx * dt
            e.y += e.vy * dt
            drag = math.exp(-1.2 * dt)
            e.vx *= drag
            e.vy *= drag
        self.debris = [d for d in self.debris if d.age < d.life]
        self.glows = [g for g in self.glows if g.age < g.life]
        self.embers = [e for e in self.embers if e.age < e.life]
        self.beams = [b for b in self.beams if b.age < b.life]
        self.rings = [r for r in self.rings if r.age < r.life]
        self.sparks = [s for s in self.sparks if s.age < s.life]

    def draw(self, surf: pygame.Surface, cam: Camera, overlay: pygame.Surface) -> None:
        for g in self.glows:
            t = g.age / g.life
            sx, sy = cam.to_screen(g.x, g.y)
            rad = int(min(300.0, max(6.0, g.radius * cam.zoom * (0.7 + 0.5 * t))))
            light = pygame.Surface((rad * 2, rad * 2))
            fade = (1 - t) ** 2
            for step in range(GLOW_STEPS):   # nested discs, outermost first: a gaussian of light
                share = 1 - step / GLOW_STEPS
                k = fade * math.exp(-5.0 * share * share)
                pygame.draw.circle(light, tuple(min(255, int(c * k)) for c in g.color), (rad, rad), max(1, int(rad * share)))
            surf.blit(light, (int(sx) - rad, int(sy) - rad), special_flags=pygame.BLEND_RGB_ADD)
        for rp in self.ripples:
            t = rp.age / rp.life
            sx, sy = cam.to_screen(rp.x, rp.y)
            # vanishing: the ring closes in on the ship; appearing: it spreads out from her
            base = 14 + (34 * (1 - t) if rp.vanishing else 34 * t)
            for k in range(2):
                pts = []
                for j in range(40):
                    a = j / 40 * math.tau
                    wob = 1 + 0.08 * math.sin(a * 6 + rp.phase + rp.age * 9 + k) * (1 - t)
                    rr = (base + k * 6) * wob
                    pts.append((sx + math.cos(a) * rr, sy + math.sin(a) * rr))
                alpha = int(120 * math.sin(math.pi * t) / (1 + k))
                if alpha > 3:
                    pygame.draw.lines(overlay, (*CLOAK, alpha), True, pts, 1)
        for shard in self.debris:
            t = shard.age / shard.life
            sx, sy = cam.to_screen(shard.x, shard.y)
            hx, hy = math.cos(shard.angle) * shard.length / 2, math.sin(shard.angle) * shard.length / 2
            hot = theme.mix((255, 220, 170), shard.color, min(1.0, t * 3))
            pygame.draw.line(surf, theme.mix(hot, theme.BG, t ** 1.3), (sx - hx, sy - hy), (sx + hx, sy + hy), 2 if t < 0.4 else 1)
        for e in self.embers:
            t = e.age / e.life
            sx, sy = cam.to_screen(e.x, e.y)
            col = theme.mix(theme.mix((255, 210, 120), EMBER, min(1.0, t * 2)), theme.BG, t ** 1.5)
            pygame.draw.circle(surf, col, (int(sx), int(sy)), 1)
        for b in self.beams:
            t = 1.0 - b.age / b.life
            p0 = cam.to_screen(b.x0, b.y0)
            p1 = cam.to_screen(b.x1, b.y1)
            if b.cone is not None and b.spread > 12:
                facing, spread, rng_ = b.cone
                d = math.hypot(b.x1 - b.x0, b.y1 - b.y0)
                pts = [p0]
                for k in range(7):
                    a = math.radians(facing - spread / 2 + spread * k / 6)
                    pts.append(cam.to_screen(b.x0 + math.sin(a) * d, b.y0 + math.cos(a) * d))
                pygame.draw.polygon(overlay, (*b.color, int(38 * t)), pts)
            col = theme.mix(theme.BG, b.color, 0.35 + 0.65 * t)
            for w, a in BEAM_GLOW:                     # the soft light around the shot
                pygame.draw.line(overlay, (*b.color, int(a * t)), p0, p1, w)
            pygame.draw.circle(overlay, (*theme.mix(b.color, (255, 255, 255), 0.4), int(90 * t)),
                               (int(p1[0]), int(p1[1])), int(3 + 4 * t))      # where it strikes
            if b.style == "pulse":
                _bolts(surf, col, p0, p1, max(1, int(b.width * (0.8 + t))), b.age)
                continue
            pygame.draw.line(surf, col, p0, p1, max(1, int(b.width * (0.6 + t))))
            pygame.draw.line(surf, theme.mix(col, (255, 255, 255), 0.5 * t), p0, p1, 1)
        for r in self.rings:
            t = r.age / r.life
            sx, sy = cam.to_screen(r.x, r.y)
            rad = max(3, int(r.radius * cam.zoom * (0.35 + 0.65 * math.sqrt(t))))
            col = theme.mix(r.color, theme.BG, t)
            pygame.draw.circle(surf, col, (int(sx), int(sy)), rad, max(1, int(3 * (1 - t))))
            if r.core and t < 0.35:
                pygame.draw.circle(surf, theme.mix((255, 255, 240), r.color, t / 0.35), (int(sx), int(sy)),
                                   max(2, int(rad * 0.45 * (1 - t / 0.35))))
        for pp in self.pops:
            t = pp.age / pp.life
            sx, sy = cam.to_screen(pp.x, pp.y)
            col = theme.mix(FIZZLE, theme.BG, t)
            r0, r1 = 3 + 4 * t, 7 + 5 * t
            for k in range(4):
                a = pp.spin + k * math.pi / 2
                pygame.draw.line(surf, col, (sx + math.cos(a) * r0, sy + math.sin(a) * r0),
                                 (sx + math.cos(a) * r1, sy + math.sin(a) * r1), 2)
        for s in self.sparks:
            t = s.age / s.life
            sx, sy = cam.to_screen(s.x, s.y)
            pygame.draw.circle(surf, theme.mix(s.color, theme.BG, t), (int(sx), int(sy)), 1 if t > 0.5 else 2)


UNKNOWN_WEAPON = (215, 215, 215)   # a ship we can't identify
FIZZLE = (150, 150, 150)           # a round shot down before it could go off properly
EMBER = (255, 132, 60)
CLOAK = (170, 225, 215)            # the shimmer of a cloak engaging or dropping
GLOW_STEPS = 28             # burning fragments of a ship
BEAM_GLOW = ((13, 30), (7, 60))   # (pixels wide, alpha at full strength): the halo around a beam


def _bolts(surf: pygame.Surface, col: theme.Color, a: tuple[float, float], b: tuple[float, float], width: int,
           age: float) -> None:
    """A disruptor: short bright bolts racing from the firing ship to the end of the shot."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    on, gap = 12.0, 9.0
    t = (age * 400.0) % (on + gap)
    hot = theme.mix(col, (255, 255, 255), 0.4)
    while t < length:
        e = min(length, t + on)
        pygame.draw.line(surf, col, (a[0] + ux * t, a[1] + uy * t), (a[0] + ux * e, a[1] + uy * e), width + 1)
        pygame.draw.line(surf, hot, (a[0] + ux * t, a[1] + uy * t), (a[0] + ux * e, a[1] + uy * e), 1)
        t += on + gap


__all__ = ["FIZZLE", "UNKNOWN_WEAPON", "Effects"]
