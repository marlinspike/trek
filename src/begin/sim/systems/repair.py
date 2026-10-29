"""Damage control [R §10].

Efficiency is the surviving crew fraction (the host's docked repair ratio
while docked). A repair priority multiplies its class by 4 and every other
class by 0.5 (Begin 2.0). Destroyed items can only be rebuilt while docked.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..events import Message, SubsystemRepaired, Tone
from ..ship import REPAIR_CLASS, Ship

if TYPE_CHECKING:
    from ..world import World


def update_repair(world: World, ship: Ship, dt: float) -> None:
    if ship.crew <= 0:
        return
    rng = world.rng
    cls = ship.cls
    host = world.ships.get(ship.docked_to) if ship.docked_to is not None else None
    if host is not None:
        eff = max(host.cls.docked_repair_ratio, 0.0) * 2.0  # [M] docked ships repair twice as fast
    else:
        eff = ship.crew / max(1, cls.crew)
    if eff < 0.1:
        return
    docked = host is not None
    prio = ship.repair_priority
    for sub in ship.subsystems():
        if sub.damage == 0:
            continue
        if sub.destroyed and not (docked and rng.unit() < 0.02 * dt * 10):
            continue
        mult = 1.0 if prio is None else (4.0 if sub.kind == prio else 0.5)
        rate = cls.repair.rate(REPAIR_CLASS[sub.kind]) * mult * eff
        sub.repair_progress += rng.uniform(0.0, 2.0) * rate * dt
        whole = int(sub.repair_progress)
        if whole <= 0:
            continue
        sub.repair_progress -= whole
        sub.damage = max(0, sub.damage - whole)
        if sub.damage == 0:
            sub.repair_progress = 0.0
            world.emit(SubsystemRepaired(world.tick, ship.id, sub.sid, sub.label))
            world.emit(Message(world.tick, f"Repairs completed on {ship.name}'s {sub.label.lower()}.",
                               Tone.GOOD, speaker="Engineering", ship_id=ship.id,
                               visible_to=frozenset({ship.side})))
