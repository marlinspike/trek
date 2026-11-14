"""Phasers: firing banks, their roles and fire modes."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ...core.angles import bearing, norm360
from ..ship import BankRole, Ship
from .base import Authority, Command, Rejected, _indices, _require_target

if TYPE_CHECKING:
    from ..world import World


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
        from ..ship import bank_bears, bank_ready
        from ..systems.phasers import bank_bears_point, bank_origin

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
        from ..systems.phasers import fire_bank

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
