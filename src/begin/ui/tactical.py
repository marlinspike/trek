"""The tactical map: grid, ships, ordnance, arcs and effects.

Everything shown comes from the player's side `Observation`: hostile ships
are drawn where sensors put them, not where they are. Positions are
interpolated between simulation ticks so motion is smooth at 60 FPS while
the simulation runs at 10 ticks per cycle.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

import pygame

from ..core.angles import norm180
from ..sim.events import Event, ShieldHit
from ..sim.factory import SHIELD_FACINGS
from ..sim.observation import ContactView, Observation, OrdnanceView
from ..sim.ship import Ship
from . import theme
from .camera import Camera
from .effects import Effects
from .hulls import draw_hull, hull_pixel_scale

Pose = tuple[float, float, float]  # x, y, course


def lerp_pose(a: Pose | None, b: Pose, t: float) -> Pose:
    if a is None:
        return b
    dc = norm180(b[2] - a[2])
    return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, (a[2] + dc * t) % 360.0)


@dataclass
class Snapshot:
    ships: dict[int, Pose] = field(default_factory=dict)
    ordnance: dict[int, Pose] = field(default_factory=dict)

    @staticmethod
    def take(obs: Observation) -> Snapshot:
        s = Snapshot()
        for sh in obs.own_ships(alive_only=False):
            s.ships[sh.id] = (sh.x, sh.y, sh.course)
        for c in obs.contacts().values():
            s.ships[c.id] = (c.x, c.y, c.course)
        for o in obs.ordnance():
            s.ordnance[o.id] = (o.x, o.y, o.course)
        return s


@dataclass
class TacticalView:
    cam: Camera
    effects: Effects = field(default_factory=Effects)
    shield_flashes: dict[int, list[list[float]]] = field(default_factory=dict)  # ship -> [[sector, age]]
    show_arcs: bool = False
    hover_world: tuple[float, float] | None = None
    _overlay: pygame.Surface | None = None

    def ingest(self, events: list[Event], obs: Observation) -> None:
        visible = {s.id for s in obs.own_ships(alive_only=False)} | {c.id for c in obs.contacts().values() if c.visible}
        friendly = {s.id for s in obs.own_ships(alive_only=False)}
        self.effects.ingest(events, obs.side, visible, friendly)
        for ev in events:
            if isinstance(ev, ShieldHit) and ev.ship_id in visible:
                self.shield_flashes.setdefault(ev.ship_id, []).append([float(ev.sector), 0.0])

    def update(self, dt: float) -> None:
        self.effects.update(dt)
        for sid in list(self.shield_flashes):
            fl = [f for f in self.shield_flashes[sid] if f[1] + dt < 0.6]
            for f in fl:
                f[1] += dt
            if fl:
                self.shield_flashes[sid] = fl
            else:
                del self.shield_flashes[sid]

    # ----------------------------------------------------------------- drawing

    def draw(self, surf: pygame.Surface, obs: Observation, prev: Snapshot | None, now: Snapshot, alpha: float,
             player_id: int | None, target_id: int | None, selected_sub: str | None) -> None:
        cam = self.cam
        r = cam.rect
        if self._overlay is None or self._overlay.get_size() != surf.get_size():
            self._overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        overlay = self._overlay
        overlay.fill((0, 0, 0, 0))
        clip = surf.get_clip()
        surf.set_clip(r)
        pygame.draw.rect(surf, theme.BG, r)

        def pose(sid: int) -> Pose | None:
            b = now.ships.get(sid)
            if b is None:
                return None
            return lerp_pose(prev.ships.get(sid) if prev else None, b, alpha)

        me = obs.own(player_id) if player_id is not None else None
        if me is not None and cam.follow == me.id:
            p = pose(me.id)
            if p:
                cam.cx, cam.cy = p[0], p[1]

        self._grid(surf)
        if me is not None and me.exists:
            p = pose(me.id)
            if p:
                self._ranges(surf, overlay, me, p)

        # ordnance
        for o in obs.ordnance():
            b = now.ordnance.get(o.id)
            if b is None:
                continue
            p = lerp_pose(prev.ordnance.get(o.id) if prev else None, b, alpha)
            self._ordnance(surf, o, p)

        # ships
        for s in obs.own_ships(alive_only=False):
            if not s.exists:
                continue
            p = pose(s.id)
            if p:
                self._own_ship(surf, overlay, s, p, s.id == player_id, obs)
        for c in obs.contacts().values():
            p = pose(c.id)
            if p:
                self._contact(surf, c, p, c.id == target_id, selected_sub)

        # target link
        if me is not None and target_id is not None:
            pm, pt = pose(me.id), pose(target_id)
            if pm and pt:
                self._dashed(surf, theme.dim(theme.HOSTILE, 0.75), cam.to_screen(pm[0], pm[1]), cam.to_screen(pt[0], pt[1]), 6, 6)

        self.effects.draw(surf, cam, overlay)
        surf.blit(overlay, (0, 0))
        self._scale_bar(surf)
        pygame.draw.rect(surf, theme.BORDER, r, 1)
        surf.set_clip(clip)

    def _grid(self, surf: pygame.Surface) -> None:
        cam = self.cam
        r = cam.rect
        # pick a spacing that lands between ~50 and ~150 px
        spacing = 500.0
        for s in (500.0, 1000.0, 2000.0, 5000.0, 10000.0, 20000.0, 50000.0, 100000.0):
            spacing = s
            if s * cam.zoom >= 55:
                break
        x0, y1 = cam.to_world(r.left, r.top)
        x1, y0 = cam.to_world(r.right, r.bottom)
        gx = math.floor(x0 / spacing) * spacing
        while gx <= x1:
            sx, _ = cam.to_screen(gx, 0)
            major = abs(gx / spacing) % 5 < 1e-6
            pygame.draw.line(surf, theme.GRID_MAJOR if major else theme.GRID, (sx, r.top), (sx, r.bottom))
            gx += spacing
        gy = math.floor(y0 / spacing) * spacing
        while gy <= y1:
            _, sy = cam.to_screen(0, gy)
            major = abs(gy / spacing) % 5 < 1e-6
            pygame.draw.line(surf, theme.GRID_MAJOR if major else theme.GRID, (r.left, sy), (r.right, sy))
            gy += spacing

    def _scale_bar(self, surf: pygame.Surface) -> None:
        cam = self.cam
        r = cam.rect
        for units in (500, 1000, 2000, 5000, 10000, 20000, 50000):
            px = units * cam.zoom
            if px >= 70:
                break
        x, y = r.left + 16, r.bottom - 18
        pygame.draw.line(surf, theme.TEXT_DIM, (x, y), (x + px, y))
        pygame.draw.line(surf, theme.TEXT_DIM, (x, y - 4), (x, y + 2))
        pygame.draw.line(surf, theme.TEXT_DIM, (x + px, y - 4), (x + px, y + 2))
        theme.text(surf, f"{units:,}", (x + px + 6, y - 7), theme.TEXT_DIM, 11, "mono")

    def _ranges(self, surf: pygame.Surface, overlay: pygame.Surface, me: Ship, p: Pose) -> None:
        cam = self.cam
        sx, sy = cam.to_screen(p[0], p[1])
        rr = me.cls.banks_range * cam.zoom
        if 12 < rr < 4000:
            self._dashed_circle(surf, theme.dim(theme.FRIEND, 0.45), (sx, sy), rr)
            theme.text(surf, "phaser", (sx + rr * 0.707 + 4, sy - rr * 0.707 - 6), theme.dim(theme.FRIEND, 0.6), 10)
        sr = me.sensor_range() * cam.zoom
        if 12 < sr < 6000:
            pygame.draw.circle(surf, theme.dim(theme.FRIEND, 0.22), (int(sx), int(sy)), int(sr), 1)
        if self.show_arcs:
            for b in me.banks:
                c = b.mount.arc_center + p[2]
                w = b.mount.arc_width
                if w >= 359:
                    continue
                pts = [(sx, sy)]
                for k in range(13):
                    a = math.radians(c - w / 2 + w * k / 12)
                    pts.append((sx + math.sin(a) * rr, sy - math.cos(a) * rr))
                col = theme.GOOD if b.charge >= me.cls.banks_charge - 1e-6 else theme.CAUTION
                pygame.draw.polygon(overlay, (*col, 18), pts)
                pygame.draw.polygon(overlay, (*col, 60), pts, 1)

    def _shield_ring(self, surf: pygame.Surface, ship_id: int, sx: float, sy: float, course: float, rad: float,
                     strengths: list[tuple[float, bool]] | None) -> None:
        flashes = {int(f[0]): f[1] for f in self.shield_flashes.get(ship_id, [])}
        for i, facing in enumerate(SHIELD_FACINGS):
            fl = flashes.get(i)
            if strengths is None and fl is None:
                continue
            if strengths is not None:
                st, up = strengths[i] if i < len(strengths) else (0.0, False)
                if not up:
                    continue
                col = theme.mix(theme.ALERT, theme.SHIELD, st / 100.0)
                col = theme.dim(col, 0.55)
            else:
                col = theme.SHIELD
            if fl is not None:
                col = theme.mix((255, 255, 255), col, fl / 0.6)
            a0 = math.radians(90 - (course + facing + 26))
            a1 = math.radians(90 - (course + facing - 26))
            rect = pygame.Rect(0, 0, rad * 2, rad * 2)
            rect.center = (int(sx), int(sy))
            pygame.draw.arc(surf, col, rect, a0, a1, 2 if fl is None else 3)

    def _own_ship(self, surf: pygame.Surface, overlay: pygame.Surface, s: Ship, p: Pose, is_player: bool,
                  obs: Observation) -> None:
        cam = self.cam
        if not cam.visible(p[0], p[1], 200):
            return
        sx, sy = cam.to_screen(p[0], p[1])
        k = hull_pixel_scale(s.cls.hull, cam.zoom)
        color = theme.FRIEND if s.alive else theme.TEXT_FAINT
        if not is_player and s.alive:
            color = theme.ALLY
        if s.cloaked:
            color = theme.dim(color, 0.5)
        # velocity leader
        if s.warp > 0.05:
            a = math.radians(p[2])
            L = 18 + s.warp * 6
            pygame.draw.line(surf, theme.dim(color, 0.5), (sx, sy), (sx + math.sin(a) * L * 1.5, sy - math.cos(a) * L * 1.5))
        if is_player and abs(norm180(s.desired_course - s.course)) > 1:
            a = math.radians(s.desired_course)
            L = 50 * k
            pygame.draw.line(surf, theme.dim(theme.CAUTION, 0.7), (sx, sy), (sx + math.sin(a) * L, sy - math.cos(a) * L), 1)
        draw_hull(surf, s.cls.hull, sx, sy, p[2], k, color)
        strengths = [(sh.effective if not sh.destroyed else 0.0, sh.up and not sh.destroyed and sh.effective > 0.5)
                     for sh in s.shields]
        self._shield_ring(surf, s.id, sx, sy, p[2], 62 * k, strengths)
        label = s.name if s.alive else f"{s.name} — {s.status.value}"
        theme.text(surf, label, (sx + 34 * k + 6, sy - 8), color, 12, weight="medium")
        if is_player:
            theme.text(surf, f"w{s.warp:.1f}", (sx + 34 * k + 6, sy + 6), theme.TEXT_DIM, 10, "mono")

    def _contact(self, surf: pygame.Surface, c: ContactView, p: Pose, targeted: bool, sub: str | None) -> None:
        cam = self.cam
        if not cam.visible(p[0], p[1], 200):
            return
        sx, sy = cam.to_screen(p[0], p[1])
        color = theme.HOSTILE if c.identified else theme.UNKNOWN
        if not c.visible:
            color = theme.dim(color, 0.45)
        if c.cls is not None:
            k = hull_pixel_scale(c.cls.hull, cam.zoom)
            if c.warp > 0.05 and c.visible:
                a = math.radians(p[2])
                L = 18 + c.warp * 6
                pygame.draw.line(surf, theme.dim(color, 0.45), (sx, sy), (sx + math.sin(a) * L * 1.5, sy - math.cos(a) * L * 1.5))
            draw_hull(surf, c.cls.hull, sx, sy, p[2], k, color, fill_alpha=0.22 if c.visible else 0.08)
            self._shield_ring(surf, c.id, sx, sy, p[2], 62 * k, None)
            rad = 40 * k
        else:
            rad = 10
            pts = [(sx, sy - rad), (sx + rad, sy), (sx, sy + rad), (sx - rad, sy)]
            pygame.draw.polygon(surf, color, pts, 1)
            theme.text(surf, "?", (sx, sy), color, 12, anchor="center")
        if not c.visible:
            self._dashed_circle(surf, theme.dim(color, 0.8), (sx, sy), rad + 6, seg=8)
        label = c.label if c.identified else f"#{c.id}"
        theme.text(surf, label, (sx + rad + 8, sy - 8), color, 12, weight="medium")
        if not c.visible:
            theme.text(surf, f"lost {c.age:.0f}s", (sx + rad + 8, sy + 6), theme.TEXT_FAINT, 10)
        if targeted:
            b = rad + 10
            col = theme.CAUTION
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                cx, cy = sx + dx * b, sy + dy * b
                pygame.draw.line(surf, col, (cx, cy), (cx - dx * 8, cy), 2)
                pygame.draw.line(surf, col, (cx, cy), (cx, cy - dy * 8), 2)
            if sub:
                theme.text(surf, f"⌖ {sub}", (sx, sy + b + 6), col, 11, anchor="midtop")

    def _ordnance(self, surf: pygame.Surface, o: OrdnanceView, p: Pose) -> None:
        cam = self.cam
        if not cam.visible(p[0], p[1], 20):
            return
        sx, sy = cam.to_screen(p[0], p[1])
        a = math.radians(p[2])
        if o.kind == "torpedo":
            col = theme.TORPEDO_FRIEND if o.friendly else theme.TORPEDO
            tail = min(28.0, 8 + o.speed * cam.zoom * 0.05)
            pygame.draw.line(surf, theme.dim(col, 0.45), (sx, sy), (sx - math.sin(a) * tail, sy + math.cos(a) * tail), 1)
            pts = [(sx + math.sin(a) * 4, sy - math.cos(a) * 4), (sx + math.cos(a) * 3, sy + math.sin(a) * 3),
                   (sx - math.sin(a) * 3, sy + math.cos(a) * 3), (sx - math.cos(a) * 3, sy - math.sin(a) * 3)]
            pygame.draw.polygon(surf, col if o.armed else theme.dim(col, 0.6), pts)
        else:
            col = theme.TORPEDO_FRIEND if o.friendly else theme.PROBE
            pygame.draw.circle(surf, col, (int(sx), int(sy)), 4, 1)
            pygame.draw.circle(surf, col, (int(sx), int(sy)), 1)
            if o.code:
                theme.text(surf, o.code, (sx + 7, sy - 6), theme.dim(col, 0.9), 10, "mono")

    @staticmethod
    def _dashed(surf: pygame.Surface, col: theme.Color, a: tuple[float, float], b: tuple[float, float], on: float, off: float) -> None:
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 1:
            return
        ux, uy = dx / L, dy / L
        d = 0.0
        while d < L:
            e = min(L, d + on)
            pygame.draw.line(surf, col, (a[0] + ux * d, a[1] + uy * d), (a[0] + ux * e, a[1] + uy * e))
            d = e + off

    @staticmethod
    def _dashed_circle(surf: pygame.Surface, col: theme.Color, c: tuple[float, float], r: float, seg: int | None = None) -> None:
        n = seg or max(16, min(120, int(r / 6)))
        for i in range(0, n, 2):
            a0 = 2 * math.pi * i / n
            a1 = 2 * math.pi * (i + 1) / n
            pygame.draw.line(surf, col, (c[0] + math.cos(a0) * r, c[1] + math.sin(a0) * r),
                             (c[0] + math.cos(a1) * r, c[1] + math.sin(a1) * r))

    # ----------------------------------------------------------------- picking

    def pick(self, obs: Observation, now: Snapshot, sx: float, sy: float, radius: float = 22.0) -> int | None:
        best, bd = None, radius
        for sid, (x, y, _) in now.ships.items():
            px, py = self.cam.to_screen(x, y)
            d = math.hypot(px - sx, py - sy)
            if d < bd:
                best, bd = sid, d
        return best


__all__ = ["Snapshot", "TacticalView", "lerp_pose"]
