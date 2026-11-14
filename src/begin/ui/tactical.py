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
from functools import partial
from typing import TYPE_CHECKING, Callable

import pygame

from ..content.schema import Faction
from ..core.angles import norm180
from ..content.schema import HullDef, ShipClass
from ..sim.events import CloakFlash, Detonation, Event, HullHit, SeekerLock, ShieldHit, ShipArrived, ShipStatusChanged
from ..sim.ship import SHIELD_FACINGS
from ..sim.observation import ContactView, Observation, OrdnanceView
from ..sim.ship import Ship
from . import theme
from .camera import Camera
from .blast import SHIELD as SHIELD_GLOW, Blast, HullHit as HitFlash, ShieldFlare
from .effects import Effects, Light, Spark
from .torpedo_art import draw_round, round_size
from .fleet_art import art_px, fleet_image, has_art
from .showpiece import SPRITE_CENTRE_Y, SPRITE_PX, ship_image, ship_lights
from .hulls import MIN_HULL_PX, draw_hull, hull_pixel_scale
from .starfield import Starfield
from . import gfx, stealth
from .hive_marks import HiveMark, adaptation_rings, critical_ring, dormant_veil, hive_mark

if TYPE_CHECKING:
    from ..sim.away import AwayOp

SHIELD_FLASH = 0.7        # seconds a shield hit shimmers
TRAIL_POINT = 0.25        # cycles between the points of an engine trail
TRAIL_BANDS = 4           # strokes per wake, each fainter toward the tail
LEADER_MIN, LEADER_PER_WARP = 10.0, 4.0   # pixels: a ship's velocity leader, at rest and per warp factor
SMOULDER_BELOW = 0.5      # hull fraction below which a ship trails sparks
SPRITE_MIN_K = 0.9         # pixels per hull unit at which a ship is drawn with her baked art
HULL_LIGHT_MAX = 0.8       # the most a hull is lit by weapon light (1 would wash her out)
LIT_CACHE = 96             # lit copies of ship art kept, keyed by the art and the light's colour step
_LIT: dict[tuple[pygame.Surface, tuple[int, ...]], pygame.Surface] = {}
SHOWPIECE = frozenset({"federation.hc"})     # the hand-built art (showpiece.py); the rest is fleet_art.py
TORP_TRAIL = 1.4          # cycles of exhaust a torpedo leaves behind it
TORP_TRAIL_POINT = 0.05   # cycles between the points of a torpedo trail
SEEKER_TRAIL = 4.0        # × a torpedo's trail: a plasma-seeker's winding path lingers [E]
LABEL_GROUP_PX = 40       # ships closer than this on screen share one name on the map
LOCK_TIME = 0.35          # seconds the target brackets take to close in
BLAST_MIN_PX = 12.0       # the fireball of the smallest ship on screen, pixels
COLLAPSE = (255, 120, 90)  # a shield giving way flares red
JOLT_FROM = 8.0           # hull damage in one blow that jolts the map (our ship only)
JOLT_MAX = 6.0            # pixels
INBOUND_RANGE = 9000.0    # an enemy round this close and heading for one of ours is marked as a threat
INBOUND_CONE = 14.0       # degrees either side of dead on
INCOMING_SOUND = 4500.0   # an inbound round this close is heard rushing in
ADAPT_NOTE = 0.25         # the target's name says how far her hive has adapted, past this [E]

Pose = tuple[float, float, float]  # x, y, course


def _k(length: float, zoom: float) -> float:
    """Pixels per hull design unit for a hull `length` world units long (as `hull_pixel_scale`)."""
    return max(length * zoom, MIN_HULL_PX) / 100.0


def _art(cls_id: str | None, length: float, course: float, k: float) -> pygame.Surface | None:
    """A class's baked art at a course and `k` pixels per hull unit, or None if she has none."""
    if cls_id in SHOWPIECE:
        return ship_image(round(course) % 360, round(k / SPRITE_PX, 2))
    if cls_id is not None and has_art(cls_id):
        return fleet_image(cls_id, round(course) % 360, round(k / art_px(length), 2))
    return None


@dataclass
class Wreck:
    """A ship destroyed: the blast stays where she died, and grows or shrinks as the view zooms."""
    blast: Blast
    x: float
    y: float
    length: float          # her hull, world units
    k0: float              # pixels per hull unit when she blew


@dataclass
class Strike:
    """A blow that got through to a ship's hull, on the side it came from, riding along with her."""
    hit: HitFlash
    ship: int
    x: float               # where she was, in case she's gone from view
    y: float
    bearing: float         # compass degrees from her centre toward the shot
    length: float
    k0: float
    delay: float = 0.0     # seconds until the beam that struck it gets there


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
    _overlay_used: pygame.Rect | None = None       # what was drawn on the overlay last frame, to clear
    _glow_used: pygame.Rect | None = None
    _glow: pygame.Surface | None = None
    _lights: list[Light] = field(default_factory=list)
    _label_rects: list[pygame.Rect] = field(default_factory=list)   # labels drawn this frame
    _range_tag: tuple[float, float] | None = None    # where 'phaser' goes by our range ring this frame
    _names: list[Callable[[], object]] = field(default_factory=list)   # ships' names, drawn after every hull
    _label_more: dict[int, int] = field(default_factory=dict)      # a group's named ship: how many more fly with her
    _label_quiet: set[int] = field(default_factory=set)            # ships named by their group's label this frame
    _label_reach: dict[int, float] = field(default_factory=dict)   # a group's named ship: screen x of its right-most ship
    torp_trails: dict[int, list[tuple[float, float, float]]] = field(default_factory=dict)   # round -> [(x, y, time)]
    clock: float = 0.0                       # wall-clock seconds, for animation
    _lock: tuple[int | None, float] = (None, 0.0)   # the target the brackets are on, and when they started closing
    wrecks: list[Wreck] = field(default_factory=list)
    strikes: list[Strike] = field(default_factory=list)
    jolt: bool = True                        # the map gives a small jolt when our ship takes a heavy blow
    _shake: float = 0.0                      # pixels the map is jolting by right now
    _jolts: list[list[float]] = field(default_factory=list)   # [seconds until it lands, pixels]
    _player: int | None = None               # our ship, as last drawn
    _warned: set[int] = field(default_factory=set)   # enemy rounds we've already heard coming
    _rng: random.Random = field(default_factory=lambda: random.Random(11))
    _last: dict[int, tuple[float, float, float, HullDef | None, str | None, bool]] = field(default_factory=dict)  # as last drawn
    _flicker: dict[int, float] = field(default_factory=dict)        # our ship: when she last fired through her cloak
    _cloak_flashes: list[tuple[float, float, float]] = field(default_factory=list)   # (x, y, when) another fired from one
    _solutions: dict[int, tuple[float, float]] = field(default_factory=dict)  # [E] seeker hit her: (when, how long)

    def ingest(self, events: list[Event], obs: Observation) -> None:
        visible = {s.id for s in obs.own_ships(alive_only=False)} | {c.id for c in obs.contacts().values() if c.visible}
        friendly = {s.id for s in obs.own_ships(alive_only=False)}
        self.effects.ingest(events, obs.side, visible, friendly, lambda sid: faction_seen(obs, sid),
                            lambda sid: self._body(obs, sid))
        fresh: list[Wreck] = []
        for ev in events:
            if isinstance(ev, ShieldHit) and ev.ship_id in visible:
                power = 0.35 + 0.65 * min(1.0, (ev.absorbed + ev.penetrated) / 40.0)
                # a phaser's blow lights the shield when its beam gets there, not when the bank fires
                wait = self.effects.landing.get((ev.attacker, ev.ship_id), 0.0) if ev.attacker is not None else 0.0
                self.shield_flashes.setdefault(ev.ship_id, []).append(
                    [float(ev.sector), -wait, power, 1.0 if ev.collapsed else 0.0, ev.strength])
                if ev.collapsed:
                    self._collapse(obs, ev.ship_id, ev.sector, wait)
                    if ev.ship_id == self._player:
                        self._jolts.append([wait, 2.5])
            elif isinstance(ev, HullHit) and ev.ship_id in visible and ev.amount > 0:
                self._strike(obs, ev)
                if ev.ship_id == self._player and ev.amount >= JOLT_FROM:
                    wait = self.effects.landing.get((ev.attacker, ev.ship_id), 0.0) if ev.attacker is not None else 0.0
                    self._jolts.append([wait, min(JOLT_MAX, 2.0 + ev.amount / 8.0)])
            elif isinstance(ev, ShipArrived):
                me = self._seen(obs, ev.ship_id)
                if me is not None:
                    col = theme.FRIEND if me[5] else theme.HOSTILE
                    self.effects.warp_in(ev.origin[0], ev.origin[1], me[0], me[1], theme.mix(col, (255, 255, 255), 0.3))
            elif isinstance(ev, SeekerLock):
                if ev.ship_id in friendly:                  # our seeker hit her: the firing window opens
                    self._solutions[ev.target] = (self.clock, ev.cycles)
                    me = self._seen(obs, ev.target)
                    if me is not None:
                        self._sounds.append(("lock", me[0], me[1]))
            elif isinstance(ev, CloakFlash):
                if ev.ship_id in friendly:
                    self._flicker[ev.ship_id] = self.clock
                else:
                    self._cloak_flashes.append((ev.x, ev.y, self.clock))
                    self._sounds.append(("cloak", ev.x, ev.y))
            elif isinstance(ev, ShipStatusChanged) and ev.status == "destroyed":
                w = self._wreck(ev.ship_id)
                if w is not None:
                    fresh.append(w)
            elif isinstance(ev, Detonation) and ev.source in ("ship", "destruct") and fresh:
                # the breakup goes off where she really was, which sensors may only have had roughly
                w = min(fresh, key=lambda w: math.hypot(w.x - ev.x, w.y - ev.y))
                w.x, w.y = ev.x, ev.y
                fresh.remove(w)

    def _body(self, obs: Observation, sid: int | None) -> tuple[float, float, float] | None:
        """Where we see a ship and how long she is: (x, y, hull length), for effects that land on her."""
        me = self._seen(obs, sid)
        if me is None:
            return None
        return me[0], me[1], me[3].length if me[3] is not None else 200.0

    def _collapse(self, obs: Observation, sid: int, sector: int, wait: float) -> None:
        """A shield facing giving way: its arc bursts into sparks that scatter outward."""
        me = self._seen(obs, sid)
        if me is None:
            return
        x, y, course, hull, _, _ = me
        length = hull.length if hull is not None else 200.0
        facing = math.radians(course + SHIELD_FACINGS[sector % len(SHIELD_FACINGS)])
        for _ in range(16):
            a = facing + self._rng.uniform(-0.5, 0.5)
            r = length * 0.62
            sp = length * self._rng.uniform(0.4, 1.1)
            spark = Spark(x + math.sin(a) * r, y + math.cos(a) * r, math.sin(a) * sp, math.cos(a) * sp,
                          self._rng.choice((COLLAPSE, (255, 220, 200), SHIELD_GLOW)), self._rng.uniform(0.3, 0.7))
            spark.age = -wait
            self.effects.sparks.append(spark)

    @staticmethod
    def _seen(obs: Observation, sid: int | None) -> tuple[float, float, float, HullDef | None, str | None, bool] | None:
        """Where we see a ship: (x, y, course, hull, class, ours), or None."""
        if sid is None:
            return None
        own = obs.own(sid)
        if own is not None:
            return own.x, own.y, own.course, own.cls.hull, own.cls.id, True
        c = obs.contact(sid)
        if c is None:
            return None
        return c.x, c.y, c.course, c.cls.hull if c.cls is not None else None, c.cls.id if c.cls is not None else None, False

    def _strike(self, obs: Observation, ev: HullHit) -> None:
        me = self._seen(obs, ev.ship_id)
        if me is None:
            return
        x, y, _, hull, _, _ = me
        them = self._seen(obs, ev.attacker)
        bearing = math.degrees(math.atan2(them[0] - x, them[1] - y)) if them is not None else self._rng.uniform(0, 360)
        length = hull.length if hull is not None else 200.0
        k0 = _k(length, self.cam.zoom)
        hit = HitFlash(0.0, 0.0, k0 * (9.0 + 9.0 * min(1.0, ev.amount / 40.0)))
        hit.start(self._rng)
        wait = self.effects.landing.get((ev.attacker, ev.ship_id), 0.0) if ev.attacker is not None else 0.0
        self.strikes.append(Strike(hit, ev.ship_id, x, y, bearing, length, k0, wait))

    def _wreck(self, sid: int) -> Wreck | None:
        seen = self._last.pop(sid, None)          # a ship destroyed has already dropped off sensors: where we last saw her
        if seen is None:
            return None
        x, y, course, hull, cls_id, ours = seen
        length = hull.length if hull is not None else 200.0
        k0 = _k(length, self.cam.zoom)
        image: pygame.Surface | None = None
        if k0 >= SPRITE_MIN_K:
            image = _art(hull.class_id if hull is not None else cls_id, length, course, k0)
        if image is None and hull is not None:      # her outline, filled in, to be torn apart
            size = int(110 * k0) + 4
            image = gfx.Surface((size, size), pygame.SRCALPHA)
            draw_hull(image, hull, size / 2, size / 2, course, k0, theme.FRIEND if ours else theme.HOSTILE, fill_alpha=0.6)
        blast = Blast(0.0, 0.0, max(BLAST_MIN_PX, 30.0 * k0), seed=self._rng.randrange(1 << 30))
        blast.start(image)
        w = Wreck(blast, x, y, length, k0)
        self.wrecks.append(w)
        return w

    def update(self, dt: float) -> None:
        self.clock += dt
        self._shake *= math.exp(-9.0 * dt)
        for j in self._jolts:
            j[0] -= dt
            if j[0] <= 0:
                self._shake = max(self._shake, j[1])
        self._jolts = [j for j in self._jolts if j[0] > 0]
        self.effects.update(dt)
        for w in self.wrecks:
            w.blast.update(dt)
        self.wrecks = [w for w in self.wrecks if not w.blast.done]
        for st in self.strikes:
            if st.delay > 0:
                st.delay -= dt
                continue
            st.hit.update(dt)
        self.strikes = [st for st in self.strikes if not st.hit.done]
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
        self._player = player_id
        cam = self.cam
        if self.jolt and self._shake > 0.3:   # a heavy blow on our ship: the picture jumps, then settles
            jx = self._rng.uniform(-1, 1) * self._shake / cam.zoom
            jy = self._rng.uniform(-1, 1) * self._shake / cam.zoom
            try:
                cam.cx, cam.cy = cam.cx + jx, cam.cy + jy
                self._draw(surf, obs, prev, now, alpha, player_id, target_id, selected_sub, selected_ally, (jx, jy))
            finally:
                cam.cx, cam.cy = cam.cx - jx, cam.cy - jy     # the rest of the screen stays put
            return
        self._draw(surf, obs, prev, now, alpha, player_id, target_id, selected_sub, selected_ally, (0.0, 0.0))

    def _draw(self, surf: pygame.Surface, obs: Observation, prev: Snapshot | None, now: Snapshot, alpha: float,  # noqa: C901
              player_id: int | None, target_id: int | None, selected_sub: str | None, selected_ally: int | None,
              jolt: tuple[float, float]) -> None:
        cam = self.cam
        r = cam.rect
        gfx.set_stage(r)
        self._lights = self.effects.lights(cam) if gfx.LIGHTING else []
        if self._overlay is None or self._overlay.get_size() != surf.get_size():
            self._overlay = gfx.Surface(surf.get_size(), pygame.SRCALPHA)
            gfx.track(self._overlay)
            self._overlay_used = pygame.Rect(r)
        overlay = self._overlay
        # the overlay is mostly empty: only what was drawn on it last frame is cleared, only what is drawn now is added
        if self._overlay_used is not None:
            overlay.fill((0, 0, 0, 0), self._overlay_used.clip(r))
        gfx.take_dirty(overlay)
        self._label_rects = []
        self._range_tag = None
        self._names = []
        self._burning = []
        clip = surf.get_clip()
        surf.set_clip(r)

        def pose(sid: int) -> Pose | None:
            b = now.ships.get(sid)
            if b is None:
                return None
            return lerp_pose(prev.ships.get(sid) if prev else None, b, alpha)

        me = obs.own(player_id) if player_id is not None else None
        if me is not None and cam.follow == me.id:
            p = pose(me.id)
            if p:
                cam.cx, cam.cy = p[0] + jolt[0], p[1] + jolt[1]

        self.stars.backdrop(surf, r, cam.cx, cam.cy, theme.BG)
        self._starfield(surf)
        self._grid(surf)
        self._trails(overlay, obs, pose)
        self._plasma(overlay, obs, pose)
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
                self._torp_trail(overlay, o.id, p, obs.time, f, theme.EXHAUST if o.follow is not None else None)
                if not o.friendly:
                    near = self._inbound(obs, p)
                    if near is not None:
                        self._threat(surf, overlay, o, p)
                        if near < INCOMING_SOUND and o.id not in self._warned:
                            self._warned.add(o.id)            # heard once per round, as it closes
                            self._sounds.append(("incoming", p[0], p[1]))
            self._ordnance(surf, o, p, f, overlay)
        for oid in [k for k in self.torp_trails if k not in live]:
            del self.torp_trails[oid]
        self._warned &= live

        names = {s.id: s.name for s in obs.own_ships(alive_only=False)}
        names.update({c.id: c.label if c.identified else f"#{c.id}" for c in obs.contacts().values()})
        self._links(surf, overlay, obs, pose, player_id, selected_ally)

        # ships
        self._label_more, self._label_quiet, self._label_reach = {}, set(), {}
        allies = [(s.id, pose(s.id)) for s in obs.own_ships(alive_only=False) if s.exists and s.alive and not s.cloaked]
        self._group_labels([(sid, p) for sid, p in allies if p], {player_id, selected_ally})
        for s in obs.own_ships(alive_only=False):
            if not s.exists:
                continue
            p = pose(s.id)
            if p:
                self._own_ship(surf, overlay, s, p, s.id == player_id, obs, s.id == selected_ally, names)
        contacts = [(c, p) for c in obs.contacts().values() if (p := pose(c.id))]
        self._group_labels([(c.id, p) for c, p in contacts if c.visible], {target_id})
        for c, p in contacts:
            mark = hive_mark(obs, c.id, player_id) if c.identified else None
            self._contact(surf, c, p, c.id == target_id, selected_sub, overlay, mark)
        for name in self._names:
            name()
        self._names = []
        self._range_label(surf)
        for sid, x, y, left, reach in obs.countdowns():      # a ship about to go up: how far the blast will reach
            if cam.visible(x, y, reach + 100):
                sx, sy = cam.to_screen(x, y)
                critical_ring(surf, overlay, sx, sy, reach * cam.zoom, left, self.clock,
                              "CORE CRITICAL" if obs.is_hive(sid) else "SELF-DESTRUCT")

        # target link
        if me is not None and target_id is not None:
            pm, pt = pose(me.id), pose(target_id)
            if pm and pt:
                self._dashed(surf, theme.dim(theme.HOSTILE, 0.75), cam.to_screen(pm[0], pm[1]), cam.to_screen(pt[0], pt[1]), 6, 6)

        self._ripples(obs, pose)
        glow = None
        if self.effects.beams:            # soft light of the shots in flight, added on in one go
            if self._glow is None or self._glow.get_size() != surf.get_size():
                self._glow = gfx.Surface(surf.get_size())
                gfx.track(self._glow)
                self._glow_used = pygame.Rect(r)
            glow = self._glow
            if self._glow_used is not None:
                glow.fill((0, 0, 0), self._glow_used.clip(r))
            gfx.take_dirty(glow)
        self.effects.draw(surf, cam, overlay, glow)
        if glow is not None:
            self._glow_used = lit = gfx.take_dirty(glow)
            if lit is not None and (lit := lit.clip(r)).w > 0:
                surf.blit(glow, lit.topleft, area=lit, special_flags=pygame.BLEND_RGB_ADD)
                gfx.offer_light(glow, lit)
        self._fire(surf, pose)
        self._overlay_used = used = gfx.take_dirty(overlay)
        if used is not None and (used := used.clip(r)).w > 0:
            surf.blit(overlay, used.topleft, area=used)
        self._scale_bar(surf)
        gfx.draw.rect(surf, theme.border(), r, 1)
        surf.set_clip(clip)

    def _fire(self, surf: pygame.Surface, pose: Callable[[int], Pose | None]) -> None:
        """Ships blowing up and blows landing on hulls: burning pieces, then their light added onto the map."""
        cam = self.cam
        for w in self.wrecks:
            if not cam.visible(w.x, w.y, 400):
                continue
            s = max(BLAST_MIN_PX, 30.0 * _k(w.length, cam.zoom)) / w.blast.radius
            w.blast.x, w.blast.y = cam.to_screen(w.x, w.y)
            w.blast.draw_pieces(surf, s)
            w.blast.draw(surf, s)
        for st in self.strikes:
            p = pose(st.ship)
            if p is not None:
                st.x, st.y = p[0], p[1]
            if st.delay > 0 or not cam.visible(st.x, st.y, 100):
                continue
            k = _k(st.length, cam.zoom)
            sx, sy = cam.to_screen(st.x, st.y)
            a = math.radians(st.bearing)
            st.hit.x, st.hit.y = sx + math.sin(a) * 22 * k, sy - math.cos(a) * 22 * k
            st.hit.draw(surf, k / st.k0)

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
                    gfx.draw.lines(overlay, (*wake, alpha), False, path[lo:hi + 1], 2 if band == TRAIL_BANDS - 1 else 1)

    def _plasma(self, overlay: pygame.Surface, obs: Observation, pose: Callable[[int], Pose | None]) -> None:
        """Warp plasma [E]: the trails our sensors can follow, ours that the enemy can, the seekers hunting along
        them, and the shiver where a ship fired from her cloak."""
        cam = self.cam
        seen = obs.plasma()
        for sid, pts in seen.items():
            stealth.plasma_trail(overlay, cam, pts, obs.plasma_fresh, self.clock, sid)
        for sid, pts in obs.venting().items():
            stealth.plasma_trail(overlay, cam, pts, obs.plasma_fresh, self.clock, sid, own=True)
        for o in obs.ordnance():
            if o.follow is not None and (p := pose(o.id)) is not None:
                stealth.scent(overlay, cam, seen.get(o.follow, []), (p[0], p[1]), self.clock)
        self._cloak_flashes = [f for f in self._cloak_flashes if self.clock - f[2] < stealth.FLICKER]
        for x, y, when in self._cloak_flashes:
            if cam.visible(x, y, 100):
                sx, sy = cam.to_screen(x, y)
                stealth.fire_flash(overlay, sx, sy, max(14.0, 60 * _k(300.0, cam.zoom)), self.clock - when)

    def _torp_trail(self, overlay: pygame.Surface, oid: int, p: Pose, now: float, f: Faction | None,
                    seeker: theme.Color | None = None) -> None:
        """The exhaust a torpedo leaves: a short streak that fades out behind it. A plasma-seeker's is longer and
        takes the colour of the plasma it is following, so its winding path stays on the map a while."""
        span = TORP_TRAIL * (SEEKER_TRAIL if seeker is not None else 1.0)
        pts = self.torp_trails.setdefault(oid, [])
        if pts and now < pts[-1][2]:
            pts.clear()
        if not pts or now - pts[-1][2] >= TORP_TRAIL_POINT:
            pts.append((p[0], p[1], now))
        while pts and now - pts[0][2] > span:
            pts.pop(0)
        cam = self.cam
        if len(pts) < 2 or not cam.visible(p[0], p[1], 300):
            return
        col = seeker or (f.torpedo_color if f is not None else theme.TORPEDO)
        path = [cam.to_screen(x, y) for x, y, _ in pts] + [cam.to_screen(p[0], p[1])]
        n = len(path) - 1
        for i in range(n):                    # a faint thread, fainter the older it is
            k = (i + 1) / n
            gfx.draw.aaline(overlay, (*col, int((110 if seeker else 70) * k * k)), path[i], path[i + 1],
                            1.2 if seeker else 0.75)   # a hair-thin thread
        warm = theme.mix(col, (255, 255, 255), 0.35)
        for i, (x, y, born) in enumerate(pts):   # and a stream of sparks that drift apart and fade
            age = now - born
            k = max(0.0, 1.0 - age / span)
            if k <= 0.05:
                continue
            q = path[i]
            jit = (age * 9.0 + 1.0)
            h = (oid * 92821 + i * 68917) & 0xFFFF
            dx = ((h & 0xFF) / 255.0 - 0.5) * jit
            dy = ((h >> 8) / 255.0 - 0.5) * jit
            gfx.draw.circle(overlay, (*warm, int(190 * k * k)), (int(q[0] + dx), int(q[1] + dy)), 1 if k < 0.6 else 2)

    @staticmethod
    def _inbound(obs: Observation, p: Pose) -> float | None:
        """How far this round is from the nearest of our ships it is heading for, or None if it isn't a threat."""
        best: float | None = None
        for s in obs.own_ships():
            if not s.exists:
                continue
            dx, dy = s.x - p[0], s.y - p[1]
            d = math.hypot(dx, dy)
            if d > INBOUND_RANGE:
                continue
            if d < 1.0 or abs(norm180(math.degrees(math.atan2(dx, dy)) - p[2])) < INBOUND_CONE:
                best = d if best is None else min(best, d)
        return best

    def _threat(self, surf: pygame.Surface, overlay: pygame.Surface, o: OrdnanceView, p: Pose) -> None:
        """An enemy round inbound: its fuse radius ringed faintly on the map, or a marker at the edge if it's off screen."""
        cam = self.cam
        sx, sy = cam.to_screen(p[0], p[1])
        r = cam.rect
        beat = 0.6 + 0.4 * math.sin(self.clock * 8.0)
        if r.collidepoint(sx, sy):
            rad = o.prox * cam.zoom
            if 10 < rad < 1500:
                self._dashed_circle(overlay, (*theme.HOSTILE, int(70 * beat)), (sx, sy), rad, seg=24)
            return
        # off screen: a chevron on the edge of the map, pointing the way it is coming from
        cx, cy = r.center
        dx, dy = sx - cx, sy - cy
        span = max(abs(dx) / max(r.width / 2 - 14, 1), abs(dy) / max(r.height / 2 - 14, 1))
        if span <= 0:
            return
        ex, ey = cx + dx / span, cy + dy / span
        ang = math.atan2(dy, dx)
        tip = (ex + math.cos(ang) * 6, ey + math.sin(ang) * 6)
        left = (ex + math.cos(ang + 2.5) * 8, ey + math.sin(ang + 2.5) * 8)
        right = (ex + math.cos(ang - 2.5) * 8, ey + math.sin(ang - 2.5) * 8)
        notch = (ex - math.cos(ang) * 2, ey - math.sin(ang) * 2)
        gfx.draw.polygon(surf, theme.mix(theme.BG, theme.HOSTILE, 0.5 + 0.5 * beat), (tip, left, notch, right))

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
            surf.fill(theme.GRID_MAJOR if major else theme.GRID, (int(sx), r.top, 1, r.height))
            gx += spacing
        gy = math.floor(y0 / spacing) * spacing
        while gy <= y1:
            _, sy = cam.to_screen(0, gy)
            major = abs(gy / spacing) % 5 < 1e-6
            surf.fill(theme.GRID_MAJOR if major else theme.GRID, (r.left, int(sy), r.width, 1))
            gy += spacing

    def _scale_bar(self, surf: pygame.Surface) -> None:
        cam = self.cam
        r = cam.rect
        for units in (500, 1000, 2000, 5000, 10000, 20000, 50000):
            px = units * cam.zoom
            if px >= 70:
                break
        x, y = r.left + 16, r.bottom - 18
        gfx.draw.line(surf, theme.TEXT_DIM, (x, y), (x + px, y))
        gfx.draw.line(surf, theme.TEXT_DIM, (x, y - 4), (x, y + 2))
        gfx.draw.line(surf, theme.TEXT_DIM, (x + px, y - 4), (x + px, y + 2))
        theme.text(surf, f"{units:,}", (x + px + 6, y - 7), theme.TEXT_DIM, 11, "mono")

    def _later(self, draw: Callable[..., object], *args: object, **kw: object) -> None:
        """A ship's name (or a line under it), drawn once every hull is down, so a neighbour's hull never covers it."""
        self._names.append(partial(draw, *args, **kw))

    def _range_label(self, surf: pygame.Surface) -> None:
        """'phaser' by our weapons' range ring, unless a ship's name is already there."""
        if self._range_tag is None:
            return
        x, y = self._range_tag
        box = pygame.Rect(int(x), int(y), theme.text_width("phaser", 10), 14)
        if box.collidelist(self._label_rects) < 0:
            theme.text(surf, "phaser", (x, y), theme.dim(theme.FRIEND, 0.6), 10)

    def _ranges(self, surf: pygame.Surface, overlay: pygame.Surface, me: Ship, p: Pose) -> None:
        cam = self.cam
        sx, sy = cam.to_screen(p[0], p[1])
        rr = me.cls.banks_range * cam.zoom
        if 12 < rr < 4000:
            self._dashed_circle(surf, theme.dim(theme.FRIEND, 0.45), (sx, sy), rr)
            self._range_tag = (sx + rr * 0.707 + 4, sy - rr * 0.707 - 6)   # named after the ships: see `_range_label`
        sr = me.sensor_range() * cam.zoom
        if 12 < sr < 6000:
            gfx.draw.circle(surf, theme.dim(theme.FRIEND, 0.22), (int(sx), int(sy)), int(sr), 1)
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
                gfx.draw.polygon(overlay, (*col, 18), pts)
                gfx.draw.polygon(overlay, (*col, 60), pts, 1)

    def _shield_ring(self, surf: pygame.Surface, ship_id: int, sx: float, sy: float, course: float, rad: float,
                     strengths: list[tuple[float, bool]] | None, overlay: pygame.Surface | None = None) -> None:
        flashes = {int(f[0]): f for f in self.shield_flashes.get(ship_id, []) if f[1] >= 0}   # <0: the beam isn't there yet
        for i, facing in enumerate(SHIELD_FACINGS):
            hit = flashes.get(i)
            fl = hit[1] if hit is not None else None
            if hit is not None and overlay is not None:
                self._shimmer(overlay, ship_id, i, sx, sy, course + facing, rad, hit)
                # the bubble itself lights up round the blow, added onto the map
                ShieldFlare(sx, sy, rad, rad, math.radians(course + facing - 90), 0.45 + 0.55 * hit[2],
                            hit[1], SHIELD_FLASH, COLLAPSE if hit[3] > 0 else SHIELD_GLOW).draw(surf)
            if strengths is None and fl is None:
                continue
            if strengths is not None:
                st, up = strengths[i] if i < len(strengths) else (0.0, False)
                if not up:
                    continue
                col = theme.mix(theme.ALERT, theme.SHIELD, st / 100.0)
                col = theme.dim(col, 0.55)
            elif hit is not None and len(hit) > 4:
                col = theme.mix(theme.ALERT, theme.SHIELD, max(0.0, min(100.0, hit[4])) / 100.0)  # as weak as she is
            else:
                col = theme.SHIELD
            if fl is not None:
                col = theme.mix((255, 255, 255), col, fl / SHIELD_FLASH)
            a0 = math.radians(90 - (course + facing + 26))
            a1 = math.radians(90 - (course + facing - 26))
            rect = pygame.Rect(0, 0, rad * 2, rad * 2)
            rect.center = (int(sx), int(sy))
            gfx.draw.arc(surf, col, rect, a0, a1, 2 if fl is None else 3)

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
                            gfx.draw.arc(overlay, (*col, alpha), rect, b0, b0 + (a1 - a0) / 4, 2)
                else:
                    gfx.draw.arc(overlay, (*col, alpha), rect, a0, a1, 2 if k == 0 else 1)
        rng = random.Random(ship_id * 31 + sector * 7 + int(age * 24))
        for _ in range(int(3 + 5 * power)):
            b = math.radians(facing + rng.uniform(-20, 20))
            r = rad + rng.uniform(-1.5, 4.0 + 6 * t)
            alpha = int(220 * fade * rng.uniform(0.4, 1.0))
            if alpha > 4:
                gfx.draw.circle(overlay, (255, 255, 255, alpha), (int(sx + math.sin(b) * r), int(sy - math.cos(b) * r)), 1)

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
    def _placed(cls: ShipClass, sx: float, sy: float, course: float,
                k: float) -> tuple[pygame.Surface, pygame.Rect, float, float] | None:
        """A ship's baked art and where it goes on screen (with the centre it turns about), or None: no art."""
        cls_id = cls.hull.class_id                 # a class built on another's hull wears its art
        img = _art(cls_id, cls.hull.length, course, k)
        if img is None:
            return None
        if cls_id not in SHOWPIECE:                # fleet art is centred on the hull origin
            return img, img.get_rect(center=(int(sx), int(sy))), sx, sy
        a = math.radians(course)
        off = -SPRITE_CENTRE_Y * k                 # the sprite's centre sits a little aft of the hull origin
        cx, cy = sx - math.sin(a) * off, sy + math.cos(a) * off
        return img, img.get_rect(center=(int(cx), int(cy))), cx, cy

    @staticmethod
    def _sprite(surf: pygame.Surface, cls: ShipClass, sx: float, sy: float, course: float,
                k: float) -> tuple[pygame.Surface, pygame.Rect] | None:
        """Close in, a ship is drawn with her baked art; returns the art and where it went (None: no art)."""
        placed = TacticalView._placed(cls, sx, sy, course, k)
        if placed is None:
            return None
        img, rect, cx, cy = placed
        surf.blit(img, rect)
        if cls.hull.class_id in SHOWPIECE:
            ship_lights(surf, cx, cy, round(course) % 360, round(k / SPRITE_PX, 2), pygame.time.get_ticks() / 1000.0)
        return img, rect

    def _light_on(self, sx: float, sy: float, size: float) -> tuple[theme.Color, float] | None:
        """The weapon light falling on a ship `size` pixels across at (sx, sy): its colour and strength."""
        r = g = b = tot = 0.0
        for lt in self._lights:
            d = max(0.0, math.hypot(lt.x - sx, lt.y - sy) - size * 0.5)
            if d >= lt.reach:
                continue
            f = lt.k * (1.0 - d / lt.reach) ** 2
            r += lt.color[0] * f
            g += lt.color[1] * f
            b += lt.color[2] * f
            tot += f
        if tot < 0.04:
            return None
        return (int(r / tot), int(g / tot), int(b / tot)), min(HULL_LIGHT_MAX, tot)

    @staticmethod
    def _light_art(surf: pygame.Surface, art: tuple[pygame.Surface, pygame.Rect],
                   light: tuple[theme.Color, float] | None) -> None:
        """Baked art catching the light: the art again, tinted by the light and added on, only where it is."""
        if light is None:
            return
        img, rect = art
        col, amount = light
        c = tuple(min(255, int(v * amount * 0.75)) // 8 * 8 for v in col)   # in steps, so a fading light reuses
        key = (img, c)
        lit = _LIT.get(key)
        if lit is None:
            tint = pygame.Surface(pygame.Surface.get_size(img), pygame.SRCALPHA, 32)   # physical pixels
            pygame.Surface.blit(tint, img, (0, 0), special_flags=pygame.BLEND_RGBA_MAX)
            pygame.Surface.fill(tint, (*c, 255), special_flags=pygame.BLEND_RGBA_MULT)
            lit = tint.premul_alpha()              # light only where the art is, however soft its edge
            if isinstance(img, gfx.Canvas):
                lit = gfx.adopt(lit, img.density)
            if len(_LIT) >= LIT_CACHE:
                _LIT.pop(next(iter(_LIT)))
            _LIT[key] = lit
        surf.blit(lit, rect, special_flags=pygame.BLEND_RGB_ADD)

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
            gfx.draw.polygon(overlay, (*col, alpha), pts)
        gfx.draw.line(overlay, (*col, 200), a, b, 1)

    def _own_ship(self, surf: pygame.Surface, overlay: pygame.Surface, s: Ship, p: Pose, is_player: bool,  # noqa: C901
                  obs: Observation, selected: bool = False, names: dict[int, str] | None = None) -> None:
        cam = self.cam
        if not cam.visible(p[0], p[1], 200):
            return
        sx, sy = cam.to_screen(p[0], p[1])
        k = hull_pixel_scale(s.cls.hull, cam.zoom)
        if s.alive and not s.cloaked:
            self._last[s.id] = (p[0], p[1], p[2], s.cls.hull, s.cls.id, True)
        color = theme.FRIEND if s.alive else theme.TEXT_FAINT
        if not is_player and s.alive:
            color = theme.ALLY
        if s.cloaked:
            color = theme.dim(color, 0.5)
        # velocity leader
        if s.warp > 0.05:
            self._velocity_leader(surf, sx, sy, p[2], s.warp, k, theme.dim(color, 0.5))
        if is_player and abs(norm180(s.desired_course - s.course)) > 1:
            a = math.radians(s.desired_course)
            L = 50 * k
            gfx.draw.line(surf, theme.dim(theme.CAUTION, 0.7), (sx, sy), (sx + math.sin(a) * L, sy - math.cos(a) * L), 1)
        light = self._light_on(sx, sy, 100 * k) if s.alive and not s.cloaked else None
        if s.alive and s.cloaked:
            art = self._under_cloak(surf, overlay, s, sx, sy, p[2], k, color)
        else:
            drawn = self._sprite(surf, s.cls, sx, sy, p[2], k) if s.alive and k >= SPRITE_MIN_K else None
            art = drawn is not None
            if drawn is None:
                drawn = draw_hull(surf, s.cls.hull, sx, sy, p[2], k, color)
            if drawn is not None:
                self._light_art(surf, drawn, light)
        strengths = [(sh.effective if not sh.destroyed else 0.0, sh.up and not sh.destroyed and sh.effective > 0.5)
                     for sh in s.shields]
        self._shield_ring(surf, s.id, sx, sy, p[2], 62 * k, strengths, overlay)
        if s.alive and s.structure < s.structure_max * SMOULDER_BELOW:
            self._burning.append((p[0], p[1], s.structure / s.structure_max))
        op = next((o for o in obs.away_ops() if o.shuttle == s.id), None) if s.alive and s.cls.craft else None
        if op is not None and op.phase == "aboard":
            return                     # latched to the hive ship's hull: the activity panel tells their story
        label = s.name if s.alive else f"{s.name} — {s.status.value}"
        if s.alive and s.docked_to is not None:
            label += " · docked"
        if s.id in self._label_more:
            label += f"  +{self._label_more[s.id]}"
        if s.id in self._label_quiet:
            return                     # named by her group's label (never the selected ship: she keeps her own)
        lx = max(sx, self._label_reach.get(s.id, sx)) + (62 * k + 12 if art else 34 * k + 6)   # clear of her art (and her group's)
        lw = theme.text_width(label, 12, weight="medium")
        if lx + lw > cam.rect.right - 6:                    # no room on the right: her name goes on the left
            lx = sx - (62 * k + 12 if art else 34 * k + 6) - lw
        place = self._label_x(sx, sy, lx, lw)
        if place is not None:
            lx = place
            # our own ship's name carries her warp (and a cloak or a leak) on a line below: room is kept for it
            tall = 26 + (12 if obs.leaking(s.id) else 0) if is_player else 26 if op is not None else 14
            top = self._free_label_y(lx, sy - 8, max(lw, 90) if is_player else lw, tall)
            if art:
                self._leader(surf, sx, sy, 62 * k, lx if lx > sx else lx + lw, top, color)
            self._later(theme.label, surf, label, (lx, top), color, 12)
            ly = top + 14
            room = int(cam.rect.right - 4 - lx)
            if is_player:
                self._later(theme.text, surf, f"w{s.warp:.1f}", (lx, ly), theme.TEXT_DIM, 10, "mono")
                if s.alive and s.cloaked:
                    self._later(theme.text, surf, "CLOAKED", (lx + theme.text_width(f"w{s.warp:.1f}", 10, "mono") + 8, ly),
                               theme.CLOAK, 10, weight="semibold")
                ly += 12
                if obs.leaking(s.id):
                    self._later(theme.text, surf, theme.fit("venting plasma", 10, room), (lx, ly), theme.EXHAUST, 10)
                    ly += 12
            elif op is not None:
                self._shuttle_lines(surf, op, lx, ly, room, names or {})
                ly += 12
            elif s.alive:
                st = obs.ally_order(s.id)
                mission = st.summary(names or {}) if st is not None else ""
                if mission:
                    self._later(theme.text, surf, theme.fit(mission, 10, room), (lx, ly),
                               theme.TEXT_FAINT if not selected else theme.TEXT_DIM, 10)
                    ly += 12
            if s.alive and s.boarders > 0 and s.boarder_side != s.side:
                self._later(theme.text, surf, theme.fit(f"boarders aboard: {s.boarders}", 10, room, weight="medium"), (lx, ly),
                           theme.ALERT, 10, weight="medium")
        if selected:
            b = 62 * k + 8
            for dx, dy in ((-1, -1), (1, -1), (-1, 1), (1, 1)):
                cx, cy = sx + dx * b, sy + dy * b
                gfx.draw.line(surf, theme.ALLY, (cx, cy), (cx - dx * 7, cy), 1)
                gfx.draw.line(surf, theme.ALLY, (cx, cy), (cx, cy - dy * 7), 1)

    def _under_cloak(self, surf: pygame.Surface, overlay: pygame.Surface, s: Ship, sx: float, sy: float, course: float,
                 k: float, color: theme.Color) -> bool:
        """One of ours under her cloak [E]: her art faint and swaying, the field turning round her, and for a
        moment after she fires through it, almost all of her. True when her art was drawn."""
        since = self.clock - self._flicker.get(s.id, -1e9)
        flicker = max(0.0, 1.0 - since / stealth.FLICKER) ** 2
        rad = 62 * k
        stealth.cloak_field(overlay, sx, sy, rad, self.clock, flicker)
        placed = self._placed(s.cls, sx, sy, course, k) if k >= SPRITE_MIN_K else None
        if placed is None:
            draw_hull(surf, s.cls.hull, sx, sy, course, k, theme.mix(color, theme.CLOAK, 0.6), fill_alpha=0.08 + 0.3 * flicker)
            return False
        stealth.cloaked_art(surf, placed[0], placed[1], self.clock, flicker)
        return True

    def _group_labels(self, ships: list[tuple[int, Pose]], keep: set[int | None]) -> None:
        """Ships flying in close formation share one name on the map ("Bismark (BC)  +2") instead of a pile of
        names over each other. The ships in `keep` (the target, our own ship) always have their own name, and
        zooming in pulls a group apart."""
        cam = self.cam
        pts = sorted((sid not in keep, sid, cam.to_screen(p[0], p[1])) for sid, p in ships if cam.visible(p[0], p[1], 0))
        placed: list[tuple[int, float, float]] = []      # (her group's named ship, x, y) for every ship so far
        for free, sid, (x, y) in pts:
            if free:     # a ship near any of a group joins it, so a line of ships becomes one group, not several
                near = next((lid for lid, px, py in placed
                             if lid not in keep and (x - px) ** 2 + (y - py) ** 2 < LABEL_GROUP_PX ** 2), None)
                if near is not None:
                    self._label_quiet.add(sid)
                    self._label_more[near] = self._label_more.get(near, 0) + 1
                    self._label_reach[near] = max(self._label_reach.get(near, x), x)
                    placed.append((near, x, y))
                    continue
            placed.append((sid, x, y))

    def _contact(self, surf: pygame.Surface, c: ContactView, p: Pose, targeted: bool, sub: str | None,  # noqa: C901
                 overlay: pygame.Surface | None = None, hive: HiveMark | None = None) -> None:
        cam = self.cam
        if not cam.visible(p[0], p[1], 200):
            return
        sx, sy = cam.to_screen(p[0], p[1])
        if c.visible:
            self._last[c.id] = (p[0], p[1], p[2], c.cls.hull if c.cls is not None else None,
                                c.cls.id if c.cls is not None else None, False)
        else:
            self._last.pop(c.id, None)
        color = theme.HOSTILE if c.identified else theme.UNKNOWN
        if not c.visible:
            color = theme.dim(color, 0.45)
        if c.cls is not None:
            k = hull_pixel_scale(c.cls.hull, cam.zoom)
            if c.warp > 0.05 and c.visible:
                self._velocity_leader(surf, sx, sy, p[2], c.warp, k, theme.dim(color, 0.45))
            light = self._light_on(sx, sy, 100 * k) if c.visible else None
            drawn = (self._sprite(surf, c.cls, sx, sy, p[2], k) if c.visible and c.identified and k >= SPRITE_MIN_K
                     else None)
            art = drawn is not None
            if drawn is None and not c.exhaust:        # placed only by her plasma: no outline, only the fix
                drawn = draw_hull(surf, c.cls.hull, sx, sy, p[2], k, color, fill_alpha=0.22 if c.visible else 0.08)
            if drawn is not None:
                self._light_art(surf, drawn, light)
            self._shield_ring(surf, c.id, sx, sy, p[2], 62 * k, None, overlay)
            hurt = (c.assessed.hull if c.assessed is not None and c.assessed.hull is not None
                    else c.scan.structure_frac if c.scan is not None else None)
            if c.visible and hurt is not None and hurt < SMOULDER_BELOW:
                self._burning.append((p[0], p[1], hurt))   # we've seen how badly she's hurt
            rad = 62 * k + 4 if art else 40 * k
        else:
            art = False
            rad = 10
            pts = [(sx, sy - rad), (sx + rad, sy), (sx, sy + rad), (sx - rad, sy)]
            gfx.draw.polygon(surf, color, pts, 1)
            theme.text(surf, "?", (sx, sy), color, 12, anchor="center")
        if hive is not None and c.visible and overlay is not None:
            if hive.dormant > 0:
                dormant_veil(overlay, sx, sy, rad, hive.dormant, self.clock)
            else:
                adaptation_rings(overlay, sx, sy, rad, hive, self.clock)
        if c.solution > 0 and overlay is not None:
            when, total = self._solutions.get(c.id, (-10.0, c.solution))
            stealth.firing_solution(surf, overlay, sx, sy, rad, c.solution, max(total, c.solution),
                                    self.clock - when, self.clock)
        if c.exhaust and overlay is not None:
            color = theme.EXHAUST
            stealth.exhaust_fix(surf, overlay, sx, sy, max(rad + 10, min(180.0, c.uncertainty * cam.zoom)), self.clock, c.id)
        elif not c.visible:
            self._dashed_circle(surf, theme.dim(color, 0.8), (sx, sy), rad + 6, seg=8)
        elif c.haze > 0:
            # beyond rated sensor range: the ring shows how far off the reported position may be
            ring = max(rad + 6, c.uncertainty * cam.zoom)
            self._dashed_circle(surf, theme.dim(color, 0.6), (sx, sy), int(ring), seg=12)
        label = c.label if c.identified else f"#{c.id}"
        if (c.visible and c.haze > 0) or c.exhaust:
            label = "~" + label
        if c.id in self._label_more:
            label += f"  +{self._label_more[c.id]}"
        lost = not c.visible
        lw = theme.text_width(label, 12, weight="medium")
        lx = max(sx, self._label_reach.get(c.id, sx)) + rad + (20 if c.solution > 0 else 8)   # clear of its brackets
        if lx + lw > cam.rect.right - 6:                    # no room on the right: the name goes on the left
            lx = sx - rad - 8 - lw
        place = self._label_x(sx, sy, lx, lw)
        quiet = c.id in self._label_quiet or place is None
        lx = place if place is not None else lx
        top = sy - 8 if quiet else self._free_label_y(lx, sy - 8, lw, 26 if lost or c.solution > 0 else 14)
        if art and not quiet:
            self._leader(surf, sx, sy, rad - 4, lx if lx > sx else lx + lw, top, color)
        if not quiet:
            self._later(theme.label, surf, label, (lx, top), color, 12)
        if c.solution > 0 and place is not None:
            self._later(theme.text, surf, f"FIRING SOLUTION · {c.solution:.0f}s", (lx, top + 14),
                       theme.mix(theme.EXHAUST, (255, 255, 255), 0.45), 10, weight="semibold")
        elif c.exhaust and place is not None:
            self._later(theme.text, surf, "EXHAUST · rough fix", (lx, top + 14), theme.EXHAUST, 10, weight="semibold")
        elif hive is not None and c.visible and place is not None and not quiet:
            note = self._hive_note(hive, targeted)
            if note:
                room = int(cam.rect.right - 4 - lx)
                self._later(theme.text, surf, theme.fit(note, 10, room), (lx, top + 14),
                           theme.HIVE if hive.dormant > 0 else theme.dim(theme.HIVE, 0.85), 10, weight="medium")
        elif lost and place is not None:
            self._later(theme.text, surf, f"lost {c.age:.0f}s", (lx, top + 14), theme.TEXT_FAINT, 10)
        if targeted:
            if self._lock[0] != c.id:
                self._lock = (c.id, self.clock)             # a new target: the brackets close in on it
                self._sounds.append(("lock", p[0], p[1]))
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
                gfx.draw.line(surf, col, (cx, cy), a1, 2)
                gfx.draw.line(surf, col, (cx, cy), a2, 2)
            if t < 1.0 and overlay is not None:
                gfx.draw.circle(overlay, (*theme.CAUTION, int(60 * (1 - t))), (int(sx), int(sy)), int(b), 1)
            if sub:
                theme.text(surf, f"⌖ {sub}", (sx, sy + b + 6), col, 11, anchor="midtop")

    @staticmethod
    def _hive_note(m: HiveMark, targeted: bool) -> str:
        """The line under a Borg ship's name: dark and when she wakes; for the target, what the hive has learned
        and where her relay is."""
        if m.dormant > 0:
            return f"DORMANT · wakes in {m.dormant:.0f}"
        if not targeted:
            return ""
        parts = []
        if max(m.phaser, m.torpedo) >= ADAPT_NOTE:
            parts.append(f"adapted: phasers {m.phaser * 100:.0f}% · torpedoes {m.torpedo * 100:.0f}%")
        if m.relay:
            parts.append(f"relay: {m.relay}")
        return "  ·  ".join(parts)

    def _ordnance(self, surf: pygame.Surface, o: OrdnanceView, p: Pose, f: Faction | None,
                  overlay: pygame.Surface | None = None) -> None:
        cam = self.cam
        if not cam.visible(p[0], p[1], 20):
            return
        sx, sy = cam.to_screen(p[0], p[1])
        if o.kind == "torpedo":
            col = f.torpedo_color if f is not None else theme.TORPEDO
            style = f.torpedo_style if f is not None else "photon"
            size = round_size(o.yield_, cam.zoom)
            if overlay is not None:
                draw_round(surf, overlay, sx, sy, p[2], col, style, size, self.clock, o.id, o.armed)
            tag = f"×{o.count}"
            if o.count > 1 and cam.rect.contains(pygame.Rect(int(sx + size * 2 + 4), int(sy - 6),
                                                             theme.text_width(tag, 10, "mono"), 14)):
                theme.text(surf, tag, (sx + size * 2 + 4, sy - 6), theme.dim(col, 0.9), 10, "mono")
        else:
            col = f.torpedo_color if f is not None else theme.PROBE
            gfx.draw.circle(surf, col, (int(sx), int(sy)), 4, 1)
            gfx.draw.circle(surf, col, (int(sx), int(sy)), 1)
            if o.code:
                theme.text(surf, o.code, (sx + 7, sy - 6), theme.dim(col, 0.9), 10, "mono")

    @staticmethod
    def _velocity_leader(surf: pygame.Surface, sx: float, sy: float, heading: float, warp: float, k: float,
                         col: theme.Color) -> None:
        """A short line ahead of a ship's bow, longer the faster she goes: enough to read her heading and pace at a
        glance, never so long that it reaches across her neighbours."""
        a = math.radians(heading)
        b = 56 * k                           # from just past her bow, so the line never draws over her
        L = LEADER_MIN + LEADER_PER_WARP * min(warp, 9.0)
        gfx.draw.line(surf, col, (sx + math.sin(a) * b, sy - math.cos(a) * b),
                      (sx + math.sin(a) * (b + L), sy - math.cos(a) * (b + L)))

    @staticmethod
    def _leader(surf: pygame.Surface, sx: float, sy: float, ring: float, lx: float, top: float, col: theme.Color) -> None:
        """A short line from a ship's shield ring out to her name, when the name has moved clear of her art."""
        a = math.atan2(top + 7 - sy, lx - sx)
        start = (sx + math.cos(a) * (ring + 2), sy + math.sin(a) * (ring + 2))
        end = (lx - 3, top + 7) if lx > sx else (lx + 3, top + 7)
        gfx.draw.line(surf, theme.dim(col, 0.5), start, end, 1)

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
            gfx.draw.line(surf, col, (a[0] + ux * d, a[1] + uy * d), (a[0] + ux * e, a[1] + uy * e))
            d = e + off

    def _shuttle_lines(self, surf: pygame.Surface, op: AwayOp, lx: float, ly: float, room: int,
                       names: dict[int, str]) -> None:
        """An away team's shuttle in flight: who is aboard, and what they are doing (`hail <shuttle>` reaches them)."""
        crew = ", ".join(m.capitalize() for m in op.members)
        where = names.get(op.target, "the hive ship")
        doing = {"outbound": f"crossing to {where}", "aboard": f"{op.label} aboard {where}",
                 "return": "coming home"}.get(op.phase, op.phase)
        col = theme.ALERT if op.noticed else theme.HIVE
        theme.text(surf, theme.fit(f"{crew} · {doing}", 10, room), (lx, ly), col, 10)

    def _label_x(self, sx: float, sy: float, lx: float, lw: int) -> float | None:
        """Where a ship's name goes across: kept whole inside the map when she is on it, and left out when she
        is off it (half a name cut by the map's edge is never drawn)."""
        area = self.cam.rect
        if not area.collidepoint(sx, sy):
            return None
        return max(area.left + 4, min(lx, area.right - 4 - lw))

    def _free_label_y(self, x: float, y: float, w: int, h: int) -> float:
        """Push a label down until it clears the labels already drawn this frame, so close ships stay legible."""
        area = self.cam.rect
        r = pygame.Rect(int(x), int(min(max(y, area.top + 2), area.bottom - h - 2)), w, h)
        for _ in range(12):
            hit = r.collidelist(self._label_rects)
            if hit < 0:
                break
            r.top = self._label_rects[hit].bottom + 1
        if r.bottom > area.bottom - 2:      # pushed off the bottom of the map: stack it above instead
            r.bottom = area.bottom - 2
            for _ in range(12):
                hit = r.collidelist(self._label_rects)
                if hit < 0:
                    break
                r.bottom = self._label_rects[hit].top - 1
        self._label_rects.append(r)
        return r.top

    @staticmethod
    def _dashed_circle(surf: pygame.Surface, col: theme.Color | tuple[int, int, int, int], c: tuple[float, float], r: float, seg: int | None = None) -> None:
        n = seg or max(16, min(120, int(r / 6)))
        for i in range(0, n, 2):
            a0 = 2 * math.pi * i / n
            a1 = 2 * math.pi * (i + 1) / n
            gfx.draw.line(surf, col, (c[0] + math.cos(a0) * r, c[1] + math.sin(a0) * r),
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
