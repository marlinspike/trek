"""The weapons' words: targeting, aiming, locking and turning mounts, firing, loading, phaser settings and point defense."""

from __future__ import annotations

import re

from ...sim.commands import (
    ConfigureAutoload, ControlProbe, FirePhasers, FireTorpedoes, LaunchProbe, LoadTubes, LockWeapons, SelectTarget,
    SetBanks, SetFireMode, SetPhaserSpread, SetPointDefense, SetTubes, TurnMounts,
)
from ...sim.ship import BankRole, FireMode, PDDoctrine
from ..tokens import ParseError, Tokens, aim_ahead, take_aim
from ..vocab import AIM_FIRST, AIM_HELP, FILLER, WEAPONS, is_num, match_word, system_word
from .base import ParserBase, ParseResult


class WeaponVerbs(ParserBase):
    def _v_target(self, tok: Tokens, res: ParseResult) -> None:
        lead = tok.peek()
        if tok.take_word("off", "none", "clear"):
            res.commands.append(self._cmd(SelectTarget, target=None))
            return
        tok.skip_filler()
        rest = [w.strip(".!?;'\"").removesuffix("'s").removesuffix("s'") for w in tok.toks[tok.i:]]
        whose = lead in ("the", "her", "its", "his") or (bool(rest) and (
            rest[0] in self._THEIR or rest[0] in self._FACTIONS or rest[0].rstrip("s") in self._FACTIONS
            or tok.toks[tok.i].endswith(("'s", "s'"))))
        if whose and any(system_word(w) for w in rest):
            # "target their shields", "target her engines", "target the Klingons' shields", "target all their
            # torps": an officer knocks that system out and stops there [E]
            self._disable_enemy(tok, res)
            return
        if tok.peek() in ("their", "her", "its", "his", "the") and self.ship.target is not None:
            tok.next()                          # "target their hull", "target their life support": the current target
        target: int | None
        if self.ship.target is not None and (tok.peek() in AIM_FIRST or aim_ahead(tok)):
            target = self.ship.target
        else:
            target = self.resolve_ship(tok)
        sub = None
        tok.skip_filler()
        hull = False
        if not tok.done():
            g = take_aim(tok)
            if g is None:
                raise ParseError(f"I don't know the system '{tok.peek()}'. Aim at: {AIM_HELP}.")
            sub, hull = g or None, g == ""
        res.commands.append(self._cmd(SelectTarget, target=target, subsystem=sub, hull=hull))

    def _v_aim(self, tok: Tokens, res: ParseResult) -> None:
        """`aim [at] <system>`: precision fire at a system of the current target ('aim warp core', 'aim life support')."""
        tok.skip_filler()
        if tok.peek() in ("their", "her", "its", "his") and system_word(tok.peek(1) or ""):
            self._disable_enemy(tok, res)      # "aim at their shields": as 'target their shields' [E]
            return
        if tok.peek() in ("their", "her", "its", "his"):
            tok.next()
        g = take_aim(tok)
        if g is None:
            raise ParseError(f"Aim at what? {AIM_HELP}." if tok.done() else
                             f"I don't know the system '{tok.peek()}'. Aim at: {AIM_HELP}.")
        if self.ship.target is None:
            raise ParseError("No target to aim at: 'target <ship>' first.")
        res.commands.append(self._cmd(SelectTarget, target=self.ship.target, subsystem=g or None, hull=g == ""))

    def _weapon(self, tok: Tokens, default: str | None = None) -> tuple[str, bool]:
        """Weapon noun, with Begin's optional leading 'all' ('all torpedo tubes', 'all banks', 'tor').

        Returns (weapon, all_given)."""
        tok.skip_filler()
        all_given = False
        if tok.peek() in ("all", "al", "every") and match_word(tok.peek(1) or "", WEAPONS) is not None:
            tok.next()
            all_given = True
        t = tok.peek()
        w = match_word(t, WEAPONS) if t else None
        if w is None:
            if default is not None:
                return default, all_given
            raise ParseError("Which weapons? phasers, torpedoes or probes.")
        tok.next()
        while tok.peek() is not None and match_word(tok.peek() or "", WEAPONS) == w:
            tok.next()
        return w, all_given

    def _mounts(self, tok: Tokens, all_given: bool) -> tuple[int, ...] | None:
        m = tok.mount_list()
        return None if all_given else m

    def _v_lock(self, tok: Tokens, res: ParseResult) -> None:
        tok.skip_filler()
        if tok.is_word("all") and tok.is_word("probes", "probe", k=1) or tok.is_word("probes", "probe"):
            all_probes = tok.take_word("all")
            tok.next()
            code = None
            if not all_probes and not tok.take_word("all"):
                code = tok.next()
                if code is None:
                    raise ParseError("Lock which probe? 'lock probe <code> on <ship>' (see 'status probes').")
            tok.take_word("on")
            target = self.resolve_ship(tok)
            res.commands.append(self._cmd(ControlProbe, code=code, target=target))
            return
        which = "both"
        all_given = False
        if tok.is_word("all") and match_word(tok.peek(1) or "", WEAPONS) is None:
            tok.next()
        else:
            t = tok.peek()
            if t is not None and (match_word(t, WEAPONS) is not None or t in ("all", "al")):
                which, all_given = self._weapon(tok)
        mounts = self._mounts(tok, all_given)
        tok.take_word("on")
        target = None if tok.take_word("off", "none") else self.resolve_ship(tok)
        disp = None
        if tok.take_word("dispersion", "disp", "spread"):
            disp = tok.number("dispersion")
        else:
            disp = tok.opt_number()
        if disp is not None and which == "phaser":
            raise ParseError("Dispersion applies to torpedo tubes.")
        res.commands.append(self._cmd(
            LockWeapons, target=target,
            banks=mounts if which == "phaser" else None, tubes=mounts if which == "tube" else None,
            phasers=which in ("phaser", "both"), torpedoes=which in ("tube", "both"), dispersion=disp,
        ))

    def _v_turn(self, tok: Tokens, res: ParseResult) -> None:
        tok.skip_filler()
        if tok.is_word("all") and tok.is_word("probes", "probe", k=1) or tok.is_word("probes", "probe"):
            all_probes = tok.take_word("all")
            tok.next()
            code = None
            if not all_probes and not tok.take_word("all"):
                code = tok.next()
                if code is None:
                    raise ParseError("Turn which probe? 'turn probe <code> course <c>' (see 'status probes').")
            tok.take_word("to")
            tok.take_word("course")
            res.commands.append(self._cmd(ControlProbe, code=code, course=tok.number("course") % 360))
            return
        w, all_given = self._weapon(tok)
        if w == "launcher":
            raise ParseError("Probes are turned by code: 'turn probe <code> course <c>' or 'turn all probes course <c>'.")
        # Begin: 'turn banks [<list>] [to] <mark>' — the last number is the mark
        nums: list[str] = []
        saw_to = False
        while not tok.done():
            t = tok.peek()
            if t in ("all", "al"):
                tok.next()
                all_given = True
            elif t in ("to", "mark"):
                tok.next()
                saw_to = True
            elif t == "and":
                tok.next()
            elif is_num(t) or (t and re.match(r"^\d+-\d+$", t)):
                nums.append(tok.next() or "")
            else:
                break
        if not nums:
            raise ParseError("Turn to which mark? e.g. 'turn banks 1 2 to 90'.")
        mark = float(nums.pop())
        sub = Tokens(" ".join(nums))
        sub.max_mount = tok.max_mount
        mounts = sub.mount_list()
        if not sub.done():
            raise ParseError(f"Bad mount list '{' '.join(nums)}'.")
        if all_given:
            mounts = None
        del saw_to
        if w == "phaser":
            res.commands.append(self._cmd(TurnMounts, mark=mark % 360, banks=mounts))
        else:
            res.commands.append(self._cmd(TurnMounts, mark=mark % 360,
                                          tubes=mounts if mounts else tuple(range(len(self.ship.tubes)))))

    def _v_fp(self, tok: Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "phaser", False)

    def _v_ft(self, tok: Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "tube", False)

    def _v_fpr(self, tok: Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "launcher", False)

    def _v_phaser(self, tok: Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "phaser", False)

    def _v_torp(self, tok: Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "tube", False)

    def _v_probe(self, tok: Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "launcher", False)

    def _v_fire(self, tok: Tokens, res: ParseResult) -> None:
        w, all_given = self._weapon(tok, "phaser")
        self._fire(tok, res, w, all_given)

    def _fire(self, tok: Tokens, res: ParseResult, weapon: str, all_given: bool) -> None:
        tok.skip_filler()
        all_given = all_given or tok.peek() in ("all", "al", "every")
        mounts = self._mounts(tok, all_given)
        spread = None
        target = None
        course = None
        fan = 0.0
        sub = None
        while not tok.done():
            if tok.take_word("spread", "s"):
                if weapon == "tube":
                    fan = tok.number("spread")   # a torpedo spread is a fan around the lead point
                else:
                    spread = tok.number("spread")
            elif tok.take_word("fan", "dispersion"):
                fan = tok.number("fan")
            elif tok.take_word("course"):
                course = tok.number("course")
            elif tok.peek() in ("at", "on"):
                tok.next()
                target = self.resolve_ship(tok)
            elif is_num(tok.peek()):
                v = float(tok.next() or 0)
                if weapon == "phaser":
                    spread = v           # 'fire all phasers 45', 'phaser all 45'
                elif weapon == "launcher":
                    course = v
                else:
                    raise ParseError(f"Torpedo tube {v:g} does not exist.")
            elif tok.peek() in FILLER:
                tok.next()
            elif tok.peek() in ("their", "her", "its", "his") and aim_ahead(tok, 1):
                tok.next()              # "fire phasers at their shields": the current target, aimed
            elif (g := take_aim(tok)) is not None:
                sub = g or None
            else:
                target = self.resolve_ship(tok)
        if weapon == "phaser":
            res.commands.append(self._cmd(FirePhasers, banks=mounts, spread=spread, target=target, subsystem=sub))
        elif weapon == "tube":
            res.commands.append(self._cmd(FireTorpedoes, tubes=mounts, target=target, fan=fan, subsystem=sub))
        else:
            if target is None and course is None:
                target = self.ship.target
            if target is None and course is None:
                raise ParseError("Fire probes at a ship or on a course: 'fire probes at <ship>' or 'course <c>'.")
            res.commands.append(self._cmd(LaunchProbe, launchers=mounts, target=target, course=course,
                                          count=len(mounts) if mounts else (99 if all_given else 1)))

    def _v_load(self, tok: Tokens, res: ParseResult) -> None:
        w, all_given = self._weapon(tok, "tube")
        if w == "phaser":
            raise ParseError("Phaser banks charge by themselves; load applies to tubes and launchers.")
        mounts = self._mounts(tok, all_given)
        prox = None
        tm = None
        ordnance = None
        nums: list[float] = []
        while not tok.done():
            if tok.take_word("proximity", "prox"):
                prox = tok.number("proximity")
            elif tok.take_word("time", "fuse"):
                tm = tok.number("time")
            elif is_num(tok.peek()):
                nums.append(tok.number("value"))
            elif tok.peek() in FILLER:
                tok.next()
            else:
                ordnance = self._ordnance(tok, w)
        # Begin: 'load launchers <list> <prox> <time>' and 'load tubes <list> <prox>'
        if nums and prox is None:
            prox = nums.pop(0)
        if nums and w == "launcher" and tm is None:
            tm = nums.pop(0)
        if nums:
            raise ParseError("Too many numbers: load takes a proximity (and for probes a time).")
        if prox is not None or ordnance is not None or tm is not None:
            res.commands.append(self._cmd(ConfigureAutoload, weapon=w, mounts=mounts, prox=prox, time=tm,
                                          ordnance=ordnance, enabled=True))
        res.commands.append(self._cmd(LoadTubes, tubes=mounts, weapon=w))

    def _v_unload(self, tok: Tokens, res: ParseResult) -> None:
        w, all_given = self._weapon(tok, "tube")
        if w == "phaser":
            raise ParseError("Phaser banks can't be unloaded; use 'disable banks'.")
        res.commands.append(self._cmd(LoadTubes, tubes=self._mounts(tok, all_given), unload=True, weapon=w))

    def _ordnance(self, tok: Tokens, weapon: str) -> str:
        t = tok.next() or ""
        pool = self.obs.content.torpedoes if weapon == "tube" else self.obs.content.probes
        t2 = t.replace("-", "").replace("_", "")
        if t2 in pool:
            return t2
        # "mkvii" / "mk-7" style
        roman = {"viii": "8", "vii": "7", "ii": "2"}
        for r, d in roman.items():
            if t2.endswith(r) and t2[: -len(r)] + d in pool:
                return t2[: -len(r)] + d
        hits = [k for k in pool if k.startswith(t2)] if len(t2) >= 2 else []
        if len(hits) == 1:
            return hits[0]
        raise ParseError(f"Didn't understand '{t}'.")

    def _v_autoload(self, tok: Tokens, res: ParseResult) -> None:
        w, all_given = self._weapon(tok, "tube")
        if w == "phaser":
            raise ParseError("Phaser banks charge automatically; autoload applies to tubes and launchers.")
        mounts = self._mounts(tok, all_given)
        enabled: bool | None = True
        prox = None
        tm = None
        ordnance = None
        reload = False
        nums: list[float] = []
        while not tok.done():
            if tok.take_word("off", "disable", "no"):
                enabled = False
            elif tok.take_word("on", "enable"):
                enabled = True
            elif tok.take_word("proximity", "prox"):
                prox = tok.number("proximity")
            elif tok.take_word("time", "fuse"):
                tm = tok.number("time")
            elif tok.take_word("now", "reload"):
                reload = True
            elif is_num(tok.peek()):
                nums.append(tok.number("value"))
            elif tok.peek() in FILLER:
                tok.next()
            else:
                ordnance = self._ordnance(tok, w)
        if nums:
            if prox is None:
                prox = nums.pop(0)
            if nums and w == "launcher" and tm is None:
                tm = nums.pop(0)
            if nums:
                raise ParseError("Too many numbers: autoload takes a proximity (and for probes a time).")
        res.commands.append(self._cmd(ConfigureAutoload, weapon=w, mounts=mounts, enabled=enabled,
                                      ordnance=ordnance, prox=prox, time=tm, reload=reload))

    def _v_spread(self, tok: Tokens, res: ParseResult) -> None:
        _, all_given = self._weapon(tok, "phaser")
        mounts = self._mounts(tok, all_given)
        res.commands.append(self._cmd(SetPhaserSpread, spread=tok.number("spread"), banks=mounts))

    def _enable(self, tok: Tokens, res: ParseResult, on: bool) -> None:
        w, all_given = self._weapon(tok)
        mounts = self._mounts(tok, all_given)
        if w == "phaser":
            res.commands.append(self._cmd(SetBanks, banks=mounts, enabled=on))
        elif w == "tube":
            res.commands.append(self._cmd(SetTubes, tubes=mounts, enabled=on))
        else:
            raise ParseError("Probe launchers need no charging; use 'load' or 'unload launchers'.")

    def _v_enable(self, tok: Tokens, res: ParseResult) -> None:
        self._enable(tok, res, True)

    def _v_disable(self, tok: Tokens, res: ParseResult) -> None:
        """`disable tubes 1 2` switches off your own weapons; `disable gorkon shields` (or `cripple ...`) sets
        an officer to knock out the enemy's."""
        if self._about_enemy(tok):
            self._disable_enemy(tok, res)
        else:
            self._enable(tok, res, False)

    def _about_enemy(self, tok: Tokens) -> bool:
        verb = tok.toks[tok.i - 1] if tok.i > 0 else "disable"
        if not verb.startswith("disable"):
            return True
        words = [w.strip(".!?;'\"").removesuffix("'s").removesuffix("s'") for w in tok.toks[tok.i:]]
        own = {"all", "bank", "banks", "tube", "tubes", "launcher", "launchers", "phaser", "phasers", "torpedo",
               "torpedoes", "torps", "tor", "ph", "la", "b", "tu", "pr", "probes", "probe"}
        return any(w and not w.isdigit() and w not in own for w in words)

    def _v_role(self, tok: Tokens, res: ParseResult) -> None:
        _, all_given = self._weapon(tok, "phaser")
        mounts = self._mounts(tok, all_given)
        roles = {"offense": ("offense", "offence", "attack"), "flex": ("flex", "both"),
                 "defense": ("defense", "defence", "pd", "reserve")}
        r = match_word(tok.next() or "", roles)
        if r is None:
            raise ParseError("Role must be offense, flex or defense.")
        res.commands.append(self._cmd(SetBanks, banks=mounts, role=BankRole(r)))

    def _v_mode(self, tok: Tokens, res: ParseResult) -> None:
        w, all_given = self._weapon(tok)
        if w == "launcher":
            raise ParseError("Probes are always launched by order.")
        mounts = self._mounts(tok, all_given)
        modes = {"manual": ("manual", "man", "hold"), "assisted": ("assisted", "assist", "as"),
                 "automatic": ("automatic", "auto", "free")}
        m = match_word(tok.next() or "", modes)
        if m is None:
            raise ParseError("Mode must be manual, assisted or automatic.")
        res.commands.append(self._cmd(SetFireMode, weapon=w, mounts=mounts, mode=FireMode(m)))

    def _v_pd(self, tok: Tokens, res: ParseResult) -> None:
        docs: dict[str, tuple[str, ...]] = {d.value: (d.value,) for d in PDDoctrine}
        docs["conservative"] = ("conservative", "cons", "low")
        docs["aggressive"] = ("aggressive", "aggr", "high")
        docs["balanced"] = ("balanced", "bal", "normal", "on")
        t = tok.next()
        d = match_word(t or "", docs)
        if d is None:
            raise ParseError("Point defense: off, conservative, balanced or aggressive.")
        reserve = None
        if tok.take_word("reserve", "banks"):
            reserve = tok.mount_list() or ()
        res.commands.append(self._cmd(SetPointDefense, doctrine=PDDoctrine(d), reserve=reserve))
