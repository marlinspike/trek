"""Screen-space light and fire for the showpiece scenes: soft halos, shield flares, hull hits and the
destruction of a ship, all drawn additively onto a black "glow" surface that is then added onto the
scene, plus the burning pieces of the ship drawn straight onto the scene.

Everything here works in pixels and wall-clock seconds. Each effect keeps its moving parts as offsets
from its own centre, so the battle map can pin one to a point in space by moving its centre to wherever
that point is on screen this frame, and pass a scale `s` when the view has zoomed since it began.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from functools import lru_cache

import pygame

CLOAK = (170, 225, 215)           # the shimmer of a cloak dropping
SHIELD = (120, 200, 255)          # a deflector taking a hit
FIRE_HOT = (255, 246, 220)
FIRE_MID = (255, 170, 70)
FIRE_DEEP = (200, 60, 24)
SHOCK = (190, 225, 255)


def mix(a: tuple[int, int, int], b: tuple[int, int, int], t: float) -> tuple[int, int, int]:
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def level(col: tuple[int, int, int], k: float) -> tuple[int, int, int]:
    """col scaled by k, in steps of 1/16 so the halo cache stays small."""
    q = round(max(0.0, min(1.0, k)) * 16) / 16
    return (int(col[0] * q) // 8 * 8, int(col[1] * q) // 8 * 8, int(col[2] * q) // 8 * 8)


@lru_cache(maxsize=512)
def halo(radius: int, col: tuple[int, int, int]) -> pygame.Surface:
    """A soft round light (black outside), for adding onto the scene: brightest at the centre."""
    d = radius * 2 + 1
    g = pygame.Surface((d, d))
    g.fill((0, 0, 0))
    steps = min(radius, 40)                   # nested discs, outermost first
    for i in range(steps, 0, -1):
        r = max(1, round(radius * i / steps))
        k = (1.0 - r / radius) ** 2.2
        pygame.draw.circle(g, (int(col[0] * k), int(col[1] * k), int(col[2] * k)), (radius, radius), r)
    return g


def add_light(glow: pygame.Surface, x: float, y: float, radius: float, col: tuple[int, int, int], k: float) -> None:
    """A halo of `radius` pixels at (x, y), at brightness k (0..1)."""
    c = level(col, k)
    if c == (0, 0, 0) or radius < 1:
        return
    r = round(radius)
    if r < 40:
        img = halo(max(2, r), c)
    else:
        # big lights: one full-strength halo per size and colour, dimmed on a copy, so a growing,
        # fading fireball doesn't build a new halo every frame
        r = min(400, r // 8 * 8 if r < 120 else r // 24 * 24)
        img = halo(r, (col[0] // 16 * 16, col[1] // 16 * 16, col[2] // 16 * 16)).copy()
        q = round(max(0.0, min(1.0, k)) * 16) * 16 - 1
        if q < 254:
            img.fill((q, q, q), special_flags=pygame.BLEND_RGB_MULT)
    glow.blit(img, img.get_rect(center=(round(x), round(y))), special_flags=pygame.BLEND_RGB_ADD)


def ring(glow: pygame.Surface, x: float, y: float, rx: float, ry: float, col: tuple[int, int, int], k: float,
         width: int = 2, tilt: float = 0.0) -> None:
    """A glowing ellipse (a shockwave seen a little edge-on): a soft band with a bright core."""
    if k <= 0.01 or rx < 2:
        return
    ct, st = math.cos(tilt), math.sin(tilt)
    pad = width * 6 + 2
    reach = max(rx, ry) + pad
    box = pygame.Rect(0, 0, int(reach * 2) + 1, int(reach * 2) + 1)
    box.center = (round(x), round(y))
    box = box.clip(glow.get_rect())
    if box.width <= 0 or box.height <= 0:
        return
    pts = []
    for j in range(72):
        a = j / 72 * math.tau
        ex, ey = math.cos(a) * rx, math.sin(a) * ry
        pts.append((x + ex * ct - ey * st - box.x, y + ex * st + ey * ct - box.y))
    band = pygame.Surface(box.size)                 # drawn apart and added, so it never darkens what is lit
    band.fill((0, 0, 0))
    for w, share in ((width * 6, 0.18), (width * 3, 0.35), (width, 1.0)):
        pygame.draw.lines(band, level(col, k * share), True, pts, max(1, w))
    glow.blit(band, box.topleft, special_flags=pygame.BLEND_RGB_ADD)


# ---------------------------------------------------------------- shields and hits

@dataclass
class ShieldFlare:
    """A shot stopped by a deflector: the bubble lights up around the blow and ripples out from it."""
    x: float                  # centre of the ship
    y: float
    rx: float                 # the bubble's radii, pixels
    ry: float
    angle: float              # where on the bubble it landed, radians (screen, 0 = right, clockwise)
    strength: float = 1.0     # 1 a torpedo, less for a phaser
    t: float = 0.0
    life: float = 0.9
    color: tuple[int, int, int] = SHIELD

    def draw(self, glow: pygame.Surface) -> None:
        u = self.t / self.life
        fade = (1 - u) ** 1.6 * self.strength
        spread = 0.6 + 2.4 * u                          # the lit arc widens as it fades
        steps = 64 if self.rx + self.ry > 80 else 32    # a small bubble needs fewer lights round its rim
        for j in range(steps):
            a = j / steps * math.tau
            d = abs((a - self.angle + math.pi) % math.tau - math.pi)
            k = math.exp(-(d / spread) ** 2) * fade
            if k < 0.03:
                continue
            px = self.x + math.cos(a) * self.rx
            py = self.y + math.sin(a) * self.ry
            add_light(glow, px, py, 6 + 0.16 * (self.rx + self.ry) * k, self.color, 0.9 * k)
        hx = self.x + math.cos(self.angle) * self.rx
        hy = self.y + math.sin(self.angle) * self.ry
        add_light(glow, hx, hy, 0.5 * (self.rx + self.ry) * (0.4 + 0.6 * u), self.color, 0.5 * fade)
        add_light(glow, hx, hy, 10 + 18 * self.strength, (235, 250, 255), fade * (1 - u))
        ring(glow, self.x, self.y, self.rx, self.ry, self.color, 0.45 * fade, 1)
        add_light(glow, self.x, self.y, max(self.rx, self.ry) * 1.1, self.color, 0.12 * fade)     # the whole bubble glimmers


@dataclass
class HullHit:
    """A blow that reaches the hull: a white-hot flash, a burst of fire and a spray of sparks."""
    x: float
    y: float
    size: float                                     # pixels across the burst
    t: float = 0.0
    life: float = 0.8
    sparks: list[list[float]] = field(default_factory=list)

    def start(self, rng: random.Random) -> None:
        for _ in range(16):
            a = rng.uniform(0, math.tau)
            sp = rng.uniform(0.6, 2.2) * self.size
            self.sparks.append([0.0, 0.0, math.cos(a) * sp, math.sin(a) * sp, rng.uniform(0.3, 0.7)])

    def update(self, dt: float) -> None:
        self.t += dt
        for s in self.sparks:
            s[0] += s[2] * dt
            s[1] += s[3] * dt
            s[2] *= 0.92
            s[3] *= 0.92

    @property
    def done(self) -> bool:
        return self.t >= self.life

    def draw(self, glow: pygame.Surface, s: float = 1.0) -> None:
        u = self.t / self.life
        size = self.size * s
        add_light(glow, self.x, self.y, size * (0.6 + 1.4 * u), mix(FIRE_MID, FIRE_DEEP, u), (1 - u) ** 1.5)
        if u < 0.3:
            add_light(glow, self.x, self.y, size * 0.7, FIRE_HOT, 1 - u / 0.3)
        for x, y, _, _, life in self.sparks:
            k = 1 - self.t / life
            if k > 0:
                add_light(glow, self.x + x * s, self.y + y * s, 3, mix(FIRE_HOT, FIRE_MID, 1 - k), k)


# ---------------------------------------------------------------- a ship destroyed

@dataclass
class _Chunk:
    img: pygame.Surface
    x: float                  # from the centre of the blast, pixels at scale 1
    y: float
    vx: float
    vy: float
    angle: float
    spin: float


@dataclass
class Blast:
    """A ship destroyed, in stages: a blinding flash, a fireball that swells and reddens, a flattened
    shockwave racing outward, the hull torn into burning pieces that tumble away, secondary bursts,
    a long spray of embers, and a dull red cloud that lingers."""
    x: float
    y: float
    radius: float                                   # the ship's size, pixels
    seed: int = 1
    t: float = 0.0
    life: float = 4.0
    tilt: float = 0.0
    chunks: list[_Chunk] = field(default_factory=list)
    embers: list[list[float]] = field(default_factory=list)
    puffs: list[tuple[float, float, float, float]] = field(default_factory=list)    # (dx, dy, at, size)
    secondaries: list[tuple[float, float, float]] = field(default_factory=list)    # (dx, dy, at)

    def start(self, image: pygame.Surface | None) -> None:
        rng = random.Random(self.seed)
        R = self.radius
        self.tilt = rng.uniform(-0.5, 0.5)
        if image is not None:                       # the hull itself, torn into pieces
            w, h = image.get_size()
            n = 4
            for i in range(n):
                for j in range(n):
                    r = pygame.Rect(i * w // n, j * h // n, w // n + 1, h // n + 1).clip(image.get_rect())
                    piece = image.subsurface(r).copy()
                    if piece.get_bounding_rect().width < 3:
                        continue
                    # torn, not cut: a jagged outline instead of the square it was taken from
                    pw, ph = piece.get_size()
                    jag = [(pw / 2 + math.cos(a) * pw * rng.uniform(0.35, 0.75), ph / 2 + math.sin(a) * ph * rng.uniform(0.35, 0.75))
                           for a in (q / 7 * math.tau + rng.uniform(-0.3, 0.3) for q in range(7))]
                    mask = pygame.Surface((pw, ph), pygame.SRCALPHA)
                    mask.fill((255, 255, 255, 0))
                    pygame.draw.polygon(mask, (255, 255, 255, 255), jag)
                    piece.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
                    ox = r.centerx - w / 2
                    oy = r.centery - h / 2
                    d = math.hypot(ox, oy) or 1.0
                    sp = rng.uniform(0.35, 1.1) * R
                    self.chunks.append(_Chunk(piece, ox, oy,
                                              ox / d * sp + rng.uniform(-0.2, 0.2) * R,
                                              oy / d * sp + rng.uniform(-0.2, 0.2) * R,
                                              0.0, rng.uniform(-200, 200)))
        for _ in range(90):
            a = rng.uniform(0, math.tau)
            sp = rng.uniform(0.3, 3.2) * R
            self.embers.append([0.0, 0.0, math.cos(a) * sp, math.sin(a) * sp, rng.uniform(1.2, 3.4),
                                rng.random()])
        for _ in range(7):
            a = rng.uniform(0, math.tau)
            d = rng.uniform(0.0, 0.55) * R
            self.puffs.append((math.cos(a) * d, math.sin(a) * d, rng.uniform(0.0, 0.25), rng.uniform(0.7, 1.3)))
        for _ in range(5):
            a = rng.uniform(0, math.tau)
            d = rng.uniform(0.4, 1.4) * R
            self.secondaries.append((math.cos(a) * d, math.sin(a) * d, rng.uniform(0.25, 1.1)))

    @property
    def done(self) -> bool:
        return self.t >= self.life

    def update(self, dt: float) -> None:
        self.t += dt
        drag = math.exp(-0.9 * dt)
        for c in self.chunks:
            c.x += c.vx * dt
            c.y += c.vy * dt
            c.vx *= drag
            c.vy *= drag
            c.angle += c.spin * dt
        edrag = math.exp(-1.4 * dt)
        for e in self.embers:
            e[0] += e[2] * dt
            e[1] += e[3] * dt
            e[2] *= edrag
            e[3] *= edrag

    def draw_pieces(self, surf: pygame.Surface, s: float = 1.0) -> None:
        """The tumbling pieces of hull, onto the scene (before the light is added)."""
        u = self.t / 2.6
        if u >= 1:
            return
        alpha = int(255 * (1 - u) ** 1.2)
        for c in self.chunks:
            img = pygame.transform.rotate(c.img, c.angle) if abs(s - 1) < 0.02 else pygame.transform.rotozoom(c.img, c.angle, s)
            img.set_alpha(alpha)
            surf.blit(img, img.get_rect(center=(round(self.x + c.x * s), round(self.y + c.y * s))))

    def draw(self, glow: pygame.Surface, s: float = 1.0) -> None:
        t, R = self.t, self.radius * s
        # 1. the flash: a blinding white core and a wide bloom that washes the screen
        if t < 0.35:
            k = 1 - t / 0.35
            add_light(glow, self.x, self.y, R * 4.5, (255, 240, 225), 0.55 * k)
            add_light(glow, self.x, self.y, R * 1.4, (255, 255, 255), k)
        # 2. the fireball: overlapping billows that swell, cool from white to orange to deep red
        for dx, dy, at, size in self.puffs:
            u = (t - at) / 1.6
            if 0 <= u < 1:
                col = mix(mix(FIRE_HOT, FIRE_MID, u * 2.2), FIRE_DEEP, max(0.0, u * 1.6 - 0.4))
                rad = R * size * (0.7 + 1.7 * math.sqrt(u))
                add_light(glow, self.x + dx * s * (1 + u), self.y + dy * s * (1 + u), rad, col, (1 - u) ** 1.3)
        # 3. the shockwave: a flattened ring racing outward, and a fainter one behind it
        for lag, share in ((0.0, 1.0), (0.18, 0.45)):
            u = (t - 0.05 - lag) / 1.5
            if 0 <= u < 1:
                rr = R * (0.6 + 7.5 * u ** 0.7)
                ring(glow, self.x, self.y, rr, rr * 0.32, SHOCK, share * (1 - u) ** 1.4, 2, self.tilt)
        # 4. secondary bursts as the pieces go up
        for dx, dy, at in self.secondaries:
            u = (t - at) / 0.5
            if 0 <= u < 1:
                add_light(glow, self.x + dx * s, self.y + dy * s, R * 0.55 * (0.5 + u), mix(FIRE_HOT, FIRE_MID, u), (1 - u) ** 1.5)
        # 5. the burning pieces glow hot
        u = t / 2.6
        if u < 1:
            for c in self.chunks:
                add_light(glow, self.x + c.x * s, self.y + c.y * s, max(4.0, c.img.get_width() * 0.6 * s), mix(FIRE_MID, FIRE_DEEP, u), 0.6 * (1 - u))
        # 6. embers flung far and fading, and the dull red cloud left behind
        for x, y, _, _, life, flick in self.embers:
            k = 1 - t / life
            if k > 0:
                add_light(glow, self.x + x * s, self.y + y * s, 2 + 3 * k, mix(FIRE_HOT, FIRE_DEEP, 1 - k), k * (0.7 + 0.3 * math.sin(t * 25 + flick * 9)))
        if t > 0.3:
            u = (t - 0.3) / (self.life - 0.3)
            add_light(glow, self.x, self.y, R * (1.6 + 1.2 * u), (120, 40, 30), 0.45 * (1 - u))


__all__ = ["Blast", "CLOAK", "HullHit", "SHIELD", "ShieldFlare", "add_light", "halo", "level", "mix", "ring"]
