"""Tab completion for the console [E].

Tab finishes the word being typed: a command ("tor" → "torpedoes"), a ship on
sensors ("hy" → "Hydra"), an officer ("wo" → "worf,"), a system to aim at,
a station, a named order. One match is filled in with a space after it; several
are extended to what they share and offered in a strip above the console, and
pressing Tab again steps through them. Nothing is ever chosen that the captain
didn't type the start of.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from .vocab import AIM_WORDS, VERBS

# words worth finishing that aren't verbs: the second words of common orders
EXTRA = ("phasers", "torpedoes", "probes", "shields", "all", "spread", "warp", "course", "fire", "evasive",
         "helm", "tactical", "engineering", "science", "manoeuvres", "red", "yellow", "green", "record",
         "stop", "status", "damage", "report", "reinforcements", "detail", "simple", "classic", "quiet", "full")


def vocabulary() -> list[str]:
    words: set[str] = set()
    for spellings in VERBS.values():
        words.update(s for s in spellings if len(s) >= 3 and s.isalpha())
    for spellings in AIM_WORDS.values():
        words.update(s for s in spellings if s.isalpha())
    words.update(EXTRA)
    return sorted(words)


_LAST = re.compile(r"(\S*)$")


@dataclass
class Completer:
    """Remembers the options of the last Tab, so the next Tab steps through them."""

    options: list[str] = field(default_factory=list)
    index: int = -1
    stem: str = ""          # the line before the word being completed
    typed: str = ""         # what the captain had typed of the word

    def reset(self) -> None:
        self.options = []
        self.index = -1

    def complete(self, line: str, names: list[str], officers: list[str], orders: list[str]) -> str:
        """The line after one press of Tab."""
        if self.options and self.index >= 0 and line == self.stem + self.options[self.index] + " ":
            self.index = (self.index + 1) % len(self.options)          # Tab again: the next option
            return self.stem + self.options[self.index] + " "
        if self.options and self.index < 0 and line.lower() == (self.stem + _common_prefix([o.lower() for o in self.options])).lower():
            self.index = 0                                              # Tab on the shared part: the first option
            return self.stem + self.options[0] + " "
        m = _LAST.search(line)
        word = m.group(1) if m else ""
        stem = line[: len(line) - len(word)]
        if not word:
            self.reset()
            return line
        low = word.lower()
        first_word = not stem.strip()
        pool: list[str] = []
        if first_word:
            pool += [f"{o}," for o in officers]
        pool += names + orders + vocabulary()
        seen: set[str] = set()
        opts = []
        for w in pool:
            if w.lower().startswith(low) and w.lower() != low and w.lower() not in seen:
                seen.add(w.lower())
                opts.append(w)
        self.stem, self.typed = stem, word
        if not opts:
            self.reset()
            return line
        if len(opts) == 1:
            self.reset()
            return stem + opts[0] + " "
        common = _common_prefix([o.lower() for o in opts])
        self.options = opts[:8]
        self.index = -1
        if len(common) > len(low):
            # extend to what they share, in the case of the first option
            return stem + opts[0][: len(common)]
        return line         # several, sharing nothing more: shown above the console; Tab again takes the first


def _common_prefix(words: list[str]) -> str:
    if not words:
        return ""
    p = words[0]
    for w in words[1:]:
        while not w.startswith(p):
            p = p[:-1]
    return p


__all__ = ["Completer", "vocabulary"]
