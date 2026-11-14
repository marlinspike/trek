"""Probes and their kin: launches at a ship or a point."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ...core.angles import norm360
from ..ship import BankRole, FireMode, PDDoctrine, Ship
from .base import Command, Rejected, _indices, _require_target

if TYPE_CHECKING:
    from ..world import World


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
        from ..systems.ordnance import launch_probe

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
