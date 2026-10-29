"""Begin-style command console.

Turns typed orders into the same typed commands the mouse, the AI and the
officers use. Begin's long forms work ("fire phasers 1 2 spread 10"), as do
terse forms ("fp 1 2 s 10", "al tor al mk7 1200") and readable English-ish
variants ("autoload all torpedo tubes with mk7 prox 1200").

Words can be abbreviated to any unique prefix of two or more letters.
Mount lists accept "all"/"al", "1 2 3", "1,2,3" and ranges "1-3".
Ships are named by any unique prefix of their name, or "#<id>" for an
unidentified contact.

The parser never touches the world: it reads an `Observation` and returns
commands for the caller to submit, plus UI actions and help text.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..sim.commands import (
    AllyOrder, Command, ConfigureAutoload, ControlProbe, Dock, FirePhasers, FireTorpedoes, LaunchProbe,
    LoadTubes, LockWeapons, Pursue, ReinforceShield, Scan, SelectTarget, SelfDestruct, SetBanks, SetCloak,
    SetFireMode, SetHelm, SetPhaserSpread, SetPointDefense, SetRepairPriority, SetShields, Surrender,
    Tractor, Transport, TurnMounts,
)
from ..sim.observation import Observation
from ..sim.ship import TARGETABLE_GROUPS, BankRole, FireMode, Kind, PDDoctrine


class ParseError(Exception):
    pass


@dataclass
class ParseResult:
    commands: list[Command] = field(default_factory=list)
    actions: list[tuple[str, object]] = field(default_factory=list)  # UI actions: ("pause", None), ("speed", 2.0)…
    info: list[str] = field(default_factory=list)
    error: str | None = None
    echo: str = ""


@dataclass
class ParseContext:
    ship_id: int
    obs: Observation


# ------------------------------------------------------------------ vocabulary

VERBS: dict[str, tuple[str, ...]] = {
    "helm": ("helm", "h", "course", "c"),
    "warp": ("warp", "w", "speed"),
    "pursue": ("pursue", "pu", "chase", "follow"),
    "elude": ("elude", "el", "evade", "flee"),
    "fire": ("fire", "f", "shoot"),
    "fp": ("fp",),
    "ft": ("ft",),
    "fpr": ("fpr",),
    "target": ("target", "t", "tgt", "designate"),
    "lock": ("lock", "lk"),
    "turn": ("turn", "point"),
    "load": ("load", "ld"),
    "unload": ("unload", "ul"),
    "autoload": ("autoload", "al"),
    "spread": ("spread", "sp"),
    "enable": ("enable",),
    "disable": ("disable",),
    "role": ("role",),
    "raise": ("raise", "up"),
    "lower": ("lower", "down"),
    "reinforce": ("reinforce", "reenforce", "rf"),
    "repair": ("repair", "rep"),
    "scan": ("scan", "sc"),
    "tractor": ("tractor", "tr"),
    "release": ("release",),
    "dock": ("dock",),
    "undock": ("undock",),
    "cloak": ("cloak", "cl"),
    "decloak": ("decloak", "uncloak"),
    "destruct": ("destruct", "selfdestruct", "sd"),
    "abort": ("abort",),
    "surrender": ("surrender",),
    "transport": ("transport", "beam"),
    "board": ("board",),
    "detonate": ("detonate", "det", "boom"),
    "tell": ("tell", "order"),
    "mode": ("mode", "firemode", "fm"),
    "pd": ("pd", "pointdefense", "point-defense", "defense"),
    "stop": ("stop", "allstop", "halt"),
    "pause": ("pause", "p"),
    "resume": ("resume", "go", "unpause"),
    "time": ("time", "x"),
    "range": ("range", "rng", "zoom", "scale", "display"),
    "help": ("help", "?", "commands"),
    "status": ("status", "st", "report"),
    "damage": ("damage", "dmg"),
}

WEAPONS = {
    "phaser": ("phasers", "phaser", "ph", "banks", "bank", "b"),
    "tube": ("torpedoes", "torpedo", "torps", "torp", "tor", "tubes", "tube", "tu"),
    "launcher": ("probes", "probe", "pr", "launchers", "launcher", "la"),
}

REPAIR_KINDS: dict[str, Kind | None] = {
    "all": None, "none": None, "reactors": Kind.REACTOR, "batteries": Kind.BATTERY, "drives": Kind.DRIVE,
    "warp": Kind.DRIVE, "engines": Kind.DRIVE, "impulse": Kind.IMPULSE, "sensors": Kind.SENSORS,
    "computer": Kind.COMPUTER, "shields": Kind.SHIELD, "phasers": Kind.PHASER, "tubes": Kind.TUBE,
    "torpedoes": Kind.TUBE, "launchers": Kind.LAUNCHER, "probes": Kind.LAUNCHER,
    "transporters": Kind.TRANSPORTER, "tractor": Kind.TRACTOR, "cloak": Kind.CLOAK,
}

FILLER = {"with", "the", "to", "at", "on", "of", "and", "set", "please", "by", "using", "for", "a"}

HELP = [
    "helm <course> [warp <w>] · warp <w> · pursue|elude <ship> [warp <w>] · stop",
    "target <ship> [propulsion|weapons|phasers|torpedoes|shields|power|sensors|cloak] · target off",
    "fire phasers [all|1 2|1-3] [spread <s>] [at <ship>]  (fp) · fire torpedoes [list] [at <ship>] [fan <deg>]  (ft)",
    "fire probes [list] at <ship> | course <c>  (fpr) · detonate <code>|all · turn probe <code> course <c>",
    "lock [banks|tubes] [list] on <ship> [dispersion <d>] · turn banks|tubes <list> <mark> · spread <s>",
    "autoload <tor|probe> [all|list] [<type>] [<prox>] [time <t>] [on|off]   e.g.  al tor al mk7 400",
    "load tubes [list] · unload tubes [list] · mode phasers|tubes [list] manual|assisted|automatic",
    "pd off|conservative|balanced|aggressive [reserve <banks>] · role banks <list> offense|flex|defense",
    "raise|lower [shields] [all|list] · reinforce <n>|off · repair <system>|all · scan <ship>",
    "tractor <ship>|off · dock <base> · undock · cloak on|off · destruct <cycles> · abort · surrender",
    "transport <ship> <crew> · board <ship> [<crew>] · tell <ally> <order> [<ship>]",
    "range <units> (display radius) · pause · resume · time 0.25|0.5|1|2|4 · status · damage · help",
]

_NUM = re.compile(r"^[+-]?\d+(\.\d+)?$")


def _is_num(tok: str) -> bool:
    return bool(_NUM.match(tok))


def _match(word: str, table: dict[str, tuple[str, ...]]) -> str | None:
    """Exact alias first, then a unique prefix (≥ 2 letters) of any alias."""
    for key, aliases in table.items():
        if word in aliases:
            return key
    if len(word) < 2:
        return None
    hits = {key for key, aliases in table.items() for a in aliases if a.startswith(word)}
    return hits.pop() if len(hits) == 1 else None


class _Tokens:
    def __init__(self, text: str) -> None:
        text = text.replace(",", " ").replace("°", " ")
        self.toks = [t for t in text.lower().split() if t]
        self.i = 0
        self.max_mount = 12

    def peek(self, k: int = 0) -> str | None:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def next(self) -> str | None:
        t = self.peek()
        if t is not None:
            self.i += 1
        return t

    def done(self) -> bool:
        return self.i >= len(self.toks)

    def skip_filler(self) -> None:
        while self.peek() in FILLER:
            self.i += 1

    def take_word(self, *words: str) -> bool:
        """Consume the next token if it is (a prefix ≥ 2 of) one of `words`."""
        self.skip_filler()
        t = self.peek()
        if t is None:
            return False
        for w in words:
            if t == w or (len(t) >= 2 and w.startswith(t)):
                self.i += 1
                return True
        return False

    def number(self, what: str) -> float:
        self.skip_filler()
        t = self.next()
        if t is None or not _is_num(t):
            raise ParseError(f"Expected a number for {what}.")
        return float(t)

    def opt_number(self) -> float | None:
        self.skip_filler()
        t = self.peek()
        if t is not None and _is_num(t):
            self.i += 1
            return float(t)
        return None

    def mount_list(self) -> tuple[int, ...] | None:
        """'all'/'al' → None; '1 2', '1-3' → zero-based indices; nothing → None."""
        self.skip_filler()
        t = self.peek()
        if t in ("all", "al", "every"):
            self.i += 1
            return None
        out: list[int] = []
        while True:
            t = self.peek()
            if t is None:
                break
            m = re.match(r"^(\d+)-(\d+)$", t)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                out.extend(range(min(a, b) - 1, max(a, b)))
                self.i += 1
                continue
            if t.isdigit() and 1 <= int(t) <= self.max_mount:
                out.append(int(t) - 1)
                self.i += 1
                continue
            break
        return tuple(out) if out else None


# ------------------------------------------------------------------ parser

class Parser:
    def __init__(self, ctx: ParseContext) -> None:
        self.ctx = ctx
        self.obs = ctx.obs
        ship = self.obs.own(ctx.ship_id)
        if ship is None:
            raise ParseError("No ship under command.")
        self.ship = ship

    # ship names ------------------------------------------------------
    def _ship_table(self) -> list[tuple[str, int]]:
        names: list[tuple[str, int]] = []
        for s in self.obs.own_ships(alive_only=False):
            names.append((s.name.lower(), s.id))
        for c in self.obs.contacts().values():
            if c.identified:
                names.append((c.label.lower().split(" (")[0], c.id))
        return names

    def resolve_ship(self, tok: _Tokens, allow_none: bool = False) -> int | None:
        tok.skip_filler()
        t = tok.peek()
        if t is None:
            if allow_none:
                return None
            raise ParseError("Which ship?")
        if t.startswith("#") and t[1:].isdigit():
            tok.next()
            sid = int(t[1:])
            if self.obs.contact(sid) is None and self.obs.own(sid) is None:
                raise ParseError(f"No contact #{sid}.")
            return sid
        table = self._ship_table()
        # allow multi-word names: try the longest run of tokens that matches
        for span in (3, 2, 1):
            words = [tok.peek(k) for k in range(span)]
            if any(w is None for w in words):
                continue
            phrase = " ".join(w for w in words if w)
            exact = [sid for n, sid in table if n == phrase]
            hits = exact or list({sid for n, sid in table if n.startswith(phrase)})
            if len(hits) == 1:
                tok.i += span
                return hits[0]
            if len(hits) > 1 and span == 1:
                raise ParseError(f"'{phrase}' matches more than one ship.")
        if allow_none:
            return None
        raise ParseError(f"No ship named '{t}' on sensors.")

    # entry -------------------------------------------------------------
    def parse(self, text: str) -> ParseResult:
        res = ParseResult(echo=text.strip())
        tok = _Tokens(text)
        s = self.ship
        tok.max_mount = max(6, len(s.banks), len(s.tubes), len(s.launchers), len(s.shields))
        if tok.done():
            return res
        try:
            self._parse_into(tok, res)
            tok.skip_filler()
            if not tok.done():
                raise ParseError(f"Didn't understand '{' '.join(tok.toks[tok.i:])}'.")
        except ParseError as e:
            res.commands.clear()
            res.error = str(e)
        return res

    def _cmd(self, cls: type[Command], **kw: object) -> Command:
        return cls(ship_id=self.ship.id, **kw)  # type: ignore[arg-type]

    def _parse_into(self, tok: _Tokens, res: ParseResult) -> None:
        first = tok.next()
        assert first is not None
        if _is_num(first):  # bare "90 4" = helm
            tok.i -= 1
            first = "helm"
        verb = _match(first, VERBS)
        if verb is None:
            raise ParseError(f"Unknown command '{first}'. Type 'help' for the list.")
        handler = getattr(self, f"_v_{verb}")
        handler(tok, res)

    # helm ------------------------------------------------------------
    def _v_helm(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("course")
        course = tok.opt_number()
        warp = None
        if tok.take_word("warp", "w", "speed"):
            warp = tok.number("warp")
        elif course is not None:
            warp = tok.opt_number()
        if course is None and warp is None:
            raise ParseError("helm needs a course and/or warp, e.g. 'helm 90 warp 4'.")
        res.commands.append(self._cmd(SetHelm, course=course, warp=warp))

    def _v_warp(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(SetHelm, warp=tok.number("warp")))

    def _v_stop(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(SetHelm, warp=0.0))

    def _pursue(self, tok: _Tokens, res: ParseResult, elude: bool) -> None:
        target = self.resolve_ship(tok)
        warp = None
        if tok.take_word("warp", "w"):
            warp = tok.number("warp")
        else:
            warp = tok.opt_number()
        res.commands.append(self._cmd(Pursue, target=target, warp=warp, elude=elude))

    def _v_pursue(self, tok: _Tokens, res: ParseResult) -> None:
        self._pursue(tok, res, False)

    def _v_elude(self, tok: _Tokens, res: ParseResult) -> None:
        self._pursue(tok, res, True)

    # targeting -------------------------------------------------------------
    def _v_target(self, tok: _Tokens, res: ParseResult) -> None:
        if tok.take_word("off", "none", "clear"):
            res.commands.append(self._cmd(SelectTarget, target=None))
            return
        target = self.resolve_ship(tok)
        sub = None
        tok.skip_filler()
        t = tok.peek()
        if t is not None:
            groups = {g: (g,) for g in TARGETABLE_GROUPS}
            groups["propulsion"] = ("propulsion", "engines", "drives", "warp")
            groups["torpedoes"] = ("torpedoes", "tubes", "torps")
            g = _match(t, groups)
            if g is not None:
                tok.next()
                sub = g
        res.commands.append(self._cmd(SelectTarget, target=target, subsystem=sub))

    def _weapon(self, tok: _Tokens, default: str | None = None) -> str:
        """Weapon kind; accepts 'all torpedo tubes', 'torpedo tubes', 'tor' and the like."""
        tok.skip_filler()
        t = tok.peek()
        if t in ("all", "al") and _match(tok.peek(1) or "", WEAPONS) is not None:
            tok.next()  # "all" here is the mount list; mount_list() then sees none and means all
        t = tok.peek()
        w = _match(t, WEAPONS) if t else None
        if w is None:
            if default is not None:
                return default
            raise ParseError("Which weapons? phasers, torpedoes or probes.")
        tok.next()
        while tok.peek() is not None and _match(tok.peek() or "", WEAPONS) == w:
            tok.next()
        return w

    def _v_lock(self, tok: _Tokens, res: ParseResult) -> None:
        if tok.take_word("probe"):
            code = tok.next()
            tok.take_word("on")
            target = self.resolve_ship(tok)
            res.commands.append(self._cmd(ControlProbe, code=code, target=target))
            return
        which = "both"
        if tok.take_word("all"):
            which = "both"
        else:
            t = tok.peek()
            w = _match(t, WEAPONS) if t else None
            if w is not None:
                tok.next()
                which = w
        mounts = tok.mount_list()
        tok.take_word("on")
        target = None if tok.take_word("off", "none") else self.resolve_ship(tok)
        disp = None
        if tok.take_word("dispersion", "disp"):
            disp = tok.number("dispersion")
        res.commands.append(self._cmd(
            LockWeapons, target=target,
            banks=mounts if which == "phaser" else None, tubes=mounts if which == "tube" else None,
            phasers=which in ("phaser", "both"), torpedoes=which in ("tube", "both"), dispersion=disp,
        ))

    def _v_turn(self, tok: _Tokens, res: ParseResult) -> None:
        if tok.take_word("probe"):
            code = tok.next()
            tok.take_word("course")
            res.commands.append(self._cmd(ControlProbe, code=code, course=tok.number("course")))
            return
        w = self._weapon(tok)
        mounts = tok.mount_list()
        tok.take_word("to", "mark")
        mark = tok.number("mark")
        if w == "phaser":
            res.commands.append(self._cmd(TurnMounts, mark=mark, banks=mounts if mounts else None))
        else:
            res.commands.append(self._cmd(TurnMounts, mark=mark, tubes=mounts if mounts else tuple(range(len(self.ship.tubes)))))

    # fire ------------------------------------------------------------
    def _v_fp(self, tok: _Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "phaser")

    def _v_ft(self, tok: _Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "tube")

    def _v_fpr(self, tok: _Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "launcher")

    def _v_fire(self, tok: _Tokens, res: ParseResult) -> None:
        self._fire(tok, res, self._weapon(tok, "phaser"))

    def _fire(self, tok: _Tokens, res: ParseResult, weapon: str) -> None:
        mounts = tok.mount_list()
        spread = None
        target = None
        course = None
        fan = 0.0
        sub = None
        while not tok.done():
            if tok.take_word("spread", "s"):
                spread = tok.number("spread")
            elif tok.take_word("fan", "dispersion"):
                fan = tok.number("fan")
            elif tok.take_word("course"):
                course = tok.number("course")
            elif tok.peek() in ("at", "on"):
                tok.next()
                target = self.resolve_ship(tok)
            elif _match(tok.peek() or "", {g: (g,) for g in TARGETABLE_GROUPS}) is not None:
                sub = _match(tok.next() or "", {g: (g,) for g in TARGETABLE_GROUPS})
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
            res.commands.append(self._cmd(LaunchProbe, launchers=mounts, target=target, course=course))

    # loading -------------------------------------------------------------
    def _v_load(self, tok: _Tokens, res: ParseResult) -> None:
        w = self._weapon(tok, "tube")
        mounts = tok.mount_list()
        prox = None
        tm = None
        ordnance = None
        while not tok.done():
            if tok.take_word("proximity", "prox"):
                prox = tok.number("proximity")
            elif tok.take_word("time"):
                tm = tok.number("time")
            elif _is_num(tok.peek() or ""):
                prox = tok.number("proximity")
            else:
                ordnance = self._ordnance(tok, w)
        if prox is not None or ordnance is not None or tm is not None:
            res.commands.append(self._cmd(ConfigureAutoload, weapon=w, mounts=mounts, prox=prox, time=tm,
                                          ordnance=ordnance))
        if w == "tube":
            res.commands.append(self._cmd(LoadTubes, tubes=mounts))
        else:
            res.commands.append(self._cmd(ConfigureAutoload, weapon=w, mounts=mounts, enabled=True))

    def _v_unload(self, tok: _Tokens, res: ParseResult) -> None:
        self._weapon(tok, "tube")
        res.commands.append(self._cmd(LoadTubes, tubes=tok.mount_list(), unload=True))

    def _ordnance(self, tok: _Tokens, weapon: str) -> str:
        t = tok.next() or ""
        pool = self.obs.content.torpedoes if weapon == "tube" else self.obs.content.probes
        t2 = t.replace("-", "").replace("_", "")
        if t2 in pool:
            return t2
        # "mkvii" / "mk-7" style
        roman = {"vii": "7", "viii": "8", "ii": "2"}
        for r, d in roman.items():
            if t2.endswith(r) and t2[: -len(r)] + d in pool:
                return t2[: -len(r)] + d
        hits = [k for k in pool if k.startswith(t2)] if len(t2) >= 2 else []
        if len(hits) == 1:
            return hits[0]
        raise ParseError(f"Unknown {'torpedo' if weapon == 'tube' else 'probe'} type '{t}'.")

    def _v_autoload(self, tok: _Tokens, res: ParseResult) -> None:
        w = self._weapon(tok, "tube")
        if w == "phaser":
            raise ParseError("Phaser banks charge automatically; autoload applies to tubes and launchers.")
        mounts = tok.mount_list()
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
            elif _is_num(tok.peek() or ""):
                nums.append(tok.number("value"))
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

    # phaser settings -------------------------------------------------------------
    def _v_spread(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("banks", "phasers")
        mounts = tok.mount_list() if tok.peek() in ("all", "al") else None
        res.commands.append(self._cmd(SetPhaserSpread, spread=tok.number("spread"), banks=mounts))

    def _v_enable(self, tok: _Tokens, res: ParseResult) -> None:
        self._weapon(tok, "phaser")
        res.commands.append(self._cmd(SetBanks, banks=tok.mount_list(), enabled=True))

    def _v_disable(self, tok: _Tokens, res: ParseResult) -> None:
        self._weapon(tok, "phaser")
        res.commands.append(self._cmd(SetBanks, banks=tok.mount_list(), enabled=False))

    def _v_role(self, tok: _Tokens, res: ParseResult) -> None:
        self._weapon(tok, "phaser")
        mounts = tok.mount_list()
        roles = {"offense": ("offense", "offence", "attack"), "flex": ("flex", "both"),
                 "defense": ("defense", "defence", "pd", "reserve")}
        r = _match(tok.next() or "", roles)
        if r is None:
            raise ParseError("Role must be offense, flex or defense.")
        res.commands.append(self._cmd(SetBanks, banks=mounts, role=BankRole(r)))

    def _v_mode(self, tok: _Tokens, res: ParseResult) -> None:
        w = self._weapon(tok)
        if w == "launcher":
            raise ParseError("Probes are always launched by order.")
        mounts = tok.mount_list()
        modes = {"manual": ("manual", "man", "hold"), "assisted": ("assisted", "assist", "as"),
                 "automatic": ("automatic", "auto", "free")}
        m = _match(tok.next() or "", modes)
        if m is None:
            raise ParseError("Mode must be manual, assisted or automatic.")
        res.commands.append(self._cmd(SetFireMode, weapon=w, mounts=mounts, mode=FireMode(m)))

    def _v_pd(self, tok: _Tokens, res: ParseResult) -> None:
        docs = {d.value: (d.value,) for d in PDDoctrine}
        docs["conservative"] = ("conservative", "cons", "low")
        docs["aggressive"] = ("aggressive", "aggr", "high")
        docs["balanced"] = ("balanced", "bal", "normal", "on")
        t = tok.next()
        d = _match(t or "", docs)
        if d is None:
            raise ParseError("Point defense: off, conservative, balanced or aggressive.")
        reserve = None
        if tok.take_word("reserve", "banks"):
            reserve = tok.mount_list() or ()
        res.commands.append(self._cmd(SetPointDefense, doctrine=PDDoctrine(d), reserve=reserve))

    # shields ---------------------------------------------------------------
    def _v_raise(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("shields")
        res.commands.append(self._cmd(SetShields, sectors=tok.mount_list(), up=True))

    def _v_lower(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("shields")
        res.commands.append(self._cmd(SetShields, sectors=tok.mount_list(), up=False))

    def _v_reinforce(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("shield")
        if tok.take_word("off", "none", "clear"):
            res.commands.append(self._cmd(ReinforceShield, sector=None))
            return
        res.commands.append(self._cmd(ReinforceShield, sector=int(tok.number("shield")) - 1))

    # engineering and specials ----------------------------------------------------
    def _v_repair(self, tok: _Tokens, res: ParseResult) -> None:
        w = tok.next() or "all"
        k = _match(w, {k: (k,) for k in REPAIR_KINDS})
        if k is None:
            raise ParseError(f"Unknown system '{w}'.")
        res.commands.append(self._cmd(SetRepairPriority, kind=REPAIR_KINDS[k]))

    def _v_scan(self, tok: _Tokens, res: ParseResult) -> None:
        target = self.resolve_ship(tok, allow_none=True) or self.ship.target
        if target is None:
            raise ParseError("Scan which ship?")
        res.commands.append(self._cmd(Scan, target=target))

    def _v_tractor(self, tok: _Tokens, res: ParseResult) -> None:
        if tok.take_word("off", "release"):
            res.commands.append(self._cmd(Tractor, target=None))
        else:
            res.commands.append(self._cmd(Tractor, target=self.resolve_ship(tok)))

    def _v_release(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(Tractor, target=None))

    def _v_dock(self, tok: _Tokens, res: ParseResult) -> None:
        if tok.take_word("off"):
            res.commands.append(self._cmd(Dock, host=None))
            return
        host = self.resolve_ship(tok)
        tok.take_word("on")
        res.commands.append(self._cmd(Dock, host=host))

    def _v_undock(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(Dock, host=None))

    def _v_cloak(self, tok: _Tokens, res: ParseResult) -> None:
        on = not tok.take_word("off")
        tok.take_word("on")
        res.commands.append(self._cmd(SetCloak, on=on))

    def _v_decloak(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(SetCloak, on=False))

    def _v_destruct(self, tok: _Tokens, res: ParseResult) -> None:
        if tok.take_word("abort", "off", "cancel"):
            res.commands.append(self._cmd(SelfDestruct, cycles=None))
            return
        n = tok.opt_number()
        res.commands.append(self._cmd(SelfDestruct, cycles=n if n is not None else 5.0))

    def _v_abort(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("destruct")
        res.commands.append(self._cmd(SelfDestruct, cycles=None))

    def _v_surrender(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(Surrender))

    def _v_transport(self, tok: _Tokens, res: ParseResult) -> None:
        target = self.resolve_ship(tok)
        n = tok.opt_number()
        res.commands.append(self._cmd(Transport, target=target, count=int(n if n is not None else 10)))

    def _v_board(self, tok: _Tokens, res: ParseResult) -> None:
        target = self.resolve_ship(tok)
        n = tok.opt_number()
        if n is None:
            n = max(6.0, min(self.ship.cls.beam_cap * max(1, len(self.ship.transporters)), self.ship.crew * 0.25))
        res.commands.append(self._cmd(Transport, target=target, count=int(n)))

    def _v_detonate(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("probe", "probes")
        if tok.take_word("all") or tok.done():
            res.commands.append(self._cmd(ControlProbe, code=None, detonate=True))
        else:
            res.commands.append(self._cmd(ControlProbe, code=tok.next(), detonate=True))

    def _v_tell(self, tok: _Tokens, res: ParseResult) -> None:
        ally = self.resolve_ship(tok)
        assert ally is not None
        order = tok.next()
        if order is None:
            raise ParseError("Tell them what? e.g. 'tell <ally> attack <ship>'.")
        target = self.resolve_ship(tok, allow_none=True)
        value = tok.opt_number()
        res.commands.append(self._cmd(AllyOrder, ally=ally, order=order, target=target, value=value))

    # UI ------------------------------------------------------------------
    def _v_pause(self, tok: _Tokens, res: ParseResult) -> None:
        res.actions.append(("pause", None))

    def _v_resume(self, tok: _Tokens, res: ParseResult) -> None:
        res.actions.append(("resume", None))

    def _v_time(self, tok: _Tokens, res: ParseResult) -> None:
        v = tok.number("time scale")
        if v not in (0.25, 0.5, 1.0, 2.0, 4.0):
            raise ParseError("Time scale must be 0.25, 0.5, 1, 2 or 4.")
        res.actions.append(("speed", v))

    def _v_range(self, tok: _Tokens, res: ParseResult) -> None:
        """Begin's `range <r>`: set the tactical display radius (world units); bare `range` reports it."""
        v = tok.opt_number()
        if v is not None and not (200 <= v <= 500000):
            raise ParseError("Display range must be between 200 and 500,000 units.")
        res.actions.append(("range", v))

    def _v_help(self, tok: _Tokens, res: ParseResult) -> None:
        tok.toks = tok.toks[: tok.i]
        res.info.extend(HELP)

    def _v_status(self, tok: _Tokens, res: ParseResult) -> None:
        res.actions.append(("status", None))

    def _v_damage(self, tok: _Tokens, res: ParseResult) -> None:
        res.actions.append(("damage", None))


def parse(text: str, ctx: ParseContext) -> ParseResult:
    try:
        return Parser(ctx).parse(text)
    except ParseError as e:
        return ParseResult(error=str(e), echo=text)


__all__ = ["HELP", "ParseContext", "ParseError", "ParseResult", "Parser", "parse"]
