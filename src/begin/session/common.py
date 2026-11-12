"""Constants and small helpers shared by the battle session's parts."""

from __future__ import annotations

import re
from typing import Protocol

from ..battle import Battle
from ..console.vocab import VERBS
from ..sim.events import Tone as EventTone
from ..sim.ship import Ship

CHART = "\0chart"             # `Printout.live` for the chart, which the session keeps current
ORDER_TRANSLATE_WAIT = 8.0    # seconds a named order waits for a step's translation before skipping it

EVENT_TONE = {EventTone.INFO: "text", EventTone.GOOD: "good", EventTone.CAUTION: "caution", EventTone.ALERT: "alert",
              EventTone.CREW: "crew"}


class TourLink(Protocol):
    """What a battle on a tour of duty can ask of the tour (a `TourRun`)."""

    def reinforcement_arrival(self, battle: Battle, player_ship: Ship | None) -> tuple[object | None, str]: ...


# "hail the X", "open a channel to X", "open hailing frequencies", "get me the X", "put me through to X" [E]
HAIL_ORDER = re.compile(r"^\s*(hail(ing)?( frequencies)?|open (a |hailing )?(channel|frequencies|comms?)( to| with)?|"
                         r"get me|put me through to|signal|raise them|raise the)\b\s*", re.I)


def exact_verb(text: str) -> bool:
    """The line starts with a console verb spelled in full (not a number, prefix or ordinary word)."""
    first = text.strip().lower().split(None, 1)[:1]
    return bool(first) and any(first[0] in spellings for spellings in VERBS.values())


__all__ = ["CHART", "EVENT_TONE", "HAIL_ORDER", "ORDER_TRANSLATE_WAIT", "TourLink", "exact_verb"]
