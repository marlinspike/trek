"""Torpedoes in flight [E]: each race's rounds drawn their own way, big enough to find at any zoom.

The look is set per race in factions.toml (`colors.torpedo_style`):

- **photon**: a glowing core with a slowly turning star of light, pulsing a few times a second.
- **disruptor**: a harsher, flickering flare whose long spikes lie along its line of flight.
- **plasma**: a big soft ball that wobbles as it comes, with no spikes at all.
- **pulse**: a short bright bolt that flickers, streaking along its course.

A heavier warhead is drawn bigger and brighter. A round not yet armed glows dimmer. All sizes are in
pixels, with a floor, so a round never shrinks to nothing when the view zooms out; they grow a little
when zoomed right in.
"""

from __future__ import annotations

import math

import pygame

from . import theme
from .blast import add_light
from . import gfx

WHITE = (255, 255, 255)
BASE_PX = 4.0             # a Mark 7's core, pixels, at ordinary zoom
REF_YIELD = 15.0          # the warhead that is drawn at BASE_PX
PULSE_HZ = 6.0            # how fast a photon torpedo's light beats


def round_size(yield_: float, zoom: float) -> float:
    """Pixels across a round's core: by its warhead, never below a floor, a little bigger zoomed right in."""
    heft = max(0.8, min(1.6, (max(yield_, 1.0) / REF_YIELD) ** 0.6))
    near = max(1.0, min(2.2, (zoom / 0.12) ** 0.5))
    return BASE_PX * heft * near


def draw_round(surf: pygame.Surface, overlay: pygame.Surface, sx: float, sy: float, course: float,
               col: theme.Color, style: str, size: float, clock: float, seed: int, armed: bool = True) -> None:
    """One round at (sx, sy) on screen, heading `course` (compass degrees). Light is added onto `surf`."""
    bright = 1.0 if armed else 0.6
    hot = theme.mix(col, WHITE, 0.6)
    if style == "plasma":
        _plasma(surf, sx, sy, col, hot, size, clock, seed, bright)
    elif style == "disruptor":
        _disruptor(surf, overlay, sx, sy, course, col, hot, size, clock, seed, bright)
    elif style == "pulse":
        _pulse(surf, overlay, sx, sy, course, col, hot, size, clock, seed, bright)
    else:
        _photon(surf, overlay, sx, sy, col, hot, size, clock, seed, bright)


def _photon(surf: pygame.Surface, overlay: pygame.Surface, sx: float, sy: float, col: theme.Color,
            hot: theme.Color, size: float, clock: float, seed: int, bright: float) -> None:
    beat = 0.75 + 0.25 * math.sin(clock * math.tau * PULSE_HZ + seed)
    add_light(surf, sx, sy, size * 3.4, col, 0.55 * bright * beat)
    add_light(surf, sx, sy, size * 1.5, hot, 0.95 * bright)
    spin = clock * 1.6 + seed * 0.7
    for j in range(8):                                   # four long rays and four short between them
        a = spin + j * math.pi / 4
        reach = size * (3.6 if j % 2 == 0 else 2.0) * (0.85 + 0.15 * beat)
        tip = (sx + math.cos(a) * reach, sy + math.sin(a) * reach)
        alpha = int((150 if j % 2 == 0 else 90) * bright * beat)
        gfx.draw.line(overlay, (*hot, alpha), (sx, sy), tip, 1)
    gfx.draw.circle(surf, theme.mix(hot, WHITE, 0.5 * bright), (int(sx), int(sy)), max(1, int(size * 0.45)))


def _disruptor(surf: pygame.Surface, overlay: pygame.Surface, sx: float, sy: float, course: float,
               col: theme.Color, hot: theme.Color, size: float, clock: float, seed: int, bright: float) -> None:
    jag = 0.7 + 0.3 * abs(math.sin(clock * 37.0 + seed * 1.3))       # a ragged, uneven flicker
    add_light(surf, sx, sy, size * 2.8, col, 0.6 * bright * jag)
    add_light(surf, sx, sy, size * 1.3, hot, 0.95 * bright)
    a = math.radians(course)
    ux, uy = math.sin(a), -math.cos(a)                    # along the line of flight, on screen
    for along, reach, alpha in ((True, 4.2, 170), (False, 1.8, 110)):
        dx, dy = (ux, uy) if along else (-uy, ux)
        r = size * reach * jag
        gfx.draw.line(overlay, (*hot, int(alpha * bright)), (sx - dx * r, sy - dy * r), (sx + dx * r, sy + dy * r), 1)
    gfx.draw.circle(surf, theme.mix(hot, WHITE, 0.4 * bright), (int(sx), int(sy)), max(1, int(size * 0.4)))


def _plasma(surf: pygame.Surface, sx: float, sy: float, col: theme.Color, hot: theme.Color, size: float,
            clock: float, seed: int, bright: float) -> None:
    big = size * 1.5
    add_light(surf, sx, sy, big * 3.0, col, 0.45 * bright)
    for j in range(3):                                    # lobes of light that roll round the core
        a = clock * 4.0 + seed + j * math.tau / 3
        wob = big * 0.45 * (0.8 + 0.2 * math.sin(clock * 7.0 + j))
        add_light(surf, sx + math.cos(a) * wob, sy + math.sin(a) * wob, big * 1.3, col, 0.5 * bright)
    add_light(surf, sx, sy, big * 1.1, hot, 0.9 * bright)


def _pulse(surf: pygame.Surface, overlay: pygame.Surface, sx: float, sy: float, course: float,
           col: theme.Color, hot: theme.Color, size: float, clock: float, seed: int, bright: float) -> None:
    on = 0.6 + 0.4 * (1.0 if math.sin(clock * math.tau * 12.0 + seed) > 0 else 0.0)
    a = math.radians(course)
    ux, uy = math.sin(a), -math.cos(a)
    tail = size * 4.5
    gfx.draw.line(overlay, (*col, int(120 * bright * on)), (sx, sy), (sx - ux * tail, sy - uy * tail), max(2, int(size * 0.8)))
    gfx.draw.line(surf, hot, (sx, sy), (sx - ux * tail * 0.6, sy - uy * tail * 0.6), 1)
    add_light(surf, sx, sy, size * 2.4, col, 0.6 * bright * on)
    add_light(surf, sx, sy, size * 1.2, hot, 0.9 * bright)


__all__ = ["draw_round", "round_size"]
