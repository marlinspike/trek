"""Helm: course, warp, pursuit and evasion, and ending a battle."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ...core.angles import norm360
from ..ship import HelmMode, Ship
from .base import Authority, Command, Rejected, _require_target

if TYPE_CHECKING:
    from ..objectives import Objective
    from ..world import World


@dataclass(kw_only=True)
class SetHelm(Command):
    course: float | None = None
    warp: float | None = None
    name: ClassVar[str] = "helm"

    def channels(self) -> tuple[str, ...]:
        return ("helm",)

    def validate(self, world: World, ship: Ship) -> None:
        if ship.cls.is_base:
            raise Rejected(f"{ship.cls.name}s are immobile.")
        if self.warp is not None and self.warp > ship.max_attainable_warp + 1e-6 and ship.max_attainable_warp < ship.cls.max_warp:
            # accepted, but the helm explains the limit
            world.say(ship, f"Helm: maximum attainable warp is {ship.max_attainable_warp:.1f}.", "caution")

    def apply(self, world: World, ship: Ship) -> None:
        _end_evasive(world, ship, self)
        if self.course is not None:
            ship.desired_course = norm360(self.course)
            ship.helm_mode = HelmMode.COURSE
            ship.helm_target = None
        if self.warp is not None:
            ship.desired_warp = max(world.rules.min_warp, min(self.warp, ship.cls.max_warp))

    def describe(self) -> str:
        parts = []
        if self.course is not None:
            parts.append(f"course {self.course:.0f}")
        if self.warp is not None:
            parts.append(f"warp {self.warp:.1f}")
        return "helm " + " ".join(parts)


def end_objectives(world: World, ship: Ship, ending: list[Objective], outcome: str, reason: str) -> None:
    """Take objectives off the ship and announce each. A disable that worked spares its targets from the officers'
    and the computer's guns (the captain wanted her crippled, not destroyed); the aim goes back to the hull."""
    from ..events import ObjectiveEnded

    ship.objectives = [o for o in ship.objectives if o not in ending]
    still = {t for o in ship.objectives for t in o.targets}   # "their shields and engines": the engines are next
    for o in ending:
        if outcome == "done" and o.goal == "disable":
            ship.spared.update(set(o.targets) - still)
        if o.goal not in ("destroy", "hunt") and not (o.goal == "strike" and o.group == "hull") \
                and ship.target_subsystem is not None:
            ship.target_subsystem = None     # the systems were the objective's aim: by default we aim at the hull
        world.emit(ObjectiveEnded(world.tick, ship.id, o.officer, o.goal, o.group, o.targets, outcome, reason))


def _end_evasive(world: World, ship: Ship, cmd: Command) -> None:
    """Any navigation order from the captain ends evasive manoeuvres."""
    if ship.evasive and cmd.issuer >= Authority.CAPTAIN:
        ship.evasive = False
        ship.evasive_resume = None
        world.say(ship, "Evasive manoeuvres ended: the helm takes your order.", "dim", speaker="Helm")


@dataclass(kw_only=True)
class Evasive(Command):
    """Tell the helm to dodge incoming torpedoes on its own (remake extension, Federation drill).

    The helm keeps the captain's course and warp, turns away from each torpedo
    that would hit, and comes back afterwards. Any navigation order from the
    captain (helm, warp, stop, pursue, elude, dock) ends it.
    """

    on: bool = True
    name: ClassVar[str] = "evasive"

    def validate(self, world: World, ship: Ship) -> None:
        if not self.on:
            return
        if ship.cls.is_base:
            raise Rejected(f"{ship.cls.name}s are immobile.")
        faction = world.content.factions.get(ship.faction)
        if faction is None or "evasive" not in faction.orders:
            name = faction.name if faction is not None else ship.faction
            raise Rejected(f"{name} crews aren't drilled in evasive manoeuvres; that is a Starfleet order.")

    def apply(self, world: World, ship: Ship) -> None:
        if self.on:
            if not ship.evasive:
                ship.evasive_resume = (ship.desired_course, ship.desired_warp, ship.helm_mode, ship.helm_target)
            ship.evasive = True
            world.release_holds(ship.id, "helm")   # the captain's last helm order no longer pins the helm
        else:
            ship.evasive = False
            ship.evasive_resume = None


@dataclass(kw_only=True)
class Pursue(Command):
    target: int
    warp: float | None = None
    elude: bool = False
    keep: float | None = None   # [E] hold the target at this range: close when beyond it, open when inside, circle at it
    name: ClassVar[str] = "pursue"

    def channels(self) -> tuple[str, ...]:
        return ("helm",)

    def validate(self, world: World, ship: Ship) -> None:
        if ship.cls.is_base:
            raise Rejected(f"{ship.cls.name}s are immobile.")
        _require_target(world, ship, self.target)

    def apply(self, world: World, ship: Ship) -> None:
        _end_evasive(world, ship, self)
        ship.helm_mode = HelmMode.ELUDE if self.elude else HelmMode.PURSUE
        ship.helm_target = self.target
        ship.helm_keep = self.keep if self.keep is not None and self.keep > 0 else None
        if self.warp is not None:
            ship.desired_warp = max(world.rules.min_warp, min(self.warp, ship.cls.max_warp))
