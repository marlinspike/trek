"""Orders to allies: `tell <ally> ...`, `tell all ...`."""

from __future__ import annotations

from ...sim.allies import ORDER_WORDS, SHIP_ORDERS, AllyStanding
from ...sim.commands import AllyOrder
from .. import reports
from ..plain import ally_words
from ..tokens import ParseError, Tokens
from ..vocab import candidates, match_word
from .base import FLEET_WORDS, ParserBase, ParseResult


class AllyVerbs(ParserBase):
    def _ally_targets(self, tok: Tokens) -> list[int]:
        tok.skip_filler()
        t = tok.peek()
        if t in FLEET_WORDS and not any(n == t for n, _ in self._ship_table()):
            tok.next()                       # `tell all attack wraith`: every ship of ours under command [E]
            tok.take_word("ships", "of", "our", "us", "units", "hands")
            members = [s.id for s in self.obs.own_ships() if s.id != self.ship.id and s.alive]
            if not members:
                raise ParseError("We have no other ships to give orders to.")
            return members
        if t is not None and t.isdigit():
            g = int(t)
            members = [s.id for s in self.obs.own_ships()
                       if s.id != self.ship.id and (st := self.obs.ally_order(s.id)) is not None and st.group == g]
            tok.next()
            if not members:
                raise ParseError(f"Group {g} has no ships. Use 'tell <ally> join {g}'.")
            return members
        sid = self.resolve_ship(tok)
        assert sid is not None
        if self.obs.own(sid) is None:
            raise ParseError(f"{self._ship_name(sid)} is not under your command.")
        if sid == self.ship.id:
            raise ParseError("Give your own ship orders directly.")
        return [sid]

    def _v_tell(self, tok: Tokens, res: ParseResult) -> None:
        allies = self._ally_targets(tok)
        said = " ".join(tok.toks[tok.i:])
        meant = ally_words(said)             # "tell the Yorktown to fall back": run [E]
        if meant != said:
            tok.toks, tok.i = Tokens(meant).toks, 0
        tok.skip_filler()
        word = tok.next()
        if word is None:
            raise ParseError("Tell them what? e.g. 'tell <ally> attack <ship>'.")
        # two-word forms: hold fire / hold course / open fire / cease fire
        if word in ("hold", "cease") and tok.is_word("course"):
            tok.next()
            order = "course"
        else:
            order = match_word(word, ORDER_WORDS) or ""
            if not order:
                cands = candidates(word, ORDER_WORDS)
                if len(cands) <= 1:
                    raise ParseError(f"Unknown order '{word}'. Try 'help'.")
                order = self._settle(word, cands, tok, lambda o, t, r: self._tell_order(allies, o, t, r))
            if order in ("hold", "open"):
                tok.take_word("fire")
        self._tell_order(allies, order, tok, res)

    def _tell_order(self, allies: list[int], order: str, tok: Tokens, res: ParseResult) -> None:
        """The rest of `tell <ally> <order> ...`: the order's ship, range or destination."""
        target = None
        value = None
        dest = None
        if order == "report":
            for a in allies:
                ally = self.obs.own(a)
                if ally is not None:
                    res.display.extend(reports.report_lines(self.obs, ally, self.obs.ally_order(a) or AllyStanding()))
            return
        if order in SHIP_ORDERS:
            target = self.resolve_ship(tok)
        if order in ("escort", "approach", "course", "join", "board"):
            tok.take_word("at", "range", "distance", "with")
            value = tok.opt_number()
        if order == "tow":
            tok.take_word("to")
            dest = self.resolve_ship(tok)
        for a in allies:
            res.commands.append(self._cmd(AllyOrder, ally=a, order=order, target=target, value=value, destination=dest))
