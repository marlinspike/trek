"""Shields: raising, lowering and reinforcing."""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ..ship import Ship
from .base import Command, Rejected, _indices

if TYPE_CHECKING:
    from ..world import World


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
