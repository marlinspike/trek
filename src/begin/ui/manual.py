"""The in-game manual: a topic browser over the Markdown help library.

Left: a search box and the topics by category. Right: the page, rendered
from Markdown, with live blocks (weapon tables, the coach) filled in from
the game data and the current battle. Links jump between topics; example
commands can be clicked to put them in the console.

Typing searches, Enter opens the best match, Backspace goes back, the wheel
and arrow keys scroll, and Esc closes.
"""

from __future__ import annotations

import re
from functools import partial
from typing import Callable

import pygame

from ..help.coach import HelpContext, expand
from ..help.docs import HelpLibrary, Topic, library
from . import markdown, theme
from .widgets import UI

SIDEBAR_W = 270
HEADER_H = 54
CONTENT_MAX = 900


class ManualView:
    def __init__(self, context: Callable[[], HelpContext], on_try: Callable[[str], None],
                 on_close: Callable[[], None], lib: HelpLibrary | None = None) -> None:
        self.lib = lib or library()
        self.context = context
        self.on_try = on_try
        self.on_close = on_close
        self.topic_id = "index"
        self.history: list[str] = []
        self.scroll = 0.0
        self.side_scroll = 0.0
        self.search = ""
        self._cache: tuple[str, int, str] | None = None
        self._layout: markdown.Layout | None = None
        self._expanded_at = -1
        self.content_rect = pygame.Rect(0, 0, 0, 0)
        self.side_rect = pygame.Rect(0, 0, 0, 0)
        self.view_h = 0

    # ------------------------------------------------------------ navigation

    @property
    def topic(self) -> Topic | None:
        return self.lib.topics.get(self.topic_id) or self.lib.topics.get("index")

    def open(self, query: str | None = None) -> str | None:
        """Show a topic for `help <query>`; returns a message when nothing matched (the index opens instead)."""
        self.lib.refresh()
        self.search = ""
        if not query:
            self.go("index", remember=False)
            return None
        t = self.lib.resolve(query)
        if t is None:
            self.search = query
            self.go("index", remember=False)
            return f"No help page for '{query}'. Showing search results."
        self.go(t.id, remember=False)
        return None

    def go(self, tid: str, remember: bool = True) -> None:
        if tid not in self.lib.topics:
            t = self.lib.resolve(tid)
            if t is None:
                return
            tid = t.id
        if remember and tid != self.topic_id:
            self.history.append(self.topic_id)
            del self.history[:-40]
        self.topic_id = tid
        self.scroll = 0.0
        self._cache = None

    def _pick(self, tid: str) -> None:
        self.go(tid)
        self.search = ""

    def back(self) -> None:
        if self.history:
            self.topic_id = self.history.pop()
            self.scroll = 0.0
            self._cache = None

    # ------------------------------------------------------------ input

    def key(self, ev: pygame.event.Event) -> None:
        k = ev.key
        if k == pygame.K_ESCAPE:
            if self.search:
                self.search = ""
            else:
                self.on_close()
        elif k == pygame.K_BACKSPACE:
            if self.search:
                self.search = self.search[:-1]
            else:
                self.back()
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER) and self.search:
            hits = self.lib.search(self.search)
            if hits:
                self.go(hits[0].id)
                self.search = ""
        elif k == pygame.K_DOWN:
            self.wheel(-2)
        elif k == pygame.K_UP:
            self.wheel(2)
        elif k == pygame.K_PAGEDOWN or (k == pygame.K_SPACE and not self.search):
            self.scroll += self.view_h * 0.85
        elif k == pygame.K_PAGEUP:
            self.scroll -= self.view_h * 0.85
        elif k == pygame.K_HOME:
            self.scroll = 0
        elif k == pygame.K_END:
            self.scroll = 1e9
        elif k in (pygame.K_F1,):
            self.on_close()

    def text(self, s: str) -> None:
        if s == " " and not self.search:
            return
        self.search += s

    def wheel(self, dy: int, pos: tuple[int, int] | None = None) -> None:
        if pos is not None and self.side_rect.collidepoint(pos):
            self.side_scroll = max(0.0, self.side_scroll - dy * 40)
        else:
            self.scroll -= dy * 48

    # ------------------------------------------------------------ drawing

    def _page_text(self, t: Topic, ctx: HelpContext) -> str:
        body = expand(t.body, ctx)

        def titled(m: re.Match[str]) -> str:  # a bare [[id]] link shows the page's title
            other = self.lib.topics.get(m.group(1))
            return f"[[{m.group(1)}|{other.title}]]" if other is not None else m.group(0)

        body = re.sub(r"\[\[([^\]|]+)\]\]", titled, body)
        if t.see:
            links = []
            for s in t.see:
                other = self.lib.topics.get(s) or self.lib.resolve(s)
                if other is not None:
                    links.append(f"[[{other.id}|{other.title}]]")
            if links:
                body += "\n\n---\n**See also:** " + " · ".join(links)
        return body

    def _get_layout(self, t: Topic, width: int) -> markdown.Layout:
        live = "{{" in t.body
        now = pygame.time.get_ticks()
        if self._cache is not None and self._cache[0] == t.id and self._cache[1] == width and \
                not (live and now - self._expanded_at > 500):
            assert self._layout is not None
            return self._layout
        text = self._page_text(t, self.context())
        self._expanded_at = now
        if self._cache is None or self._cache != (t.id, width, text) or self._layout is None:
            self._layout = markdown.layout(markdown.parse(text), width)
            self._cache = (t.id, width, text)
        return self._layout

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, ui: UI) -> None:
        self.lib.refresh()
        shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        shade.fill((2, 5, 12, 200))
        surf.blit(shade, (0, 0))
        pygame.draw.rect(surf, theme.BG, rect, border_radius=8)
        pygame.draw.rect(surf, theme.BORDER_HI, rect, 1, border_radius=8)
        ui.add(rect, lambda: None)  # swallow clicks inside the window
        t = self.topic
        self._header(surf, rect, ui, t)
        body = pygame.Rect(rect.x, rect.y + HEADER_H, rect.width, rect.height - HEADER_H - 28)
        self.side_rect = pygame.Rect(body.x, body.y, SIDEBAR_W, body.height)
        self._sidebar(surf, self.side_rect, ui)
        content = pygame.Rect(self.side_rect.right + 1, body.y, body.right - self.side_rect.right - 1, body.height)
        self.content_rect = content
        if t is not None:
            self._content(surf, content, ui, t)
        theme.text(surf, "Type to search · Enter opens · Backspace goes back · click a › example to put it in the console · Esc closes",
                   (rect.x + 16, rect.bottom - 21), theme.TEXT_FAINT, 11)
        edit = str(t.path) if t is not None and t.path is not None else ""
        if edit:
            theme.text(surf, f"Page source: {edit}", (rect.right - 16, rect.bottom - 21), theme.TEXT_FAINT, 10, "mono",
                       anchor="topright")

    def _header(self, surf: pygame.Surface, rect: pygame.Rect, ui: UI, t: Topic | None) -> None:
        h = pygame.Rect(rect.x, rect.y, rect.width, HEADER_H)
        pygame.draw.rect(surf, theme.BG_PANEL, h, border_top_left_radius=8, border_top_right_radius=8)
        pygame.draw.line(surf, theme.BORDER, (h.x, h.bottom), (h.right, h.bottom))
        pygame.draw.line(surf, theme.FRIEND, (h.x + 18, h.y + 1), (h.x + 60, h.y + 1), 2)
        theme.text(surf, "BEGIN MANUAL", (h.x + 18, h.y + 18), theme.TEXT, 15, weight="semibold")
        if t is not None:
            crumb = f"{t.category}  ›  {t.title}"
            theme.text(surf, crumb, (h.x + SIDEBAR_W + 32, h.y + 19), theme.TEXT_DIM, 13)
        bx = h.right - 16
        for label, act, tip, enabled in (("×  Close", self.on_close, "Esc", True),
                                         ("‹  Back", self.back, "Backspace", bool(self.history)),
                                         ("Coach", lambda: self.go("coach"), "Advice for the situation you're in", True),
                                         ("Contents", lambda: self.go("index"), "All topics", True)):
            w = theme.text_width(label, 12, weight="medium") + 26
            bx -= w
            ui.button(surf, pygame.Rect(bx, h.y + 13, w, 28), label, act, tip, enabled=enabled,
                      accent=theme.GOOD if label == "Coach" else theme.FRIEND)
            bx -= 8

    def _sidebar(self, surf: pygame.Surface, r: pygame.Rect, ui: UI) -> None:
        pygame.draw.rect(surf, theme.BG_PANEL, r, border_bottom_left_radius=8)
        pygame.draw.line(surf, theme.BORDER, (r.right, r.y), (r.right, r.bottom))
        sb = pygame.Rect(r.x + 14, r.y + 14, r.width - 28, 32)
        pygame.draw.rect(surf, theme.BG_INPUT, sb, border_radius=4)
        pygame.draw.rect(surf, theme.FRIEND if self.search else theme.BORDER, sb, 1, border_radius=4)
        caret = "▏" if (pygame.time.get_ticks() // 500) % 2 == 0 else ""
        if self.search:
            theme.text(surf, self.search + caret, (sb.x + 30, sb.y + 8), theme.TEXT, 13)
        else:
            theme.text(surf, "Search the manual…", (sb.x + 30, sb.y + 8), theme.TEXT_FAINT, 13)
        pygame.draw.circle(surf, theme.TEXT_DIM, (sb.x + 15, sb.y + 15), 5, 1)
        pygame.draw.line(surf, theme.TEXT_DIM, (sb.x + 19, sb.y + 19), (sb.x + 22, sb.y + 22), 2)

        lst = pygame.Rect(r.x, sb.bottom + 10, r.width, r.bottom - sb.bottom - 14)
        prev = surf.get_clip()
        surf.set_clip(lst)
        y = lst.y - int(self.side_scroll)
        if self.search:
            hits = self.lib.search(self.search)
            theme.text(surf, f"{len(hits)} RESULT{'S' if len(hits) != 1 else ''}", (r.x + 18, y + 4), theme.TEXT_FAINT, 10,
                       weight="semibold")
            y += 24
            for t in hits:
                y = self._side_item(surf, ui, lst, t, y, show_summary=True)
        else:
            for cat, topics in self.lib.categories():
                theme.text(surf, cat.upper(), (r.x + 18, y + 8), theme.TEXT_FAINT, 10, weight="semibold")
                y += 28
                for t in topics:
                    y = self._side_item(surf, ui, lst, t, y)
                y += 6
        surf.set_clip(prev)
        total = y + int(self.side_scroll) - lst.y
        self.side_scroll = max(0.0, min(self.side_scroll, max(0, total - lst.height)))

    def _side_item(self, surf: pygame.Surface, ui: UI, clip: pygame.Rect, t: Topic, y: int,
                   show_summary: bool = False) -> int:
        h = 40 if show_summary and t.summary else 26
        row = pygame.Rect(clip.x + 8, y, clip.width - 16, h)
        if row.bottom > clip.top and row.top < clip.bottom:
            current = t.id == self.topic_id
            hover = row.collidepoint(ui.mouse) and clip.collidepoint(ui.mouse)
            if current or hover:
                pygame.draw.rect(surf, theme.mix(theme.BG_PANEL, theme.FRIEND, 0.18 if current else 0.08), row, border_radius=4)
            if current:
                pygame.draw.rect(surf, theme.FRIEND, pygame.Rect(row.x, row.y + 5, 3, row.height - 10))
            theme.text(surf, t.title, (row.x + 14, row.y + 5), theme.TEXT if current else theme.TEXT_DIM, 13,
                       weight="medium" if current else "regular")
            if show_summary and t.summary:
                s = t.summary if theme.text_width(t.summary, 11) < row.width - 24 else t.summary[:38] + "…"
                theme.text(surf, s, (row.x + 14, row.y + 22), theme.TEXT_FAINT, 11)
            vis = row.clip(clip)
            if vis.height > 0:
                ui.add(vis, partial(self._pick, t.id))
        return y + h + 2

    def _content(self, surf: pygame.Surface, r: pygame.Rect, ui: UI, t: Topic) -> None:
        pad = 36
        width = min(CONTENT_MAX, r.width - pad * 2 - 14)
        lay = self._get_layout(t, width)
        title_h = 74 if t.summary else 52
        self.view_h = r.height
        total = title_h + lay.height + 40
        self.scroll = max(0.0, min(self.scroll, max(0, total - r.height)))
        y0 = r.y + 24 - int(self.scroll)
        prev = surf.get_clip()
        surf.set_clip(r)
        theme.text(surf, t.title, (r.x + pad, y0), theme.TEXT, 28, weight="semibold")
        if t.summary:
            theme.text(surf, t.summary, (r.x + pad, y0 + 40), theme.TEXT_DIM, 14)
        surf.set_clip(prev)
        origin = (r.x + pad, y0 + title_h)
        markdown.draw(surf, lay, origin, r)
        for hot in lay.hots:
            hr = hot.rect.move(origin).clip(r)
            if hr.height <= 0:
                continue
            if hot.kind == "link":
                ui.add(hr, partial(self.go, hot.value))
            else:
                if hr.collidepoint(ui.mouse):
                    pygame.draw.rect(surf, theme.FRIEND, hr, 1, border_radius=3)
                    theme.text(surf, "put in console ›", (hr.right - 10, hr.y + 4), theme.FRIEND, 11, anchor="topright")
                ui.add(hr, partial(self.on_try, hot.value), "Put this command in the console")
        if total > r.height:  # scrollbar
            track = pygame.Rect(r.right - 8, r.y + 6, 4, r.height - 12)
            pygame.draw.rect(surf, theme.BG_PANEL_HI, track, border_radius=2)
            th = max(30, int(track.height * r.height / total))
            ty = track.y + int((track.height - th) * (self.scroll / max(1, total - r.height)))
            pygame.draw.rect(surf, theme.BORDER_HI, pygame.Rect(track.x, ty, 4, th), border_radius=2)


__all__ = ["ManualView"]
