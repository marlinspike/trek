"""Ship operations: scans, hails, the cloak, sweeps and seekers, tractor beams, docking and transporters."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ..ship import Ship, ShipStatus, Tube
from .base import Command, Rejected, _require_target
from .helm import _end_evasive

if TYPE_CHECKING:
    from ..world import World


@dataclass(kw_only=True)
class Scan(Command):
    target: int
    by: str = ""            # the officer running the scan ("" the captain) [E]
    name: ClassVar[str] = "scan"

    def validate(self, world: World, ship: Ship) -> None:
        t = _require_target(world, ship, self.target)
        if ship.sensors is None or ship.sensors.destroyed:
            raise Rejected("Sensors are inoperative.")
        if not world.is_visible(ship.side, t.id):
            raise Rejected("Target is not in sensor contact.")
        reach = ship.sensor_range() * world.rules.scan_range_fraction
        d = math.hypot(t.x - ship.x, t.y - ship.y)
        if d > reach:
            raise Rejected(f"Too far for a detailed scan ({d:,.0f} > {reach:,.0f}).")

    def apply(self, world: World, ship: Ship) -> None:
        world.begin_scan(ship, self.target, self.by)


@dataclass(kw_only=True)
class Hail(Command):
    """Hail an enemy ship [E]: demand surrender, tell them to withdraw, threaten, taunt or just talk.

    The enemy captain answers from their state of mind (sim/systems/disposition.py). `persuasion` is
    0..1.5 (1 = an ordinary hail), judged by the language model when there is one; `threat` and `bluff`
    mark a hail backed by a threat, or by strength we don't have. `text` is what the captain said.
    """

    target: int
    intent: str = "talk"
    persuasion: float = 1.0
    threat: bool = False
    bluff: bool = False
    text: str = ""
    release: bool = False          # we offer to send back the prisoners we hold, if they agree
    answered: object = None        # the HailAnswered event, once carried out (for whoever issued it)
    name: ClassVar[str] = "hail"

    def validate(self, world: World, ship: Ship) -> None:
        from ..systems.disposition import HAIL_GAP_CYCLES, INTENTS

        if self.intent not in INTENTS:
            raise Rejected(f"Unknown hail '{self.intent}'.")
        t = world.ships.get(self.target)
        if t is None or not t.exists:
            raise Rejected("That ship no longer exists.")
        if t.side == ship.side:
            raise Rejected(f"{t.name} is one of ours: use 'tell' to give her orders.")
        if world.apparent_position(ship.side, t.id) is None:
            raise Rejected("No sensor contact with that ship.")
        if t.status == ShipStatus.SURRENDERED:
            raise Rejected(f"{t.name} has already surrendered. Beam a party of six or more across to take her.")
        if not t.alive or t.crew <= 0:
            raise Rejected(f"Nobody aboard {t.name} is answering.")
        since = (world.tick - t.mood.last_hailed) / world.rules.ticks_per_cycle
        if since < HAIL_GAP_CYCLES:
            raise Rejected(f"{t.name} has just answered us (try again in {HAIL_GAP_CYCLES - since:.0f} cycles).")

    def apply(self, world: World, ship: Ship) -> None:
        from ..systems.disposition import answer

        self.answered = answer(world, ship, world.ships[self.target], self.intent, self.persuasion, self.threat,
                               self.bluff, self.release)

    def validate_now(self, world: World, ship: Ship) -> str | None:
        """The refusal, if any, before the hail is put into words (and maybe judged by the model)."""
        try:
            self.validate(world, ship)
        except Rejected as r:
            return str(r)
        return None

    def describe(self) -> str:
        return "hail"


@dataclass(kw_only=True)
class SetCloak(Command):
    on: bool
    name: ClassVar[str] = "cloak"

    def validate(self, world: World, ship: Ship) -> None:
        if not ship.cls.can_cloak or ship.cloak is None:
            raise Rejected(f"The {ship.cls.name} has no cloaking device.")
        if self.on and ship.cloak.destroyed:
            raise Rejected("Cloaking device is destroyed.")
        if self.on and not ship.cloak.intact:
            raise Rejected("Cloaking device is damaged.")

    def apply(self, world: World, ship: Ship) -> None:
        ship.cloaked = self.on
        world.say(ship, "Cloak engaged." if self.on else "Cloak disengaged.", "info")


@dataclass(kw_only=True)
class Sweep(Command):
    """[E] The science officer sweeps for plasma trails: for a while our sensors follow warp plasma much further
    (sensors.SWEEP_REACH), cloaked ships' included. `target` names one ship to look for (the report)."""

    target: int | None = None
    name: ClassVar[str] = "sweep"

    def channels(self) -> tuple[str, ...]:
        return ("science.sweep",)

    def validate(self, world: World, ship: Ship) -> None:
        if ship.sensors is None or ship.sensors.destroyed:
            raise Rejected("Sensors are inoperative.")

    def apply(self, world: World, ship: Ship) -> None:
        from ..systems import sensors

        ship.sweep = SWEEP_CYCLES
        seen = sensors.plasma_seen(world, ship.side)
        if self.target is not None:
            t = world.ships.get(self.target)
            name = world.label(ship.side, self.target)
            text = (f"Plasma trail found: {name}, a damaged warp drive." if self.target in seen else
                    f"No plasma from {name}. Her drives are sound, or she isn't at warp." if t is not None else
                    "Nothing to sweep for.")
        else:
            names = [world.label(ship.side, sid) for sid in seen]
            text = (f"Plasma trails: {', '.join(names)}." if names else
                    "Sweeping for plasma trails. Nothing yet: their drives are sound, or they aren't at warp.")
        world.say(ship, text, "good" if seen else "info", speaker="Science")

    def describe(self) -> str:
        return "sweep for plasma trails"


SWEEP_CYCLES = 20.0


@dataclass(kw_only=True)
class FireSeeker(Command):
    """[E] Fire a plasma-seeker down a ship's plasma trail: it flies the trail and homes on her at its end."""

    target: int
    name: ClassVar[str] = "seeker"

    def channels(self) -> tuple[str, ...]:
        return ("torpedoes",)

    def _tube(self, ship: Ship) -> Tube:
        tube = next((t for t in ship.tubes if t.loaded is not None and t.loaded.ordnance == "seeker"), None)
        if tube is None:
            raise Rejected("No plasma-seeker is loaded. Ask Seven or Spock to design one ('design seeker').")
        return tube

    def validate(self, world: World, ship: Ship) -> None:
        from ..systems import sensors

        self._tube(ship)
        if self.target not in sensors.plasma_seen(world, ship.side):
            raise Rejected("We have no plasma trail from that ship. Try 'sweep'.")

    def apply(self, world: World, ship: Ship) -> None:
        from ..systems.ordnance import launch_seeker

        launch_seeker(world, ship, self._tube(ship), self.target)

    def describe(self) -> str:
        return "fire a plasma-seeker"


@dataclass(kw_only=True)
class Tractor(Command):
    target: int | None
    name: ClassVar[str] = "tractor"

    def validate(self, world: World, ship: Ship) -> None:
        if self.target is None:
            return
        if not ship.cls.has_tractor or ship.tractor is None or not ship.tractor.intact:
            raise Rejected("No working tractor beam.")
        t = _require_target(world, ship, self.target)
        d = math.hypot(t.x - ship.x, t.y - ship.y)
        if d > world.rules.tractor_range:
            raise Rejected(f"Target beyond tractor range ({d:,.0f} > {world.rules.tractor_range:,.0f}).")

    def apply(self, world: World, ship: Ship) -> None:
        ship.tractor_target = self.target
        world.say(ship, "Tractor beam engaged." if self.target is not None else "Tractor beam released.", "info")


@dataclass(kw_only=True)
class Dock(Command):
    host: int | None  # None = undock
    name: ClassVar[str] = "dock"

    def validate(self, world: World, ship: Ship) -> None:
        if self.host is None:
            if ship.docked_to is None:
                raise Rejected("Not docked.")
            return
        h = world.ships.get(self.host)
        if h is None or not h.alive:
            raise Rejected("No such base.")
        if h.side != ship.side:
            raise Rejected("Cannot dock with a hostile vessel.")
        if h.cls.mass_capacity <= 0:
            raise Rejected(f"The {h.cls.name} has no docking facilities.")
        d = math.hypot(h.x - ship.x, h.y - ship.y)
        if d > world.rules.dock_range:
            raise Rejected(f"Too far to dock ({d:,.0f} > {world.rules.dock_range:,.0f}).")
        used = sum(s.cls.mass for s in world.ships.values() if s.docked_to == h.id)
        if used + ship.cls.mass > h.cls.mass_capacity:
            raise Rejected("Docking bays are full.")

    def apply(self, world: World, ship: Ship) -> None:
        _end_evasive(world, ship, self)
        ship.docked_to = self.host
        if self.host is not None:
            ship.desired_warp = 0.0
            ship.warp = 0.0
            ship.tractor_target = None
            world.say(ship, f"Docked with {world.ships[self.host].name}.", "good")
        else:
            world.say(ship, "Undocked.", "info")


@dataclass(kw_only=True)
class Transport(Command):
    """Beam crew to an ally, or boarding parties onto an enemy (shields facing must be down)."""

    target: int
    count: int
    name: ClassVar[str] = "transport"

    def validate(self, world: World, ship: Ship) -> None:
        t = _require_target(world, ship, self.target)
        working = [x for x in ship.transporters if not x.destroyed]
        if not working:
            raise Rejected("No working transporters.")
        d = math.hypot(t.x - ship.x, t.y - ship.y)
        if d > world.rules.beam_range:
            raise Rejected(f"Out of transporter range ({d:,.0f} > {world.rules.beam_range:,.0f}).")
        from .. import collective
        from ..systems.damage import relative_bearing_from

        if collective.is_hive(world, ship) and t.side != ship.side:
            # the Borg beam drones through shields, theirs and ours, unless ours are tuned against them [E]
            why = collective.can_beam_through(world, ship, t)
            if why is not None:
                raise Rejected(why)
            if ship.crew - self.count < 6:
                raise Rejected("Not enough drones to spare.")
            return
        # Begin beamed through the facing shield only; we beam through any of hers that is fully down [E]
        if t.shields and all(x.effective >= world.rules.shield_gap for x in t.shields):
            raise Rejected(f"All of {t.name}'s shields are up: one must be down to beam through.")
        own = ship.shield_for_bearing(relative_bearing_from(ship, t.x, t.y))
        if own is not None and own.effective > 0:
            raise Rejected("Our facing shield must be lowered to transport.")
        if ship.crew - self.count < 6:
            raise Rejected("Not enough crew to spare.")

    def apply(self, world: World, ship: Ship) -> None:
        world.transport(ship, world.ships[self.target], self.count)
