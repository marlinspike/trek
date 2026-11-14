"""The status displays: status, damage, banks, tubes, launchers, shields, fleet, chart, range, scan and the computer."""

from __future__ import annotations

from ...sim.commands import Scan, SetShields
from .. import reports
from ..tokens import ParseError, Tokens
from ..vocab import FILLER, is_num, match_word
from .base import ParserBase, ParseResult


class StatusVerbs(ParserBase):
    def _v_status(self, tok: Tokens, res: ParseResult) -> None:
        what = {"damage": ("damage", "ship"), "banks": ("banks", "phasers", "bank"), "tubes": ("tubes", "torpedoes", "tube"),
                "launchers": ("launchers", "launcher"), "probes": ("probes", "probe"), "shields": ("shields", "shield"),
                "fleet": ("fleet", "allies"), "report": ("report",), "group": ("group", "groups")}
        t = tok.next()
        k = match_word(t, what) if t else "damage"
        if k is None:
            raise ParseError("status damage, banks, tubes, launchers, probes, shields or fleet.")
        if k == "probes":
            res.display.extend(reports.probes_lines(self.obs, self.ship))
        else:
            getattr(self, f"_v_{k}")(tok, res)

    def _v_report(self, tok: Tokens, res: ParseResult) -> None:
        res.display.extend(reports.report_lines(self.obs, self.ship))

    def _v_damage(self, tok: Tokens, res: ParseResult) -> None:
        res.display.extend(reports.damage_lines(self.obs, self.ship))

    def _v_banks(self, tok: Tokens, res: ParseResult) -> None:
        res.display.extend(reports.banks_lines(self.obs, self.ship))

    def _v_tubes(self, tok: Tokens, res: ParseResult) -> None:
        res.display.extend(reports.tubes_lines(self.obs, self.ship))

    def _v_launchers(self, tok: Tokens, res: ParseResult) -> None:
        res.display.extend(reports.launchers_lines(self.obs, self.ship))

    def _v_shields(self, tok: Tokens, res: ParseResult) -> None:
        if tok.take_word("up", "raise", "on"):
            res.commands.append(self._cmd(SetShields, sectors=self._shield_list(tok), up=True))
        elif tok.take_word("down", "lower", "drop", "off"):
            res.commands.append(self._cmd(SetShields, sectors=self._shield_list(tok), up=False))
        else:
            res.display.extend(reports.shields_lines(self.obs, self.ship))

    def _v_fleet(self, tok: Tokens, res: ParseResult) -> None:
        tok.rest()  # Begin accepts (and ignores) display options here
        res.display.extend(reports.fleet_lines(self.obs, self.ship.id))

    def _v_group(self, tok: Tokens, res: ParseResult) -> None:
        res.display.extend(reports.group_lines(self.obs))

    def _v_chart(self, tok: Tokens, res: ParseResult) -> None:
        opts: dict[str, object] = {}
        word = tok.peek()  # "on" and "by" are filler elsewhere, so look at the raw token
        if word is None:
            opts["show"] = True
        elif word == "on":
            tok.next()
            opts["auto"] = True
        elif tok.is_word("off"):
            tok.next()
            opts["auto"] = False
        elif tok.is_word("all"):
            tok.next()
            opts["all"] = True
        elif word == "by":
            tok.next()
            sort = match_word(tok.next() or "", {"name": ("name",), "distance": ("distance", "range"), "nation": ("nation", "side")})
            if sort is None:
                raise ParseError("chart by name, distance or nation.")
            opts["sort"] = sort
        else:
            tok.take_word("from")
            sid = self.resolve_ship(tok)
            assert sid is not None
            if tok.peek() == "on":
                tok.next()
                opts["include"] = sid
            elif tok.is_word("off"):
                tok.next()
                opts["exclude"] = sid
            else:
                opts["origin"] = sid
        res.actions.append(("chart", opts))

    def _v_range(self, tok: Tokens, res: ParseResult) -> None:
        """Begin's `range <r>` / `display <r>` / `scan <r>`: set the position display range; bare `range` reports it."""
        if tok.peek() in ("in", "out"):            # [E] 'zoom in', 'zoom out': halve or double the range shown
            res.actions.append(("range", tok.next()))
            return
        v = tok.opt_number()
        if v is not None and not (200 <= v <= 500000):
            raise ParseError("Display range must be between 200 and 500,000 units.")
        res.actions.append(("range", v))

    def _v_scan(self, tok: Tokens, res: ParseResult) -> None:
        tok.take_word("range")
        if is_num(tok.peek()) or (tok.peek() in FILLER and is_num(tok.peek(1))):
            self._v_range(tok, res)
            return
        if tok.take_word("ship"):
            pass
        target = self.resolve_ship(tok, allow_none=True) or self.ship.target
        if target is None:
            raise ParseError("Scan which ship (or 'scan <range>')?")
        own = self.obs.own(target)
        if own is not None:
            res.display.extend(reports.damage_lines(self.obs, own))
            return
        c = self.obs.contact(target)
        if c is not None and c.scan is not None:
            res.display.extend(reports.scan_lines(self.obs, c, self.ship))
        res.commands.append(self._cmd(Scan, target=target))

    def _v_computer(self, tok: Tokens, res: ParseResult) -> None:
        res.display.extend(reports.library_lines(self.obs.content, tok.rest()))
