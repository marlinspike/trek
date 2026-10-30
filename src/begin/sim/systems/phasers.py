"""Phaser banks: arcs, readiness, cone fire [R §6, E arcs/mounts]."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ...core.angles import ang_dist, bearing, in_arc, norm360
from ..events import OrdnanceDestroyed, PhaserFired
from ..ordnance import Torpedo
from ..ship import CREW_DECKS, PhaserBank, Ship
from .damage import Aim, DamageKind, apply_damage, exposure, relative_bearing_from, subsystems_for

if TYPE_CHECKING:
    from ..world import World


def bank_origin(ship: Ship, bank: PhaserBank) -> tuple[float, float]:
    return ship.hull_to_world(*bank.mount.pos)


def bank_ready(ship: Ship, bank: PhaserBank) -> bool:
    return bank.intact and bank.charge >= ship.cls.banks_charge - 1e-6


def bank_bears(ship: Ship, bank: PhaserBank, world_bearing: float) -> bool:
    rel = norm360(world_bearing - ship.course)
    return in_arc(rel, bank.mount.arc_center, bank.mount.arc_width)


def bank_bears_point(ship: Ship, bank: PhaserBank, x: float, y: float) -> bool:
    """Whether a bank can aim at a point, measured from its mount [E].

    A point nearer the ship's centre than the mount itself is up against the
    hull, where the mount's own arc means nothing: every bank reaches it.
    Without this, a ship that closed to point blank could never be hit, and a
    starbase could never fire at an enemy sitting inside its hull radius.
    """
    ox, oy = bank_origin(ship, bank)
    if math.hypot(x - ship.x, y - ship.y) <= math.hypot(ox - ship.x, oy - ship.y):
        return True
    return bank_bears(ship, bank, bearing(x - ox, y - oy))


def phaser_damage(world: World, charge: float, spread: float, dist: float, rng_: float) -> float:
    """[R] charge × (45 / spread) × sqrt(1 − d/range) × 0.5."""
    r = world.rules
    if dist >= rng_:
        return 0.0
    return charge * (r.phaser_dam_mult / spread) * math.sqrt(1.0 - dist / rng_) * r.phaser_half


def targeting_accuracy(world: World, ship: Ship, target: Ship, selector: str, dist: float, spread: float) -> float:
    """Chance that each damage roll lands on the selected subsystem group [E].

    Precision comes from the firing ship's computer and sensors, range,
    beam width, how well the side knows the target (recent scan), and how
    exposed the selected systems are to this angle of attack.
    """
    rel = relative_bearing_from(target, ship.x, ship.y)
    if selector == CREW_DECKS:
        best_exp = 0.6                    # the crew decks run through the whole hull
    else:
        subs = subsystems_for(target, selector)
        if not subs:
            return 0.0
        best_exp = max(exposure(target, s, rel) for s in subs)
    rng_ = ship.cls.banks_range
    soph = 0.55 + 0.45 * ship.sophistication
    sensors = math.sqrt(ship.sensors.health) if ship.sensors is not None else 0.3
    range_f = 0.5 + 0.5 * math.sqrt(max(0.0, 1.0 - dist / rng_))
    spread_f = (world.rules.spread_min / max(spread, world.rules.spread_min)) ** 0.6
    intel = world.intel_quality(ship.side, target.id)
    know = 0.7 + 0.3 * intel
    acc = world.rules.targeted_max_accuracy * soph * sensors * range_f * spread_f * know * (0.3 + 0.7 * best_exp)
    return max(0.0, min(world.rules.targeted_max_accuracy, acc))


def _detonate_split(world: World, t: Torpedo, n: int) -> None:
    """Members of a torpedo group destroyed by a beam explode where they are."""
    from .ordnance import blast

    kind = DamageKind.SHIELD_BORE if t.spec.is_shield_bore else DamageKind.BLAST
    blast(world, t.x, t.y, t.yield_, "torpedo", t.owner, n, kind, None, None, cause="intercepted",
          radius_scale=t.spec.blast_scale)


def fire_bank(
    world: World,
    ship: Ship,
    bank: PhaserBank,
    world_bearing: float,
    spread: float,
    target_id: int | None = None,
    selector: str | None = None,
    defensive: bool = False,
) -> PhaserFired:
    rules = world.rules
    spread = max(rules.spread_min, min(rules.spread_max, spread))
    ox, oy = bank_origin(ship, bank)
    rng_ = ship.cls.banks_range
    charge = bank.charge
    bank.charge = 0.0
    bank.mark = norm360(world_bearing - ship.course)
    if not defensive:
        bank.spread = spread
    half = spread / 2.0
    ship.stats.phaser_shots += 1
    ship.reveal_time = max(ship.reveal_time, rules.cloak_reveal_cycles)

    ev = PhaserFired(world.tick, ship.id, bank.index, (ox, oy), world_bearing, spread, rng_, defensive=defensive)
    end_d = rng_
    # ordnance in the cone: any energy detonates torpedoes and probes; plasma bleeds [R]
    for t in world.torpedoes:
        if t.detonate or t.fizzle:
            continue
        dx, dy = t.x - ox, t.y - oy
        d = math.hypot(dx, dy)
        if d >= rng_ or ang_dist(bearing(dx, dy), world_bearing) > half:
            continue
        dmg = phaser_damage(world, charge, spread, d, rng_)
        if t.spec.is_plasma:
            t.strength -= dmg
            if t.strength <= 0:
                t.fizzle = True
                world.emit(OrdnanceDestroyed(world.tick, t.x, t.y, "torpedo", ship.id))
                ship.stats.ordnance_intercepted += 1
        else:
            # [E] a beam is not certain to catch every torpedo of a group: each
            # member is set off with a chance that grows with the energy delivered
            p_kill = min(rules.beam_kill_max, rules.beam_kill_base + dmg * rules.beam_kill_per_damage)
            if defensive:
                p_kill *= rules.pd_kill_scale * (1.0 + rules.morale_accuracy * ship.morale_factor)
            killed = sum(1 for _ in range(t.salvo) if world.rng.unit() < p_kill)
            if killed >= t.salvo:
                t.detonate = True
                t.shot_down = True
            elif killed > 0:
                t.salvo -= killed
                _detonate_split(world, t, killed)
            if killed:
                world.emit(OrdnanceDestroyed(world.tick, t.x, t.y, "torpedo", ship.id))
                ship.stats.ordnance_intercepted += killed
        if defensive:
            end_d = min(end_d, d)
    for p in world.probes:
        if p.detonate:
            continue
        dx, dy = p.x - ox, p.y - oy
        d = math.hypot(dx, dy)
        if d >= rng_ or ang_dist(bearing(dx, dy), world_bearing) > half:
            continue
        p.detonate = True
        p.remote = True  # a hit sets a probe off at full warhead, arming bypassed [R]
        world.emit(OrdnanceDestroyed(world.tick, p.x, p.y, "probe", ship.id))
        ship.stats.ordnance_intercepted += 1
        if defensive:
            end_d = min(end_d, d)

    # ships in the cone — friend or foe [R]
    for other in list(world.ships.values()):
        if other is ship or not other.exists or other.docked_to is not None:
            continue
        dx, dy = other.x - ox, other.y - oy
        d = math.hypot(dx, dy)
        if d >= rng_ or d < 1e-6 or ang_dist(bearing(dx, dy), world_bearing) > half:
            continue
        dmg = phaser_damage(world, charge, spread, d, rng_)
        aim = None
        if selector and other.id == target_id:
            acc = targeting_accuracy(world, ship, other, selector, d, spread)
            aim = Aim(selector, min(1.0, acc * (1.0 + world.rules.morale_accuracy * ship.morale_factor)))
        apply_damage(world, other, dmg, ox, oy, DamageKind.PHASER, ship.id, aim)
        ev.hits.append(other.id)
        if other.id == target_id:
            end_d = min(end_d, d)
    if ev.hits:
        ship.stats.phaser_hits += 1
    r = math.radians(world_bearing)
    ev.end = (ox + math.sin(r) * end_d, oy + math.cos(r) * end_d)
    world.emit(ev)
    return ev
