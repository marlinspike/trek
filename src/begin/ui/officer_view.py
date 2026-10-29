"""What the officers are doing, made visible [E].

Two pieces, both drawn by `BattleScene` while any officer is flying the ship
or working an objective:

- the activity panel, top left of the map: one block per officer with the job
  (conn, helm, or the objective), the current step in plain words, and how
  the job stands ("Wraith 3/6 shields out, weakest up 15%");
- intent on the map: the course the helm officer has chosen (amber while
  dodging torpedoes, with the torpedoes being dodged marked), the weapons
  officer's target bracketed and labelled with the system she is after, and
  the ring of bursts from her last salvo, which fades over a few seconds.
"""

from __future__ import annotations

import math
from collections.abc import Callable

import pygame

from ..crew.helm import incoming
from ..crew.officers import Activity
from ..sim.observation import Observation
from ..sim.ship import Ship
from . import theme
from .camera import Camera

PANEL_W = 470
AIM_FADE = 4.0          # seconds a salvo's ring stays on the map
HELM_SECONDS = 5.0      # how far ahead the helm officer's course is drawn

ROLE_WORDS = {"conn": "has the conn", "helm": "at the helm"}


def _fit(s: str, size: int, width: int) -> str:
    if theme.text_width(s, size) <= width:
        return s
    while s and theme.text_width(s + "…", size) > width:
        s = s[:-1]
    return s + "…"


def draw_panel(surf: pygame.Surface, top_left: tuple[int, int], acts: list[Activity],
               name_of: Callable[[str], str], tick: int, tpc: int) -> pygame.Rect | None:
    """The activity panel; returns the area it covers."""
    if not acts:
        return None
    x, y = top_left
    rows: list[tuple[str, theme.Color, int, str]] = []
    for a in acts:
        head = f"{name_of(a.officer_id).upper()}  ·  {ROLE_WORDS.get(a.role, a.role)}"
        rows.append((head, theme.CREW, 12, "semibold"))
        fresh = (tick - a.since) < 2 * tpc
        col = theme.CAUTION if a.kind == "evade" else (theme.TEXT if fresh else theme.TEXT_DIM)
        rows.append((a.doing, col, 13, "regular"))
        if a.progress:
            rows.append((a.progress, theme.TEXT_DIM, 12, "regular"))
    h = sum(size + 6 for _, _, size, _ in rows) + 12 + 6 * (len(acts) - 1)
    box = pygame.Rect(x, y, PANEL_W, h)
    pygame.draw.rect(surf, theme.BG_PANEL_HI, box, border_radius=4)
    pygame.draw.rect(surf, theme.dim(theme.CREW, 0.6), box, 1, border_radius=4)
    cy = y + 7
    for i, (s, col, size, weight) in enumerate(rows):
        if i and weight == "semibold":
            cy += 6
        theme.text(surf, _fit(s, size, PANEL_W - 20), (x + 10, cy), col, size, weight=weight)
        cy += size + 6
    return box


def draw_intent(surf: pygame.Surface, cam: Camera, obs: Observation, ship: Ship | None, acts: list[Activity],
                name_of: Callable[[str], str]) -> None:
    """The helm's chosen course, the torpedoes it is dodging, and the weapons officer's aim."""
    if ship is None:
        return
    upw = obs.rules.units_per_warp
    for a in acts:
        if a.plan is not None:
            col = theme.CAUTION if a.kind == "evade" else theme.CREW
            r = math.radians(a.plan.course)
            reach = max(600.0, max(1.0, a.plan.warp) * upw * HELM_SECONDS)
            p0 = cam.to_screen(ship.x, ship.y)
            p1 = cam.to_screen(ship.x + math.sin(r) * reach, ship.y + math.cos(r) * reach)
            _dashed(surf, theme.dim(col, 0.9), p0, p1, 8, 5)
            _arrow_head(surf, col, p0, p1)
            theme.text(surf, name_of(a.officer_id), (p1[0] + 6, p1[1] - 8), col, 11, weight="medium")
            if a.kind == "evade":
                for t in incoming(obs, ship):
                    tr = math.radians(t.course)
                    q0 = cam.to_screen(t.x, t.y)
                    q1 = cam.to_screen(t.x + math.sin(tr) * t.speed * 2.0, t.y + math.cos(tr) * t.speed * 2.0)
                    _dashed(surf, theme.dim(theme.HOSTILE, 0.8), q0, q1, 4, 4)
                    pygame.draw.circle(surf, theme.HOSTILE, (int(q0[0]), int(q0[1])), 5, 1)
            continue
        if a.target is not None:
            c = obs.contact(a.target)
            if c is not None and c.visible:
                sx, sy = cam.to_screen(c.x, c.y)
                _brackets(surf, theme.CREW, (sx, sy), 20)
                what = a.role.split(" on ")[0].lower() if " on " in a.role else a.role.lower()
                theme.text(surf, f"{name_of(a.officer_id)}: {what}", (sx + 24, sy + 12), theme.CREW, 11, weight="medium")
        if a.aim is not None:
            ax, ay, spread, tick = a.aim
            age = (obs.tick - tick) / obs.rules.ticks_per_cycle
            if 0 <= age < AIM_FADE:
                k = 1.0 - age / AIM_FADE
                sx, sy = cam.to_screen(ax, ay)
                rr = max(6.0, spread * cam.zoom)
                _dashed_circle(surf, theme.dim(theme.CREW, 0.4 + 0.6 * k), (sx, sy), rr)
                pygame.draw.line(surf, theme.dim(theme.CREW, k), (sx - 5, sy), (sx + 5, sy))
                pygame.draw.line(surf, theme.dim(theme.CREW, k), (sx, sy - 5), (sx, sy + 5))


def _brackets(surf: pygame.Surface, col: theme.Color, c: tuple[float, float], r: float) -> None:
    x, y = c
    k = r * 0.45
    for sx, sy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
        cx, cy = x + sx * r, y + sy * r
        pygame.draw.line(surf, col, (cx, cy), (cx - sx * k, cy), 2)
        pygame.draw.line(surf, col, (cx, cy), (cx, cy - sy * k), 2)


def _arrow_head(surf: pygame.Surface, col: theme.Color, a: tuple[float, float], b: tuple[float, float]) -> None:
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for d in (2.6, -2.6):
        pygame.draw.line(surf, col, b, (b[0] + math.cos(ang + d) * 9, b[1] + math.sin(ang + d) * 9), 2)


def _dashed(surf: pygame.Surface, col: theme.Color, a: tuple[float, float], b: tuple[float, float],
            on: float, off: float) -> None:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 1:
        return
    ux, uy = dx / length, dy / length
    t = 0.0
    while t < length:
        e = min(length, t + on)
        pygame.draw.line(surf, col, (a[0] + ux * t, a[1] + uy * t), (a[0] + ux * e, a[1] + uy * e), 2)
        t += on + off


def _dashed_circle(surf: pygame.Surface, col: theme.Color, c: tuple[float, float], r: float) -> None:
    n = max(16, min(96, int(r / 5)))
    for i in range(0, n, 2):
        a0, a1 = 2 * math.pi * i / n, 2 * math.pi * (i + 1) / n
        pygame.draw.line(surf, col, (c[0] + math.cos(a0) * r, c[1] + math.sin(a0) * r),
                         (c[0] + math.cos(a1) * r, c[1] + math.sin(a1) * r), 1)


__all__ = ["draw_intent", "draw_panel"]
