"""The bridge's voices: one line at a time, on a thread of their own [E].

The screen hands the speaker every line an officer says aloud (the same lines the subtitles show), each with who
says it and what kind of line it is. The speaker casts it (see `casting.py`), cleans it for the ear, and speaks it
through the engine, one voice at a time:

- an urgent line (a warning, a refusal) goes to the front and cuts short a routine one being spoken;
- routine lines still waiting when two more have queued behind them are dropped (an officer's remark before an
  answer to the captain), and a line that has waited more
  than a few seconds is no longer news and is dropped too (a warning keeps a little longer, and only the two newest
  wait): the log keeps every word, the voice only what is current;
- nothing is spoken that the settings don't ask for (see `SpeechSettings.wants`).

It never blocks the game: the engine speaks on the speaker's thread.
"""

from __future__ import annotations

import re
import threading
import time
from dataclasses import dataclass, field
from typing import Callable

from .casting import CAST, VoiceInfo, cast_all, part_for
from .engines import Engine, Silent, Spoken, make_engine
from .settings import SpeechSettings

MAX_WAITING = 2       # routine lines waiting beyond this are dropped
FIXED = "<fixed>"
CUT_EVERY = 0.05      # seconds between tries at stopping a line being cut short
CUT_TRIES = 20
URGENT_STALE = 10.0   # a warning still waiting after this long has been overtaken by events
STALE = 6.0           # seconds a routine line may wait before it's no longer worth saying

_HINT = re.compile(r"\s*\((?:[YN] |Ctrl|press|type|say )[^)]*\)")     # "(Y makes it so, N belays)"
_CLASS = re.compile(r"\s*\((?:[A-Z]{2,3})\)")                          # "Sandstorm (FR)"
_CONTACT = re.compile(r"#(\d+)")
_UNITS = re.compile(r"(\d),(\d{3})")
_FIGURES = re.compile(r"\s*\([\d\s,.<>=≥≤/%×-]*\)")                     # "(12,467 > 2,000)": for the eye only
_POINT_NOUGHT = re.compile(r"\b(\d+)\.0\b")                             # "warp 4.0" is "warp 4"


def speakable(text: str) -> str:
    """A line as it should be heard: no key hints or class codes in brackets, contacts by number, plain dashes."""
    t = _HINT.sub("", text)
    t = _CLASS.sub("", t)
    t = _FIGURES.sub("", t)
    t = _POINT_NOUGHT.sub(r"\1", t)
    t = _CONTACT.sub(r"contact \1", t)
    t = _UNITS.sub(r"\1\2", t)
    t = t.replace("›", "").replace("·", ",").replace("—", ", ").replace("–", " to ").replace("×", " times ")
    return re.sub(r"\s+", " ", t).strip()


@dataclass
class _Ask:
    part: str
    text: str
    urgent: bool
    at: float
    cut: bool = False
    kind: str = "report"


@dataclass
class Speaker:
    """Speaks the bridge's lines. `store` is settings.json's "speech" section, read afresh for every line (Settings
    and the battle page change it in place); `play`/`stop_play` let Piper's voices through the screen's sound."""
    store: dict[str, object] = field(default_factory=dict)
    play: Callable[[bytes, float], None] | None = None
    stop_play: Callable[[], None] | None = None
    engine: Engine | None = None
    _waiting: list[_Ask] = field(default_factory=list)
    _speaking: _Ask | None = None
    _wake: threading.Condition = field(default_factory=threading.Condition)
    _thread: threading.Thread | None = None
    _closed: bool = False
    _engine_for: str = ""
    _voices: list[VoiceInfo] | None = None
    _cast: tuple[object, dict[str, str | None]] | None = None
    said: list[tuple[str, str]] = field(default_factory=list)    # (part, text) spoken, most recent last (for tests)

    @staticmethod
    def silent() -> Speaker:
        """A speaker that says nothing: for tests and for screens with no voices."""
        return Speaker(engine=Silent())

    @property
    def settings(self) -> SpeechSettings:
        return SpeechSettings.from_dict(self.store)

    # ------------------------------------------------------------ the engine and its voices

    def __post_init__(self) -> None:
        if self.engine is not None:
            self._engine_for = FIXED          # an engine handed in (a test's) is kept whatever the settings say

    def _engine(self) -> Engine:
        if self._engine_for == FIXED and self.engine is not None:
            return self.engine
        choice = self.settings.engine
        if self.engine is None or choice != self._engine_for:
            if self.engine is not None:
                self.engine.close()
            self.engine = make_engine(choice, self.play, self.stop_play)
            self._engine_for = choice
            self._voices = None
        return self.engine

    def problem(self) -> str | None:
        """Why nothing will be heard, or None."""
        s = self.settings
        if not s.enabled:
            return "Officers' voices are off."
        return self._engine().problem()

    def voices(self) -> list[VoiceInfo]:
        if self._voices is None:
            self._voices = self._engine().voices()
        return self._voices

    def voice_for(self, part: str) -> str | None:
        """The voice a part speaks with now: the player's choice, or the cast's."""
        kind, voices, chosen = self._engine().kind, self.voices(), self.settings.cast
        key = (kind, id(voices), tuple(sorted(chosen.items())))
        if self._cast is None or self._cast[0] != key:
            self._cast = (key, cast_all(kind, voices, chosen))
        return self._cast[1].get(part, self._cast[1].get("captain"))

    def line_for(self, part: str, text: str) -> Spoken:
        s = self.settings
        cast = CAST.get(part, CAST["captain"])
        return Spoken(speakable(text), self.voice_for(part), cast.rate * s.rate, cast.pitch, s.volume)

    # ------------------------------------------------------------ speaking

    def say(self, text: str, officer: str | None = None, faction: str | None = None, kind: str = "report",
            urgent: bool = False) -> bool:
        """Queue a line, if the settings want it said. True when it was queued."""
        if not self.settings.wants(kind, urgent) or not text.strip():
            return False
        ask = _Ask(part_for(officer, faction), text, urgent, time.monotonic(), kind=kind)
        with self._wake:
            if urgent:
                self._waiting.insert(0, ask)
                if self._speaking is not None and not self._speaking.urgent:
                    self._cut_short(self._speaking)
            elif any(a.text == text for a in self._waiting) or (
                    self._speaking is not None and self._speaking.text == text and not self._speaking.cut):
                return False                     # already about to be said, or being said: once is enough
            else:
                self._waiting.append(ask)
            while sum(1 for a in self._waiting if not a.urgent) > MAX_WAITING:     # remarks go before answers
                routine = [a for a in self._waiting if not a.urgent]
                self._waiting.remove(next((a for a in routine if a.kind == "report"), routine[0]))
            while sum(1 for a in self._waiting if a.urgent) > MAX_WAITING:     # the newest warnings, not a backlog
                self._waiting.remove(next(a for a in reversed(self._waiting) if a.urgent))
            self._wake.notify()
        self._start()
        return True

    def hear(self, part: str, text: str | None = None) -> None:
        """Say a sample line in a part's voice now (Settings' Hear button), whatever is queued."""
        sample = text or SAMPLES.get(part, "All systems ready, Captain.")
        self.stop()
        with self._wake:
            self._waiting.insert(0, _Ask(part, sample, True, time.monotonic()))
            self._wake.notify()
        self._start()

    def _cut_short(self, ask: _Ask) -> None:
        """Cut short the line being said (call with `_wake` held). The engine is told to stop until the line is
        over: a stop that lands just before the engine has started its process would otherwise be lost."""
        ask.cut = True
        threading.Thread(target=self._stop_engine, args=(ask,), daemon=True).start()

    def _stop_engine(self, ask: _Ask) -> None:
        for _ in range(CUT_TRIES):
            eng = self.engine
            if eng is not None:
                eng.stop()
            time.sleep(CUT_EVERY)
            with self._wake:
                if self._speaking is not ask:
                    return

    def stop(self) -> None:
        """Hush: drop everything waiting and cut short what is being said."""
        with self._wake:
            self._waiting.clear()
            if self._speaking is not None:
                self._cut_short(self._speaking)

    def close(self) -> None:
        with self._wake:
            self._closed = True
            self._waiting.clear()
            self._wake.notify()
        if self.engine is not None:
            self.engine.close()

    def _start(self) -> None:
        # under the lock: a thread that has just decided to end clears `_thread` first, so a line queued in that
        # moment always gets a thread to say it
        with self._wake:
            if self._thread is None or not self._thread.is_alive():
                self._closed = False
                self._thread = threading.Thread(target=self._run, daemon=True, name="speech")
                self._thread.start()

    def _next(self) -> _Ask | None:
        with self._wake:
            while not self._waiting and not self._closed:
                self._wake.wait(timeout=30)
                if not self._waiting:
                    self._thread = None  # idle: the thread ends, and the next line starts another
                    return None
            if self._closed:
                self._thread = None
                return None
            ask = self._waiting.pop(0)
            self._speaking = ask
            return ask

    def _run(self) -> None:
        while True:
            ask = self._next()
            if ask is None:
                return
            try:
                if time.monotonic() - ask.at <= (URGENT_STALE if ask.urgent else STALE):
                    line = self.line_for(ask.part, ask.text)
                    with self._wake:
                        if ask.cut:
                            continue
                    self.said.append((ask.part, line.text))
                    del self.said[:-50]
                    self._engine().speak(line)
            except Exception:  # noqa: BLE001 - a voice that fails must never stop the game
                pass
            finally:
                with self._wake:
                    self._speaking = None


SAMPLES = {
    "spock": "Fascinating. Their shields are weakest aft, Captain. I recommend we come about.",
    "worf": "Torpedoes armed and locked on the target, Captain. Ready to fire.",
    "geordi": "I can give you warp eight, Captain, but she won't like it for long.",
    "seven": "Their vessel has adapted to our phasers. Remodulating now.",
    "sulu": "Course laid in, Captain. Warp six on your order.",
    "chekov": "Keptin, enemy ship bearing two seven zero, closing fast!",
    "doctor": "Sickbay is ready, Captain. Please try not to fill it.",
    "computer": "Warning. Hull integrity at forty percent.",
    "klingon": "You fight like a Ferengi. Surrender, or die with honour.",
    "romulan": "You are in Romulan space, Captain. Leave, while you still can.",
    "orion": "A fine ship you have there, Captain. It would be a shame to scratch it.",
    "borg": "Lower your shields and surrender your vessel.",
    "captain": "This is the captain. State your business.",
}


__all__ = ["CUT_EVERY", "MAX_WAITING", "URGENT_STALE", "SAMPLES", "STALE", "Speaker", "speakable"]
