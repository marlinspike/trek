"""Constants and small helpers shared by the battle screen's parts."""

from __future__ import annotations

from dataclasses import dataclass

import pygame

from .. import theme

SPEEDS = (0.25, 0.5, 1.0, 2.0, 4.0)
# the session's tones (see session/news.py) in this screen's colours
TONE_COLOR: dict[str, theme.Color] = {
    "text": theme.TEXT, "dim": theme.TEXT_DIM, "good": theme.GOOD, "caution": theme.CAUTION, "alert": theme.ALERT,
    "crew": theme.CREW, "friend": theme.FRIEND, "hail": theme.HAIL, "readback": theme.mix(theme.TEXT_DIM, theme.CREW, 0.45),
}

CONTROLS = [
    ("Space", "Pause / resume"),
    ("[  ]", "Slower / faster (0.25× – 4×)"),
    ("W  S", "Warp up / down"),
    ("A  D", "Turn 15° port / starboard (Shift: 5°)"),
    ("Right-click map", "Steer toward that point"),
    ("Right-click ship, E", "Command wheel on that ship (E: your target); 1-8 pick a slice"),
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
    ("O, then 1-4", "Counsel: each officer's plan from here; 1-4 go all in ('counsel <goal>' aims it)"),
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
    channel: str = "computer"     # "bridge": people speaking (the captain, officers, other captains); "computer": the rest


FKEYS = {getattr(pygame, f"K_F{n}"): f"F{n}" for n in (2, 3, 4, 5, 6, 7, 8, 10, 11, 12)}


RED_ALERT_FLOOR, RED_ALERT_PULSE, RED_ALERT_PERIOD = 0.22, 0.38, 1.8   # border tint and its pulse (seconds)
RED_ALERT_SETTLE = 6.0     # seconds the red alert pulses before it settles to a steady edge


def ratio(hits: int, shots: int) -> str:
    return f"{hits}/{shots}"
