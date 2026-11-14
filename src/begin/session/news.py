"""What a game session tells whoever is watching it: the outbox the UI (or a network peer, or a test) reads.

A session never draws, plays a sound or touches a widget. Everything the captain should see or hear comes out
as one of these plain records, in order, through `Session.subscribe`. The battle screen turns them into log
lines, subtitles, sounds and printouts; a headless test just collects them; a network host would send them on.

Tones are words, not colours, so the UI picks its own palette:
text, dim, good, caution, alert, crew, friend (the captain's own words), hail (another ship's captain) and
readback (an officer repeating an order).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Union

from ..sim.events import Event

Tone = Literal["text", "dim", "good", "caution", "alert", "crew", "friend", "hail", "readback"]
ALERT_TONE = {"red": "alert", "yellow": "caution", "green": "good"}    # alert conditions, as tones
TONES: tuple[str, ...] = ("text", "dim", "good", "caution", "alert", "crew", "friend", "hail", "readback")


@dataclass(frozen=True, slots=True)
class Line:
    """A line for the log. `channel` is "bridge" for people speaking, "computer" for everything else."""
    text: str
    tone: str = "text"
    channel: str = "computer"
    mono: bool = False
    tick: int = 0


@dataclass(frozen=True, slots=True)
class Notice:
    """A short message to flash where the captain is looking (a refused order, a problem)."""
    text: str
    tone: str = "caution"
    seconds: float = 3.0


@dataclass(frozen=True, slots=True)
class Voice:
    """Someone says a line aloud: subtitles, and the officers' spoken voices."""
    speaker: str
    text: str
    tone: str = "crew"
    station: str | None = None
    officer: str | None = None
    urgent: bool = False
    kind: str = "report"           # readback | proposal | report | hail: what a spoken-voice setting may skip
    faction: str | None = None     # an enemy captain's race, so the voice can be cast by it


@dataclass(frozen=True, slots=True)
class Cue:
    """A sound the moment calls for: confirm, deny, lock, alert."""
    name: str
    level: float = 0.6


@dataclass(frozen=True, slots=True)
class Printout:
    """A display (status, damage, chart...) to keep on the map. `live` re-runs it as the battle moves on."""
    lines: tuple[str, ...]
    live: str | None = None


@dataclass(frozen=True, slots=True)
class Prompt:
    """Put `text` in the console, ready for the captain to finish (None: just give the console focus)."""
    text: str | None = None


@dataclass(frozen=True, slots=True)
class Show:
    """Open a screen over the battle: 'debrief' when it ends."""
    overlay: str


@dataclass(frozen=True, slots=True)
class Request:
    """A console order that belongs to whoever is presenting the battle, not to the game: display range,
    the manual, sound, the HUD and Bridge settings, key macros, voice orders."""
    name: str
    value: object = None


@dataclass(frozen=True, slots=True)
class Ticked:
    """The world moved on (or an order landed): the events this side saw, for effects and sound."""
    events: tuple[Event, ...] = field(default_factory=tuple)
    stepped: bool = False


@dataclass(frozen=True, slots=True)
class Commanding:
    """The captain now commands this ship (at the start, or after beaming across)."""
    ship_id: int


News = Union[Line, Notice, Voice, Cue, Printout, Prompt, Show, Request, Ticked, Commanding]

__all__ = ["ALERT_TONE", "Commanding", "Cue", "Line", "News", "Notice", "Printout", "Prompt", "Request", "Show", "TONES",
           "Ticked", "Tone", "Voice"]
