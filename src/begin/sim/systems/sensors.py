"""Sensors, contacts, fog of war and active scans [R §11, E fusion and scans].

Each side keeps a contact table fed by every working sensor platform on
that side (ships and data probes). Lost contacts keep their last known
state; computers sophisticated enough (Starfleet) dead-reckon them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..events import ContactChanged, Message, ScanCompleted, Tone
from ..ship import Kind, Ship

if TYPE_CHECKING:
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
    scan: ScanRecord | None = None


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
            refl = s.cls.scanner_reflect
            if s.cloaked and s.reveal_time <= 0:
                refl *= rules.cloak_reflect
            seen = False
            ident = False
            for px, py, r in platforms:
                reach = r * refl
                d2 = (s.x - px) ** 2 + (s.y - py) ** 2
                if d2 <= reach * reach:
                    seen = True
                    if d2 <= (reach * 0.6) ** 2:
                        ident = True
                        break
            if seen:
                vx, vy = s.velocity(rules.units_per_warp)
                c.x, c.y, c.vx, c.vy = s.x, s.y, vx, vy
                c.course, c.warp, c.last_tick = s.course, s.warp, world.tick
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
                c.visible = False
                world.emit(ContactChanged(world.tick, side, s.id, False))
                if side == world.player_side:
                    what = "cloaked" if s.cloaked else "out of sensor range"
                    world.emit(Message(world.tick, f"Lost contact with {world.label(side, s.id)} ({what}).",
                                       Tone.CAUTION, visible_to=frozenset({side})))

        vis: set[int] = set()
        for o in (*world.torpedoes, *world.probes):
            if o.side == side:
                vis.add(o.id)
                continue
            for px, py, r in platforms:
                reach = r * rules.probe_reflect
                if (o.x - px) ** 2 + (o.y - py) ** 2 <= reach * reach:
                    vis.add(o.id)
                    break
        intel.visible_ordnance = vis


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
    if c.visible:
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


def perform_scan(world: World, ship: Ship, target: Ship) -> None:
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
    world.emit(ScanCompleted(world.tick, ship.id, target.id))


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
