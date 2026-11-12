"""The end of a battle, as the captain is told it: the verdict, the score, the ship's record, the officer who
stood out, the honours earned, and every side's and ship's tally [E]. Built by `BattleSession.debrief()`."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..sim.scoring import SideResult
from ..sim.ship import Ship


@dataclass(frozen=True)
class SideTally:
    side: int
    name: str
    ours: bool
    result: SideResult


@dataclass(frozen=True)
class Debrief:
    reason: str                       # how it ended ("The enemy has been destroyed.")
    verdict: str                      # the assessment in words
    score: float
    cycles: float
    side: int                         # ours
    ship: Ship | None                 # the ship the captain ended in, with her record (`ship.stats`)
    standout: str | None              # the officer who did the most, in a sentence
    had_crew: bool                    # whether there were bridge officers at all
    honours: list[str] = field(default_factory=list)       # a ribbon won, officers' trust risen
    sides: list[SideTally] = field(default_factory=list)
    ships: list[Ship] = field(default_factory=list)        # the ships' tallies, the first few


__all__ = ["Debrief", "SideTally"]
