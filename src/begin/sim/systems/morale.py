"""Crew morale [E].

Every ship's crew has spirits from 0 to 100, starting at its race's usual
level (`morale` in factions.toml). They fall with damage to the hull, crew
lost, systems destroyed, shields collapsing and friends lost, scaled by the
race's steadiness (Klingons hold under fire, Orion pirates don't). They rise
with damage dealt, enemies destroyed, repairs finished and the captain's
address, and drift back to the usual level once out of the fight.

Morale is the crew's will, not its numbers (crew losses already slow
repairs and weaken the ship), so its effects are modest: at 100 repairs run
25% faster, tubes load 15% faster and point defense and aimed fire are 15%
better; at 0 the same amounts worse; at 50 nothing changes. AI captains
with a shaken crew retreat sooner and strike their colours more readily.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..events import (
    HullHit, HullRepaired, MoraleShift, ShieldHit, ShipStatusChanged, SubsystemDamaged, SubsystemRepaired,
)
from ..ship import Ship
from .repair import in_battle

if TYPE_CHECKING:
    from ..world import World

BAND = 20.0     # officers remark when morale crosses into another band of this many points
LOST = ("destroyed", "derelict", "surrendered", "captured")


def morale_factor(ship: Ship) -> float:
    """-1 at morale 0, 0 at 50, +1 at 100."""
    return ship.morale_factor


def band(morale: float) -> int:
    """0 (broken) .. 4 (high): which fifth of the scale."""
    return min(4, int(morale // BAND))


def adjust(world: World, ship: Ship, delta: float, cause: str = "") -> None:
    """Change one ship's morale, and say so when it crosses into another band."""
    if not ship.exists or delta == 0:
        return
    before = ship.morale
    ship.morale = max(0.0, min(100.0, before + delta))
    if band(ship.morale) != band(before):
        world.emit(MoraleShift(world.tick, ship.id, ship.morale, ship.morale > before, cause))


def update_morale(world: World, dt: float) -> None:
    """This tick's events, then the slow drift back to normal out of the fight."""
    r = world.rules
    ships = world.ships
    events, world.morale_events = world.morale_events, []
    for ev in events:
        if isinstance(ev, HullHit):
            s = ships.get(ev.ship_id)
            if s is None:
                continue
            share = ev.amount / max(1.0, s.structure_max)
            crew = ev.crew_lost / max(1, s.cls.crew)
            adjust(world, s, -s.steadiness * (r.morale_hull_loss * share + r.morale_crew_loss * crew), "damage")
            a = ships.get(ev.attacker) if ev.attacker is not None else None
            if a is not None and a.side != s.side:
                adjust(world, a, r.morale_damage_dealt * share, "hits")
        elif isinstance(ev, ShieldHit) and ev.collapsed:
            s = ships.get(ev.ship_id)
            if s is not None:
                adjust(world, s, -s.steadiness * r.morale_shield_down, "shield")
        elif isinstance(ev, SubsystemDamaged) and ev.destroyed:
            s = ships.get(ev.ship_id)
            if s is not None:
                adjust(world, s, -s.steadiness * r.morale_system_lost, "damage")
        elif isinstance(ev, SubsystemRepaired):
            s = ships.get(ev.ship_id)
            if s is not None:
                adjust(world, s, r.morale_repaired, "repairs")
        elif isinstance(ev, HullRepaired):
            s = ships.get(ev.ship_id)
            if s is not None:
                adjust(world, s, r.morale_hull_patched, "repairs")
        elif isinstance(ev, ShipStatusChanged) and ev.status in LOST:
            gone = ships.get(ev.ship_id)
            if gone is None:
                continue
            for s in ships.values():
                if not s.alive or s.id == gone.id:
                    continue
                if s.side == gone.side:
                    adjust(world, s, -s.steadiness * r.morale_ally_lost, "loss")
                else:
                    bonus = r.morale_kill_bonus if s.id == ev.by_ship else 0.0
                    adjust(world, s, r.morale_enemy_lost + bonus, "kill")
    tpc = r.ticks_per_cycle
    if world.tick % tpc:
        return
    for s in ships.values():
        if s.alive and s.morale != s.morale_base and not in_battle(world, s):
            step = r.morale_recovery * dt * tpc
            gap = s.morale_base - s.morale
            adjust(world, s, max(-step, min(step, gap)), "rest")


__all__ = ["adjust", "band", "morale_factor", "update_morale"]
