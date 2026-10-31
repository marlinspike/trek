"""What enemy captains make of the fight, and how they answer a hail [E].

Every AI captain watches what happens to their own side. Shields collapsing,
hull hits, ships destroyed, captured or surrendering: each is a shock. How a
captain takes it depends on their temper (rolled per captain from the race's
`temperament` in factions.toml): a cool one is cowed by it (fear), a hot one
is enraged (anger) and holds the ship that did it responsible. Every loss they
watch also wears down their resolve, which starts at their obstinacy, so even
a stubborn captain comes round after seeing their friends battered.

Fear makes a captain break off sooner and strike their colours more readily;
anger makes them fight harder and go after whoever they blame (ai/captain.py).

The captain of a ship can hail an enemy (`Hail` in sim/commands.py). This
module decides the answer from the enemy captain's state of mind, their own
damage, their crew's morale, the odds as they see them and how persuasive the
hail was. A captain who surrenders lowers their shields and their weapons go
cold: the victor can keep firing (straight into the hull) or beam a party
across and take the ship without a fight, the crew held as prisoners. One who
agrees to withdraw holds fire and leaves the field; fire on them and the deal
is off. Fire on a ship that has surrendered and every captain who sees it
trusts you less.

Everything here is deterministic: hails are commands, and their dice come from
the world's seeded streams. The words of the exchange are the comms layer's
(crew/hails.py), with or without a language model.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Iterable

from ..events import CaptainMood, Event, HailAnswered, HullHit, ShieldHit, ShipStatusChanged, SubsystemDamaged
from ..ship import Ship, ShipStatus

if TYPE_CHECKING:
    from ...ai.personality import Personality
    from ..world import World

INTENTS = ("surrender", "withdraw", "threat", "taunt", "talk")
DEMANDS = ("surrender", "withdraw")

# shocks: how hard each thing seen happening to one's own side lands (before temper and distance)
SHOCK_HULL = 0.35           # × the share of the victim's hull lost in one hit, capped below
SHOCK_HULL_CAP = 0.1
SHOCK_SHIELD_DOWN = 0.04
SHOCK_SYSTEM_LOST = 0.02
SHOCK_LOST = {"destroyed": 0.38, "derelict": 0.32, "captured": 0.30, "surrendered": 0.22}
SELF_SHARE = 0.5            # what a captain's own ship taking hits does to them, × the shock to a watcher
FAR = 0.5                   # × the shock for an ally lost far away (heard over comms, not watched)
RISE = 1.6                  # how fast fear and anger build from a shock
WEAR = 0.45                 # how fast resolve is worn down
COOL_PER_CYCLE = 0.006      # anger fades this much a cycle
CALM_PER_CYCLE = 0.003      # fear fades this much a cycle
MOOD_AT = 0.45              # fear or anger above this shows (they say so)
WAVER_AT = 0.2              # resolve below this: they are wavering
HAIL_GAP_CYCLES = 6.0       # a captain answers the same enemy once in this many cycles
PESTER_CYCLES = 20.0        # hailed again inside this, they grow irritated
TREACHERY_DISTRUST = 0.45   # firing on a ship that surrendered: every witness trusts you this much less
TREACHERY_ANGER = 0.35


def seat(ship: Ship, p: Personality) -> None:
    """Give a ship's mood its captain's temperament (when an AI captain takes command)."""
    m = ship.mood
    m.temper, m.obstinacy, m.fanaticism = p.temper, p.obstinacy, p.fanaticism
    if not m.seated:
        # on a tour, word of how we treated earlier surrenders has gone ahead of us
        m.trust = p.trust
        m.resolve = _clamp(p.obstinacy * (1.0 - 0.35 * max(0.0, p.trust)))
        m.distrust = max(m.distrust, 0.6 * max(0.0, -p.trust))
    m.seated = True


def _clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


# ------------------------------------------------------------------ watching the fight

def update_disposition(world: World, events: Iterable[Event], dt: float) -> None:
    """Weigh this tick's events in every watching captain's mind, then let tempers cool a little."""
    ships = world.ships
    for ev in events:
        if isinstance(ev, HullHit):
            v = ships.get(ev.ship_id)
            if v is None:
                continue
            a = ships.get(ev.attacker) if ev.attacker is not None else None
            if a is not None and a.side != v.side:
                if v.status == ShipStatus.SURRENDERED:
                    _treachery(world, v, a, "fired on the surrendered " + v.name)
                    continue
                _broken_terms(world, v, a)
            share = ev.amount / max(1.0, v.structure_max)
            _witness(world, v, min(SHOCK_HULL_CAP, SHOCK_HULL * share), a, f"{v.name}'s hull breached", self_too=True)
        elif isinstance(ev, ShieldHit):
            v = ships.get(ev.ship_id)
            a = ships.get(ev.attacker) if ev.attacker is not None else None
            if v is None or a is None or a.side == v.side:
                continue
            if v.status == ShipStatus.SURRENDERED:
                _treachery(world, v, a, "fired on the surrendered " + v.name)
                continue
            _broken_terms(world, v, a)
            if ev.collapsed:
                _witness(world, v, SHOCK_SHIELD_DOWN, a, f"{v.name}'s shields failing", self_too=True)
        elif isinstance(ev, SubsystemDamaged) and ev.destroyed:
            v = ships.get(ev.ship_id)
            if v is not None:
                _witness(world, v, SHOCK_SYSTEM_LOST, None, f"{v.name} losing systems", self_too=True)
        elif isinstance(ev, ShipStatusChanged) and ev.status in SHOCK_LOST:
            v = ships.get(ev.ship_id)
            if v is None:
                continue
            a = ships.get(ev.by_ship) if ev.by_ship is not None else None
            if ev.status == "captured":
                # she has changed sides by now: her old side is whoever is not her new one, among the watchers
                old = _old_side(ev.cause)
                _witness(world, v, SHOCK_LOST["captured"], None, v.name, side=old, lost=True)
            else:
                _witness(world, v, SHOCK_LOST[ev.status], a, v.name, lost=True)
    tpc = world.rules.ticks_per_cycle
    if world.tick % tpc:
        return
    for s in ships.values():
        m = s.mood
        if not s.alive or not m.seated:
            continue
        m.anger = max(0.0, m.anger - COOL_PER_CYCLE * dt * tpc)
        m.fear = max(0.0, m.fear - CALM_PER_CYCLE * dt * tpc)


def _old_side(cause: str) -> int | None:
    try:
        return int(cause.rsplit(" ", 1)[-1])
    except ValueError:
        return None


def _witness(world: World, victim: Ship, shock: float, attacker: Ship | None, what: str,
             self_too: bool = False, side: int | None = None, lost: bool = False) -> None:
    if shock <= 0:
        return
    side = victim.side if side is None else side
    near = world.rules.battle_enemy_range * 1.5
    for w in world.ships.values():
        if not w.alive or w.side != side or not w.mood.seated:
            continue
        if w.id == victim.id:
            if self_too:
                _shock(world, w, shock * SELF_SHARE, attacker, what, lost=False)
            continue
        d = ((w.x - victim.x) ** 2 + (w.y - victim.y) ** 2) ** 0.5
        _shock(world, w, shock * (1.0 if d <= near else FAR), attacker, what, lost=lost, name=victim.name)


def _shock(world: World, w: Ship, shock: float, attacker: Ship | None, what: str, lost: bool,
           name: str = "") -> None:
    m = w.mood
    hot = anger_share(m.temper)
    m.anger = _clamp(m.anger + shock * RISE * hot * (1.0 - m.anger))
    m.fear = _clamp(m.fear + shock * RISE * (1.0 - hot) * (1.0 - m.fear) * (1.0 - 0.6 * m.fanaticism))
    m.resolve = _clamp(m.resolve - shock * WEAR * (1.0 - 0.5 * hot))
    if attacker is not None and (m.nemesis is None or hot >= 0.5):
        m.nemesis = attacker.id
    if lost and name and name not in m.seen_lost:
        m.seen_lost.append(name)
    _show(world, w, name or what, attacker)


def anger_share(temper: float) -> float:
    """How much of a shock turns to anger rather than fear: none below a temper of 0.35, all of it above 0.85."""
    return _clamp((temper - 0.35) / 0.5)


def _show(world: World, w: Ship, cause: str, attacker: Ship | None) -> None:
    """Emit a CaptainMood when the captain's state of mind changes enough to show."""
    m = w.mood
    word = shows(w)
    if word and word != m.said:
        m.said = word
        world.emit(CaptainMood(world.tick, w.id, word, cause, attacker.id if attacker is not None else m.nemesis))


def shows(s: Ship) -> str:
    """The mood a captain lets show: enraged, shaken, wavering, or "" (composed)."""
    m = s.mood
    if m.anger >= MOOD_AT and m.anger >= m.fear:
        return "enraged"
    if m.fear >= MOOD_AT:
        return "shaken"
    if m.resolve < WAVER_AT and m.obstinacy >= WAVER_AT and m.fear > m.anger:
        return "wavering"
    return ""


def _broken_terms(world: World, v: Ship, a: Ship) -> None:
    """Firing on a ship that agreed to withdraw: the deal is off, and they are furious."""
    m = v.mood
    if m.terms and m.terms_side == a.side:
        world.faith_broken.setdefault(a.side, set()).add(v.id)
        m.terms = ""
        v.hold_fire = False
        m.anger = _clamp(m.anger + 0.4)
        m.nemesis = a.id
        m.said = ""
        world.emit(CaptainMood(world.tick, v.id, "betrayed", v.name, a.id))
        m.said = "enraged"


def _treachery(world: World, v: Ship, a: Ship, what: str) -> None:
    """Fire on a ship that struck her colours: every captain of her side who sees it trusts you less."""
    world.faith_broken.setdefault(a.side, set()).add(v.id)
    for w in world.ships.values():
        if not w.alive or w.side != v.side or not w.mood.seated or w.id == v.id:
            continue
        m = w.mood
        first = m.distrust < TREACHERY_DISTRUST
        m.distrust = _clamp(m.distrust + TREACHERY_DISTRUST * 0.5)
        m.anger = _clamp(m.anger + TREACHERY_ANGER * 0.5 * (0.5 + m.temper))
        m.nemesis = a.id
        if first:
            m.said = ""
            world.emit(CaptainMood(world.tick, w.id, "betrayed", v.name, a.id))
            m.said = shows(w) or "betrayed"


# ------------------------------------------------------------------ answering a hail

@dataclass(frozen=True)
class Reading:
    """How a captain sees their position when hailed (also what the comms layer tells the model)."""

    fear: float          # fear with their own damage, morale and the odds folded in
    anger: float
    resolve: float
    distrust: float
    hull_lost: float
    odds: float          # the hailer's side's share of the strength on the field, as they see it
    pliancy: float       # fear less what holds them: above 0.3 or so they will listen


def side_strength(world: World, side: int) -> float:
    return sum(s.cls.mass * max(0.0, s.structure) / max(1.0, s.structure_max)
               for s in world.ships.values() if s.alive and s.side == side)


def weapons_left(s: Ship) -> float:
    mounts = list(s.banks) + list(s.tubes)
    return sum(1 for x in mounts if x.intact) / len(mounts) if mounts else 0.0


def reading(world: World, hailer: Ship, target: Ship) -> Reading:
    m = target.mood
    hull_lost = 1.0 - max(0.0, target.structure) / max(1.0, target.structure_max)
    ours, theirs = side_strength(world, hailer.side), side_strength(world, target.side)
    odds = ours / max(1.0, ours + theirs)
    fear = _clamp(m.fear + 0.45 * hull_lost + 0.25 * (1.0 - weapons_left(target)) + 0.5 * (odds - 0.5)
                  + 0.25 * max(0.0, -target.morale_factor) + (0.15 if not target.can_move() else 0.0))
    pliancy = fear - 0.55 * m.resolve - 0.5 * m.anger - 0.3 * m.fanaticism + 0.15 * max(0.0, m.trust)
    return Reading(fear, m.anger, m.resolve, m.distrust, hull_lost, odds, pliancy)


def seen_through(world: World, hailer: Ship, target: Ship) -> bool:
    """A bluff fails when they have scanned us and what they saw doesn't back it up."""
    intel = world.intel.get(target.side)
    c = intel.contacts.get(hailer.id) if intel is not None else None
    if c is None or c.scan is None:
        return False
    return c.scan.structure_frac < 0.7 or weapons_left(hailer) < 0.6


def mood_word(r: Reading, s: Ship) -> str:
    if r.anger >= 0.5 and r.anger >= r.fear:
        return "enraged"
    if r.fear >= 0.75 and r.anger < 0.3:
        return "broken"
    if r.fear >= MOOD_AT:
        return "shaken"
    if s.mood.resolve < WAVER_AT and s.mood.obstinacy >= WAVER_AT:
        return "wavering"
    return "calm"


def answer(world: World, hailer: Ship, target: Ship, intent: str, persuasion: float = 1.0,
           threat: bool = False, bluff: bool = False, release: bool = False) -> HailAnswered:
    """The enemy captain hears the hail and answers. Applies what they agree to; returns the event (emitted)."""
    m = target.mood
    r_ = world.rules
    tpc = r_.ticks_per_cycle
    rng = world.rng.derive(f"hail:{target.id}:{world.tick}")
    persuasion = _clamp(persuasion, 0.0, 1.5)
    t = m.temper
    if world.tick - m.last_hailed < PESTER_CYCLES * tpc:
        m.anger = _clamp(m.anger + 0.05)          # pestered
    m.last_hailed = world.tick
    m.hails += 1
    why: list[str] = []

    if bluff:
        if seen_through(world, hailer, target):
            persuasion -= 0.5
            m.anger = _clamp(m.anger + 0.15)
            why.append("their scans don't back up your bluff")
        else:
            persuasion += 0.3
            threat = True
            why.append("they believe the bluff")
    if threat or intent == "threat":
        before = reading(world, hailer, target)
        weight = 0.12 * max(0.3, persuasion) * (0.5 + before.odds)
        m.fear = _clamp(m.fear + weight * (1.0 - t))
        m.anger = _clamp(m.anger + weight * t)
        m.resolve = _clamp(m.resolve - 0.06 * persuasion * (1.0 - t))
    if intent == "taunt":
        m.anger = _clamp(m.anger + 0.12 + 0.1 * t)

    r = reading(world, hailer, target)
    mood = mood_word(r, target)
    if m.seen_lost:
        why.append(f"they have watched {_names(m.seen_lost)} lost")
    if r.hull_lost > 0.5:
        why.append("their hull is failing")
    if r.odds > 0.65:
        why.append("they are outgunned")
    elif r.odds < 0.35:
        why.append("they think they are winning")
    if m.distrust > 0.2:
        why.append("they no longer trust your word")

    outcome = "talk" if intent in ("talk", "threat", "taunt") else "refuse"
    p = captain_odds(world, hailer, target, intent, persuasion)
    if intent == "withdraw" and p == 0.0 and (target.cls.is_base or not target.can_move()):
        why.append("they cannot leave")
    if intent in DEMANDS:
        if rng.unit() < p:
            outcome = intent
        elif r.anger >= 0.8 and rng.unit() < 0.4:
            outcome = "silence"
        elif r.anger >= 0.45 or (persuasion < 0.5 and t >= 0.5):
            outcome = "defy"
        elif p >= 0.15:
            outcome = "waver"
            m.resolve = _clamp(m.resolve - 0.08 * max(0.5, persuasion))   # pressed again, they may give way
        else:
            outcome = "refuse"
            m.resolve = _clamp(m.resolve - 0.03 * persuasion)
    elif intent == "taunt" or (intent == "threat" and r.anger >= 0.45):
        outcome = "silence" if r.anger >= 0.85 and rng.unit() < 0.3 else "defy"

    if outcome == "surrender":
        world.surrender(target)
        mood = "broken" if r.fear >= 0.6 else mood
    elif outcome == "withdraw":
        m.terms, m.terms_side = "withdraw", hailer.side
        target.hold_fire = True
        target.desired_warp = target.max_attainable_warp
        if release:
            n = _release_prisoners(world, hailer.side, target)
            if n:
                why.append(f"{n} prisoners beamed back to them")
    ev = HailAnswered(world.tick, hailer.id, target.id, intent, outcome, mood, "; ".join(why))
    world.emit(ev)
    return ev


def _release_prisoners(world: World, side: int, to: Ship) -> int:
    """Send the prisoners we hold back to an enemy ship that agreed terms; returns how many went."""
    room = max(0, to.cls.crew - to.crew)
    sent = 0
    for s in world.ships.values():
        if s.side != side or not s.alive or s.prisoners <= 0 or room <= 0:
            continue
        n = min(s.prisoners, room)
        s.prisoners -= n
        to.crew += n
        room -= n
        sent += n
    return sent


def _names(names: list[str]) -> str:
    if len(names) == 1:
        return f"the {names[0]}"
    return ", ".join(f"the {n}" for n in names[:-1]) + f" and the {names[-1]}"


def captain_odds(world: World, hailer: Ship, target: Ship, intent: str, persuasion: float = 1.0) -> float:
    """The chance a demand is accepted now (for tests and tuning; no dice rolled, nothing changed)."""
    r = reading(world, hailer, target)
    if intent == "surrender":
        sw = world.content.factions[target.faction].doctrine.surrender_willingness
        scale = 0.4 + 0.6 * min(1.0, sw * 2.5)          # a proud navy's captains rarely strike their colours...
        scale += (1.0 - scale) * _clamp((r.fear - 0.6) / 0.4)   # ...unless they are truly terrified
        return _clamp((r.pliancy - 0.3 + 0.3 * (persuasion - 1.0) - 0.4 * r.distrust) * 2.0) * scale
    if intent == "withdraw":
        if target.cls.is_base or not target.can_move():
            return 0.0
        return _clamp((r.pliancy + 0.05 + 0.3 * (persuasion - 1.0) - 0.2 * r.distrust) * 1.8)
    return 0.0


__all__ = [
    "DEMANDS", "HAIL_GAP_CYCLES", "INTENTS", "Reading", "answer", "captain_odds", "mood_word", "reading", "seat",
    "seen_through", "shows", "update_disposition",
]
