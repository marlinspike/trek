"""Bake lit sprites for every ship class: `python tools/render_fleet.py [class ...]`.

The heavy cruiser has hand-built art (`render_ship.py`); every other class is built here
from its hull in `hulls.toml`, so the picture always matches the outline, the weapon mounts
and the subsystems the game uses. Each shape becomes part of a height field:

- a hull ellipse is a dome, or a saucer (a shallow dome with a lip) when it is big and round;
- a hull polygon is a bevelled slab, with a raised spine where it straddles the keel;
- a nacelle is a capsule standing proud of the hull (a short, fat one is an engine block);
- a detail ellipse is a raised tier, or a dome when it is small (a bridge, a pod);
- a two-point detail is a panel groove, a longer one a raised plate.

Normals from the field are lit like the Enterprise (key, fill and rim light, specular,
ambient occlusion), over faction plating and markings, with windows, engines, impulse,
navigation lights and a deflector glowing and blooming. One sprite is baked every 30° so the
light stays put on screen while the ship turns. The canvas is centred on the hull origin.
Sprites go to `src/begin/assets/ships/fleet/<faction>-<class>-<heading>.png`; the game reads
their scale from `begin.ui.fleet_art.art_px`. Needs numpy, which the game itself does not.
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pygame

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
from render_ship import LIGHT, RIM, SS, _blur, _norm, _poly_mask  # noqa: E402

from begin.content.loader import default_content  # noqa: E402
from begin.content.schema import HullDef, Shape  # noqa: E402
from begin.ui.fleet_art import BAKED, FLEET_DIR, HAND_BUILT, art_px, sprite_name  # noqa: E402

Vec3 = tuple[float, float, float]
MARGIN = 6.0              # hull units of canvas around the hull, room for the bloom


@dataclass(frozen=True)
class Material:
    hull: Vec3            # plating albedo
    engine: Vec3          # nacelle albedo
    panel: tuple[float, float]   # plate size, hull units (across, along)
    window: Vec3
    glow: Vec3            # nacelle glow
    cap: Vec3             # the end of a nacelle that glows hottest
    impulse: Vec3
    rim: Vec3             # tint of the rim light
    tones: tuple[float, ...] = (-0.085, -0.03, 0.0, 0.0, 0.025, 0.045)


MATERIALS = {
    "federation": Material((0.75, 0.78, 0.81), (0.56, 0.59, 0.64), (2.6, 3.4), (1.0, 0.9, 0.62),
                           (0.22, 0.5, 1.0), (1.0, 0.34, 0.12), (0.85, 0.2, 0.1), (0.28, 0.42, 0.62)),
    "klingon": Material((0.44, 0.52, 0.47), (0.36, 0.42, 0.39), (3.0, 2.4), (1.0, 0.72, 0.4),
                        (1.0, 0.28, 0.12), (1.0, 0.36, 0.14), (1.0, 0.25, 0.1), (0.3, 0.5, 0.42),
                        (-0.12, -0.05, 0.0, 0.0, 0.04, 0.08)),
    "romulan": Material((0.55, 0.64, 0.57), (0.42, 0.5, 0.46), (2.8, 2.8), (0.75, 1.0, 0.8),
                        (0.3, 1.0, 0.48), (0.45, 1.0, 0.6), (0.3, 0.9, 0.45), (0.3, 0.58, 0.46)),
    "orion": Material((0.66, 0.55, 0.42), (0.47, 0.41, 0.35), (2.2, 3.0), (1.0, 0.82, 0.5),
                      (1.0, 0.6, 0.18), (1.0, 0.68, 0.22), (1.0, 0.5, 0.15), (0.62, 0.48, 0.32),
                      (-0.1, -0.04, 0.0, 0.0, 0.03, 0.07)),
}


@dataclass
class Part:
    kind: str             # saucer, dome, slab, nacelle, engine
    shape: Shape


@dataclass
class Baked:
    """Everything about a ship but the light: geometry, albedo, emissives."""
    px: float
    x: np.ndarray
    y: np.ndarray
    H: np.ndarray
    ship: np.ndarray
    base: np.ndarray
    em: np.ndarray
    rim: Vec3
    parts: list[Part] = field(default_factory=list)


def _extent(hull: HullDef) -> float:
    r = 0.0
    for s in hull.shapes:
        if s.kind == "ellipse":
            r = max(r, abs(s.center[0]) + s.radii[0], abs(s.center[1]) + s.radii[1])
        else:
            r = max([r] + [max(abs(px), abs(py)) for px, py in s.points])
    return r + MARGIN


def _bevel(mask: np.ndarray, units: float, px: float) -> np.ndarray:
    """0 at a shape's edge rising to 1 `units` inside it."""
    b = _blur(mask.astype(float), max(1, int(units * px * SS)))
    return np.where(mask, np.clip((b - 0.5) * 2.0, 0, 1), 0.0)


def _segment_dist(x: np.ndarray, y: np.ndarray, a: tuple[float, float], b: tuple[float, float]) -> np.ndarray:
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    t = np.clip(((x - ax) * dx + (y - ay) * dy) / max(1e-9, dx * dx + dy * dy), 0, 1)
    return np.hypot(x - (ax + t * dx), y - (ay + t * dy))


def _is_saucer(s: Shape) -> bool:
    rx, ry = s.radii
    return rx >= 12 and abs(rx - ry) <= 0.2 * max(rx, ry)


def build(hull: HullDef, faction: str, px: float, seed: int) -> Baked:
    mat = MATERIALS.get(faction, MATERIALS["federation"])
    R = _extent(hull)
    step = 1.0 / (px * SS)
    x, y = np.meshgrid(np.arange(-R, R, step), np.arange(R, -R, -step))
    H = np.full(x.shape, -1e9)
    part = np.zeros(x.shape, np.int16)
    parts: list[Part] = []
    rng = np.random.default_rng(seed)

    def put(mask: np.ndarray, h: np.ndarray, p: Part) -> None:
        nonlocal H
        parts.append(p)
        take = mask & (h > H)
        H = np.where(take, h, H)
        part[take] = len(parts)

    station = not any(s.role == "nacelle" for s in hull.shapes)
    for s in hull.shapes:
        if s.role == "hull" and s.kind == "ellipse":
            (cx, cy), (rx, ry) = s.center, s.radii
            q = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if _is_saucer(s):
                Rs = (rx + ry) / 2
                rho = np.sqrt(q)
                h = 5.0 + 0.104 * Rs * np.sqrt(np.clip(1 - q, 0, 1)) + 0.9 * np.sqrt(np.clip(1 - (rho / 0.97) ** 8, 0, 1))
                put(q < 1, h, Part("saucer", s))
            else:
                amp = min(7.0, max(1.2, 0.55 * min(rx, ry)))
                put(q < 1, 3.5 + amp * np.sqrt(np.clip(1 - q, 0, 1)) ** 0.7, Part("dome", s))
        elif s.role == "hull":
            m = _poly_mask(x, y, list(s.points))
            xs = [p[0] for p in s.points]
            h = 3.0 + 1.8 * np.sqrt(_bevel(m, 1.8, px))
            if min(xs) < 0 < max(xs) and not station:     # a spine down the keel
                half = max(abs(min(xs)), max(xs))
                h += 1.4 * np.exp(-(x / max(2.0, 0.18 * half)) ** 2) * _bevel(m, 3.0, px)
            put(m, h, Part("slab", s))
    for s in hull.shapes:
        if s.role != "nacelle" or s.kind != "ellipse":
            continue
        (cx, cy), (rx, ry) = s.center, s.radii
        dx, dy = (x - cx) / rx, (y - cy) / ry
        if rx > 0.45 * ry:                                # short and fat: an engine block
            q = dx ** 2 + dy ** 2
            put(q < 1, 5.0 + 0.7 * rx * np.sqrt(np.clip(1 - q, 0, 1)), Part("engine", s))
        else:
            q = dx ** 2 + np.abs(dy) ** 6
            put(q < 1, 6.5 + 0.95 * rx * np.sqrt(np.clip(1 - q, 0, 1)), Part("nacelle", s))

    ship = part > 0
    H = np.where(ship, H, 0.0)
    kind = np.array([""] + [p.kind for p in parts])[part]
    hullish = ship & (kind != "nacelle") & (kind != "engine")

    # plating: polar panels on saucers, a grid elsewhere, two-tone
    base = np.zeros(x.shape + (3,))
    base[:] = mat.hull
    base[(kind == "nacelle") | (kind == "engine")] = mat.engine
    tones = rng.choice(mat.tones, 20000)
    tones[0] = 0.0
    pw, ph = mat.panel
    pid = np.floor((x + 200) / pw).astype(int) * 131 + np.floor((y + 200) / ph).astype(int)
    line = (np.abs((x + 200) / pw - np.round((x + 200) / pw)) * pw < 0.06) | \
           (np.abs((y + 200) / ph - np.round((y + 200) / ph)) * ph < 0.06)
    line &= ship & (kind != "nacelle") & (kind != "engine")
    for i, p in enumerate(parts, start=1):
        on = part == i
        if p.kind == "saucer":
            (cx, cy), (rx, ry) = p.shape.center, p.shape.radii
            rho = np.hypot(x - cx, y - cy)
            ang = (np.degrees(np.arctan2(x - cx, y - cy)) + 360.0) % 360.0
            ring = 3.1
            pid = np.where(on, np.floor(rho / ring).astype(int) * 97 + np.floor(ang / 10.0).astype(int), pid)
            sline = (np.abs(rho / ring - np.round(rho / ring)) * ring < 0.07) | \
                    (np.abs(ang / 10.0 - np.round(ang / 10.0)) * 10.0 * np.pi / 180.0 * rho < 0.07)
            line = np.where(on, sline & (rho > 4.0), line)
            base[on & (np.abs(rho - (rx + ry) / 2 * 0.95) < 0.3)] *= 0.8          # the rim
        elif p.kind == "nacelle":
            (cx, cy), (rx, ry) = p.shape.center, p.shape.radii
            line |= on & (np.abs((y + 200) / 2.2 - np.round((y + 200) / 2.2)) * 2.2 < 0.06)
            base[on & (np.abs(x - cx) < 0.1 * rx + 0.12)] *= 0.82                  # a spine
    base *= (1.0 + tones[pid % 20000])[..., None]
    base[line] *= 0.72

    # faction markings
    if faction == "klingon":
        chev = hullish & (kind == "slab") & (np.abs(((y + np.abs(x) * 0.5) / 2.2) % 1.0 - 0.5) < 0.12) & (np.abs(x) > 6)
        base[chev] *= 0.78
    elif faction == "romulan":
        # feathers fanning out across the wings, darker at the trailing edge
        for i, p in enumerate(parts, start=1):
            if p.kind != "slab":
                continue
            on = part == i
            top = max(py for _, py in p.shape.points)
            fan = np.degrees(np.arctan2(np.abs(x), top - y + 4.0))
            band = (np.floor(fan / 7.0).astype(int) % 2 == 0) & (np.abs(x) > 4)
            base[on & band] *= np.array([0.86, 0.95, 0.88])
            edge = _bevel(_poly_mask(x, y, list(p.shape.points)), 2.2, px)
            base[on & (edge < 0.75) & (np.abs(x) > 6)] *= np.array([0.78, 0.9, 0.8])
    elif faction == "orion":
        stripe = hullish & (np.abs(np.abs(x) - 3.4) < 0.7)
        base[stripe] *= np.array([0.62, 0.42, 0.32])
    elif faction == "federation":
        base[hullish & (kind == "dome") & (np.abs(x) < 0.5)] *= 0.86

    # details: tiers and domes raised, grooves cut
    for s in hull.shapes:
        if s.role != "detail":
            continue
        if s.kind == "ellipse":
            (cx, cy), (rx, ry) = s.center, s.radii
            q = ((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2
            if max(rx, ry) <= 9:
                H += np.where(ship & (q < 1), 1.6 * np.sqrt(np.clip(1 - q, 0, 1)), 0.0)
                tones_ok = ship & (q < 1)
                base[tones_ok] = np.array(mat.hull) * 1.03
            else:
                H += np.where(ship, 0.9 * np.sqrt(_bevel(q < 1, 1.2, px)), 0.0)
                base[ship & (np.abs(np.sqrt(q) - 1) * (rx + ry) / 2 < 0.14)] *= 0.62
        elif len(s.points) == 2:
            groove = ship & (_segment_dist(x, y, s.points[0], s.points[1]) < 0.3)
            H -= np.where(groove, 0.25, 0.0)
            base[groove] *= 0.6
        else:
            m = _poly_mask(x, y, list(s.points))
            H += np.where(ship, 0.7 * np.sqrt(_bevel(m, 1.0, px)), 0.0)
            edge = m & (_bevel(m, 0.35, px) < 0.5)
            base[edge & ship] *= 0.62

    # emissives
    em = np.zeros(x.shape + (3,))
    edge = _bevel(hullish, 2.4, px)
    band = hullish & (edge > 0.35) & (edge < 0.8)
    sx, sy = 1.25, 1.9
    i_, j_ = np.round(x / sx), np.round(y / sy)
    lit = (np.sin(i_ * 12.9898 + j_ * 78.233 + seed) * 43758.5453) % 1.0 < 0.4
    windows = band & lit & (np.hypot(x - i_ * sx, y - j_ * sy) < 0.21)
    for p in parts:
        if p.kind == "saucer":                                # rings of windows round the rim
            (cx, cy), (rx, ry) = p.shape.center, p.shape.radii
            Rs = (rx + ry) / 2
            rho = np.hypot(x - cx, y - cy)
            ang = np.degrees(np.arctan2(x - cx, y - cy))
            for rr, gap in ((0.9 * Rs, 2.6), (0.86 * Rs, 2.6), (0.5 * Rs, 5.0)):
                pitch = gap / rr * 180.0 / np.pi
                k = np.round(ang / pitch)
                keep = (np.sin(k * 7.13 + rr * 3.1 + seed) * 9137.31) % 1.0 < 0.62
                windows |= (part > 0) & (np.abs(rho - rr) < 0.21) & (np.abs(ang - k * pitch) * np.pi / 180 * rr < 0.21) & keep
            windows &= ~((kind == "saucer") & (np.abs(rho - 0.95 * Rs) < 0.5))
    # lit ports down the length of a long plate (a starbase's spokes)
    for s in hull.shapes:
        if s.role != "detail" or s.kind != "poly" or len(s.points) < 3:
            continue
        xs, ys = [p[0] for p in s.points], [p[1] for p in s.points]
        w_, h_ = max(xs) - min(xs), max(ys) - min(ys)
        if max(w_, h_) < 2.5 * min(w_, h_):
            continue
        m = _poly_mask(x, y, list(s.points))
        mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
        along, across = (x, y - my) if w_ > h_ else (y, x - mx)
        k = np.round(along / 1.4)
        windows |= m & (np.abs(across) < 0.22) & (np.abs(along - k * 1.4) < 0.22)
    em[windows & hullish] = mat.window
    # a station's corners carry beacons
    if station:
        for s in hull.shapes:
            if s.role == "hull" and s.kind == "poly":
                for vx, vy in s.points:
                    d = math.hypot(vx, vy)
                    bx, by = vx * (d - 1.6) / d, vy * (d - 1.6) / d
                    em[hullish & (np.hypot(x - bx, y - by) < 0.6)] = mat.cap

    for p in parts:
        if p.kind not in ("nacelle", "engine"):
            continue
        (cx, cy), (rx, ry) = p.shape.center, p.shape.radii
        on = (part > 0) & (((x - cx) / rx) ** 2 + ((y - cy) / ry) ** 2 < 1.05)
        dx, dy = x - cx, (y - cy) / ry
        front = 1.0 if faction != "orion" else -1.0          # Orion engines burn at the stern
        k = np.clip(1 - (dx / (0.78 * rx)) ** 2 - ((dy - front * 0.86) / 0.12) ** 2, 0, 1)
        cap = on & (k > 0)
        em[cap] = np.maximum(em[cap], (np.array(mat.cap)[None, :] * np.stack([k, k ** 1.5, k ** 2], axis=-1)[cap] ** 0.6) * 1.1)
        if p.kind == "engine":
            k2 = np.clip(1 - (dx / (0.7 * rx)) ** 2 - ((dy + 0.86) / 0.14) ** 2, 0, 1)
            em[on & (k2 > 0)] = np.array(mat.glow) * k2[on & (k2 > 0), None] ** 0.5
            continue
        span = (dy > -0.75) & (dy < 0.6)
        seg = np.abs(((y + 200.0) / 1.5) % 1.0 - 0.5) < 0.36
        w = max(0.3, 0.1 * rx)
        if faction == "federation":
            em[on & span & seg & (np.abs(np.abs(dx) - 0.69 * rx) < w)] = mat.glow
        elif faction == "klingon":
            side = -np.sign(cx) if cx != 0 else 1.0
            em[on & span & (np.abs(dx - side * 0.5 * rx) < w)] = mat.glow
        elif faction == "romulan":
            em[on & span & (np.abs(dx) < 0.32 * rx)] = np.array(mat.glow) * 0.85
        else:
            em[on & (dy > -0.6) & (dy < 0.6) & seg & (np.abs(dx) < w)] = np.array(mat.glow) * 0.7

    # impulse engines at the stern of the main hull, unless a nacelle sits there
    col = hullish & (np.abs(x) < 0.6)
    if col.any():
        y_aft = float(y[col].min())
        imp = hullish & (np.abs(np.abs(x) - 1.7) < 1.0) & (np.abs(y - (y_aft + 0.9)) < 0.4)
        em[imp] = mat.impulse
    # navigation lights at the beam's widest, and a Klingon torpedo tube aglow at the nose
    if faction == "federation" and hullish.any():
        xm = float(np.abs(x[hullish]).max())
        tip = hullish & (np.abs(x) > xm - 0.9)
        ym = float(y[tip].mean())
        em[hullish & (np.hypot(x + xm - 0.6, y - ym) < 0.5)] = (1.0, 0.2, 0.2)
        em[hullish & (np.hypot(x - xm + 0.6, y - ym) < 0.5)] = (0.2, 1.0, 0.4)
        # the deflector: at the forward end of a secondary hull below the saucer
        saucers = [p for p in parts if p.kind == "saucer"]
        for p in parts:
            if p.kind == "dome" and p.shape.kind == "ellipse" and saucers and p.shape.center[1] < saucers[0].shape.center[1]:
                (cx, cy), (rx, ry) = p.shape.center, p.shape.radii
                dy0 = cy + 0.6 * ry
                defl = np.exp(-((x - cx) / (0.45 * rx)) ** 2 - ((y - dy0) / 1.6) ** 2) * hullish
                em += defl[..., None] * np.array([1.0, 0.66, 0.32]) * 0.8
                break
    if faction == "klingon" and col.any():
        y_nose = float(y[col].max())
        k = np.clip(1 - (x / 1.6) ** 2 - ((y - (y_nose - 1.2)) / 0.9) ** 2, 0, 1)
        em[hullish & (k > 0)] = np.array(mat.cap)[None, :] * k[hullish & (k > 0), None] * 1.1

    return Baked(px, x, y, H, ship, base, em, mat.rim, parts)


def shade(b: Baked, heading: float) -> pygame.Surface:
    """Light the ship for a heading (degrees clockwise on screen): the light stays put, so it turns against her."""
    step = 1.0 / (b.px * SS)
    gy, gx = np.gradient(b.H, step)
    gx, gy = np.clip(gx, -6, 6), np.clip(-gy, -6, 6)
    N = _norm(np.stack([-gx, -gy, np.ones_like(b.H)], axis=-1))
    a = math.radians(heading)

    def ship_frame(v: Vec3) -> np.ndarray:
        lx, ly, lz = v
        return _norm(np.array([lx * math.cos(a) - ly * math.sin(a), lx * math.sin(a) + ly * math.cos(a), lz]))
    L, Rm = ship_frame(LIGHT), ship_frame(RIM)
    Hv = _norm(L + np.array([0.0, 0.0, 1.0]))
    ndl = np.clip(N @ L, 0, 1)
    spec = np.clip(N @ Hv, 0, 1) ** 44
    rim = np.clip(N @ Rm, 0, 1) ** 2 * (1 - N[..., 2]) ** 0.6
    fill = 0.5 + 0.15 * N[..., 1]

    ao = np.clip(1.0 - np.clip(_blur(b.H, max(1, int(1.6 * b.px * SS))) - b.H, 0, None) * 0.07, 0.6, 1.0)
    ao = np.where(b.ship, ao, 1.0)
    col = b.base * ((0.14 * fill + 1.12 * ndl) * ao)[..., None]
    col += (spec * 0.6 * ao)[..., None] + (np.clip(N @ Hv, 0, 1) ** 8 * 0.08 * ao)[..., None]
    col += rim[..., None] * np.array(b.rim) * 0.9
    col += ((1 - N[..., 2]) ** 3 * 0.22)[..., None] * np.array(b.rim) * 1.5

    em = b.em
    col = col * (1.0 - np.clip(em.max(axis=-1, keepdims=True) * 2.0, 0, 0.85)) + em
    glow = np.zeros_like(em)
    for units, gain in ((0.9, 1.3), (2.6, 1.1), (5.0, 0.6)):
        r = max(1, int(units * b.px * SS))
        glow += np.stack([_blur(em[..., i], r) for i in range(3)], axis=-1) * gain
    alpha = b.ship.astype(float)
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
    a_d = np.where(a_d < 4 / 255, 0.0, a_d)             # no faint haze far out: smaller files
    rgb_d = down(rgb * a_out[..., None]) / np.maximum(a_d, 1e-6)[..., None]
    out = np.dstack([np.clip(rgb_d, 0, 1) * 255, a_d * 255]).astype(np.uint8)
    out[a_d == 0] = 0
    surf = pygame.image.frombuffer(np.ascontiguousarray(out).tobytes(), (out.shape[1], out.shape[0]), "RGBA")
    return surf.copy()


def main() -> None:
    pygame.init()
    FLEET_DIR.mkdir(parents=True, exist_ok=True)
    content = default_content()
    only = set(sys.argv[1:])
    for n, (cid, cls) in enumerate(sorted(content.classes.items())):
        if cid in HAND_BUILT or cls.hull is None or (only and cid not in only):
            continue
        b = build(cls.hull, cls.faction, art_px(cls.hull.length), seed=1701 + n)
        for i in range(BAKED):
            hdg = 360 * i // BAKED
            s = shade(b, hdg)
            pygame.image.save(s, str(FLEET_DIR / sprite_name(cid, hdg)))
        print("baked", cid, s.get_size(), f"{b.px} px/unit")


if __name__ == "__main__":
    main()
