"""Standing objectives the captain gives an officer, such as "disable their shields" [E].

The simulation only records them (so they replay with the battle). The officer
who was asked works out how to meet one, turn by turn (crew/objectives.py), and
ends it with `EndObjective` when it is met or can't be.

To add a goal: add it to `GOALS`, then give it a planner in `crew/objectives.py`.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from .ship import TARGETABLE_GROUPS

if TYPE_CHECKING:
    from .observation import ContactView, Observation

GOALS = ("disable", "destroy", "capture")

# what the captain can ask to have disabled, and how each is spoken of
DISABLE_GROUPS: dict[str, str] = {
    "shields": "shields", "phasers": "phasers", "torpedoes": "torpedo tubes", "weapons": "weapons",
    "propulsion": "engines", "sensors": "sensors", "cloak": "cloaking device",
}
DESTROY_GROUP = "hull"   # the group a destroy objective is filed under
CAPTURE_GROUP = "crew"   # and a capture: her crew are what stands between us and her
assert set(DISABLE_GROUPS) <= set(TARGETABLE_GROUPS)


@dataclass(slots=True)
class Objective:
    goal: str                    # one of GOALS
    group: str                   # a TARGETABLE_GROUPS key (what to disable)
    targets: tuple[int, ...]     # ship ids
    officer: str = ""            # who works on it; "" = the science officer
    started: int = 0             # tick

    def describe(self, names: dict[int, str] | None = None) -> str:
        who = ", ".join((names or {}).get(t, f"#{t}") for t in self.targets)
        if self.goal in ("destroy", "capture"):
            return f"{self.goal} {who}"
        return f"{self.goal} {DISABLE_GROUPS.get(self.group, self.group)} on {who}"


def baitable(obs: Observation, c: ContactView) -> bool:
    """Will this ship's point defense spend several banks on a lone torpedo? Judged from what Seven
    knows: its race's habits, and from a scan, how many of its crew are left [E]."""
    if c.cls is None:
        return False
    faction = obs.content.factions.get(c.cls.faction)
    discipline = faction.pd_discipline if faction is not None else 0.7
    if c.scan is not None:
        discipline *= 0.5 + 0.5 * max(0.0, min(1.0, c.scan.crew / max(1, c.cls.crew)))
    return discipline < 0.6


__all__ = ["CAPTURE_GROUP", "DESTROY_GROUP", "DISABLE_GROUPS", "GOALS", "Objective", "baitable"]
