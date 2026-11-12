"""The Orders tab: the captain's library of named orders and key macros, one card each [E].

A card shows the order's name, what it does (its note, or its steps), and the
key that runs it if one does. Click a card to run it; right-click to see every
step. While a recording is on, the tab shows it with Save and Discard; otherwise
"Record" starts one (or type `record <name>`). Key macros that aren't an order
(`key F5 fire all phasers 10`) are listed after the orders: they are orders too,
just bound to a key.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pygame

from . import theme
from .hud import Panel
from . import gfx

if TYPE_CHECKING:
    from .battle_scene import BattleScene

CARD_H = 34


def _fit(s: str, size: int, width: int, family: str = "ui") -> str:
    if theme.text_width(s, size, family) <= width:
        return s
    while s and theme.text_width(s + "…", size, family) > width:
        s = s[:-1]
    return s + "…"


def _runner(hud: BattleScene, line: str) -> Callable[[], object]:
    return lambda: hud.run_console(line)


def _shower(hud: BattleScene, name: str, steps: list[str]) -> Callable[[], object]:
    return lambda: hud._show([f"ORDER {name.upper()}"] + [f"  {i + 1}. {s}" for i, s in enumerate(steps)], None)


class OrdersPanel(Panel):
    title = "Orders"
    min_height = 120
    weight = 1.0

    def tab_label(self, hud: BattleScene) -> str:
        n = len(hud.session.named_orders())
        rec = hud.recording is not None
        return "Orders · rec" if rec else (f"Orders · {n}" if n else "Orders")

    def body(self, surf: pygame.Surface, rect: pygame.Rect, y: int, hud: BattleScene) -> None:
        x0, w = rect.x + 10, rect.width - 20
        rec = hud.recording
        if rec is not None:
            theme.text(surf, f"● Recording {rec.name} · {len(rec.steps)} order{'s' if len(rec.steps) != 1 else ''}",
                       (x0 + 2, y + 3), theme.ALERT, 12, weight="medium")
            hud.ui.button(surf, pygame.Rect(rect.right - 160, y, 70, 20), "Save", lambda: hud.run_console("record stop"),
                          "Save it as a named order", accent=theme.GOOD, size=11)
            hud.ui.button(surf, pygame.Rect(rect.right - 84, y, 72, 20), "Discard",
                          lambda: hud.run_console("record off"), "Throw the recording away", size=11)
        else:
            theme.text(surf, "Click to run · right-click for the steps", (x0 + 2, y + 3), theme.TEXT_FAINT, 11)
            hud.ui.button(surf, pygame.Rect(rect.right - 84, y, 72, 20), "● Record", lambda: hud.type_line("record "),
                          "Record the orders you give next as a named order", accent=theme.ALERT, size=11)
        y += 26
        keyed = {v.strip().lower().removeprefix("execute order ").strip(): k for k, v in hud.keys.items()}
        cards: list[tuple[str, str, str | None, str, list[str]]] = []
        for o in hud.session.named_orders().values():
            cards.append((o.name, o.note or o.summary(), keyed.get(o.name), o.name, [s.text for s in o.steps]))
        for k, v in sorted(hud.keys.items()):
            if v.strip().lower().removeprefix("execute order ").strip() in hud.session.named_orders():
                continue
            cards.append((k, v, None, v, [v]))
        if not cards:
            theme.para(surf, "No orders yet. Give a few orders after 'record <name>' and they're kept here.",
                       (x0 + 2, y + 4), rect.right - 14 - x0, theme.TEXT_DIM, 12, 18, bottom=rect.bottom - 4)
            return
        running = hud.session.running_order()
        for name, what, key, line, steps in cards:
            if y + CARD_H > rect.bottom - 4:
                theme.text(surf, "… more: type 'orders'", (x0 + 2, y + 2), theme.TEXT_FAINT, 11)
                break
            r = pygame.Rect(x0, y, w, CARD_H - 4)
            hover = r.collidepoint(hud.ui.mouse)
            live = running == name
            gfx.draw.rect(surf, theme.BG_PANEL_HI if hover or live else theme.BG_INPUT, r, border_radius=4)
            gfx.draw.rect(surf, theme.FRIEND if live else (theme.BORDER_HI if hover else theme.BORDER), r, 1,
                             border_radius=4)
            theme.text(surf, name, (r.x + 10, r.y + 7), theme.FRIEND, 13, "mono", weight="medium")
            nx = r.x + 10 + max(90, theme.text_width(name, 13, "mono") + 14)
            tail = 0
            if key:
                kw = theme.text_width(key, 11, "mono") + 12
                kr = pygame.Rect(r.right - kw - 8, r.y + 6, kw, 18)
                gfx.draw.rect(surf, theme.BG_INPUT, kr, border_radius=3)
                gfx.draw.rect(surf, theme.BORDER_HI, kr, 1, border_radius=3)
                theme.text(surf, key, kr.center, theme.TEXT_DIM, 11, "mono", anchor="center")
                tail = kw + 14
            theme.text(surf, _fit(what, 12, r.right - nx - tail - 8), (nx, r.y + 8), theme.TEXT_DIM, 12)
            hud.ui.add(r, _runner(hud, line), f"Run {name}", right=_shower(hud, name, steps))
            y += CARD_H


__all__ = ["OrdersPanel"]
