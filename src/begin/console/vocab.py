"""The console's vocabulary: verbs and their spellings, weapon and system words, and the help summary.

Shared by the parser, the plain-English rewriter (`plain.py`), the officers and the manual. Any word can be
shortened to a unique prefix, which `match_word` resolves.
"""

from __future__ import annotations

import difflib
import re
from typing import Mapping, Sequence

from ..sim.ship import HULL, Kind, RepairTarget

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
    "probe": ("probe", "probes", "pr"),
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
    "hail": ("hail", "hailing", "channel"),
    "prisoners": ("prisoners", "brig"),
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
    "Hail:     hail [<ship>|all] [<your words>]   e.g. 'hail gr'oth surrender and your crew will be treated well'",
    "          (demand surrender, tell them to withdraw, threaten, bluff or just talk; 'open a channel to <ship>' too)",
    "          A ship that surrenders drops her shields: board her with six or more and her crew are taken prisoner.",
    "          prisoners   (who you hold)",
    "Tour:     request reinforcements   (on a tour of duty: Starfleet sends a ship, which arrives after a delay)",
    "Sound:    sound on|off|<0-100>   sound phaser|torpedo a-d   (M mutes)",
    "Other:    key F<n>|^<x> <commands; separated; by semicolons> · translate on|off|always · help · quit",
]


_NUM = re.compile(r"^[+-]?\d+(\.\d+)?$")


def is_num(tok: str | None) -> bool:
    return tok is not None and bool(_NUM.match(tok))


def match_word(word: str, table: Mapping[str, Sequence[str]], min_len: int = 2) -> str | None:
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


def candidates(word: str, table: Mapping[str, Sequence[str]]) -> list[str]:
    hits = [key for key, aliases in table.items() if any(a.startswith(word) for a in aliases)]
    primary = [key for key in hits if table[key][0].startswith(word)]
    return primary or hits


# the enemy systems a captain can ask to have knocked out, in their words
DISABLE_WORDS: dict[str, str] = {
    **dict.fromkeys(("shield", "shields", "deflector", "deflectors", "screens"), "shields"),
    **dict.fromkeys(("phaser", "phasers", "banks", "beams", "disruptor", "disruptors", "beam"), "phasers"),
    **dict.fromkeys(("torpedo", "torpedoes", "torpedos", "torps", "torp", "tubes", "tube", "launchers"),
                    "torpedoes"),
    **dict.fromkeys(("weapon", "weapons", "guns", "armament", "arms"), "weapons"),
    **dict.fromkeys(("engine", "engines", "drive", "drives", "warp", "impulse", "propulsion"), "propulsion"),
    **dict.fromkeys(("sensor", "sensors", "eyes"), "sensors"),
    **dict.fromkeys(("cloak", "cloaking"), "cloak"),
}


def system_word(word: str) -> str | None:
    """The enemy system a word names ("shields", "torps"), allowing for a slip of the keyboard ("sheilds")."""
    w = word.strip(".!?;'\"").removesuffix("'s").removesuffix("s'")
    hit = DISABLE_WORDS.get(w)
    if hit is not None or len(w) < 5:
        return hit
    close = difflib.get_close_matches(w, list(DISABLE_WORDS), n=1, cutoff=0.8)
    return DISABLE_WORDS[close[0]] if close else None


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


__all__ = ["AIM_FIRST", "AIM_HELP", "AIM_WORDS", "DISABLE_WORDS", "FILLER", "HAVE_WORDS", "HELP", "REPAIR_KINDS",
           "STATION_WORDS", "VERBS", "WEAPONS", "candidates", "is_num", "match_word", "system_word"]
