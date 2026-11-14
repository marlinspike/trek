"""Interface size [E]: the whole screen drawn larger on a big window that isn't Retina.

A Retina Mac or a Windows display at 150% already lays the window out in points and draws in real pixels, so the
game's 14-point text is a comfortable size there. A 27-inch monitor at 2560x1440 with no scaling shows the same
14 points as 14 tiny pixels. The cure is the one the Retina path already uses: lay the screen out on a smaller
logical canvas and draw it at a higher density. Text and hulls are set at the real pixel size, so they stay sharp
on the graphics card; the software renderer scales the finished frame up instead (a little softer).

`ui_scale` in Settings is 0 to follow the window (`auto`) or one of the sizes in `CHOICES`.
"""

from __future__ import annotations

import pygame

AUTO = 0.0
CHOICES: tuple[float, ...] = (AUTO, 1.0, 1.15, 1.3, 1.5)
LOW, HIGH = 1000, 1440        # window heights (in points) where the auto size starts to grow, and reaches 1.35
AT_HIGH = 1.35
MOST = 1.5
RETINA = 1.5                  # a density this high is already scaled by the system: auto leaves it alone


def auto(height: int, density: float = 1.0) -> float:
    """The interface size for a window `height` points tall: 1 up to 1,000 (every layout is designed for those),
    then growing so a maximised 2560x1440 window reads like a 1900x1070 one; never above 1.5."""
    if density >= RETINA or height <= LOW:
        return 1.0
    z = 1.0 + (AT_HIGH - 1.0) * (height - LOW) / (HIGH - LOW)
    return round(min(MOST, z) * 20) / 20


def chosen(setting: float, height: int, density: float = 1.0) -> float:
    """The size to draw at: the one picked in Settings, or the window's own when it is on auto."""
    try:
        v = float(setting)
    except (TypeError, ValueError):
        v = AUTO
    if v <= 0.0:
        return auto(height, density)
    return min(MOST, max(1.0, v))


def logical(points: tuple[int, int], zoom: float) -> tuple[int, int]:
    """The canvas the scenes lay out on: the window's size in points, divided by the interface size."""
    return max(1, round(points[0] / zoom)), max(1, round(points[1] / zoom))


MOUSE_EVENTS = (pygame.MOUSEMOTION, pygame.MOUSEBUTTONDOWN, pygame.MOUSEBUTTONUP)


def to_logical(ev: pygame.event.Event, zoom: float) -> pygame.event.Event:
    """A mouse event in the window's points, moved onto the logical canvas."""
    if zoom == 1.0 or ev.type not in MOUSE_EVENTS:
        return ev
    d = dict(ev.dict)
    d["pos"] = (int(ev.pos[0] / zoom + 1e-6), int(ev.pos[1] / zoom + 1e-6))
    if "rel" in d:
        d["rel"] = (round(ev.rel[0] / zoom), round(ev.rel[1] / zoom))
    return pygame.event.Event(ev.type, d)


def label(setting: float) -> str:
    return "Auto" if float(setting or 0.0) <= 0.0 else f"{round(float(setting) * 100)}%"


__all__ = ["AUTO", "CHOICES", "auto", "chosen", "label", "logical", "to_logical"]
