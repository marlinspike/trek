"""Damage control [R §10].

Efficiency is the surviving crew fraction (the host's docked repair ratio
while docked). A repair priority multiplies its class by 4 and every other
class by 0.5 (Begin 2.0). Begin 2.0 rebuilt destroyed items only while docked;
here the crew rebuilds them in space too, at the same rate, starting from 100% [E].
A system hit by aimed fire repairs at `aimed_repair` × the rate in space until it
is whole again, so a captain can knock systems out and keep them out [E].

The hull is repaired too [E]: slowly in battle, faster once the fighting is
over, and fastest at a base. Crews in space patch the hull to
`hull_field_limit`; only a base restores it fully. The hull can be the repair
priority like any system.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ..events import HullRepaired, Message, SubsystemRepaired, Tone
from ..ship import HULL, REPAIR_CLASS, Ship

if TYPE_CHECKING:
    from ..world import World


def _efficiency(world: World, ship: Ship) -> tuple[float, bool]:
    """How fast the crews work (0 when they can't), and whether the ship is docked. Morale speeds or slows
    them a little [E]."""
    if ship.crew <= 0:
        return 0.0, False
    spirit = 1.0 + world.rules.morale_repair * ship.morale_factor
    host = world.ships.get(ship.docked_to) if ship.docked_to is not None else None
    if host is not None:
        return max(host.cls.docked_repair_ratio, 0.0) * 2.0 * spirit, True  # [M] docked ships repair twice as fast
    eff = ship.crew / max(1, ship.cls.crew)
    return (eff * spirit if eff >= 0.1 else 0.0), False


def in_battle(world: World, ship: Ship) -> bool:
    """Hit lately, or an enemy ship close by [E]."""
    r = world.rules
    if world.tick - ship.last_hull_hit < r.battle_quiet_cycles * r.ticks_per_cycle:
        return True
    return any(o.alive and o.side != ship.side and math.hypot(o.x - ship.x, o.y - ship.y) < r.battle_enemy_range
               for o in world.ships.values())


def hull_limit(world: World, ship: Ship) -> float:
    """The structure repairs can bring the hull back to here and now."""
    docked = ship.docked_to is not None
    return ship.structure_max * (1.0 if docked else world.rules.hull_field_limit)


def under_repair(world: World, ship: Ship) -> tuple[set[str], bool]:
    """The subsystems the crews are working on now, and whether the hull is one of them (for the HUD)."""
    eff, docked = _efficiency(world, ship)
    if eff <= 0 or not ship.exists:
        return set(), False
    subs = {s.sid for s in ship.subsystems() if s.damage > 0}
    return subs, 0.0 < ship.structure < hull_limit(world, ship) - 0.05


def update_repair(world: World, ship: Ship, dt: float) -> None:
    eff, docked = _efficiency(world, ship)
    if eff <= 0:
        return
    rng = world.rng
    cls = ship.cls
    prio = ship.repair_priority
    for sub in ship.subsystems():
        if sub.damage == 0:
            continue
        mult = 1.0 if prio is None else (4.0 if sub.kind == prio else 0.5)
        rate = cls.repair.rate(REPAIR_CLASS[sub.kind]) * mult * eff
        if sub.aimed_hit and not docked:
            rate *= world.rules.aimed_repair   # aimed fire wrecks the parts crews can't patch in space [E]
        sub.repair_progress += rng.uniform(0.0, 2.0) * rate * dt
        whole = int(sub.repair_progress)
        if whole <= 0:
            continue
        sub.repair_progress -= whole
        sub.damage = max(0, sub.damage - whole)
        if sub.damage == 0:
            sub.repair_progress = 0.0
            sub.aimed_hit = False
            world.emit(SubsystemRepaired(world.tick, ship.id, sub.sid, sub.label))
            world.emit(Message(world.tick, f"Repairs completed on {ship.name}'s {sub.label.lower()}.",
                               Tone.GOOD, speaker="Engineering", ship_id=ship.id,
                               visible_to=frozenset({ship.side})))
    _repair_hull(world, ship, eff, docked, dt)


def _repair_hull(world: World, ship: Ship, eff: float, docked: bool, dt: float) -> None:
    r = world.rules
    limit = hull_limit(world, ship)
    if ship.structure <= 0 or ship.structure >= limit:
        return
    prio = ship.repair_priority
    mult = 1.0 if prio is None else (4.0 if prio == HULL else 0.5)
    if docked:
        rate = r.hull_repair_docked
    else:
        rate = r.hull_repair_rate * (r.hull_repair_under_fire if in_battle(world, ship) else 1.0)
    before = ship.structure / ship.structure_max
    ship.structure = min(limit, ship.structure + ship.structure_max * rate * mult * eff * dt)
    after = ship.structure / ship.structure_max
    # report each quarter of the hull restored, and the end of the work
    done = ship.structure >= limit - 1e-6
    if done or int(after * 4) > int(before * 4):
        world.emit(HullRepaired(world.tick, ship.id, after, done))
        if done:
            text = (f"Hull repairs on {ship.name} complete." if docked or limit >= ship.structure_max else
                    f"Hull patched on {ship.name} to {after * 100:.0f}%. A starbase can do the rest.")
            world.emit(Message(world.tick, text, Tone.GOOD, speaker="Engineering", ship_id=ship.id,
                               visible_to=frozenset({ship.side})))
