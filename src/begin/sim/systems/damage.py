"""Damage resolution: shields, hull, crew, subsystems, ordnance, blasts.

Shield absorption follows Begin 1.65 [R]. Beyond the shields the default
REMAKE model [E] uses a structural hull pool and location-aware subsystem
rolls, so ships can be crippled without being destroyed and subsystem
targeting is a real mechanic. The CLASSIC_165 model reproduces 1.65's
`dealDamageToHull` for comparison and fidelity tests.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum
from typing import TYPE_CHECKING

from ...core.angles import bearing, norm360
from ..events import HullHit, ShieldHit, SubsystemDamaged
from ..rules import DamageModel
from ..ship import DAMAGE_WEIGHT, TARGETABLE_GROUPS, Kind, Ship, ShipStatus, Subsystem

if TYPE_CHECKING:
    from ..world import World


class DamageKind(str, Enum):
    PHASER = "phaser"
    BLAST = "blast"          # antimatter torpedo, probe or ship explosion
    PLASMA = "plasma"
    SHIELD_BORE = "bore"     # Orion Shield Auger: x4 vs shields, never penetrates [R]


@dataclass(frozen=True, slots=True)
class Aim:
    """A deliberate attempt to hit particular subsystems."""

    selector: str     # TARGETABLE_GROUPS key or a specific subsystem sid
    accuracy: float   # 0..1 chance that each damage roll goes to the selection


def subsystems_for(ship: Ship, selector: str) -> list[Subsystem]:
    kinds = TARGETABLE_GROUPS.get(selector)
    if kinds is not None:
        return [s for s in ship.subsystems() if s.kind in kinds and not s.destroyed]
    s = ship.subsystem(selector)
    return [s] if s is not None and not s.destroyed else []


def exposure(ship: Ship, sub: Subsystem, rel_bearing: float) -> float:
    """How exposed a subsystem is to a hit arriving from `rel_bearing` (0..1)."""
    px, py = sub.pos[0] / 50.0, sub.pos[1] / 50.0
    r = math.radians(rel_bearing)
    ux, uy = math.sin(r), math.cos(r)
    return max(0.0, min(1.0, 0.5 + 0.5 * (px * ux + py * uy)))


def relative_bearing_from(ship: Ship, x: float, y: float) -> float:
    """Bearing of point (x, y) seen from the ship, relative to its bow."""
    return norm360(bearing(x - ship.x, y - ship.y) - ship.course)


def apply_damage(
    world: World,
    target: Ship,
    amount: float,
    from_x: float,
    from_y: float,
    kind: DamageKind,
    attacker: int | None = None,
    aim: Aim | None = None,
) -> float:
    """Apply a hit to a ship. Returns damage that penetrated the shields."""
    if not target.exists or target.docked_to is not None:
        return 0.0
    amount = float(round(amount))
    if amount <= 0:
        return 0.0
    rules = world.rules
    rel = relative_bearing_from(target, from_x, from_y)
    target.reveal_time = max(target.reveal_time, rules.cloak_reveal_cycles)
    att = world.ships.get(attacker) if attacker is not None else None
    if att is not None:
        att.stats.damage_dealt += amount
    target.stats.damage_taken += amount

    # ---- shields [R]
    remaining = amount
    shield = target.shield_for_bearing(rel)
    if shield is not None and shield.up and not shield.destroyed:
        capacity = target.cls.shield_strength * shield.effective / 100.0
        incoming = amount * 4.0 if kind == DamageKind.SHIELD_BORE else amount
        absorbed = min(incoming, capacity)
        loss = 1.0 + absorbed * (1.0 - target.cls.shield_absorption)
        if shield.reinforced:
            loss *= 0.5
        was_up = shield.strength > 1.0
        shield.strength = max(0.0, shield.strength - loss)
        shield.effective = min(shield.effective, shield.strength)
        shield.flash = 0.6
        target.stats.shield_damage_absorbed += absorbed
        if kind == DamageKind.SHIELD_BORE:
            world.emit(ShieldHit(world.tick, target.id, shield.index, absorbed, 0.0,
                                 was_up and shield.strength <= 1.0, attacker, shield.strength))
            return 0.0
        remaining = max(0.0, amount - absorbed)
        world.emit(ShieldHit(world.tick, target.id, shield.index, absorbed, remaining,
                             was_up and shield.strength <= 1.0, attacker, shield.strength))
    elif kind == DamageKind.SHIELD_BORE:
        return 0.0
    if remaining <= 0.0:
        return 0.0

    if rules.damage_model == DamageModel.CLASSIC_165:
        _hull_classic(world, target, remaining, attacker)
    else:
        _hull_remake(world, target, remaining, rel, attacker, aim)
    return remaining


def _hull_classic(world: World, ship: Ship, dmg: float, attacker: int | None) -> None:
    rng = world.rng
    ship.stats.hull_damage_taken += dmg
    if dmg >= 50.0:
        world.emit(HullHit(world.tick, ship.id, dmg, ship.crew, attacker))
        world.destroy_ship(ship, "hull breach", attacker)
        return
    d = int(dmg)
    lost = int(rng.irange(0, d) / 100.0 * ship.crew) + rng.irange(0, d // 3)
    _crew_loss(world, ship, lost, attacker)
    world.emit(HullHit(world.tick, ship.id, dmg, lost, attacker))
    if ship.status != ShipStatus.ACTIVE:
        return
    for _ in range(int(dmg / 10.0)):
        for kind, p in DAMAGE_WEIGHT.items():
            if kind == Kind.COMPUTER or not rng.chance(p):
                continue
            items = [s for s in ship.subsystems() if s.kind == kind]
            if items:
                _hit_subsystem(world, ship, rng.choice(items), False)


def _hull_remake(
    world: World, ship: Ship, dmg: float, rel: float, attacker: int | None, aim: Aim | None
) -> None:
    rng = world.rng
    rules = world.rules
    ship.stats.hull_damage_taken += dmg

    # armour (2.0 Armadillo) soaks hull damage before structure [R gate, E pool]
    hull_dmg = dmg
    if ship.armour > 0:
        soak = min(ship.armour, hull_dmg * 0.6)
        ship.armour -= soak
        hull_dmg -= soak
    ship.structure -= hull_dmg

    frac = dmg / max(1.0, ship.structure_max)
    lost = int(round(ship.crew * frac * rng.uniform(0.4, 1.2) * rules.crew_loss_scale))
    lost = min(lost, ship.crew)
    world.emit(HullHit(world.tick, ship.id, dmg, lost, attacker))
    _crew_loss(world, ship, lost, attacker)

    if ship.structure <= 0.0:
        world.destroy_ship(ship, "structural failure", attacker)
        return
    if ship.status != ShipStatus.ACTIVE and ship.status != ShipStatus.SURRENDERED:
        return

    # subsystem rolls: Begin's n = dmg/10, with the fractional part as a chance
    rolls_f = dmg * rules.subsystem_rolls_per_damage
    rolls = int(rolls_f) + (1 if rng.unit() < rolls_f - int(rolls_f) else 0)
    targeted = subsystems_for(ship, aim.selector) if aim is not None else []
    subs = [s for s in ship.subsystems() if not s.destroyed]
    if not subs:
        return
    by_kind: dict[Kind, list[Subsystem]] = {}
    for s in subs:
        by_kind.setdefault(s.kind, []).append(s)
    for _ in range(rolls):
        if targeted and aim is not None and rng.unit() < aim.accuracy:
            weights = [0.15 + exposure(ship, s, rel) for s in targeted]
            pick = _weighted(rng.unit(), targeted, weights)
            _hit_subsystem(world, ship, pick, True)
            targeted = [s for s in targeted if not s.destroyed]
            continue
        for kind, items in by_kind.items():
            exps = [exposure(ship, s, rel) for s in items]
            p = DAMAGE_WEIGHT[kind] * max(0.25, min(1.4, 1.6 * sum(exps) / len(exps)))
            if rng.unit() >= p:
                continue
            live = [s for s in items if not s.destroyed]
            if not live:
                continue
            weights = [0.1 + exposure(ship, s, rel) ** 2 for s in live]
            _hit_subsystem(world, ship, _weighted(rng.unit(), live, weights), False)


def _weighted(u: float, items: list[Subsystem], weights: list[float]) -> Subsystem:
    total = sum(weights)
    acc = 0.0
    x = u * total
    for s, w in zip(items, weights):
        acc += w
        if x <= acc:
            return s
    return items[-1]


def _hit_subsystem(world: World, ship: Ship, sub: Subsystem, targeted: bool) -> None:
    rng = world.rng
    if sub.destroyed:
        return
    amount = 5 + rng.irange(0, 25)
    if targeted:
        amount += 10
    if sub.kind == Kind.REACTOR:
        # [R] 25% of reactor hits destroy it outright, otherwise double damage
        sub.damage = 100 if rng.chance(0.25) else min(100, sub.damage + amount * 2)
    elif sub.kind == Kind.TRANSPORTER:
        sub.damage = min(100, sub.damage + amount * 2)
    else:
        sub.damage = min(100, sub.damage + amount)
    sub.repair_progress = 0.0
    sub.on_damaged()
    if sub.kind == Kind.CLOAK:
        ship.cloaked = False
    if sub.kind == Kind.TRACTOR:
        ship.tractor_target = None
    world.emit(SubsystemDamaged(world.tick, ship.id, sub.sid, sub.label, sub.damage, sub.destroyed, targeted))
    if sub.destroyed:
        ship.stats.subsystems_disabled += 1


def _crew_loss(world: World, ship: Ship, lost: int, attacker: int | None) -> None:
    if lost <= 0:
        return
    lost = min(lost, ship.crew)
    ship.crew -= lost
    ship.stats.crew_lost += lost
    if ship.boarders > 0:
        ship.boarders = max(0, ship.boarders - world.rng.irange(0, lost))
    if 0 < ship.crew < 6 or ship.crew == 0:
        world.lose_all_hands(ship, "casualties", attacker)
