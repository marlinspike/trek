"""Sensors, contacts, fog of war and active scans [R §11, E fusion and scans].

Each side keeps a contact table fed by every working sensor platform on
that side (ships and data probes). Lost contacts keep their last known
state; computers sophisticated enough (Starfleet) dead-reckon them.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..events import CloakFlash, ContactChanged, Message, ScanCompleted, Tone
from ..ship import Kind, Ship

if TYPE_CHECKING:
    from ..ordnance import Probe, Torpedo
    from ..world import World


@dataclass(slots=True)
class ScanRecord:
    tick: int
    shields: list[float]                 # estimated strength % per sector (-1 = down/destroyed)
    subsystems: dict[str, int]           # sid -> estimated damage %
    crew: int
    structure_frac: float
    charged_banks: int
    loaded_tubes: int
    probes_loaded: int
    confidence: float


@dataclass(slots=True)
class Assessment:
    """What a side has seen of a contact's condition from its own hits on it, kept current between scans."""

    tick: int
    shields: list[float | None]          # % per sector from the last hit on it (None = not hit yet)
    hull: float | None = None            # structure fraction, once a hit has got through
    power_out: bool = False              # her life support is failing: the crew has moments left


@dataclass(slots=True)
class Contact:
    ship_id: int
    visible: bool = False
    ever: bool = False
    x: float = 0.0
    y: float = 0.0
    vx: float = 0.0
    vy: float = 0.0
    course: float = 0.0
    warp: float = 0.0
    last_tick: int = 0
    identified: bool = False
    haze: float = 0.0            # 0 = exact (inside rated range) .. 1 = at the edge of what sensors can make out
    uncertainty: float = 0.0     # how far off the reported position may be, in world units
    scan: ScanRecord | None = None
    assessed: Assessment | None = None
    ghost: bool = False          # [E] lost to a cloak that leaves nothing to follow: no dead reckoning, the last fix only
    trail: int = -1              # [E] tick of the last fix from her leaking warp plasma (cloaked, drives damaged)


@dataclass(slots=True)
class SideIntel:
    side: int
    contacts: dict[int, Contact] = field(default_factory=dict)
    visible_ordnance: set[int] = field(default_factory=set)
    dead_reckoning: bool = False


def update_sensors(world: World) -> None:
    rules = world.rules
    ships = list(world.ships.values())
    for side, intel in world.intel.items():
        platforms: list[tuple[float, float, float]] = []
        best_soph = 0.0
        for s in ships:
            if s.side == side and s.alive:
                r = s.sensor_range()
                if r > 0:
                    platforms.append((s.x, s.y, r))
                best_soph = max(best_soph, s.sophistication)
        for p in world.probes:
            if p.side == side and p.spec.scan_range > 0:
                platforms.append((p.x, p.y, p.spec.scan_range))
        intel.dead_reckoning = best_soph >= 0.75

        for s in ships:
            if s.side == side or not s.exists:
                continue
            c = intel.contacts.get(s.id)
            if c is None:
                c = intel.contacts[s.id] = Contact(s.id)
            # [E] Starfleet-rated sensors: inside rated range any uncloaked ship is seen exactly and identified;
            # beyond it the return grows hazier until sensor_haze_limit × range, where it fades out. A cloaked
            # ship is not detected at all (until it gives itself away by firing).
            hidden = s.cloaked and s.reveal_time <= 0
            true_ratio = min((math.hypot(s.x - px, s.y - py) / r for px, py, r in platforms), default=math.inf)
            ratio = math.inf if hidden else true_ratio
            if s.solution > 0 and s.solution_side == side:
                hidden, ratio = False, min(true_ratio, 1.0)   # [E] a seeker's hit: her exact fix, whatever the range
            sweeping = any(o.side == side and o.sweep > 0 for o in ships)
            if hidden and leaking(s) and true_ratio <= (SWEEP_REACH if sweeping else 1.0):
                _trail_fix(world, side, c, s)        # her damaged nacelles leave a plasma trail [E]
            seen = ratio <= rules.sensor_haze_limit
            exact = ratio <= 1.0
            if seen:
                vx, vy = s.velocity(rules.units_per_warp)
                c.x, c.y, c.vx, c.vy = s.x, s.y, vx, vy
                c.haze = c.uncertainty = 0.0
                if not exact:
                    c.haze = (ratio - 1.0) / max(1e-6, rules.sensor_haze_limit - 1.0)
                    ex, ey = _haze_offset(world, side, s.id)
                    err = c.haze * rules.sensor_haze_error * _rated_range(platforms)
                    c.x, c.y = s.x + ex * err, s.y + ey * err
                    c.uncertainty = err
                c.course, c.warp, c.last_tick = s.course, s.warp, world.tick
                ident = exact
                c.identified = c.identified or ident
                if not c.visible:
                    c.visible = True
                    first = not c.ever
                    c.ever = True
                    world.emit(ContactChanged(world.tick, side, s.id, True))
                    if not first and side == world.player_side:
                        world.emit(Message(world.tick, f"Contact regained: {world.label(side, s.id)}.",
                                           Tone.CAUTION, visible_to=frozenset({side})))
            elif c.visible:
                c.ghost = s.cloaked and s.cls.cloak_fire and c.trail < world.tick
                c.visible = False
                world.emit(ContactChanged(world.tick, side, s.id, False))
                if side == world.player_side:
                    what = "cloaked" if s.cloaked else "out of sensor range"
                    world.emit(Message(world.tick, f"Lost contact with {world.label(side, s.id)} ({what}).",
                                       Tone.CAUTION, visible_to=frozenset({side})))

        vis: set[int] = set()
        ordnance: list[Torpedo | Probe] = [*world.torpedoes, *world.probes]
        for o in ordnance:
            if o.side == side:
                vis.add(o.id)
                continue
            for px, py, r in platforms:
                reach = r * rules.probe_reflect
                if (o.x - px) ** 2 + (o.y - py) ** 2 <= reach * reach:
                    vis.add(o.id)
                    break
        intel.visible_ordnance = vis


TRAIL_ERROR = 700.0          # how far off a fix from a plasma trail may be [E]
TRAIL_DAMAGE = 25            # % damage at which a warp drive starts to leak plasma [E]


PLASMA_LIFE = 40.0           # cycles a plasma trail lingers [E]
PLASMA_STEP = 0.5            # cycles between trail points
SWEEP_REACH = 1.6            # × rated sensor range: how far a science sweep follows plasma [E]


def update_plasma(world: World) -> None:
    """[E] Every leaking ship lays a trail of plasma; old trail fades away."""
    tpc = world.rules.ticks_per_cycle
    every = max(1, int(PLASMA_STEP * tpc))
    oldest = world.tick - int(PLASMA_LIFE * tpc)
    for sid in list(world.plasma):
        pts = [p for p in world.plasma[sid] if p[2] >= oldest]
        if pts and sid in world.ships:
            world.plasma[sid] = pts
        else:
            del world.plasma[sid]
    if world.tick % every:
        return
    for s in world.ships.values():
        if s.alive and leaking(s):
            world.plasma.setdefault(s.id, []).append((s.x, s.y, world.tick))


def plasma_seen(world: World, side: int) -> dict[int, list[tuple[float, float, int]]]:
    """[E] The plasma trails a side's sensors can make out: points inside rated sensor range of one of its ships
    (or inside a sweep's reach), for ships not on that side."""
    plats = []
    for s in world.ships.values():
        if s.side == side and s.alive and s.sensor_range() > 0:
            plats.append((s.x, s.y, s.sensor_range() * (SWEEP_REACH if s.sweep > 0 else 1.0)))
    out: dict[int, list[tuple[float, float, int]]] = {}
    for sid, pts in world.plasma.items():
        venting = world.ships.get(sid)
        if venting is None or venting.side == side:
            continue
        seen = [p for p in pts if any((p[0] - x) ** 2 + (p[1] - y) ** 2 <= r * r for x, y, r in plats)]
        if seen:
            out[sid] = seen
    return out


def leaking(ship: Ship) -> bool:
    """[E] A ship at warp with a damaged warp drive vents plasma that any sensor can follow, cloak or no cloak.
    Repairs stop it, and so does dropping below warp 1."""
    return ship.warp >= 1.0 and any(not d.destroyed and d.damage >= TRAIL_DAMAGE for d in ship.drives)


def _trail_fix(world: World, side: int, c: Contact, s: Ship) -> None:
    """A rough fix on a cloaked ship from her plasma trail: where she is, give or take TRAIL_ERROR, with her
    heading. It updates once a cycle and never makes her visible."""
    if c.trail >= 0 and world.tick - c.trail < world.rules.ticks_per_cycle:
        return
    ex, ey = _haze_offset(world, side, s.id)
    vx, vy = s.velocity(world.rules.units_per_warp)
    c.x, c.y, c.vx, c.vy = s.x + ex * TRAIL_ERROR, s.y + ey * TRAIL_ERROR, vx, vy
    c.course, c.warp, c.last_tick = s.course, s.warp, world.tick
    c.trail, c.ever, c.ghost = world.tick, True, False


def fired_from(world: World, ship: Ship, cycles: float | None = None) -> None:
    """A ship fired. A cloaked ship shows herself for a while [R]; one whose cloak is made to fire through (the
    Enterprise's refit) [E] drops it, fires and is gone again in the same moment: everyone sees the flash where she
    fired, and nothing after it."""
    reveal = world.rules.cloak_reveal_cycles if cycles is None else cycles
    if not (ship.cloaked and ship.cls.cloak_fire):
        ship.reveal_time = max(ship.reveal_time, reveal)
        return
    if ship.reveal_time <= 0:
        for side, intel in world.intel.items():
            if side == ship.side:
                continue
            c = intel.contacts.setdefault(ship.id, Contact(ship.id))
            c.x, c.y, c.vx, c.vy = ship.x, ship.y, 0.0, 0.0
            c.course, c.warp, c.last_tick = ship.course, ship.warp, world.tick
            c.ever, c.ghost = True, True
    if not world.step_events or not any(isinstance(e, CloakFlash) and e.ship_id == ship.id
                                        for e in world.step_events):
        world.emit(CloakFlash(world.tick, ship.id, ship.x, ship.y))


def _rated_range(platforms: list[tuple[float, float, float]]) -> float:
    return max((r for _, _, r in platforms), default=0.0)


def _haze_offset(world: World, side: int, ship_id: int) -> tuple[float, float]:
    """A unit-scale position error for a hazy contact, redrawn once a cycle (deterministic per battle)."""
    cycle = world.tick // world.rules.ticks_per_cycle
    rng = random.Random(((world.seed * 1_000_003 + side) * 7_919 + ship_id) * 104_729 + cycle)
    a = rng.uniform(0.0, 2.0 * math.pi)
    m = math.sqrt(rng.random())
    return math.sin(a) * m, math.cos(a) * m


def apparent_position(world: World, side: int, ship_id: int) -> tuple[float, float] | None:
    s = world.ships.get(ship_id)
    if s is None or not s.exists:
        return None
    if s.side == side:
        return s.x, s.y
    intel = world.intel.get(side)
    if intel is None:
        return s.x, s.y
    c = intel.contacts.get(ship_id)
    if c is None or not c.ever:
        return None
    if c.visible or c.ghost:
        return c.x, c.y
    if intel.dead_reckoning:
        age = min(15.0, (world.tick - c.last_tick) * world.rules.dt)
        return c.x + c.vx * age, c.y + c.vy * age
    return c.x, c.y


def track(world: World, side: int, ship_id: int) -> tuple[float, float, float, float] | None:
    s = world.ships.get(ship_id)
    if s is None or not s.exists:
        return None
    if s.side == side:
        vx, vy = s.velocity(world.rules.units_per_warp)
        return s.x, s.y, vx, vy
    pos = apparent_position(world, side, ship_id)
    if pos is None:
        return None
    c = world.intel[side].contacts[ship_id]
    if c.visible:
        return c.x, c.y, c.vx, c.vy
    return pos[0], pos[1], 0.0, 0.0


def is_visible(world: World, side: int, ship_id: int) -> bool:
    s = world.ships.get(ship_id)
    if s is None or not s.exists:
        return False
    if s.side == side:
        return True
    c = world.intel.get(side, SideIntel(side)).contacts.get(ship_id)
    return bool(c and c.visible)


def scan_duration(ship: Ship) -> float:
    return 2.5 - 1.5 * ship.sophistication


def perform_scan(world: World, ship: Ship, target: Ship, by: str = "") -> None:
    """Complete an active scan: noisy snapshot of the target's condition."""
    rng = world.rng
    soph = ship.sophistication
    noise = (1.0 - soph) * 15.0
    shields = []
    for sh in target.shields:
        if sh.destroyed or not sh.up:
            shields.append(-1.0)
        else:
            shields.append(max(0.0, min(100.0, sh.effective + rng.gauss(0, noise))))
    subs: dict[str, int] = {}
    for sub in target.subsystems():
        if sub.kind in (Kind.SHIELD,):
            subs[sub.sid] = sub.damage
            continue
        if rng.unit() < (1.0 - soph) * 0.3:
            continue  # this system was not resolved
        est = sub.damage if sub.damage in (0, 100) else int(max(1, min(99, sub.damage + rng.gauss(0, noise))))
        subs[sub.sid] = est
    rec = ScanRecord(
        tick=world.tick, shields=shields, subsystems=subs,
        crew=int(max(0, target.crew * (1 + rng.gauss(0, noise / 100)))),
        structure_frac=max(0.0, target.structure / max(1.0, target.structure_max)),
        charged_banks=sum(1 for b in target.banks if b.intact and b.charge >= target.cls.banks_charge - 1e-6),
        loaded_tubes=sum(1 for t in target.tubes if t.loaded is not None),
        probes_loaded=sum(1 for lch in target.launchers if lch.loaded is not None),
        confidence=0.5 + 0.5 * soph,
    )
    c = world.intel[ship.side].contacts.get(target.id)
    if c is not None:
        c.scan = rec
        c.identified = True
    world.emit(ScanCompleted(world.tick, ship.id, target.id, by))


def assess(world: World, side: int, target: Ship) -> Assessment | None:
    """The side's running damage assessment of a target it has on sensors (None when it has no contact)."""
    c = world.intel.get(side, SideIntel(side)).contacts.get(target.id)
    if c is None or not c.ever:
        return None
    if c.assessed is None:
        c.assessed = Assessment(world.tick, [None] * len(target.shields))
    c.assessed.tick = world.tick
    return c.assessed


def intel_quality(world: World, side: int, target_id: int) -> float:
    """0..1: how current the side's detailed knowledge of a target is."""
    s = world.ships.get(target_id)
    if s is not None and s.side == side:
        return 1.0
    c = world.intel.get(side, SideIntel(side)).contacts.get(target_id)
    if c is None or c.scan is None:
        return 0.0
    age = (world.tick - c.scan.tick) * world.rules.dt
    return max(0.0, 1.0 - age / 60.0) * c.scan.confidence


def distance(a: Ship, b: Ship) -> float:
    return math.hypot(a.x - b.x, a.y - b.y)
