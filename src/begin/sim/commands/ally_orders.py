"""Ally orders: the captain's `tell <ally> ...` (vocabulary in `sim/allies.py`)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ...core.angles import in_arc, norm360
from ..ship import Ship
from .base import Command, Rejected

if TYPE_CHECKING:
    from ..world import World


@dataclass(kw_only=True)
class AllyOrder(Command):
    """Captain's order to an ally ship (Begin's `tell <ally> ...`); see `allies.py` for the vocabulary."""

    ally: int
    order: str
    target: int | None = None
    value: float | None = None
    destination: int | None = None
    name: ClassVar[str] = "tell"
    needs_crew: ClassVar[bool] = False

    def validate(self, world: World, ship: Ship) -> None:
        from ..allies import ORDER_WORDS

        a = world.ships.get(self.ally)
        if a is None or not a.alive:
            raise Rejected("That ally is not available.")
        if a.side != ship.side:
            raise Rejected(f"{a.name} is not under your command.")
        if a.id == ship.id:
            raise Rejected("Give your own ship orders directly.")
        if self.order not in ORDER_WORDS:
            raise Rejected(f"Unknown order '{self.order}'.")
        self._check_target(world, ship, a)
        self._check_equipment(a)
        self._check_details(world, a)

    def _check_target(self, world: World, ship: Ship, a: Ship) -> None:
        """The ship the order names: there, seen, and on the right side (an enemy to attack, a friend to escort)."""
        from ..allies import SHIP_ORDERS

        o = self.order
        need = SHIP_ORDERS.get(o, "none")
        if need != "none" and self.target is None:
            raise Rejected(f"'{o}' needs a ship.")
        if self.target is None:
            return
        t = world.ships.get(self.target)
        if t is None or not t.exists:
            raise Rejected("That ship no longer exists.")
        if t.id == a.id:
            raise Rejected(f"{a.name} cannot {o} itself.")
        if need is True and t.side == a.side:
            raise Rejected(f"{t.name} is one of ours.")
        if need is False and t.side != a.side:
            raise Rejected(f"{t.name} is not one of ours.")
        if t.side != a.side and world.apparent_position(ship.side, t.id) is None:
            raise Rejected("No sensor contact with that ship.")

    def _check_equipment(self, a: Ship) -> None:
        """The ally has working gear for the order."""
        o = self.order
        if o == "phaser" and not any(b.intact for b in a.banks):
            raise Rejected(f"{a.name}: we have no working phasers.")
        if o == "torpedo" and not any(t.intact for t in a.tubes):
            raise Rejected(f"{a.name}: we have no working torpedo tubes.")
        if o == "probe" and not any(lch.intact for lch in a.launchers):
            raise Rejected(f"{a.name}: we have no working probe launchers.")
        if o in ("recover", "eject") and a.cls.mass_capacity <= 0:
            raise Rejected(f"{a.name} has no docking bays.")
        if o in ("tow", "tractor") and (a.tractor is None or not a.tractor.intact):
            raise Rejected(f"{a.name}: our tractor beam is not working.")
        if o == "board" and not any(not x.destroyed for x in a.transporters):
            raise Rejected(f"{a.name}: our transporters are down.")

    def _check_details(self, world: World, a: Ship) -> None:
        """What else the order needs: a course, a group, a docking bay, a destination."""
        o = self.order
        t = world.ships[self.target] if self.target is not None else None
        if o == "course" and self.value is None:
            raise Rejected("Hold which course?")
        if o == "join" and (self.value is None or self.value < 1):
            raise Rejected("Join which group (1 or more)?")
        if o == "dock" and t is not None and t.cls.mass_capacity <= 0:
            raise Rejected(f"{t.name} has no docking bays.")
        if o == "eject" and t is not None and t.docked_to != a.id:
            raise Rejected(f"{t.name} is not docked with {a.name}.")
        if o == "tow" and self.destination is None:
            raise Rejected("Tow it where? 'tell <ally> tow <ship> <destination ship>'.")
        if o == "undock" and a.docked_to is None:
            raise Rejected(f"{a.name} is not docked.")

    def apply(self, world: World, ship: Ship) -> None:
        world.deliver_order(ship, self)

    def describe(self) -> str:
        return f"tell {self.order}"


def in_mount_arc(ship: Ship, mount_center: float, mount_width: float, world_bearing: float) -> bool:
    return in_arc(norm360(world_bearing - ship.course), mount_center, mount_width)
