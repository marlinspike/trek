"""Counsel: each bridge officer's way forward from here, rebuilt from the live situation [E].

Press O (or type `counsel`) in battle. Every officer reads the same `Situation` (crew/situation.py) but values
different things, so each offers a different, plausible plan for the next stretch of the fight:

* tactical (Worf, or Sulu standing in): **the sword**. Decisive force, concentrated, now.
* helm (Spock, or Chekov): **geometry and the mind**. Choose the range, use the shields, read the captain.
* engineering (La Forge): **keep the ship and her people alive to win**. Power, repairs, the people aboard.
* science (Seven of Nine, or Spock): **knowledge and precision**. Know first, then remove exactly what matters.

A plan is a title, the reason in a sentence or two built from live numbers, and two to four steps, each a real
console line. Going all in on one officer's plan is a coherent way to fight; taking a step from each can do well
too. Plans are assembled from *moves*: a library of capabilities, each scored by how well it fits the situation
now and weighted by how much each perspective values it. Nothing here changes anything: running a step is the
captain typing it.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Iterator, Mapping
from dataclasses import dataclass, field, replace

from ..core.angles import bearing, norm360
from ..sim.rules import DEFAULT_RULES
from .situation import EnemyView, ShieldView, Situation

STATIONS = ("tactical", "helm", "engineering", "science")
PERSPECTIVE = {
    "tactical": "The sword",
    "helm": "Geometry and the mind",
    "engineering": "Keep her alive to win",
    "science": "Know, then strike precisely",
}
MAX_STEPS = 4
OWN = 0.8                 # a move whose lean for a station is at least this is that perspective's own
SWEET = 0.65              # torpedoes hit best from the nearer part of the envelope


@dataclass(frozen=True)
class Step:
    line: str                 # the console line, exactly as typed
    label: str                # what it does, in a few words


@dataclass(frozen=True)
class Plan:
    station: str
    officer: str              # officer id ("worf")
    name: str                 # "Worf"
    perspective: str          # "The sword"
    title: str
    reason: str
    steps: tuple[Step, ...]
    keys: tuple[str, ...] = ()      # the moves it is built from, lead first

    @property
    def lines(self) -> list[str]:
        return [s.line for s in self.steps]


@dataclass
class Move:
    key: str
    title: str
    reason: str
    steps: list[Step]
    score: float                             # 0..1: how much the situation calls for it
    leans: dict[str, float]                  # station -> how much that perspective values it
    group: str = ""                          # moves in the same group are alternatives: a plan takes one
    voice: dict[str, str] = field(default_factory=dict)    # station -> its own title for this move

    def value(self, station: str) -> float:
        return self.score * self.leans.get(station, 0.0)


Check = Callable[[str], "str | None"]


# ------------------------------------------------------------------ helpers

def _pct(x: float | None) -> str:
    return "unknown" if x is None else f"{x * 100:.0f}%"


def _rng(x: float) -> str:
    return f"{x:,.0f}"


def _in_env(s: Situation, e: EnemyView) -> bool:
    return e.our_env is not None and e.our_env[0] <= e.range <= e.our_env[1] * 0.85


def _sweet(s: Situation, e: EnemyView) -> bool:
    if e.our_env is None:
        return False
    lo, hi = e.our_env
    return lo * 1.1 <= e.range <= lo + (hi - lo) * SWEET * 0.5


def _fire_now(s: Situation, e: EnemyView, spread_ok: bool = True) -> list[Step]:
    """What our weapons can do against her this moment."""
    out: list[Step] = []
    if s.hold_fire:
        return out
    if s.tubes_loaded >= 2 and _in_env(s, e):
        fan = spread_ok and e.max_warp >= 9.0 and e.our_env is not None and e.range > e.our_env[0] * 2.5
        out.append(Step("fire all torpedoes spread 10" if fan else "fire all torpedoes",
                        f"{s.tubes_loaded} torpedoes" + (", fanned" if fan else "")))
    if s.banks_ready >= 2 and e.range < s.phaser_range:
        out.append(Step("fire all phasers spread 10", f"{s.banks_ready} phaser banks"))
    return out


def _target(s: Situation, e: EnemyView, system: str = "") -> Step | None:
    if s.target == e.id and not system:
        return None
    line = f"target {e.handle}" + (f" {system}" if system else "")
    return Step(line, f"target her {system}" if system else f"target the {e.name}")


def _turn_to(s: Situation, brg: float, sh: ShieldView) -> float:
    """The course that puts shield `sh` toward an absolute bearing."""
    return norm360(brg - sh.facing)


def _sector_away(s: Situation) -> list[int]:
    """Our shields facing away from every enemy we can see (1-based, as the console counts them)."""
    rels = [e.rel for e in s.fighting if e.visible and e.range < 30000]
    out = []
    for sh in s.shields:
        if sh.destroyed or not sh.up:
            continue
        if all(abs((r - sh.facing + 180) % 360 - 180) > 95 for r in rels):
            out.append(sh.index + 1)
    return out


def odds(s: Situation, e: EnemyView, intent: str, persuasion: float = 1.25) -> float:
    """How likely her captain is to accept now: the same reading the comms officer has (sim/systems/disposition)."""
    r = e.reading
    if r is None or e.cls is None:
        return 0.0

    def clamp(x: float) -> float:
        return max(0.0, min(1.0, x))

    if intent == "surrender":
        sw = e.surrender_willingness
        scale = 0.4 + 0.6 * min(1.0, sw * 2.5)
        scale += (1.0 - scale) * clamp((r.fear - 0.6) / 0.4)
        return clamp((r.pliancy - 0.3 + 0.3 * (persuasion - 1.0) - 0.4 * r.distrust) * 2.0) * scale
    if e.cls.is_base or e.max_warp <= 0:
        return 0.0
    return clamp((r.pliancy + 0.05 + 0.3 * (persuasion - 1.0) - 0.2 * r.distrust) * 1.8)


# ------------------------------------------------------------------ the moves

def moves(s: Situation, goal: Goal | None = None) -> list[Move]:
    """Every move worth considering now, each scored for the situation (and the captain's goal, if one is set)."""
    if goal is not None and goal.targets:
        s = replace(s, focus=goal.live(s))
    out: list[Move] = []
    for gen in (_sword, _geometry, _keep, _knowledge, _mission_moves, _coach):
        out.extend(m for m in gen(s) if m.steps and m.score > 0.0)
    if goal is not None and not goal.achieved(s):
        for m in out:
            m.score *= GOAL_KEEP.get(m.key, 0.55)       # the goal comes first; survival still counts
        out.extend(m for m in _goal_moves(s, goal) if m.steps)
    return out


# ------------------------------------------------------------------ the captain's goal

GOAL_KEEP = {"evasive": 1.0, "fresh-shield": 0.9, "power": 0.9, "reinforce": 0.8, "brace": 0.7, "repairs": 0.75,
             "hunt": 0.9, "scan": 0.8, "plasma": 0.8, "focus": 0.9, "meet-charge": 0.9, "bait": 0.9, "ring": 0.85,
             "standoff": 0.85, "inside": 0.85, "strike": 1.0, "dormant": 1.0, "relay": 0.9, "learn": 0.85,
             "tune": 0.8, "remodulate": 0.85, "starfleet": 0.8, "seeker-strike": 1.0, "seeker-kill": 1.0}
SYSTEMS = ("shields", "phasers", "torpedoes", "weapons", "engines", "sensors", "cloak")
_SYSTEM_WORDS = {"engine": "engines", "engines": "engines", "drive": "engines", "drives": "engines",
                 "warp": "engines", "propulsion": "engines", "shield": "shields", "shields": "shields",
                 "weapon": "weapons", "weapons": "weapons", "guns": "weapons", "phaser": "phasers",
                 "phasers": "phasers", "disruptors": "phasers", "torpedo": "torpedoes", "torpedoes": "torpedoes",
                 "tubes": "torpedoes", "sensor": "sensors", "sensors": "sensors", "cloak": "cloak"}
_KIND_WORDS = {"destroy": "destroy", "kill": "destroy", "sink": "destroy", "eliminate": "destroy", "finish": "destroy",
               "disable": "disable", "cripple": "disable", "knock": "disable", "disarm": "disable",
               "capture": "capture", "take": "capture", "board": "capture", "seize": "capture",
               "survive": "survive", "escape": "survive", "save": "mission", "rescue": "mission",
               "protect": "mission", "mission": "mission", "win": "mission"}


@dataclass(frozen=True)
class Goal:
    """What the captain asked the officers to plan for: `counsel destroy the Gr'oth`, `counsel kill all the cubes`,
    `counsel disable all their engines`, `counsel capture the Mugger`, `counsel survive`."""

    kind: str                          # destroy | disable | capture | survive | mission
    targets: tuple[int, ...] = ()
    system: str = ""                   # disable: what to knock out
    text: str = ""                     # the goal in words, for the panel

    def live(self, s: Situation) -> tuple[int, ...]:
        return tuple(t for t in self.targets if (e := s.enemy(t)) is not None and not e.surrendered)

    def achieved(self, s: Situation) -> bool:
        if self.kind in ("destroy", "capture"):
            return bool(self.targets) and not self.live(s)
        return False


def parse_goal(text: str, s: Situation) -> Goal | str:
    """A goal from the captain's words, or why it can't be read."""
    words = [w.strip(".,!?;:'\"").lower() for w in text.split()]
    words = [w.removesuffix("'s") for w in words if w]
    if not words:
        return "Counsel toward what? e.g. 'counsel destroy the Gr'oth' or 'counsel disable all their engines'."
    kind = next((_KIND_WORDS[w] for w in words if w in _KIND_WORDS), None)
    system = next((_SYSTEM_WORDS[w] for w in words if w in _SYSTEM_WORDS), "")
    if kind is None:
        kind = "disable" if system else "destroy"
    if kind in ("survive", "mission"):
        what = "Keep the ship alive" if kind == "survive" else "Accomplish the mission"
        return Goal(kind, text=what)
    if kind == "disable" and not system:
        system = "weapons"
    enemies = [e for e in s.enemies if not e.surrendered]
    every = any(w in ("all", "every", "each", "them", "their", "everyone", "everything") for w in words)
    picked: list[int] = []
    for e in enemies:
        name = e.name.lower()
        cls = e.cls.name.lower() if e.cls else ""
        fac = e.faction.lower()
        for w in words:
            if len(w) < 3 or w in _KIND_WORDS or w in _SYSTEM_WORDS or w in ("all", "the", "their", "every"):
                continue
            base = w.rstrip("s") if len(w) > 4 else w
            if name.startswith(w) or (cls and (cls.startswith(base) or base in cls.split())) or \
                    (fac and fac.startswith(base)):
                picked.append(e.id)
                break
    if not picked and every:
        picked = [e.id for e in enemies]
    if not picked:
        return f"No enemy ship matches '{text}'. Name her, or say 'all'."
    names = [s.enemy(i).name for i in picked]  # type: ignore[union-attr]
    who = f"the {names[0]}" if len(names) == 1 else f"all {len(names)} of them"
    if kind == "disable":
        return Goal(kind, tuple(picked), system, f"Disable {who}'s {system}" if len(names) == 1 else
                    f"Disable {system} on {who}")
    return Goal(kind, tuple(picked), "", f"{kind.capitalize()} {who}")


def strike_system(s: Situation, e: EnemyView) -> tuple[str, str]:
    """[E] What a sweep-and-strike salvo should go into, and why, from where the fight stands: her warp drive if she
    is running or must be stopped, her weapons if ours is the ship in trouble, else her shields, so that the next
    salvo, from us or anyone, goes through."""
    m = s.mission
    if e.withdrawing or (m is not None and m.state == "open" and m.kind == "intercept"):
        return "warp", "she is running, and with her drive gone she can't get away or reach anyone"
    if s.hull < 0.5 or (m is not None and m.state == "open" and e.hunter):
        return "weapons", "she can't hurt us, or anyone we protect, without them"
    return "shields", "once they are down, every hit after it goes to her hull"


def _sweep_strike(s: Situation, e: EnemyView, score: float = 0.95) -> Iterator[Move]:
    """[E] A cloaked ship leaking plasma: sweep, seeker down the trail, and an aimed salvo the moment it lands.
    Seven aims for the system that decides the fight; Worf would rather put the whole salvo into her hull."""
    system, why = strike_system(s, e)
    lit = f"{DEFAULT_RULES.seeker_lock_cycles:.0f} seconds"
    yield Move("seeker-strike", f"Sweep and strike the {e.name}'s {system}",
               f"The {e.name} is cloaked but her damaged drive vents plasma at {_rng(e.range)}. A seeker down the "
               f"trail lights her up for {lit}, and I put every torpedo into her {system} the instant it lands: {why}.",
               [Step(f"strike {e.handle} {system}", f"seeker, then a salvo into her {system}")], score,
               {"science": 1.0, "tactical": 0.5, "helm": 0.4}, "hunt")
    yield Move("seeker-kill", f"Sweep and strike: kill the {e.name}",
               f"The {e.name} thinks her cloak hides her. Her plasma doesn't. A seeker down the trail, and the moment it hits, "
               "everything we have into her hull.", [Step(f"strike {e.handle}", "seeker, then a full salvo")],
               score * 0.9, {"tactical": 1.0, "helm": 0.3}, "hunt-kill")


def _goal_moves(s: Situation, g: Goal) -> Iterator[Move]:
    """Each perspective's way to the captain's goal."""
    targets = [e for e in s.fighting if e.id in g.live(s)]
    if g.kind == "survive":
        yield from _survive(s)
        return
    if g.kind == "mission":
        for m in _mission_moves(s):
            m.score = min(1.0, m.score * 1.2)
            yield m
        return
    if not targets:
        return
    seen = [e for e in targets if e.visible]
    lost = [e for e in targets if not e.visible]
    e = min(seen, key=lambda x: x.range) if seen else None
    if lost and not seen:
        x = min(lost, key=lambda x: x.range)
        if x.exhaust and g.kind in ("destroy", "disable"):
            system = "" if g.kind == "destroy" else {"engines": "warp"}.get(g.system, g.system)
            yield Move("goal-strike", f"{g.text}: sweep and strike",
                       f"She is cloaked, but her plasma trail gives her away. A seeker down it lights her up, and the "
                       f"salvo goes into her {system or 'hull'} the instant it hits.",
                       [Step(f"strike {x.handle} {system}".strip(), "seeker, then the salvo")], 1.0,
                       {"science": 1.0, "tactical": 1.0, "helm": 0.6}, "hunt")
            return
        yield Move("goal-find", f"Find the {x.name} first", f"{g.text}: but we have lost her. Nothing else helps until "
                   "we know where she is.", [Step(f"hunt {x.handle}", "find her")], 1.0,
                   {"science": 1.0, "tactical": 0.8, "helm": 0.8}, "hunt")
        return
    assert e is not None
    many = len(targets) > 1
    order = sorted(seen, key=lambda x: (x.hull if x.hull is not None else 1.0) * x.threat)
    if g.kind == "destroy":
        weakest = order[0]
        steps = [x for x in (_target(s, weakest),) if x] + (_fire_now(s, weakest) or
                                                              [Step(f"pursue {weakest.handle}", "close on her")])
        why = (f"{g.text}. Take them one at a time, weakest first: the {weakest.name} "
               f"({_pct(weakest.hull)} hull) falls fastest and takes her guns out of the fight." if many else
               f"{g.text}. Everything on her, every time a bank charges or a tube loads.")
        yield Move("goal-kill", f"{g.text}: {'one at a time' if many else 'all weapons'}", why, steps, 1.0,
                   {"tactical": 1.0, "helm": 0.4}, "target")
        if e.shields and e.weakest is not None and e.shields[e.weakest] < 60:
            yield Move("goal-weak-face", f"Turn into the {e.name}'s weak shield",
                       f"Her shield {e.weakest + 1} is at {max(0.0, e.shields[e.weakest]):.0f}%. Come round to it and "
                       "every hit goes straight to her hull.",
                       [Step(f"pursue {e.handle}", "work round her")], 0.85, {"helm": 1.0}, "helm")
        else:
            yield from (m for m in _geometry(replace(s, focus=(e.id,))) if m.key in ("standoff", "inside", "split"))
        if not e.scanned:
            yield Move("goal-scan", f"Scan the {e.name}", "To destroy her quickly we need her shields and damage.",
                       [Step(f"scan {e.handle}", "full scan")], 0.95, {"science": 1.0}, "scan")
        else:
            yield Move("goal-hole", f"Open a hole in the {e.name}'s shields",
                       "I will burst torpedoes where her point defense won't react until one of her shields is gone for "
                       "good. Then every weapon we have goes through.", [Step(f"disable {e.handle} shields", "her shields")],
                       0.85, {"science": 1.0}, "objective")
        yield Move("goal-arm", "Power to the weapons and the shield toward her",
                   f"A fight to the finish is long. I'll keep the crews on the tubes and banks and reinforce the shield "
                   f"facing the {e.name}.", [Step("repair tubes", "tubes first"), *(
                       [Step(f"reenforce {s.facing.index + 1}", "the shield toward her")] if s.facing and s.facing.up else [])],
                   0.8, {"engineering": 1.0}, "repairs")
        return
    if g.kind == "disable":
        system = g.system
        aim = {"engines": "propulsion", "weapons": "weapons", "phasers": "phasers", "torpedoes": "torpedoes",
               "shields": "shields", "sensors": "sensors", "cloak": "cloak"}[system]
        handles = "all" if many and len(targets) == len([x for x in s.fighting if not x.hive]) else e.handle
        yield Move("goal-disable", g.text,
                   f"I'll burst torpedoes where their point defense won't react, at their {system} only, and spare the rest "
                   f"of {'them' if many else 'her'}. Keep {'each' if many else 'her'} at 3,500 to 7,500 from us.",
                   [Step(f"disable {handles} {system}", f"their {system}")], 1.0, {"science": 1.0, "tactical": 0.3},
                   "objective")
        yield Move("goal-aim", f"Aimed fire at the {e.name}'s {system}",
                   f"Lock every weapon on her {system}: phasers at that system wear it down without breaking her apart.",
                   [x for x in (_target(s, e, aim),) if x] + _fire_now(s, e, False), 0.95, {"tactical": 1.0},
                   "target")
        lo = (e.our_env[0] * 1.3) if e.our_env else 3500.0
        want = max(3500.0, lo)
        line = f"pursue {e.handle} at 5500" if e.range > 7500 or e.range < want else ""
        if line:
            yield Move("goal-range", f"Hold the {e.name} at 3,500 to 7,500",
                       f"She is at {_rng(e.range)}. In that band our torpedoes are armed and her point defense has the "
                       "least time to react.", [Step(line, "hold the range")], 0.95, {"helm": 1.0}, "helm")
        else:
            yield Move("goal-hold", f"Keep the {e.name} where she is",
                       f"She is at {_rng(e.range)}, inside the band where our torpedoes arm and burst cleanly. Evasive "
                       "keeps us there while dodging.", [Step("evasive", "hold and dodge")], 0.8, {"helm": 1.0}, "dodge")
        yield Move("goal-tubes", "Keep the tubes loaded and close in",
                   "Disabling shots are torpedoes. I'll keep the crews on the tubes so every salvo is ready when Seven calls for it.",
                   [Step("repair tubes", "tubes first")], 0.75, {"engineering": 1.0}, "repairs")
        return
    if g.kind == "capture":
        yield Move("goal-capture", f"Take the {e.name}",
                   "Open one of her shields, thin her crew through the gap with phasers, and board her with our security "
                   "teams.", [Step(f"capture {e.handle}", "board and keep her")], 1.0, {"tactical": 1.0, "science": 0.4},
                   "objective")
        if e.reading is not None:
            p = odds(s, e, "surrender")
            yield Move("goal-yield", f"Ask the {e.name} to yield",
                       f"A ship that strikes her colours can be boarded without a fight. About {p * 100:.0f}% likely now; "
                       "it rises as her hull falls.",
                       [Step(f"hail {e.handle} Lower your shields and surrender. Your crew will be treated well.",
                             "demand her surrender")], 0.9, {"helm": 1.0}, "hail")
        yield Move("goal-engines", f"Stop the {e.name} running",
                   "A prize that can run is not a prize. Her drives first, then her shields.",
                   [Step(f"disable {e.handle} engines", "her engines")], 0.9, {"science": 1.0}, "objective")
        yield Move("goal-transporters", "Transporters and security ready",
                   "Boarding takes people and working transporters. I'll keep the transporter rooms repaired.",
                   [Step("repair transporters", "transporters first")], 0.7, {"engineering": 1.0}, "repairs")


def _survive(s: Situation) -> Iterator[Move]:
    m = s.main_threat
    if m is not None:
        yield Move("survive-run", f"Open the range from the {m.name}",
                   f"At warp {s.max_warp:g} we can outrun what she can follow. Distance is armour.",
                   [Step(f"elude {m.handle} warp {s.top_warp:g}", "run")], 0.95, {"helm": 1.0}, "helm")
    yield Move("survive-repair", "Repairs to the hull and shields",
               f"Hull at {_pct(s.hull)}. Every crew on the hull and shields until we are clear.",
               [Step("repair hull", "the hull first"), Step("repair auto", "La Forge directs")], 0.9,
               {"engineering": 1.0}, "repairs")
    if s.can_cloak and not s.cloaked:
        yield Move("survive-cloak", "Cloak", "Under the cloak they cannot lock on us.", [Step("cloak on", "cloak")], 0.9,
                   {"science": 1.0, "engineering": 0.5}, "cloak")
    if m is not None and m.reading is not None:
        yield Move("survive-hail", f"Offer the {m.name} a way out",
                   "A captain who withdraws stops shooting.",
                   [Step(f"hail {m.handle} Captain, withdraw now and no one else needs to die.", "open a channel")],
                   0.6 + odds(s, m, "withdraw"), {"tactical": 0.6, "science": 0.8}, "hail")


def _coach(s: Situation) -> Iterator[Move]:
    """The tactical coach's own reading (help/coach.py), so the officers know everything it knows."""
    station = {"tactical": "tactical", "helm": "helm", "engineering": "engineering", "science": "science"}
    for t in s.tips:
        if not t.commands:
            continue
        st = station.get(t.station, "tactical")
        score = {0: 0.85, 1: 0.7, 2: 0.55, 3: 0.42, 4: 0.32}.get(t.priority, 0.25)
        text = t.text.replace("**", "")
        yield Move(f"coach:{t.title}", t.title, text, [Step(c, t.title.lower()) for c in t.commands[:2]], score,
                   {st: 0.8}, "coach:" + t.title)


def _sword(s: Situation) -> Iterator[Move]:
    T = {"tactical": 1.0}
    m = s.main_threat
    live = [e for e in s.fighting if e.visible]
    if m is not None and not (m.hive and m.opening):
        steps = [x for x in (_target(s, m),) if x] + _fire_now(s, m)
        if not _fire_now(s, m) and not s.hold_fire:
            steps.append(Step(f"pursue {m.handle}", "close on her"))
        share = m.threat / max(1.0, s.theirs)
        weak = f" Her shield toward us is at {m.shield_to_us:.0f}%." if m.shield_to_us is not None else ""
        what = m.cls.name if m.cls else "unidentified"
        hull = f", hull {_pct(m.hull)}" if m.hull is not None else ""
        if len(live) > 1:
            reason = (f"The {m.name} is the most dangerous ship out there ({what}{hull}, {share * 100:.0f}% of their "
                      f"strength).{weak} Put everything on her and the rest lose their best gun.")
        else:
            reason = f"The {m.name} ({what}{hull}) is the one we can reach.{weak} Everything on her, now."
            share = 0.6
        yield Move("focus", f"Mass fire on the {m.name}", reason, steps, 0.55 + 0.35 * share,
                   {**T, "helm": 0.3, "science": 0.25}, "target",
                   voice={"tactical": f"Strike the {m.name}: all weapons"})
    for e in live:
        if e.style == "charge" and e.closing > 150 and s.tubes_loaded >= max(2, s.tubes // 2) and _in_env(s, e):
            yield Move("meet-charge", f"Meet the {e.name}'s charge with a full salvo",
                       f"She is charging in at {e.closing:,.0f} a cycle for a point-blank alpha strike. Her phasers reach "
                       f"{_rng(e.her_phaser_range)}; our torpedoes reach her now, at {_rng(e.range)}. Every round that "
                       "lands before she arrives is damage she brings in with her.",
                       [x for x in (_target(s, e),) if x] + [Step("fire all torpedoes", "every loaded tube")], 0.9,
                       {**T, "helm": 0.4}, "torpedoes")
            break
    dark = [e for e in s.enemies if e.cloaked_hint and not e.visible and e.range < 25000]
    if dark and s.pd != "aggressive":
        yield Move("pd", "Point defense to aggressive",
                   f"The {dark[0].name} is cloaked. When she decloaks she fires first, at close range. Aggressive point "
                   "defense spends our banks freely on her rounds.", [Step("pd aggressive", "point defense aggressive")],
                   0.5, {**T, "engineering": 0.3}, "pd")
    t = s.target_view
    if (t is not None and t.visible and t.pd_discipline < 0.6 and s.tubes_loaded >= 3 and 3000 < t.range < 8000
            and not s.hold_fire and "bait" not in s.objectives):
        yield Move("bait", f"Bait the {t.name}'s point defense",
                   f"{t.faction.title() or 'Her'} gunners fire every bank at the first torpedo they see. Send one, and "
                   f"the other {s.tubes_loaded - 1} a moment later while her banks recharge.",
                   [Step(f"bait {t.handle}", "one torpedo, then the rest")], 0.75, {**T, "science": 0.6}, "torpedoes")
    if m is not None and m.her_phaser_range and s.phaser_range >= m.her_phaser_range and not m.hive:
        our_banks = s.banks
        their = m.cls.banks if m.cls else 0
        if our_banks >= their:
            steps = [x for x in (_target(s, m),) if x] + [Step(f"pursue {m.handle}", "close to phaser range")]
            if m.range < s.phaser_range and s.banks_ready:
                steps.append(Step("fire all phasers spread 10", "phasers"))
            low = s.torps_left < max(1, s.tubes) * 2
            yield Move("close", "Close and finish her with phasers",
                       f"Our {our_banks} banks reach {_rng(s.phaser_range)} to her {their} at {_rng(m.her_phaser_range)}"
                       + (f", and we have only {s.torps_left} torpedoes left" if low else "")
                       + ". Up close the phasers hit hardest and she has no answer.",
                       steps, 0.5 + (0.2 if low else 0.0), {**T, "helm": 0.5, "engineering": 0.5 if low else 0.1}, "helm")
    for e in live:
        if (e.hull is not None and e.hull < 0.35 and e.surrender_willingness >= 0.1 and not e.hive
                and "capture" not in s.objectives and s.transporters > 0):
            yield Move("prize", f"Take the {e.name} as a prize",
                       f"Her hull is down to {_pct(e.hull)}. Open one shield, thin her crew through the gap and board "
                       "her: a ship taken is a ship that fights for us.",
                       [Step(f"capture {e.handle}", "board and keep her")], 0.6, {**T, "science": 0.4}, "objective")
            break
    if s.allies and m is not None:
        a = next((a for a in s.allies if a.hull > 0.35 and a.order != "attack"), None)
        if a is not None:
            yield Move("squadron", f"Bring the {a.name} onto the {m.name}",
                       f"Two ships on one target break her shields twice as fast. The {a.name} is {_rng(a.range)} off "
                       f"with {a.tubes_loaded} tubes loaded.",
                       [Step(f"tell {a.name.lower()} attack {m.handle}", f"the {a.name} attacks")], 0.5,
                       {**T, "helm": 0.3}, "squadron")
    for e in live:
        if e.hive and e.dormant > 0:
            yield Move("dormant", f"She sleeps: everything on the {e.name}",
                       f"The {e.name} has gone dark for about {e.dormant:.0f} cycles: no shields, no weapons, no "
                       "healing. Mass everything on her warp core now.",
                       [x for x in (_target(s, e, "power"),) if x] + [Step("fire all", "every weapon")], 1.0,
                       {**T, "science": 0.7, "helm": 0.4}, "target")
        elif e.hive and e.opening:
            what = "every weapon we fire passes" if e.opening == "stolen" else "our harmonic torpedoes pass"
            steps = [x for x in (_target(s, e, "propulsion"),) if x] + [Step("fire all torpedoes", "torpedoes"),
                                                                         Step("fire all phasers", "phasers")]
            if s.can_cloak and not s.cloaked:
                steps.append(Step("cloak on", "cloak, so she can't answer"))
            yield Move("strike", f"Strike through the {e.name}'s shields",
                       f"For now {what} straight through her shields. One full salvo at her warp drives wrecks them, "
                       "and drives destroyed this way can take her core with them.", steps, 1.0,
                       {**T, "science": 0.6, "helm": 0.3}, "target")


def _round_range(r: float) -> float:
    """A range the helm is told to hold, to the nearest 500."""
    return max(500.0, round(r / 500.0) * 500.0)


def _geometry(s: Situation) -> Iterator[Move]:
    H = {"helm": 1.0}
    m = s.main_threat
    if s.inbound and not s.evasive and s.faction == "federation":
        yield Move("evasive", "Evasive manoeuvres",
                   f"{s.inbound} enemy {'weapon is' if s.inbound == 1 else 'weapons are'} inbound. The helm jinks "
                   "out of each round's path and holds our course or pursuit.",
                   [Step("evasive", "dodge the incoming")], 0.95, {**H, "engineering": 0.35, "tactical": 0.2}, "dodge")
    if m is not None and not (m.hive and (m.opening or m.dormant)):
        hpr = m.her_phaser_range
        her_lo = m.her_env[0] if m.her_env else 0.0
        our = m.our_env
        if our is not None and (hpr > s.phaser_range * 0.95 or m.style == "charge" or (m.cls and m.cls.banks > s.banks)):
            # she wants it close: keep her at torpedo range, outside her phasers
            want = _round_range(min(max(hpr * 2.0, our[0] * 1.5), our[1] * SWEET))
            steps = [Step(f"elude {m.handle} at {want:.0f}", f"hold her at {_rng(want)}")]
            if s.tubes_loaded >= 2 and _in_env(s, m):
                steps.append(Step("fire all torpedoes", "torpedoes from range"))
            yield Move("standoff", f"Hold the {m.name} at torpedo range",
                       f"Her phasers reach {_rng(hpr)}; our torpedoes arm at {_rng(our[0])} and reach {_rng(our[1])}. "
                       f"At {_rng(want)} to {_rng(min(our[1] * SWEET, want * 2.5))} we hit her and she cannot answer with "
                       "her banks." + (" She charges: let her come on to our salvo, then open the range again."
                                       if m.style == "charge" else ""),
                       steps, 0.62 if m.range < want * 0.85 else 0.45, {**H, "engineering": 0.4}, "helm",
                       voice={"helm": f"Fight the {m.name} at our range, not hers"})
        elif her_lo > 0:
            close = _round_range(max(1000.0, her_lo * 0.6))
            steps = [Step(f"pursue {m.handle} at {close:.0f}", f"inside {_rng(her_lo)}")] + \
                [x for x in _fire_now(s, m, False) if "phasers" in x.line]
            yield Move("inside", f"Get inside the {m.name}'s torpedo envelope",
                       f"Her {m.her_torpedo.name if m.her_torpedo else 'torpedoes'} need {_rng(her_lo)} to arm. Inside "
                       f"that she has only her phasers, which reach {_rng(hpr)}; ours reach {_rng(s.phaser_range)}.",
                       steps, 0.55 if m.range > her_lo else 0.35, {**H, "tactical": 0.5}, "helm")
    dark = [e for e in s.enemies if e.cloaked_hint and not e.visible and e.range < 25000]
    if dark and not s.evasive and not s.inbound and s.faction == "federation":
        yield Move("ready-evasive", "Evasive manoeuvres, ready for her",
                   f"The {dark[0].name} is under her cloak, last seen {_rng(dark[0].range)} off. She must decloak to "
                   "fire, and she fires at once. With evasive on, the helm jinks the moment a round is in the water.",
                   [Step("evasive", "watch for her torpedoes")], 0.55, {**H, "engineering": 0.3}, "dodge")
    f, best = s.facing, s.freshest
    if m is not None and f is not None and best is not None and f.effective < 45 and best.effective > f.effective + 30 \
            and m.range < 15000:
        course = _turn_to(s, m.bearing, best)
        yield Move("fresh-shield", f"Turn shield {best.index + 1} toward them",
                   f"Shield {f.index + 1}, facing the {m.name}, is down to {f.effective:.0f}%. Shield {best.index + 1} is "
                   f"at {best.effective:.0f}%. Course {course:.0f} puts it between us and her.",
                   [Step(f"helm {course:.0f}", f"shield {best.index + 1} toward her")], 0.85 - f.effective / 100.0,
                   {**H, "engineering": 0.6}, "helm")
    live = [e for e in s.fighting if e.visible and e.range < 25000 and e.cls is not None]
    if len(live) >= 2:
        fast = max(live, key=lambda e: e.max_warp)
        slow = min(live, key=lambda e: e.max_warp)
        if fast.max_warp - slow.max_warp >= 1.5 and s.max_warp > slow.max_warp:
            w = round(min(s.max_warp, (fast.max_warp + slow.max_warp) / 2.0), 1)
            yield Move("split", f"Draw them apart: the {fast.name} comes on alone",
                       f"The {fast.name} makes warp {fast.max_warp:g}, the {slow.name} only {slow.max_warp:g}. Run at warp "
                       f"{w:g} and the fast one reaches us well ahead of her friends; turn and fight her one on one.",
                       [Step(f"elude {slow.handle} warp {w:g} at 15000", f"open from the {slow.name}"),
                        *[x for x in (_target(s, fast),) if x]], 0.5, {**H, "tactical": 0.3}, "helm")
    plasma = [e for e in live if e.her_torpedo is not None and e.her_torpedo.warhead_type == 2 and e.her_env is not None]
    if plasma and not any(e.hive for e in live):
        e = min(plasma, key=lambda e: e.range)
        if s.inbound_plasma or e.range < (e.her_env[1] if e.her_env else 0) * 0.45:
            yield Move("plasma", "Open the range: plasma fades",
                       "Romulan plasma loses its punch with every thousand it flies. "
                       + (f"At {_rng(e.range)} a hit is near full strength; double the distance and it is a fraction."
                          if e.range > 1500 else "Up close it hits at full strength; at range it is a fraction."),
                       [Step(f"elude {e.handle} warp {s.top_warp:g} at {_round_range(min(max(e.range * 2.0, 9000.0), 15000.0)):.0f}",
                             "open the range")],
                       0.8 if s.inbound_plasma else 0.45, {**H, "engineering": 0.5}, "helm")
    # the mind: a captain close to giving way
    best_h: tuple[float, EnemyView, str] | None = None
    for e in live:
        if e.reading is None or e.withdrawing or e.surrendered:
            continue
        for intent in ("surrender", "withdraw"):
            p = odds(s, e, intent)
            if p >= 0.3 and (best_h is None or p > best_h[0]):
                best_h = (p, e, intent)
    if best_h is not None:
        p, e, intent = best_h
        release = " Your people in our brig will be returned." if s.prisoners and intent == "withdraw" else ""
        words = ("Lower your shields and surrender. Your crew will be treated well." if intent == "surrender" else
                 "Captain, withdraw now and no one else needs to die." + release)
        r = e.reading
        assert r is not None
        yield Move("hail", f"Hail the {e.name}: offer her captain a way out",
                   f"Her captain reads fear {r.fear:.1f}, resolve {r.resolve:.1f}: about {p * 100:.0f}% likely to "
                   f"{'strike her colours' if intent == 'surrender' else 'withdraw'} if we offer it now. A ship that "
                   "leaves the field is one we needn't destroy.",
                   [Step(f"hail {e.handle} {words}", "open a channel")], min(1.0, 0.35 + p), {**H, "engineering": 0.3},
                   "hail")


def _keep(s: Situation) -> Iterator[Move]:
    E = {"engineering": 1.0}
    m = s.main_threat
    if s.battery < 0.35 and s.power_net < 0:
        away = _sector_away(s)
        if away:
            yield Move("power", "Lower the shields facing away",
                       f"Batteries at {_pct(s.battery)} and draining. Shields {', '.join(map(str, away))} face nothing; "
                       "lowering them lets the reactors catch up.",
                       [Step("lower " + " ".join(map(str, away)), "save power")], 0.85, {**E, "helm": 0.2}, "power")
    f = s.facing
    if (m is not None and f is not None and f.up and not any(x.reinforced for x in s.shields) and m.closing > 100
            and m.range < 15000 and f.effective >= 65):
        yield Move("brace", f"Reinforce shield {f.index + 1} before she arrives",
                   f"The {m.name} is closing at {m.closing:,.0f} a cycle and shield {f.index + 1} will take her first "
                   "salvo. Reinforced, it draws on the shields that face nothing.",
                   [Step(f"reenforce {f.index + 1}", f"shield {f.index + 1}")], 0.45, {**E, "helm": 0.3}, "shields")
    if m is not None and f is not None and m.range < 12000 and f.effective < 65 and not f.reinforced and f.up:
        yield Move("reinforce", f"Reinforce shield {f.index + 1}",
                   f"Shield {f.index + 1} faces the {m.name} at {f.effective:.0f}%. Reinforcing it draws strength from the "
                   "others, which face nothing.",
                   [Step(f"reenforce {f.index + 1}", f"shield {f.index + 1}")], 0.7 - f.effective / 200.0,
                   {**E, "helm": 0.4}, "shields")
    sh = s.ship
    down = [x for x in sh.subsystems() if x.destroyed] if hasattr(sh, "subsystems") else []
    kinds = {getattr(x.kind, "value", str(x.kind)) for x in down}
    pick = next((k for k in ("drive", "tube", "phaser", "shield", "reactor", "sensors", "transporter") if k in kinds), None)
    if not sh.repairs_by and pick is None and s.hull >= 0.7 and s.fighting:
        yield Move("crews", "Let me run the damage crews",
                   "Nothing is badly hurt yet. If I direct the repair crews from the start, they go where each hit lands "
                   "without waiting on an order, and you keep your mind on the fight.",
                   [Step("repair auto", "La Forge directs the crews")], 0.3, {**E}, "repairs")
    if not sh.repairs_by and (pick is not None or s.hull < 0.7):
        word = {"drive": "drives", "tube": "tubes", "phaser": "phasers", "shield": "shields", "reactor": "power",
                "sensors": "sensors", "transporter": "transporters"}.get(pick or "", "hull")
        what = f"our {word} are hurt" if pick else f"the hull is at {_pct(s.hull)}"
        yield Move("repairs", "Let me run the repairs",
                   f"{what[0].upper() + what[1:]}. I'll put the crews on what matters most as the fight changes, "
                   f"{word} first.",
                   [Step(f"repair {word}", f"{word} first"), Step("repair auto", "La Forge directs the crews")],
                   0.4 + 0.3 * (1.0 - s.hull) + (0.15 if pick else 0.0), {**E}, "repairs")
    if s.leaking:
        yield Move("leak", "Stop the plasma leak",
                   "A damaged drive is venting plasma. Anyone with a sweep can follow it straight to us, cloak or no "
                   "cloak. Repairing the drives seals it.",
                   [Step("repair drives", "seal the drives")], 0.65, {**E, "science": 0.4}, "repairs")
    if s.heat > 0.6 and not s.boost:
        yield Move("boost", "A team on the drives",
                   f"The drives are at {s.heat * 100:.0f}% of their limit. A team nursing them keeps them cooler for "
                   "the run ahead; other repairs slow.", [Step("boost", "run hot for longer")], 0.35 + 0.4 * s.heat,
                   {**E, "helm": 0.4}, "boost")
    if m is not None and s.torps_left < max(1, s.tubes) * 2 and s.tubes:
        yield Move("save-torps", "Save the torpedoes: fight with phasers",
                   f"Only {s.torps_left} torpedoes left. Phasers recharge; torpedoes don't. Keep the last ones for a "
                   "kill.", [Step(f"pursue {m.handle}", "close to phaser range"),
                             Step("mode tubes manual", "tubes fire only on your order")], 0.6, {**E, "tactical": 0.3}, "helm")
    if s.calls_left > 0 and (s.outgunned or s.hull < 0.5):
        yield Move("starfleet", "Call Starfleet in",
                   f"Their strength is {s.theirs:.0f} to our {s.ours:.0f}. Starfleet can have a ship here in about "
                   f"{s.eta:.0f} cycles; we have {s.calls_left} call{'s' if s.calls_left != 1 else ''} left this tour.",
                   [Step("request reinforcements", "ask Starfleet for a ship")], 0.75 if s.outgunned else 0.5,
                   {**E, "tactical": 0.2}, "starfleet")
    for a in s.allies:
        if a.hull < 0.35 and a.order not in ("withdraw", "run"):
            yield Move("ally-back", f"Pull the {a.name} back",
                       f"The {a.name}'s hull is at {_pct(a.hull)}. One more salvo and we lose her and her crew.",
                       [Step(f"tell {a.name.lower()} withdraw", "she leaves the fight")], 0.65, {**E, "helm": 0.3},
                       "squadron")
            break
    if s.can_cloak and not s.cloaked and m is not None and (s.hull < 0.5 or s.inbound >= 2) and not m.hive:
        yield Move("cloak", "Cloak and break their lock",
                   f"Hull at {_pct(s.hull)}{f' and {s.inbound} weapons inbound' if s.inbound else ''}. Under the cloak "
                   "their torpedoes lose us and we choose when to come back.",
                   [Step("cloak on", "cloak")], 0.55, {**E, "helm": 0.5}, "cloak")
    if s.morale < 40:
        yield Move("rally", "A word to the crew",
                   f"Morale is {s.morale:.0f}. A shaken crew loads, repairs and aims slower.",
                   [Step("address crew Steady. We have the better ship and the better crew.", "rally them")], 0.45,
                   {**E}, "morale")


def _knowledge(s: Situation) -> Iterator[Move]:
    S = {"science": 1.0}
    m = s.main_threat
    unscanned = [e for e in s.fighting if e.visible and not e.scanned and e.range < 40000 and e.cls is not None]
    if unscanned:
        e = m if m is not None and m in unscanned else unscanned[0]
        yield Move("scan", f"Scan the {e.name}",
                   f"We know nothing of the {e.name}'s shields, loaded tubes or damage. A scan shows where to hit her "
                   "and what she can still do.", [Step(f"scan {e.handle}", "full scan")],
                   0.8 if e is m else 0.55, {**S, "tactical": 0.25}, "scan")
    if m is not None and m.scanned and not m.hive and s.tubes and "disable" not in s.objectives:
        if m.runner or m.style == "raid":
            system, why = "engines", "she fights by running; without her drives she can only stand and take it"
        elif m.threat > s.ours * 0.45 or (m.banks_ready or 0) >= 3 or (m.tubes_loaded or 0) >= 3:
            system, why = "weapons", (f"she outguns what we can absorb: {m.banks_ready or 0} banks charged and "
                                      f"{m.tubes_loaded or 0} tubes loaded at the last scan")
        else:
            system, why = "shields", "a permanent hole in her shields makes every later hit count"
        yield Move("disable", f"Disable the {m.name}'s {system}",
                   f"Knock out exactly what decides this fight: {why}. I burst torpedoes where her point defense won't "
                   "react, then spare her.", [Step(f"disable {m.handle} {system}", f"her {system}")], 0.65,
                   {**S, "tactical": 0.35}, "objective")
    t = s.target_view or m
    if (t is not None and t.visible and t.pd_discipline >= 0.8 and s.tubes_loaded >= 3 and _in_env(s, t)
            and not t.hive and not s.hold_fire):
        yield Move("ring", f"Fan the salvo past the {t.name}'s point defense",
                   f"Her gunners are disciplined: they hold their banks for a salvo, not a lone round. Fanned 15°, the "
                   f"{s.tubes_loaded} rounds arrive from different angles and only some can be stopped.",
                   [x for x in (_target(s, t),) if x] + [Step("fire all torpedoes spread 15", "a fanned salvo")], 0.6,
                   {**S, "tactical": 0.5}, "torpedoes")
    cloaked = [e for e in s.enemies if e.cloaked_hint and not e.visible]
    if cloaked:
        e = min(cloaked, key=lambda e: e.range)
        if s.deflector:
            steps = [Step(f"helm {e.bearing:.0f}", "turn toward her"), Step("pulse", "deflector pulse")]
            how = f"Turn to bearing {e.bearing:.0f} and pulse the deflector: it lights up a cloaked ship in the cone."
        elif "tachyon" in s.projects or any(o == "hunt" for o in s.objectives):
            steps, how = [], ""
        else:
            steps = [Step(f"hunt {e.handle}", "find her")]
            how = "I'll build a tachyon detector, burst it where she should be, and target her for you."
        if steps:
            yield Move("hunt", f"Find the {e.name}", f"We lost the {e.name} at {_rng(e.range)}: she has cloaked. " + how,
                       steps, 0.9, {**S, "tactical": 0.4, "helm": 0.3}, "hunt")
    venting = [e for e in s.enemies if e.exhaust and not e.surrendered]
    if venting and "strike" not in s.objectives and not s.hold_fire:
        yield from _sweep_strike(s, min(venting, key=lambda e: e.range))
    elif s.trails or venting:
        ex = venting[0] if venting else None
        steps = [Step(f"seeker {ex.handle}" if ex else "seeker", "plasma-seeker down her trail")] if ex or s.trails else []
        steps.insert(0, Step("sweep", "sweep for plasma trails"))
        yield Move("trails", "Follow the plasma trail",
                   "A damaged warp drive vents plasma we can sweep for and follow, cloaked or not. A seeker flies down "
                   "the trail to whoever left it.", steps, 0.6, {**S, "tactical": 0.3}, "hunt")
    for e in s.fighting:
        if not (e.hive and e.visible):
            continue
        if e.weak_point:
            yield Move("relay", f"Hit the {e.name}'s vinculum relay",
                       f"I have found her relay in her {e.weak_point}. Destroy it and every drone aboard goes dormant.",
                       [x for x in (_target(s, e, "relay"),) if x] + [Step(f"away {e.handle} relay", "an away team")],
                       0.95, {**S, "tactical": 0.6}, "borg")
        elif s.duty != "harmonics":
            yield Move("learn", f"Learn the {e.name}",
                       "Trading shots only teaches her. Keep scanning: halfway through I find her vinculum relay, at the "
                       "end her shield harmonics.", [Step("duty harmonics", "study her"), Step(f"scan {e.handle}", "scan")],
                       0.85, {**S}, "borg")
        if s.tuning < 0.5 and s.duty != "shields":
            yield Move("tune", "Tune our shields against her beams",
                       "Untuned, our shields let her drones beam aboard. Past halfway her transporters can't lock on.",
                       [Step("tune shields", "tune the shield harmonics")], 0.7, {**S, "engineering": 0.6}, "borg-shields")
        if e.adapted >= 0.5 and not s.remodulating:
            yield Move("remodulate", "Remodulate the phasers",
                       f"She has learned our phaser frequency ({e.adapted * 100:.0f}%). A new one starts her from nothing.",
                       [Step("remodulate", "new frequency"), Step("duty phasers", "keep them changing")], 0.8,
                       {**S, "tactical": 0.6}, "borg-phasers")
        break


def _mission_moves(s: Situation) -> Iterator[Move]:
    mv = s.mission
    if mv is None or mv.state != "open":
        return
    if mv.kind == "rescue" and mv.ward_id is not None:
        near = mv.ward_range <= 2800.0
        left = f", {mv.time_left:.0f} cycles before her reactor fails" if mv.time_left is not None else ""
        rate = s.transporters * s.beam_cap * 0.06
        if near and mv.ward_shield is not None and mv.ward_shield.up:
            hunters = [e for e in s.fighting if e.visible and e.range < 15000]
            guard = ""
            if hunters:
                h = min(hunters, key=lambda e: e.range)
                guard = f" Keep a strong shield toward the {h.name}, {_rng(h.range)} off."
            yield Move("beam", f"Lower shield {mv.ward_shield.index + 1} and beam them across",
                       f"The {mv.ward_name} is {_rng(mv.ward_range)} off, behind our shield {mv.ward_shield.index + 1}. "
                       f"Lowered, our {s.transporters} transporters take about {rate:.0f} people a cycle: {mv.aboard} "
                       f"aboard{left}.{guard}",
                       [Step(f"lower {mv.ward_shield.index + 1}", f"shield {mv.ward_shield.index + 1} down"),
                        Step("stop", "hold station")], 1.0, {"engineering": 1.0, "helm": 0.6, "science": 0.3}, "rescue,helm")
        elif not near:
            course = mv.ward_bearing
            w = min(s.top_warp, 8.0 if mv.ward_range > 8000 else 4.0)
            yield Move("alongside", f"Bring us alongside the {mv.ward_name}",
                       f"Transporters reach {_rng(3000)}; she is {_rng(mv.ward_range)} away with {mv.aboard} aboard{left}.",
                       [Step(f"helm {course:.0f} warp {w:g}", f"toward the {mv.ward_name}")], 0.9,
                       {"helm": 1.0, "engineering": 0.6, "tactical": 0.3}, "helm")
        elif mv.beaming and s.facing is not None and s.facing.up and s.main_threat is not None:
            yield Move("guard-beam", "Hold the shield toward them while we beam",
                       f"Transporters are working: {mv.aboard} still aboard. The {s.main_threat.name} is "
                       f"{_rng(s.main_threat.range)} off: reinforce the shield that faces her.",
                       [Step(f"reenforce {s.facing.index + 1}", "reinforce it")], 0.7, {"engineering": 0.9, "helm": 0.4},
                       "shields")
    if mv.kind in ("rescue", "escort") and mv.ward_id is not None:
        hunters = [e for e in s.fighting if e.hunter and e.visible]
        if hunters:
            h = min(hunters, key=lambda e: math.hypot(mv.ward_x - (s.ship.x + e.range * math.sin(math.radians(e.bearing))),
                                                       mv.ward_y - (s.ship.y + e.range * math.cos(math.radians(e.bearing)))))
            hx = s.ship.x + h.range * math.sin(math.radians(h.bearing))
            hy = s.ship.y + h.range * math.cos(math.radians(h.bearing))
            to_ward = math.hypot(hx - mv.ward_x, hy - mv.ward_y)
            yield Move("hunters", f"Kill the {h.name} before she reaches the {mv.ward_name}",
                       f"The {h.name} is going for the {mv.ward_name}, {_rng(to_ward)} from her. "
                       f"She is the one ship that decides this mission.",
                       [x for x in (_target(s, h),) if x] + (_fire_now(s, h) or [Step(f"pursue {h.handle}", "run her down")]),
                       0.95 if to_ward < 12000 else 0.7, {"tactical": 1.0, "science": 0.4, "helm": 0.4}, "target",
                       voice={"tactical": f"Kill the {h.name}: she hunts the {mv.ward_name}"})
            if to_ward < 15000:
                px, py = mv.ward_x + (hx - mv.ward_x) * 0.3, mv.ward_y + (hy - mv.ward_y) * 0.3
                course = bearing(px - s.ship.x, py - s.ship.y)
                yield Move("interpose", f"Put us between the {h.name} and the {mv.ward_name}",
                           f"Her torpedoes must pass us to reach the {mv.ward_name}. Point defense and a strong shield "
                           "take what's meant for her, and the hunter must deal with us first.",
                           [Step(f"helm {course:.0f} warp {min(s.top_warp, 8.0):g}", "interpose")], 0.8,
                           {"helm": 1.0, "engineering": 0.4}, "helm")
                if h.scanned:
                    yield Move("disable-hunter", f"Disable the {h.name}'s weapons",
                               f"Without her weapons the {h.name} can chase the {mv.ward_name} all she likes.",
                               [Step(f"disable {h.handle} weapons", "her weapons")], 0.75, {"science": 1.0}, "objective")
    if mv.kind == "escort" and mv.ward_id is not None and mv.ward_range > 6000:
        yield Move("convoy-close", f"Close up on the {mv.ward_name}",
                   f"She is {_rng(mv.ward_range)} from us and {_rng(mv.to_range)} from safety. The hunters will go for her, "
                   "not us: we fight best where she is.",
                   [Step(f"helm {mv.ward_bearing:.0f} warp {min(s.top_warp, 8.0):g}", f"to the {mv.ward_name}")],
                   0.75 if any(e.hunter for e in s.enemies) else 0.5, {"helm": 1.0, "engineering": 0.6}, "helm")
    elif mv.kind == "escort" and mv.ward_id is not None and mv.ward_hull < 0.5:
        yield Move("convoy-guard", f"Escort the {mv.ward_name} close",
                   f"Her hull is at {_pct(mv.ward_hull)} and she is {_rng(mv.to_range)} from safety.",
                   [Step(f"helm {mv.ward_bearing:.0f} warp {min(s.top_warp, 8.0):g}", f"to the {mv.ward_name}")], 0.7,
                   {"helm": 0.8, "engineering": 0.8}, "helm")
    if mv.kind == "intercept" and mv.runner_id is not None:
        r = s.enemy(mv.runner_id)
        if r is not None and r.visible:
            esc = f" At her speed she is clear in about {mv.runner_escape:.0f} cycles." if mv.runner_escape else ""
            reach = max(s.phaser_range, r.our_env[1] if r.our_env else 0.0)
            # lock on only once she is in reach: a lock on a ship out of range keeps our weapons off the ones that are
            aim = [x for x in (_target(s, r),) if x] if r.range <= reach * 1.1 else []
            steps = aim + [Step(f"pursue {r.handle} warp {s.top_warp:g}", "run her down")]
            if s.heat > 0.4 and not s.boost:
                steps.append(Step("boost", "keep the drives cool"))
            yield Move("run-down", f"Run down the {r.name}",
                       f"The {r.name} is {_rng(r.range)} off and making for the edge at warp {r.max_warp:g}; we make "
                       f"{s.top_warp:g}.{esc} If she reaches her people, they learn everything she saw.",
                       steps, 0.95, {"tactical": 1.0, "helm": 0.8}, "target",
                       voice={"helm": f"Cut the {r.name} off"})
            if mv.runner_intercept is not None and mv.runner_meet is not None and r.range > 4000:
                yield Move("intercept", f"Cut the {r.name} off",
                           f"A stern chase gives her the lead she started with. Course {mv.runner_intercept:.0f} at warp "
                           f"{s.top_warp:g} meets her in about {mv.runner_meet:.0f} cycles"
                           + (", well before she is clear." if mv.runner_escape and mv.runner_meet < mv.runner_escape
                              else "; it is close.") + " I will come round onto her when we are in range.",
                           [Step(f"helm {mv.runner_intercept:.0f} warp {s.top_warp:g}", "intercept course")], 1.0,
                           {"helm": 1.0, "engineering": 0.4}, "helm")
            if r.scanned:
                yield Move("runner-engines", f"Take out the {r.name}'s engines",
                           "A ship that can't move can't run. I'll burst torpedoes at her drives and spare the rest of her.",
                           [Step(f"disable {r.handle} engines", "her engines")], 0.85, {"science": 1.0, "tactical": 0.4},
                           "objective")
            elif r.range < 20000:
                yield Move("runner-scan", f"Scan the {r.name}",
                           "Before we chase her we should know her drives' state: a damaged one is slower than she looks.",
                           [Step(f"scan {r.handle}", "full scan")], 0.75, {"science": 1.0}, "scan")
        elif r is not None and (r.cloaked_hint or r.exhaust):
            yield Move("runner-hunt", f"Find the {r.name}",
                       f"The {r.name} has gone dark. She is still running.", [Step(f"hunt {r.handle}", "find her")], 0.95,
                       {"science": 1.0, "tactical": 0.5}, "hunt")


# ------------------------------------------------------------------ assembling plans

def plan_for(station: str, all_moves: list[Move], taken: set[str] | None = None) -> tuple[Move | None, list[Move]]:
    """The lead move and the moves that follow it for one station's perspective. A move another officer already
    leads with is passed over when this perspective has another of its own worth nearly as much: four officers
    saying the same thing is one opinion, not counsel."""
    ranked = sorted(all_moves, key=lambda m: -m.value(station))
    own = [m for m in ranked if m.leans.get(station, 0.0) >= OWN and m.value(station) > 0.05]
    if taken and own and own[0].key in taken:
        alt = next((m for m in own if m.key not in taken and m.value(station) >= own[0].value(station) * 0.45), None)
        if alt is not None:
            own.remove(alt)
            own.insert(0, alt)
    if own:
        lead: Move | None = own[0]
    else:
        open_ = [m for m in ranked if m.value(station) > 0.05]
        lead = next((m for m in open_ if not taken or m.key not in taken), open_[0] if open_ else None)
    if lead is None:
        return None, []
    return lead, follow_on(station, lead, ranked)


def follow_on(station: str, lead: Move, all_moves: list[Move]) -> list[Move]:
    """The moves that follow a lead in one station's plan: the best of the rest that claim nothing the lead (or an
    earlier follow-on) already claims, up to MAX_STEPS steps."""
    ranked = sorted(all_moves, key=lambda m: -m.value(station))
    chosen = [lead]
    groups = _groups(lead)
    n = len(lead.steps)
    for m in ranked:
        if m is lead or m.value(station) < lead.value(station) * 0.3 or n >= MAX_STEPS:
            continue
        if _groups(m) & groups:
            continue
        if n + len(m.steps) > MAX_STEPS:
            continue
        lines = {st.line for c in chosen for st in c.steps}
        if any(st.line in lines for st in m.steps):
            continue
        chosen.append(m)
        n += len(m.steps)
        groups |= _groups(m)
    return chosen[1:]


_HELM_VERBS = ("pursue ", "elude ", "helm ", "stop", "warp ")
_OBJECTIVE_VERBS = ("disable ", "capture ", "strike ")


def _groups(m: Move) -> set[str]:
    """What a move claims: its own groups, plus the target and the helm if its steps set them (a plan that
    targets two ships or steers two ways at once is no plan)."""
    out = {g for g in m.group.split(",") if g}
    for st in m.steps:
        if st.line.startswith("target "):
            out.add("target")
        if st.line.startswith(_HELM_VERBS):
            out.add("helm")
        if st.line.startswith(("fire ", "volley")):
            out.add("fire")
        if st.line.startswith(_OBJECTIVE_VERBS):
            out |= {"target", "fire"}      # an officer's objective works the weapons herself: no captain's fire beside it
        if st.line.startswith("strike "):
            out.add("helm")                # [E] and a sweep and strike closes to torpedo range off her trail
    return out


def counsel(s: Situation, officers: Mapping[str, object], check: Check | None = None,
            goal: Goal | None = None) -> list[Plan]:
    """Each officer's plan, in station order. `officers` maps station -> officer profile (with `id` and `name`);
    `check(line)` is the console's dry run: a step it would refuse is never offered. With a `goal`, each plan is
    that officer's way to it."""
    if not s.ship.alive:
        return []
    all_moves = moves(s, goal)
    if check is not None:
        kept = []
        for m in all_moves:
            m.steps = [st for st in m.steps if check(st.line) is None]
            if m.steps:
                kept.append(m)
        all_moves = kept
    out: list[Plan] = []
    taken: set[str] = set()
    leads: dict[str, Move] = {}
    for station in STATIONS:              # first each officer's own lead, four different ways forward
        if officers.get(station) is None:
            continue
        lead, _ = plan_for(station, all_moves, taken)
        if lead is not None:
            leads[station] = lead
            taken.add(lead.key)
    # what follows each lead, leaving another officer's lead to that officer, and a move two plans would both follow
    # with to the officer whose own perspective it is: four plans, not one plan four times
    lead_lines = {st: {x.line for x in m.steps} for st, m in leads.items()}
    lead_keys = {m.key for m in leads.values()}

    def free(station: str) -> list[Move]:
        theirs = set().union(*(v for st, v in lead_lines.items() if st != station))
        return [m for m in all_moves if m.key not in lead_keys and not any(x.line in theirs for x in m.steps)]

    first = {st: follow_on(st, lead, free(st)) for st, lead in leads.items()}
    owner: dict[str, str] = {}
    for st, rest in first.items():
        for m in rest:
            cur = owner.get(m.key)
            if cur is None or m.leans.get(st, 0.0) > next(x for x in first[cur] if x.key == m.key).leans.get(cur, 0.0):
                owner[m.key] = st
    for station in STATIONS:
        o = officers.get(station)
        lead = leads.get(station)
        if o is None or lead is None:
            continue
        mine = [m for m in free(station) if owner.get(m.key, station) == station]
        rest = follow_on(station, lead, mine)
        claimed = {x.line for st, r in first.items() if st != station for m in r if owner.get(m.key) == st
                   for x in m.steps}
        rest = [m for m in rest if not any(x.line in claimed for x in m.steps)]
        steps: list[Step] = []
        for m in (lead, *rest):
            for step in m.steps:
                if len(steps) < MAX_STEPS and step.line not in {x.line for x in steps}:
                    steps.append(step)
        reason = lead.reason
        if rest:
            reason += " Then: " + "; ".join(m.title[0].lower() + m.title[1:] for m in rest[:2]) + "."
        out.append(Plan(station, str(getattr(o, "id", station)), str(getattr(o, "name", station)), PERSPECTIVE[station],
                        lead.voice.get(station, lead.title), reason, tuple(steps), (lead.key, *(m.key for m in rest))))
    return out


__all__ = ["Goal", "MAX_STEPS", "Move", "parse_goal", "PERSPECTIVE", "Plan", "STATIONS", "Step", "counsel", "moves", "odds", "plan_for"]
