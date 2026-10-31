"""Begin-style command console.

Turns typed orders into the same typed commands the mouse, the AI and the
officers use. Every command in the Begin manual works in its documented
forms ("fire phasers 1 2 3 spread 10", "lock all tubes on bluefin with a
dispersion of 45", "tell the agena to attack the derango"), as do terse
forms ("fir tor al", "fp 1 2 s 10", "al tor al mk7 1200") and the remake's
additions (autoload, fire modes, point defense, bank roles, time control).

As in Begin, any word can be shortened to a unique prefix ("fir tor 1,2,3"),
and words like "the", "to", "at", "on" and "with" are ignored. Mount lists
accept "all"/"al", "1 2 3", "1,2,3", "1 2 and 3" and ranges "1-3". Ships are
named by any unique prefix of their name, or "#<id>" for an unidentified
contact.

The parser never touches the world: it reads an `Observation` and returns
commands for the caller to submit, UI actions, and text displays.
"""

from __future__ import annotations

import difflib
import re
from dataclasses import dataclass, field
from typing import Mapping, Sequence

from ..sim.allies import ORDER_WORDS, SHIP_ORDERS, AllyStanding
from ..sim.commands import (
    AllyOrder, Command, ConfigureAutoload, ControlProbe, DelegateStation, Dock, FirePhasers, FireTorpedoes, LaunchProbe,
    LoadTubes, LockWeapons, Pursue, ReinforceShield, Scan, SelectTarget, SelfDestruct, SetBanks, SetCloak,
    SetFireMode, SetHelm, SetPhaserSpread, SetPointDefense, SetRepairPriority, ManageRepairs, Evasive, AddressCrew, SetShields, SetTubes, Surrender,
    CeaseFire, OpenFire, StandDown, DeflectorPulse, EndObjective, FireAtPoint, FireBait, FireSpecialRound, SetObjective, StartProject, Tractor, Transport, TurnMounts,
)
from ..sim.observation import Observation
from ..sim.ship import HULL, BankRole, FireMode, Kind, PDDoctrine, RepairTarget
from . import reports


class ParseError(Exception):
    pass


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
    ship_id: int
    obs: Observation


# ------------------------------------------------------------------ vocabulary

# canonical verb -> spellings. The first spelling is the primary name: when a prefix
# matches several verbs, the ones whose primary name it abbreviates win ("fir" = fire).
VERBS: dict[str, tuple[str, ...]] = {
    "helm": ("helm", "h", "course", "c"),
    "warp": ("warp", "w", "speed"),
    "pursue": ("pursue", "chase", "follow"),
    "elude": ("elude", "evade", "flee"),
    "evasive": ("evasive", "evasion", "jink"),
    "address": ("address", "rally", "speech"),
    "morale": ("morale", "spirits"),
    "stop": ("stop", "allstop", "halt"),
    "cease": ("cease", "ceasefire"),
    "hold": ("hold", "holdfire"),
    "open": ("open", "openfire"),
    "fire": ("fire", "f", "shoot"),
    "fp": ("fp",),
    "ft": ("ft",),
    "fpr": ("fpr",),
    "phaser": ("phaser", "phasers"),
    "torp": ("torp", "torps", "torpedo", "torpedoes", "torpedos"),
    "probe": ("probe", "probes"),
    "target": ("target", "t", "tgt", "designate"),
    "lock": ("lock", "lk"),
    "turn": ("turn", "point"),
    "load": ("load", "ld"),
    "unload": ("unload", "ul"),
    "autoload": ("autoload", "al"),
    "spread": ("spread", "sp"),
    "enable": ("enable",),
    "disable": ("disable", "disarm", "cripple"),
    "destroy": ("destroy", "eliminate", "annihilate"),
    "capture": ("capture", "seize"),
    "bait": ("bait",),
    "role": ("role",),
    "raise": ("raise", "up"),
    "lower": ("lower", "drop", "down"),
    "reinforce": ("reinforce", "reenforce", "rf"),
    "repair": ("repair",),
    "scan": ("scan", "sc"),
    "design": ("design", "collaborate", "invent"),
    "tachyon": ("tachyon",),
    "range": ("range", "display", "rng", "zoom", "scale"),
    "chart": ("chart",),
    "report": ("report",),
    "damage": ("damage", "dmg"),
    "status": ("status", "st"),
    "banks": ("banks", "bank"),
    "tubes": ("tubes", "tube"),
    "launchers": ("launchers", "launcher"),
    "shields": ("shields", "shield"),
    "fleet": ("fleet",),
    "group": ("group", "groups"),
    "computer": ("computer", "library"),
    "tractor": ("tractor", "tr"),
    "release": ("release",),
    "dock": ("dock",),
    "undock": ("undock",),
    "cloak": ("cloak", "cl"),
    "decloak": ("decloak", "uncloak"),
    "destruct": ("destruct", "self", "selfdestruct", "sd"),
    "abort": ("abort",),
    "surrender": ("surrender",),
    "transport": ("transport", "beam"),
    "board": ("board",),
    "aim": ("aim",),
    "detonate": ("detonate", "det", "boom"),
    "tell": ("tell", "order"),
    "mode": ("mode", "firemode", "fm"),
    "pd": ("pd", "pointdefense", "point-defense", "defense"),
    "pause": ("pause", "p"),
    "resume": ("resume", "go", "unpause"),
    "time": ("time", "x"),
    "help": ("help", "?", "man", "manual", "commands"),
    "coach": ("coach", "advise", "advice", "hint"),
    "quit": ("quit", "exit"),
    "key": ("key",),
    "text": ("text",),
    "delegate": ("delegate", "dg"),
    "assume": ("assume", "takeback"),
    "conn": ("conn",),
    "pulse": ("pulse", "deflector"),
    "crew": ("crew", "bridge", "officers"),
    "ask": ("ask", "say"),
    "translate": ("translate", "interpret", "english"),
    "execute": ("execute", "exec"),
    "orders": ("orders", "plans"),
    "belay": ("belay",),
    "sound": ("sound", "volume", "audio", "mute"),
    "hud": ("hud", "detail"),
    "request": ("request", "reinforcements", "summon"),
}

WEAPONS = {
    "phaser": ("phasers", "phaser", "ph", "banks", "bank", "b"),
    "tube": ("torpedoes", "torpedo", "torpedos", "torps", "torp", "tor", "tubes", "tube", "tu"),
    "launcher": ("probes", "probe", "pr", "launchers", "launcher", "la"),
}

REPAIR_KINDS: dict[str, RepairTarget | None] = {
    "all": None, "none": None, "reactors": Kind.REACTOR, "power": Kind.REACTOR, "core": Kind.REACTOR, "batteries": Kind.BATTERY, "drives": Kind.DRIVE,
    "warp": Kind.DRIVE, "engines": Kind.DRIVE, "impulse": Kind.IMPULSE, "sensors": Kind.SENSORS,
    "computer": Kind.COMPUTER, "shields": Kind.SHIELD, "phasers": Kind.PHASER, "banks": Kind.PHASER,
    "tubes": Kind.TUBE, "torpedoes": Kind.TUBE, "launchers": Kind.LAUNCHER, "probes": Kind.LAUNCHER,
    "transporters": Kind.TRANSPORTER, "tractor": Kind.TRACTOR, "cloak": Kind.CLOAK, "hull": HULL,
}

# what you can aim at, in the words a captain would use; two-word names are joined first ("warp core")
AIM_WORDS: dict[str, tuple[str, ...]] = {
    "shields": ("shields", "shield", "generators", "shieldgenerators"),
    "power": ("power", "reactors", "reactor", "warpcore", "core", "batteries", "battery", "antimatter"),
    "crew": ("lifesupport", "life-support", "crew", "crewdecks", "crewquarters", "quarters", "decks"),
    "weapons": ("weapons", "weapon", "armament", "guns"),
    "phasers": ("phasers", "phaser", "banks", "disruptors", "beams"),
    "torpedoes": ("torpedoes", "tubes", "torps", "torpedo"),
    "propulsion": ("propulsion", "engines", "engine", "drives", "drive", "warp", "nacelles", "impulse", "warpdrive"),
    "sensors": ("sensors", "sensor", "computer", "scanners"),
    "cloak": ("cloak", "cloaking"),
}
AIM_FIRST = {"hull"} | {sp for spellings in AIM_WORDS.values() for sp in spellings}   # words that start an aim
AIM_HELP = "hull, shields, power (warp core), life support (crew), weapons, phasers, torpedoes, propulsion, sensors, cloak"


def _aim_ahead(tok: _Tokens, skip: int = 0) -> bool:
    """A system is named next (after `skip` words), without consuming it."""
    i = tok.i
    tok.i += skip
    try:
        return _take_aim(tok) is not None
    finally:
        tok.i = i


def _take_aim(tok: _Tokens) -> str | None:
    """A subsystem group named next ("warp core", "life support", "shields"), consumed; "hull" gives ""."""
    tok.skip_filler()
    a, b = tok.peek(), tok.peek(1)
    if a is None:
        return None
    if a in ("hull", "ship"):
        tok.next()
        return ""
    if b is not None:
        g = _match(a + b, AIM_WORDS, min_len=99)
        if g is not None:
            tok.next()
            tok.next()
            if tok.peek() in ("system", "systems", "generator", "generators"):
                tok.next()
            return g
    g = _match(a, AIM_WORDS)
    if g is not None:
        tok.next()
        if tok.peek() in ("system", "systems", "generator", "generators"):
            tok.next()
    return g


FILLER = {"with", "the", "to", "at", "on", "of", "and", "set", "please", "by", "using", "for", "a", "an", "from"}

# the manual's command summary, grouped as in its overview (pp. 4-7) plus the 2.0 and remake additions
HELP = [
    "Helm:     helm <course> [warp] <w> · pursue|elude <ship> [warp] <w> · warp <w> · stop · <course> <warp>",
    "          evasive [off] · evasive manoeuvres · take evasive action   (Federation: the helm dodges incoming torpedoes until your next helm order)",
    "Crew:     address crew <your words>   (a speech to the crew lifts morale; once a minute at most) · morale (how the crews feel)",
    "Display:  range|display|scan <range> · chart [on|off|all|<ship>|by name|distance|nation] · report",
    "Status:   status [damage|banks|tubes|launchers|probes|shields|fleet] · damage · banks · tubes · launchers · shields · fleet · group",
    "Phasers:  fire [all] phasers [<list>] [spread] <s> · lock [all] banks [<list>] on <ship> · turn banks [<list>] to <mark>",
    "          enable|disable [all] banks [<list>] · spread <s> · role banks <list> offense|flex|defense",
    "Torps:    fire [all] torpedoes [<list>] [spread <deg>]   (fir tor al, torp 1 2, fire all tor spread 10) · lock [all] tubes [<list>] on <ship> [dispersion <d>]",
    "          turn tubes [<list>] to <mark> · load [all] tubes [<list>] [prox] <p> · unload [all] tubes [<list>] · enable|disable tubes",
    "Hold:     cease fire · hold fire · stop firing   (every weapon stops and officers' objectives end; point defense stays on) · open fire",
    "          stand down   (all that, and every station and the bridge come back to you) · <officer>, stand down (just theirs)",
    "Probes:   fire [all] probes [<list>] at <ship> | course <c> · load launchers [<list>] [prox] <p> [time] <t> · unload launchers",
    "          turn probe <code>|all probes [course] <c> · lock probe <code>|all probes on <ship> · detonate <code>|all · status probes",
    "Shields:  raise|lower|drop [shields] <list>|all · reenforce <n>|off",
    "Ship:     beam|transport <ally> (change ships) · beam <ship> <crew> · board <ship> [<crew>] · repair <system>|hull|all",
    "          tractor <ship>|off · dock <base> [on|off] · undock · cloak on|off · self destruct <cycles> · abort · surrender",
    "Repairs:  repair auto [<officer>] (an officer directs the crews) · repair manual",
    "Allies:   tell|order <ally>|<group#> target|attack|torpedo|phaser|probe <enemy> · hold fire · open fire · disengage",
    "          escort <ally> [at] <range> · course <c> · run · withdraw · cancel · report · approach <ship> <range> · defend <ship>",
    "          stop · dock <base> · undock · tractor <ship> · tow <ship> <dest> · release · board <ship> <n> · join <n> · leave",
    "          recover|eject <ship> (bases)",
    "Library:  computer ship <nation> <class> · computer torpedo <class> · computer probe <class>",
    "Remake:   autoload tor|probe [<list>] [<type>] [<prox>] [time <t>] [on|off] · mode phasers|tubes manual|assisted|automatic",
    "          pd off|conservative|balanced|aggressive [reserve <banks>] · target <ship> [system] · aim <system> · pause · resume · time <x>",
    "Crew:     delegate|assume helm|tactical|engineering|science|all · crew [chatter on|off] · ask <officer> <words>",
    "          I have nav|weapons|fire|phasers|torps|shields|sensors|the conn   (take that station back; its officer's work ends)",
    "          <officer>, <words>   e.g. 'worf, fire all torpedoes' · 'spock, what do you recommend?'",
    "Special:  design tachyon|deflector · tachyon <ship>|<bearing> <range> · pulse · conn <officer>|captain",
    "          disable|cripple <shields|phasers|torpedoes|weapons|engines|sensors> <ships|all> · disable off",
    "          target|take out their <system> · target all their <system>   (the weapons officer knocks it out, then spares her) · target their hull",
    "          destroy <ships> · capture <ship> · bait <ship>   (standing objectives and tricks for Seven)",
    "Orders:   execute order <name> | <name>   (a named order from config/orders.toml) · orders (list them) · belay (stop one running)",
    "Display:  hud detail|simple   (simple: hover a panel for its numbers)",
    "Tour:     request reinforcements   (on a tour of duty: Starfleet sends a ship, which arrives after a delay)",
    "Sound:    sound on|off|<0-100>   sound phaser|torpedo a-d   (M mutes)",
    "Other:    key F<n>|^<x> <commands; separated; by semicolons> · translate on|off|always · help · quit",
]

_NUM = re.compile(r"^[+-]?\d+(\.\d+)?$")


def _is_num(tok: str | None) -> bool:
    return tok is not None and bool(_NUM.match(tok))


def _match(word: str, table: Mapping[str, Sequence[str]], min_len: int = 2) -> str | None:
    """Exact spelling first, then a unique prefix; a prefix of several entries prefers primary names."""
    for key, aliases in table.items():
        if word in aliases:
            return key
    if len(word) < min_len:
        return None
    hits = [key for key, aliases in table.items() if any(a.startswith(word) for a in aliases)]
    if len(hits) > 1:
        primary = [key for key in hits if table[key][0].startswith(word)]
        if primary:
            hits = primary
    return hits[0] if len(hits) == 1 else None


def _candidates(word: str, table: Mapping[str, Sequence[str]]) -> list[str]:
    hits = [key for key, aliases in table.items() if any(a.startswith(word) for a in aliases)]
    primary = [key for key in hits if table[key][0].startswith(word)]
    return primary or hits


# plain-English stop orders said to the bridge at large [E]; "seize fire" is a cease fire, not a capture
_STOP_FIRE = re.compile(
    r"(?:(?:seize|sieze|ceese|sease|ceaze|cese|ceace|ceas)\s+fir(?:e|ing)|hold\s+(?:your|our|all|the)\s+fire|"
    r"(?:don'?t|do\s+not)\s+(?:shoot|fire)|weapons\s+(?:cold|hold|tight|safe)|"
    r"stop\s+(?:attacking|engaging|disabling|targeting|shooting\s+at|firing\s+at|the\s+(?:attack|run))|"
    r"abort\s+(?:the\s+)?(?:attack|run|attack\s+run|objective)|(?:call|break)\s+(?:it\s+)?off|disengage|"
    r"(?:leave|let)\s+(?:them|her|him|it)\s+(?:alone|go|be)|spare\s+(?:them|her|him|it)\b|"
    r"forget\s+(?:the|their|her|its|it|that|about)\b|never\s*mind|"
    r"cancel(?:\s+(?:that|it|this|objective|the\s+(?:order|attack|disable|objective)))?\W*$)")
_STOP_ALL = re.compile(r"(?:stand\s*down|standown|knock\s+it\s+off|that'?s\s+enough|enough)\W*$")

_THEIR_TYPOS = re.compile(r"\b(?:thier|theri|thir|ther|theyre|they're)\b")
_POSSESSIVE = re.compile(r"\b(their|her|its|his|them|enemy|enemies|all|both|every|each)\b|\w's\b|\ws'(?=\s|$)")
# "hit their shields", "bring down her shields", "get their shields down": a disable, when it names their systems
_SOFT_DISABLE = re.compile(r"^(?:hit|shoot(?:\s+at)?|go\s+after|bring\s+down|take\s+down|knock\s+down|get|"
                           r"blast|pound|hammer|concentrate\s+(?:fire\s+)?on)\s+(.+)$")
_WANT_DOWN = re.compile(r"^(?:i want|i need|we need|i'?d like)\s+((?:their|her|its|his)\b.*?)\s+(?:down|out|gone|offline)\W*$")
_REWRITES: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"^all\s+stop\b"), "stop"),                           # "all stop": the engines, as on any bridge
    (re.compile(r"^i'?ll\s+take\s+(?:it\s+from\s+here|over|it)\b"), "i have it"),
    (re.compile(r"^i'?ll\s+(?:take|handle|run)\s+"), "i have "),         # "I'll take the helm"
    (re.compile(r"^i'?ll\s+fly(?:\s+(?:her|it|the\s+ship))?\b"), "i have nav"),
    (re.compile(r"^give\s+me\s+"), "i have "),                          # "give me the helm"
    (re.compile(r"^(?:the\s+)?(\w+)\s+(?:is|are)\s+mine\b"), r"i have \1"),
    (re.compile(r"^stop\s+evading\b|^no\s+more\s+evasive\b"), "evasive off"),
    (re.compile(r"^evasives\b"), "evasive"),
    (re.compile(r"^finish\s+off\s+"), "destroy "),                      # "finish off the Wraith"
    (re.compile(r"^finish\s+(.+?)(?:\s+off)?\W*$"), r"destroy \1"),     # "finish her off"
    (re.compile(r"^take\s+(.+?)\s+out\W*$"), r"take out \1"),          # "take their shields out", "take them all out"
)


def plain_order(text: str) -> str:
    """A captain's plain words in the console's own: typos of 'their', 'I'll take the helm', 'all stop',
    'hit their shields', 'finish her off'. Anything else is left as it was typed."""
    low = text.strip().lower()
    if not low or _SPOKEN.match(low):
        return text          # a message, a hail or a macro: the captain's own words, untouched
    low = _THEIR_TYPOS.sub("their", low)
    for pat, repl in _REWRITES:
        new = pat.sub(repl, low, count=1)
        if new != low:
            return new
    m = _WANT_DOWN.match(low)
    if m is not None and any(_system_word(w) for w in m.group(1).split()):
        return f"disable {m.group(1)}"           # "I want their shields down"
    m = _SOFT_DISABLE.match(low)
    if m is not None and _POSSESSIVE.search(m.group(1)) and any(_system_word(w) for w in m.group(1).split()):
        return f"disable {m.group(1)}"
    return low if low != text.strip().lower() else text


# a later order in the same line starts with a verb: "cease fire and take evasive action", "stand down, I have nav"
_SPLIT = re.compile(r"\s*(?:[,;]|\band\s+then\b|\bthen\b|\band\b)\s*")
_NO_SPLIT = ("tell", "order", "key", "address", "ask", "say", "text", "translate", "interpret", "english")
# words said over a channel to another captain are theirs to hear, never orders to our own bridge:
# "hail them, stand down and you will live"
_SPOKEN = re.compile(r"^(?:(?:" + "|".join(_NO_SPLIT) + r"|hail|hailing|channel)\b|"
                     r"open\s+(?:a\s+)?(?:channel|hailing|frequencies|comms|communications)\b)")


def _starts_order(piece: str) -> bool:
    first = (piece.split() or [""])[0].rstrip("!?.")
    if not first or _is_num(first) or _system_word(first) or first in AIM_FIRST:
        return False
    return first in ("i", "i've", "ive", "i'll", "ill", "stand", "take", "knock", "all", "give", "finish") or \
        _match(first, VERBS) is not None or bool(_STOP_FIRE.match(piece) or _STOP_ALL.match(piece))


def split_orders(text: str) -> list[str]:
    """The separate orders in a line, where each after the first plainly starts a new one; else the line."""
    low = text.strip()
    if not low or _SPOKEN.match(low.lower()):
        return [low]
    pieces: list[str] = []
    start = 0
    for m in _SPLIT.finditer(low):
        if m.start() == 0:
            continue
        after = low[m.end():].lower()
        if _starts_order(after):
            pieces.append(low[start:m.start()])
            start = m.end()
    pieces.append(low[start:])
    pieces = [p.strip(" ,;") for p in pieces if p.strip(" ,;")]
    if len(pieces) > 1 and not _starts_order(pieces[0].lower()):
        return [low]         # "7, stand down": the first part is no order of its own
    return [plain_order(p) for p in pieces] if len(pieces) > 1 else [low]


def _system_word(word: str) -> str | None:
    """The enemy system a word names ("shields", "torps"), allowing for a slip of the keyboard ("sheilds")."""
    w = word.strip(".!?;'\"").removesuffix("'s").removesuffix("s'")
    hit = Parser._DISABLE_WORDS.get(w)
    if hit is not None or len(w) < 5:
        return hit
    close = difflib.get_close_matches(w, list(Parser._DISABLE_WORDS), n=1, cutoff=0.8)
    return Parser._DISABLE_WORDS[close[0]] if close else None


class _Tokens:
    def __init__(self, text: str) -> None:
        self.raw = text
        text = text.replace(",", " ").replace("°", " ")
        text = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", text.lower())      # "cease-fire", "stand-down"
        # "Cease fire!", "evasive!", "stand down." : the punctuation that ends an order is not part of a word
        self.toks = [t if _is_num(t) else (t.rstrip("!?.") or t) for t in text.split()]
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

    def rest(self) -> list[str]:
        out = self.toks[self.i:]
        self.i = len(self.toks)
        return out

    def skip_filler(self) -> None:
        while self.peek() in FILLER:
            self.i += 1

    def is_word(self, *words: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t is not None and any(t == w or (len(t) >= 2 and w.startswith(t)) for w in words)

    def take_word(self, *words: str) -> bool:
        """Consume the next token if it is (a prefix ≥ 2 of) one of `words`."""
        self.skip_filler()
        if self.is_word(*words):
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
        if _is_num(t):
            self.i += 1
            return float(t)  # type: ignore[arg-type]
        return None

    def is_mount(self, t: str | None) -> bool:
        if t is None:
            return False
        if re.match(r"^\d+-\d+$", t):
            return True
        return t.isdigit() and 1 <= int(t) <= self.max_mount

    def mount_list(self) -> tuple[int, ...] | None:
        """'all'/'al' → None; '1 2', '1,2', '1 2 and 3', '1-3' → zero-based indices; nothing → None."""
        self.skip_filler()
        t = self.peek()
        if t in ("all", "al", "every"):
            self.i += 1
            return None
        out: list[int] = []
        while True:
            t = self.peek()
            if t == "and" and out and self.is_mount(self.peek(1)):
                self.i += 1
                continue
            if t is None or not self.is_mount(t):
                break
            m = re.match(r"^(\d+)-(\d+)$", t)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                out.extend(range(min(a, b) - 1, max(a, b)))
            else:
                out.append(int(t) - 1)
            self.i += 1
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
        if t in ("me", "us", "flagship") and not any(n == t for n, _ in self._ship_table()):
            tok.next()  # 'tell tau escort me'
            return self.ship.id
        table = self._ship_table()
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

    def _ship_name(self, sid: int) -> str:
        s = self.obs.own(sid)
        if s is not None:
            return s.name
        c = self.obs.contact(sid)
        return c.label.split(" (")[0] if c is not None else f"#{sid}"

    # entry -------------------------------------------------------------
    def parse(self, text: str) -> ParseResult:
        """One line; several orders in it ("cease fire and take evasive action") are carried out in turn."""
        plain = plain_order(text)
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

    def _parse_one(self, text: str, said: str) -> ParseResult:
        res = ParseResult(echo=said.strip())
        stop = _STOP_ALL.match(text.strip().lower()) or _STOP_FIRE.match(text.strip().lower())
        if stop is not None:
            # "hold your fire", "stop attacking", "break off", "never mind", "knock it off": said to the bridge,
            # these stop the shooting (or every officer) at once, never waiting on a language model [E]
            res.commands.append(self._cmd(StandDown if stop.re is _STOP_ALL else CeaseFire))
            return res
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
            res.actions.clear()
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
        if first in ("i", "i've", "ive") and tok.peek() in ("have", "got", "'ve", "has"):
            self._v_ihave(tok, res)
            return
        if first in ("take", "knock") and tok.peek() == "out":
            tok.next()      # "take out their shields": disable them; "take out the Wraith": destroy her [E]
            if any(_system_word(w) for w in tok.toks[tok.i:]):
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
        verb = _match(first, VERBS)
        if verb is None:
            cands = _candidates(first, VERBS) if len(first) >= 2 else []
            if len(cands) > 1:
                raise ParseError(f"'{first}' is ambiguous: {', '.join(cands)}.")
            raise ParseError(f"Unknown command '{first}'. Type 'help' for the list.")
        getattr(self, f"_v_{verb}")(tok, res)

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
        if course is not None and not -360 <= course <= 360:
            raise ParseError("Course must be between -360 and +360 degrees.")
        res.commands.append(self._cmd(SetHelm, course=course % 360 if course is not None else None, warp=warp))

    def _v_warp(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(SetHelm, warp=tok.number("warp")))

    def _v_stop(self, tok: _Tokens, res: ParseResult) -> None:
        if tok.take_word("firing", "fire", "shooting", "weapons"):
            res.commands.append(self._cmd(CeaseFire))     # "stop firing": cease fire, not all stop [E]
            return
        if tok.take_word("everything", "everyone", "everybody", "all"):
            self._v_standdown(tok, res)                   # "stop everything": the officers stand down [E]
            return
        res.commands.append(self._cmd(SetHelm, warp=0.0))

    # cease fire [E] ----------------------------------------------------
    def _v_cease(self, tok: _Tokens, res: ParseResult) -> None:
        """`cease fire`: every weapon stops, officers' objectives end, until you fire or say open fire."""
        tok.take_word("fire", "firing")
        res.commands.append(self._cmd(CeaseFire))

    def _v_hold(self, tok: _Tokens, res: ParseResult) -> None:
        if not tok.take_word("fire", "firing") and tok.peek() is not None:
            raise ParseError("Hold what? 'hold fire' stops every weapon.")
        res.commands.append(self._cmd(CeaseFire))

    def _v_standdown(self, tok: _Tokens, res: ParseResult) -> None:
        """`stand down [all|everyone]` [E]: cease fire, every objective ends, every station and the bridge
        come back to the captain, and the helm steadies."""
        tok.rest()
        res.commands.append(self._cmd(StandDown))

    def _v_ihave(self, tok: _Tokens, res: ParseResult) -> None:
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

    def _v_open(self, tok: _Tokens, res: ParseResult) -> None:
        if not tok.take_word("fire") and tok.peek() is not None:
            raise ParseError("Open what? 'open fire' lifts a cease fire.")
        res.commands.append(self._cmd(OpenFire))

    def _pursue(self, tok: _Tokens, res: ParseResult, elude: bool) -> None:
        target = self.resolve_ship(tok)
        if tok.take_word("warp", "w"):
            warp: float | None = tok.number("warp")
        else:
            warp = tok.opt_number()
        res.commands.append(self._cmd(Pursue, target=target, warp=warp, elude=elude))

    def _v_pursue(self, tok: _Tokens, res: ParseResult) -> None:
        self._pursue(tok, res, False)

    def _v_elude(self, tok: _Tokens, res: ParseResult) -> None:
        tok.skip_filler()
        if tok.done() or tok.is_word("torpedoes", "torps", "incoming"):
            self._v_evasive(tok, res)    # 'evade' with no ship to run from: evasive manoeuvres
            return
        self._pursue(tok, res, True)

    def _v_address(self, tok: _Tokens, res: ParseResult) -> None:
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

    def _v_morale(self, tok: _Tokens, res: ParseResult) -> None:
        tok.rest()
        res.display.extend(reports.morale_lines(self.obs))

    def _v_evasive(self, tok: _Tokens, res: ParseResult) -> None:
        """evasive [manoeuvres|action] [on|off]: the helm dodges incoming torpedoes until the next navigation order."""
        off = False
        while not tok.done():
            w = tok.next() or ""
            if w in ("off", "cancel", "stop", "end", "belay"):
                off = True
        res.commands.append(self._cmd(Evasive, on=not off))

    # targeting -------------------------------------------------------------
    def _v_target(self, tok: _Tokens, res: ParseResult) -> None:
        lead = tok.peek()
        if tok.take_word("off", "none", "clear"):
            res.commands.append(self._cmd(SelectTarget, target=None))
            return
        tok.skip_filler()
        rest = [w.strip(".!?;'\"").removesuffix("'s").removesuffix("s'") for w in tok.toks[tok.i:]]
        whose = lead in ("the", "her", "its", "his") or (bool(rest) and (
            rest[0] in self._THEIR or rest[0] in self._FACTIONS or rest[0].rstrip("s") in self._FACTIONS
            or tok.toks[tok.i].endswith(("'s", "s'"))))
        if whose and any(_system_word(w) for w in rest):
            # "target their shields", "target her engines", "target the Klingons' shields", "target all their
            # torps": an officer knocks that system out and stops there [E]
            self._disable_enemy(tok, res)
            return
        if tok.peek() in ("their", "her", "its", "his", "the") and self.ship.target is not None:
            tok.next()                          # "target their hull", "target their life support": the current target
        if self.ship.target is not None and (tok.peek() in AIM_FIRST or _aim_ahead(tok)):
            target = self.ship.target
        else:
            target = self.resolve_ship(tok)
        sub = None
        tok.skip_filler()
        hull = False
        if not tok.done():
            g = _take_aim(tok)
            if g is None:
                raise ParseError(f"I don't know the system '{tok.peek()}'. Aim at: {AIM_HELP}.")
            sub, hull = g or None, g == ""
        res.commands.append(self._cmd(SelectTarget, target=target, subsystem=sub, hull=hull))

    def _v_aim(self, tok: _Tokens, res: ParseResult) -> None:
        """`aim [at] <system>`: precision fire at a system of the current target ('aim warp core', 'aim life support')."""
        tok.skip_filler()
        if tok.peek() in ("their", "her", "its", "his") and _system_word(tok.peek(1) or ""):
            self._disable_enemy(tok, res)      # "aim at their shields": as 'target their shields' [E]
            return
        if tok.peek() in ("their", "her", "its", "his"):
            tok.next()
        g = _take_aim(tok)
        if g is None:
            raise ParseError(f"Aim at what? {AIM_HELP}." if tok.done() else
                             f"I don't know the system '{tok.peek()}'. Aim at: {AIM_HELP}.")
        if self.ship.target is None:
            raise ParseError("No target to aim at: 'target <ship>' first.")
        res.commands.append(self._cmd(SelectTarget, target=self.ship.target, subsystem=g or None, hull=g == ""))

    def _weapon(self, tok: _Tokens, default: str | None = None) -> tuple[str, bool]:
        """Weapon noun, with Begin's optional leading 'all' ('all torpedo tubes', 'all banks', 'tor').

        Returns (weapon, all_given)."""
        tok.skip_filler()
        all_given = False
        if tok.peek() in ("all", "al", "every") and _match(tok.peek(1) or "", WEAPONS) is not None:
            tok.next()
            all_given = True
        t = tok.peek()
        w = _match(t, WEAPONS) if t else None
        if w is None:
            if default is not None:
                return default, all_given
            raise ParseError("Which weapons? phasers, torpedoes or probes.")
        tok.next()
        while tok.peek() is not None and _match(tok.peek() or "", WEAPONS) == w:
            tok.next()
        return w, all_given

    def _mounts(self, tok: _Tokens, all_given: bool) -> tuple[int, ...] | None:
        m = tok.mount_list()
        return None if all_given else m

    # lock / turn ------------------------------------------------------------
    def _v_lock(self, tok: _Tokens, res: ParseResult) -> None:
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
        if tok.is_word("all") and _match(tok.peek(1) or "", WEAPONS) is None:
            tok.next()
        else:
            t = tok.peek()
            if t is not None and (_match(t, WEAPONS) is not None or t in ("all", "al")):
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

    def _v_turn(self, tok: _Tokens, res: ParseResult) -> None:
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
            elif _is_num(t) or (t and re.match(r"^\d+-\d+$", t)):
                nums.append(tok.next() or "")
            else:
                break
        if not nums:
            raise ParseError("Turn to which mark? e.g. 'turn banks 1 2 to 90'.")
        mark = float(nums.pop())
        sub = _Tokens(" ".join(nums))
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

    # fire ------------------------------------------------------------
    def _v_fp(self, tok: _Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "phaser", False)

    def _v_ft(self, tok: _Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "tube", False)

    def _v_fpr(self, tok: _Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "launcher", False)

    def _v_phaser(self, tok: _Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "phaser", False)

    def _v_torp(self, tok: _Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "tube", False)

    def _v_probe(self, tok: _Tokens, res: ParseResult) -> None:
        self._fire(tok, res, "launcher", False)

    def _v_fire(self, tok: _Tokens, res: ParseResult) -> None:
        w, all_given = self._weapon(tok, "phaser")
        self._fire(tok, res, w, all_given)

    def _fire(self, tok: _Tokens, res: ParseResult, weapon: str, all_given: bool) -> None:
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
            elif _is_num(tok.peek()):
                v = float(tok.next() or 0)
                if weapon == "phaser":
                    spread = v           # 'fire all phasers 45', 'phaser all 45'
                elif weapon == "launcher":
                    course = v
                else:
                    raise ParseError(f"Torpedo tube {v:g} does not exist.")
            elif tok.peek() in FILLER:
                tok.next()
            elif tok.peek() in ("their", "her", "its", "his") and _aim_ahead(tok, 1):
                tok.next()              # "fire phasers at their shields": the current target, aimed
            elif (g := _take_aim(tok)) is not None:
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

    # loading -------------------------------------------------------------
    def _v_load(self, tok: _Tokens, res: ParseResult) -> None:
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
            elif _is_num(tok.peek()):
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

    def _v_unload(self, tok: _Tokens, res: ParseResult) -> None:
        w, all_given = self._weapon(tok, "tube")
        if w == "phaser":
            raise ParseError("Phaser banks can't be unloaded; use 'disable banks'.")
        res.commands.append(self._cmd(LoadTubes, tubes=self._mounts(tok, all_given), unload=True, weapon=w))

    def _ordnance(self, tok: _Tokens, weapon: str) -> str:
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

    def _v_autoload(self, tok: _Tokens, res: ParseResult) -> None:
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
            elif _is_num(tok.peek()):
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

    # phaser settings -------------------------------------------------------------
    def _v_spread(self, tok: _Tokens, res: ParseResult) -> None:
        _, all_given = self._weapon(tok, "phaser")
        mounts = self._mounts(tok, all_given)
        res.commands.append(self._cmd(SetPhaserSpread, spread=tok.number("spread"), banks=mounts))

    def _enable(self, tok: _Tokens, res: ParseResult, on: bool) -> None:
        w, all_given = self._weapon(tok)
        mounts = self._mounts(tok, all_given)
        if w == "phaser":
            res.commands.append(self._cmd(SetBanks, banks=mounts, enabled=on))
        elif w == "tube":
            res.commands.append(self._cmd(SetTubes, tubes=mounts, enabled=on))
        else:
            raise ParseError("Probe launchers need no charging; use 'load' or 'unload launchers'.")

    def _v_enable(self, tok: _Tokens, res: ParseResult) -> None:
        self._enable(tok, res, True)

    def _v_disable(self, tok: _Tokens, res: ParseResult) -> None:
        """`disable tubes 1 2` switches off your own weapons; `disable gorkon shields` (or `cripple ...`) sets
        an officer to knock out the enemy's."""
        if self._about_enemy(tok):
            self._disable_enemy(tok, res)
        else:
            self._enable(tok, res, False)

    def _about_enemy(self, tok: _Tokens) -> bool:
        verb = tok.toks[tok.i - 1] if tok.i > 0 else "disable"
        if not verb.startswith("disable"):
            return True
        words = [w.strip(".!?;'\"").removesuffix("'s").removesuffix("s'") for w in tok.toks[tok.i:]]
        own = {"all", "bank", "banks", "tube", "tubes", "launcher", "launchers", "phaser", "phasers", "torpedo",
               "torpedoes", "torps", "tor", "ph", "la", "b", "tu", "pr", "probes", "probe"}
        return any(w and not w.isdigit() and w not in own for w in words)

    def _v_role(self, tok: _Tokens, res: ParseResult) -> None:
        _, all_given = self._weapon(tok, "phaser")
        mounts = self._mounts(tok, all_given)
        roles = {"offense": ("offense", "offence", "attack"), "flex": ("flex", "both"),
                 "defense": ("defense", "defence", "pd", "reserve")}
        r = _match(tok.next() or "", roles)
        if r is None:
            raise ParseError("Role must be offense, flex or defense.")
        res.commands.append(self._cmd(SetBanks, banks=mounts, role=BankRole(r)))

    def _v_mode(self, tok: _Tokens, res: ParseResult) -> None:
        w, all_given = self._weapon(tok)
        if w == "launcher":
            raise ParseError("Probes are always launched by order.")
        mounts = self._mounts(tok, all_given)
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
    def _shield_list(self, tok: _Tokens) -> tuple[int, ...] | None:
        all_given = tok.take_word("all")
        tok.take_word("shields", "shield")
        mounts = tok.mount_list()
        if tok.take_word("all"):
            all_given = True
        tok.take_word("shields", "shield")
        return None if all_given else mounts

    def _v_raise(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(SetShields, sectors=self._shield_list(tok), up=True))

    def _v_lower(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(SetShields, sectors=self._shield_list(tok), up=False))

    def _v_reinforce(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("shield")
        if tok.take_word("off", "none", "clear"):
            res.commands.append(self._cmd(ReinforceShield, sector=None))
            return
        n = int(tok.number("shield"))
        if not 1 <= n <= max(1, len(self.ship.shields)):
            raise ParseError(f"Shields are numbered 1 to {len(self.ship.shields)}.")
        res.commands.append(self._cmd(ReinforceShield, sector=n - 1))

    # status displays -------------------------------------------------------
    def _v_status(self, tok: _Tokens, res: ParseResult) -> None:
        what = {"damage": ("damage", "ship"), "banks": ("banks", "phasers", "bank"), "tubes": ("tubes", "torpedoes", "tube"),
                "launchers": ("launchers", "launcher"), "probes": ("probes", "probe"), "shields": ("shields", "shield"),
                "fleet": ("fleet", "allies"), "report": ("report",), "group": ("group", "groups")}
        t = tok.next()
        k = _match(t, what) if t else "damage"
        if k is None:
            raise ParseError("status damage, banks, tubes, launchers, probes, shields or fleet.")
        if k == "probes":
            res.display.extend(reports.probes_lines(self.obs, self.ship))
        else:
            getattr(self, f"_v_{k}")(tok, res)

    def _v_report(self, tok: _Tokens, res: ParseResult) -> None:
        res.display.extend(reports.report_lines(self.obs, self.ship))

    def _v_damage(self, tok: _Tokens, res: ParseResult) -> None:
        res.display.extend(reports.damage_lines(self.obs, self.ship))

    def _v_banks(self, tok: _Tokens, res: ParseResult) -> None:
        res.display.extend(reports.banks_lines(self.obs, self.ship))

    def _v_tubes(self, tok: _Tokens, res: ParseResult) -> None:
        res.display.extend(reports.tubes_lines(self.obs, self.ship))

    def _v_launchers(self, tok: _Tokens, res: ParseResult) -> None:
        res.display.extend(reports.launchers_lines(self.obs, self.ship))

    def _v_shields(self, tok: _Tokens, res: ParseResult) -> None:
        if tok.take_word("up", "raise", "on"):
            res.commands.append(self._cmd(SetShields, sectors=self._shield_list(tok), up=True))
        elif tok.take_word("down", "lower", "drop", "off"):
            res.commands.append(self._cmd(SetShields, sectors=self._shield_list(tok), up=False))
        else:
            res.display.extend(reports.shields_lines(self.obs, self.ship))

    def _v_fleet(self, tok: _Tokens, res: ParseResult) -> None:
        tok.rest()  # Begin accepts (and ignores) display options here
        res.display.extend(reports.fleet_lines(self.obs, self.ship.id))

    def _v_group(self, tok: _Tokens, res: ParseResult) -> None:
        res.display.extend(reports.group_lines(self.obs))

    def _v_chart(self, tok: _Tokens, res: ParseResult) -> None:
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
            sort = _match(tok.next() or "", {"name": ("name",), "distance": ("distance", "range"), "nation": ("nation", "side")})
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

    def _v_range(self, tok: _Tokens, res: ParseResult) -> None:
        """Begin's `range <r>` / `display <r>` / `scan <r>`: set the position display range; bare `range` reports it."""
        v = tok.opt_number()
        if v is not None and not (200 <= v <= 500000):
            raise ParseError("Display range must be between 200 and 500,000 units.")
        res.actions.append(("range", v))

    def _v_scan(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("range")
        if _is_num(tok.peek()) or (tok.peek() in FILLER and _is_num(tok.peek(1))):
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
            res.display.extend(reports.scan_lines(self.obs, c))
        res.commands.append(self._cmd(Scan, target=target))

    def _v_computer(self, tok: _Tokens, res: ParseResult) -> None:
        res.display.extend(reports.library_lines(self.obs.content, tok.rest()))

    # engineering and specials ----------------------------------------------------
    def _v_repair(self, tok: _Tokens, res: ParseResult) -> None:
        if tok.take_word("auto", "officer", "delegate"):
            # an officer directs the crews; with no name, the ship's science officer (Spock) or engineer
            res.commands.append(self._cmd(ManageRepairs, officer=" ".join(tok.rest()).strip().lower() or "auto"))
            return
        if tok.take_word("manual", "captain", "myself"):
            res.commands.append(self._cmd(ManageRepairs, officer=""))
            return
        w = tok.next() or "all"
        k = _match(w, {k: (k,) for k in REPAIR_KINDS})
        if k is None:
            raise ParseError(f"Unknown system '{w}'.")
        res.commands.append(self._cmd(SetRepairPriority, kind=REPAIR_KINDS[k]))

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
        if tok.take_word("off"):
            res.commands.append(self._cmd(Dock, host=None))
            return
        tok.take_word("on")
        res.commands.append(self._cmd(Dock, host=host))

    def _v_undock(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(Dock, host=None))

    def _v_design(self, tok: _Tokens, res: ParseResult) -> None:
        """`design tachyon`: Spock and Seven build a one-off special round [E]."""
        from ..sim.projects import PROJECTS

        tok.skip_filler()
        word = (tok.peek() or "").lower()
        hits = [p for p in PROJECTS if p.startswith(word)] if word else []
        if len(hits) != 1:
            raise ParseError(f"Design what? Known: {', '.join(PROJECTS)}.")
        tok.rest()
        res.commands.append(self._cmd(StartProject, project=hits[0]))

    def _v_tachyon(self, tok: _Tokens, res: ParseResult) -> None:
        """`tachyon <bearing> <range>`, `tachyon <ship>` or bare `tachyon` (at the target): burst the detector there."""
        import math

        tok.take_word("fire", "at", "toward", "towards")
        tok.skip_filler()
        if _is_num(tok.peek()):
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

    def _v_cloak(self, tok: _Tokens, res: ParseResult) -> None:
        on = not tok.take_word("off")
        tok.take_word("on")
        res.commands.append(self._cmd(SetCloak, on=on))

    def _v_decloak(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(SetCloak, on=False))

    def _v_destruct(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("destruct")
        if tok.take_word("abort", "off", "cancel"):
            res.commands.append(self._cmd(SelfDestruct, cycles=None))
            return
        n = tok.opt_number()
        if n is None:
            raise ParseError("Self destruct in how many cycles? e.g. 'self destruct 10'.")
        res.commands.append(self._cmd(SelfDestruct, cycles=n))

    def _v_abort(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("destruct")
        res.commands.append(self._cmd(SelfDestruct, cycles=None))

    def _v_surrender(self, tok: _Tokens, res: ParseResult) -> None:
        res.commands.append(self._cmd(Surrender))

    def _v_transport(self, tok: _Tokens, res: ParseResult) -> None:
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

    def _v_board(self, tok: _Tokens, res: ParseResult) -> None:
        target = self.resolve_ship(tok)
        n = tok.opt_number()
        if n is None:
            n = self.ship.boarding_party()
        res.commands.append(self._cmd(Transport, target=target, count=int(n)))

    def _v_detonate(self, tok: _Tokens, res: ParseResult) -> None:
        tok.take_word("probe", "probes")
        if tok.take_word("all") or tok.done():
            tok.take_word("probes", "probe")
            res.commands.append(self._cmd(ControlProbe, code=None, detonate=True))
        else:
            res.commands.append(self._cmd(ControlProbe, code=tok.next(), detonate=True))

    # allies ----------------------------------------------------------------
    def _ally_targets(self, tok: _Tokens) -> list[int]:
        tok.skip_filler()
        t = tok.peek()
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

    def _v_tell(self, tok: _Tokens, res: ParseResult) -> None:
        allies = self._ally_targets(tok)
        tok.skip_filler()
        word = tok.next()
        if word is None:
            raise ParseError("Tell them what? e.g. 'tell <ally> attack <ship>'.")
        # two-word forms: hold fire / hold course / open fire / cease fire
        if word in ("hold", "cease") and tok.is_word("course"):
            tok.next()
            order = "course"
        else:
            order = _match(word, ORDER_WORDS) or ""
            if not order:
                cands = _candidates(word, ORDER_WORDS)
                raise ParseError(f"'{word}' is ambiguous: {', '.join(cands)}." if len(cands) > 1
                                 else f"Unknown order '{word}'. Try 'help'.")
            if order in ("hold", "open"):
                tok.take_word("fire")
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

    def _v_help(self, tok: _Tokens, res: ParseResult) -> None:
        """`help` / `man` opens the manual; `help <command>` opens that command's page."""
        query = " ".join(tok.rest())
        res.actions.append(("manual", query or None))

    def _v_coach(self, tok: _Tokens, res: ParseResult) -> None:
        tok.rest()
        res.actions.append(("manual", "coach"))

    def _v_quit(self, tok: _Tokens, res: ParseResult) -> None:
        res.actions.append(("quit", None))

    def _v_execute(self, tok: _Tokens, res: ParseResult) -> None:
        """`execute [order] <name>`: run one of the captain's named orders (config/orders.toml)."""
        tok.take_word("order", "plan")
        name = " ".join(tok.rest()).strip()
        if not name:
            raise ParseError("Execute which order? Type 'orders' to list them.")
        res.actions.append(("execute", name))

    def _v_orders(self, tok: _Tokens, res: ParseResult) -> None:
        tok.rest()
        res.actions.append(("orders", None))

    def _v_belay(self, tok: _Tokens, res: ParseResult) -> None:
        """`belay [that|order]`: stop the named order that is running, and cease fire;
        `belay all|everything`: and the officers stand down too."""
        everything = any(w in ("all", "everything", "everyone", "everybody") for w in tok.rest())
        res.actions.append(("belay", None))
        res.commands.append(self._cmd(StandDown if everything else CeaseFire))   # and whatever the officers had going

    def _v_request(self, tok: _Tokens, res: ParseResult) -> None:
        """`request reinforcements` [E]: on a tour of duty, ask Starfleet for a ship; she arrives after the stop's ETA."""
        tok.take_word("reinforcements", "reinforcement", "backup", "help", "support", "assistance", "starfleet")
        tok.rest()
        res.actions.append(("reinforcements", None))

    def _v_hud(self, tok: _Tokens, res: ParseResult) -> None:
        """`hud detail|simple`: every number on the panels, or only what matters (hover a panel to see the rest)."""
        first = tok.toks[0] if tok.toks else ""
        w = tok.next()
        if w is None:
            res.actions.append(("hud", "detail" if first == "detail" else None))
        elif w in ("detail", "detailed", "full", "all", "on", "more"):
            res.actions.append(("hud", "detail"))
        elif w in ("simple", "less", "off", "minimal", "clean"):
            res.actions.append(("hud", "simple"))
        else:
            raise ParseError("hud detail (every number on the panels) or hud simple (hover a panel for the rest).")

    def _v_sound(self, tok: _Tokens, res: ParseResult) -> None:
        """`sound on|off|<0-100>`, `sound phaser b`: the battle's sound effects and which version (M mutes too)."""
        first = tok.toks[0] if tok.toks else ""
        w = tok.next()
        if first == "mute" and w is None:
            res.actions.append(("sound", "off"))
        elif w is None:
            res.actions.append(("sound", None))
        elif w in ("on", "off"):
            res.actions.append(("sound", w))
        elif _is_num(w) and 0 <= float(w) <= 100:
            res.actions.append(("sound", float(w)))
        elif w in ("phaser", "phasers", "torpedo", "torpedoes", "launch"):
            which = "phaser" if w.startswith("phaser") else "torpedo"
            v = tok.next()
            if v is not None and v not in ("a", "b", "c", "d"):
                raise ParseError(f"sound {which} a, b, c or d: the versions of the {which} sound.")
            res.actions.append(("sound", (which, v)))
        else:
            raise ParseError("sound on, sound off, sound <0-100> for the volume, or sound phaser|torpedo a|b|c|d.")

    def _v_translate(self, tok: _Tokens, res: ParseResult) -> None:
        """`translate on|off|always`: plain-English console input through the language model [E]."""
        w = tok.next()
        if w is None:
            res.actions.append(("translate", None))
            return
        mode = _match(w, {"fallback": ("on", "fallback", "auto"), "off": ("off", "never"), "always": ("always", "all")})
        if mode is None:
            raise ParseError("translate on, translate off or translate always.")
        res.actions.append(("translate", mode))

    def _v_text(self, tok: _Tokens, res: ParseResult) -> None:
        res.info.append("This remake has no text mode: the tactical display is always on. "
                        "Status commands print Begin's text displays here in the console.")

    # bridge officers (remake extension) ---------------------------------
    def _v_delegate(self, tok: _Tokens, res: ParseResult) -> None:
        for st in _stations(tok):
            res.commands.append(self._cmd(DelegateStation, station=st, on=True))

    def _v_assume(self, tok: _Tokens, res: ParseResult) -> None:
        for st in _stations(tok):
            res.commands.append(self._cmd(DelegateStation, station=st, on=False))

    _DISABLE_WORDS: dict[str, str] = {
        **dict.fromkeys(("shield", "shields", "deflector", "deflectors", "screens"), "shields"),
        **dict.fromkeys(("phaser", "phasers", "banks", "beams", "disruptor", "disruptors", "beam"), "phasers"),
        **dict.fromkeys(("torpedo", "torpedoes", "torpedos", "torps", "torp", "tubes", "tube", "launchers"),
                        "torpedoes"),
        **dict.fromkeys(("weapon", "weapons", "guns", "armament", "arms"), "weapons"),
        **dict.fromkeys(("engine", "engines", "drive", "drives", "warp", "impulse", "propulsion"), "propulsion"),
        **dict.fromkeys(("sensor", "sensors", "eyes"), "sensors"),
        **dict.fromkeys(("cloak", "cloaking"), "cloak"),
    }
    _THEIR = ("their", "all", "every", "everyone", "everybody", "them", "enemy", "enemies", "each", "both")
    _EVERYONE = ("all", "everyone", "everybody", "them", "enemy", "enemies", "both", "every", "each", "they")
    _FACTIONS = {"klingon": "klingon", "romulan": "romulan", "orion": "orion", "federation": "federation",
                 "pirate": "orion", "pirates": "orion"}

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

    def _v_destroy(self, tok: _Tokens, res: ParseResult) -> None:
        """`destroy <ships|all|klingons>`: an officer's standing order to take the ships out [E]."""
        words = [w.strip(".!?;'\"").removesuffix("'s").removesuffix("s'") for w in tok.rest()]
        words = [w for w in words if w]
        if any(w in ("off", "cancel", "stop", "belay", "abort") for w in words):
            res.commands.append(self._cmd(EndObjective, group="hull", outcome="cancelled"))
            return
        res.commands.append(self._cmd(SetObjective, goal="destroy", group="hull", targets=self._enemy_targets(words)))

    def _v_capture(self, tok: _Tokens, res: ParseResult) -> None:
        """`capture <ship>`: open a shield, thin her crew through the gap, board her and keep her [E]."""
        words = [w.strip(".!?;'\"").removesuffix("'s").removesuffix("s'") for w in tok.rest()]
        words = [w for w in words if w]
        if any(w in ("off", "cancel", "stop", "belay", "abort") for w in words):
            res.commands.append(self._cmd(EndObjective, group="crew", outcome="cancelled"))
            return
        res.commands.append(self._cmd(SetObjective, goal="capture", group="crew", targets=self._enemy_targets(words)))

    def _v_bait(self, tok: _Tokens, res: ParseResult) -> None:
        """`bait [ship]`: one torpedo to draw their point defense, the rest a cycle later [E]."""
        tok.take_word("at")
        sid = self.resolve_ship(tok, allow_none=True)
        res.commands.append(self._cmd(FireBait, target=sid if sid is not None else self.ship.target))

    def _disable_enemy(self, tok: _Tokens, res: ParseResult) -> None:
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
        groups = list(dict.fromkeys(g for w in words if (g := _system_word(w)) is not None))
        if not groups and verb.startswith("disarm"):
            groups = ["weapons"]
        if not groups:
            raise ParseError("Disable what? shields, phasers, torpedoes, weapons, engines, sensors or cloak.")
        if "weapons" in groups:
            groups = [g for g in groups if g not in ("phasers", "torpedoes")]   # 'weapons' covers both
        targets = self._enemy_targets([w for w in words if _system_word(w) is None])
        for group in groups:
            res.commands.append(self._cmd(SetObjective, goal="disable", group=group, targets=targets))

    def _v_pulse(self, tok: _Tokens, res: ParseResult) -> None:
        """`pulse`: sweep the cone ahead with the deflector's tachyon pulse [E]."""
        tok.rest()
        res.commands.append(self._cmd(DeflectorPulse))

    def _v_conn(self, tok: _Tokens, res: ParseResult) -> None:
        """`conn <officer>` gives an officer the whole bridge; `conn captain` (or bare `conn`) takes it back [E]."""
        tok.take_word("to")
        words = [w for w in tok.rest() if w.lower() not in ("the",)]
        who = " ".join(words).strip().lower()
        res.actions.append(("conn", None if who in ("", "captain", "me", "back", "off", "mine", "return") else who))

    def _v_crew(self, tok: _Tokens, res: ParseResult) -> None:
        w = tok.next()
        if w is not None and _match(w, {"chatter": ("chatter", "talk", "quiet")}) == "chatter":
            on = not (w.startswith("q") or tok.take_word("off"))
            tok.take_word("on")
            res.actions.append(("crew", ("chatter", on)))
            return
        res.actions.append(("crew", None))

    def _v_ask(self, tok: _Tokens, res: ParseResult) -> None:
        raw = tok.raw.strip().split(None, 1)
        rest = raw[1] if len(raw) > 1 else ""
        m = re.match(r"^\s*([^\s,:]+(?:\s+of\s+nine)?)\s*[,:]?\s*(.*)$", rest, re.I)
        if not m:
            raise ParseError("Ask whom? e.g. 'ask worf status' or 'spock, what do you recommend?'")
        tok.rest()
        res.actions.append(("ask", (m.group(1), m.group(2))))

    def _v_key(self, tok: _Tokens, res: ParseResult) -> None:
        """Begin 2.0's `key <F#|^x> <string>`: bind a key to console commands (';' separates commands)."""
        name = tok.next()
        if name is None:
            res.actions.append(("key", None))
            return
        name = name.upper() if name.startswith("f") else name
        if not re.fullmatch(r"(F([2-8]|1[0-2])|\^[a-z])", name):
            raise ParseError("Keys are F2-F8, F10-F12 or ^a-^z (F1 is help, F9 the debug view).")
        raw = tok.raw.strip()
        parts = raw.split(None, 2)
        text = parts[2].strip() if len(parts) > 2 else ""
        tok.rest()
        res.actions.append(("key", (name, text)))


# what the captain can say they have: "I have nav", "I have fire", "I have torps", "I have the conn" [E]
HAVE_WORDS: dict[str, tuple[str, ...]] = {
    "helm": ("helm", "nav", "navigation", "navs", "steering", "course", "wheel", "flying"),
    "tactical": ("tactical", "weapons", "weapon", "fire", "phasers", "phaser", "torps", "torp", "torpedoes", "torpedo",
                 "torpedos", "guns", "tubes", "targeting"),
    "engineering": ("engineering", "engines", "power", "shields", "shield"),
    "science": ("science", "sensors", "scans", "scanning"),
    "all": ("conn", "bridge", "ship", "everything", "all", "command", "stations", "it"),
}

STATION_WORDS: dict[str, tuple[str, ...]] = {
    "helm": ("helm", "conn", "navigation", "nav"),
    "tactical": ("tactical", "weapons", "fire"),
    "engineering": ("engineering", "engines", "power", "damage"),
    "science": ("science", "sensors", "scans"),
}


def _stations(tok: "_Tokens") -> list[str]:
    tok.skip_filler()
    words = tok.rest()
    if not words or words[0] in ("all", "al", "everything", "stations"):
        return list(STATION_WORDS)
    out: list[str] = []
    for w in words:
        if w in ("and", "station", "stations", "to", "the"):
            continue
        st = _match(w, STATION_WORDS)
        if st is None:
            raise ParseError(f"No station called '{w}'. Stations: helm, tactical, engineering, science.")
        out.append(st)
    return out


def parse(text: str, ctx: ParseContext) -> ParseResult:
    try:
        return Parser(ctx).parse(text)
    except ParseError as e:
        return ParseResult(error=str(e), echo=text)


__all__ = ["HELP", "ParseContext", "ParseError", "ParseResult", "Parser", "VERBS", "parse"]
