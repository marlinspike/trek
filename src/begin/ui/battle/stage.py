"""One card on the map at a time [E].

A big fight is when the captain most needs a calm screen, so the map shows one transient card at a time: an
officer's proposal, the comms card while someone is talking, a subtitle, or the mission card when the mission
has news. Whatever isn't the one shrinks to a one-line strip (the mission, the comms channel) or waits in the log
(a subtitle; the log keeps every word). The counsel, when the captain opens it, is the one.

The order, first that applies:

  counsel     the captain opened it
  proposal    an officer is waiting for a yes or no
  comms       someone on the channel spoke in the last few cycles, or the captain brought it up
  urgent      a warning or a refusal in a subtitle
  mission     the mission card has news (it started, changed, or ended): shown in full for a few seconds of its
              own turn, and again while the captain's pointer rests on its strip
  subtitle    an officer's line

Pure bookkeeping: what to show, not how; `render.py` draws it.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

import pygame

MISSION_NEWS = 8.0      # seconds the mission card shows in full when it has news
COMMS_FRESH = 8.0       # cycles after the last word on a channel that the comms card stays open

_NUMBERS = re.compile(r"[\d,.]+")


def news_key(state: str, kind: str, hint: str, tone: object) -> tuple[object, ...]:
    """What makes the mission card news: its state, its kind, what it asks of the captain (numbers aside, so a
    closing range isn't news) and its colour (time running short is)."""
    return state, kind, _NUMBERS.sub("#", hint), tone


@dataclass
class Stage:
    news: tuple[object, ...] | None = None    # the mission's news as last seen
    news_left: float = 0.0                     # seconds of the mission card's turn still to come
    last: float = 0.0                          # when `pick` last ran (wall clock)
    shown: str | None = None                   # the card shown this frame
    cards: list[pygame.Rect] = field(default_factory=list)   # the cards and writing drawn on the map last frame

    def pick(self, now: float, *, counsel: bool = False, proposal: bool = False, comms: bool = False,
             urgent: bool = False, news: tuple[object, ...] | None = None, hover: bool = False,
             subtitle: bool = False) -> str | None:
        """The one card to show this frame: counsel, proposal, comms, urgent, mission, subtitle, or None."""
        dt = min(0.25, max(0.0, now - self.last)) if self.last else 0.0
        self.last = now
        if news is None:
            self.news, self.news_left = None, 0.0
        elif news != self.news:
            self.news, self.news_left = news, MISSION_NEWS
        mission = news is not None and (self.news_left > 0 or hover)
        order = (("counsel", counsel), ("proposal", proposal), ("comms", comms), ("urgent", urgent),
                 ("mission", mission), ("subtitle", subtitle))
        self.shown = next((name for name, on in order if on), None)
        if self.shown == "mission" and not hover:
            self.news_left = max(0.0, self.news_left - dt)    # its turn runs only while it is the one shown
        return self.shown

    @property
    def subtitle(self) -> bool:
        return self.shown in ("urgent", "subtitle")


__all__ = ["COMMS_FRESH", "MISSION_NEWS", "Stage", "news_key"]
