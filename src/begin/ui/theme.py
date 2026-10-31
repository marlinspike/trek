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
HAIL = (238, 196, 120)         # an enemy captain's voice over the comms [E]
PHASER = (255, 170, 90)
PHASER_FRIEND = (130, 230, 255)
TORPEDO = (255, 120, 80)
TORPEDO_FRIEND = (120, 210, 255)
PLASMA = (140, 255, 120)
PROBE = (230, 200, 120)
BLAST = (255, 200, 140)
SHIELD = (96, 170, 255)
REPAIR = (120, 220, 255)      # systems the repair crews are working on

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


_FONT_FILES = {
    ("ui", "regular"): "Inter-Regular.ttf",
    ("ui", "medium"): "Inter-Medium.ttf",
    ("ui", "semibold"): "Inter-SemiBold.ttf",
    ("mono", "regular"): "JetBrainsMono-Regular.ttf",
    ("mono", "medium"): "JetBrainsMono-Medium.ttf",
    ("display", "regular"): "Exo2-Medium.ttf",
    ("display", "medium"): "Exo2-Medium.ttf",
    ("display", "semibold"): "Exo2-SemiBold.ttf",
    ("title", "regular"): "Goldman-Bold.ttf",
}
# Exo 2, the display face for headings, menus and short buttons, is spaced out a little, console-style.
# Goldman is only for the game's title, drawn as metal lettering by `title_art`.
_SCALE: dict[str, float] = {}
_TRACK = {"display": 0.06, "title": 0.06}       # extra space between letters, as a fraction of the size


def _usable(f: pygame.font.Font) -> bool:
    """Some SDL_ttf/FreeType builds load a font but measure every glyph as zero width."""
    try:
        return f.size("Ag")[0] > 0 and f.render("Ag", True, TEXT).get_width() > 0
    except pygame.error:
        return False


@lru_cache(maxsize=64)
def _fallback(size: int) -> pygame.font.Font:
    return pygame.font.Font(None, int(size * 1.3))


@lru_cache(maxsize=64)
def font(size: int, family: str = "ui", weight: str = "regular") -> pygame.font.Font:
    """Bundled fonts (Inter for text, JetBrains Mono for figures, Exo 2 for headings and buttons, Goldman for the title),
    falling back to pygame's default."""
    name = _FONT_FILES.get((family, weight)) or _FONT_FILES[(family, "regular")]
    try:
        f = pygame.font.Font(str(FONT_DIR / name), round(size * _SCALE.get(family, 1.0)))
        if _usable(f):
            return f
    except (OSError, pygame.error):
        pass
    return _fallback(size)


def _has_glyphs(f: pygame.font.Font, s: str) -> bool:
    """The display face covers Latin text and punctuation, but no arrows or symbols (U+2190 on); SDL
    draws a box for a missing glyph rather than saying so, hence the range check."""
    return all(ord(c) < 0x2190 for c in s)


@lru_cache(maxsize=1024)
def _tracked(s: str, color: Color, size: int, family: str, weight: str) -> pygame.Surface:
    """A line drawn a letter at a time with extra space between the letters."""
    f = font(size, family, weight)
    gap = round(size * _TRACK[family])
    glyphs = [f.render(c, True, color) for c in s]
    w = sum(g.get_width() for g in glyphs) + gap * max(0, len(s) - 1)
    out = pygame.Surface((max(1, w), f.get_height()), pygame.SRCALPHA)
    x = 0
    for g in glyphs:
        out.blit(g, (x, 0))
        x += g.get_width() + gap
    return out


def render(s: str, color: Color, size: int = 14, family: str = "ui", weight: str = "regular") -> pygame.Surface:
    """Render a line of text, never raising: a string the font can't measure falls back to the default font.

    The same labels are drawn every frame, so finished lines are cached; callers must not draw on the result."""
    return _render_cached(s, tuple(color), size, family, weight)    # type: ignore[arg-type]


@lru_cache(maxsize=2048)
def _render_cached(s: str, color: Color, size: int, family: str, weight: str) -> pygame.Surface:
    f = font(size, family, weight)
    if family == "display" and not _has_glyphs(f, s):
        f = font(size, "ui", weight)              # a symbol the display face lacks: the whole label in Inter
    elif family in _TRACK and f is not _fallback(size):
        try:
            return _tracked(s, tuple(color), size, family, weight)    # type: ignore[arg-type]
        except pygame.error:
            pass
    try:
        return f.render(s, True, color)
    except pygame.error:
        pass
    try:
        return _fallback(size).render(s, True, color)
    except pygame.error:
        return pygame.Surface((0, f.get_height()), pygame.SRCALPHA)


def text(surf: pygame.Surface, s: str, pos: tuple[float, float], color: Color = TEXT, size: int = 14,
         family: str = "ui", weight: str = "regular", anchor: str = "topleft") -> pygame.Rect:
    img = render(s, color, size, family, weight)
    r = img.get_rect()
    setattr(r, anchor, (int(pos[0]), int(pos[1])))
    surf.blit(img, r)
    return r


def text_width(s: str, size: int = 14, family: str = "ui", weight: str = "regular") -> int:
    try:
        f = font(size, family, weight)
        if family == "display" and not _has_glyphs(f, s):
            f = font(size, "ui", weight)
        elif family in _TRACK:
            return f.size(s)[0] + round(size * _TRACK[family]) * max(0, len(s) - 1)
        return f.size(s)[0]
    except pygame.error:
        return _fallback(size).size(s)[0]


def bar(surf: pygame.Surface, rect: pygame.Rect, frac: float, color: Color, bg: Color = (24, 36, 60)) -> None:
    pygame.draw.rect(surf, bg, rect, border_radius=2)
    frac = max(0.0, min(1.0, frac))
    if frac > 0:
        r = rect.copy()
        r.width = max(1, int(rect.width * frac))
        pygame.draw.rect(surf, color, r, border_radius=2)


_alert = 0.0      # 0..1: how far panel borders are tinted red this frame (red alert)


def set_alert(level: float) -> None:
    """Red alert: the panels' borders take on this much of the alert colour (0 = none)."""
    global _alert
    _alert = max(0.0, min(1.0, level))


def border() -> Color:
    return mix(BORDER, ALERT, _alert) if _alert > 0 else BORDER


def panel(surf: pygame.Surface, rect: pygame.Rect, title: str | None = None, accent: Color = FRIEND) -> int:
    """Draw a panel frame; returns the y where content should start."""
    pygame.draw.rect(surf, BG_PANEL, rect, border_radius=4)
    pygame.draw.rect(surf, border(), rect, 1, border_radius=4)
    if title:
        pygame.draw.line(surf, accent, (rect.x + 10, rect.y + 1), (rect.x + 34, rect.y + 1), 2)
        text(surf, title.upper(), (rect.x + 10, rect.y + 5), TEXT_DIM, 11, "display", weight="medium")
        return rect.y + 26
    return rect.y + 8


GOLD_METAL = ((0.0, (255, 244, 190)), (0.45, (240, 190, 80)), (0.55, (170, 110, 30)), (1.0, (250, 210, 110)))


@lru_cache(maxsize=8)
def title_art(s: str, size: int, lean: float = 0.15) -> pygame.Surface:
    """The game's title as metal lettering: a gold sheen banded across the middle, a bevelled top edge,
    a dark outline and a warm glow. The surface has a margin of `size // 3` round the letters."""
    m = render(s, (255, 255, 255), size, "title")
    w, h = m.get_size()
    if lean:                                     # sheared a row at a time into a forward lean
        sheared = pygame.Surface((w + int(h * lean), h), pygame.SRCALPHA)
        for y in range(h):
            sheared.blit(m, (int((h - y) * lean), y), pygame.Rect(0, y, w, 1))
        m = sheared
        w = m.get_width()
    fill = pygame.Surface((w, h), pygame.SRCALPHA)
    stops = GOLD_METAL
    for y in range(h):
        t = y / max(1, h - 1)
        for (t0, c0), (t1, c1) in zip(stops, stops[1:]):
            if t0 <= t <= t1:
                pygame.draw.line(fill, (*_mix(c0, c1, (t - t0) / (t1 - t0)), 255), (0, y), (w, y))
                break
    fill.blit(m, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)        # the sheen, cut to the letters
    pad = size // 3
    out = pygame.Surface((w + pad * 2, h + pad * 2), pygame.SRCALPHA)
    glow = pygame.Surface(out.get_size(), pygame.SRCALPHA)
    glow.blit(m, (pad, pad))
    glow.fill((255, 150, 60, 255), special_flags=pygame.BLEND_RGBA_MULT)
    glow = pygame.transform.gaussian_blur(glow, max(4, h // 10))
    glow.fill((255, 255, 255, 150), special_flags=pygame.BLEND_RGBA_MULT)
    out.blit(glow, (0, 0))
    edge = m.copy()                              # a dark outline a few pixels thick
    edge.fill((10, 20, 40, 255), special_flags=pygame.BLEND_RGBA_MULT)
    r = max(2, size // 26)
    for dx in range(-r, r + 1):
        for dy in range(-r, r + 1):
            if dx * dx + dy * dy <= r * r + 1:
                out.blit(edge, (pad + dx, pad + dy))
    out.blit(fill, (pad, pad))
    bevel = m.copy()                             # light catching the top edges of the letters
    bevel.fill((255, 255, 255, 90), special_flags=pygame.BLEND_RGBA_MULT)
    bevel.blit(m, (0, max(1, size // 40)), special_flags=pygame.BLEND_RGBA_SUB)
    out.blit(bevel, (pad, pad))
    return out


__all__ = [n for n in dir() if n.isupper()] + ["bar", "border", "set_alert", "dim", "font", "health_color", "mix", "panel",
                                                "render", "text", "text_width", "title_art"]
