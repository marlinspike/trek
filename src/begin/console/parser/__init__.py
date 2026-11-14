"""Begin-style command console.

Turns typed orders into the same typed commands the mouse, the AI and the
officers use. Every command in the Begin manual works in its documented
forms ("fire phasers 1 2 3 spread 10", "lock all tubes on bluefin with a
dispersion of 45", "tell the agena to attack the derango"), as do terse
forms ("fir tor al", "fp 1 2 s 10", "al tor al mk7 1200") and the remake's
additions (autoload, fire modes, point defense, bank roles, time control).

As in Begin, any word can be shortened to a unique prefix ("fir tor 1,2,3"); a verb prefix several
commands share is settled by the words after it ("pu tal" = pursue the Talon),
and words like "the", "to", "at", "on" and "with" are ignored. Mount lists
accept "all"/"al", "1 2 3", "1,2,3", "1 2 and 3" and ranges "1-3". Ships are
named by any unique prefix of their name, or "#<id>" for an unidentified
contact.

The parser never touches the world: it reads an `Observation` and returns
commands for the caller to submit, UI actions, and text displays.

The parser is a package: `base` holds the results, the context and the dispatch; each station's verbs are a
mixin in a module of its own (helm, weapons, systems, status, allies, comms, borg, officers, interface).
"""

from __future__ import annotations

from ..tokens import ParseError
from .allies import AllyVerbs
from .base import (
    AWAY_CALLS, BRIDGE_SWITCHES, DUTY_WORDS, FLEET_WORDS, KEEP_MIN, NOTHING_LOST, SHIELD_SIDES, SHUTTLE_CALLS,
    ParseContext, ParseResult,
)
from .borg import BorgVerbs
from .comms import CommsVerbs
from .helm import HelmVerbs
from .interface import InterfaceVerbs
from .officers import OfficerVerbs
from .status import StatusVerbs
from .systems import SystemVerbs
from .weapons import WeaponVerbs


class Parser(HelmVerbs, WeaponVerbs, SystemVerbs, StatusVerbs, AllyVerbs, InterfaceVerbs, BorgVerbs, CommsVerbs, OfficerVerbs):
    """Begin's console language, read against one `Observation`."""


def parse(text: str, ctx: ParseContext) -> ParseResult:
    try:
        return Parser(ctx).parse(text)
    except ParseError as e:
        return ParseResult(error=str(e), echo=text)


__all__ = [
    "AWAY_CALLS",
    "BRIDGE_SWITCHES",
    "DUTY_WORDS",
    "FLEET_WORDS",
    "KEEP_MIN",
    "NOTHING_LOST",
    "ParseContext",
    "ParseError",
    "ParseResult",
    "Parser",
    "SHIELD_SIDES",
    "SHUTTLE_CALLS",
    "parse",
]
