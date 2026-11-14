"""The Borg [E]: remodulation, hive duties, repelling boarders, the away team, sweep, seeker and strike."""

from __future__ import annotations

import re

from ...sim.away import TASKS, task_from_words
from ...sim.commands import (
    AwayTeam, Countermeasure, EndObjective, FireSeeker, Remodulate, SetDuty, SetObjective, ShuttleOrder, Sweep,
)
from ..tokens import ParseError, Tokens
from ..vocab import DISABLE_WORDS, system_word
from .base import _STRIKE_FILLER, _STRIKE_HULL, DUTY_WORDS, ParserBase, ParseResult


class BorgVerbs(ParserBase):
    def _v_remodulate(self, tok: Tokens, res: ParseResult) -> None:
        """`remodulate`: the phasers on a new frequency, which the hive must learn from nothing."""
        tok.rest()
        res.commands.append(self._cmd(Remodulate, by=""))

    def _v_duty(self, tok: Tokens, res: ParseResult) -> None:
        """`tune shields` / `duty harmonics` / `duty phasers` / `duty off`: the science officer's hive work.
        Shields: tune our shield harmonics against their beams (and their transporters). Harmonics: keep scanning
        their ships for the weak point and their shield harmonics. Phasers: remodulate before they learn them."""
        words = [w.strip(".,!?") for w in tok.rest()]
        duty = next((d for w in words for d, keys in DUTY_WORDS.items() if w in keys), None)
        if duty is None:
            if any(w in ("off", "stop", "none", "nothing", "belay") for w in words):
                duty = ""
            elif not words:
                duty = "shields"         # bare "tune": the shields, the thing a captain most often wants tuned
            else:
                raise ParseError("Which duty? 'tune shields', 'duty harmonics', 'duty phasers' or 'duty off'.")
        who = next((w for w in words if w in ("seven", "spock")), "")
        res.commands.append(self._cmd(SetDuty, duty=duty, by=who))

    def _v_repel(self, tok: Tokens, res: ParseResult) -> None:
        """`repel security` (security teams to the decks the drones hold) or `repel seal` (seal and vent them)."""
        first = tok.toks[tok.i - 1] if tok.i > 0 else ""
        words = [w.strip(".,!?") for w in tok.rest()]
        if first.startswith(("seal", "vent")) or any(w.startswith(("seal", "vent")) for w in words):
            kind = "seal"
        else:
            kind = "security"
        res.commands.append(self._cmd(Countermeasure, kind=kind))

    def _v_away(self, tok: Tokens, res: ParseResult) -> None:
        """`away <ship> <task> [with seven]` [E]: Worf (and Seven) take a shuttle across to a Borg ship, or beam
        over to a dormant one. Tasks: relay, harmonics, weapons, charges, survey, rescue. `away recall` (or
        `recall`) calls them home; `away <task>` gives the team out there a new one."""
        rest = " ".join(tok.toks[tok.i:])
        if self._away_op() is not None:
            tok.rest()
            self._hail_away(rest, res)
            return
        target = self.resolve_ship(tok, allow_none=True)
        words = " ".join(w.strip(".,!?") for w in tok.rest())
        if target is None:
            hives = [c for c in self.obs.hostile_contacts() if c.visible and self.obs.is_hive(c.id)]
            t = self.ship.target if self.ship.target is not None and self.obs.is_hive(self.ship.target) else None
            target = t if t is not None else (min(hives, key=lambda c: c.distance_to(self.ship.x, self.ship.y)).id
                                              if hives else None)
        if target is None:
            raise ParseError("Away to which ship? 'away <Borg ship> <task>'.")
        # no task named: put out her relay if Seven has found it, else look round inside for it
        task = (next((t for t in TASKS if re.search(rf"\b{t}\b", words)), None) or task_from_words(words)
                or ("relay" if self.obs.weak_point(target) else "survey"))
        members = self._away_members(words, task)
        dormant = self.obs.dormant(target) > 0
        beam = "beam" in words or "transport" in words or (dormant and "shuttle" not in words)
        res.commands.append(self._cmd(AwayTeam, target=target, task=task, members=members, by_shuttle=not beam))

    def _away_members(self, words: str, task: str) -> tuple[str, ...]:
        gone = self.ship.away | self.ship.wounded
        named = [n for n in ("worf", "seven", "sulu", "spock") if re.search(rf"\b{n}\b", words) and n not in gone]
        lead: str = next((n for n in ("worf", "sulu") if n in named), None) or \
            next((n for n in ("worf", "sulu") if n not in gone), "worf")
        team = [lead] + [n for n in named if n != lead]
        if task == "harmonics" and "seven" not in team:
            team.append("seven")          # only Seven knows how the Collective keeps them
        return tuple(dict.fromkeys(team))

    def _v_sweep(self, tok: Tokens, res: ParseResult) -> None:
        """`sweep [<ship>]`: science sweeps for plasma trails from damaged warp drives, cloaked ships' too [E].
        `sweep strike ...` (or `sweep and strike ...`) is the whole kill chain: see `strike`."""
        if tok.peek() in ("strike", "and", "&", "n", "kill") and (tok.peek() != "and" or tok.peek(1) in ("strike", "kill")):
            self._v_strike(tok, res)
            return
        tok.take_word("for", "trails", "trail", "exhaust", "plasma")
        tok.take_word("from", "of")
        sid = self.resolve_ship(tok, allow_none=True)
        tok.rest()
        res.commands.append(self._cmd(Sweep, target=sid))

    def _v_seeker(self, tok: Tokens, res: ParseResult) -> None:
        """`seeker [<ship>]`: fire a plasma-seeker down a ship's trail; with no ship, the nearest trail [E]."""
        tok.take_word("at", "on", "after", "down")
        sid = self.resolve_ship(tok, allow_none=True)
        tok.rest()
        trails = self.obs.plasma()
        if sid is None:
            if not trails:
                raise ParseError("No plasma trail on sensors. Try 'sweep'.")
            sid = min(trails, key=lambda k: min((p[0] - self.ship.x) ** 2 + (p[1] - self.ship.y) ** 2
                                                  for p in trails[k]))
        res.commands.append(self._cmd(FireSeeker, target=sid))

    def _v_strike(self, tok: Tokens, res: ParseResult) -> None:
        """`strike [<ship>] [<system>]` (also `sweep strike ...`): sweep and strike, the kill chain for a cloaked ship
        that leaks plasma [E]. The science officer sweeps for her trail, fires a plasma-seeker down it, and the moment
        it hits puts an aimed salvo into the system named (shields, phasers, torpedoes, weapons, warp/engines,
        sensors, cloak) or, with none named, her hull. With no ship named: the nearest ship whose trail we can see,
        else our target, else the nearest one that has cloaked. `strike off` calls it off.

        Words come in any order, and systems shorten like anything else: `str tal sh` is the Talon's shields."""
        from ...sim.objectives import STRIKE_DEFAULT

        words = [w.strip(".!?;,'\"").removesuffix("'s").removesuffix("s'") for w in tok.rest()]
        words = [w for w in words if w]
        if any(w in ("off", "cancel", "stop", "belay", "abort") for w in words):
            end = [o.group for o in self.ship.objectives if o.goal == "strike"]
            if not end:
                raise ParseError("No sweep and strike to call off.")
            for g in dict.fromkeys(end):
                res.commands.append(self._cmd(EndObjective, group=g, outcome="cancelled"))
            return
        group = None
        ship_words: list[str] = []
        names = [n for n, _ in self._ship_table()]
        for w in words:
            g = self._strike_system(w, names)
            if g is not None:
                group = group or g
            elif w in _STRIKE_HULL:
                group = group or "hull"
            elif w not in _STRIKE_FILLER:
                ship_words.append(w)
        sid = self._strike_ship(ship_words)
        res.commands.append(self._cmd(SetObjective, goal="strike", group=group or STRIKE_DEFAULT, targets=(sid,)))

    @staticmethod
    def _strike_system(word: str, names: list[str]) -> str | None:
        """The system a word in a strike order names: a whole word ("warp", "sheilds"), or a short prefix of one
        that is no ship's name ("sh", "eng") [E]."""
        from ...sim.objectives import STRIKE_GROUPS

        g = system_word(word)
        if g is not None:
            return g
        if len(word) < 2 or any(n.startswith(word) for n in names):
            return None
        hits = {grp for w, grp in DISABLE_WORDS.items() if w.startswith(word)}
        hits |= {"hull"} if "hull".startswith(word) else set()
        return hits.pop() if len(hits) == 1 and next(iter(hits)) in STRIKE_GROUPS else None

    def _strike_ship(self, words: list[str]) -> int:
        """The ship to sweep and strike: one named, else the nearest whose trail we can see, else our target, else
        the nearest that has cloaked."""
        if words:
            return self._lost_ship(words)
        hostile = [c for c in self.obs.hostile_contacts() if c.id not in self.obs.gone()]
        trails = self.obs.plasma()
        venting = [c for c in hostile if c.exhaust or c.id in trails]
        if venting:
            return min(venting, key=lambda c: c.distance_to(self.ship.x, self.ship.y)).id
        if self.ship.target is not None and self.ship.target in {c.id for c in hostile}:
            return self.ship.target
        try:
            return self._lost_ship([])
        except ParseError:
            raise ParseError("Strike whom? No plasma trail on sensors and nothing has cloaked. "
                             "'strike <ship> [shields|weapons|warp|...]'.") from None

    def _v_recall(self, tok: Tokens, res: ParseResult) -> None:
        tok.rest()
        res.commands.append(self._cmd(ShuttleOrder, order="recall"))
