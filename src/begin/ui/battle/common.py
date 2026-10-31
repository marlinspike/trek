"""Constants and small helpers shared by the battle screen's parts."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Protocol

import pygame

from ...battle import Battle
from ...console.vocab import VERBS
from ...sim.events import Tone
from ...sim.ship import Ship
from .. import theme

SPEEDS = (0.25, 0.5, 1.0, 2.0, 4.0)
TONE_COLOR = {
    Tone.INFO: theme.TEXT, Tone.GOOD: theme.GOOD, Tone.CAUTION: theme.CAUTION, Tone.ALERT: theme.ALERT,
    Tone.CREW: theme.CREW,
}

CONTROLS = [
    ("Space", "Pause / resume"),
    ("[  ]", "Slower / faster (0.25× – 4×)"),
    ("W  S", "Warp up / down"),
    ("A  D", "Turn 15° port / starboard (Shift: 5°)"),
    ("Right-click map", "Steer toward that point"),
    ("Shift + right-click ship", "Pursue that ship"),
    ("Left-click ship", "Select target"),
    ("Tab", "Next target"),
    ("R", "Cycle subsystem aim (hull, propulsion, weapons…)"),
    ("F  T  P", "Fire phasers / torpedoes / launch probe"),
    ("X", "Scan target"),
    ("G", "Raise / lower shields"),
    ("V", "Cycle point-defense doctrine"),
    ("Q", "Show phaser arcs"),
    ("Wheel, + −", "Zoom"),
    ("Drag, arrows", "Pan the map"),
    ("C", "Centre and follow own ship"),
    ("Enter or /", "Open the command console (type 'help')"),
    ("F2-F8, F10-F12, Ctrl+key", "Run a 'key' macro you defined in the console"),
    ("Wheel over the log", "Scroll the console log"),
    ("I", "Damage assessment (inspect own ship)"),
    ("M", "Sound on / off"),
    ("F1 or H", "This reference"),
    ("Esc", "Close overlay / battle menu"),
]


@dataclass
class LogLine:
    tick: int
    text: str
    color: theme.Color
    mono: bool = False


FKEYS = {getattr(pygame, f"K_F{n}"): f"F{n}" for n in (2, 3, 4, 5, 6, 7, 8, 10, 11, 12)}


RED_ALERT_FLOOR, RED_ALERT_PULSE, RED_ALERT_PERIOD = 0.22, 0.38, 1.8   # border tint and its pulse (seconds)
ORDER_TRANSLATE_WAIT = 8.0     # seconds a named order waits for a step's translation before skipping it


class TourLink(Protocol):
    """What a battle on a tour of duty can ask of the tour (a `TourRun`)."""

    def reinforcement_arrival(self, battle: Battle, player_ship: Ship | None) -> tuple[object | None, str]: ...


# "hail the X", "open a channel to X", "open hailing frequencies", "get me the X", "put me through to X" [E]
HAIL_ORDER = re.compile(r"^\s*(hail(ing)?( frequencies)?|open (a |hailing )?(channel|frequencies|comms?)( to| with)?|"
                         r"get me|put me through to|signal|raise them|raise the)\b\s*", re.I)


def ratio(hits: int, shots: int) -> str:
    return f"{hits}/{shots}"


def exact_verb(text: str) -> bool:
    """The line starts with a console verb spelled in full (not a number, prefix or ordinary word)."""
    first = text.strip().lower().split(None, 1)[:1]
    return bool(first) and any(first[0] in spellings for spellings in VERBS.values())
