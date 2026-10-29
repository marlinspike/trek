"""Palette, fonts and small drawing helpers for the tactical console.

A restrained, programmatic look: deep navy field, cyan for our side, muted
red for hostiles, amber for caution, teal for healthy systems.
"""

from __future__ import annotations

from functools import lru_cache
from pathlib import Path

import pygame

Color = tuple[int, int, int]

BG = (9, 16, 31)
BG_PANEL = (13, 22, 41)
BG_PANEL_HI = (19, 31, 56)
BG_INPUT = (7, 12, 24)
GRID = (22, 36, 62)
GRID_MAJOR = (30, 49, 82)
BORDER = (38, 58, 92)
BORDER_HI = (66, 98, 146)

TEXT = (206, 219, 236)
TEXT_DIM = (124, 142, 170)
TEXT_FAINT = (76, 92, 120)

FRIEND = (79, 209, 232)       # Federation / own side cyan
FRIEND_DIM = (44, 120, 140)
ALLY = (128, 196, 255)
HOSTILE = (201, 86, 79)       # muted red
HOSTILE_DIM = (120, 56, 56)
UNKNOWN = (190, 170, 120)
CAUTION = (232, 170, 64)      # amber
ALERT = (236, 98, 82)
GOOD = (64, 196, 168)         # teal: healthy systems
CREW = (178, 160, 230)
PHASER = (255, 170, 90)
PHASER_FRIEND = (130, 230, 255)
TORPEDO = (255, 120, 80)
TORPEDO_FRIEND = (120, 210, 255)
PLASMA = (140, 255, 120)
PROBE = (230, 200, 120)
BLAST = (255, 200, 140)
SHIELD = (96, 170, 255)

FONT_DIR = Path(__file__).resolve().parent.parent / "assets" / "fonts"


def health_color(health: float, destroyed: bool = False) -> Color:
    """Teal → amber → red as a system degrades; grey when destroyed."""
    if destroyed:
        return (70, 74, 86)
    if health >= 0.999:
        return GOOD
    if health >= 0.5:
        t = (health - 0.5) / 0.5
        return _mix(CAUTION, GOOD, t)
    return _mix(ALERT, CAUTION, health / 0.5)


def _mix(a: Color, b: Color, t: float) -> Color:
    t = max(0.0, min(1.0, t))
    return (int(a[0] + (b[0] - a[0]) * t), int(a[1] + (b[1] - a[1]) * t), int(a[2] + (b[2] - a[2]) * t))


def mix(a: Color, b: Color, t: float) -> Color:
    return _mix(a, b, t)


def dim(c: Color, f: float) -> Color:
    return (int(c[0] * f), int(c[1] * f), int(c[2] * f))


@lru_cache(maxsize=64)
def font(size: int, family: str = "ui", weight: str = "regular") -> pygame.font.Font:
    """Bundled fonts (Inter for UI, JetBrains Mono for figures), falling back to pygame's default."""
    files = {
        ("ui", "regular"): "Inter-Regular.otf",
        ("ui", "medium"): "Inter-Medium.otf",
        ("ui", "semibold"): "Inter-SemiBold.otf",
        ("mono", "regular"): "JetBrainsMono-Regular.ttf",
        ("mono", "medium"): "JetBrainsMono-Medium.ttf",
    }
    name = files.get((family, weight)) or files[(family, "regular")]
    path = FONT_DIR / name
    try:
        return pygame.font.Font(str(path), size)
    except (OSError, FileNotFoundError):
        return pygame.font.Font(None, int(size * 1.3))


def text(surf: pygame.Surface, s: str, pos: tuple[float, float], color: Color = TEXT, size: int = 14,
         family: str = "ui", weight: str = "regular", anchor: str = "topleft") -> pygame.Rect:
    img = font(size, family, weight).render(s, True, color)
    r = img.get_rect()
    setattr(r, anchor, (int(pos[0]), int(pos[1])))
    surf.blit(img, r)
    return r


def text_width(s: str, size: int = 14, family: str = "ui", weight: str = "regular") -> int:
    return font(size, family, weight).size(s)[0]


def bar(surf: pygame.Surface, rect: pygame.Rect, frac: float, color: Color, bg: Color = (24, 36, 60)) -> None:
    pygame.draw.rect(surf, bg, rect, border_radius=2)
    frac = max(0.0, min(1.0, frac))
    if frac > 0:
        r = rect.copy()
        r.width = max(1, int(rect.width * frac))
        pygame.draw.rect(surf, color, r, border_radius=2)


def panel(surf: pygame.Surface, rect: pygame.Rect, title: str | None = None, accent: Color = FRIEND) -> int:
    """Draw a panel frame; returns the y where content should start."""
    pygame.draw.rect(surf, BG_PANEL, rect, border_radius=4)
    pygame.draw.rect(surf, BORDER, rect, 1, border_radius=4)
    if title:
        pygame.draw.line(surf, accent, (rect.x + 10, rect.y + 1), (rect.x + 34, rect.y + 1), 2)
        text(surf, title.upper(), (rect.x + 10, rect.y + 7), TEXT_DIM, 11, weight="semibold")
        return rect.y + 26
    return rect.y + 8


__all__ = [n for n in dir() if n.isupper()] + ["bar", "dim", "font", "health_color", "mix", "panel", "text", "text_width"]
