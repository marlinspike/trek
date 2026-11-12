"""Officers' voices as subtitles, low on the map [E].

One voice at a time: a line shows for as long as it takes to read, bright for
its first moment and then settling to a calm tone, while the next waits its
turn. Urgent lines (a warning, a refusal) go to the front and cut the current
one short. Routine chatter that is still waiting when three more lines queue up
behind it is dropped: the log keeps every word, the subtitle only what is
current.

The box keeps clear of our ship and her target: if either sits where it would
be drawn, it moves to the top of the map instead.

Each officer's line carries the mark of their station, the same marks the
command wheel and the orders on the map use:
helm a chevron, tactical a diamond, engineering a hexagon, science a ring.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from . import theme
from . import gfx

STATION_COLOR: dict[str, theme.Color] = {
    "helm": theme.ALLY, "tactical": theme.PHASER, "engineering": theme.GOOD, "science": theme.CREW,
}
BRIGHT = 1.5        # seconds a new line is bright before it settles
FADE_IN, FADE_OUT = 0.15, 0.4
MAX_WAITING = 3     # routine lines beyond this many waiting are dropped (the log has them)


def read_time(text: str) -> float:
    """Seconds to show a line: long enough to read at a glance, never lingering."""
    return max(2.2, min(6.0, 1.4 + 0.045 * len(text)))


@dataclass
class Subtitle:
    speaker: str                   # "Worf"; "" for the ship's computer
    text: str
    color: theme.Color
    station: str | None = None
    officer: str | None = None     # officer id, so the activity panel can light their block
    urgent: bool = False
    shown: float = 0.0
    life: float = 0.0

    def __post_init__(self) -> None:
        if not self.life:
            self.life = read_time(self.text)


class Subtitles:
    def __init__(self) -> None:
        self.current: Subtitle | None = None
        self.waiting: list[Subtitle] = []

    def say(self, speaker: str, text: str, color: theme.Color, station: str | None = None,
            officer: str | None = None, urgent: bool = False) -> None:
        s = Subtitle(speaker, text, color, station, officer, urgent)
        if self.current is not None and self.current.text == text and self.current.speaker == speaker:
            return
        if urgent:
            self.waiting.insert(0, s)
            if self.current is not None and not self.current.urgent:
                self.current.life = min(self.current.life, self.current.shown + 0.25)
        else:
            self.waiting.append(s)
        while len(self.waiting) > MAX_WAITING:
            routine = [w for w in self.waiting if not w.urgent]
            if not routine:
                break
            self.waiting.remove(routine[0])

    def clear(self) -> None:
        self.current = None
        self.waiting.clear()

    def update(self, dt: float) -> None:
        if self.current is not None:
            self.current.shown += dt
            if self.current.shown >= self.current.life:
                self.current = None
        if self.current is None and self.waiting:
            self.current = self.waiting.pop(0)

    @property
    def speaking(self) -> str | None:
        """The officer whose line is showing (their id), if any."""
        return self.current.officer if self.current is not None else None

    def draw(self, surf: pygame.Surface, area: pygame.Rect, keep_clear: list[tuple[float, float]]) -> pygame.Rect | None:
        s = self.current
        if s is None:
            return None
        k_in = min(1.0, s.shown / FADE_IN)
        k_out = min(1.0, max(0.0, (s.life - s.shown) / FADE_OUT))
        alpha = min(k_in, k_out)
        if alpha <= 0.01:
            return None
        bright = max(0.0, 1.0 - s.shown / BRIGHT)
        size = 15
        name = s.speaker.upper()
        name_w = theme.text_width(name, 11, weight="semibold") + 14 if name else 0
        mark_w = 20 if s.station else 0
        max_w = min(760, int(area.width * 0.72))
        lines = wrap(s.text, size, max_w - name_w - mark_w - 32)
        h = 18 + 21 * len(lines)
        w = max(theme.text_width(t, size) for t in lines) + name_w + mark_w + 32
        box = pygame.Rect(0, 0, w, h)
        box.midbottom = (area.centerx, area.bottom - 18)
        if any(box.inflate(24, 24).collidepoint(p) for p in keep_clear):
            box.midtop = (area.centerx, area.y + 84)
        glass = gfx.Surface(box.size, pygame.SRCALPHA)
        glass.fill((*theme.BG_PANEL, int(214 * alpha)))
        surf.blit(glass, box)
        edge = theme.mix(theme.dim(s.color, 0.45), s.color, bright)
        gfx.draw.rect(surf, theme.mix(theme.BG, edge, alpha), box, 1, border_radius=6)
        x = box.x + 14
        cy = box.y + 9 + 10
        if s.station:
            station_mark(surf, s.station, (x + 6, cy), 6, theme.mix(theme.BG, STATION_COLOR.get(s.station, s.color), alpha))
            x += mark_w
        if name:
            theme.text(surf, name, (x, cy - 7), theme.mix(theme.BG, s.color, alpha), 11, weight="semibold")
            x += name_w
        body = theme.mix(theme.TEXT_DIM, theme.TEXT, 0.55 + 0.45 * bright) if s.speaker else \
            theme.mix(theme.dim(s.color, 0.8), s.color, bright)
        for i, t in enumerate(lines):
            theme.text(surf, t, (x, box.y + 9 + i * 21), theme.mix(theme.BG, body, alpha), size)
        return box


def wrap(text: str, size: int, width: int) -> list[str]:
    """At most two lines; the second ends with an ellipsis if the words run on."""
    words = text.split()
    lines: list[str] = []
    cur = ""
    for wd in words:
        nxt = f"{cur} {wd}".strip()
        if theme.text_width(nxt, size) <= width or not cur:
            cur = nxt
        else:
            lines.append(cur)
            cur = wd
    if cur:
        lines.append(cur)
    if len(lines) > 2:
        last = " ".join(lines[1:])
        while last and theme.text_width(last + "…", size) > width:
            last = last[:-1]
        lines = [lines[0], last.rstrip() + "…"]
    return lines or [""]


def station_mark(surf: pygame.Surface, station: str, c: tuple[float, float], r: float, col: theme.Color) -> None:
    """Helm a chevron, tactical a diamond, engineering a hexagon, science a ring."""
    x, y = c
    if station == "helm":
        pts = [(x - r, y + r * 0.6), (x, y - r * 0.7), (x + r, y + r * 0.6)]
        gfx.draw.lines(surf, col, False, pts, 2)
    elif station == "tactical":
        gfx.draw.polygon(surf, col, [(x, y - r), (x + r, y), (x, y + r), (x - r, y)], 2)
    elif station == "engineering":
        pts = [(x + r * math.cos(math.radians(60 * k + 30)), y + r * math.sin(math.radians(60 * k + 30))) for k in range(6)]
        gfx.draw.polygon(surf, col, pts, 2)
    else:
        gfx.draw.circle(surf, col, (int(x), int(y)), int(r), 2)


__all__ = ["STATION_COLOR", "Subtitle", "Subtitles", "read_time", "station_mark", "wrap"]
