"""Bake the showpiece sprite of the player's heavy cruiser: `python tools/render_ship.py`.

An original design drawn from the federation.hc hull layout (saucer, neck, secondary
hull, pylons, two nacelles). Every part is a height field; normals from the combined
field are lit by a key light, a soft fill and a cool rim light, with specular highlights,
ambient occlusion, plating, panel lines, lit windows and glowing nacelles, grilles and a
deflector halo, then supersampled down.

The light stays fixed on screen while the ship turns, so one sprite is baked per heading
(HEADINGS of them, the ship pointing up and the light rotated against it). The game loads
the PNGs (`ui/showpiece.py`) and only rotates by the few degrees between baked headings.
Needs numpy, which the game itself does not.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import numpy as np
import pygame

OUT = Path(__file__).resolve().parent.parent / "src" / "begin" / "assets" / "ships"
HEADINGS = 12            # one sprite every 30°
PX = 7.0                 # final pixels per hull unit
SS = 2                   # supersampling
X0, X1, Y0, Y1 = -30.0, 30.0, -54.0, 52.0     # hull-unit bounds of the canvas
LIGHT = (-0.6, 0.62, 0.42)                   # screen-space key light: from upper left, above
RIM = (0.6, -0.7, 0.25)                       # cool rim light from lower right


def _norm(v: np.ndarray) -> np.ndarray:
    return v / np.maximum(1e-6, np.linalg.norm(v, axis=-1, keepdims=True))


def _blur(a: np.ndarray, r: int) -> np.ndarray:
    """Box blur (twice, so it is soft) by cumulative sums, radius r pixels."""
    for _ in range(2):
        for ax in (0, 1):
            pad = [(0, 0), (0, 0)]
            pad[ax] = (r + 1, r)
            c = np.cumsum(np.pad(a, pad, mode="edge"), axis=ax)
            hi = np.take(c, range(2 * r + 1, c.shape[ax]), axis=ax)
            lo = np.take(c, range(0, c.shape[ax] - 2 * r - 1), axis=ax)
            a = (hi - lo) / (2 * r + 1)
    return a


def _poly_mask(x: np.ndarray, y: np.ndarray, pts: list[tuple[float, float]]) -> np.ndarray:
    inside = np.zeros(x.shape, bool)
    n = len(pts)
    for i in range(n):
        (xa, ya), (xb, yb) = pts[i], pts[(i + 1) % n]
        cond = (ya > y) != (yb > y)
        xi = (xb - xa) * (y - ya) / np.where(yb - ya == 0, 1e-9, yb - ya) + xa
        inside ^= cond & (x < xi)
    return inside


def render(heading: float) -> pygame.Surface:
    step = 1.0 / (PX * SS)
    xs = np.arange(X0, X1, step)
    ys = np.arange(Y1, Y0, -step)
    x, y = np.meshgrid(xs, ys)
    H = np.full(x.shape, -1e9)
    part = np.zeros(x.shape, np.int8)          # 1 saucer 2 neck 3 hull 4 pylon 5 nacelle
    rng = np.random.default_rng(1701)

    def put(mask: np.ndarray, h: np.ndarray, pid: int) -> None:
        nonlocal H
        take = mask & (h > H)
        H = np.where(take, h, H)
        part[take] = pid

    # secondary hull: an ellipsoid, slightly flattened on top
    q = (x / 7.0) ** 2 + ((y + 14.0) / 19.0) ** 2
    put(q < 1, 4.0 + 4.6 * np.sqrt(np.clip(1 - q, 0, 1)) ** 0.7, 3)
    # pylons: thin swept blades from the hull to the nacelles
    for sgn in (-1, 1):
        pts = [(sgn * 4.5, -15.0), (sgn * 16.0, -22.5), (sgn * 16.0, -27.5), (sgn * 4.5, -23.0)]
        m = _poly_mask(x, y, pts)
        t = np.clip((np.abs(x) - 4.5) / 11.5, 0, 1)
        put(m, 3.2 + 2.8 * t + 0.25 * np.cos((y + 22.0) * 0.5), 4)
    # nacelles: capsules with rounded ends, higher than everything but the saucer
    for sgn in (-1, 1):
        dx, dy = (x - sgn * 17.0) / 3.6, (y + 30.0) / 20.5
        q = dx ** 2 + np.abs(dy) ** 6
        put(q < 1, 7.0 + 3.4 * np.sqrt(np.clip(1 - q, 0, 1)), 5)
    # neck: a swept dorsal with a rounded cross-section
    neck = _poly_mask(x, y, [(-3.4, 6.0), (3.4, 6.0), (4.6, -7.0), (-4.6, -7.0)])
    w = 3.4 + (6.0 - y) / 13.0 * 1.2
    put(neck, 5.0 + 1.8 * np.sqrt(np.clip(1 - (x / np.maximum(w, 0.1)) ** 2, 0, 1)), 2)
    # saucer: a shallow dome with a rim, a sensor ring and a bridge dome
    rho = np.hypot(x, y - 24.0)
    R = 25.0
    s = np.clip(1 - (rho / R) ** 2, 0, 1)
    hs = 7.4 + 2.6 * np.sqrt(s) + 0.9 * np.sqrt(np.clip(1 - (rho / (R * 0.97)) ** 8, 0, 1))
    hs += 0.35 * ((rho > 8.6) & (rho < 9.6))                               # sensor ring
    hs += 0.25 * ((rho > 15.2) & (rho < 15.6))
    hs += 1.9 * np.sqrt(np.clip(1 - (rho / 4.2) ** 2, 0, 1))                # bridge dome
    put(rho < R, hs, 1)

    ship = part > 0
    H = np.where(ship, H, 0.0)

    # normals from the combined height field (units of hull units)
    gy, gx = np.gradient(H, step)
    gx, gy = np.clip(gx, -6, 6), np.clip(-gy, -6, 6)            # rows run downward in y
    N = _norm(np.stack([-gx, -gy, np.ones_like(H)], axis=-1))

    # the light turns against the ship, so on screen it always comes from the same side
    a = math.radians(heading)
    def ship_frame(v: tuple[float, float, float]) -> np.ndarray:
        lx, ly, lz = v
        return _norm(np.array([lx * math.cos(a) - ly * math.sin(a), lx * math.sin(a) + ly * math.cos(a), lz]))
    # heading is clockwise on screen; rotating the ship clockwise = rotating the light counter-clockwise
    L, Rm = ship_frame(LIGHT), ship_frame(RIM)
    V = np.array([0.0, 0.0, 1.0])
    Hv = _norm(L + V)

    ndl = np.clip(N @ L, 0, 1)
    spec = np.clip(N @ Hv, 0, 1) ** 48
    rim = np.clip(N @ Rm, 0, 1) ** 2 * (1 - N[..., 2]) ** 0.6
    fill = 0.5 + 0.5 * N[..., 1] * 0.3

    # albedo: hull plating, a touch warmer on the saucer, darker nacelles
    base = np.zeros(x.shape + (3,))
    base[:] = (0.74, 0.77, 0.80)
    base[part == 1] = (0.78, 0.80, 0.82)
    base[part == 5] = (0.56, 0.59, 0.64)
    base[part == 4] = (0.68, 0.71, 0.75)
    # plating: panels with slightly different tones
    ang = (np.degrees(np.arctan2(x, y - 24.0)) + 360.0) % 360.0
    ring_i = np.floor(rho / 3.1).astype(int)
    sect = np.floor(ang / (10.0 if True else 1)).astype(int)
    pid_s = ring_i * 97 + sect
    pid_h = np.floor((x + 40) / 2.6).astype(int) * 131 + np.floor((y + 80) / 3.4).astype(int)
    tones = rng.choice([-0.085, -0.03, 0.0, 0.0, 0.025, 0.045], 20000)       # two-tone plating
    tones[0] = 0.0
    pidx = np.where(part == 1, pid_s, pid_h) % 20000
    pidx = np.where((part == 1) & (rho < 4.6), 0, pidx)          # the bridge dome is one piece
    base *= (1.0 + tones[pidx])[..., None]
    # panel lines
    line = np.zeros(x.shape, bool)
    on_s = part == 1
    line |= on_s & (np.abs(rho / 3.1 - np.round(rho / 3.1)) * 3.1 < 0.07) & (rho > 5.0)
    line &= ~(on_s & (rho < 4.6))
    line |= on_s & (np.abs(ang / 10.0 - np.round(ang / 10.0)) * 10.0 * np.pi / 180.0 * rho < 0.07) & (rho > 9.6)
    on_h = (part >= 2) & (part != 5)
    line |= on_h & (np.abs((x + 40) / 2.6 - np.round((x + 40) / 2.6)) * 2.6 < 0.06)
    line |= on_h & (np.abs((y + 80) / 3.4 - np.round((y + 80) / 3.4)) * 3.4 < 0.06)
    on_n = part == 5
    line |= on_n & (np.abs((y + 80) / 2.2 - np.round((y + 80) / 2.2)) * 2.2 < 0.06)
    base[line] *= 0.72
    # a few darker accent bands: on the saucer rim and down the hull
    base[on_s & (rho > 23.6) & (rho < 24.2)] *= 0.8
    base[(part == 3) & (np.abs(x) < 0.5)] *= 0.86

    # phaser strips: thin dark arcs on the saucer's upper face
    for r0, a0, a1 in ((17.8, 300.0, 420.0), (17.8, 120.0, 240.0)):
        a_rel = (ang - a0) % 360.0
        base[on_s & (np.abs(rho - r0) < 0.32) & (a_rel < (a1 - a0))] *= 0.55
    # shuttle bay at the stern of the secondary hull, a dark recess
    bay = (part == 3) & (np.abs(x) < 2.6) & (y < -29.0)
    base[bay] *= 0.35

    # ambient occlusion: where the surroundings stand higher
    ao = np.clip(1.0 - np.clip(_blur(H, int(1.6 * PX * SS)) - H, 0, None) * 0.07, 0.6, 1.0)
    ao = np.where(ship, ao, 1.0)

    light = 0.14 * fill + 1.12 * ndl
    col = base * (light * ao)[..., None]
    col += (spec * 0.7 * ao)[..., None] + (np.clip(N @ Hv, 0, 1) ** 8 * 0.08 * ao)[..., None]
    col += rim[..., None] * np.array([0.28, 0.42, 0.62]) * 0.9
    col += ((1 - N[..., 2]) ** 3 * 0.25)[..., None] * np.array([0.5, 0.65, 0.9])     # a cool fresnel edge

    # emissive: windows, nacelle grilles, bussard caps, deflector halo, navigation lights
    em = np.zeros(x.shape + (3,))
    def dots(cx: np.ndarray, cy: np.ndarray, r: float, colr: tuple[float, float, float], where: np.ndarray) -> None:
        for px, py in zip(cx, cy):
            m = ((x - px) ** 2 + (y - py) ** 2 < r * r) & where
            em[m] = colr
    warm = (1.0, 0.9, 0.62)
    for rr, stepd, off in ((22.6, 2.6, 0.0), (21.6, 2.6, 1.3), (12.6, 6.0, 1.0)):
        th = np.radians(np.arange(off, 360.0, stepd))
        keep = (rng.uniform(0, 1, th.shape) < 0.62) & (np.abs(((np.degrees(th) + 180) % 360) - 180) < 165)
        dots(np.sin(th[keep]) * rr, 24.0 + np.cos(th[keep]) * rr, 0.2, warm, part == 1)
    for sgn in (-1, 1):
        yy = np.arange(-28.0, -2.0, 1.4)
        yy = yy[rng.uniform(0, 1, yy.shape) < 0.7]
        dots(np.full_like(yy, sgn * 5.4), yy, 0.2, warm, part == 3)
        # nacelle grilles down the inboard and outboard flanks
        dx, dy = x - sgn * 17.0, y + 30.0
        seg = np.abs(((dy + 40.0) / 1.5) % 1.0 - 0.5) < 0.36
        grille = (part == 5) & (np.abs(np.abs(dx) - 2.5) < 0.38) & (dy > -14.0) & (dy < 12.0) & seg
        em[grille] = (0.22, 0.5, 1.0)
        spine = (part == 5) & (np.abs(dx) < 0.35) & (dy > -16.0) & (dy < 14.0)
        base[spine] *= 0.8
        # bussard caps: the front of each nacelle glows red-orange
        k = np.clip(1 - ((dx / 2.6) ** 2 + ((dy - 18.2) / 2.0) ** 2), 0, 1)
        cap = (part == 5) & (k > 0)
        em[cap] = np.maximum(em[cap], np.stack([k, 0.34 * k ** 1.5, 0.12 * k ** 2], axis=-1)[cap] * 1.1)
    # impulse engines at the back of the saucer, and lights in the shuttle bay
    imp = on_s & (np.abs(np.abs(x) - 3.2) < 1.6) & (np.abs(y - 0.4) < 0.45)
    em[imp] = (0.85, 0.2, 0.1)
    dots(np.array([-1.6, 0.0, 1.6]), np.array([-31.0, -31.6, -31.0]), 0.25, (0.7, 0.85, 1.0), bay)
    # navigation lights on the saucer rim
    dots(np.array([-24.4]), np.array([24.0]), 0.5, (1.0, 0.2, 0.2), part == 1)
    dots(np.array([24.4]), np.array([24.0]), 0.5, (0.2, 1.0, 0.4), part == 1)

    deflector = np.exp(-((x / 3.2) ** 2 + ((y + 2.0) / 1.6) ** 2)) * ((part == 3) | (part == 2))
    em += deflector[..., None] * np.array([1.0, 0.66, 0.32]) * 0.8

    col = col * (1.0 - np.clip(em.max(axis=-1, keepdims=True) * 2.0, 0, 0.85)) + em
    # bloom: a soft glow around everything emissive, spilling past the hull
    glow = np.stack([_blur(em[..., i], int(0.9 * PX * SS)) for i in range(3)], axis=-1) * 1.3
    glow += np.stack([_blur(em[..., i], int(2.6 * PX * SS)) for i in range(3)], axis=-1) * 1.1
    glow += np.stack([_blur(em[..., i], int(5.0 * PX * SS)) for i in range(3)], axis=-1) * 0.6
    alpha = ship.astype(float)
    rgb = col * alpha[..., None] + glow
    a_out = np.clip(alpha + glow.max(axis=-1) * 0.9, 0, 1)
    rgb = rgb / np.maximum(a_out, 1e-6)[..., None]
    # tone map and gamma
    rgb = 1.0 - np.exp(-rgb * 1.25)
    rgb = np.clip(rgb, 0, 1) ** (1 / 1.1)

    # supersampled down
    h, w = rgb.shape[:2]
    h, w = h - h % SS, w - w % SS
    def down(arr: np.ndarray) -> np.ndarray:
        arr = arr[:h, :w]
        return arr.reshape(h // SS, SS, w // SS, SS, *arr.shape[2:]).mean(axis=(1, 3))
    a_d = down(a_out)
    rgb_d = down(rgb * a_out[..., None]) / np.maximum(a_d, 1e-6)[..., None]
    out = np.dstack([np.clip(rgb_d, 0, 1) * 255, a_d * 255]).astype(np.uint8)
    surf = pygame.image.frombuffer(np.ascontiguousarray(out).tobytes(), (out.shape[1], out.shape[0]), "RGBA")
    return surf.copy()


def main() -> None:
    pygame.init()
    OUT.mkdir(parents=True, exist_ok=True)
    only = [float(a) for a in sys.argv[1:]]
    for i in range(HEADINGS):
        hdg = 360.0 * i / HEADINGS
        if only and hdg not in only:
            continue
        s = render(hdg)
        path = OUT / f"heavy-cruiser-{int(hdg):03d}.png"
        pygame.image.save(s, str(path))
        print("wrote", path.name, s.get_size())


if __name__ == "__main__":
    main()
