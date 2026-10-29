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
class Effects:
    beams: list[Beam] = field(default_factory=list)
    rings: list[Ring] = field(default_factory=list)
    sparks: list[Spark] = field(default_factory=list)
    pops: list[Pop] = field(default_factory=list)
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
                self.rings.append(Ring(ev.x, ev.y, max(ev.radius, 150.0), col, life=1.1 if ev.source == "ship" else 0.8))
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
        self.beams = [b for b in self.beams if b.age < b.life]
        self.rings = [r for r in self.rings if r.age < r.life]
        self.sparks = [s for s in self.sparks if s.age < s.life]

    def draw(self, surf: pygame.Surface, cam: Camera, overlay: pygame.Surface) -> None:
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
