"""The command base: authority, rejection, the `Command` type and the helpers the sections share."""

from __future__ import annotations

from dataclasses import dataclass
from enum import IntEnum
from typing import TYPE_CHECKING, ClassVar

from ...core.angles import bearing, norm360
from ..ship import Ship

if TYPE_CHECKING:
    from ..world import World


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
