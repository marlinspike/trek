"""The bridge officers (remake extension): delegation, the conn, standing objectives, bait, the pulse, the boost and the crew."""

from __future__ import annotations

import re

from ...sim.commands import (
    AddressCrew, DeflectorPulse, DelegateStation, EndObjective, EngineBoost, FireBait, SetObjective,
)
from .. import reports
from ..tokens import ParseError, Tokens
from ..vocab import match_word, system_word
from .base import ParserBase, ParseResult, _stations


class OfficerVerbs(ParserBase):
    def _v_address(self, tok: Tokens, res: ParseResult) -> None:
        """address [crew|ship] <words>: the captain speaks to the crew; morale rises."""
        tok.take_word("crew", "ship", "the")
        tok.take_word("crew")
        words = tok.raw.split(None, 1)[1] if len(tok.raw.split(None, 1)) > 1 else ""
        for lead in ("the crew", "crew", "ship", "the ship"):
            if words.lower().startswith(lead):
                words = words[len(lead):]
                break
        tok.rest()
        res.commands.append(self._cmd(AddressCrew, text=words.strip(" :,-\"'")))

    def _v_morale(self, tok: Tokens, res: ParseResult) -> None:
        tok.rest()
        res.display.extend(reports.morale_lines(self.obs))

    def _v_delegate(self, tok: Tokens, res: ParseResult) -> None:
        for st in _stations(tok):
            res.commands.append(self._cmd(DelegateStation, station=st, on=True))

    def _v_assume(self, tok: Tokens, res: ParseResult) -> None:
        for st in _stations(tok):
            res.commands.append(self._cmd(DelegateStation, station=st, on=False))

    def _enemy_targets(self, words: list[str]) -> tuple[int, ...]:
        """Enemy ships named in free text: names, '#id', races ('the Klingons') or 'all'/'them'.
        Nothing named: the current target, or every enemy in sight."""
        hostile = [c for c in self.obs.hostile_contacts() if c.id not in self.obs.gone()]
        targets: list[int] = []
        table = self._ship_table()
        i = 0
        while i < len(words):
            w = words[i]
            hit = None
            for span in (3, 2, 1):
                phrase = " ".join(words[i:i + span])
                if len(words[i:i + span]) < span or len(phrase) < 3:
                    continue
                exact = [sid for n, sid in table if n == phrase]
                found = exact or list({sid for n, sid in table if n.startswith(phrase)})
                if len(found) == 1 and found[0] in {c.id for c in hostile}:
                    hit, i = found[0], i + span
                    break
            if hit is not None:
                targets.append(hit)
                continue
            if w.startswith("#") and w[1:].isdigit() and int(w[1:]) in {c.id for c in hostile}:
                targets.append(int(w[1:]))
            elif w.rstrip("s") in self._FACTIONS or w in self._FACTIONS:
                fac = self._FACTIONS.get(w, self._FACTIONS.get(w.rstrip("s")))
                targets.extend(c.id for c in hostile if c.cls is not None and c.cls.faction == fac)
            elif w in self._EVERYONE:
                targets.extend(c.id for c in hostile)
            elif w == "other" and len(hostile) > 1:      # "the other ship's shields": not the one we have targeted
                targets.extend(c.id for c in hostile if c.id != self.ship.target)
            i += 1
        if not targets:
            if self.ship.target is not None and self.ship.target in {c.id for c in hostile}:
                targets = [self.ship.target]
            else:
                targets = [c.id for c in hostile]
        if not targets:
            raise ParseError("There's no enemy in sight.")
        return tuple(dict.fromkeys(targets))

    def _v_destroy(self, tok: Tokens, res: ParseResult) -> None:
        """`destroy <ships|all|klingons>`: an officer's standing order to take the ships out [E]."""
        words = [w.strip(".!?;'\"").removesuffix("'s").removesuffix("s'") for w in tok.rest()]
        words = [w for w in words if w]
        if any(w in ("off", "cancel", "stop", "belay", "abort") for w in words):
            res.commands.append(self._cmd(EndObjective, group="hull", outcome="cancelled"))
            return
        res.commands.append(self._cmd(SetObjective, goal="destroy", group="hull", targets=self._enemy_targets(words)))

    def _v_capture(self, tok: Tokens, res: ParseResult) -> None:
        """`capture <ship>`: open a shield, thin her crew through the gap, board her and keep her [E]."""
        words = [w.strip(".!?;'\"").removesuffix("'s").removesuffix("s'") for w in tok.rest()]
        words = [w for w in words if w]
        if any(w in ("off", "cancel", "stop", "belay", "abort") for w in words):
            res.commands.append(self._cmd(EndObjective, group="crew", outcome="cancelled"))
            return
        res.commands.append(self._cmd(SetObjective, goal="capture", group="crew", targets=self._enemy_targets(words)))

    def _v_bait(self, tok: Tokens, res: ParseResult) -> None:
        """`bait [ship]`: one torpedo to draw their point defense, the rest a cycle later [E]."""
        tok.take_word("at")
        sid = self.resolve_ship(tok, allow_none=True)
        res.commands.append(self._cmd(FireBait, target=sid if sid is not None else self.ship.target))

    def _disable_enemy(self, tok: Tokens, res: ParseResult) -> None:
        """`disable <shields|phasers|torpedoes|weapons|engines|sensors> [on] <ships|all|klingons>` [E].

        Words can come in any order ("disable the Klingons' shields"); `disable off` cancels.
        With no ship named: the current target, or every enemy if there is none.
        """
        verb = (tok.toks[tok.i - 1] if tok.i > 0 else "disable")
        words = [w.strip(".!?;'\"").removesuffix("'s").removesuffix("s'") for w in tok.rest()]
        words = [w for w in words if w]
        if any(w in ("off", "cancel", "stop", "belay", "abort", "nevermind") for w in words):
            res.commands.append(self._cmd(EndObjective, outcome="cancelled"))
            return
        # "disable their shields and engines": each system named, in the order given
        groups = list(dict.fromkeys(g for w in words if (g := system_word(w)) is not None))
        if not groups and verb.startswith("disarm"):
            groups = ["weapons"]
        if not groups:
            raise ParseError("Disable what? shields, phasers, torpedoes, weapons, engines, sensors or cloak.")
        if "weapons" in groups:
            groups = [g for g in groups if g not in ("phasers", "torpedoes")]   # 'weapons' covers both
        targets = self._enemy_targets([w for w in words if system_word(w) is None])
        for group in groups:
            res.commands.append(self._cmd(SetObjective, goal="disable", group=group, targets=targets))

    def _v_pulse(self, tok: Tokens, res: ParseResult) -> None:
        """`pulse`: sweep the cone ahead with the deflector's tachyon pulse [E]."""
        tok.rest()
        res.commands.append(self._cmd(DeflectorPulse))

    def _v_boost(self, tok: Tokens, res: ParseResult) -> None:
        """`boost [engines] [on|off]`: an engineering team nurses the drives so they run hot for longer, at the cost
        of slower repairs everywhere else; `boost off` sends the team back early [E]."""
        tok.take_word("the")
        tok.take_word("engines", "engine", "drives", "warp")
        off = tok.take_word("off", "stop", "end", "cancel")
        tok.take_word("on")
        res.commands.append(self._cmd(EngineBoost, on=not off))

    def _v_conn(self, tok: Tokens, res: ParseResult) -> None:
        """`conn <officer>` gives an officer the whole bridge; `conn captain` (or bare `conn`) takes it back [E]."""
        tok.take_word("to")
        words = [w for w in tok.rest() if w.lower() not in ("the",)]
        who = " ".join(words).strip().lower()
        res.actions.append(("conn", None if who in ("", "captain", "me", "back", "off", "mine", "return") else who))

    def _v_crew(self, tok: Tokens, res: ParseResult) -> None:
        w = tok.next()
        if w is not None and match_word(w, {"chatter": ("chatter", "talk", "quiet")}) == "chatter":
            on = not (w.startswith("q") or tok.take_word("off"))
            tok.take_word("on")
            res.actions.append(("crew", ("chatter", on)))
            return
        res.actions.append(("crew", None))

    def _v_ask(self, tok: Tokens, res: ParseResult) -> None:
        raw = tok.raw.strip().split(None, 1)
        rest = raw[1] if len(raw) > 1 else ""
        m = re.match(r"^\s*([^\s,:]+(?:\s+of\s+nine)?)\s*[,:]?\s*(.*)$", rest, re.I)
        if not m:
            raise ParseError("Ask whom? e.g. 'ask worf status' or 'spock, what do you recommend?'")
        tok.rest()
        res.actions.append(("ask", (m.group(1), m.group(2))))
