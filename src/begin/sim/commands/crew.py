"""The crew: repairs, stations, the conn, and the captain's last resorts (self-destruct, surrender)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ..ship import HelmMode, RepairTarget, Ship, ShipStatus
from .base import Authority, Command, Rejected

if TYPE_CHECKING:
    from ..world import World


@dataclass(kw_only=True)
class SetRepairPriority(Command):
    kind: RepairTarget | None
    name: ClassVar[str] = "repair"

    def channels(self) -> tuple[str, ...]:
        return ("engineering.priority",)

    def apply(self, world: World, ship: Ship) -> None:
        ship.repair_priority = self.kind
        if self.issuer >= Authority.CAPTAIN:
            ship.repairs_by = ""     # the captain's own priority takes the repairs back from an officer


@dataclass(kw_only=True)
class AddressCrew(Command):
    """The captain speaks to the crew (remake extension): morale rises by how rousing it was.

    `rousing` is 0..1.5: 1 for an ordinary address, judged by the language model when there is one.
    A second address within `morale_address_cycles` would ring hollow and is refused.
    """

    text: str = ""
    rousing: float = 1.0
    name: ClassVar[str] = "address"

    def validate(self, world: World, ship: Ship) -> None:
        r = world.rules
        since = (world.tick - ship.last_address) / r.ticks_per_cycle
        if since < r.morale_address_cycles:
            raise Rejected(f"The crew heard from you {since:.0f} cycles ago; another speech so soon would ring hollow "
                           f"(wait {r.morale_address_cycles - since:.0f} more).")

    def validate_now(self, world: World, ship: Ship) -> str | None:
        """The refusal, if any, before the speech is judged."""
        try:
            self.validate(world, ship)
        except Rejected as r:
            return str(r)
        return None

    def apply(self, world: World, ship: Ship) -> None:
        from ..systems.morale import adjust

        ship.last_address = world.tick
        adjust(world, ship, world.rules.morale_address * max(0.0, min(1.5, self.rousing)), "address")

    def describe(self) -> str:
        return "address to the crew"


@dataclass(kw_only=True)
class ManageRepairs(Command):
    """Let an officer direct the repair crews, or take them back (remake extension)."""

    officer: str = ""      # officer id; "" = the captain directs repairs
    name: ClassVar[str] = "repairs"
    needs_crew: ClassVar[bool] = False

    def apply(self, world: World, ship: Ship) -> None:
        ship.repairs_by = self.officer
        world.release_holds(ship.id, "engineering.priority")


# which holds a station covers when it is handed to (or taken back from) an officer
STATION_CHANNELS: dict[str, tuple[str, ...]] = {
    "helm": ("helm",),
    "tactical": ("tactical", "phasers", "torpedoes"),
    "engineering": ("shields", "engineering"),
    "science": (),
}


@dataclass(kw_only=True)
class DelegateStation(Command):
    """Hand a bridge station to its officer, or take it back (remake extension)."""

    station: str
    on: bool = True
    name: ClassVar[str] = "delegate"
    needs_crew: ClassVar[bool] = False

    def validate(self, world: World, ship: Ship) -> None:
        if self.station not in STATION_CHANNELS:
            raise Rejected(f"No {self.station} station.")

    def describe(self) -> str:
        return f"{'delegate' if self.on else 'assume'} {self.station}"

    def apply(self, world: World, ship: Ship) -> None:
        if self.on:
            ship.delegated.add(self.station)
            for prefix in STATION_CHANNELS[self.station]:
                world.release_holds(ship.id, prefix)
        else:
            was = self.station in ship.delegated
            ship.delegated.discard(self.station)
            # the officer who had the station stands down (the battle scene ends their objectives); the others keep at
            # their work: "I have nav" doesn't stop Seven disabling their shields
            if not ship.delegated:
                ship.conn, ship.conn_saved = "", set()   # every station taken back: the captain has the bridge again
            if was and self.station == "helm" and ship.helm_mode != HelmMode.COURSE:
                # the officer was chasing (or running from) someone: the captain takes a steady helm, not their chase
                ship.desired_course, ship.helm_mode, ship.helm_target = ship.course, HelmMode.COURSE, None


@dataclass(kw_only=True)
class TakeConn(Command):
    """Give one officer command of the whole bridge, or take it back (remake extension).

    The officer runs every station; the captain's own orders still hold their
    channels against the officer, and `assume <station>` takes one station back.
    Handing the conn back to the captain restores whatever was delegated before.
    """

    officer: str = ""      # officer id; "" = the captain has the conn
    name: ClassVar[str] = "conn"
    needs_crew: ClassVar[bool] = False

    def apply(self, world: World, ship: Ship) -> None:
        if self.officer:
            if not ship.conn:
                ship.conn_saved = set(ship.delegated)
            ship.conn = self.officer
            ship.delegated = set(STATION_CHANNELS)
            for prefixes in STATION_CHANNELS.values():
                for prefix in prefixes:
                    world.release_holds(ship.id, prefix)
        elif ship.conn:
            ship.conn = ""
            ship.delegated = set(ship.conn_saved)
            ship.conn_saved = set()
            if "helm" not in ship.delegated and ship.helm_mode != HelmMode.COURSE:
                # whoever had the bridge was chasing someone: the captain takes a steady helm, not their chase
                ship.desired_course, ship.helm_mode, ship.helm_target = ship.course, HelmMode.COURSE, None

    def describe(self) -> str:
        return f"conn {self.officer or 'captain'}"


@dataclass(kw_only=True)
class SelfDestruct(Command):
    cycles: float | None = None  # None = abort
    name: ClassVar[str] = "destruct"

    def validate(self, world: World, ship: Ship) -> None:
        if self.cycles is None:
            if ship.self_destruct < 0:
                raise Rejected("No self-destruct sequence is running.")
            if ship.self_destruct <= world.rules.destruct_countdown:
                raise Rejected("Too late to abort: fewer than five cycles remain.")
        elif self.cycles < 1:
            raise Rejected("Countdown must be at least 1 cycle.")

    def apply(self, world: World, ship: Ship) -> None:
        if self.cycles is None:
            ship.self_destruct = -1.0
            world.say(ship, "Self-destruct aborted.", "good", public=True)
        else:
            ship.self_destruct = float(self.cycles)
            world.say(ship, f"Self-destruct sequence initiated: {self.cycles:.0f} cycles.", "alert", public=True)


@dataclass(kw_only=True)
class Surrender(Command):
    name: ClassVar[str] = "surrender"

    def validate(self, world: World, ship: Ship) -> None:
        if ship.status != ShipStatus.ACTIVE:
            raise Rejected("Ship is not in a position to surrender.")

    def apply(self, world: World, ship: Ship) -> None:
        world.surrender(ship)
