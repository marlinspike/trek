"""The ship's systems: shields, alert, repairs, tractor, docking, the cloak, the hunt for a lost ship, self-destruct, surrender, transporters and boarding."""

from __future__ import annotations

from ...core.angles import bearing
from ...sim.commands import (
    ControlProbe, Dock, EndObjective, FireSpecialRound, ManageRepairs, ReinforceShield, SelfDestruct, SetCloak,
    SetObjective, SetRepairPriority, SetShields, StartProject, Surrender, Tractor, Transport,
)
from ..tokens import ParseError, Tokens
from ..vocab import REPAIR_KINDS, is_num, match_word
from .base import _HUNT_FILLER, NOTHING_LOST, SHIELD_SIDES, ParserBase, ParseResult


class SystemVerbs(ParserBase):
    def _shield_list(self, tok: Tokens) -> tuple[int, ...] | None:
        all_given = tok.take_word("all")
        tok.take_word("shields", "shield")
        mounts = tok.mount_list()
        if tok.take_word("all"):
            all_given = True
        tok.take_word("shields", "shield")
        return None if all_given else mounts

    def _v_raise(self, tok: Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(SetShields, sectors=self._shield_list(tok), up=True))

    def _v_lower(self, tok: Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(SetShields, sectors=self._shield_list(tok), up=False))

    def _v_reinforce(self, tok: Tokens, res: ParseResult) -> None:
        """`reinforce <n>`, `reinforce off`; also `reinforce forward|aft|port|starboard` and `reinforce [toward] <ship>`
        (bare `reinforce`: the shield facing our target, or the nearest enemy) [E]."""
        tok.take_word("shield")
        if tok.take_word("off", "none", "clear"):
            res.commands.append(self._cmd(ReinforceShield, sector=None))
            return
        if not self.ship.shields:
            raise ParseError(f"The {self.ship.cls.name} has no shields.")
        side = tok.peek()
        if side is not None and side in SHIELD_SIDES:
            tok.next()
            tok.take_word("shield", "shields")
            sh = self.ship.shield_for_bearing(SHIELD_SIDES[side])
            res.commands.append(self._cmd(ReinforceShield, sector=sh.index if sh is not None else 0))
            return
        if tok.done() or not is_num(tok.peek() or ""):
            tok.take_word("toward", "towards", "facing", "against", "the")
            sid = self.resolve_ship(tok) if not tok.done() else (self.ship.target or self._nearest_enemy())
            c = self.obs.contact(sid) if sid is not None else None
            if c is None:
                raise ParseError("Reinforce which shield? There is no enemy to face: give its number, 1 to "
                                 f"{len(self.ship.shields)}.")
            rel = (bearing(c.x - self.ship.x, c.y - self.ship.y) - self.ship.course) % 360.0
            sh = self.ship.shield_for_bearing(rel)
            res.commands.append(self._cmd(ReinforceShield, sector=sh.index if sh is not None else 0))
            return
        n = int(tok.number("shield"))
        if not 1 <= n <= max(1, len(self.ship.shields)):
            raise ParseError(f"Shields are numbered 1 to {len(self.ship.shields)}.")
        res.commands.append(self._cmd(ReinforceShield, sector=n - 1))

    def _v_repair(self, tok: Tokens, res: ParseResult) -> None:
        if tok.take_word("auto", "officer", "delegate"):
            # an officer directs the crews; with no name, the ship's science officer (Spock) or engineer
            res.commands.append(self._cmd(ManageRepairs, officer=" ".join(tok.rest()).strip().lower() or "auto"))
            return
        if tok.take_word("manual", "captain", "myself"):
            res.commands.append(self._cmd(ManageRepairs, officer=""))
            return
        w = tok.next() or "all"
        k = match_word(w, {k: (k,) for k in REPAIR_KINDS})
        if k is None:
            raise ParseError(f"Unknown system '{w}'.")
        res.commands.append(self._cmd(SetRepairPriority, kind=REPAIR_KINDS[k]))

    def _v_tractor(self, tok: Tokens, res: ParseResult) -> None:
        if tok.take_word("off", "release"):
            res.commands.append(self._cmd(Tractor, target=None))
        else:
            res.commands.append(self._cmd(Tractor, target=self.resolve_ship(tok)))

    def _v_release(self, tok: Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(Tractor, target=None))

    def _v_dock(self, tok: Tokens, res: ParseResult) -> None:
        if tok.take_word("off"):
            res.commands.append(self._cmd(Dock, host=None))
            return
        host = self.resolve_ship(tok)
        if tok.take_word("off"):
            res.commands.append(self._cmd(Dock, host=None))
            return
        tok.take_word("on")
        res.commands.append(self._cmd(Dock, host=host))

    def _v_undock(self, tok: Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(Dock, host=None))

    def _v_design(self, tok: Tokens, res: ParseResult) -> None:
        """`design tachyon`: Spock and Seven build a one-off special round [E]."""
        from ...sim.projects import PROJECTS

        tok.skip_filler()
        word = (tok.peek() or "").lower()
        hits = [p for p in PROJECTS if p.startswith(word)] if word else []
        if len(hits) != 1:
            raise ParseError(f"Design what? Known: {', '.join(PROJECTS)}.")
        tok.rest()
        res.commands.append(self._cmd(StartProject, project=hits[0]))

    def _v_tachyon(self, tok: Tokens, res: ParseResult) -> None:
        """`tachyon <bearing> <range>`, `tachyon <ship>` or bare `tachyon` (at the target): burst the detector there."""
        import math

        tok.take_word("fire", "at", "toward", "towards")
        tok.skip_filler()
        if is_num(tok.peek()):
            brg = tok.number("bearing")
            tok.take_word("range", "at", "distance")
            rng_ = tok.number("range")
            a = math.radians(brg)
            x, y = self.ship.x + math.sin(a) * rng_, self.ship.y + math.cos(a) * rng_
        else:
            sid = self.resolve_ship(tok, allow_none=True)
            if sid is None:
                sid = self.ship.target
            c = self.obs.contact(sid) if sid is not None else None
            if c is None:
                raise ParseError("Burst it where? 'tachyon <bearing> <range>' or 'tachyon <ship>'.")
            x, y = c.x, c.y
        res.commands.append(self._cmd(FireSpecialRound, ordnance="tachyon", x=x, y=y))

    def _v_hunt(self, tok: Tokens, res: ParseResult) -> None:
        """`hunt <ship>` (find, locate): the science officer finds a ship we have lost, most often a cloaked one,
        with the tachyon detector and the deflector. With no ship named: our target if we've lost it, else the
        nearest ship that has probably cloaked. `hunt off` calls it off [E]."""
        words = [w.strip(".!?;,'\"").removesuffix("'s") for w in tok.rest()]
        words = [w for w in words if w and w not in _HUNT_FILLER]
        if any(w in ("off", "cancel", "stop", "belay", "abort") for w in words):
            res.commands.append(self._cmd(EndObjective, group="hunt", outcome="cancelled"))
            return
        res.commands.append(self._cmd(SetObjective, goal="hunt", group="hunt", targets=(self._lost_ship(words),)))

    def _lost_ship(self, words: list[str]) -> int:
        """The ship the captain wants found: one named (a name, a prefix of one, or '#id'), else our lost target,
        else the nearest contact that has probably cloaked, else the nearest one we've lost."""
        hostile = [c for c in self.obs.hostile_contacts() if c.id not in self.obs.gone()]
        ids = {c.id for c in hostile}
        if words:
            if words[0].startswith("#") and words[0][1:].isdigit() and int(words[0][1:]) in ids:
                return int(words[0][1:])
            table = [(n, sid) for n, sid in self._ship_table() if sid in ids]
            for span in (3, 2, 1):
                phrase = " ".join(words[:span])
                if len(words) < span or len(phrase) < 2:
                    continue
                found = list({sid for n, sid in table if n == phrase}) or list({sid for n, sid in table if n.startswith(phrase)})
                if len(found) == 1:
                    return found[0]
                if len(found) > 1:
                    raise ParseError(f"'{phrase}' matches more than one ship.")
            if words[0] not in ("enemy", "romulan", "romulans", "klingon", "klingons", "cloaked", "contact"):
                raise ParseError(f"No ship named '{words[0]}' has been on our sensors.")
        lost = [c for c in hostile if not c.visible]
        if self.ship.target in {c.id for c in lost}:
            return self.ship.target  # type: ignore[return-value]
        cloaked = [c for c in lost if c.cloaked_hint] or lost
        if not cloaked:
            raise ParseError(NOTHING_LOST)
        return min(cloaked, key=lambda c: c.distance_to(self.ship.x, self.ship.y)).id

    def _v_cloak(self, tok: Tokens, res: ParseResult) -> None:
        on = not tok.take_word("off")
        tok.take_word("on")
        res.commands.append(self._cmd(SetCloak, on=on))

    def _v_decloak(self, tok: Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(SetCloak, on=False))

    def _v_destruct(self, tok: Tokens, res: ParseResult) -> None:
        tok.take_word("destruct")
        if tok.take_word("abort", "off", "cancel"):
            res.commands.append(self._cmd(SelfDestruct, cycles=None))
            return
        n = tok.opt_number()
        if n is None:
            raise ParseError("Self destruct in how many cycles? e.g. 'self destruct 10'.")
        res.commands.append(self._cmd(SelfDestruct, cycles=n))

    def _v_abort(self, tok: Tokens, res: ParseResult) -> None:
        tok.take_word("destruct")
        res.commands.append(self._cmd(SelfDestruct, cycles=None))

    def _v_surrender(self, tok: Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(Surrender))

    def _v_transport(self, tok: Tokens, res: ParseResult) -> None:
        """`beam <ally>` trades ships (manual p. 20); `beam <ship> <crew>` moves crew or a boarding party."""
        target = self.resolve_ship(tok)
        assert target is not None
        n = tok.opt_number()
        if n is None and self.obs.own(target) is not None:
            res.actions.append(("transfer", target))
            return
        if n is None:
            raise ParseError("How many crew? e.g. 'beam <ship> 20', or 'board <ship>'.")
        res.commands.append(self._cmd(Transport, target=target, count=int(n)))

    def _v_board(self, tok: Tokens, res: ParseResult) -> None:
        target = self.resolve_ship(tok)
        n = tok.opt_number()
        if n is None:
            n = self.ship.boarding_party()
        res.commands.append(self._cmd(Transport, target=target, count=int(n)))

    def _v_detonate(self, tok: Tokens, res: ParseResult) -> None:
        tok.take_word("probe", "probes")
        if tok.take_word("all") or tok.done():
            tok.take_word("probes", "probe")
            res.commands.append(self._cmd(ControlProbe, code=None, detonate=True))
        else:
            res.commands.append(self._cmd(ControlProbe, code=tok.next(), detonate=True))

    def _v_alert(self, tok: Tokens, res: ParseResult) -> None:
        """`alert red|yellow|green` [E]: the bundle of orders for that condition (config/alerts.toml)."""
        w = tok.next()
        if w in ("red", "r"):
            w = "red"
        elif w in ("yellow", "y", "amber"):
            w = "yellow"
        elif w in ("green", "g", "stand", "secure"):
            w = "green"
        elif w is not None:
            raise ParseError("alert red, alert yellow or alert green.")
        tok.rest()
        res.actions.append(("alert", w))
