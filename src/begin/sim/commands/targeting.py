"""Targeting: choosing, locking and scanning a target."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ...core.angles import norm360
from ..ship import TARGETABLE_GROUPS, BankRole, Ship
from .base import Command, Rejected, _indices, _require_target

if TYPE_CHECKING:
    from ..world import World


@dataclass(kw_only=True)
class SelectTarget(Command):
    """Designate the fire-control target (and optionally a subsystem group) and lock weapons."""

    target: int | None
    subsystem: str | None = None
    lock_weapons: bool = True
    hull: bool = False      # the captain named the hull: they mean to destroy her, even one they had disabled [E]
    name: ClassVar[str] = "target"

    def channels(self) -> tuple[str, ...]:
        return ("tactical.target",)

    def validate(self, world: World, ship: Ship) -> None:
        if self.target is not None:
            _require_target(world, ship, self.target)
        if self.subsystem is not None and self.subsystem not in TARGETABLE_GROUPS:
            raise Rejected(f"Unknown subsystem group '{self.subsystem}'.")
        if self.subsystem == "relay" and self.target is not None:
            ins = world.insight.get(ship.side)
            if ins is None or not ins.knows_weak(self.target):
                raise Rejected("We haven't found her relay yet: keep scanning her.")

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
