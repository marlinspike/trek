"""Ships that join a battle after it starts [E]: attack waves and reinforcements.

An `Arrival` is a group of ships waiting off the map. It drops out of warp when
its time comes: at a fixed cycle, a while after its side's ships on the field
are all beaten (`after_clear`, the lull between waves), or whichever is first.
Waves hold the battle open: it isn't over while attackers are still coming.
Reinforcements don't: if the enemy is beaten first, they aren't needed.

The world only places the ships. Who commands them is the battle's business
(`World.on_arrival`), the same way a captured ship gets new brains.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from .events import Message, ShipArrived, Tone

if TYPE_CHECKING:
    from .world import World

ENTRY_SPREAD = 1800.0      # units between ships arriving together, line abreast
ENTRY_STREAK = 9000.0      # how far back along their course the warp streak starts (for the effect)


@dataclass
class Arrival:
    side: int
    ships: tuple[str, ...]                         # class ids
    kind: str = "wave"                             # "wave" | "reinforcement"
    at: float | None = None                        # cycle it arrives by, at the latest
    after_clear: float | None = None               # or this many cycles after its side's ships are all beaten
    at_x: float = 0.0                              # where it drops out of warp
    at_y: float = 0.0
    heading: float = 180.0                         # its course on arrival
    names: tuple[str | None, ...] = ()             # names for the ships, in order (None = drawn at random)
    message: str = ""                              # what everyone hears when it arrives
    tag: str = ""                                  # who asked for it (a tour's reinforcement call)
    cleared_at: float | None = field(default=None, repr=False)
    arrived: bool = False
    ship_ids: list[int] = field(default_factory=list)

    @property
    def holds_battle(self) -> bool:
        """Attackers still to come keep the battle going."""
        return self.kind == "wave"

    def due(self, world: World, ready: bool = True) -> bool:
        """`ready`: every earlier wave is already here, so a cleared field means this one's turn."""
        if self.arrived:
            return False
        if self.at is not None and world.time >= self.at:
            return True
        if self.after_clear is not None and ready:
            if self.cleared_at is None:
                if not any(s.alive and s.side == self.side for s in world.ships.values()):
                    self.cleared_at = world.time
            if self.cleared_at is not None and world.time - self.cleared_at >= self.after_clear:
                return True
        return False

    def eta(self, world: World) -> float | None:
        """Cycles until it arrives, if that is known yet."""
        if self.arrived:
            return None
        times = []
        if self.at is not None:
            times.append(self.at - world.time)
        if self.after_clear is not None and self.cleared_at is not None:
            times.append(self.cleared_at + self.after_clear - world.time)
        return max(0.0, min(times)) if times else None


def update_arrivals(world: World) -> None:
    ready = True
    for a in world.arrivals:
        if a.due(world, ready):
            _arrive(world, a)
        if a.holds_battle and not a.arrived:
            ready = False     # waves come in order: the next one waits for this one to be beaten


def _arrive(world: World, a: Arrival) -> None:
    a.arrived = True
    face = math.radians(a.heading)
    hx, hy = math.sin(face), math.cos(face)
    px, py = math.cos(face), -math.sin(face)   # perpendicular: line abreast
    n = len(a.ships)
    for i, cid in enumerate(a.ships):
        off = (i - (n - 1) / 2.0) * ENTRY_SPREAD
        x, y = a.at_x + px * off, a.at_y + py * off
        cls = world.content.classes[cid]
        name = a.names[i] if i < len(a.names) else None
        ship = world.add_ship(cid, a.side, x, y, course=a.heading, warp=min(cls.cruise_warp, 3.0), name=name)
        a.ship_ids.append(ship.id)
        world.emit(ShipArrived(world.tick, ship.id, a.kind, (x - hx * ENTRY_STREAK, y - hy * ENTRY_STREAK)))
        if world.on_arrival is not None:
            world.on_arrival(ship)
    if a.message:
        world.emit(Message(world.tick, a.message, Tone.ALERT if a.kind == "wave" else Tone.GOOD))


def waves_pending(world: World) -> bool:
    return any(a.holds_battle and not a.arrived for a in world.arrivals)


__all__ = ["Arrival", "ENTRY_SPREAD", "update_arrivals", "waves_pending"]
