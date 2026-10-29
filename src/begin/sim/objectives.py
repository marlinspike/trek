"""Standing objectives the captain gives an officer, such as "disable their shields" [E].

The simulation only records them (so they replay with the battle). The officer
who was asked works out how to meet one, turn by turn (crew/objectives.py), and
ends it with `EndObjective` when it is met or can't be.

To add a goal: add it to `GOALS`, then give it a planner in `crew/objectives.py`.
"""

from __future__ import annotations

from dataclasses import dataclass

from .ship import TARGETABLE_GROUPS

GOALS = ("disable", "destroy")

# what the captain can ask to have disabled, and how each is spoken of
DISABLE_GROUPS: dict[str, str] = {
    "shields": "shields", "phasers": "phasers", "torpedoes": "torpedo tubes", "weapons": "weapons",
    "propulsion": "engines", "sensors": "sensors", "cloak": "cloaking device",
}
DESTROY_GROUP = "hull"   # the group a destroy objective is filed under
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
        if self.goal == "destroy":
            return f"destroy {who}"
        return f"{self.goal} {DISABLE_GROUPS.get(self.group, self.group)} on {who}"


__all__ = ["DESTROY_GROUP", "DISABLE_GROUPS", "GOALS", "Objective"]
