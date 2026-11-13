"""Starfleet's assessment: the story of a battle, as Starfleet Command would read it [E].

The end of every battle opens on this page; the old table of numbers is one click behind it. It answers what a
captain's superiors ask: was the mission done, who lived and who died, how did we conduct ourselves, what did it
cost, and what follows. At most one commendation, and only for something specific. Then a line from each officer
whose work showed, in their own manner, built from what happened.

Everything here is read from the world once the battle is over (when it is all public knowledge). Building it
changes nothing.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field

from ..sim.events import Event, HailAnswered, ObjectiveEnded, ProjectCompleted
from ..sim.scoring import Assessment
from ..sim.ship import Ship, ShipStatus
from ..sim.world import World

GONE = (ShipStatus.DESTROYED, ShipStatus.DERELICT)

KARAGITE = ("The Karagite Order of Heroism",
            "for bringing the {people} people of the {ward} home, most of them beamed across under enemy fire.")
AXANAR = ("The Palm Leaf of Axanar Peace Mission",
          "for carrying the field while sparing the {spared} enemy crew who yielded.")
GRANKITE = ("The Grankite Order of Tactics",
            "for a decisive victory that left the {ship} sound, at {hull} hull.")


@dataclass(frozen=True)
class Commendation:
    name: str
    citation: str


@dataclass(frozen=True)
class StarfleetAssessment:
    headline: str
    outcome: str                      # "won" | "lost" | "broken off"
    mission: str = ""                 # how the mission ended, in a sentence
    mission_state: str = ""           # "" (no mission) | "done" | "failed" | "open"
    mission_kind: str = ""
    people: int = 0                   # rescue: aboard at the start
    rescued: int = 0                  # rescue: safe at the end
    crew_lost: int = 0                # ours
    enemy_spared: int = 0             # surrendered, prisoners, withdrew on terms
    enemy_lost: int = 0
    surrenders: int = 0
    prisoners: int = 0
    withdrew: int = 0                 # enemy ships that left on terms
    treachery: list[str] = field(default_factory=list)    # ships we fired on after they yielded
    hull: float = 1.0                 # the flagship's
    torps_left: int = 0
    torps_full: int = 0
    systems_down: list[str] = field(default_factory=list)
    ships_lost: list[str] = field(default_factory=list)
    escaped: list[str] = field(default_factory=list)       # enemy ships that got away (and will report)
    commendation: Commendation | None = None
    bridge: list[tuple[str, str]] = field(default_factory=list)   # (officer, their line)
    follows: list[str] = field(default_factory=list)

    @property
    def conduct(self) -> str:
        """Conduct in a sentence."""
        if self.treachery:
            return (f"We fired on {_list(self.treachery)} after {'she' if len(self.treachery) == 1 else 'they'} had "
                    "struck. Their navy will not forget it.")
        bits = []
        if self.surrenders:
            bits.append(f"{_n(self.surrenders, 'surrender')} accepted")
        if self.prisoners:
            bits.append(f"{self.prisoners} prisoners taken and held under the conventions")
        if self.withdrew:
            bits.append(f"{_n(self.withdrew, 'ship')} allowed to withdraw on terms")
        if not bits:
            return "No ship yielded; none was offered terms she accepted."
        return _cap("; ".join(bits)) + ". Every truce was kept."


def _cap(text: str) -> str:
    """First letter up, the rest as written (str.capitalize would turn "the Gr'oth" into "The gr'oth")."""
    return text[:1].upper() + text[1:]


def _n(k: int, word: str) -> str:
    return f"{k} {word}{'s' if k != 1 else ''}"


def _list(xs: list[str]) -> str:
    xs = [f"the {x}" for x in xs]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def _enemy_name(world: World, side: int) -> str:
    """'the Klingons', from the enemy side's faction."""
    others = [s for s in world.ships.values() if s.side != side and not s.ward]
    if not others:
        return "the enemy"
    faction = max({s.faction for s in others}, key=lambda f: sum(1 for s in others if s.faction == f))
    name = world.content.factions[faction].name
    plural = {"Borg": "the Borg", "Federation": "the Federation ships"}.get(name)
    return plural or f"the {name}{'s' if not name.endswith('s') else ''}"


def build(world: World, side: int, flagship: int | None, start: Assessment, deeds: Iterable[Event],
          hails: Iterable[HailAnswered] = (), officers: Mapping[str, str] | None = None,
          tour: bool = False) -> StarfleetAssessment:
    """The assessment of a finished (or abandoned) battle. `officers` maps station -> officer name."""
    w = world
    names = dict(officers or {})
    me = w.ships.get(flagship) if flagship is not None else None
    winner = w.outcome.winner if w.outcome.over else None
    outcome = "won" if winner == side else ("lost" if winner is not None or (me is not None and not me.alive
                                                                              and me.status != ShipStatus.ESCAPED)
                                             else "broken off")
    enemy = _enemy_name(w, side)
    m = w.mission if w.mission is not None and w.mission.side == side else None
    # lives
    ours: list[Ship] = []
    theirs: list[Ship] = []
    for s in w.ships.values():
        owner = start.start_owner.get(s.id, s.side)
        if s.ward or s.cls.craft:
            continue
        (ours if owner == side else theirs).append(s)

    def died(s: Ship) -> int:
        if s.status in GONE:
            return max(start.start_crew.get(s.id, s.cls.crew), s.stats.crew_lost)
        return s.stats.crew_lost

    crew_lost = sum(died(s) for s in ours)
    enemy_lost = sum(died(s) for s in theirs)
    surrendered = [s for s in theirs if s.status in (ShipStatus.SURRENDERED, ShipStatus.CAPTURED) or s.side == side]
    withdrew = [s for s in theirs if s.status == ShipStatus.ESCAPED and s.mood.terms and s.mood.terms_side == side]
    escaped = [s.name for s in theirs if s.status == ShipStatus.ESCAPED and s not in withdrew]
    prisoners = sum(s.prisoners for s in w.ships.values() if s.side == side and s.alive)
    spared = prisoners + sum(s.crew for s in surrendered if s.side != side) + sum(s.crew for s in withdrew)
    broken = [w.ships[i].name for i in sorted(w.faith_broken.get(side, set())) if i in w.ships]
    ships_lost = [s.name for s in ours if s.status in GONE or s.side != side]
    # cost
    hull = max(0.0, me.structure) / max(1.0, me.structure_max) if me is not None else 0.0
    torps = (me.torps_remaining + sum(1 for t in me.tubes if t.loaded is not None)) if me is not None else 0
    full = me.cls.torps_carried if me is not None else 0
    down = [x.label for x in me.subsystems() if x.destroyed] if me is not None and me.alive else []
    # the headline: the mission's answer first, else the field's
    mission = mission_state = kind = ""
    people = rescued = 0
    if m is not None:
        mission, mission_state, kind = m.reason, m.state, m.kind
        people, rescued = m.spec.people, m.saved
    if outcome == "lost" and me is not None and not me.alive:
        headline = f"The {me.name} has been lost."
    elif m is not None and m.state == "done":
        headline = _mission_headline(m, w)
    elif m is not None and m.state == "failed":
        headline = _mission_headline(m, w)
    elif outcome == "won":
        headline = f"{enemy[0].upper() + enemy[1:]} are beaten." if not enemy.startswith("the enemy") else \
            "The enemy is beaten."
    elif outcome == "lost":
        headline = f"{enemy[0].upper() + enemy[1:]} hold the field."
    else:
        headline = "The engagement was broken off."
    # one commendation at most, for something specific
    comm = None
    under_fire = m.rescued - m.after_battle if m is not None else 0
    if m is not None and m.kind == "rescue" and m.state == "done" and people and rescued >= people and \
            under_fire * 2 >= people and any(h for h in m.hunter_ids) and outcome != "lost":
        ward = w.ships.get(m.ward_id).name if m.ward_id in w.ships else "stricken ship"  # type: ignore[union-attr]
        comm = Commendation(KARAGITE[0], KARAGITE[1].format(people=people, ward=ward))
    elif outcome == "won" and not broken and (len(surrendered) + len(withdrew)) >= 1 and spared >= 20:
        comm = Commendation(AXANAR[0], AXANAR[1].format(spared=spared))
    elif (outcome == "won" and me is not None and hull >= 0.75 and not ships_lost and len(theirs) >= 2
          and (m is None or m.state == "done")):
        comm = Commendation(GRANKITE[0], GRANKITE[1].format(ship=me.name, hull=f"{hull:.0%}"))
    bridge = _bridge(w, side, me, names, list(deeds), list(hails), m, broken, crew_lost)
    follows = _follows(escaped, broken, len(surrendered) + len(withdrew), m, tour, enemy)
    return StarfleetAssessment(
        headline=headline, outcome=outcome, mission=mission, mission_state=mission_state, mission_kind=kind,
        people=people, rescued=rescued, crew_lost=crew_lost, enemy_spared=spared, enemy_lost=enemy_lost,
        surrenders=len(surrendered), prisoners=prisoners, withdrew=len(withdrew), treachery=broken, hull=hull,
        torps_left=torps, torps_full=full, systems_down=down, ships_lost=ships_lost, escaped=escaped,
        commendation=comm, bridge=bridge, follows=follows)


def _mission_headline(m: object, w: World) -> str:
    from ..sim.mission import Mission

    assert isinstance(m, Mission)
    ward = w.ships.get(m.ward_id) if m.ward_id is not None else None
    runner = w.ships.get(m.runner_id) if m.runner_id is not None else None
    if m.kind == "rescue":
        name = ward.name if ward is not None else m.spec.ward_name or "stricken ship"
        if m.state == "done" and m.saved >= m.spec.people:
            return f"Everyone aboard the {name} is safe."
        if m.state == "done":
            return f"{m.saved} of the {m.spec.people} aboard the {name} are safe."
        return f"The {name}'s people could not be saved." if m.saved == 0 else \
            f"Only {m.saved} of the {m.spec.people} aboard the {name} were saved."
    if m.kind == "escort":
        name = ward.name if ward is not None else m.spec.ward_name or "convoy"
        return f"The {name} got through." if m.state == "done" else f"The {name} did not get through."
    name = runner.name if runner is not None else "runner"
    return f"The {name} never made it home." if m.state == "done" else f"The {name} escaped with her report."


def _bridge(w: World, side: int, me: Ship | None, names: dict[str, str], deeds: list[Event],
            hails: list[HailAnswered], m: object, broken: list[str], crew_lost: int) -> list[tuple[str, str]]:
    """A line from each officer whose work showed, in their voice."""
    out: list[tuple[str, str]] = []
    if me is None:
        return out
    st = me.stats
    won = w.outcome.winner == side
    t = names.get("tactical")
    if t:
        if broken:
            out.append((t, "We fired on a ship that had struck her colours. There is no honour in that, Captain."))
        elif st.kills or st.torpedo_hits:
            hits = f"{st.torpedo_hits} of {st.torpedoes_fired} torpedoes found their mark" if st.torpedoes_fired else \
                f"{st.phaser_hits} phaser hits"
            out.append((t, f"{_cap(_n(st.kills, 'kill')) if st.kills else 'No kills'}, and {hits}. "
                           + ("A good day." if won else "It was not enough.")))
    h = names.get("helm")
    took = [x for x in hails if x.ship_id == me.id and x.outcome in ("surrender", "withdraw")]
    if h:
        if took:
            out.append((h, f"{_n(len(took), 'captain')} chose to {'yield' if took[0].outcome == 'surrender' else 'withdraw'} "
                           "rather than die. Logic, it seems, can be persuasive."))
        elif st.ordnance_intercepted >= 3:
            out.append((h, f"Point defense stopped {st.ordnance_intercepted} rounds meant for us."))
    e = names.get("engineering")
    if e:
        hull = max(0.0, me.structure) / max(1.0, me.structure_max)
        from ..sim.mission import Mission

        if isinstance(m, Mission) and m.kind == "rescue" and m.rescued:
            out.append((e, f"Transporter rooms brought {m.saved} people across. They're in sickbay and the cargo bays, "
                           "and they're alive."))
        elif hull < 0.5 and me.alive:
            out.append((e, f"She held, Captain, but only just: the hull's at {hull:.0%}. Give me time at a starbase."))
        elif me.alive and st.damage_taken > 0:
            out.append((e, f"We took {st.damage_taken:,.0f} in damage and she's at {hull:.0%}. Nothing I can't fix."))
    s = names.get("science")
    done = [d for d in deeds if isinstance(d, ObjectiveEnded) and d.outcome == "done" and d.ship_id == me.id]
    built = [d for d in deeds if isinstance(d, ProjectCompleted) and d.ship_id == me.id]
    if s and (done or built):
        what = []
        if done:
            what.append(f"{_n(len(done), 'objective')} achieved")
        if built:
            what.append(f"{_n(len(built), 'device')} built in the field")
        out.append((s, f"{_cap(' and '.join(what))}. Precision is its own reward."))
    if crew_lost and len(out) < 4:
        out.append(("The Doctor", f"{crew_lost} of our crew will not come home. I would like it noted."))
    return out


def _follows(escaped: list[str], broken: list[str], yielded: int, m: object, tour: bool, enemy: str) -> list[str]:
    out = []
    if escaped:
        out.append(f"{_cap(_list(escaped))} got away. {enemy[0].upper() + enemy[1:]} will hear what we can do.")
    if broken:
        out.append("Their captains will remember that we fired on a ship that had yielded: expect fewer to yield again.")
    elif yielded:
        out.append("Word will spread that we keep our terms. The next captain who is offered them may take them.")
    from ..sim.mission import Mission

    if isinstance(m, Mission) and tour and m.spec.flag:
        out.append("The mission's result changes what lies ahead on this tour." if m.state == "done" else
                   "The tour goes on without the mission done; Starfleet will note it.")
    elif isinstance(m, Mission) and m.kind == "intercept" and m.state == "failed":
        out.append("Her report is on its way. The next fight may find them ready for us.")
    return out


__all__ = ["Commendation", "StarfleetAssessment", "build"]
