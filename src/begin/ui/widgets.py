"""Immediate-mode widgets: panels register hotspots while drawing; clicks hit last frame's hotspots."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

import pygame

from . import theme


@dataclass
class Hotspot:
    rect: pygame.Rect
    action: Callable[[], object]
    tooltip: str = ""
    right: Callable[[], object] | None = None
    wheel: Callable[[int], None] | None = None


@dataclass
class UI:
    hotspots: list[Hotspot] = field(default_factory=list)
    mouse: tuple[int, int] = (0, 0)
    tooltip: str = ""

    def begin_frame(self) -> None:
        self.hotspots = []
        self.tooltip = ""

    def add(self, rect: pygame.Rect, action: Callable[[], object], tooltip: str = "",
            right: Callable[[], object] | None = None, wheel: Callable[[int], None] | None = None) -> None:
        self.hotspots.append(Hotspot(rect, action, tooltip, right, wheel))
        if tooltip and rect.collidepoint(self.mouse):
            self.tooltip = tooltip

    def hit(self, pos: tuple[int, int]) -> Hotspot | None:
        for h in reversed(self.hotspots):
            if h.rect.collidepoint(pos):
                return h
        return None

    def button(self, surf: pygame.Surface, rect: pygame.Rect, label: str, action: Callable[[], object],
               tooltip: str = "", active: bool = False, enabled: bool = True, accent: theme.Color = theme.FRIEND,
               size: int = 12, right: Callable[[], object] | None = None) -> None:
        hover = rect.collidepoint(self.mouse) and enabled
        bg = theme.BG_PANEL_HI if hover else theme.BG_INPUT
        if active:
            bg = theme.mix(theme.BG_INPUT, accent, 0.28)
        pygame.draw.rect(surf, bg, rect, border_radius=3)
        pygame.draw.rect(surf, accent if (active or hover) and enabled else theme.BORDER, rect, 1, border_radius=3)
        col = theme.TEXT if enabled else theme.TEXT_FAINT
        # command labels in the display face; data (long, or a list of facts joined by ·) stays in the text face
        face = "display" if len(label) <= 20 and "·" not in label else "ui"
        theme.text(surf, label, rect.center, col, size, face, weight="medium" if face == "ui" else "regular",
                   anchor="center")
        if enabled:
            self.add(rect, action, tooltip, right)
        elif tooltip and rect.collidepoint(self.mouse):
            self.tooltip = tooltip

    def draw_tooltip(self, surf: pygame.Surface) -> None:
        if not self.tooltip:
            return
        w = theme.text_width(self.tooltip, 12) + 16
        x = min(self.mouse[0] + 14, surf.get_width() - w - 4)
        y = self.mouse[1] + 18
        if y + 24 > surf.get_height():
            y = self.mouse[1] - 28
        r = pygame.Rect(x, y, w, 22)
        pygame.draw.rect(surf, theme.BG_PANEL_HI, r, border_radius=3)
        pygame.draw.rect(surf, theme.BORDER_HI, r, 1, border_radius=3)
        theme.text(surf, self.tooltip, (r.x + 8, r.y + 4), theme.TEXT, 12)


__all__ = ["Hotspot", "UI"]
