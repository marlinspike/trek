"""Officers working together on a problem, such as Spock and Seven's tachyon detector [E].

A collaboration names the officers who take part, the phrases that set it off
when the captain talks to one of them, the project it starts (sim/projects.py),
and what each of them says. The Bridge checks every request against these before
anything else, so collaborations work with or without a language model.

To add one: add a `Collaboration` to `COLLABORATIONS` (and its project to
`sim.projects.PROJECTS` if it builds something).
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Collaboration:
    id: str
    project: str                      # the sim project it starts
    officers: tuple[str, ...]         # officer ids; the first speaks first
    trigger: re.Pattern[str]          # matched against what the captain says (lower case)
    start: tuple[tuple[str, str], ...]  # (officer id, line) said when work begins
    done: tuple[tuple[str, str], ...]   # said when the project completes


COLLABORATIONS: tuple[Collaboration, ...] = (
    # checked in order: a request that mentions the dish is about the dish, even if it mentions cloaks too
    Collaboration(
        id="deflector",
        project="deflector",
        officers=("spock", "seven"),
        trigger=re.compile(r"\b(deflector|dish|graviton|pulse)\b"),
        start=(
            ("seven", "I can modulate the deflector to emit a tachyon field ahead of us. Commander, the phase "
                      "variance?"),
            ("spock", "I will compensate. Twelve seconds, Captain. Point the bow where you believe they are."),
        ),
        done=(
            ("seven", "The deflector is ready. Say 'pulse' and anything cloaked ahead of us will be exposed."),
            ("spock", "Each pulse drains the batteries and needs half a minute to recharge. Use it judiciously."),
        ),
    ),
    Collaboration(
        id="tachyon",
        project="tachyon",
        officers=("spock", "seven"),
        trigger=re.compile(r"\b(cloak\w*|tachyon|detector|hidden ships?|find (them|the enemy)|can'?t see)\b"),
        start=(
            ("spock", "If they are cloaked, a tachyon burst would scatter off their hulls. Seven, I propose we "
                      "modify a torpedo casing to carry one."),
            ("seven", "Agreed. I will recalibrate the warhead to emit a tachyon field. Twenty seconds, Captain."),
        ),
        done=(
            ("seven", "The tachyon torpedo is ready in tube {tube}. Detonate it where you believe they are hiding."),
            ("spock", "The particles should outline any cloaked vessel for about half a minute. Fire when ready."),
        ),
    ),
)


def matching(officer_id: str, text: str) -> Collaboration | None:
    """The collaboration the captain is asking this officer for, if any."""
    low = text.lower()
    for c in COLLABORATIONS:
        if officer_id in c.officers and c.trigger.search(low):
            return c
    return None


def for_project(project: str) -> Collaboration | None:
    return next((c for c in COLLABORATIONS if c.project == project), None)


__all__ = ["COLLABORATIONS", "Collaboration", "for_project", "matching"]
