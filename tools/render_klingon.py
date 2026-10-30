"""Bake the menu's Klingon battle cruiser sprite: `python tools/render_klingon.py`.

An original design in the spirit of the klingon.bc hull layout: a command pod on a long
boom, a broad engine hull, wings swept down and back to two nacelles. Lit and finished
the same way as the Enterprise (`render_ship.py`): height fields, key, fill and rim light,
specular, ambient occlusion, plating, panel lines and glowing red-orange emissives, then
supersampled down. Only one heading is baked; it only ever appears briefly and small, on
the menu's distant passes. Needs numpy, which the game itself does not.
"""

from __future__ import annotations

import math
import sys

import numpy as np
import pygame

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent))
from render_ship import LIGHT, OUT, PX, RIM, SS, _blur, _norm, _poly_mask  # noqa: E402

X0, X1, Y0, Y1 = -34.0, 34.0, -32.0, 42.0     # hull-unit bounds of the canvas
NAME = "klingon-battlecruiser.png"


def render() -> pygame.Surface:
    step = 1.0 / (PX * SS)
    x, y = np.meshgrid(np.arange(X0, X1, step), np.arange(Y1, Y0, -step))
    H = np.full(x.shape, -1e9)
    part = np.zeros(x.shape, np.int8)          # 1 pod 2 boom 3 engine hull 4 wing 5 nacelle
    rng = np.random.default_rng(1601)

    def put(mask: np.ndarray, h: np.ndarray, pid: int) -> None:
        nonlocal H
        take = mask & (h > H)
        H = np.where(take, h, H)
        part[take] = pid

    # wings: swept down and back from the engine hull, thinning toward the tips
    for sgn in (-1, 1):
        pts = [(sgn * 5.0, 2.0), (sgn * 27.0, -9.0), (sgn * 27.0, -17.0), (sgn * 5.0, -14.0)]
        t = np.clip((np.abs(x) - 5.0) / 22.0, 0, 1)
        put(_poly_mask(x, y, pts), 5.0 - 2.6 * t + 0.2 * np.cos(y * 0.6), 4)
    # nacelles at the wing tips
    for sgn in (-1, 1):
        dx, dy = (x - sgn * 27.5) / 2.8, (y + 12.0) / 12.0
        q = dx ** 2 + np.abs(dy) ** 5
        put(q < 1, 4.2 + 2.4 * np.sqrt(np.clip(1 - q, 0, 1)), 5)
    # engine hull: a broad teardrop, tapering aft
    q = (x / 8.5) ** 2 + ((y + 6.0) / np.where(y > -6.0, 9.0, 14.0)) ** 2
    put(q < 1, 4.6 + 3.2 * np.sqrt(np.clip(1 - q, 0, 1)), 3)
    # boom: long and slender, rising toward the pod
    boom = _poly_mask(x, y, [(-1.9, 28.0), (1.9, 28.0), (3.0, 0.0), (-3.0, 0.0)])
    w = 1.9 + (28.0 - y) / 28.0 * 1.1
    put(boom, 6.0 + 1.3 * np.sqrt(np.clip(1 - (x / np.maximum(w, 0.1)) ** 2, 0, 1)), 2)
    # command pod: a flattened bulb with a raised bridge
    q = (x / 6.4) ** 2 + ((y - 32.0) / 6.0) ** 2
    hp = 6.4 + 2.6 * np.sqrt(np.clip(1 - q, 0, 1))
    hp += 1.1 * np.sqrt(np.clip(1 - (x / 2.2) ** 2 - ((y - 30.5) / 2.6) ** 2, 0, 1))
    put(q < 1, hp, 1)

    ship = part > 0
    H = np.where(ship, H, 0.0)
    gy, gx = np.gradient(H, step)
    gx, gy = np.clip(gx, -6, 6), np.clip(-gy, -6, 6)
    N = _norm(np.stack([-gx, -gy, np.ones_like(H)], axis=-1))
    L, Rm = _norm(np.array(LIGHT)), _norm(np.array(RIM))
    Hv = _norm(L + np.array([0.0, 0.0, 1.0]))
    ndl = np.clip(N @ L, 0, 1)
    spec = np.clip(N @ Hv, 0, 1) ** 40
    rim = np.clip(N @ Rm, 0, 1) ** 2 * (1 - N[..., 2]) ** 0.6

    # albedo: a dark green-grey, plated in irregular panels
    base = np.zeros(x.shape + (3,))
    base[:] = (0.44, 0.52, 0.47)
    base[part == 5] = (0.36, 0.42, 0.39)
    base[part == 1] = (0.48, 0.55, 0.50)
    pid = np.floor((x + 40) / 3.0).astype(int) * 131 + np.floor((y + 80) / 2.4).astype(int)
    tones = rng.choice([-0.12, -0.05, 0.0, 0.0, 0.04, 0.08], 20000)
    base *= (1.0 + tones[pid % 20000])[..., None]
    line = (np.abs((x + 40) / 3.0 - np.round((x + 40) / 3.0)) * 3.0 < 0.07) | \
           (np.abs((y + 80) / 2.4 - np.round((y + 80) / 2.4)) * 2.4 < 0.07)
    base[line & ship] *= 0.7
    # a feathered pattern down the wings: darker chevrons
    chev = (part == 4) & (np.abs(((y + np.abs(x) * 0.5) / 2.2) % 1.0 - 0.5) < 0.12)
    base[chev] *= 0.78

    ao = np.clip(1.0 - np.clip(_blur(H, int(1.6 * PX * SS)) - H, 0, None) * 0.07, 0.6, 1.0)
    ao = np.where(ship, ao, 1.0)
    col = base * ((0.16 + 1.08 * ndl) * ao)[..., None]
    col += (spec * 0.55 * ao)[..., None]
    col += rim[..., None] * np.array([0.3, 0.5, 0.42]) * 0.8
    col += ((1 - N[..., 2]) ** 3 * 0.2)[..., None] * np.array([0.45, 0.65, 0.55])

    # emissive: the torpedo launcher at the pod's nose, bridge windows, nacelle strips, impulse
    em = np.zeros(x.shape + (3,))
    k = np.clip(1 - ((x / 1.6) ** 2 + ((y - 37.6) / 1.0) ** 2), 0, 1)
    em[(part == 1) & (k > 0)] = np.stack([k, 0.22 * k, 0.08 * k], axis=-1)[(part == 1) & (k > 0)] * 1.2
    for px_ in np.arange(-4.4, 4.5, 1.1):
        m = ((x - px_) ** 2 + (y - 34.2) ** 2 < 0.2 ** 2) & (part == 1)
        em[m] = (1.0, 0.72, 0.4)
    for sgn in (-1, 1):
        strip = (part == 5) & (np.abs(x - sgn * 27.5 + sgn * 1.7) < 0.4) & (y > -20.0) & (y < -3.0)
        em[strip] = (1.0, 0.28, 0.12)
        cap = (part == 5) & ((x - sgn * 27.5) ** 2 / 4.0 + (y + 1.5) ** 2 / 2.0 < 1)
        em[cap] = (1.0, 0.36, 0.14)
    imp = (part == 3) & (np.abs(np.abs(x) - 2.6) < 1.4) & (np.abs(y + 19.0) < 0.5)
    em[imp] = (1.0, 0.25, 0.1)

    col = col * (1.0 - np.clip(em.max(axis=-1, keepdims=True) * 2.0, 0, 0.85)) + em
    glow = np.stack([_blur(em[..., i], int(0.9 * PX * SS)) for i in range(3)], axis=-1) * 1.3
    glow += np.stack([_blur(em[..., i], int(2.6 * PX * SS)) for i in range(3)], axis=-1) * 1.0
    alpha = ship.astype(float)
    rgb = col * alpha[..., None] + glow
    a_out = np.clip(alpha + glow.max(axis=-1) * 0.9, 0, 1)
    rgb = rgb / np.maximum(a_out, 1e-6)[..., None]
    rgb = np.clip(1.0 - np.exp(-rgb * 1.25), 0, 1) ** (1 / 1.1)

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
    s = render()
    pygame.image.save(s, str(OUT / NAME))
    print("wrote", NAME, s.get_size(), "centre y", (Y0 + Y1) / 2)


if __name__ == "__main__":
    main()
