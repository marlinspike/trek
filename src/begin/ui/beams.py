"""Phaser and disruptor fire on the battle map [E].

A shot is a short event in four parts, each telling the captain something:

1. **Charge.** The bank's emitter strip lights up and the light runs in to the point the beam leaves
   from, so you see which bank fired and which way it bears before the beam is out.
2. **Discharge.** The beam's tip races from the bank to the target, then holds: a wide soft glow, a
   coloured body and a white-hot core that shimmers along its length.
3. **Strike.** A beam stopped by a shield ends on the shield bubble; one that got through reaches the
   hull. The splash where it lands is sized by the shot.
4. **Fade.** The tail pulls in toward the target and the core goes out last.

How heavy a shot looks comes from the shot itself: the bank's charge (`PhaserFired.power`) and how
tightly the beam was focused. Point-defence shots skip the charge and stay thin and quick, so they never
read as attacks.

Races that fire "pulse" weapons (Klingon and Orion disruptors) send bolts instead: bright heads with
short streaks that fly to the target one after another.

Everything is in world coordinates and wall-clock seconds, so it reads the same at any time scale.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass

import pygame

from . import theme
from .blast import add_light
from .camera import Camera
from .hulls import MIN_HULL_PX
from . import gfx

CHARGE = 0.12          # seconds the bank's strip glows before the beam leaves
REACH = 0.07           # seconds the beam's tip takes to reach the end of the shot
HOLD = 0.30            # seconds a full-power beam stays on (less for a weaker shot)
FADE = 0.13            # seconds the tail takes to pull in
PD_HOLD = 0.12         # a point-defence shot: no charge, a short flick
CUTTER_HOLD = 3.2      # a Borg cutting beam stays on this many times longer, dragging across the hull
CUTTER_SWEEP_PX = 14.0 # how far, on screen, its end drags to either side
CUTTER_HZ = 0.45       # how fast it drags back and forth

BOLT_LEAD = 0.05       # seconds of charge before a disruptor's first bolt
BOLT_GAP = 0.06        # seconds between bolts
BOLT_FLIGHT = 0.16     # seconds a bolt takes to reach the end of the shot
BOLT_GLOW = 0.10       # seconds a bolt's splash lasts where it lands

WHITE = (255, 255, 255)


@dataclass
class Stop:
    """Where a beam is cut short on the ship it hit: on her shield bubble, or on her hull."""
    x: float
    y: float
    length: float          # her hull, world units (the bubble is drawn from it)
    on_shield: bool


@dataclass
class Beam:
    x0: float
    y0: float
    x1: float
    y1: float
    spread: float
    color: theme.Color
    life: float = 0.0          # filled in from the timings when left at 0
    age: float = 0.0
    width: float = 2.0
    cone: tuple[float, float, float] | None = None  # (facing, spread, range) for the faint cone
    style: str = "beam"        # "beam" | "pulse" (bolts) | "sweep" (a deflector pulse) | "cutter" (a Borg cutting beam)
    power: float = 1.0         # 0..1: the bank's charge
    defensive: bool = False
    strip: float = 0.0         # world length of the bank's emitter strip (0: none drawn)
    stop: Stop | None = None
    bolts: int = 0             # disruptor bolts in the shot
    landed: bool = False       # the impact splash has been thrown (sparks are spawned once)
    seed: int = 0

    def __post_init__(self) -> None:
        if self.style == "pulse" and self.bolts <= 0:
            self.bolts = 1 if self.defensive else 2 + int(self.power > 0.66)
        if self.life <= 0:
            self.life = self.timeline()[-1]

    # ------------------------------------------------------------ timings

    def timeline(self) -> tuple[float, float, float, float]:
        """(charge ends, tip arrives, tail starts in, gone), seconds from the shot."""
        if self.style == "pulse":
            lead = 0.0 if self.defensive else BOLT_LEAD
            last = lead + BOLT_GAP * (self.bolts - 1) + BOLT_FLIGHT
            return lead, lead + BOLT_FLIGHT, last, last + BOLT_GLOW
        if self.style == "sweep":
            return 0.0, 0.0, self.life * 0.6 if self.life else 0.8, self.life or 1.4
        charge = 0.0 if self.defensive else CHARGE
        hold = PD_HOLD if self.defensive else HOLD * (0.55 + 0.45 * self.power)
        if self.style == "cutter" and not self.defensive:
            hold *= CUTTER_HOLD              # a cutting beam lingers, dragging across her hull
        return charge, charge + REACH, charge + REACH + hold, charge + REACH + hold + FADE

    @property
    def arrives(self) -> float:
        """Seconds from the shot until it lands: when the target's shield or hull should light up."""
        return self.timeline()[1]

    @property
    def weight(self) -> float:
        """How heavy the shot is, 0..1.5: its charge, and how tightly it was focused."""
        if self.defensive:
            return 0.25
        focus = max(0.7, min(1.5, (45.0 / max(self.spread, 1.0)) ** 0.35))
        return max(0.15, self.power) * focus

    # ------------------------------------------------------------ drawing

    def endpoints(self, cam: Camera) -> tuple[tuple[float, float], tuple[float, float]]:
        """The shot on screen: from the bank to where it really stops (shield bubble or hull)."""
        p0 = cam.to_screen(self.x0, self.y0)
        p1 = cam.to_screen(self.x1, self.y1)
        st = self.stop
        if st is None:
            return p0, p1
        c = cam.to_screen(st.x, st.y)
        rad = 62.0 * max(st.length * cam.zoom, MIN_HULL_PX) / 100.0
        if not st.on_shield:
            rad *= 0.3                       # through the shield: it reaches her hull
        cut = _circle_entry(p0, p1, c, rad)
        return p0, cut if cut is not None else p1

    def draw(self, surf: pygame.Surface, glow: pygame.Surface, cam: Camera, clock: float) -> None:
        """Solid strokes go onto `surf`; soft light goes onto `glow`, a black layer added onto the map after."""
        if self.style == "sweep":
            self._draw_sweep(surf, glow, cam)
        elif self.style == "pulse":
            self._draw_bolts(surf, glow, cam)
        else:
            self._draw_beam(surf, glow, cam, clock)

    def _draw_beam(self, surf: pygame.Surface, overlay: pygame.Surface, cam: Camera, clock: float) -> None:
        charge, arrive, tail, gone = self.timeline()
        t = self.age
        p0, p1 = self.endpoints(cam)
        if t < charge:
            self._charge(surf, overlay, cam, p0, t / charge)
            return
        head = _ease_out(min(1.0, (t - charge) / max(arrive - charge, 1e-6)))
        back = _ease_in(max(0.0, (t - tail) / max(gone - tail, 1e-6)))
        if self.style == "cutter":
            p1 = self._cut(p0, p1, cam, t - arrive)
        a = _lerp(p0, p1, back)
        b = _lerp(p0, p1, head)
        k = 1.0 - back ** 2                   # how bright the shot still is
        w = self.weight
        body = max(1, round(1.2 + 2.4 * w))
        flicker = 0.85 + 0.15 * math.sin(clock * 61.0 + self.seed)
        if self.cone is not None and self.spread > 12 and not self.defensive:
            self._cone(overlay, cam, k)
        for width, alpha in ((body * 9, 0.05), (body * 6, 0.07), (body * 4, 0.12), (body * 2 + 1, 0.22)):   # soft light round it
            gfx.draw.aaline(overlay, _dim(self.color, alpha * k * flicker), a, b, width)
        gfx.draw.aaline(surf, theme.mix(theme.BG, self.color, 0.4 + 0.6 * k), a, b, body)
        core = theme.mix(self.color, WHITE, 0.55 + 0.25 * flicker)
        gfx.draw.aaline(surf, theme.mix(theme.BG, core, k), a, b, max(1, body // 2))
        self._shimmer(overlay, a, b, k, clock)
        if head < 1.0:
            add_light(surf, b[0], b[1], 4 + 4 * w, theme.mix(self.color, WHITE, 0.6), 0.9)   # the tip racing out
        else:                                                                                # the splash where it lands
            add_light(surf, p1[0], p1[1], (6 + 9 * w) * (0.8 + 0.2 * flicker), theme.mix(self.color, WHITE, 0.45), 0.85 * k)
        add_light(surf, a[0], a[1], 3 + 3 * w, theme.mix(self.color, WHITE, 0.5), 0.6 * k)   # the bank still lit

    def _cut(self, p0: tuple[float, float], p1: tuple[float, float], cam: Camera,
             since: float) -> tuple[float, float]:
        """Where a cutting beam bites now: once it lands, its end drags slowly across the target, side to side."""
        if since <= 0:
            return p1
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy) or 1.0
        reach = CUTTER_SWEEP_PX * max(0.6, min(1.6, cam.zoom / 0.12))
        off = reach * math.sin(since * CUTTER_HZ * math.tau + self.seed)
        return p1[0] - dy / L * off, p1[1] + dx / L * off

    def _charge(self, surf: pygame.Surface, overlay: pygame.Surface, cam: Camera, p0: tuple[float, float],
                u: float) -> None:
        """The emitter strip lights up and its light runs in to the firing point."""
        half = max(5.0, min(28.0, self.strip * cam.zoom * 0.5)) if self.strip > 0 else 6.0
        dx, dy = self.x1 - self.x0, self.y1 - self.y0
        L = math.hypot(dx, dy) or 1.0
        # across the line of fire, on screen (y flips)
        nx, ny = dy / L, dx / L
        e1 = (p0[0] - nx * half, p0[1] - ny * half)
        e2 = (p0[0] + nx * half, p0[1] + ny * half)
        gfx.draw.aaline(overlay, _dim(self.color, 0.25 + 0.5 * u), e1, e2, 2)
        run = 1.0 - _ease_in(u)
        for e in (e1, e2):
            q = _lerp(p0, e, run)
            add_light(surf, q[0], q[1], 3 + 2 * u, theme.mix(self.color, WHITE, 0.4), 0.8)
        add_light(surf, p0[0], p0[1], 2 + 5 * u * self.weight, theme.mix(self.color, WHITE, 0.6), u)

    def _shimmer(self, overlay: pygame.Surface, a: tuple[float, float], b: tuple[float, float], k: float,
                 clock: float) -> None:
        """A few bright motes running along the beam, so it reads as energy rather than a drawn line."""
        L = math.hypot(b[0] - a[0], b[1] - a[1])
        if L < 12 or k < 0.1:
            return
        rng = random.Random(self.seed * 7919 + int(clock * 30))
        for _ in range(min(10, int(L / 40) + 2)):
            q = _lerp(a, b, rng.random())
            gfx.draw.aacircle(overlay, _dim(WHITE, 0.6 * k * rng.uniform(0.3, 1.0)), q, 1)

    def _cone(self, overlay: pygame.Surface, cam: Camera, k: float) -> None:
        """A wide shot also catches anything else in its cone: a faint fan shows how wide it went."""
        assert self.cone is not None
        facing, spread, _ = self.cone
        d = math.hypot(self.x1 - self.x0, self.y1 - self.y0)
        pts = [cam.to_screen(self.x0, self.y0)]
        for j in range(7):
            ang = math.radians(facing - spread / 2 + spread * j / 6)
            pts.append(cam.to_screen(self.x0 + math.sin(ang) * d, self.y0 + math.cos(ang) * d))
        gfx.draw.polygon(overlay, _dim(self.color, 0.035 * k), pts)

    def _draw_bolts(self, surf: pygame.Surface, overlay: pygame.Surface, cam: Camera) -> None:
        lead = self.timeline()[0]
        p0, p1 = self.endpoints(cam)
        dx, dy = p1[0] - p0[0], p1[1] - p0[1]
        L = math.hypot(dx, dy)
        if L < 1:
            return
        ux, uy = dx / L, dy / L
        w = self.weight
        hot = theme.mix(self.color, WHITE, 0.55)
        if self.age < lead:                                      # the emitter gathering itself
            add_light(surf, p0[0], p0[1], 3 + 4 * w * self.age / lead, hot, self.age / lead)
        streak = min(L, 10 + 12 * w)
        for i in range(self.bolts):
            t = (self.age - lead - BOLT_GAP * i) / BOLT_FLIGHT
            if t < 0:
                continue
            if t <= 1.0:
                d = L * t
                h = (p0[0] + ux * d, p0[1] + uy * d)
                tl = (h[0] - ux * min(streak, d), h[1] - uy * min(streak, d))
                gfx.draw.aaline(overlay, _dim(self.color, 0.35), tl, h, max(3, round(3 + 3 * w)))
                gfx.draw.aaline(surf, self.color, tl, h, max(2, round(1 + 2 * w)))
                gfx.draw.aaline(surf, hot, tl, h, 1)
                add_light(surf, h[0], h[1], 4 + 4 * w, hot, 0.9)
            else:
                u = (t - 1.0) * BOLT_FLIGHT / BOLT_GLOW
                if u < 1.0:
                    add_light(surf, p1[0], p1[1], (6 + 8 * w) * (1 + 0.5 * u), hot, 0.9 * (1 - u))

    def _draw_sweep(self, surf: pygame.Surface, overlay: pygame.Surface, cam: Camera) -> None:
        """A deflector pulse: a broad, flat sweep through its arc."""
        t = 1.0 - self.age / self.life
        p0 = cam.to_screen(self.x0, self.y0)
        p1 = cam.to_screen(self.x1, self.y1)
        if self.cone is not None and self.spread > 12:
            self._cone(overlay, cam, t * 1.3)
        col = theme.mix(theme.BG, self.color, 0.35 + 0.65 * t)
        for width, alpha in ((13, 0.12), (7, 0.24)):
            gfx.draw.aaline(overlay, _dim(self.color, alpha * t), p0, p1, width)
        gfx.draw.aaline(surf, col, p0, p1, max(1, int(self.width * (0.6 + t))))

    def landing(self) -> bool:
        """True once, the moment the shot lands: time to throw sparks off whatever it hit."""
        if self.landed or self.style == "sweep" or self.age < self.arrives:
            return False
        self.landed = True
        return True


# ------------------------------------------------------------------ helpers

def _dim(col: theme.Color, k: float) -> theme.Color:
    """A colour at brightness k, for light added onto the map."""
    k = max(0.0, min(1.0, k))
    return int(col[0] * k), int(col[1] * k), int(col[2] * k)


def _lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def _ease_out(t: float) -> float:
    return 1.0 - (1.0 - t) ** 3


def _ease_in(t: float) -> float:
    return t * t


def _circle_entry(a: tuple[float, float], b: tuple[float, float], c: tuple[float, float],
                  r: float) -> tuple[float, float] | None:
    """Where the line from a to b first enters the circle at c, or None if it doesn't (or starts inside)."""
    dx, dy = b[0] - a[0], b[1] - a[1]
    fx, fy = a[0] - c[0], a[1] - c[1]
    qa = dx * dx + dy * dy
    if qa < 1e-9:
        return None
    qb = 2 * (fx * dx + fy * dy)
    qc = fx * fx + fy * fy - r * r
    if qc <= 0:
        return None
    disc = qb * qb - 4 * qa * qc
    if disc < 0:
        return None
    t = (-qb - math.sqrt(disc)) / (2 * qa)
    if not 0.0 <= t <= 1.0:
        return None
    return a[0] + dx * t, a[1] + dy * t


__all__ = ["Beam", "Stop"]
