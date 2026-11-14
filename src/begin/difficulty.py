"""How hard the enemy fights: Ensign, Captain or Admiral [E].

Difficulty changes the other side only. It scales how many ships the enemy brings and how well their captains and
crews fight (`competence`: reading the situation, timing, aim and dodging; `crew_competence`: how fast orders are
carried out). It never touches the player's own squadron: the Enterprise is a Dreadnought at every level.

* Ensign: about a third fewer enemy ships (never fewer than one a side), and slower, less able captains.
* Captain: the game as designed. Nothing changes.
* Admiral: about a third more enemy ships (more of the escorts, never a second flagship), and sharper, quicker
  captains.

Fleet sizes change in quick battles, presets and tours. A custom battle is fought with exactly the fleets the captain
chose (`BattleSetup.fixed_fleets`); only its captains' skill follows the difficulty. Starbases are never added or
taken away, and an intercept mission's runner is always kept.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass

from .ai.personality import Personality

LEVELS = ("ensign", "captain", "admiral")
DEFAULT = "captain"
MAX_SHIPS = 60          # Begin's ship limit (battle.MAX_OBJECTS)


@dataclass(frozen=True, slots=True)
class Difficulty:
    key: str
    title: str
    blurb: str
    fleet: float          # enemy ships added (+) or taken away (-), as a share of each enemy fleet
    skill: float          # added to every enemy captain's competence and crew competence (clamped to 0..1)


DIFFICULTIES: dict[str, Difficulty] = {
    "ensign": Difficulty("ensign", "Ensign", "Fewer enemy ships, and their captains are slower and less sure.",
                         -1 / 3, -0.25),
    "captain": Difficulty("captain", "Captain", "The game as designed.", 0.0, 0.0),
    "admiral": Difficulty("admiral", "Admiral", "More enemy ships, and sharper, quicker captains.", 1 / 3, 0.15),
}


def level(key: str | None) -> Difficulty:
    """The difficulty named, or Captain for anything unknown."""
    return DIFFICULTIES.get((key or "").strip().lower(), DIFFICULTIES[DEFAULT])


def change(n: int, share: float) -> int:
    """How many ships a fleet of `n` gains (+) or loses (-): a third of three is one, a third of one is none."""
    return int(math.copysign(math.floor(abs(n * share) + 0.5), share)) if share else 0


def skilled(p: Personality, d: Difficulty) -> Personality:
    """An enemy captain as the difficulty has them."""
    if not d.skill:
        return p
    return dataclasses.replace(p, competence=_clamp01(p.competence + d.skill),
                               crew_competence=_clamp01(p.crew_competence + d.skill))


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


def scaled(n: int, bases: set[int], d: Difficulty, keep: int = 1, named: set[int] | None = None) -> list[int]:
    """Which of a fleet's `n` ships come at this difficulty, as indices into it (an index twice is a second ship of
    that kind). Starbases (`bases`) stay as they are; ships come off the end, keeping at least the first `keep` that
    can move and never one under a `named` captain (a tour's commander or rival), or are added by repeating the
    fleet's escorts from the end of its list (its first ship, the flagship, only when it has nothing else)."""
    mobile = [i for i in range(n) if i not in bases]
    delta = change(len(mobile), d.fleet)
    out = list(range(n))
    if delta < 0:
        for i in sorted((i for i in mobile[max(1, keep):] if i not in (named or set())), reverse=True)[:-delta]:
            out.remove(i)
    elif delta > 0:
        # the extra ships are more of the escorts, the last-listed first: the same ships Ensign takes away, so the
        # two levels move the threat by about the same amount, and a flagship is never doubled
        free = [i for i in reversed(mobile) if i not in (named or set())]
        spare = [i for i in free if i != mobile[0]] or free
        out += [spare[i % len(spare)] for i in range(delta)] if spare else []
    return out


__all__ = ["DEFAULT", "DIFFICULTIES", "LEVELS", "Difficulty", "change", "level", "scaled", "skilled"]
