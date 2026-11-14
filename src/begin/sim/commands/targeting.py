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
class SplitFire(Command):
    """Divide the weapons between ships [E]: each bank and tube is locked on the ship it was given, in one order.

    It rests on Begin's own per-mount locks (`lock tubes 1 2 on <ship>`), so F, T and the console's `fire` with no
    ship named send every bank and tube at its own target, and assisted fire does the same. `primary` becomes the
    fire-control target (the Target panel's ship) without re-locking anything; None keeps the current one.
    """

    banks: tuple[tuple[int, tuple[int, ...]], ...] = ()    # (target id, bank indices), zero-based
    tubes: tuple[tuple[int, tuple[int, ...]], ...] = ()    # (target id, tube indices)
    primary: int | None = None
    name: ClassVar[str] = "split"

    def channels(self) -> tuple[str, ...]:
        return ("tactical.target",)

    def targets(self) -> list[int]:
        return list(dict.fromkeys([t for t, _ in self.banks] + [t for t, _ in self.tubes]))

    def validate(self, world: World, ship: Ship) -> None:
        if not any(idx for _, idx in self.banks) and not any(idx for _, idx in self.tubes):
            raise Rejected("Split which weapons? e.g. 'split tubes 1-4 on the Talon, the rest on the Wraith'.")
        for t in self.targets():
            target = _require_target(world, ship, t)
            if target.side == ship.side:
                raise Rejected(f"The {target.name} is one of ours.")
        for _, idx in self.banks:
            bad = [i + 1 for i in idx if not 0 <= i < len(ship.banks)]
            if bad:
                raise Rejected(f"Phaser bank {bad[0]} does not exist: the {ship.cls.name} has {len(ship.banks)}.")
        for _, idx in self.tubes:
            bad = [i + 1 for i in idx if not 0 <= i < len(ship.tubes)]
            if bad:
                raise Rejected(f"Torpedo tube {bad[0]} does not exist: the {ship.cls.name} has {len(ship.tubes)}.")

    def apply(self, world: World, ship: Ship) -> None:
        for t, idx in self.banks:
            for i in idx:
                ship.banks[i].lock = t
        for t, idx in self.tubes:
            for i in idx:
                ship.tubes[i].lock = t
                ship.tubes[i].dispersion = 0.0
        if self.primary is not None and self.primary != ship.target:
            ship.target = self.primary
            ship.target_subsystem = None

    def describe(self) -> str:
        return f"split fire between {len(self.targets())} ships"


def split_locks(ship: Ship) -> dict[int, tuple[list[int], list[int]]]:
    """Where each weapon is locked, when they are divided between ships: {target: (banks, tubes)}; empty when
    every bank and tube is on one ship (or none). Point-defense banks don't count: they guard us, not a target."""
    out: dict[int, tuple[list[int], list[int]]] = {}
    for i, b in enumerate(ship.banks):
        if b.lock is not None and b.role != BankRole.DEFENSE:
            out.setdefault(b.lock, ([], []))[0].append(i)
    for i, t in enumerate(ship.tubes):
        if t.lock is not None:
            out.setdefault(t.lock, ([], []))[1].append(i)
    return out if len(out) > 1 else {}


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
