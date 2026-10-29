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
from .ship import BankRole, FireMode, HelmMode, Kind, PDDoctrine, Ship, ShipStatus, TARGETABLE_GROUPS

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
        from .systems.phasers import bank_bears, bank_origin, bank_ready

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
        from .systems.ordnance import tube_solution

        if not ship.tubes:
            raise Rejected(f"The {ship.cls.name} has no torpedo tubes.")
        idx = _indices(ship.tubes, self.tubes)
        loaded = [i for i in idx if ship.tubes[i].loaded is not None and ship.tubes[i].intact]
        if not loaded:
            if any(not ship.tubes[i].intact for i in idx) and all(not ship.tubes[i].intact for i in idx):
                raise Rejected("All selected tubes are damaged.")
            if ship.torps_remaining <= 0 and not any(ship.tubes[i].loaded for i in idx):
                raise Rejected("Torpedo magazine is empty.")
            raise Rejected("No torpedoes are loaded.")
        ok: list[tuple[int, int | None]] = []
        for i in loaded:
            tgt = self.target if self.target is not None else ship.tubes[i].lock
            if tgt is not None and world.apparent_position(ship.side, tgt) is None:
                tgt = None
            if tube_solution(world, ship, ship.tubes[i], tgt) is not None:
                ok.append((i, tgt))
        if not ok:
            raise Rejected("No loaded tube has a firing solution inside its arc.")
        if self.count is not None:
            ok = ok[: max(0, self.count)]
        return ok

    def validate(self, world: World, ship: Ship) -> None:
        if self.target is not None:
            _require_target(world, ship, self.target)
        self._plan(world, ship)

    def apply(self, world: World, ship: Ship) -> None:
        from .systems.ordnance import launch_torpedoes

        groups: dict[int | None, list[int]] = {}
        for i, tgt in self._plan(world, ship):
            groups.setdefault(tgt, []).append(i)
        for tgt, idx in groups.items():
            sub = self.subsystem
            if sub is None and tgt is not None and tgt == ship.target:
                sub = ship.target_subsystem
            launch_torpedoes(world, ship, [ship.tubes[i] for i in idx], tgt, sub, self.fan)


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
    """Manually start loading (used when autoload is off) or unload."""

    tubes: tuple[int, ...] | None = None
    unload: bool = False
    name: ClassVar[str] = "load tubes"

    def apply(self, world: World, ship: Ship) -> None:
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
    kind: Kind | None
    name: ClassVar[str] = "repair"

    def channels(self) -> tuple[str, ...]:
        return ("engineering.priority",)

    def apply(self, world: World, ship: Ship) -> None:
        ship.repair_priority = self.kind


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

        sh = t.shield_for_bearing(relative_bearing_from(t, ship.x, ship.y))
        if sh is not None and sh.effective > 0:
            raise Rejected(f"{t.name}'s facing shield is up.")
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
    """Captain's order to an ally ship (Begin's `tell <ally> ...`)."""

    ally: int
    order: str
    target: int | None = None
    value: float | None = None
    args: dict[str, float] = field(default_factory=dict)
    name: ClassVar[str] = "tell"
    needs_crew: ClassVar[bool] = False

    def validate(self, world: World, ship: Ship) -> None:
        a = world.ships.get(self.ally)
        if a is None or not a.alive:
            raise Rejected("That ally is not available.")
        if a.side != ship.side:
            raise Rejected(f"{a.name} is not under your command.")
        if self.target is not None:
            _require_target(world, ship, self.target)

    def apply(self, world: World, ship: Ship) -> None:
        world.deliver_order(ship, self)


def in_mount_arc(ship: Ship, mount_center: float, mount_width: float, world_bearing: float) -> bool:
    return in_arc(norm360(world_bearing - ship.course), mount_center, mount_width)
