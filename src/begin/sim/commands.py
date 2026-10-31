"""Typed commands: the only way anything changes a ship's intent.

Players, AI captains, ship computers and delegated officers all submit the
same command types. Each command validates against the current world and
either applies or is rejected with a human-readable reason.

Authority and control channels: a command declares the channels it drives
(e.g. "helm"). When the CAPTAIN issues one, lower authorities (computer,
officer) are locked out of that channel for a hold period, so automation
never fights an explicit order. Delegating a station clears its holds.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import IntEnum
from typing import TYPE_CHECKING, ClassVar

from ..core.angles import bearing, in_arc, norm360
from .ship import BankRole, FireMode, HelmMode, Kind, PDDoctrine, RepairTarget, Ship, ShipStatus, TARGETABLE_GROUPS, Tube

if TYPE_CHECKING:
    from .world import World


class Authority(IntEnum):
    COMPUTER = 1
    OFFICER = 2
    AI_CAPTAIN = 3
    CAPTAIN = 4


class Rejected(Exception):
    """Raised by `validate` with the reason shown to whoever issued the command."""


@dataclass(kw_only=True)
class Command:
    ship_id: int
    issuer: Authority = Authority.CAPTAIN
    source: str = "captain"

    name: ClassVar[str] = "command"
    needs_crew: ClassVar[bool] = True

    def channels(self) -> tuple[str, ...]:
        return ()

    def validate(self, world: World, ship: Ship) -> None:
        """Raise `Rejected` if the command cannot be carried out now."""

    def apply(self, world: World, ship: Ship) -> None:
        raise NotImplementedError

    def describe(self) -> str:
        return self.name


def _require_target(world: World, ship: Ship, target: int | None) -> Ship:
    if target is None:
        raise Rejected("No target selected.")
    t = world.ships.get(target)
    if t is None or not t.exists:
        raise Rejected("That ship no longer exists.")
    if t.id == ship.id:
        raise Rejected("Cannot target own ship.")
    if world.apparent_position(ship.side, target) is None:
        raise Rejected("No sensor contact with that ship.")
    return t


def _indices(items: list, wanted: tuple[int, ...] | None) -> list[int]:  # type: ignore[type-arg]
    if wanted is None:
        return list(range(len(items)))
    return [i for i in wanted if 0 <= i < len(items)]


def _tube_list(idx: list[int]) -> str:
    """'tube 3', 'tubes 7 and 8', 'tubes 1-6' (1-based, runs collapsed)."""
    nums = sorted(i + 1 for i in idx)
    if len(nums) == 1:
        return f"tube {nums[0]}"
    runs: list[str] = []
    start = prev = nums[0]
    for n in [*nums[1:], None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        runs.append(str(start) if start == prev else f"{start} and {prev}" if prev == start + 1 else f"{start}-{prev}")
        if n is not None:
            start = prev = n
    return "tubes " + (", ".join(runs[:-1]) + " and " + runs[-1] if len(runs) > 1 else runs[0])


def _arc_advice(world: World, ship: Ship, idx: list[int], target: int | None) -> str:
    """Why these tubes can't bear, and which way to turn."""
    cover = _arc_words([(ship.tubes[i].mount.arc_center, ship.tubes[i].mount.arc_width) for i in idx])
    pos = world.apparent_position(ship.side, target) if target is not None else None
    if pos is None:
        return f"with no target they launch along their mark, which is outside their arc ({cover})."
    rel = norm360(bearing(pos[0] - ship.x, pos[1] - ship.y) - ship.course)
    rel180 = rel - 360.0 if rel > 180.0 else rel
    where = ("dead ahead" if abs(rel180) < 10 else "astern" if abs(rel180) > 150 else
             f"{abs(rel180):.0f}° to {'starboard' if rel180 > 0 else 'port'}")
    return f"the target is {where} (mark {rel:.0f}) and they cover {cover}. Turn to bring it into their arc."


def _arc_words(arcs: list[tuple[float, float]]) -> str:
    """The span a set of firing arcs covers, in words: 'from 95° port to 95° starboard'."""
    if any(w >= 360.0 for _, w in arcs):
        return "every bearing"
    for ref, name in ((0.0, "bow"), (180.0, "stern")):
        offs = [((c - ref + 180.0) % 360.0) - 180.0 for c, _ in arcs]
        if all(abs(o) <= 90.0 for o in offs):
            lo = min(o - w / 2.0 for o, (_, w) in zip(offs, arcs))
            hi = max(o + w / 2.0 for o, (_, w) in zip(offs, arcs))
            if lo < -180.0 or hi > 180.0:
                break
            if ref == 180.0:  # seen from the stern, port and starboard swap
                lo, hi = -hi, -lo
            if abs(lo + hi) < 1.0:
                return f"{hi:.0f}° either side of the {name}"
            side = (lambda a: f"{abs(a):.0f}° {'starboard' if a > 0 else 'port'}") if name == "bow" else \
                (lambda a: f"{abs(a):.0f}° {'port' if a > 0 else 'starboard'}")
            return f"from {side(lo)} to {side(hi)} of the {name}"
    return "; ".join(f"{w / 2.0:.0f}° either side of mark {norm360(c):.0f}" for c, w in arcs)


# ------------------------------------------------------------------ helm

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
        if self.warp is not None:
            ship.desired_warp = max(world.rules.min_warp, min(self.warp, ship.cls.max_warp))


# ------------------------------------------------------------------ targeting

@dataclass(kw_only=True)
class SelectTarget(Command):
    """Designate the fire-control target (and optionally a subsystem group) and lock weapons."""

    target: int | None
    subsystem: str | None = None
    lock_weapons: bool = True
    name: ClassVar[str] = "target"

    def channels(self) -> tuple[str, ...]:
        return ("tactical.target",)

    def validate(self, world: World, ship: Ship) -> None:
        if self.target is not None:
            _require_target(world, ship, self.target)
        if self.subsystem is not None and self.subsystem not in TARGETABLE_GROUPS:
            raise Rejected(f"Unknown subsystem group '{self.subsystem}'.")

    def apply(self, world: World, ship: Ship) -> None:
        ship.target = self.target
        ship.target_subsystem = self.subsystem if self.target is not None else None
        if self.lock_weapons:
            for b in ship.banks:
                if b.role != BankRole.DEFENSE:
                    b.lock = self.target
            for t in ship.tubes:
                t.lock = self.target


@dataclass(kw_only=True)
class LockWeapons(Command):
    target: int | None
    banks: tuple[int, ...] | None = None
    tubes: tuple[int, ...] | None = None
    phasers: bool = True
    torpedoes: bool = False
    dispersion: float | None = None
    name: ClassVar[str] = "lock"

    def validate(self, world: World, ship: Ship) -> None:
        if self.target is not None:
            _require_target(world, ship, self.target)

    def apply(self, world: World, ship: Ship) -> None:
        if self.phasers:
            for i in _indices(ship.banks, self.banks):
                ship.banks[i].lock = self.target
        if self.torpedoes:
            idx = _indices(ship.tubes, self.tubes)
            for k, i in enumerate(idx):
                ship.tubes[i].lock = self.target
                if self.dispersion is not None:
                    n = len(idx)
                    ship.tubes[i].dispersion = 0.0 if n < 2 else -self.dispersion / 2 + self.dispersion * k / (n - 1)


@dataclass(kw_only=True)
class TurnMounts(Command):
    """Point banks or tubes at a fixed relative bearing (unlocks them)."""

    mark: float
    banks: tuple[int, ...] | None = None
    tubes: tuple[int, ...] | None = None
    name: ClassVar[str] = "turn"

    def apply(self, world: World, ship: Ship) -> None:
        if self.banks is not None or self.tubes is None:
            for i in _indices(ship.banks, self.banks):
                ship.banks[i].lock = None
                ship.banks[i].mark = norm360(self.mark)
        if self.tubes is not None:
            for i in _indices(ship.tubes, self.tubes):
                ship.tubes[i].lock = None
                ship.tubes[i].mark = norm360(self.mark)


# ------------------------------------------------------------------ phasers

@dataclass(kw_only=True)
class FirePhasers(Command):
    """Fire phaser banks.

    banks None = every ready bank that can bear on the target (or along its
    current mark when there is no target). With `max_banks` the computer or
    an AI can fire exactly as many as it wants. `at_bearing` fires at a
    world bearing instead of a ship (point defense).
    """

    banks: tuple[int, ...] | None = None
    spread: float | None = None
    target: int | None = None
    subsystem: str | None = None
    at_bearing: float | None = None
    max_banks: int | None = None
    defensive: bool = False
    name: ClassVar[str] = "fire phasers"

    def channels(self) -> tuple[str, ...]:
        # point defense never takes (or is blocked by) the offensive fire channel
        return () if self.defensive else ("phasers",)

    def _plan(self, world: World, ship: Ship) -> list[tuple[int, float, int | None]]:
        """(bank index, world bearing, target id) for every bank that will fire.

        A bank fires at the command's target, else at the ship it is locked
        on, else along its current mark.
        """
        from .systems.phasers import bank_bears, bank_bears_point, bank_origin, bank_ready

        if not ship.banks:
            raise Rejected(f"The {ship.cls.name} has no phaser banks.")
        idx = _indices(ship.banks, self.banks)
        candidates = [i for i in idx if bank_ready(ship, ship.banks[i])]
        if self.banks is None and not self.defensive:
            candidates = [i for i in candidates if ship.banks[i].role != BankRole.DEFENSE or self.issuer >= Authority.AI_CAPTAIN]
        if not candidates:
            damaged = [i for i in idx if not ship.banks[i].intact]
            if damaged and len(damaged) == len(idx):
                raise Rejected("All selected phaser banks are damaged.")
            raise Rejected("No phaser banks are charged.")
        plan: list[tuple[int, float, int | None]] = []
        out_of_arc = 0
        out_of_range: int | None = None
        for i in candidates:
            b = ship.banks[i]
            target: int | None = None
            if self.at_bearing is not None:
                aim = self.at_bearing
            else:
                target = self.target if self.target is not None else b.lock
                pos = world.apparent_position(ship.side, target) if target is not None else None
                if target is not None and pos is None:
                    if self.target is not None:
                        raise Rejected("No sensor contact with the target.")
                    target = None
                if pos is not None:
                    ox, oy = bank_origin(ship, b)
                    if math.hypot(pos[0] - ox, pos[1] - oy) > ship.cls.banks_range:
                        out_of_range = target
                        continue
                    aim = bearing(pos[0] - ox, pos[1] - oy)
                    if bank_bears_point(ship, b, pos[0], pos[1]):
                        plan.append((i, aim, target))
                        continue
                    out_of_arc += 1
                    continue
                else:
                    aim = norm360(ship.course + b.mark)
            if not bank_bears(ship, b, aim):
                out_of_arc += 1
                continue
            plan.append((i, aim, target))
        if not plan:
            if out_of_range is not None:
                t = world.ships[out_of_range]
                d = math.hypot(t.x - ship.x, t.y - ship.y)
                raise Rejected(f"Target out of phaser range ({d:,.0f} > {ship.cls.banks_range:,.0f}).")
            if out_of_arc:
                raise Rejected("Target is outside the firing arcs of the charged banks.")
            raise Rejected("No phaser bank can fire.")
        if self.max_banks is not None:
            plan = plan[: max(0, self.max_banks)]
        return plan

    def validate(self, world: World, ship: Ship) -> None:
        if self.target is not None:
            _require_target(world, ship, self.target)
        self._plan(world, ship)

    def apply(self, world: World, ship: Ship) -> None:
        from .systems.phasers import fire_bank

        for i, aim, target in self._plan(world, ship):
            b = ship.banks[i]
            sub = self.subsystem
            if sub is None and target is not None and target == ship.target:
                sub = ship.target_subsystem
            fire_bank(world, ship, b, aim, self.spread if self.spread is not None else b.spread,
                      target, sub, self.defensive)


@dataclass(kw_only=True)
class SetPhaserSpread(Command):
    spread: float
    banks: tuple[int, ...] | None = None
    name: ClassVar[str] = "spread"
    needs_crew: ClassVar[bool] = False

    def validate(self, world: World, ship: Ship) -> None:
        r = world.rules
        if not (r.spread_min <= self.spread <= r.spread_max):
            raise Rejected(f"Spread must be between {r.spread_min:.0f}° and {r.spread_max:.0f}°.")

    def apply(self, world: World, ship: Ship) -> None:
        for i in _indices(ship.banks, self.banks):
            ship.banks[i].spread = self.spread


@dataclass(kw_only=True)
class SetBanks(Command):
    """Enable/disable recharging or set the role of phaser banks."""

    banks: tuple[int, ...] | None = None
    enabled: bool | None = None
    role: BankRole | None = None
    name: ClassVar[str] = "banks"
    needs_crew: ClassVar[bool] = False

    def apply(self, world: World, ship: Ship) -> None:
        for i in _indices(ship.banks, self.banks):
            b = ship.banks[i]
            if self.enabled is not None:
                b.enabled = self.enabled
            if self.role is not None:
                b.role = self.role
                if self.role == BankRole.DEFENSE:
                    b.lock = None
                elif ship.target is not None and b.lock is None:
                    b.lock = ship.target


# ------------------------------------------------------------------ torpedoes

@dataclass(kw_only=True)
class FireTorpedoes(Command):
    tubes: tuple[int, ...] | None = None
    target: int | None = None
    subsystem: str | None = None
    count: int | None = None
    fan: float = 0.0
    name: ClassVar[str] = "fire torpedoes"

    def channels(self) -> tuple[str, ...]:
        return ("torpedoes",)

    def _plan(self, world: World, ship: Ship) -> list[tuple[int, int | None]]:
        """(tube index, target id) for each tube that will fire (command target, else the tube's lock)."""
        return self._survey(world, ship)[0]

    def _survey(self, world: World, ship: Ship) -> tuple[list[tuple[int, int | None]], list[int], list[int]]:
        """The tubes that will fire, the loaded tubes that can't bear, and the selected tubes not loaded."""
        from .systems.ordnance import tube_solution

        if not ship.tubes:
            raise Rejected(f"The {ship.cls.name} has no torpedo tubes.")
        idx = _indices(ship.tubes, self.tubes)
        loaded = [i for i in idx if ship.tubes[i].loaded is not None and ship.tubes[i].intact]
        unloaded = [i for i in idx if i not in loaded]
        if not loaded:
            if any(not ship.tubes[i].intact for i in idx) and all(not ship.tubes[i].intact for i in idx):
                raise Rejected("All selected tubes are damaged.")
            if ship.torps_remaining <= 0 and not any(ship.tubes[i].loaded for i in idx):
                raise Rejected("Torpedo magazine is empty.")
            raise Rejected(f"{_tube_list(idx).capitalize()} {'is' if len(idx) == 1 else 'are'} not loaded."
                           if self.tubes is not None else "No torpedoes are loaded.")
        ok: list[tuple[int, int | None]] = []
        blind: list[int] = []
        aim_at: int | None = None
        for i in loaded:
            tgt = self.target if self.target is not None else ship.tubes[i].lock
            if tgt is not None and world.apparent_position(ship.side, tgt) is None:
                tgt = None
            if tube_solution(world, ship, ship.tubes[i], tgt) is not None:
                ok.append((i, tgt))
            else:
                blind.append(i)
                aim_at = tgt if aim_at is None else aim_at
        if not ok:
            raise Rejected(f"{_tube_list(blind).capitalize()} can't bear: {_arc_advice(world, ship, blind, aim_at)}")
        if self.count is not None:
            ok = ok[: max(0, self.count)]
        return ok, blind, unloaded

    def validate(self, world: World, ship: Ship) -> None:
        if self.target is not None:
            _require_target(world, ship, self.target)
        self._plan(world, ship)

    def apply(self, world: World, ship: Ship) -> None:
        from .systems.ordnance import launch_torpedoes

        plan, blind, unloaded = self._survey(world, ship)
        if self.issuer >= Authority.CAPTAIN and (blind or (unloaded and self.tubes is not None)):
            from .events import Message, Tone

            bits = [f"Firing {_tube_list([i for i, _ in plan])}."]
            if blind:
                aim_at = next((t for t in (self.target, *(ship.tubes[i].lock for i in blind)) if t is not None), None)
                bits.append(f"{_tube_list(blind).capitalize()} can't bear: {_arc_advice(world, ship, blind, aim_at)}")
            if unloaded and self.tubes is not None:
                bits.append(f"{_tube_list(unloaded).capitalize()} {'is' if len(unloaded) == 1 else 'are'} not loaded.")
            world.emit(Message(world.tick, " ".join(bits), Tone.CAUTION, speaker=self.source, ship_id=ship.id,
                               visible_to=frozenset({ship.side})))
        groups: dict[int | None, list[int]] = {}
        for i, tgt in plan:
            groups.setdefault(tgt, []).append(i)
        for tgt, idx in groups.items():
            sub = self.subsystem
            if sub is None and tgt is not None and tgt == ship.target:
                sub = ship.target_subsystem
            launch_torpedoes(world, ship, [ship.tubes[i] for i in idx], tgt, sub, self.fan)


@dataclass(kw_only=True)
class StartProject(Command):
    """Set the officers to design something over a few cycles (sim/projects.py) [E]."""

    project: str
    name: ClassVar[str] = "design"

    def channels(self) -> tuple[str, ...]:
        return ("project",)

    def validate(self, world: World, ship: Ship) -> None:
        from .projects import PROJECTS, project_loaded

        proj = PROJECTS.get(self.project)
        if proj is None:
            raise Rejected(f"Nothing called '{self.project}' to design. Known: {', '.join(PROJECTS)}.")
        if self.project in ship.projects:
            raise Rejected(f"The {proj.title} is already being designed ({ship.projects[self.project]:.0f} cycles left).")
        if proj.needs_tubes and not any(t.intact for t in ship.tubes):
            raise Rejected(f"The {proj.title} needs a working torpedo tube.")
        if proj.is_ready is not None and proj.is_ready(ship):
            raise Rejected(f"The {proj.title} is already set up. {proj.hint}".strip())
        loaded_in = project_loaded(ship, proj) if proj.ordnance else None
        if loaded_in is not None:
            raise Rejected(f"A {proj.title} is already loaded in tube {loaded_in + 1}.")

    def apply(self, world: World, ship: Ship) -> None:
        from .projects import PROJECTS

        ship.projects[self.project] = PROJECTS[self.project].cycles

    def describe(self) -> str:
        return f"design {self.project}"


@dataclass(kw_only=True)
class FireSpecialRound(Command):
    """Fire a designed round (e.g. the tachyon detector) at a point, fused to burst there [E]."""

    ordnance: str
    x: float
    y: float
    name: ClassVar[str] = "fire special round"

    def channels(self) -> tuple[str, ...]:
        return ("torpedoes",)

    def _tube(self, ship: Ship) -> Tube:
        tube = next((t for t in ship.tubes if t.loaded is not None and t.loaded.ordnance == self.ordnance), None)
        if tube is None:
            raise Rejected(f"No {self.ordnance} round is loaded. Ask Spock and Seven to design one ('design {self.ordnance}').")
        return tube

    def validate(self, world: World, ship: Ship) -> None:
        self._tube(ship)
        spec = world.content.torpedoes[self.ordnance]
        reach = spec.velocity * world.rules.units_per_warp * (spec.arm_time + spec.max_time_fuse)
        d = math.hypot(self.x - ship.x, self.y - ship.y)
        if d > reach:
            raise Rejected(f"That point is {d:,.0f} away; the round reaches {reach:,.0f}.")

    def apply(self, world: World, ship: Ship) -> None:
        from .systems.ordnance import launch_at_point

        launch_at_point(world, ship, self._tube(ship), self.x, self.y)

    def describe(self) -> str:
        return f"fire {self.ordnance} at ({self.x:,.0f}, {self.y:,.0f})"


@dataclass(kw_only=True)
class ConfigureAutoload(Command):
    """Set autoload behaviour for tubes or launchers.

    Changes affect subsequent loads; torpedoes already in tubes stay loaded
    unless `reload` is set.
    """

    weapon: str  # "tube" | "launcher"
    mounts: tuple[int, ...] | None = None
    enabled: bool | None = None
    ordnance: str | None = None
    prox: float | None = None
    time: float | None = None
    reload: bool = False
    name: ClassVar[str] = "autoload"
    needs_crew: ClassVar[bool] = False

    def validate(self, world: World, ship: Ship) -> None:
        if self.weapon == "tube":
            if not ship.tubes:
                raise Rejected(f"The {ship.cls.name} has no torpedo tubes.")
            allowed = world.content.compatible_torpedoes(ship.cls)
            spec = None
            if self.ordnance is not None:
                spec = next((t for t in allowed if t.id == self.ordnance), None)
                if spec is None:
                    names = ", ".join(t.id.upper() for t in allowed)
                    raise Rejected(f"Tubes cannot load {self.ordnance.upper()} (compatible: {names}).")
            spec = spec or world.content.torpedoes[ship.tubes[0].load_ordnance or ship.cls.torpedo]
            if self.prox is not None and not (world.rules.prox_floor <= self.prox <= spec.max_prox):
                raise Rejected(f"Proximity for {spec.id.upper()} must be {world.rules.prox_floor:.0f}–{spec.max_prox:.0f}.")
        elif self.weapon == "launcher":
            if not ship.launchers:
                raise Rejected(f"The {ship.cls.name} has no probe launchers.")
            allowed_p = world.content.compatible_probes(ship.cls)
            pspec = None
            if self.ordnance is not None:
                pspec = next((p for p in allowed_p if p.id == self.ordnance), None)
                if pspec is None:
                    names = ", ".join(p.id.upper() for p in allowed_p)
                    raise Rejected(f"Launchers cannot load {self.ordnance.upper()} (compatible: {names}).")
            pspec = pspec or world.content.probes[ship.launchers[0].load_ordnance or ship.cls.probe]
            if self.prox is not None and not (world.rules.probe_prox_floor <= self.prox <= pspec.max_prox):
                raise Rejected(f"Probe proximity must be {world.rules.probe_prox_floor:.0f}–{pspec.max_prox:.0f}.")
            if self.time is not None and not (world.rules.probe_time_floor <= self.time <= pspec.max_time_fuse):
                raise Rejected(f"Probe time fuse must be {world.rules.probe_time_floor:.0f}–{pspec.max_time_fuse:.0f}.")
        else:
            raise Rejected(f"Unknown weapon type '{self.weapon}'.")

    def apply(self, world: World, ship: Ship) -> None:
        if self.weapon == "tube":
            for i in _indices(ship.tubes, self.mounts):
                t = ship.tubes[i]
                if self.enabled is not None:
                    t.autoload = self.enabled
                if self.ordnance is not None:
                    t.load_ordnance = self.ordnance
                if self.prox is not None:
                    t.load_prox = self.prox
                if self.reload and t.loaded is not None:
                    ship.torps_remaining += 1
                    t.loaded = None
                    t.charge = 0.0
        else:
            for i in _indices(ship.launchers, self.mounts):
                lch = ship.launchers[i]
                if self.enabled is not None:
                    lch.autoload = self.enabled
                if self.ordnance is not None:
                    lch.load_ordnance = self.ordnance
                if self.prox is not None:
                    lch.load_prox = self.prox
                if self.time is not None:
                    lch.load_time = self.time
                if self.reload and lch.loaded is not None:
                    ship.probes_remaining += 1
                    lch.loaded = None
                    lch.prep = 0.0

    def describe(self) -> str:
        bits = [f"autoload {self.weapon}s"]
        if self.ordnance:
            bits.append(self.ordnance.upper())
        if self.prox is not None:
            bits.append(f"prox {self.prox:.0f}")
        if self.time is not None:
            bits.append(f"time {self.time:.0f}")
        if self.enabled is not None:
            bits.append("on" if self.enabled else "off")
        return " ".join(bits)


@dataclass(kw_only=True)
class LoadTubes(Command):
    """Manually start loading (used when autoload is off) or unload tubes; `weapon="launcher"` for probe launchers."""

    tubes: tuple[int, ...] | None = None
    unload: bool = False
    weapon: str = "tube"
    name: ClassVar[str] = "load tubes"

    def apply(self, world: World, ship: Ship) -> None:
        if self.weapon == "launcher":
            for i in _indices(ship.launchers, self.tubes):
                lch = ship.launchers[i]
                if self.unload:
                    if lch.loaded is not None:
                        ship.probes_remaining += 1
                    lch.loaded = None
                    lch.prep = 0.0
                    lch.autoload = False  # launchers stay empty until loaded again (manual p. 18)
                    lch.manual_load_pending = False
                else:
                    lch.autoload = True
                    lch.manual_load_pending = True
            return
        for i in _indices(ship.tubes, self.tubes):
            t = ship.tubes[i]
            if self.unload:
                if t.loaded is not None:
                    ship.torps_remaining += 1
                t.loaded = None
                t.charge = 0.0
                t.manual_load_pending = False
            else:
                t.manual_load_pending = True

    def describe(self) -> str:
        what = "launchers" if self.weapon == "launcher" else "tubes"
        return f"{'unload' if self.unload else 'load'} {what}"


@dataclass(kw_only=True)
class SetTubes(Command):
    """Enable or disable torpedo tube charging (manual p. 16)."""

    tubes: tuple[int, ...] | None = None
    enabled: bool = True
    name: ClassVar[str] = "tubes"
    needs_crew: ClassVar[bool] = False

    def validate(self, world: World, ship: Ship) -> None:
        if not ship.tubes:
            raise Rejected(f"The {ship.cls.name} has no torpedo tubes.")

    def apply(self, world: World, ship: Ship) -> None:
        for i in _indices(ship.tubes, self.tubes):
            ship.tubes[i].enabled = self.enabled

    def describe(self) -> str:
        return f"{'enable' if self.enabled else 'disable'} tubes"


# ------------------------------------------------------------------ probes

@dataclass(kw_only=True)
class LaunchProbe(Command):
    launchers: tuple[int, ...] | None = None
    target: int | None = None
    course: float | None = None
    count: int = 1
    name: ClassVar[str] = "launch probe"

    def validate(self, world: World, ship: Ship) -> None:
        if not ship.launchers:
            raise Rejected(f"The {ship.cls.name} has no probe launchers.")
        if self.target is not None:
            _require_target(world, ship, self.target)
        idx = _indices(ship.launchers, self.launchers)
        if not any(ship.launchers[i].loaded is not None for i in idx):
            raise Rejected("No probe is loaded." if ship.probes_remaining > 0 else "Probe magazine is empty.")

    def apply(self, world: World, ship: Ship) -> None:
        from .systems.ordnance import launch_probe

        n = 0
        for i in _indices(ship.launchers, self.launchers):
            lch = ship.launchers[i]
            if lch.loaded is None:
                continue
            p = launch_probe(world, ship, lch, self.target, self.course)
            if p is not None:
                n += 1
                world.say(ship, f"Probe {p.code} away.", "info")
            if self.launchers is None and n >= self.count:
                break


@dataclass(kw_only=True)
class ControlProbe(Command):
    """Detonate, re-lock or turn a probe by its control code (or all of ours)."""

    code: str | None = None  # None = all probes owned by this ship
    detonate: bool = False
    target: int | None = None
    course: float | None = None
    name: ClassVar[str] = "probe control"

    def _probes(self, world: World, ship: Ship) -> list:  # type: ignore[type-arg]
        if self.code is None:
            return [p for p in world.probes if p.owner == ship.id and not p.detonate]
        code = self.code.lower()
        return [p for p in world.probes if p.code.lower() == code and not p.detonate]

    def validate(self, world: World, ship: Ship) -> None:
        if not self._probes(world, ship):
            raise Rejected("No active probe with that code." if self.code else "No active probes.")
        if self.target is not None:
            _require_target(world, ship, self.target)

    def apply(self, world: World, ship: Ship) -> None:
        for p in self._probes(world, ship):
            if self.detonate:
                p.detonate = True
                p.remote = True
            elif self.target is not None:
                p.target = self.target
                p.deliberate_target = world.ships[self.target].side == p.side
            elif self.course is not None:
                p.target = None
                p.course = norm360(self.course)


@dataclass(kw_only=True)
class SetFireMode(Command):
    """Manual / assisted / automatic fire control per weapon group or mount [E]."""

    weapon: str  # "phaser" | "tube"
    mode: FireMode
    mounts: tuple[int, ...] | None = None
    name: ClassVar[str] = "fire mode"
    needs_crew: ClassVar[bool] = False

    def validate(self, world: World, ship: Ship) -> None:
        items = ship.banks if self.weapon == "phaser" else ship.tubes if self.weapon == "tube" else None
        if items is None:
            raise Rejected(f"Unknown weapon type '{self.weapon}'.")
        if not items:
            raise Rejected(f"The {ship.cls.name} has no {'phaser banks' if self.weapon == 'phaser' else 'torpedo tubes'}.")

    def apply(self, world: World, ship: Ship) -> None:
        items = ship.banks if self.weapon == "phaser" else ship.tubes
        for i in _indices(items, self.mounts):  # type: ignore[arg-type]
            items[i].fire_mode = self.mode


@dataclass(kw_only=True)
class SetPointDefense(Command):
    doctrine: PDDoctrine
    reserve: tuple[int, ...] | None = None  # banks to reserve for defense (replaces the current set)
    name: ClassVar[str] = "point defense"
    needs_crew: ClassVar[bool] = False

    def validate(self, world: World, ship: Ship) -> None:
        if not ship.banks:
            raise Rejected(f"The {ship.cls.name} has no phaser banks for point defense.")
        if self.reserve is not None and any(not 0 <= i < len(ship.banks) for i in self.reserve):
            raise Rejected("No such phaser bank.")

    def apply(self, world: World, ship: Ship) -> None:
        ship.pd_doctrine = self.doctrine
        if self.reserve is not None:
            for i, b in enumerate(ship.banks):
                if i in self.reserve:
                    b.role = BankRole.DEFENSE
                    b.lock = None
                elif b.role == BankRole.DEFENSE:
                    b.role = BankRole.FLEX


# ------------------------------------------------------------------ shields

@dataclass(kw_only=True)
class SetShields(Command):
    sectors: tuple[int, ...] | None = None
    up: bool = True
    name: ClassVar[str] = "shields"
    needs_crew: ClassVar[bool] = False

    def channels(self) -> tuple[str, ...]:
        idx = range(6) if self.sectors is None else self.sectors
        return tuple(f"shields.{i}" for i in idx)

    def validate(self, world: World, ship: Ship) -> None:
        if not ship.shields:
            raise Rejected(f"The {ship.cls.name} has no shields.")

    def apply(self, world: World, ship: Ship) -> None:
        for i in _indices(ship.shields, self.sectors):
            sh = ship.shields[i]
            sh.up = self.up
            if not self.up:
                sh.reinforced = False


@dataclass(kw_only=True)
class ReinforceShield(Command):
    """Reinforce one shield (quadruple upkeep, halved strength loss) or clear with sector None."""

    sector: int | None
    name: ClassVar[str] = "reinforce"

    def channels(self) -> tuple[str, ...]:
        return ("shields.reinforce",)

    def validate(self, world: World, ship: Ship) -> None:
        if not ship.shields:
            raise Rejected(f"The {ship.cls.name} has no shields.")
        if self.sector is not None:
            if not 0 <= self.sector < len(ship.shields):
                raise Rejected("No such shield.")
            sh = ship.shields[self.sector]
            if sh.destroyed:
                raise Rejected(f"Shield {self.sector + 1} generator is destroyed.")

    def apply(self, world: World, ship: Ship) -> None:
        for sh in ship.shields:
            sh.reinforced = False
        if self.sector is not None:
            sh = ship.shields[self.sector]
            sh.reinforced = True
            sh.up = True


# ------------------------------------------------------------------ engineering

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
        from .systems.morale import adjust

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

    def apply(self, world: World, ship: Ship) -> None:
        if self.on:
            ship.delegated.add(self.station)
            for prefix in STATION_CHANNELS[self.station]:
                world.release_holds(ship.id, prefix)
        else:
            ship.delegated.discard(self.station)
            if not ship.delegated:
                ship.conn, ship.conn_saved = "", set()   # every station taken back: the captain has the bridge again


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
        from .objectives import DISABLE_GROUPS, GOALS

        if self.goal not in GOALS:
            raise Rejected(f"Unknown objective '{self.goal}'.")
        if self.goal == "disable" and self.group not in DISABLE_GROUPS:
            raise Rejected(f"Can't disable '{self.group}'. Choose from: {', '.join(DISABLE_GROUPS)}.")
        if not self.targets:
            raise Rejected(f"{self.goal.capitalize()} which ships?")
        for t in self.targets:
            s = world.ships.get(t)
            if s is None or not s.exists or s.side == ship.side:
                raise Rejected(f"#{t} isn't an enemy ship in this battle.")

    def apply(self, world: World, ship: Ship) -> None:
        from .objectives import Objective

        # a new order about the same systems replaces the old one
        ship.objectives = [o for o in ship.objectives if not (o.goal == self.goal and o.group == self.group)]
        ship.objectives.append(Objective(self.goal, self.group, tuple(self.targets), self.officer, world.tick))

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
        from .events import ObjectiveEnded

        ship.hold_fire = True
        ship.pending_volley = None
        ending, ship.objectives = ship.objectives, []
        for o in ending:
            world.emit(ObjectiveEnded(world.tick, ship.id, o.officer, o.goal, o.group, o.targets, "cancelled",
                                      "cease fire"))


@dataclass(kw_only=True)
class OpenFire(Command):
    """`open fire` / `weapons free` [E]: lift a cease fire."""

    name: ClassVar[str] = "open fire"
    needs_crew: ClassVar[bool] = False

    def apply(self, world: World, ship: Ship) -> None:
        ship.hold_fire = False


def offensive_fire(cmd: Command) -> bool:
    """A command that fires on someone: what a cease fire stops (point defense isn't)."""
    if isinstance(cmd, FirePhasers):
        return not cmd.defensive
    return isinstance(cmd, (FireTorpedoes, FireSpecialRound, FireAtPoint, LaunchProbe))


@dataclass(kw_only=True)
class EndObjective(Command):
    """Finish, give up or cancel objectives: one group, or all of them when `group` is empty [E]."""

    group: str = ""
    outcome: str = "cancelled"   # "done" | "impossible" | "cancelled"
    reason: str = ""
    name: ClassVar[str] = "end objective"
    needs_crew: ClassVar[bool] = False

    def channels(self) -> tuple[str, ...]:
        return ("objective",)

    def validate(self, world: World, ship: Ship) -> None:
        if not ship.objectives:
            raise Rejected("No objectives to end.")

    def apply(self, world: World, ship: Ship) -> None:
        from .events import ObjectiveEnded

        ending = [o for o in ship.objectives if not self.group or o.group == self.group]
        ship.objectives = [o for o in ship.objectives if o not in ending]
        for o in ending:
            world.emit(ObjectiveEnded(world.tick, ship.id, o.officer, o.goal, o.group, o.targets, self.outcome,
                                      self.reason))

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
        from .systems.ordnance import launch_at_point

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
        from ..core.angles import ang_dist, bearing
        from .events import DeflectorPulsed, Message, Tone

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

    def describe(self) -> str:
        return f"conn {self.officer or 'captain'}"


@dataclass(kw_only=True)
class Scan(Command):
    target: int
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
        world.begin_scan(ship, self.target)


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
        from .systems.disposition import HAIL_GAP_CYCLES, INTENTS

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
        from .systems.disposition import answer

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
        from .systems.damage import relative_bearing_from

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


# ------------------------------------------------------------------ ally orders

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
        from .allies import ORDER_WORDS, SHIP_ORDERS

        a = world.ships.get(self.ally)
        if a is None or not a.alive:
            raise Rejected("That ally is not available.")
        if a.side != ship.side:
            raise Rejected(f"{a.name} is not under your command.")
        if a.id == ship.id:
            raise Rejected("Give your own ship orders directly.")
        o = self.order
        if o not in ORDER_WORDS:
            raise Rejected(f"Unknown order '{o}'.")
        need = SHIP_ORDERS.get(o, "none")
        if need != "none" and self.target is None:
            raise Rejected(f"'{o}' needs a ship.")
        if self.target is not None:
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
        if o == "phaser" and not any(b.intact for b in a.banks):
            raise Rejected(f"{a.name}: we have no working phasers.")
        if o == "torpedo" and not any(t.intact for t in a.tubes):
            raise Rejected(f"{a.name}: we have no working torpedo tubes.")
        if o == "probe" and not any(lch.intact for lch in a.launchers):
            raise Rejected(f"{a.name}: we have no working probe launchers.")
        if o in ("course",) and self.value is None:
            raise Rejected("Hold which course?")
        if o == "join" and (self.value is None or self.value < 1):
            raise Rejected("Join which group (1 or more)?")
        if o in ("recover", "eject") and a.cls.mass_capacity <= 0:
            raise Rejected(f"{a.name} has no docking bays.")
        if o == "dock" and self.target is not None and world.ships[self.target].cls.mass_capacity <= 0:
            raise Rejected(f"{world.ships[self.target].name} has no docking bays.")
        if o == "eject" and self.target is not None and world.ships[self.target].docked_to != a.id:
            raise Rejected(f"{world.ships[self.target].name} is not docked with {a.name}.")
        if o in ("tow", "tractor") and (a.tractor is None or not a.tractor.intact):
            raise Rejected(f"{a.name}: our tractor beam is not working.")
        if o == "tow" and self.destination is None:
            raise Rejected("Tow it where? 'tell <ally> tow <ship> <destination ship>'.")
        if o == "board" and not any(not x.destroyed for x in a.transporters):
            raise Rejected(f"{a.name}: our transporters are down.")
        if o == "undock" and a.docked_to is None:
            raise Rejected(f"{a.name} is not docked.")

    def apply(self, world: World, ship: Ship) -> None:
        world.deliver_order(ship, self)

    def describe(self) -> str:
        return f"tell {self.order}"


def in_mount_arc(ship: Ship, mount_center: float, mount_width: float, world_bearing: float) -> bool:
    return in_arc(norm360(world_bearing - ship.course), mount_center, mount_width)
