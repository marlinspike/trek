"""Immediate-mode widgets: panels register hotspots while drawing; clicks hit last frame's hotspots."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import partial
from typing import Callable

import pygame

from . import theme
from . import gfx


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
               size: int = 12, right: Callable[[], object] | None = None, face: str | None = None) -> None:
        hover = rect.collidepoint(self.mouse) and enabled
        bg = theme.BG_PANEL_HI if hover else theme.BG_INPUT
        if active:
            bg = theme.mix(theme.BG_INPUT, accent, 0.28)
        gfx.draw.rect(surf, bg, rect, border_radius=3)
        gfx.draw.rect(surf, accent if (active or hover) and enabled else theme.BORDER, rect, 1, border_radius=3)
        col = theme.TEXT if enabled else theme.TEXT_FAINT
        # command labels in the display face; data (long, or a list of facts joined by ·) stays in the text face
        if face is None:
            face = "display" if len(label) <= 20 and "·" not in label else "ui"
        weight = "medium" if face == "ui" else "regular"
        theme.frame(surf, rect)
        room = rect.width - 8
        floor = max(9, size - 2)
        while size > floor and theme.text_width(label, size, face, weight) > room:   # a tight button: smaller words,
            size -= 1                                                                  # and only then cut short
        theme.text(surf, theme.fit(label, size, room, face, weight), rect.center, col, size, face,
                   weight=weight, anchor="center")
        if enabled:
            self.add(rect, action, tooltip, right)
        elif tooltip and rect.collidepoint(self.mouse):
            self.tooltip = tooltip

    def toggle(self, surf: pygame.Surface, at: tuple[int, int], on: bool, action: Callable[[], object],
               tooltip: str = "", enabled: bool = True, words: tuple[str, str] = ("On", "Off")) -> pygame.Rect:
        """A switch: a pill whose knob slides right and lights when on, with its state in words beside it."""
        track = pygame.Rect(at[0], at[1] + 5, 46, 24)
        hover = track.inflate(60, 8).collidepoint(self.mouse) and enabled
        lit = theme.GOOD if enabled else theme.dim(theme.GOOD, 0.5)
        bg = theme.mix(theme.BG_INPUT, lit, 0.45) if on else theme.BG_INPUT
        gfx.draw.rect(surf, bg, track, border_radius=12)
        gfx.draw.rect(surf, lit if on else (theme.BORDER_HI if hover else theme.BORDER), track, 1, border_radius=12)
        knob = (track.right - 12, track.centery) if on else (track.x + 12, track.centery)
        gfx.draw.aacircle(surf, theme.TEXT if enabled else theme.TEXT_FAINT, knob, 8)
        label = words[0] if on else words[1]
        theme.text(surf, label, (track.right + 12, track.y + 3), (theme.TEXT if on else theme.TEXT_DIM) if enabled
                   else theme.TEXT_FAINT, 14)
        area = pygame.Rect(track.x, at[1], 58 + theme.text_width(label, 14) + 10, 34)
        if enabled:
            self.add(area, action, tooltip)
        elif tooltip and area.collidepoint(self.mouse):
            self.tooltip = tooltip
        return area

    def choice(self, surf: pygame.Surface, at: tuple[int, int], options: list[tuple[str, str, str]], current: str,
               pick: Callable[[str], object], enabled: bool = True, size: int = 13, height: int = 34,
               min_width: int = 64, room: int | None = None) -> int:
        """A row of joined buttons, one lit: (value, label, tooltip) each. Returns the x after the row.

        With `room` (pixels) the row never runs past it: the buttons hug their words, then the words get smaller."""
        x, y = at
        pad = 28

        def span() -> int:
            return sum(max(min_width, theme.text_width(lb, size, "display") + pad) + 4 for _, lb, _ in options) - 4

        if room is not None:
            if span() > room:
                min_width, pad = 0, 18
            while span() > room and size > 10:
                size -= 1
        for value, label, tip in options:
            w = max(min_width, theme.text_width(label, size, "display") + pad)
            self.button(surf, pygame.Rect(x, y, w, height), label, partial(pick, value), tip,
                        active=value == current, enabled=enabled, size=size, face="display")
            x += w + 4
        return x

    def slider(self, surf: pygame.Surface, rect: pygame.Rect, frac: float, enabled: bool = True,
               accent: theme.Color = theme.FRIEND) -> pygame.Rect:
        """A level from 0 to 1: a thin rail, filled to the knob. Returns where it listens (the caller drags it)."""
        frac = max(0.0, min(1.0, frac))
        rail = pygame.Rect(rect.x, rect.centery - 2, rect.width, 4)
        col = accent if enabled else theme.TEXT_FAINT
        gfx.draw.rect(surf, theme.BG_INPUT, rail, border_radius=2)
        gfx.draw.rect(surf, theme.BORDER, rail, 1, border_radius=2)
        gfx.draw.rect(surf, theme.dim(col, 0.8), pygame.Rect(rail.x, rail.y, int(rail.width * frac), rail.height),
                      border_radius=2)
        knob = (rail.x + int(rail.width * frac), rail.centery)
        hover = rect.inflate(0, 8).collidepoint(self.mouse) and enabled
        gfx.draw.aacircle(surf, theme.BG_PANEL_HI, knob, 9)
        gfx.draw.aacircle(surf, col if hover else theme.dim(col, 0.85), knob, 9, 2)
        return rect.inflate(18, 8)

    def draw_tooltip(self, surf: pygame.Surface) -> None:
        if not self.tooltip:
            return
        lines = theme.wrap(self.tooltip, 12, min(520, surf.get_width() - 24))      # a long tip wraps, never runs off
        w = max(theme.text_width(ln, 12) for ln in lines) + 16
        h = 6 + 18 * len(lines)
        x = max(4, min(self.mouse[0] + 14, surf.get_width() - w - 4))
        y = self.mouse[1] + 18
        if y + h + 2 > surf.get_height():
            y = max(4, self.mouse[1] - h - 6)
        r = pygame.Rect(x, y, w, h)
        theme.frame(surf, r)
        gfx.draw.rect(surf, theme.BG_PANEL_HI, r, border_radius=3)
        gfx.draw.rect(surf, theme.BORDER_HI, r, 1, border_radius=3)
        for i, ln in enumerate(lines):
            theme.text(surf, ln, (r.x + 8, r.y + 4 + 18 * i), theme.TEXT, 12)


@dataclass
class TextField:
    """A line of text the captain types: click to edit, Enter (or a click elsewhere) keeps it, Esc puts it back.

    The screen owns the fields and passes them keys while one is focused; `commit` saves the text and returns
    what is wrong with it, if anything, shown under the field (the text stays as typed so it can be fixed)."""

    value: str = ""
    placeholder: str = ""
    commit: Callable[[str], str | None] = lambda _text: None
    draft: str = ""
    focused: bool = False
    error: str = ""
    rect: pygame.Rect = field(default_factory=lambda: pygame.Rect(0, 0, 0, 0))
    born: float = 0.0           # when it was focused: the caret blinks from then
    prefill: bool = False       # an empty field starts from its placeholder (the shipped words), to edit rather than retype

    def focus(self, now: float = 0.0) -> None:
        if not self.focused:
            start = self.value or (self.placeholder if self.prefill else "")
            self.focused, self.draft, self.born = True, start, now

    def done(self) -> None:
        """Keep what was typed (Enter, Tab or a click elsewhere)."""
        if not self.focused:
            return
        self.focused = False
        text = " ".join(self.draft.split())
        if self.prefill and not self.value and text == " ".join(self.placeholder.split()):
            return                  # opened and closed again: the shipped words stay the shipped words
        if text == self.value and not self.error:
            return
        problem = self.commit(text)
        self.value = text
        self.error = problem or ""

    def cancel(self) -> None:
        self.focused, self.draft = False, self.value

    def key(self, ev: pygame.event.Event) -> None:
        if ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_TAB):
            self.done()
        elif ev.key == pygame.K_ESCAPE:
            self.cancel()
        elif ev.key == pygame.K_BACKSPACE:
            if ev.mod & (pygame.KMOD_CTRL | pygame.KMOD_META | pygame.KMOD_ALT):
                self.draft = self.draft.rstrip().rsplit(" ", 1)[0] if " " in self.draft.strip() else ""
            else:
                self.draft = self.draft[:-1]
        elif ev.key == pygame.K_v and ev.mod & (pygame.KMOD_CTRL | pygame.KMOD_META):
            self.draft += _clipboard()

    def text(self, s: str) -> None:
        self.draft += s.replace("\n", " ")

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, ui: UI, tooltip: str = "", now: float = 0.0,
             enabled: bool = True, mono: bool = False) -> None:
        self.rect = rect
        hover = rect.collidepoint(ui.mouse) and enabled
        gfx.draw.rect(surf, theme.BG_INPUT, rect, border_radius=3)
        edge = (theme.ALERT if self.error else theme.FRIEND if self.focused else theme.BORDER_HI if hover
                else theme.BORDER)
        gfx.draw.rect(surf, edge, rect, 1, border_radius=3)
        shown = self.draft if self.focused else self.value
        face = "mono" if mono else "ui"
        size = 13 if mono else 14
        inner = rect.width - 24
        while shown and theme.text_width(shown, size, face) > inner:     # the end of a long line, where you type
            shown = shown[1:] if self.focused else shown[:-2] + "…"
            if not self.focused and shown == "…":
                break
        y = rect.centery - size // 2 - 2
        if shown:
            theme.text(surf, shown, (rect.x + 10, y), theme.TEXT if enabled else theme.TEXT_FAINT, size, face)
        elif self.placeholder:
            theme.text(surf, theme.fit(self.placeholder, size, inner, face), (rect.x + 10, y), theme.TEXT_FAINT, size,
                       face)
        if self.focused and int((now - self.born) * 2) % 2 == 0:
            cx = rect.x + 11 + (theme.text_width(shown, size, face) if shown else 0)
            gfx.draw.line(surf, theme.FRIEND, (cx, rect.y + 7), (cx, rect.bottom - 8), 1)
        if enabled:
            ui.add(rect, partial(self.focus, now), tooltip)


def _clipboard() -> str:
    """Text on the clipboard (for pasting an address or a model name), or nothing."""
    try:
        get = getattr(pygame.scrap, "get_text", None)
        if get is not None:
            return " ".join(str(get() or "").split())
    except pygame.error:
        pass
    return ""


__all__ = ["Hotspot", "TextField", "UI"]
