"""The counsel panel and the mission card [E].

Counsel (O, or `counsel`): over the left of the map, each officer's way forward from here, rebuilt from the live
fight about once a cycle. **All in** (or keys 1 to 4) runs an officer's whole plan; a click on one step runs just
that step, so the captain can take a bit of each. Time keeps running unless the captain pauses.

The mission card: the goal, how it stands (people aboard, time left, distance to safety), and what is in the way.
The ward and the runner are marked on the map.
"""

from __future__ import annotations

import math
from functools import partial
from typing import TYPE_CHECKING, Callable

import pygame

from . import gfx, theme
from .widgets import UI

if TYPE_CHECKING:
    from ..crew.counsel import Plan
    from ..crew.situation import MissionView
    from .camera import Camera

STATION_ACCENT: dict[str, theme.Color] = {
    "tactical": (222, 128, 104),       # the sword
    "helm": (112, 168, 250),           # geometry and the mind
    "engineering": (230, 186, 96),     # keep her alive
    "science": (110, 214, 184),        # know, then strike
}
PANEL_W = 470
MISSION_W = 360
KIND_WORD = {"rescue": "RESCUE", "escort": "ESCORT", "intercept": "INTERCEPT"}


def counsel_rect(map_rect: pygame.Rect) -> pygame.Rect:
    w = min(PANEL_W, max(320, int(map_rect.width * 0.42)))
    return pygame.Rect(map_rect.x + 12, map_rect.y + 36, w, map_rect.height - 48)


def draw_counsel(surf: pygame.Surface, area: pygame.Rect, plans: list[Plan], ui: UI,
                 run_plan: Callable[[Plan], None], run_step: Callable[[Plan, str], None],
                 close: Callable[[], None], ran: dict[str, float], now: float, paused: bool, goal: str = "",
                 clear_goal: Callable[[], None] | None = None) -> pygame.Rect:
    """Draw the panel inside `area` (it takes only the height it needs). Returns the rect it covers."""
    inner = area.width - 28
    head_h, foot_h = (58 if goal else 34), 26
    most = 4
    while True:          # as many lines of each reason as the map has room for
        blocks = _blocks(plans, inner, most)
        heights = [22 + 20 + len(r) * 17 + 6 + len(rows) * 26 + 10 for _, r, rows in blocks]
        h = head_h + sum(heights) + max(0, len(blocks) - 1) * 8 + foot_h
        if h <= area.height or most <= 1:
            break
        most -= 1
    if not blocks:
        h = head_h + 44 + foot_h
    box = pygame.Rect(area.x, area.y, area.width, min(area.height, h))
    box = _draw(surf, box, blocks, heights, ui, run_plan, run_step, close, ran, now, paused, head_h, foot_h)
    if goal:
        g = pygame.Rect(box.x + 14, box.y + 32, box.width - 28, 20)
        gfx.draw.rect(surf, theme.mix(theme.BG_INPUT, theme.CREW, 0.18), g, border_radius=10)
        theme.text(surf, theme.fit(f"GOAL  ·  {goal}", 11, g.width - 40, weight="semibold"), (g.x + 10, g.y + 3),
                   theme.CREW, 11, weight="semibold")
        if clear_goal is not None:
            x = pygame.Rect(g.right - 22, g.y, 20, 20)
            theme.text(surf, "×", x.center, theme.TEXT_DIM, 13, anchor="center")
            ui.add(x, clear_goal, "Clear the goal: counsel for the whole fight")
    return box


def _blocks(plans: list[Plan], inner: int, most: int) -> list[tuple[Plan, list[str], list[list[tuple[str, int]]]]]:
    blocks: list[tuple[Plan, list[str], list[list[tuple[str, int]]]]] = []
    for p in plans:
        reason = theme.clip_lines(theme.wrap(p.reason, 12, inner - 8), most, 12, inner - 8)
        rows: list[list[tuple[str, int]]] = [[]]
        x = 0
        for st in p.steps:
            label = theme.fit(st.line, 11, inner - 30, "mono")
            w = theme.text_width(label, 11, "mono") + 18
            if rows[-1] and x + w > inner - 8:
                rows.append([])
                x = 0
            rows[-1].append((label, w))
            x += w + 6
        blocks.append((p, reason, rows))
    return blocks


def _draw(surf: pygame.Surface, box: pygame.Rect, blocks: list[tuple[Plan, list[str], list[list[tuple[str, int]]]]],
          heights: list[int], ui: UI, run_plan: Callable[[Plan], None], run_step: Callable[[Plan, str], None],
          close: Callable[[], None], ran: dict[str, float], now: float, paused: bool, head_h: int,
          foot_h: int) -> pygame.Rect:
    pad = 14
    inner = box.width - 2 * pad
    theme.shadow(surf, box, 6)
    panel = gfx.Surface(box.size, pygame.SRCALPHA)
    panel.fill((*theme.BG_PANEL, 236))
    surf.blit(panel, box)
    gfx.draw.rect(surf, theme.BORDER_HI, box, 1, border_radius=6)
    old_clip = surf.get_clip()
    surf.set_clip(box)
    theme.text(surf, "COUNSEL", (box.x + pad, box.y + 10), theme.CREW, 12, "display", weight="medium")
    sub = "each officer's way forward from here" + ("" if paused else "  ·  live")
    theme.text(surf, theme.fit(sub, 11, inner - 110), (box.x + pad + 80, box.y + 12), theme.TEXT_FAINT, 11)
    x_rect = pygame.Rect(box.right - 26, box.y + 6, 20, 20)
    theme.text(surf, "×", x_rect.center, theme.TEXT_DIM, 15, anchor="center")
    ui.add(x_rect, close, "Close the counsel (O)")
    y = box.y + head_h
    if not blocks:
        theme.text(surf, "Nothing to advise: no ship under command, or the fight is over.", (box.x + pad, y + 10),
                   theme.TEXT_DIM, 12)
    for i, ((p, reason, rows), bh) in enumerate(zip(blocks, heights)):
        if y + bh > box.bottom - foot_h + 4:
            theme.text(surf, f"{len(blocks) - i} more: make the window taller to see them", (box.x + pad, y + 4),
                       theme.TEXT_FAINT, 11)
            break
        acc = STATION_ACCENT.get(p.station, theme.CREW)
        card = pygame.Rect(box.x + 8, y, box.width - 16, bh)
        gfx.draw.rect(surf, theme.BG_PANEL_HI, card, border_radius=5)
        gfx.draw.rect(surf, theme.dim(acc, 0.45), card, 1, border_radius=5)
        gfx.draw.line(surf, acc, (card.x + 1, card.y + 6), (card.x + 1, card.bottom - 7), 3)
        # who, and the perspective
        tag = f"{i + 1}  {p.name.upper()}  ·  {p.perspective.upper()}"
        theme.text(surf, theme.fit(tag, 10, inner - 96, weight="semibold"), (card.x + 12, card.y + 7), acc, 10,
                   weight="semibold")
        allin = pygame.Rect(card.right - 82, card.y + 5, 74, 20)
        ui.button(surf, allin, f"All in  {i + 1}", partial(run_plan, p), f"Run all of {p.name}'s plan", accent=acc,
                  size=11)
        theme.text(surf, theme.fit(p.title, 15, inner - 20, weight="medium"), (card.x + 12, card.y + 24), theme.TEXT,
                   15, weight="medium")
        ry = card.y + 46
        for ln in reason:
            theme.text(surf, ln, (card.x + 12, ry), theme.TEXT_DIM, 12)
            ry += 17
        ry += 6
        steps = iter(p.steps)
        for row in rows:
            x = card.x + 12
            for label, w in row:
                st = next(steps)
                chip = pygame.Rect(x, ry, w, 21)
                done = now - ran.get(st.line, -99.0) < 2.5
                hover = chip.collidepoint(ui.mouse)
                bg = theme.mix(theme.BG_INPUT, acc, 0.3 if done else (0.16 if hover else 0.0))
                gfx.draw.rect(surf, bg, chip, border_radius=4)
                gfx.draw.rect(surf, acc if hover or done else theme.BORDER, chip, 1, border_radius=4)
                theme.text(surf, label, (chip.x + 9, chip.y + 4), theme.TEXT if not done else acc, 11, "mono")
                ui.add(chip, partial(run_step, p, st.line), f"{st.label}: run just this step")
                x += w + 6
            ry += 26
        y += bh + 8
    foot = "O closes  ·  1–4 all in  ·  click a step to run it  ·  'counsel <goal>' aims it"
    theme.text(surf, theme.fit(foot, 11, inner), (box.x + pad, box.bottom - 20), theme.TEXT_FAINT, 11)
    surf.set_clip(old_clip)
    return box


# ------------------------------------------------------------------ the mission

def _bar(surf: pygame.Surface, r: pygame.Rect, frac: float, col: theme.Color) -> None:
    gfx.draw.rect(surf, theme.BG_INPUT, r, border_radius=3)
    if frac > 0:
        gfx.draw.rect(surf, col, pygame.Rect(r.x, r.y, max(4, int(r.width * min(1.0, frac))), r.height), border_radius=3)


def mission_lines(m: MissionView) -> tuple[str, str, theme.Color, float | None]:
    """The card's two lines (how it stands, what to do or what happened), its colour, and a progress fraction."""
    if m.state == "done":
        return ("Mission accomplished.", _done_line(m), theme.GOOD, 1.0 if m.kind != "rescue" else
                (m.saved / m.people if m.people else 1.0))
    if m.state == "failed":
        return ("Mission failed.", _done_line(m), theme.ALERT, m.saved / m.people if m.kind == "rescue" and m.people
                else None)
    if m.kind == "rescue":
        left = f"  ·  {m.time_left:.0f} cycles left" if m.time_left is not None else ""
        stand = f"{m.saved} of {m.people} safe, {m.aboard} aboard{left}"
        if m.beaming:
            hint, col = "Transporters working.", theme.GOOD
        elif m.blocked == "shield":
            hint, col = "In range: lower the shield facing her to beam.", theme.CAUTION
        elif m.ward_id is None:
            hint, col = "", theme.TEXT_DIM
        else:
            hint, col = f"Get within 3,000 of her ({m.ward_range:,.0f} now) and lower the shield facing her.", theme.TEXT_DIM
        if m.time_left is not None and m.time_left < 30:
            col = theme.ALERT
        return stand, hint, col, m.saved / m.people if m.people else None
    if m.kind == "escort":
        stand = f"{m.to_range:,.0f} from safety  ·  hull {m.ward_hull * 100:.0f}%"
        hunt = f"{len(m.hunter_ids)} ship{'s' if len(m.hunter_ids) != 1 else ''} hunting her" if m.hunter_ids else \
            "No one is hunting her now."
        return stand, hunt, theme.CAUTION if m.ward_hull < 0.5 else theme.TEXT_DIM, None
    esc = f"clear in about {m.runner_escape:.0f} cycles" if m.runner_escape is not None else "position unknown"
    return f"She is running: {esc}.", "Destroy, disable or take her before she reaches the edge.", theme.CAUTION, None


def _done_line(m: MissionView) -> str:
    if m.kind == "rescue" and m.people:
        return f"{m.saved} of {m.people} people safe."
    return ""


def draw_mission(surf: pygame.Surface, top_right: tuple[int, int], m: MissionView, now: float) -> pygame.Rect:
    """The mission card, its top right corner at `top_right`. Returns its rect."""
    pad = 12
    inner = MISSION_W - 2 * pad
    stand, hint, col, frac = mission_lines(m)
    h = 24 + 22 + 18 + (12 if frac is not None else 0) + (18 if hint else 0) + 8
    box = pygame.Rect(top_right[0] - MISSION_W, top_right[1], MISSION_W, h)
    theme.shadow(surf, box, 6)
    gfx.draw.rect(surf, theme.BG_PANEL_HI, box, border_radius=6)
    edge = col if m.state != "open" else theme.dim(theme.FRIEND, 0.7)
    if m.state == "open" and col == theme.ALERT:
        edge = theme.mix(theme.dim(theme.ALERT, 0.6), theme.ALERT, 0.5 + 0.5 * math.sin(now * math.tau / 1.2))
    gfx.draw.rect(surf, edge, box, 1, border_radius=6)
    gfx.draw.line(surf, theme.FRIEND, (box.x + 10, box.y + 1), (box.x + 46, box.y + 1), 2)
    state = {"open": "MISSION", "done": "MISSION · DONE", "failed": "MISSION · FAILED"}[m.state]
    theme.text(surf, f"{state}  ·  {KIND_WORD.get(m.kind, m.kind.upper())}", (box.x + pad, box.y + 6),
               theme.TEXT_DIM, 11, "display", weight="medium")
    y = box.y + 24
    theme.text(surf, theme.fit(m.title, 15, inner, weight="medium"), (box.x + pad, y), theme.TEXT, 15, weight="medium")
    y += 22
    theme.text(surf, theme.fit(stand, 12, inner), (box.x + pad, y), theme.TEXT if m.state == "open" else col, 12)
    y += 18
    if frac is not None:
        _bar(surf, pygame.Rect(box.x + pad, y, inner, 6), frac, theme.GOOD if m.state != "failed" else theme.ALERT)
        y += 12
    if hint:
        theme.text(surf, theme.fit(hint, 12, inner), (box.x + pad, y), col, 12)
    return box


def draw_marks(surf: pygame.Surface, cam: Camera, m: MissionView, poses: dict[int, tuple[float, float, float]],
               clip: pygame.Rect, now: float) -> None:
    """A ring and a word on the ward and the runner, so the captain can find the ship the mission is about."""
    if m.state != "open":
        return
    marks = []
    if m.ward_id is not None and m.ward_id in poses:
        marks.append((m.ward_id, "WARD" if m.kind == "escort" else "STRICKEN", theme.FRIEND))
    if m.runner_id is not None and m.runner_id in poses:
        marks.append((m.runner_id, "RUNNER", theme.CAUTION))
    old = surf.get_clip()
    surf.set_clip(clip)
    for sid, word, col in marks:
        x, y = cam.to_screen(poses[sid][0], poses[sid][1])
        r = 17 + 2 * math.sin(now * math.tau / 2.0)
        gfx.draw.circle(surf, theme.dim(col, 0.8), (int(x), int(y)), int(r), 1)
        theme.text(surf, word, (x, y - r - 14), col, 10, weight="semibold", anchor="midtop")
    if m.kind == "escort" and m.ward_id is not None:
        tx, ty = cam.to_screen(*m.to)
        if clip.collidepoint(tx, ty):
            gfx.draw.circle(surf, theme.dim(theme.GOOD, 0.7), (int(tx), int(ty)), 9, 1)
            theme.text(surf, "SAFETY", (tx, ty + 12), theme.dim(theme.GOOD, 0.9), 10, weight="semibold", anchor="midtop")
    surf.set_clip(old)


__all__ = ["STATION_ACCENT", "counsel_rect", "draw_counsel", "draw_marks", "draw_mission", "mission_lines"]
