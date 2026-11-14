"""A stop that teaches: the officer walks the captain through one system, a step at a time [E].

The Shakedown Cruise (content/data/tours.toml) gives each stop a `lesson`: a few steps, each with what the officer
says, the keys or words that do it, what counts as done, and a word of praise. The battle runs as usual; the drill
watches what the captain does and moves on when a step is done. Nothing is forced: a captain who already knows the
step simply finds it ticked off.

Pure bookkeeping, like the rest of the tour: the session hands in `Facts` each cycle and says the lines it returns.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable

GAP = 3.0           # cycles between one step done and the next one given
NUDGE = 45.0        # cycles a step may wait before the officer reminds the captain, once


@dataclass(frozen=True, slots=True)
class Facts:
    """What the drill can see of the captain's ship and bridge this cycle."""
    cycle: float
    warp: float = 0.0
    warp_change: float = 0.0         # how far the captain has moved our ordered warp since the battle began
    turned: float = 0.0              # degrees our ordered course has moved since the battle began
    pursuing: bool = False           # the helm is following or keeping range on a ship
    targeted: bool = False           # a bank or tube is locked on a ship
    phaser_shots: int = 0
    phaser_hits: int = 0
    torpedoes: int = 0
    torpedo_hits: int = 0
    shields_up: int = 0
    shields: int = 6
    reinforced: bool = False
    boost: bool = False
    delegated: int = 0               # stations an officer runs
    counsel: bool = False            # the captain opened the counsel
    followed: bool = False           # ... and took a plan, or a step of one
    accepted: bool = False           # the captain said yes to an officer's proposal
    scanned: bool = False
    beaten: bool = False             # the enemy is beaten (or gone)


CHECKS: dict[str, Callable[[Facts], bool]] = {
    "warp": lambda f: f.warp_change >= 1.0,
    "turn": lambda f: f.turned >= 20.0 or f.pursuing,
    "target": lambda f: f.targeted,
    "phasers": lambda f: f.phaser_shots > 0,
    "phaser_hit": lambda f: f.phaser_hits > 0,
    "torpedo": lambda f: f.torpedoes > 0,
    "torpedo_hit": lambda f: f.torpedo_hits > 0,
    "shields_up": lambda f: f.shields_up >= f.shields > 0,
    "reinforce": lambda f: f.reinforced,
    "shields_trim": lambda f: 0 < f.shields_up < f.shields,
    "boost": lambda f: f.boost,
    "delegate": lambda f: f.delegated > 0,
    "counsel": lambda f: f.counsel,
    "follow": lambda f: f.followed,
    "proposal": lambda f: f.accepted,
    "scan": lambda f: f.scanned,
    "win": lambda f: f.beaten,
}


@dataclass(frozen=True, slots=True)
class Step:
    say: str                 # what the officer says when the step begins
    do: str                  # the keys or words that do it, for the lesson card
    done: str                # a key of CHECKS
    praise: str = ""         # what the officer says when it is done

    def __post_init__(self) -> None:
        if self.done not in CHECKS:
            raise ValueError(f"lesson step: unknown check {self.done!r} (one of {', '.join(CHECKS)})")

    @staticmethod
    def from_dict(d: dict[str, Any]) -> Step:
        return Step(str(d["say"]).strip(), str(d.get("do", "")).strip(), str(d["done"]), str(d.get("praise", "")).strip())


@dataclass(frozen=True, slots=True)
class LessonView:
    """The lesson card: which step, what to do, and what has been done."""
    title: str
    officer: str
    step: int                        # 0-based; == len(steps) when the lesson is learned
    steps: tuple[Step, ...]

    @property
    def learned(self) -> bool:
        return self.step >= len(self.steps)

    @property
    def current(self) -> Step | None:
        return None if self.learned else self.steps[self.step]


@dataclass
class Drill:
    title: str
    officer: str
    steps: tuple[Step, ...]
    step: int = 0
    given_at: float | None = None    # the cycle the current step was given (None: not yet)
    done_at: float = -1e9            # the cycle the last step was done
    nudged: bool = False
    log: list[str] = field(default_factory=list)

    def update(self, f: Facts) -> list[str]:
        """The officer's lines this cycle: the next step, praise for one done, or a reminder."""
        out: list[str] = []
        while self.step < len(self.steps):
            s = self.steps[self.step]
            if self.given_at is None:
                if f.cycle - self.done_at < GAP and not f.beaten:
                    break                          # a breath between steps, unless the fight is already won
                self.given_at, self.nudged = f.cycle, False
                if not CHECKS[s.done](f):          # a step already done needs no telling
                    out.append(s.say)
                    break
            if CHECKS[s.done](f):
                if s.praise:
                    out.append(s.praise)
                self.log.append(s.done)
                self.step += 1
                self.given_at, self.done_at = None, f.cycle
                continue
            if not self.nudged and f.cycle - self.given_at >= NUDGE and s.do:
                self.nudged = True
                out.append(f"When you are ready, Captain: {s.do}.")
            break
        return out

    def view(self) -> LessonView:
        return LessonView(self.title, self.officer, self.step, self.steps)


__all__ = ["CHECKS", "Drill", "Facts", "LessonView", "Step"]
