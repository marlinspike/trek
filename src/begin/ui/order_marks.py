"""The captain's orders, drawn on the map [E], and a ghost of the order being typed.

One grammar for everything the bridge draws, shape for what kind of order and
colour for whose station:

- a dashed tether with chevrons: a helm order about another ship (pursue draws
  the chevrons toward her, elude away from her); helm blue;
- a faint ray from the bow: the course the helm is turning to, while the ship
  is still coming round; helm blue;
- a double line: a tractor beam held on a ship; engineering green;
- HOLD FIRE beside our ship while the captain's cease fire stands; amber;
- brackets on a ship: tactical's aim (`officer_view` draws the officers' own).

The labels only show when the map is zoomed in far enough for them to sit
clear of the ships, and nothing is drawn over our ship or her target.

While the captain types, `draw_preview` shows what the line would do before
Enter: the course as a ghost ray, the ship as ghost brackets, a pursuit as a
ghost tether; and `preview_text` says it in a sentence, the same one the
officer will read back.
"""

from __future__ import annotations

import math
import time

import pygame

from ..sim.commands import (
    Command, FirePhasers, FireTorpedoes, LaunchProbe, LockWeapons, Pursue, Scan, SelectTarget, SetHelm, SetObjective,
    Tractor, Transport,
)
from ..sim.observation import Observation
from ..sim.ship import HelmMode, Ship
from . import theme
from .camera import Camera
from .officer_view import _arrow_head, _brackets, _dashed
from . import gfx

HELM = theme.ALLY
ENGINEERING = theme.GOOD
LABEL_ZOOM = 0.02        # labels only when zoomed in at least this far


def _pos(obs: Observation, sid: int | None) -> tuple[float, float] | None:
    if sid is None:
        return None
    s = obs.own(sid)
    if s is not None:
        return s.x, s.y
    c = obs.contact(sid)
    return (c.x, c.y) if c is not None and c.visible else None


def _chevrons(surf: pygame.Surface, col: theme.Color, a: tuple[float, float], b: tuple[float, float], n: int) -> None:
    dx, dy = b[0] - a[0], b[1] - a[1]
    length = math.hypot(dx, dy)
    if length < 60:
        return
    ang = math.atan2(dy, dx)
    for k in range(1, n + 1):
        t = k / (n + 1)
        x, y = a[0] + dx * t, a[1] + dy * t
        for d in (2.5, -2.5):
            gfx.draw.line(surf, col, (x, y), (x + math.cos(ang + d) * 8, y + math.sin(ang + d) * 8), 2)


def draw_orders(surf: pygame.Surface, cam: Camera, obs: Observation, ship: Ship | None) -> None:
    """The captain's standing orders (helm and tractor), for the stations the captain runs."""
    if ship is None or not ship.alive:
        return
    me = cam.to_screen(ship.x, ship.y)
    labels = cam.zoom >= LABEL_ZOOM
    if "helm" not in ship.delegated and not ship.conn:
        other = _pos(obs, ship.helm_target)
        if ship.helm_mode in (HelmMode.PURSUE, HelmMode.ELUDE) and other is not None:
            them = cam.to_screen(*other)
            col = theme.dim(HELM, 0.75)
            _dashed(surf, col, me, them, 6, 6)
            if ship.helm_keep is not None:
                word = f"holding at {ship.helm_keep:,.0f}"
            elif ship.helm_mode == HelmMode.PURSUE:
                _chevrons(surf, HELM, me, them, 2)
                word = "pursuing"
            else:
                _chevrons(surf, HELM, them, me, 2)
                word = "eluding"
            if labels:
                mx, my = (me[0] + them[0]) / 2, (me[1] + them[1]) / 2
                theme.text(surf, word, (mx + 10, my - 16), col, 11, weight="medium")
        elif ship.helm_mode == HelmMode.COURSE and ship.desired_warp > 0:
            off = abs((ship.desired_course - ship.course + 180) % 360 - 180)
            if off > 4:
                r = math.radians(ship.desired_course)
                reach = max(60.0, min(260.0, 40 + off * 1.2))
                p1 = (me[0] + math.sin(r) * reach, me[1] - math.cos(r) * reach)
                _dashed(surf, theme.dim(HELM, 0.7), me, p1, 5, 6)
                _arrow_head(surf, theme.dim(HELM, 0.9), me, p1)
                if labels:
                    theme.text(surf, f"{round(ship.desired_course) % 360:03d}", (p1[0] + 6, p1[1] - 7), theme.dim(HELM, 0.9),
                               11, "mono")
    held = _pos(obs, ship.tractor_target)
    if held is not None:
        them = cam.to_screen(*held)
        ang = math.atan2(them[1] - me[1], them[0] - me[0])
        nx, ny = -math.sin(ang) * 3, math.cos(ang) * 3
        for s in (1, -1):
            gfx.draw.line(surf, theme.dim(ENGINEERING, 0.8), (me[0] + nx * s, me[1] + ny * s),
                             (them[0] + nx * s, them[1] + ny * s), 1)
    if ship.hold_fire:
        theme.text(surf, "HOLD FIRE", (me[0], me[1] + 26), theme.CAUTION, 10, weight="semibold", anchor="midtop")


def preview_targets(cmds: list[Command]) -> list[int]:
    out: list[int] = []
    for c in cmds:
        for attr in ("target",):
            v = getattr(c, attr, None)
            if isinstance(v, int) and isinstance(c, (FirePhasers, FireTorpedoes, LaunchProbe, LockWeapons, SelectTarget,
                                                     Scan, Tractor, Transport)):
                out.append(v)
        if isinstance(c, SetObjective):
            out.extend(c.targets)
    return list(dict.fromkeys(out))


def draw_preview(surf: pygame.Surface, cam: Camera, obs: Observation, ship: Ship | None, cmds: list[Command]) -> None:
    """A ghost of what the typed line would do: a breathing outline, never solid, never over our ship."""
    if ship is None or not cmds:
        return
    beat = 0.55 + 0.45 * math.sin(time.monotonic() * math.tau / 1.4)
    col = theme.mix(theme.BG, theme.FRIEND, 0.45 + 0.4 * beat)
    me = cam.to_screen(ship.x, ship.y)
    for c in cmds:
        if isinstance(c, SetHelm) and c.course is not None:
            r = math.radians(c.course)
            p1 = (me[0] + math.sin(r) * 150, me[1] - math.cos(r) * 150)
            _dashed(surf, col, (me[0] + math.sin(r) * 22, me[1] - math.cos(r) * 22), p1, 4, 5)
            _arrow_head(surf, col, me, p1)
        elif isinstance(c, Pursue):
            other = _pos(obs, c.target)
            if other is not None:
                them = cam.to_screen(*other)
                _dashed(surf, col, me, them, 4, 7)
                if c.elude:
                    _chevrons(surf, col, them, me, 2)
                else:
                    _chevrons(surf, col, me, them, 2)
    for sid in preview_targets(cmds):
        p = _pos(obs, sid)
        if p is not None:
            sx, sy = cam.to_screen(*p)
            _brackets(surf, col, (sx, sy), 24 + 3 * beat)


__all__ = ["draw_orders", "draw_preview", "preview_targets"]
