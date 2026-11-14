"""The weapons' words: targeting, aiming, locking and turning mounts, firing, loading, phaser settings and point defense."""

from __future__ import annotations

import re

from ...sim.commands import (
    ConfigureAutoload, ControlProbe, EndObjective, FirePhasers, FireTorpedoes, LaunchProbe, LoadTubes, LockWeapons,
    OpenFire, Pursue, SelectTarget, SetBanks, SetFireMode, SetObjective, SetPhaserSpread, SetPointDefense, SetTubes,
    SplitFire, TurnMounts,
)
from ...sim.objectives import ENGAGE_GROUP
from ...sim.ship import BankRole, FireMode, PDDoctrine
from ..tokens import ParseError, Tokens, aim_ahead, take_aim
from ..vocab import AIM_FIRST, AIM_HELP, FILLER, WEAPONS, is_num, match_word, system_word
from .base import ParserBase, ParseResult


# [E] splitting the weapons between ships: the words for "the rest", and numbers as they are spoken
_REST = ("rest", "others", "remaining", "remainder", "other", "everything", "else")
_NUMBER_WORDS = {"one": "1", "two": "2", "three": "3", "four": "4", "five": "5", "six": "6", "seven": "7",
                 "eight": "8", "nine": "9", "ten": "10", "eleven": "11", "twelve": "12", "won": "1", "too": "2",
                 "for": "4", "ate": "8"}
_REST_MARK = (-1,)      # a clause's mounts: whatever of that weapon no other clause named


def spoken_mounts(toks: list[str]) -> list[str]:
    """'tubes one through four' -> 'tubes 1-4'; 'one and two' -> '1 and 2'. A homophone ('for', 'too') becomes a
    number only between numbers or right after a weapon, so 'four on the Talon' and 'the rest for' stay as said."""
    out: list[str] = []
    for i, t in enumerate(toks):
        prev = out[-1] if out else ""
        nxt = toks[i + 1] if i + 1 < len(toks) else ""
        if t in _NUMBER_WORDS and (t in ("won", "too", "for", "ate")) and not (
                is_num(prev) or match_word(prev, WEAPONS) is not None or prev == "and" and len(out) > 1 and is_num(out[-2])):
            out.append(t)
            continue
        if t in _NUMBER_WORDS:
            t = _NUMBER_WORDS[t]
        if t in ("through", "thru", "to") and is_num(prev) and (is_num(nxt) or nxt in _NUMBER_WORDS) and out:
            out[-1] = prev + "-"
            continue
        if out and out[-1].endswith("-") and is_num(t):
            out[-1] = out[-1] + t
            continue
        out.append(t)
    return out


class WeaponVerbs(ParserBase):
    def _v_split(self, tok: Tokens, res: ParseResult) -> None:
        """[E] `split <ship> <ship>`: divide the weapons between two ships, as the weapons officer would judge it.
        `split tubes 1-4 <ship> rest <ship>`, `split phasers <ship> torpedoes <ship>`: the captain's own division.
        `split off` puts everything back on the target. A trailing `now` fires each group at its ship at once."""
        from ...crew.split_fire import divide

        words = spoken_mounts([w for w in tok.rest() if w not in ("fire", "our", "weapons", "between", "across",
                                                                  "among", "amongst", "up")])
        sub = Tokens(" ".join(words))
        sub.max_mount = max(12, len(self.ship.banks), len(self.ship.tubes))
        if sub.take_word("off", "clear", "none", "cancel", "undo") or (sub.done() and tok.toks and tok.toks[0] == "unsplit"):
            if self.ship.target is None:
                raise ParseError("Nothing to put back together: no target is selected.")
            res.commands.append(self._cmd(SelectTarget, target=self.ship.target, subsystem=self.ship.target_subsystem))
            return
        now = False
        clauses: list[tuple[str | None, tuple[int, ...] | None, int]] = []
        weapon: str | None = None
        mounts: tuple[int, ...] | None = None
        while not sub.done():
            t = sub.peek() or ""
            w = match_word(t, WEAPONS)
            if w is not None and w != "launcher" and len(t) >= 3:
                sub.next()
                weapon, mounts = w, None
                while sub.peek() is not None and match_word(sub.peek() or "", WEAPONS) == w:
                    sub.next()
            elif sub.is_mount(t):
                mounts = sub.mount_list()
            elif t in _REST:
                sub.next()
                mounts = _REST_MARK
            elif t in ("now", "fire", "go") and sub.peek(1) is None:
                sub.next()
                now = True
            elif t in FILLER or t in ("then", "and", "onto", "against", "of", "them", "all", "both", "us"):
                sub.next()
            else:
                sid = self.resolve_ship(sub)
                assert sid is not None
                clauses.append((weapon, mounts, sid))
                mounts = None
        if not clauses or all(w is None and m is None for w, m, _ in clauses) and len({c[2] for c in clauses}) < 2:
            # "split fire", "divide the torpedoes between them": the target and the nearest other enemy
            named = {c[2] for c in clauses}
            first = next(iter(named)) if named else self.ship.target
            others = sorted((c for c in self.obs.hostile_contacts() if c.id != first and c.visible
                             and c.id not in self.obs.gone()), key=lambda c: c.distance_to(self.ship.x, self.ship.y))
            if first is None or not others:
                raise ParseError("Split between which ships? e.g. 'split talon wraith' or "
                                 "'split tubes 1-4 talon rest wraith'.")
            only_w = next((w for w, _, _ in clauses), weapon)
            clauses = [(only_w, None, first), (only_w, None, others[0].id)]
        hostile = {c.id for c in self.obs.hostile_contacts()}
        for _, _, sid in clauses:
            if sid not in hostile:
                raise ParseError(f"The {self._name(sid)} is not an enemy.")
        if all(m is None for _, m, _ in clauses) and len({w for w, _, _ in clauses}) == 1:
            # only ships named (and perhaps one weapon): divided as the weapons officer would judge it
            only = clauses[0][0]
            ships = tuple(dict.fromkeys(sid for _, _, sid in clauses))
            if len(ships) < 2:
                raise ParseError("Split between which two ships? e.g. 'split talon wraith'.")
            d = divide(self.obs, self.ship, ships)
            if d is None:
                raise ParseError("Neither ship is on sensors.")
            banks_on = d.banks if only in (None, "phaser") else {}
            tubes_on = d.tubes if only in (None, "tube") else {}
            if not banks_on and not tubes_on:
                raise ParseError("The ship has none of those to divide.")
            res.commands.append(self._cmd(SplitFire, banks=tuple(banks_on.items()), tubes=tuple(tubes_on.items()),
                                          primary=d.primary if only is None else None))
        else:
            banks_on, tubes_on = self._divide_as_told(clauses)
            res.commands.append(self._cmd(SplitFire, banks=tuple(banks_on.items()), tubes=tuple(tubes_on.items()),
                                          primary=clauses[0][2]))
        if now:      # each group at its own ship, so the readback says where every one went
            for sid, g in banks_on.items():
                res.commands.append(self._cmd(FirePhasers, banks=tuple(g), target=sid))
            for sid, g in tubes_on.items():
                res.commands.append(self._cmd(FireTorpedoes, tubes=tuple(g), target=sid))

    def _name(self, sid: int) -> str:
        c = self.obs.contact(sid)
        return c.label.split(" (")[0] if c is not None else f"#{sid}"

    def _divide_as_told(self, clauses: list[tuple[str | None, tuple[int, ...] | None, int]]
                        ) -> tuple[dict[int, tuple[int, ...]], dict[int, tuple[int, ...]]]:
        """The captain's own division: numbered mounts first, then each 'rest' (or a weapon named without numbers)
        takes what is left of that weapon. Numbers with no weapon named are tubes (and so is the rest). A ship named alone, after
        others were given weapons, takes the rest of everything."""
        n = {"phaser": len(self.ship.banks), "tube": len(self.ship.tubes)}
        given: dict[str, dict[int, list[int]]] = {"phaser": {}, "tube": {}}
        taken: dict[str, set[int]] = {"phaser": set(), "tube": set()}
        later: list[tuple[str, int]] = []
        # numbers with no weapon named anywhere in the line are tubes, and so is 'the rest' of them
        tubes_only = all(w is None for w, _, _ in clauses) and any(m not in (None, _REST_MARK) for _, m, _ in clauses)
        for w, m, sid in clauses:
            kinds = [w] if w is not None else (["tube"] if tubes_only or m not in (None, _REST_MARK) else ["phaser", "tube"])
            for k in kinds:
                if m is None or m == _REST_MARK:
                    later.append((k, sid))
                    continue
                bad = [i + 1 for i in m if i >= n[k]]
                if bad:
                    what = "phaser bank" if k == "phaser" else "torpedo tube"
                    raise ParseError(f"{what.capitalize()} {bad[0]} does not exist: the {self.ship.cls.name} has {n[k]}.")
                clash = [i + 1 for i in m if i in taken[k]]
                if clash:
                    raise ParseError(f"{'Bank' if k == 'phaser' else 'Tube'} {clash[0]} is named twice.")
                given[k].setdefault(sid, []).extend(m)
                taken[k].update(m)
        for k, sid in later:
            rest = [i for i in range(n[k]) if i not in taken[k]
                    and not (k == "phaser" and self.ship.banks[i].role == BankRole.DEFENSE)]
            if rest:
                given[k].setdefault(sid, []).extend(rest)
                taken[k].update(rest)
        if not given["phaser"] and not given["tube"]:
            raise ParseError("Nothing left to give that ship: every bank and tube is already named.")
        return ({sid: tuple(v) for sid, v in given["phaser"].items()}, {sid: tuple(v) for sid, v in given["tube"].items()})

    def _v_engage(self, tok: Tokens, res: ParseResult) -> None:
        """`engage <ship>`: target her, close and open fire. `engage <ship> and <ship>`: the weapons officer fights
        both at once, dividing the weapons between them as the battle moves (a standing objective) [E]."""
        words = [w.strip(".!?;'\"").removesuffix("'s").removesuffix("s'") for w in tok.rest()]
        words = [w for w in words if w and w not in ("and", "with", "both")]
        if any(w in ("off", "cancel", "stop", "belay", "abort") for w in words):
            res.commands.append(self._cmd(EndObjective, group=ENGAGE_GROUP, outcome="cancelled"))
            return
        if not words:
            raise ParseError("Engage which ships? e.g. 'engage talon and wraith'.")
        targets = self._enemy_targets(words)
        if len(targets) == 1:
            res.commands.append(self._cmd(SelectTarget, target=targets[0]))
            res.commands.append(self._cmd(Pursue, target=targets[0]))
            res.commands.append(self._cmd(OpenFire))
            return
        res.commands.append(self._cmd(SetObjective, goal="engage", group=ENGAGE_GROUP, targets=targets))

    def _v_target(self, tok: Tokens, res: ParseResult) -> None:
        lead = tok.peek()
        w0 = match_word(lead or "", WEAPONS)
        if w0 in ("phaser", "tube") and len(lead or "") >= 3 and not tok.is_word("their", "her", k=1):
            self._v_split(tok, res)     # "target tubes 1 2 on the Talon, the rest on the Wraith" [E]
            return
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
