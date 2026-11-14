"""The Borg [E] (sim/collective.py, sim/away.py): the hive, the away team and the shuttle."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ..ship import Ship
from .base import Command, Rejected, _require_target

if TYPE_CHECKING:
    from ..world import World

DUTIES = ("shields", "phasers", "harmonics")


@dataclass(kw_only=True)
class Remodulate(Command):
    """Change our phasers' frequency: the hive must learn the new one from nothing, though each is learned faster
    than the last. The banks lose their charge and fire again once they have recharged on the new frequency.
    `by` is who chose it: Seven's random pattern is the hardest for them to predict."""

    by: str = ""
    name: ClassVar[str] = "remodulate"

    def channels(self) -> tuple[str, ...]:
        return ("phasers.remodulate",)

    def validate(self, world: World, ship: Ship) -> None:
        if not any(b.intact or b.damage < 100 for b in ship.banks):
            raise Rejected("No phaser banks to remodulate.")
        if ship.remodulating > 0:
            raise Rejected("The banks are already being remodulated.")

    def apply(self, world: World, ship: Ship) -> None:
        from .. import collective
        from ..events import HiveEvent

        ship.phaser_freq += 1
        ship.freq_pattern = {"seven": 0.35, "spock": 0.7}.get(self.by, 1.0)
        ship.remodulating = collective.REMODULATE_CYCLES
        for b in ship.banks:
            b.charge = 0.0
        world.emit(HiveEvent(world.tick, ship.id, "remodulated", None, self.by))

    def describe(self) -> str:
        return "remodulate phasers"


@dataclass(kw_only=True)
class SetDuty(Command):
    """Put an officer on hive work [E]: "shields" (tune our shield harmonics against their beams), "phasers"
    (watch the hive's adaptation and remodulate our phasers before they learn them), "harmonics" (keep scanning
    their ships for their weak points and shield harmonics), or "" to stand them down. One duty at a time: the
    officer can't do the others while on it."""

    duty: str
    by: str = ""            # "" the science officer: Seven, or Spock when she is away
    name: ClassVar[str] = "duty"

    def channels(self) -> tuple[str, ...]:
        return ("science.duty",)

    def validate(self, world: World, ship: Ship) -> None:
        if self.duty and self.duty not in DUTIES:
            raise Rejected(f"No duty called '{self.duty}'. Known: {', '.join(DUTIES)}.")
        if not self.by and self.duty:
            if not _science_officer(ship):
                raise Rejected("Seven and Spock are both off the ship.")
            return
        if self.by in ship.away:
            raise Rejected("They're on the away team.")
        if self.by in ship.wounded:
            raise Rejected("They're in sickbay.")
        if self.duty == "shields" and not ship.shields:
            raise Rejected("No shields to tune.")

    def apply(self, world: World, ship: Ship) -> None:
        if self.duty != "shields" and ship.duty == "shields":
            pass        # the tuning holds where it is; it just stops improving
        ship.duty, ship.duty_by = self.duty, (self.by or _science_officer(ship)) if self.duty else ""

    def describe(self) -> str:
        return f"duty {self.duty or 'off'}"


def _science_officer(ship: Ship) -> str:
    """Who takes hive work when the captain names nobody: Seven, or Spock while she is away or hurt."""
    gone = ship.away | ship.wounded
    return next((o for o in ("seven", "spock") if o not in gone), "")


COUNTERMEASURES = ("security", "seal")


@dataclass(kw_only=True)
class Countermeasure(Command):
    """Fight drones aboard [E]: "security" puts security teams on the decks (the drones win fewer rounds for a
    while); "seal" seals and vents the sections they hold (most of them die, and a few of ours)."""

    kind: str
    name: ClassVar[str] = "repel"

    def validate(self, world: World, ship: Ship) -> None:
        if self.kind not in COUNTERMEASURES:
            raise Rejected(f"No countermeasure called '{self.kind}'.")
        if ship.boarders <= 0:
            raise Rejected("There are no boarders aboard.")
        if self.kind == "seal" and ship.seal_ready > 0:
            raise Rejected(f"The sections are still being sealed: {ship.seal_ready:.0f} cycles.")
        if self.kind == "security" and ship.security > 0:
            raise Rejected("Security teams are already on the decks.")

    def apply(self, world: World, ship: Ship) -> None:
        from .. import collective

        if self.kind == "security":
            ship.security = collective.SECURITY_CYCLES
            world.say(ship, "Security teams to every deck the drones hold.", "info", speaker="Security")
            return
        killed, ours = collective.seal_section(world, ship)
        lost = f" We lost {ours} of ours." if ours else ""
        world.say(ship, f"Sections sealed and vented: {killed} drones dead.{lost}", "caution", speaker="Engineering")

    def describe(self) -> str:
        return f"repel boarders ({self.kind})"


@dataclass(kw_only=True)
class AwayTeam(Command):
    """Send officers across to a Borg ship (sim/away.py): by shuttle while she is awake, or by transporter when
    she is dormant and close. `members` are officer ids; `task` one of sim.away.TASKS."""

    target: int
    task: str
    members: tuple[str, ...] = ("worf",)
    by_shuttle: bool = True
    name: ClassVar[str] = "away"

    def validate(self, world: World, ship: Ship) -> None:
        from .. import away, collective

        t = _require_target(world, ship, self.target)
        if not collective.is_hive(world, t) or t.side == ship.side:
            raise Rejected("Away teams are for Borg ships.")
        if not t.alive:
            raise Rejected(f"{t.name} is not a working ship any more.")
        if self.task not in away.TASKS:
            raise Rejected(f"No task called '{self.task}'. Known: {', '.join(away.TASKS)}.")
        if not self.members:
            raise Rejected("Who goes?")
        gone = [m for m in self.members if m in ship.away or m in ship.wounded]
        if gone:
            raise Rejected("They're not available: on another team, or in sickbay.")
        if away.op_for(world, ship.id) is not None:
            raise Rejected("An away team is already out.")
        if self.task == "harmonics" and "seven" not in self.members:
            raise Rejected("Only Seven can take their harmonics: she knows how the Collective keeps them.")
        if away.TASKS[self.task][2] and t.dormant <= 0:
            raise Rejected(f"Only while {t.name}'s drones are dormant.")
        if self.by_shuttle:
            if not away.has_shuttles(ship):
                raise Rejected(f"{ship.name} carries no shuttles.")
            return
        if t.dormant <= 0:
            raise Rejected(f"{t.name}'s drones are awake: we can't beam across. Take a shuttle.")
        if not any(not x.destroyed for x in ship.transporters):
            raise Rejected("No working transporters.")
        d = math.hypot(t.x - ship.x, t.y - ship.y)
        if d > world.rules.beam_range:
            raise Rejected(f"Out of transporter range ({d:,.0f} > {world.rules.beam_range:,.0f}).")

    def apply(self, world: World, ship: Ship) -> None:
        from .. import away

        away.launch(world, ship, world.ships[self.target], self.members, self.task, self.by_shuttle)

    def describe(self) -> str:
        return f"away team ({self.task})"


@dataclass(kw_only=True)
class ShuttleOrder(Command):
    """The captain hails the away team [E]: `order` "recall" brings them home, "task" sets them a new task."""

    order: str
    task: str = ""
    name: ClassVar[str] = "shuttle"
    needs_crew: ClassVar[bool] = False

    def validate(self, world: World, ship: Ship) -> None:
        from .. import away

        if away.op_for(world, ship.id) is None:
            raise Rejected("No away team is out.")
        if self.order not in ("recall", "task"):
            raise Rejected("Recall them, or give them a task.")
        if self.order == "task" and self.task not in away.TASKS:
            raise Rejected(f"No task called '{self.task}'. Known: {', '.join(away.TASKS)}.")

    def apply(self, world: World, ship: Ship) -> None:
        from .. import away

        op = away.op_for(world, ship.id)
        assert op is not None
        reply = away.order(world, op, self.order, self.task)
        speaker = {"worf": "Lieutenant Worf", "seven": "Seven of Nine"}.get(op.members[0], "Away team") \
            if op.members else "Shuttle"
        world.say(ship, reply, "info", speaker=speaker)

    def describe(self) -> str:
        return "recall the away team" if self.order == "recall" else f"away team: {self.task}"
