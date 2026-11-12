"""Game modes the main menu offers, so a new kind of battle needs no change to the menu [E].

A `Mode` makes a `BattleSetup` from the content, a seed and the faction the player chose. The menu draws one
button per registered mode, in order, with its hotkey; the battle screen plays whatever setup it makes. To add a
mode, write its setup function (see `battle.patrol_battle`) and `register` it here, or from a plugin module.
Linked campaigns (the tour of duty) and hand-made battles (presets, the custom screen) have pages of their own.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable

from .battle import BattleSetup, patrol_battle, quick_battle
from .content.schema import ContentDB

SetupMaker = Callable[[ContentDB, int, str], BattleSetup]


@dataclass(frozen=True)
class Mode:
    key: str                 # a stable id: "quick", "patrol"
    title: str               # the menu button
    blurb: str               # its tooltip
    hotkey: str | None       # a key name on the main menu ("return", "p"), or None
    make: SetupMaker         # (content, seed, player faction) -> the battle


MODES: list[Mode] = [
    Mode("quick", "Quick battle", "A seeded random engagement", "return",
         lambda content, seed, faction: quick_battle(content, seed, faction)),
    Mode("patrol", "Patrol", "A random mission: an ambush, a wolf pack, a second wave, an escort or a flagship", "p",
         lambda content, seed, faction: patrol_battle(content, seed, faction)),
]


def register(mode: Mode) -> None:
    """Add a mode to the menu (replacing one with the same key)."""
    for i, m in enumerate(MODES):
        if m.key == mode.key:
            MODES[i] = mode
            return
    MODES.append(mode)


def find(key: str) -> Mode | None:
    return next((m for m in MODES if m.key == key), None)


__all__ = ["MODES", "Mode", "SetupMaker", "find", "register"]
