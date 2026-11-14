"""The helm's words: course and warp, stopping, holding and opening fire, pursuit and evasion."""

from __future__ import annotations

from ...sim.commands import CeaseFire, DelegateStation, Evasive, OpenFire, Pursue, SetHelm, StandDown
from ..tokens import ParseError, Tokens
from ..vocab import FILLER, HAVE_WORDS, STATION_WORDS
from .base import KEEP_MIN, ParserBase, ParseResult


class HelmVerbs(ParserBase):
    def _v_helm(self, tok: Tokens, res: ParseResult) -> None:
        tok.take_word("course")
        tok.skip_filler()
        turn = 180.0 if tok.take_word("about", "around", "reverse") else None
        if turn is None and tok.peek() in ("port", "left", "starboard", "right"):
            side = -1.0 if tok.next() in ("port", "left") else 1.0      # [E] 'hard to port', 'turn right 45'
            turn = side * (tok.opt_number() or 90.0)
        if turn is not None:
            course_now = self.ship.course
            res.commands.append(self._cmd(SetHelm, course=(course_now + turn) % 360, warp=None))
            return
        course = tok.opt_number()
        warp = None
        if tok.take_word("warp", "w", "speed"):
            warp = tok.number("warp")
        elif course is not None:
            warp = tok.opt_number()
        if course is None and warp is None:
            raise ParseError("helm needs a course and/or warp, e.g. 'helm 90 warp 4'.")
        if course is not None and not -360 <= course <= 360:
            raise ParseError("Course must be between -360 and +360 degrees.")
        res.commands.append(self._cmd(SetHelm, course=course % 360 if course is not None else None, warp=warp))

    def _v_warp(self, tok: Tokens, res: ParseResult) -> None:
        tok.skip_filler()
        if tok.take_word("max", "maximum", "full", "flank"):
            res.commands.append(self._cmd(SetHelm, warp=self.ship.cls.max_warp))     # [E] 'full speed', 'maximum warp'
            return
        step = 1 if tok.take_word("up", "faster", "more") else -1 if tok.take_word("down", "slower", "less") else 0
        if step:                                    # [E] 'speed up', 'slow down': two warp at a time
            now = self.ship.desired_warp
            res.commands.append(self._cmd(SetHelm, warp=max(0.0, min(self.ship.cls.max_warp, now + 2.0 * step))))
            return
        res.commands.append(self._cmd(SetHelm, warp=tok.number("warp")))

    def _v_stop(self, tok: Tokens, res: ParseResult) -> None:
        if tok.take_word("firing", "fire", "shooting", "weapons"):
            res.commands.append(self._cmd(CeaseFire))     # "stop firing": cease fire, not all stop [E]
            return
        if tok.take_word("everything", "everyone", "everybody", "all"):
            self._v_standdown(tok, res)                   # "stop everything": the officers stand down [E]
            return
        res.commands.append(self._cmd(SetHelm, warp=0.0))

    def _v_cease(self, tok: Tokens, res: ParseResult) -> None:
        """`cease fire`: every weapon stops, officers' objectives end, until you fire or say open fire."""
        tok.take_word("fire", "firing")
        res.commands.append(self._cmd(CeaseFire))

    def _v_hold(self, tok: Tokens, res: ParseResult) -> None:
        if not tok.take_word("fire", "firing") and tok.peek() is not None:
            raise ParseError("Hold what? 'hold fire' stops every weapon.")
        res.commands.append(self._cmd(CeaseFire))

    def _v_standdown(self, tok: Tokens, res: ParseResult) -> None:
        """`stand down [all|everyone]` [E]: cease fire, every objective ends, every station and the bridge
        come back to the captain, and the helm steadies."""
        tok.rest()
        res.commands.append(self._cmd(StandDown))

    def _v_ihave(self, tok: Tokens, res: ParseResult) -> None:
        """`I have nav` / `I have fire|weapons|phasers|torps` / `I have the conn` [E]: the captain takes that
        station (or every station) back from its officer, and whatever they were working on ends."""
        tok.next()
        tok.take_word("got")
        words = [w.strip(".!'\"") for w in tok.rest()
                 if w not in FILLER and w not in ("got", "control", "of", "now", "here", "over", "back")]
        if not words:
            raise ParseError("You have what? e.g. 'I have nav', 'I have weapons', 'I have the conn'.")
        stations: list[str] = []
        for w in words:
            st = next((k for k, spellings in HAVE_WORDS.items() if w in spellings), None)
            if st is None:
                raise ParseError(f"I have what? '{w}' is no station. Try nav, weapons, phasers, torps, shields, "
                                 "sensors or the conn.")
            stations.extend(STATION_WORDS if st == "all" else [st])
        for st in dict.fromkeys(stations):
            res.commands.append(self._cmd(DelegateStation, station=st, on=False))

    def _v_open(self, tok: Tokens, res: ParseResult) -> None:
        tok.skip_filler()
        if tok.is_word("channel", "hailing", "frequencies", "comms", "communications"):
            while tok.is_word("channel", "hailing", "frequencies", "frequency", "comms", "communications", "a", "to",
                              "with", "the"):
                tok.next()
            self._v_hail(tok, res)        # "open a channel to the Gr'oth", "open hailing frequencies" [E]
            return
        if not tok.take_word("fire") and tok.peek() is not None:
            raise ParseError("Open what? 'open fire' lifts a cease fire.")
        res.commands.append(self._cmd(OpenFire))

    def _pursue(self, tok: Tokens, res: ParseResult, elude: bool) -> None:
        target = self.resolve_ship(tok)
        warp: float | None = None
        keep: float | None = None
        while not tok.done():
            ranged = tok.peek() == "at"          # 'at' is filler elsewhere; here it names the range to hold
            if ranged:
                tok.i += 1
            if tok.take_word("warp", "w"):
                warp = tok.number("warp")
            elif tok.take_word("range", "keep"):
                keep = tok.number("range")       # [E] 'elude talon range 9000': hold her at 9,000
            else:
                n = tok.opt_number()
                if n is None:
                    break
                if ranged or n > KEEP_MIN:       # [E] 'elude talon at 9000', or a number no warp could be
                    keep = n
                else:
                    warp = n
        res.commands.append(self._cmd(Pursue, target=target, warp=warp, elude=elude, keep=keep))

    def _v_pursue(self, tok: Tokens, res: ParseResult) -> None:
        self._pursue(tok, res, False)

    def _v_elude(self, tok: Tokens, res: ParseResult) -> None:
        tok.skip_filler()
        if tok.done() or tok.is_word("torpedoes", "torps", "incoming"):
            self._v_evasive(tok, res)    # 'evade' with no ship to run from: evasive manoeuvres
            return
        self._pursue(tok, res, True)

    def _v_evasive(self, tok: Tokens, res: ParseResult) -> None:
        """evasive [manoeuvres|action] [on|off]: the helm dodges incoming torpedoes until the next navigation order."""
        off = False
        while not tok.done():
            w = tok.next() or ""
            if w in ("off", "cancel", "stop", "end", "belay"):
                off = True
        res.commands.append(self._cmd(Evasive, on=not off))
