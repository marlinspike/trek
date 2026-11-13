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
    first: bool = False                 # heard before ordinary orders, whose words it would otherwise read as [E]


COLLABORATIONS: tuple[Collaboration, ...] = (
    # checked in order: a request that mentions the dish is about the dish, even if it mentions cloaks too
    # [E] a torpedo that flies a damaged ship's plasma trail (sim/systems/ordnance.py)
    Collaboration(
        id="seeker",
        project="seeker",
        first=True,
        officers=("seven", "spock"),
        trigger=re.compile(r"\b(program|design|build|make|rig|modify|prepare)\b.*\b(torpedo|torp|round|seeker)s?\b.*"
                           r"\b(exhaust|plasma|trail|follow|track|chase)\b|\b(design|build|make)\b.*\bseekers?\b"),
        start=(
            ("seven", "A torpedo can be taught to follow a plasma trail. I will rewrite its guidance to seek the "
                      "ionised exhaust."),
            ("spock", "And I will widen its sensor cone, so it does not lose the scent at a turn. Eighteen seconds."),
        ),
        done=(
            ("seven", "The plasma-seeker is ready in tube {tube}. Say 'seeker' and it will follow the nearest trail "
                      "to its source."),
            ("spock", "It will follow every turn she made, Captain. Only a repaired drive leaves it nothing to follow."),
        ),
    ),
    # [E] the Borg (sim/collective.py)
    Collaboration(
        id="harmonic",
        project="harmonic",
        first=True,
        officers=("seven", "worf", "spock", "sulu"),
        trigger=re.compile(r"\bharmonic\b.*\b(torpedo|torp|round|warhead)s?\b|\b(design|build|load)\s+harmonics?\b"),
        start=(
            ("seven", "I will tune three warheads to their shield harmonics. Mr. Worf, keep the tubes clear."),
            ("worf", "The tubes are yours. Sixteen seconds."),
        ),
        done=(
            ("seven", "Harmonic torpedoes are loaded. Their shields will not stop them, until the hive adapts."),
            ("worf", "They go with the next volley, Captain."),
        ),
    ),
    Collaboration(
        id="inoculate",
        project="inoculate",
        first=True,
        officers=("doctor", "seven"),
        trigger=re.compile(r"\b(inoculat\w*|vaccin\w*|antigen|immuni[sz]\w*|nanoprobes?)\b"),
        start=(
            ("doctor", "A nanoprobe antigen. Seven, I will need a sample of your own nanoprobes as the template."),
            ("seven", "Take what you need, Doctor. The crew must not become drones."),
        ),
        done=(
            ("doctor", "The inoculation is done. Anyone the drones overpower dies a free man rather than joins them. "
                       "Small comfort, but it is something."),
        ),
    ),
    Collaboration(
        id="encrypt",
        project="encrypt",
        first=True,
        officers=("geordi", "seven", "spock"),
        trigger=re.compile(r"\b(encrypt\w*|lock\s*out|lockouts?|lock\s+(?:them|the\s+drones|the\s+computer)\s+out)\b"),
        start=(
            ("geordi", "Encrypting the command codes, section by section. Seven, which routines do they hit first?"),
            ("seven", "Environmental, then propulsion. Lock those first."),
        ),
        done=(
            ("geordi", "Lockout's in place. They can walk the corridors all they like; they're not taking another system."),
        ),
    ),
    Collaboration(
        id="sever",
        project="sever",
        first=True,
        officers=("seven", "spock", "geordi"),
        trigger=re.compile(r"\b(sever\w*|cut\s+(?:the|their|them|the\s+drones)\s*(?:off|link|links)?|isolate\s+the\s+drones)\b"),
        start=(
            ("seven", "The drones aboard still hear the hive. I will flood their subspace link with noise."),
        ),
        done=(
            ("seven", "The drones aboard are cut off from the Collective. Alone, they are slow, and they cannot learn."),
        ),
    ),
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


def matching(officer_id: str, text: str, first: bool = False) -> Collaboration | None:
    """The collaboration the captain is asking this officer for, if any (`first`: only those heard before
    ordinary orders)."""
    low = text.lower()
    for c in COLLABORATIONS:
        if (c.first or not first) and officer_id in c.officers and c.trigger.search(low):
            return c
    return None


def for_project(project: str) -> Collaboration | None:
    return next((c for c in COLLABORATIONS if c.project == project), None)


__all__ = ["COLLABORATIONS", "Collaboration", "for_project", "matching"]
