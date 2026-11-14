"""Hails [E]: hailing an enemy, the away team, and prisoners."""

from __future__ import annotations

import difflib
import re

from ...sim.away import TASKS, task_from_words
from ...sim.commands import ShuttleOrder
from .. import reports
from ..tokens import ParseError, Tokens
from .base import _HAIL_ALL, _HAIL_SPEECH, AWAY_CALLS, SHUTTLE_CALLS, ParserBase, ParseResult, _after_tokens


class CommsVerbs(ParserBase):
    def _away_op(self) -> object | None:
        return next(iter(self.obs.away_ops()), None) if self.ship is not None else None

    def _hail_away(self, words: str, res: ParseResult) -> None:
        """The captain on the comm to the away team: come home, a new task, or (no words) how it is going."""
        low = words.lower()
        if re.search(r"\b(recall|come (back|home)|return|get out|abort|back to the ship|home|withdraw|break off|"
                     r"pull out|beam out)\b", low):
            res.commands.append(self._cmd(ShuttleOrder, order="recall"))
            return
        task = next((t for t in TASKS if re.search(rf"\b{t}\b", low)), None) or task_from_words(low)
        if task is not None:
            res.commands.append(self._cmd(ShuttleOrder, order="task", task=task))
            return
        if low.strip():
            raise ParseError("The away team can come home ('recall') or take a new task: "
                             f"{', '.join(TASKS)}.")
        res.display.extend(reports.away_lines(self.obs, self.ship))

    def _v_hail(self, tok: Tokens, res: ParseResult) -> None:
        """`hail [<ship>|all] [words]` [E]: speak to an enemy captain; with no ship named, the current target."""
        rest_raw = _after_tokens(tok.raw, tok.i)            # the captain's own words, commas and all
        rest = rest_raw.replace(":", " ")                    # same length: offsets still line up
        tok.rest()
        sub = Tokens(rest)
        while sub.is_word("frequencies", "frequency", "channel", "to", "with", "the", "open"):
            sub.next()
        sid: int | None = None
        everyone = False
        if sub.peek() in _HAIL_ALL:
            sub.next()
            everyone = True
        elif sub.peek() in AWAY_CALLS and self._away_op() is not None:
            sub.next()                                       # the shuttle's name, or Worf's: the words follow it
            self._hail_away(" ".join(_after_tokens(rest, sub.i).split()), res)
            return
        elif (craft := sub.peek()) is not None and craft in SHUTTLE_CALLS:
            raise ParseError(f"The {craft.title()} is in the shuttle bay, Captain: no away team is out. "
                             "'away <Borg ship> <task>' sends one.")
        else:
            try:
                sid = self.resolve_ship(sub, allow_none=True)
            except ParseError:
                sid = None
            own = self.obs.own(sid) if sid is not None else None
            if own is not None and own.cls.craft and self._away_op() is not None:
                self._hail_away(" ".join(_after_tokens(rest, sub.i).split()), res)
                return
            if sid is not None and own is not None and self.obs.contact(sid) is None:
                raise ParseError(f"{self._ship_name(sid)} is one of ours: use 'tell' to give her orders.")
            if sid is None:
                self._hail_misnamed(sub)
        words = " ".join(_after_tokens(rest, sub.i).split()).strip(" :,-\"'")
        if sid is None and not everyone:
            if self.ship.target is None:
                raise ParseError("Hail whom? Name a ship ('hail gr'oth ...'), 'hail all', or target one first.")
            sid = self.ship.target
        res.actions.append(("hail", (None if everyone else sid, words)))

    def _hail_misnamed(self, sub: Tokens) -> None:
        """'hail gargoyle' or 'hail thm': a word that reads as a ship that isn't there, not as the captain's words.
        Caught when it is close to a ship's name or to 'them', or is the only word and not one a captain would say."""
        sub.skip_filler()
        first = sub.peek()
        if first is None or first.startswith("#"):
            return
        names = sorted({n for n, _ in self._ship_table()} | {n.split()[0] for n, _ in self._ship_table()})
        near = difflib.get_close_matches(first, names + list(_HAIL_ALL), n=1, cutoff=0.75)
        only = sub.peek(1) is None and first not in _HAIL_SPEECH
        if near or only:
            hint = ""
            if near and near[0] in _HAIL_ALL:
                hint = " Did you mean 'hail them'?"
            elif near:
                hint = f" Did you mean the {near[0].title()}?"
            raise ParseError(f"No ship named '{first}' on sensors.{hint}")

    def _v_prisoners(self, tok: Tokens, res: ParseResult) -> None:
        """`prisoners` [E]: the crews of surrendered ships we hold."""
        tok.rest()
        res.actions.append(("prisoners", None))
