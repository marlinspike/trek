"""The tactical map: grid, ships, ordnance, arcs and effects.

Everything shown comes from the player's side `Observation`: hostile ships
are drawn where sensors put them, not where they are. Positions are
interpolated between simulation ticks so motion is smooth at 60 FPS while
the simulation runs at 10 ticks per cycle.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Callable

import pygame

from ..content.schema import Faction
from ..core.angles import norm180
from ..sim.events import Event, ShieldHit
from ..sim.factory import SHIELD_FACINGS
from ..sim.observation import ContactView, Observation, OrdnanceView
from ..sim.ship import Ship
from . import theme
from .camera import Camera
from .effects import Effects
from .showpiece import SPRITE_CENTRE_Y, SPRITE_PX, ship_image, ship_lights
from .hulls import draw_hull, hull_pixel_scale
from .starfield import Starfield

SHIELD_FLASH = 0.7        # seconds a shield hit shimmers
TRAIL_POINT = 0.25        # cycles between the points of an engine trail
TRAIL_BANDS = 4           # strokes per wake, each fainter toward the tail
SMOULDER_BELOW = 0.5      # hull fraction below which a ship trails sparks
SPRITE_MIN_K = 0.9         # pixels per hull unit at which a ship with showpiece art is drawn with it
SHOWPIECE = frozenset({"federation.hc"})
TORP_TRAIL = 1.4          # cycles of exhaust a torpedo leaves behind it
TORP_TRAIL_POINT = 0.05   # cycles between the points of a torpedo trail
LOCK_TIME = 0.35          # seconds the target brackets take to close in

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



def faction_seen(obs: Observation, sid: int | None) -> Faction | None:
    """The race of a ship as our side can see it: our own, or a contact we have identified."""
    if sid is None:
        return None
    own = obs.own(sid)
    if own is not None:
        return obs.content.factions.get(own.faction)
    c = obs.contact(sid)
    if c is None or c.cls is None or not c.identified:
        return None
    return obs.content.factions.get(c.cls.faction)

@dataclass
class TacticalView:
    cam: Camera
    effects: Effects = field(default_factory=Effects)
    shield_flashes: dict[int, list[list[float]]] = field(default_factory=dict)  # ship -> [[sector, age, power, collapsed]]
    _burning: list[tuple[float, float, float]] = field(default_factory=list)   # (x, y, hull fraction) seen damaged this frame
    trails: dict[int, list[tuple[float, float, float]]] = field(default_factory=dict)   # ship -> [(x, y, time)]
    _cloaked: dict[int, bool] = field(default_factory=dict)     # how each ship looked last frame, to see it vanish
    stars: Starfield = field(default_factory=Starfield)
    _sounds: list[tuple[str, float, float]] = field(default_factory=list)   # (sound, x, y) seen this frame
    show_arcs: bool = False
    hover_world: tuple[float, float] | None = None
    _overlay: pygame.Surface | None = None
    _label_rects: list[pygame.Rect] = field(default_factory=list)   # labels drawn this frame
    torp_trails: dict[int, list[tuple[float, float, float]]] = field(default_factory=dict)   # round -> [(x, y, time)]
    clock: float = 0.0                       # wall-clock seconds, for animation
    _lock: tuple[int | None, float] = (None, 0.0)   # the target the brackets are on, and when they started closing

    def ingest(self, events: list[Event], obs: Observation) -> None:
        visible = {s.id for s in obs.own_ships(alive_only=False)} | {c.id for c in obs.contacts().values() if c.visible}
        friendly = {s.id for s in obs.own_ships(alive_only=False)}
        self.effects.ingest(events, obs.side, visible, friendly, lambda sid: faction_seen(obs, sid))
        for ev in events:
            if isinstance(ev, ShieldHit) and ev.ship_id in visible:
                power = 0.35 + 0.65 * min(1.0, (ev.absorbed + ev.penetrated) / 40.0)
                self.shield_flashes.setdefault(ev.ship_id, []).append(
                    [float(ev.sector), 0.0, power, 1.0 if ev.collapsed else 0.0])

    def update(self, dt: float) -> None:
        self.clock += dt
        self.effects.update(dt)
        for x, y, frac in self._burning:
            self.effects.smoulder(x, y, frac, dt, self.cam.zoom)
        for sid in list(self.shield_flashes):
            fl = [f for f in self.shield_flashes[sid] if f[1] + dt < SHIELD_FLASH]
            for f in fl:
                f[1] += dt
            if fl:
                self.shield_flashes[sid] = fl
            else:
                del self.shield_flashes[sid]

    # ----------------------------------------------------------------- drawing

    def draw(self, surf: pygame.Surface, obs: Observation, prev: Snapshot | None, now: Snapshot, alpha: float,
             player_id: int | None, target_id: int | None, selected_sub: str | None,
             selected_ally: int | None = None) -> None:
        cam = self.cam
        r = cam.rect
        if self._overlay is None or self._overlay.get_size() != surf.get_size():
            self._overlay = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        overlay = self._overlay
        overlay.fill((0, 0, 0, 0))
        self._label_rects = []
        self._burning = []
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

        self._starfield(surf)
        self._grid(surf)
        self._trails(overlay, obs, pose)
        if me is not None and me.exists:
            p = pose(me.id)
            if p:
                self._ranges(surf, overlay, me, p)

        # ordnance
        live: set[int] = set()
        for o in obs.ordnance():
            b = now.ordnance.get(o.id)
            if b is None:
                continue
            p = lerp_pose(prev.ordnance.get(o.id) if prev else None, b, alpha)
            f = obs.content.factions.get(o.faction)
            if o.kind == "torpedo":
                live.add(o.id)
                self._torp_trail(overlay, o.id, p, obs.time, f)
            self._ordnance(surf, o, p, f, overlay)
        for oid in [k for k in self.torp_trails if k not in live]:
            del self.torp_trails[oid]

        names = {s.id: s.name for s in obs.own_ships(alive_only=False)}
        names.update({c.id: c.label if c.identified else f"#{c.id}" for c in obs.contacts().values()})
        self._links(surf, overlay, obs, pose, player_id, selected_ally)

        # ships
        for s in obs.own_ships(alive_only=False):
            if not s.exists:
                continue
            p = pose(s.id)
            if p:
                self._own_ship(surf, overlay, s, p, s.id == player_id, obs, s.id == selected_ally, names)
        for c in obs.contacts().values():
            p = pose(c.id)
            if p:
                self._contact(surf, c, p, c.id == target_id, selected_sub, overlay)

        # target link
        if me is not None and target_id is not None:
            pm, pt = pose(me.id), pose(target_id)
            if pm and pt:
                self._dashed(surf, theme.dim(theme.HOSTILE, 0.75), cam.to_screen(pm[0], pm[1]), cam.to_screen(pt[0], pt[1]), 6, 6)

        self._ripples(obs, pose)
        self.effects.draw(surf, cam, overlay)
        surf.blit(overlay, (0, 0))
        self._scale_bar(surf)
        pygame.draw.rect(surf, theme.border(), r, 1)
        surf.set_clip(clip)

    def _starfield(self, surf: pygame.Surface) -> None:
        """Faint stars far beyond the battle, drifting a little against the grid as the view pans."""
        self.stars.draw(surf, self.cam.rect, self.cam.cx, self.cam.cy)

    def _trails(self, overlay: pygame.Surface, obs: Observation, pose: Callable[[int], Pose | None]) -> None:
        """Engine wakes: where each ship has just been, longer the faster it goes."""
        now = obs.time
        seen: dict[int, tuple[float, theme.Color]] = {}
        for s in obs.own_ships():
            if s.exists and not s.cloaked:
                seen[s.id] = (s.warp, theme.FRIEND if s.id == self.cam.follow else theme.ALLY)
        for c in obs.contacts().values():
            if c.visible:
                seen[c.id] = (c.warp, theme.HOSTILE if c.identified else theme.UNKNOWN)
        for sid in list(self.trails):
            if sid not in seen:
                del self.trails[sid]
        cam = self.cam
        for sid, (warp, col) in seen.items():
            p = pose(sid)
            if p is None:
                continue
            pts = self.trails.setdefault(sid, [])
            if pts and now < pts[-1][2]:
                pts.clear()          # time went backwards: a new battle in the same view
            if not pts or now - pts[-1][2] >= TRAIL_POINT:
                pts.append((p[0], p[1], now))
            span = 1.0 + 0.8 * warp                        # cycles of wake kept
            while pts and now - pts[0][2] > span:
                pts.pop(0)
            if warp < 0.2 or len(pts) < 2 or not cam.visible(p[0], p[1], 400):
                continue
            path = [cam.to_screen(x, y) for x, y, _ in pts] + [cam.to_screen(p[0], p[1])]
            n = len(path) - 1
            strength = min(1.0, 0.35 + warp / 10)
            wake = theme.mix(col, (235, 240, 255), 0.35)
            for band in range(TRAIL_BANDS):     # a few strokes, fading toward the tail
                lo, hi = n * band // TRAIL_BANDS, n * (band + 1) // TRAIL_BANDS
                alpha = int(95 * strength * ((band + 1) / TRAIL_BANDS) ** 1.5)
                if hi > lo and alpha > 3:
                    pygame.draw.lines(overlay, (*wake, alpha), False, path[lo:hi + 1], 2 if band == TRAIL_BANDS - 1 else 1)

    def _torp_trail(self, overlay: pygame.Surface, oid: int, p: Pose, now: float, f: Faction | None) -> None:
        """The exhaust a torpedo leaves: a short streak that fades out behind it."""
        pts = self.torp_trails.setdefault(oid, [])
        if pts and now < pts[-1][2]:
            pts.clear()
        if not pts or now - pts[-1][2] >= TORP_TRAIL_POINT:
            pts.append((p[0], p[1], now))
        while pts and now - pts[0][2] > TORP_TRAIL:
            pts.pop(0)
        cam = self.cam
        if len(pts) < 2 or not cam.visible(p[0], p[1], 300):
            return
        col = f.torpedo_color if f is not None else theme.TORPEDO
        path = [cam.to_screen(x, y) for x, y, _ in pts] + [cam.to_screen(p[0], p[1])]
        n = len(path) - 1
        for i in range(n):                    # each segment fainter the older it is
            k = (i + 1) / n
            pygame.draw.line(overlay, (*col, int(170 * k * k)), path[i], path[i + 1], 1 if k < 0.5 else 2)

    def _ripples(self, obs: Observation, pose: Callable[[int], Pose | None]) -> None:
        """A ship that cloaks or decloaks in sight bends the light around it for a moment."""
        now: dict[int, bool] = {}
        for s in obs.own_ships():
            if s.exists:
                now[s.id] = s.cloaked
        for c in obs.contacts().values():
            # lost at close range with a cloak suspected: it vanished in front of us
            now[c.id] = not c.visible and c.cloaked_hint
        for sid, hidden in now.items():
            was = self._cloaked.get(sid)
            if was is not None and was != hidden:
                p = pose(sid)
                if p is not None:
                    self.effects.ripple(p[0], p[1], vanishing=hidden)
                    self._sounds.append(("cloak", p[0], p[1]))
        self._cloaked = now

    def take_sounds(self) -> list[tuple[str, float, float]]:
        out, self._sounds = self._sounds, []
        return out

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
                     strengths: list[tuple[float, bool]] | None, overlay: pygame.Surface | None = None) -> None:
        flashes = {int(f[0]): f for f in self.shield_flashes.get(ship_id, [])}
        for i, facing in enumerate(SHIELD_FACINGS):
            hit = flashes.get(i)
            fl = hit[1] if hit is not None else None
            if hit is not None and overlay is not None:
                self._shimmer(overlay, ship_id, i, sx, sy, course + facing, rad, hit)
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
                col = theme.mix((255, 255, 255), col, fl / SHIELD_FLASH)
            a0 = math.radians(90 - (course + facing + 26))
            a1 = math.radians(90 - (course + facing - 26))
            rect = pygame.Rect(0, 0, rad * 2, rad * 2)
            rect.center = (int(sx), int(sy))
            pygame.draw.arc(surf, col, rect, a0, a1, 2 if fl is None else 3)

    @staticmethod
    def _shimmer(overlay: pygame.Surface, ship_id: int, sector: int, sx: float, sy: float, facing: float,
                 rad: float, hit: list[float]) -> None:
        """A hit on a shield: the arc ripples outward and glitters, brightest where the blow landed."""
        age, power, collapsed = hit[1], hit[2], hit[3] > 0
        t = age / SHIELD_FLASH
        fade = (1.0 - t) ** 1.5 * power
        col = theme.ALERT if collapsed else theme.mix((235, 245, 255), theme.SHIELD, 0.4)
        for k in range(3):
            r = rad + 2 + (k * 3 + 6 * t) * (1.0 + 0.4 * k)
            half = 14 + 12 * t + 4 * k
            rect = pygame.Rect(0, 0, int(r * 2), int(r * 2))
            rect.center = (int(sx), int(sy))
            a0, a1 = math.radians(90 - (facing + half)), math.radians(90 - (facing - half))
            alpha = int(150 * fade / (1 + k))
            if alpha > 4:
                if collapsed and k == 0:   # a failing shield breaks up rather than ripples
                    for j in range(4):
                        b0 = a0 + (a1 - a0) * j / 4
                        if (j + int(age * 30)) % 2 == 0:
                            pygame.draw.arc(overlay, (*col, alpha), rect, b0, b0 + (a1 - a0) / 4, 2)
                else:
                    pygame.draw.arc(overlay, (*col, alpha), rect, a0, a1, 2 if k == 0 else 1)
        rng = random.Random(ship_id * 31 + sector * 7 + int(age * 24))
        for _ in range(int(3 + 5 * power)):
            b = math.radians(facing + rng.uniform(-20, 20))
            r = rad + rng.uniform(-1.5, 4.0 + 6 * t)
            alpha = int(220 * fade * rng.uniform(0.4, 1.0))
            if alpha > 4:
                pygame.draw.circle(overlay, (255, 255, 255, alpha), (int(sx + math.sin(b) * r), int(sy - math.cos(b) * r)), 1)

    def _links(self, surf: pygame.Surface, overlay: pygame.Surface, obs: Observation,
               pose: Callable[[int], Pose | None], player_id: int | None, selected_ally: int | None) -> None:
        """Tractor beams, and each ally's standing order as a faint line to whoever it concerns."""
        cam = self.cam
        for s in obs.own_ships():
            ps = pose(s.id)
            if ps is None:
                continue
            a = cam.to_screen(ps[0], ps[1])
            if s.tractor_target is not None:
                pt = pose(s.tractor_target)
                if pt is not None:
                    self._beam(overlay, a, cam.to_screen(pt[0], pt[1]), theme.SHIELD)
            if s.id == player_id:
                continue
            st = obs.ally_order(s.id)
            if st is None:
                continue
            bright = 0.95 if s.id == selected_ally else 0.5
            if st.move_target is not None and st.movement not in (None, "course", "run", "withdraw", "stop"):
                pt = pose(st.move_target)
                if pt is not None:
                    self._dashed(surf, theme.dim(theme.ALLY, bright), a, cam.to_screen(pt[0], pt[1]), 3, 7)
            if st.target is not None:
                pt = pose(st.target)
                if pt is not None:
                    self._dashed(surf, theme.dim(theme.HOSTILE, bright * 0.8), a, cam.to_screen(pt[0], pt[1]), 3, 7)

    @staticmethod
    def _sprite(surf: pygame.Surface, cls_id: str, sx: float, sy: float, course: float, k: float) -> bool:
        """Close in, a ship with showpiece art is drawn with it. False when there's none for the class."""
        if cls_id not in SHOWPIECE:
            return False
        scale = round(k / SPRITE_PX, 2)
        img = ship_image(round(course) % 360, scale)
        if img is None:
            return False
        a = math.radians(course)
        off = -SPRITE_CENTRE_Y * k                 # the sprite's centre sits a little aft of the hull origin
        cx, cy = sx - math.sin(a) * off, sy + math.cos(a) * off
        surf.blit(img, img.get_rect(center=(int(cx), int(cy))))
        ship_lights(surf, cx, cy, round(course) % 360, scale, pygame.time.get_ticks() / 1000.0)
        return True

    @staticmethod
    def _beam(overlay: pygame.Surface, a: tuple[float, float], b: tuple[float, float], col: theme.Color) -> None:
        """A tractor beam: a soft band with a bright core, widening toward the held ship."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        L = math.hypot(dx, dy)
        if L < 1:
            return
        nx, ny = -dy / L, dx / L
        for w, alpha in ((7.0, 40), (4.0, 70)):
            pts = [(a[0] + nx * w * 0.4, a[1] + ny * w * 0.4), (b[0] + nx * w, b[1] + ny * w),
                   (b[0] - nx * w, b[1] - ny * w), (a[0] - nx * w * 0.4, a[1] - ny * w * 0.4)]
            pygame.draw.polygon(overlay, (*col, alpha), pts)
        pygame.draw.line(overlay, (*col, 200), a, b, 1)

    def _own_ship(self, surf: pygame.Surface, overlay: pygame.Surface, s: Ship, p: Pose, is_player: bool,
                  obs: Observation, selected: bool = False, names: dict[int, str] | None = None) -> None:
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
        if not (s.alive and not s.cloaked and k >= SPRITE_MIN_K and self._sprite(surf, s.cls.id, sx, sy, p[2], k)):
            draw_hull(surf, s.cls.hull, sx, sy, p[2], k, color)
        strengths = [(sh.effective if not sh.destroyed else 0.0, sh.up and not sh.destroyed and sh.effective > 0.5)
                     for sh in s.shields]
        self._shield_ring(surf, s.id, sx, sy, p[2], 62 * k, strengths, overlay)
        if s.alive and s.structure < s.structure_max * SMOULDER_BELOW:
            self._burning.append((p[0], p[1], s.structure / s.structure_max))
        label = s.name if s.alive else f"{s.name} — {s.status.value}"
        if s.alive and s.docked_to is not None:
            label += " · docked"
        lx = sx + 34 * k + 6
        top = self._free_label_y(lx, sy - 8, theme.text_width(label, 12, weight="medium"), 14)
        theme.text(surf, label, (lx, top), color, 12, weight="medium")
        ly = top + 14
        if is_player:
            theme.text(surf, f"w{s.warp:.1f}", (lx, ly), theme.TEXT_DIM, 10, "mono")
            ly += 12
        elif s.alive:
            st = obs.ally_order(s.id)
            mission = st.summary(names or {}) if st is not None else ""
            if mission:
                theme.text(surf, mission, (lx, ly), theme.TEXT_FAINT if not selected else theme.TEXT_DIM, 10)
                ly += 12
        if s.alive and s.boarders > 0 and s.boarder_side != s.side:
            theme.text(surf, f"boarders aboard: {s.boarders}", (lx, ly), theme.ALERT, 10, weight="medium")
        if selected:
            b = 62 * k + 8
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                cx, cy = sx + dx * b, sy + dy * b
                pygame.draw.line(surf, theme.ALLY, (cx, cy), (cx - dx * 7, cy), 1)
                pygame.draw.line(surf, theme.ALLY, (cx, cy), (cx, cy - dy * 7), 1)

    def _contact(self, surf: pygame.Surface, c: ContactView, p: Pose, targeted: bool, sub: str | None,
                 overlay: pygame.Surface | None = None) -> None:
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
            self._shield_ring(surf, c.id, sx, sy, p[2], 62 * k, None, overlay)
            if c.visible and c.scan is not None and c.scan.structure_frac < SMOULDER_BELOW:
                self._burning.append((p[0], p[1], c.scan.structure_frac))   # we've seen how badly she's hurt
            rad = 40 * k
        else:
            rad = 10
            pts = [(sx, sy - rad), (sx + rad, sy), (sx, sy + rad), (sx - rad, sy)]
            pygame.draw.polygon(surf, color, pts, 1)
            theme.text(surf, "?", (sx, sy), color, 12, anchor="center")
        if not c.visible:
            self._dashed_circle(surf, theme.dim(color, 0.8), (sx, sy), rad + 6, seg=8)
        elif c.haze > 0:
            # beyond rated sensor range: the ring shows how far off the reported position may be
            ring = max(rad + 6, c.uncertainty * cam.zoom)
            self._dashed_circle(surf, theme.dim(color, 0.6), (sx, sy), int(ring), seg=12)
        label = c.label if c.identified else f"#{c.id}"
        if c.visible and c.haze > 0:
            label = "~" + label
        lost = not c.visible
        top = self._free_label_y(sx + rad + 8, sy - 8, theme.text_width(label, 12, weight="medium"), 26 if lost else 14)
        theme.text(surf, label, (sx + rad + 8, top), color, 12, weight="medium")
        if lost:
            theme.text(surf, f"lost {c.age:.0f}s", (sx + rad + 8, top + 14), theme.TEXT_FAINT, 10)
        if targeted:
            if self._lock[0] != c.id:
                self._lock = (c.id, self.clock)             # a new target: the brackets close in on it
            t = min(1.0, (self.clock - self._lock[1]) / LOCK_TIME)
            ease = 1 - (1 - t) ** 3
            b = rad + 10 + 46 * (1 - ease)
            col = theme.mix(theme.BG, theme.CAUTION, 0.35 + 0.65 * ease)
            if t >= 1.0:                                      # locked: a slow breath of light
                col = theme.mix(theme.CAUTION, (255, 240, 200), 0.25 * (0.5 + 0.5 * math.sin(self.clock * 3)))
            spin = math.radians(90 * (1 - ease))
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                ox, oy = dx * b, dy * b
                rx = ox * math.cos(spin) - oy * math.sin(spin)
                ry = ox * math.sin(spin) + oy * math.cos(spin)
                cx, cy = sx + rx, sy + ry
                ax, ay = -dx * 8, -dy * 8                     # the two arms of the bracket, turned with it
                a1 = (cx + ax * math.cos(spin), cy + ax * math.sin(spin))
                a2 = (cx - ay * math.sin(spin), cy + ay * math.cos(spin))
                pygame.draw.line(surf, col, (cx, cy), a1, 2)
                pygame.draw.line(surf, col, (cx, cy), a2, 2)
            if t < 1.0 and overlay is not None:
                pygame.draw.circle(overlay, (*theme.CAUTION, int(60 * (1 - t))), (int(sx), int(sy)), int(b), 1)
            if sub:
                theme.text(surf, f"⌖ {sub}", (sx, sy + b + 6), col, 11, anchor="midtop")

    def _ordnance(self, surf: pygame.Surface, o: OrdnanceView, p: Pose, f: Faction | None,
                  overlay: pygame.Surface | None = None) -> None:
        cam = self.cam
        if not cam.visible(p[0], p[1], 20):
            return
        sx, sy = cam.to_screen(p[0], p[1])
        a = math.radians(p[2])
        if o.kind == "torpedo":
            col = f.torpedo_color if f is not None else theme.TORPEDO
            if overlay is not None:          # the glow of the warhead, pulsing faintly
                pulse = 0.8 + 0.2 * math.sin(self.clock * 14 + o.id)
                pygame.draw.circle(overlay, (*col, int(40 * pulse)), (int(sx), int(sy)), 9)
                pygame.draw.circle(overlay, (*theme.mix(col, (255, 255, 255), 0.5), int(85 * pulse)), (int(sx), int(sy)), 5)
            tail = min(28.0, 8 + o.speed * cam.zoom * 0.05)
            pygame.draw.line(surf, theme.dim(col, 0.45), (sx, sy), (sx - math.sin(a) * tail, sy + math.cos(a) * tail), 1)
            pts = [(sx + math.sin(a) * 4, sy - math.cos(a) * 4), (sx + math.cos(a) * 3, sy + math.sin(a) * 3),
                   (sx - math.sin(a) * 3, sy + math.cos(a) * 3), (sx - math.cos(a) * 3, sy - math.sin(a) * 3)]
            pygame.draw.polygon(surf, col if o.armed else theme.dim(col, 0.6), pts)
        else:
            col = f.torpedo_color if f is not None else theme.PROBE
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

    def _free_label_y(self, x: float, y: float, w: int, h: int) -> float:
        """Push a label down until it clears the labels already drawn this frame, so close ships stay legible."""
        r = pygame.Rect(int(x), int(y), w, h)
        for _ in range(12):
            hit = r.collidelist(self._label_rects)
            if hit < 0:
                break
            r.top = self._label_rects[hit].bottom + 1
        self._label_rects.append(r)
        return r.top

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
