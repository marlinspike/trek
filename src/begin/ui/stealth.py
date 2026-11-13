"""What cloaks and plasma look like on the map [E]: our ship under her cloak, the flash when she fires
through it, the warp plasma a damaged drive leaves, a contact placed only by that plasma, and the
plasma-seeker torpedo hunting along a trail.

Drawing only: everything here is handed screen positions and times by `tactical.py`, which reads them
from the side's `Observation`.
"""

from __future__ import annotations

import math
from collections import OrderedDict
from collections.abc import Callable, Sequence

import pygame

from . import gfx, theme
from .camera import Camera

CLOAK_ALPHA = 110           # how much of her art's light shows through the cloak, 0..255
CLOAK_STRIP = 3             # pixels per band of the shimmer
CLOAK_SWAY = 1.6            # pixels the bands sway by
FLICKER = 0.55              # seconds she shows after firing through the cloak
FADED_CACHE = 48
_FADED: OrderedDict[tuple[int, int], tuple[pygame.Surface, pygame.Surface]] = OrderedDict()
SCENT_POINTS = 7            # trail points ahead of a seeker that light up as it hunts


def _faded(img: pygame.Surface, alpha: int) -> pygame.Surface:
    """Her art as the cloak lets it through: a sea-green ghost of light, premultiplied to be added onto the map
    (glass catching the light, not a shadow), as bright as `alpha` (0..255) allows."""
    key = (id(img), alpha // 8)
    hit = _FADED.get(key)
    if hit is not None and hit[0] is img:
        _FADED.move_to_end(key)
        return hit[1]
    tint = pygame.Surface(pygame.Surface.get_size(img), pygame.SRCALPHA, 32)     # physical pixels
    pygame.Surface.blit(tint, img, (0, 0), special_flags=pygame.BLEND_RGBA_MAX)
    g = alpha // 8 * 8
    col = theme.mix(theme.CLOAK, (255, 255, 255), 0.3)
    pygame.Surface.fill(tint, (col[0] * g // 255, col[1] * g // 255, col[2] * g // 255, 255),
                        special_flags=pygame.BLEND_RGBA_MULT)
    out = tint.premul_alpha()
    if isinstance(img, gfx.Canvas):
        out = gfx.adopt(out, img.density)
    _FADED[key] = (img, out)
    if len(_FADED) > FADED_CACHE:
        _FADED.popitem(last=False)
    return out


def cloaked_art(surf: pygame.Surface, img: pygame.Surface, rect: pygame.Rect, clock: float, flicker: float = 0.0) -> None:
    """Our ship under her cloak: her art, faint and sea-green, swaying in thin bands like air over hot metal.
    `flicker` (0..1) is the moment after she fired through it, when she shows almost whole."""
    alpha = int(CLOAK_ALPHA + (230 - CLOAK_ALPHA) * flicker + 14 * math.sin(clock * 1.7))
    faded = _faded(img, max(8, min(255, alpha)))
    w, h = img.get_size()
    sway = CLOAK_SWAY * (1.0 - flicker)
    for row in range(0, h, CLOAK_STRIP):
        off = sway * math.sin(clock * 3.1 + row * 0.21) + 0.6 * sway * math.sin(clock * 5.3 - row * 0.07)
        surf.blit(faded, (rect.x + round(off), rect.y + row), area=pygame.Rect(0, row, w, min(CLOAK_STRIP, h - row)),
                  special_flags=pygame.BLEND_RGB_ADD)


def cloak_field(overlay: pygame.Surface, sx: float, sy: float, rad: float, clock: float, flicker: float = 0.0) -> None:
    """The cloak's field round her: a slow, broken ring of light that turns, and breathes."""
    breath = 0.5 + 0.5 * math.sin(clock * 1.2)
    for ring, (n, speed, width, alpha) in enumerate(((7, 0.25, 2, 58), (11, -0.4, 1, 40))):
        r = rad + 4 + ring * 5 + 2 * breath
        box = pygame.Rect(0, 0, int(r * 2), int(r * 2))
        box.center = (int(sx), int(sy))
        a = int((alpha + 30 * breath) * (1.0 + 1.5 * flicker))
        for i in range(n):
            start = clock * speed + i * math.tau / n
            gfx.draw.arc(overlay, (*theme.CLOAK, min(255, a)), box, start, start + math.tau / n * 0.45, width)


def plasma_trail(overlay: pygame.Surface, cam: Camera, pts: Sequence[tuple[float, float, int]],
                 fresh: Callable[[int], float], clock: float, seed: int, own: bool = False) -> None:
    """Warp plasma vented from a damaged drive: a soft rose ribbon, brightest where it is fresh, breaking up
    into drifting wisps as it ages. Our own is fainter (it is what the enemy sees, not what we hunt)."""
    if len(pts) < 2:
        return
    col = theme.EXHAUST
    gain = 0.55 if own else 1.0
    screen = [cam.to_screen(x, y) for x, y, _ in pts]
    for i in range(len(pts) - 1):
        k = fresh(pts[i + 1][2])                                    # 1 fresh .. 0 gone
        if k <= 0.02:
            continue
        a, b = screen[i], screen[i + 1]
        gfx.draw.line(overlay, (*col, int(26 * k * gain)), a, b, 7)
        gfx.draw.aaline(overlay, (*theme.mix(col, (255, 255, 255), 0.4), int(120 * k * k * gain)), a, b, 1.0)
    for i, ((x, y), (_, _, born)) in enumerate(zip(screen, pts)):     # wisps: each point breathes out a puff
        k = fresh(born)
        if k <= 0.05:
            continue
        h = (seed * 7919 + born * 104729) & 0xFFFF
        drift = (1.0 - k) * 9.0
        dx = math.sin(clock * 0.7 + h) * drift + ((h & 0xFF) / 255.0 - 0.5) * 4
        dy = math.cos(clock * 0.6 + h * 0.37) * drift + ((h >> 8) / 255.0 - 0.5) * 4
        r = 1.5 + 3.5 * (1.0 - k)
        gfx.draw.circle(overlay, (*col, int(70 * k * gain)), (int(x + dx), int(y + dy)), int(r))


def scent(overlay: pygame.Surface, cam: Camera, pts: Sequence[tuple[float, float, int]], at: tuple[float, float],
          clock: float) -> None:
    """A plasma-seeker on the hunt: the stretch of trail just ahead of it lights up in a running pulse, so you
    can watch it take the scent and follow it."""
    if not pts:
        return
    near = min(range(len(pts)), key=lambda i: (pts[i][0] - at[0]) ** 2 + (pts[i][1] - at[1]) ** 2)
    ahead = pts[near:near + SCENT_POINTS]
    hot = theme.mix(theme.EXHAUST, (255, 255, 255), 0.55)
    prev = cam.to_screen(at[0], at[1])
    for j, (x, y, _) in enumerate(ahead):
        p = cam.to_screen(x, y)
        run = 0.5 + 0.5 * math.sin(clock * 9.0 - j * 0.9)
        fade = 1.0 - j / SCENT_POINTS
        gfx.draw.aaline(overlay, (*hot, int(150 * fade * run)), prev, p, 1.5)
        gfx.draw.circle(overlay, (*hot, int(200 * fade * run)), (int(p[0]), int(p[1])), 2)
        prev = p


def exhaust_fix(surf: pygame.Surface, overlay: pygame.Surface, sx: float, sy: float, rad: float, clock: float,
                cid: int) -> None:
    """A contact we have only by her plasma: no ship drawn, just a wavering rose ring where she must be (as wide
    as the fix is rough), a small flame at its heart, and the word EXHAUST so nobody mistakes it for a sighting."""
    col = theme.EXHAUST
    n = 48
    pts = []
    for i in range(n + 1):
        a = math.tau * i / n
        wob = 1.0 + 0.05 * math.sin(a * 5 + clock * 2.2 + cid) + 0.03 * math.sin(a * 9 - clock * 3.1)
        pts.append((sx + math.cos(a) * rad * wob, sy + math.sin(a) * rad * wob))
    breath = 0.5 + 0.5 * math.sin(clock * 2.0 + cid)
    gfx.draw.lines(overlay, (*col, int(70 + 60 * breath)), False, pts, 1)
    gfx.draw.circle(overlay, (*col, int(5 + 5 * breath)), (int(sx), int(sy)), int(rad))
    gfx.draw.circle(overlay, (*col, int(10 + 8 * breath)), (int(sx), int(sy)), int(rad * 0.35))
    flame = [(sx, sy - 7 - 2 * breath), (sx + 4, sy + 1), (sx + 1.5, sy + 4), (sx - 1.5, sy + 4), (sx - 4, sy + 1)]
    gfx.draw.polygon(surf, theme.mix(theme.BG, col, 0.75 + 0.25 * breath), flame)
    gfx.draw.circle(surf, theme.mix(col, (255, 255, 255), 0.6), (int(sx), int(sy + 1)), 1)


SNAP = 0.28                 # seconds a firing solution's brackets take to snap onto her
SOLUTION_FLASH = 0.6        # seconds of the ring that bursts out from her the moment the seeker hits


def firing_solution(surf: pygame.Surface, overlay: pygame.Surface, sx: float, sy: float, rad: float, left: float,
                    total: float, age: float, clock: float) -> None:
    """[E] Our seeker hit her: a firing solution for `left` of `total` seconds. A bright ring bursts out from her at
    the moment of the hit, four hot brackets snap onto her, and a thin ring round them drains clockwise as the
    window closes, so the captain sees at a glance how long is left to shoot. The colour is the plasma's own,
    burned whiter: the trail is what gave her away."""
    hot = theme.mix(theme.EXHAUST, (255, 255, 255), 0.45)
    if 0.0 <= age < SOLUTION_FLASH:
        k = age / SOLUTION_FLASH
        gfx.draw.circle(overlay, (*hot, int(190 * (1.0 - k) ** 2)), (int(sx), int(sy)), int(rad * (1.0 + 1.6 * k)), 2)
        gfx.draw.circle(overlay, (*theme.EXHAUST, int(60 * (1.0 - k))), (int(sx), int(sy)), int(rad * (0.9 + 0.6 * k)))
    t = min(1.0, max(0.0, age / SNAP)) if age >= 0 else 1.0
    ease = 1 - (1 - t) ** 3
    b = rad + 12 + rad * 1.2 * (1 - ease)
    frac = max(0.0, min(1.0, left / max(0.1, total)))
    urgent = frac < 0.34
    beat = 0.5 + 0.5 * math.sin(clock * (14.0 if urgent else 6.0))
    col = theme.mix(hot, (255, 255, 255), 0.25 * beat) if not urgent else theme.mix(theme.EXHAUST, hot, beat)
    arm = max(6.0, b * 0.42)
    for dx, dy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
        cx, cy = sx + dx * b, sy + dy * b
        gfx.draw.line(surf, col, (cx, cy), (cx - dx * arm, cy), 2)
        gfx.draw.line(surf, col, (cx, cy), (cx, cy - dy * arm), 2)
    r = b * 1.25
    box = pygame.Rect(0, 0, int(r * 2), int(r * 2))
    box.center = (int(sx), int(sy))
    gfx.draw.arc(overlay, (*theme.EXHAUST, 40), box, 0.0, math.tau, 1)
    if frac > 0.0:
        start = math.pi / 2                       # from twelve o'clock, draining clockwise as the seconds go
        gfx.draw.arc(overlay, (*hot, int(150 + 90 * beat)), box, start, start + math.tau * frac, 2)


def fire_flash(overlay: pygame.Surface, sx: float, sy: float, rad: float, age: float) -> None:
    """Where a ship fired from her cloak: a brief bright shiver of the field, gone in half a second."""
    t = age / FLICKER
    if not 0.0 <= t < 1.0:
        return
    r = rad * (0.8 + 0.7 * t)
    a = int(200 * (1.0 - t) ** 2)
    gfx.draw.circle(overlay, (*theme.mix(theme.CLOAK, (255, 255, 255), 0.5), a), (int(sx), int(sy)), int(r), 2)
    gfx.draw.circle(overlay, (*theme.CLOAK, a // 4), (int(sx), int(sy)), int(r * 0.8))


__all__ = ["FLICKER", "cloak_field", "cloaked_art", "exhaust_fix", "fire_flash", "firing_solution", "plasma_trail",
           "scent"]
