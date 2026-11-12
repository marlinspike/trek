"""Pointing: "fire at him" means the ship under the mouse [E].

When the captain types (or says) an order while the mouse rests on a ship,
words that point at a ship are read as that ship: "that one", "this ship",
and "him", "her", "it" or "them" straight after a word that takes a ship
("fire at her", "pursue him", "scan it", "hail them"). The line is rewritten
with the ship's name before it is parsed, and the rewritten line is what the
log shows, so the captain sees exactly which ship was meant.

"her" in "raise her shields" is left alone: it doesn't follow a word that
takes a ship. And nothing is rewritten when the mouse isn't on a ship.
"""

from __future__ import annotations

import re

_DEMONSTRATIVE = re.compile(r"\b(that|this)\s+(one|ship|vessel|contact|bird of prey|cruiser)\b", re.I)
_TAKES_SHIP = (r"at|on|to|target|targeting|pursue|chase|follow|elude|evade|scan|hail|lock|tractor|board|"
               r"disable|cripple|destroy|capture|bait|engage|attack|intercept|escort|defend|approach")
_PRONOUN = re.compile(rf"\b({_TAKES_SHIP})\s+(him|her|it|them)\b", re.I)


def resolve_pointing(text: str, name: str | None) -> str:
    """`text` with pointing words replaced by `name` (the ship under the mouse); unchanged if there is none."""
    if not name:
        return text
    out = _DEMONSTRATIVE.sub(name, text)
    return _PRONOUN.sub(lambda m: f"{m.group(1)} {name}", out)


def points(text: str) -> bool:
    """Whether the line points at a ship at all."""
    return bool(_DEMONSTRATIVE.search(text) or _PRONOUN.search(text))


__all__ = ["points", "resolve_pointing"]
