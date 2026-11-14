"""The parser's ground: its results, its context, the vocabulary it shares, and `ParserBase`, which reads ship
names and settles which verb a line begins with. The verbs themselves live in the modules beside this one."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable

from ...sim.away import SHUTTLE_NAMES
from ...sim.commands import CeaseFire, Command, StandDown
from ...sim.observation import Observation
from ..plain import STOP_ALL, STOP_FIRE, ally_words, plain_order, split_orders
from ..tokens import ParseError, Tokens
from ..vocab import STATION_WORDS, VERBS, candidates, is_num, match_word, system_word

# `hud <switch> <value>`: the Bridge setting and its parts (see session/prefs.py) [E]
BRIDGE_SWITCHES: dict[str, tuple[str, tuple[str, ...]]] = {
    "bridge": ("bridge", ("full", "quiet", "classic")),
    "wheel": ("wheel", ("on", "off")),
    "focus": ("focus", ("slow", "pause", "off")),
    "proposals": ("proposals", ("often", "rarely", "off")),
    "orders": ("map_orders", ("on", "off")),
    "subtitles": ("subtitles", ("all", "urgent", "off")),
    "readbacks": ("readbacks", ("voiced", "log", "off")),
    "preview": ("preview", ("on", "off")),
}

# `tell all ...`: every ship of ours under command [E]
FLEET_WORDS = ("all", "fleet", "everyone", "everybody", "squadron", "wingmen", "allies")
# `reinforce forward`: a shield by the side of the ship it covers, as a bearing off the bow [E]
SHIELD_SIDES = {"forward": 0.0, "front": 0.0, "fore": 0.0, "bow": 0.0, "starboard": 90.0, "right": 90.0,
                "aft": 180.0, "rear": 180.0, "stern": 180.0, "port": 270.0, "left": 270.0}

_HAIL_ALL = ("all", "everyone", "everybody", "enemies", "them", "fleet")
# a hail of one word that is still something a captain would say, not a misheard ship's name
_HAIL_SPEECH = frozenset("""surrender yield withdraw retreat leave greetings hello hi hail respond answer identify
    stand cease halt stop""".split())


@dataclass
class ParseResult:
    commands: list[Command] = field(default_factory=list)
    actions: list[tuple[str, object]] = field(default_factory=list)  # UI actions: ("pause", None), ("speed", 2.0)…
    info: list[str] = field(default_factory=list)      # plain help text
    display: list[str] = field(default_factory=list)   # Begin's tabular status displays (monospaced)
    error: str | None = None
    echo: str = ""


@dataclass
class ParseContext:
    ship_id: int | None      # None: no ship under command, so only orders that need no ship work
    obs: Observation





NOTHING_LOST = "Every enemy we know of is on sensors: there's nothing to find. Name a ship to hear where she is."

# words that don't name the ship to find: "find the cloaked ship", "hunt for her", "locate that ship" [E]
_HUNT_FILLER = frozenset(("for", "down", "the", "a", "her", "him", "it", "them", "that", "this", "ship", "vessel",
                          "where", "is", "she", "he", "out", "again", "please", "now"))

# words that don't name the ship or the system in a sweep and strike [E]: "strike the talon's shields", "sweep and
# strike her warp drive", "seeker strike at the talon's engines"
_STRIKE_FILLER = _HUNT_FILLER | frozenset(("and", "strike", "sweep", "seeker", "at", "on", "into", "in", "of", "to",
                                           "her", "their", "its", "his", "salvo", "kill", "hit", "then", "with",
                                           "by", "from", "through", "along", "trail", "trails", "exhaust", "plasma",
                                           "drive", "system", "systems", "chain"))
_STRIKE_HULL = ("hull", "everything")

# words for the science officer's hive duties [E]
DUTY_WORDS = {"shields": ("shields", "shield", "harmonics-shields", "deflectors"),
              "harmonics": ("harmonics", "harmonic", "survey", "scan", "scans", "scanning", "weakness"),
              "phasers": ("phasers", "phaser", "frequency", "frequencies", "remodulate")}


KEEP_MIN = 100.0     # [E] a bare number after pursue/elude above this is a range to hold, not a warp

# [E] how a captain points at a ship without naming her: our target (else the nearest enemy), or the nearest enemy
_POINTING = frozenset(("target", "her", "him", "it", "them", "that", "this", "she", "they", "enemy", "hostile"))
_NEAREST = frozenset(("nearest", "closest", "near"))
_SHIP_NOUNS = frozenset(("ship", "vessel", "one", "enemy", "enemies", "hostile", "contact", "target"))


class ParserBase:
    """Ship names, the entry point and verb dispatch. The verbs are mixins on top of this (see `__init__`)."""

    # how a captain names the enemy as a body: "their shields", "all of them", "the Klingons" [E]
    _THEIR = ("their", "all", "every", "everyone", "everybody", "them", "enemy", "enemies", "each", "both")
    _EVERYONE = ("all", "everyone", "everybody", "them", "enemy", "enemies", "both", "every", "each", "they")
    _FACTIONS = {"klingon": "klingon", "romulan": "romulan", "orion": "orion", "federation": "federation",
                 "pirate": "orion", "pirates": "orion"}

    if TYPE_CHECKING:
        # verbs and helpers one station's mixin borrows from another's; `Parser` brings them all together
        def _v_ihave(self, tok: Tokens, res: ParseResult) -> None: ...
        def _v_standdown(self, tok: Tokens, res: ParseResult) -> None: ...
        def _v_destroy(self, tok: Tokens, res: ParseResult) -> None: ...
        def _v_hail(self, tok: Tokens, res: ParseResult) -> None: ...
        def _disable_enemy(self, tok: Tokens, res: ParseResult) -> None: ...
        def _enemy_targets(self, words: list[str]) -> tuple[int, ...]: ...
        def _shield_list(self, tok: Tokens) -> tuple[int, ...] | None: ...
        def _lost_ship(self, words: list[str]) -> int: ...
        def _away_op(self) -> object | None: ...
        def _hail_away(self, words: str, res: ParseResult) -> None: ...

    def __init__(self, ctx: ParseContext) -> None:
        self.ctx = ctx
        self.obs = ctx.obs
        ship = self.obs.own(ctx.ship_id) if ctx.ship_id is not None else None
        if ship is None:
            raise ParseError("No ship under command.")
        self.ship = ship

    def _ship_table(self) -> list[tuple[str, int]]:
        names: list[tuple[str, int]] = []
        for s in self.obs.own_ships(alive_only=False):
            names.append((s.name.lower(), s.id))
        for c in self.obs.contacts().values():
            if c.identified:
                names.append((c.label.lower().split(" (")[0], c.id))
        return names

    def resolve_ship(self, tok: Tokens, allow_none: bool = False) -> int | None:
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
        if t in ("me", "us", "flagship") and not any(n == t for n, _ in self._ship_table()):
            tok.next()  # 'tell tau escort me'
            return self.ship.id
        table = self._ship_table()
        pointed = self._pointed_ship(tok, table, allow_none)
        if pointed is not None:
            return pointed
        # allow multi-word names: try the longest run of tokens that matches
        for span in (3, 2, 1):
            words = [tok.peek(k) for k in range(span)]
            if any(w is None for w in words):
                continue
            phrase = " ".join(w for w in words if w)
            exact = list({sid for n, sid in table if n == phrase})   # a captured ship is ours and a contact
            hits = exact or list({sid for n, sid in table if n.startswith(phrase)})
            if len(hits) == 1:
                tok.i += span
                return hits[0]
            if len(hits) > 1 and span == 1:
                raise ParseError(f"'{phrase}' matches more than one ship.")
        if allow_none:
            return None
        raise ParseError(f"No ship named '{t}' on sensors.")

    def _pointed_ship(self, tok: Tokens, table: list[tuple[str, int]], quiet: bool = False) -> int | None:
        """[E] A ship named the way a captain points at one: 'the target', 'her', 'them', 'that ship' mean the
        one we have targeted; 'the nearest (enemy)', 'the closest one' the nearest enemy on sensors. A ship
        whose name really is the word ('Target') still wins."""
        t = tok.peek()
        if t is None or any(n == t for n, _ in table):
            return None
        if t in _POINTING:
            span = 2 if tok.peek(1) in _SHIP_NOUNS else 1
            sid = self.ship.target if self.ship.target is not None else self._nearest_enemy()
            if sid is None:
                if quiet:
                    return None
                raise ParseError("No target, and no enemy on sensors. Name a ship, or press Tab for the nearest.")
            tok.i += span
            return sid
        if t in _NEAREST:
            span = 2 if tok.peek(1) in _SHIP_NOUNS else 1
            sid = self._nearest_enemy()
            if sid is None:
                if quiet:
                    return None
                raise ParseError("No enemy on sensors.")
            tok.i += span
            return sid
        return None

    def _nearest_enemy(self) -> int | None:
        """The nearest enemy we can see (the one Tab would pick)."""
        seen = [c for c in self.obs.hostile_contacts() if c.visible and not c.exhaust]
        if not seen:
            return None
        x, y = self.ship.x, self.ship.y
        return min(seen, key=lambda c: c.distance_to(x, y)).id

    def _ship_name(self, sid: int) -> str:
        s = self.obs.own(sid)
        if s is not None:
            return s.name
        c = self.obs.contact(sid)
        return c.label.split(" (")[0] if c is not None else f"#{sid}"

    def parse(self, text: str) -> ParseResult:
        """One line; several orders in it ("cease fire and take evasive action") are carried out in turn."""
        plain = self._to_ally(text) or plain_order(text)
        pieces = split_orders(plain)
        if len(pieces) > 1:
            parts = [self._parse_one(p, p) for p in pieces]
            if all(p.error is None for p in parts):
                res = ParseResult(echo=text.strip())
                for p in parts:
                    res.commands.extend(p.commands)
                    res.actions.extend(p.actions)
                    res.info.extend(p.info)
                    res.display.extend(p.display)
                return res
        return self._parse_one(plain, text)

    def _to_ally(self, text: str) -> str | None:
        """'Yorktown, attack the Wraith': a line that opens with one of our ships' names is an order to her, as
        `tell yorktown attack wraith` [E]. A name that is also a command word needs the comma ('Target, ...')."""
        low = text.strip().lower()
        for s in self.obs.own_ships():
            if s.id == self.ship.id or not s.alive:
                continue
            name = s.name.lower()
            m = re.match(r"(?:the\s+|uss\s+)?" + re.escape(name) + r"(\s*[,:]\s*|\s+)(.+)$", low)
            if m is None:
                continue
            first = name.split()[0]
            if "," not in m.group(1) and ":" not in m.group(1) and (match_word(first, VERBS) or first in FLEET_WORDS):
                continue
            return f"tell {name} {ally_words(m.group(2))}"
        return None

    def _parse_one(self, text: str, said: str) -> ParseResult:
        res = ParseResult(echo=said.strip())
        stop = STOP_ALL.match(text.strip().lower()) or STOP_FIRE.match(text.strip().lower())
        if stop is not None:
            # "hold your fire", "stop attacking", "break off", "never mind", "knock it off": said to the bridge,
            # these stop the shooting (or every officer) at once, never waiting on a language model [E]
            res.commands.append(self._cmd(StandDown if stop.re is STOP_ALL else CeaseFire))
            return res
        tok = Tokens(text)
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
            res.actions.clear()
            res.error = str(e)
        return res

    def _cmd(self, cls: type[Command], **kw: object) -> Command:
        return cls(ship_id=self.ship.id, **kw)  # type: ignore[arg-type]

    def _parse_into(self, tok: Tokens, res: ParseResult) -> None:
        first = tok.next()
        assert first is not None
        if is_num(first):  # bare "90 4" = helm
            tok.i -= 1
            first = "helm"
        if first in ("i", "i've", "ive") and tok.peek() in ("have", "got", "'ve", "has"):
            self._v_ihave(tok, res)
            return
        if first in ("take", "knock") and tok.peek() == "out":
            tok.next()      # "take out their shields": disable them; "take out the Wraith": destroy her [E]
            if any(system_word(w) for w in tok.toks[tok.i:]):
                self._disable_enemy(tok, res)
            else:
                self._v_destroy(tok, res)
            return
        if first == "take" and tok.peek() in ("evasive", "evasion"):
            first = tok.next() or "evasive"       # "take evasive action"
        if first == "stand" and tok.is_word("down"):
            tok.next()
            self._v_standdown(tok, res)
            return
        verb = match_word(first, VERBS)
        if verb is None:
            cands = candidates(first, VERBS) if len(first) >= 2 else []
            if len(cands) > 1:
                verb = self._settle(first, cands, tok)
            else:
                raise ParseError(f"Unknown command '{first}'. Type 'help' for the list.")
        getattr(self, f"_v_{verb}")(tok, res)

    def _settle(self, first: str, cands: list[str], tok: Tokens,
                run: Callable[[str, Tokens, ParseResult], None] | None = None) -> str:
        """A verb prefix shared by several commands ("pu" = pursue or pulse) is settled by the words after it:
        the one command that makes sense of the whole line wins ("pu tal" pursues the Talon). When the words name
        a ship, a command aimed at her beats one that reads her name as something else ("de tal" destroys the
        Talon rather than detonating a probe coded 'tal'); a command that merely ignores the words yields to one
        that reads them. `run` reads the rest of the line for one candidate (by default, the verb's handler)."""
        if run is None:
            run = lambda verb, t, r: getattr(self, f"_v_{verb}")(t, r)  # noqa: E731
        named = self.resolve_ship(Tokens(" ".join(tok.toks[tok.i:])), allow_none=True) if not tok.done() else None
        fits: list[tuple[str, bool, bool]] = []
        for verb in cands:
            trial = Tokens(tok.raw)
            trial.toks, trial.i, trial.max_mount = tok.toks, tok.i, tok.max_mount
            out = ParseResult()
            try:
                run(verb, trial, out)
                trial.skip_filler()
            except ParseError:
                continue
            if trial.done():
                fits.append((verb, named is not None and named in _ships_in(out), trial.swallowed))
        best = [v for v, aimed, _ in fits if aimed] or [v for v, _, swallowed in fits if not swallowed] \
            or [v for v, _, _ in fits]
        if len(best) == 1:
            return best[0]
        raise ParseError(f"'{first}' is ambiguous: {', '.join(best or cands)}.")


def _ships_in(res: ParseResult) -> set[int]:
    """The ships a parsed order is aimed at: its commands' targets and the ship a hail is for."""
    out: set[int] = set()
    for c in res.commands:
        for name in ("target", "ally", "destination"):
            v = getattr(c, name, None)
            if isinstance(v, int):
                out.add(v)
        targets = getattr(c, "targets", None)
        if isinstance(targets, tuple):
            out.update(t for t in targets if isinstance(t, int))
    for name, arg in res.actions:
        if name == "hail" and isinstance(arg, tuple) and isinstance(arg[0], int):
            out.add(arg[0])
    return out


def _stations(tok: "Tokens") -> list[str]:
    tok.skip_filler()
    words = tok.rest()
    if not words or words[0] in ("all", "al", "everything", "stations"):
        return list(STATION_WORDS)
    out: list[str] = []
    for w in words:
        if w in ("and", "station", "stations", "to", "the"):
            continue
        st = match_word(w, STATION_WORDS)
        if st is None:
            raise ParseError(f"No station called '{w}'. Stations: helm, tactical, engineering, science.")
        out.append(st)
    return out


def _after_tokens(raw: str, n: int) -> str:
    """The text of `raw` from its n-th token on (tokens as `Tokens` splits them), untouched."""
    spans = list(re.finditer(r"[^\s,°]+", raw))
    return raw[spans[n].start():] if n < len(spans) else ""


SHUTTLE_CALLS = tuple(n.lower() for n in SHUTTLE_NAMES)


AWAY_CALLS = ("shuttle", "away", "team", "worf", "seven", "sulu", *SHUTTLE_CALLS)   # who a hail to the away team names [E]
