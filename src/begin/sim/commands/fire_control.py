"""Fire control: objectives, holding and opening fire, bait, firing at a point and the deflector pulse."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ...core.angles import bearing
from ..ship import HelmMode, Ship, Tube
from .base import Authority, Command, Rejected
from .helm import end_objectives
from .phasers import FirePhasers
from .probes import LaunchProbe
from .torpedoes import FireTorpedoes

if TYPE_CHECKING:
    from ..world import World


@dataclass(kw_only=True)
class FireBait(FireTorpedoes):
    """Fire one torpedo to draw the enemy's point defense, then the rest a moment later [E].

    A trigger-happy defense spends several banks on the first round it sees;
    the volley behind it arrives while those banks are still recharging.
    """

    delay: float = 1.0           # cycles between the bait and the volley
    name: ClassVar[str] = "fire bait"

    def validate(self, world: World, ship: Ship) -> None:
        super().validate(world, ship)
        if ship.pending_volley is not None:
            raise Rejected("A bait volley is already under way.")
        if sum(1 for t in ship.tubes if t.loaded is not None and t.intact) < 2:
            raise Rejected("Bait needs at least two loaded tubes: one to draw their fire, the rest to follow.")

    def apply(self, world: World, ship: Ship) -> None:
        self.count = 1
        super().apply(world, ship)
        target = self.target if self.target is not None else ship.target
        due = world.tick + max(1, int(round(self.delay * world.rules.ticks_per_cycle)))
        ship.pending_volley = (due, target, self.subsystem, int(self.issuer))

    def describe(self) -> str:
        return "fire one torpedo as bait, the rest to follow"


@dataclass(kw_only=True)
class SetObjective(Command):
    """Give an officer a standing objective, e.g. disable the shields of one or more ships [E]."""

    goal: str = "disable"
    group: str = "weapons"
    targets: tuple[int, ...] = ()
    officer: str = ""
    name: ClassVar[str] = "objective"
    needs_crew: ClassVar[bool] = False

    def channels(self) -> tuple[str, ...]:
        return ("objective",)

    def validate(self, world: World, ship: Ship) -> None:
        from ..objectives import DISABLE_GROUPS, GOALS, STRIKE_GROUPS

        if self.goal not in GOALS:
            raise Rejected(f"Unknown objective '{self.goal}'.")
        if self.goal == "disable" and self.group not in DISABLE_GROUPS:
            raise Rejected(f"Can't disable '{self.group}'. Choose from: {', '.join(DISABLE_GROUPS)}.")
        if self.goal == "strike" and self.group not in STRIKE_GROUPS:
            raise Rejected(f"Strike at what? Choose from: {', '.join(STRIKE_GROUPS)}.")
        if not self.targets:
            raise Rejected(f"{self.goal.capitalize()} which ships?")
        for t in self.targets:
            s = world.ships.get(t)
            if s is None or not s.exists or s.side == ship.side:
                raise Rejected(f"#{t} isn't an enemy ship in this battle.")

    def apply(self, world: World, ship: Ship) -> None:
        from ..objectives import Objective

        # a new order about the same systems replaces the old one
        ship.objectives = [o for o in ship.objectives if not (o.goal == self.goal and o.group == self.group)]
        if self.goal != "hunt":     # finding a ship fires nothing, so it changes nobody's rules of engagement
            ship.spared.difference_update(self.targets)    # a new order about her: the officer may fire on her again
            ship.hold_fire = False      # a new order to attack lifts an earlier cease fire, or the officer never shoots
        ship.objectives.append(Objective(self.goal, self.group, tuple(self.targets), self.officer, world.tick))
        if self.goal in ("disable", "capture") and self.issuer >= Authority.CAPTAIN:
            # [E] the captain hands the weapons to the officer: her own earlier target and fire orders no longer pin them
            for prefix in ("tactical", "phasers", "torpedoes"):
                world.release_holds(ship.id, prefix)

    def describe(self) -> str:
        return f"{self.goal} {self.group} on {len(self.targets)} ship{'s' if len(self.targets) != 1 else ''}"


@dataclass(kw_only=True)
class CeaseFire(Command):
    """`cease fire` [E]: stop every weapon. Officers' objectives end, a bait volley is called off,
    and neither officers nor the fire computer may fire again until the captain fires or says open fire.
    Point defense keeps shooting down torpedoes."""

    name: ClassVar[str] = "cease fire"
    needs_crew: ClassVar[bool] = False

    def apply(self, world: World, ship: Ship) -> None:
        ship.hold_fire = True
        ship.pending_volley = None
        end_objectives(world, ship, list(ship.objectives), "cancelled", "cease fire")


@dataclass(kw_only=True)
class OpenFire(Command):
    """`open fire` / `weapons free` [E]: lift a cease fire."""

    name: ClassVar[str] = "open fire"
    needs_crew: ClassVar[bool] = False

    def apply(self, world: World, ship: Ship) -> None:
        ship.hold_fire = False
        ship.spared.clear()          # weapons free: on everyone


@dataclass(kw_only=True)
class StandDown(Command):
    """`stand down` [E]: the captain takes the whole ship back from the officers at once.

    Everything a cease fire does (weapons hold, objectives end, a bait volley is called off), and every
    station and the bridge come back to the captain, evasive manoeuvres end, and a helm that was chasing
    someone steadies on its present course. Point defense keeps shooting down torpedoes.
    """

    name: ClassVar[str] = "stand down"
    needs_crew: ClassVar[bool] = False

    def apply(self, world: World, ship: Ship) -> None:
        CeaseFire(ship_id=ship.id, issuer=self.issuer).apply(world, ship)
        if ship.helm_mode != HelmMode.COURSE and ("helm" in ship.delegated or ship.evasive):
            ship.desired_course, ship.helm_mode, ship.helm_target = ship.course, HelmMode.COURSE, None
        ship.evasive, ship.evasive_resume = False, None
        ship.delegated = set()
        ship.conn, ship.conn_saved = "", set()


def fire_target(cmd: Command, ship: Ship) -> int | None:
    """The ship an offensive command shoots at: its own target, else the ship's."""
    t = getattr(cmd, "target", None)
    return t if isinstance(t, int) else ship.target


def offensive_fire(cmd: Command) -> bool:
    """A command that fires on someone: what a cease fire stops (point defense isn't, and nor is a
    tachyon detector round, which harms nobody: it only looks)."""
    if isinstance(cmd, FirePhasers):
        return not cmd.defensive
    return isinstance(cmd, (FireTorpedoes, FireAtPoint, LaunchProbe))


@dataclass(kw_only=True)
class EndObjective(Command):
    """Finish, give up or cancel objectives: one group, or all of them when `group` is empty [E]."""

    group: str = ""
    outcome: str = "cancelled"   # "done" | "impossible" | "cancelled"
    reason: str = ""
    officer: str | None = None   # only this officer's objectives ("" = the science officer's default); None = anyone's
    name: ClassVar[str] = "end objective"
    needs_crew: ClassVar[bool] = False

    def channels(self) -> tuple[str, ...]:
        # [E] an officer reporting her objective met or impossible is a report, not a rival order: no hold stops it
        return ("objective",) if self.outcome == "cancelled" else ()

    def validate(self, world: World, ship: Ship) -> None:
        if not ship.objectives:
            raise Rejected("No objectives to end.")

    def apply(self, world: World, ship: Ship) -> None:
        ending = [o for o in ship.objectives if (not self.group or o.group == self.group)
                  and (self.officer is None or o.officer == self.officer)]
        end_objectives(world, ship, ending, self.outcome, self.reason)

    def describe(self) -> str:
        return f"objective {self.group or 'all'} {self.outcome}"


@dataclass(kw_only=True)
class FireAtPoint(Command):
    """Fire ordinary torpedoes fused to burst at a point: beside a ship, or between several [E].

    A low proximity setting with a time fuse means the round looks, to the
    enemy's point defense, like a miss until it bursts.
    """

    x: float
    y: float
    tubes: tuple[int, ...] | None = None
    prox: float | None = None
    target: int | None = None        # whose systems the blast is aimed at
    spread: float = 0.0              # tubes burst on a ring this wide around the point, covering aim error
    subsystem: str | None = None
    name: ClassVar[str] = "fire torpedoes at point"

    def channels(self) -> tuple[str, ...]:
        return ("torpedoes",)

    def _ready(self, world: World, ship: Ship) -> list[Tube]:
        out = []
        for t in ship.tubes:
            if self.tubes is not None and t.index not in self.tubes:
                continue
            if t.loaded is None or not t.intact or not t.enabled:
                continue
            spec = world.content.torpedoes[t.loaded.ordnance]
            if spec.special:
                continue
            out.append(t)
        return out

    def validate(self, world: World, ship: Ship) -> None:
        tubes = self._ready(world, ship)
        if not tubes:
            raise Rejected("No tube is loaded with an ordinary torpedo.")
        spec = world.content.torpedoes[tubes[0].loaded.ordnance]  # type: ignore[union-attr]
        reach = spec.velocity * world.rules.units_per_warp * (spec.arm_time + spec.max_time_fuse)
        d = math.hypot(self.x - ship.x, self.y - ship.y)
        if d > reach:
            raise Rejected(f"That point is {d:,.0f} away; torpedoes reach {reach:,.0f}.")
        if d < spec.velocity * world.rules.units_per_warp * spec.arm_time:
            raise Rejected("Too close: the torpedoes wouldn't be armed by then.")

    def apply(self, world: World, ship: Ship) -> None:
        from ..systems.ordnance import launch_at_point

        prox = None if self.prox is None else max(world.rules.prox_floor, self.prox)
        tubes = self._ready(world, ship)
        for k, t in enumerate(tubes):
            x, y = self.x, self.y
            if self.spread > 0 and len(tubes) > 1:
                a = math.tau * k / len(tubes)
                x, y = x + math.sin(a) * self.spread, y + math.cos(a) * self.spread
            launch_at_point(world, ship, t, x, y, prox=prox, target=self.target, subsystem=self.subsystem)

    def describe(self) -> str:
        return f"torpedoes to burst at ({self.x:,.0f}, {self.y:,.0f})"


@dataclass(kw_only=True)
class DeflectorPulse(Command):
    """Sweep a cone ahead of the ship with tachyons from the deflector dish, lighting up cloaked ships [E]."""

    name: ClassVar[str] = "pulse"

    def channels(self) -> tuple[str, ...]:
        return ("deflector",)

    def validate(self, world: World, ship: Ship) -> None:
        if ship.cls.is_base:
            raise Rejected("Bases have no deflector dish.")
        if not ship.deflector_ready:
            raise Rejected("The deflector isn't set up for tachyon pulses. Ask Spock or Seven ('design deflector').")
        if ship.deflector_cooldown > 0:
            raise Rejected(f"The deflector is recharging ({ship.deflector_cooldown:.0f} cycles).")
        cost = world.rules.deflector_pulse_energy
        if ship.battery_charge() < cost:
            raise Rejected(f"A pulse needs {cost:.0f} energy in the batteries ({ship.battery_charge():.0f} stored).")

    def apply(self, world: World, ship: Ship) -> None:
        from ...core.angles import ang_dist
        from ..events import DeflectorPulsed, Message, Tone

        rules = world.rules
        need = rules.deflector_pulse_energy
        for b in ship.batteries:
            if b.online and need > 0:
                take = min(b.charge, need)
                b.charge -= take
                need -= take
        ship.deflector_cooldown = rules.deflector_pulse_cooldown
        found = 0
        for s in world.ships.values():
            if s is ship or not s.alive or not s.cloaked:
                continue
            d = math.hypot(s.x - ship.x, s.y - ship.y)
            if d <= rules.deflector_pulse_range and ang_dist(bearing(s.x - ship.x, s.y - ship.y), ship.course) <= rules.deflector_pulse_arc / 2:
                s.reveal_time = max(s.reveal_time, rules.deflector_pulse_reveal)
                found += 1
        world.emit(DeflectorPulsed(world.tick, ship.id, ship.x, ship.y, ship.course, rules.deflector_pulse_arc,
                                   rules.deflector_pulse_range, found))
        text = (f"Deflector pulse: {found} cloaked ship{'s' if found != 1 else ''} lit up for "
                f"{rules.deflector_pulse_reveal:.0f} cycles." if found else "Deflector pulse: nothing cloaked ahead.")
        world.emit(Message(world.tick, text, Tone.GOOD if found else Tone.CAUTION, ship_id=ship.id,
                           visible_to=frozenset({ship.side})))

    def describe(self) -> str:
        return "deflector pulse"
