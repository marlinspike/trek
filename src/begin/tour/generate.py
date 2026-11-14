"""Generated tours of duty [E]: a fresh patrol each time, built from the patrol situations.

`generate_tour(content, seed)` makes a `TourDef` like the hand-written ones in `content/data/tours.toml`, so
everything a tour does (the Ready Room, carried damage, reinforcements, the log) works the same. The same seed
always makes the same tour, and the seed is in the tour's id (`generated-<seed>`), so a save resumes it.

The shape of every generated tour:

- One adversary for the whole patrol (any race that fights random battles), so the tour tells one story.
- Four stops, each one of the patrol situations (battle.py `PATROL_SITUATIONS`): an ambush, a wolf pack, a
  second wave, a distress call, a convoy or a runner. At least one carries a mission.
- The threat rises stop by stop, sized against the squadron a captain can field (the flagship and the fleet
  budget), not against the flagship alone.
- A choice in the Ready Room before the third stop and before the last: refit and let them gather, or press on.
- The last stop is the boss: the adversary's heaviest ship under a named captain, her screen, and a second
  wave when the first is beaten.

The flagship is the faction's default (the Enterprise as a Dreadnought for the Federation): generated tours
never change it.
"""

from __future__ import annotations

import random
from pathlib import Path

from ..battle import PATROL_SITUATIONS, PLAYER_FLAGSHIP_CLASSES, _articles, _fill
from ..content.schema import ContentDB, ShipClass
from ..core.rng import Rng
from ..sim.mission import MissionDef
from .model import Choice, Stop, TourDef, WaveDef
from .state import TourState

PREFIX = "generated-"
STOPS = 4                          # before the boss
BUDGET = 240                       # fleet points for escorts
# each stop's threat as a share of the squadron's strength (flagship mass + budget): rising to the boss
THREAT = (0.50, 0.68, 0.85, 1.00)
BOSS_THREAT = 1.10                 # the boss and her screen
BOSS_WAVE = 0.60                   # the wave that comes when they are beaten
SITUATIONS = ("ambush", "wolfpack", "waves", "rescue", "convoy", "runner")
MISSIONS = ("rescue", "convoy", "runner")
OFFICERS = ("spock", "worf", "seven", "geordi")      # the officers who brief in the Ready Room

SECTORS = ("Kalandra Sector", "Typhon Expanse", "Beta Renner", "Hromi Cluster", "Mutara Reach", "Sector 21503",
           "Azure Drift", "Paulson Belt")
SYSTEMS = ("Arcadia", "Tessen", "Drema", "Ventax", "Kaleb", "Morikin", "Gamma Tauri", "Selcundi", "Zayra",
           "Barradas", "Nimbus", "Kurl", "Teneb", "Sarona", "Ogus", "Yadera", "Calder", "Penthara")
STARBASES = ("Starbase 74", "Starbase 133", "Starbase 211", "Deep Space 4")
# how the threat grows, in the officer's briefing: one line per stop after the first
RISING = ("", "They have heard of us now: this group came looking.",
          "They are sending better ships after us.", "Their commanders are taking us seriously: expect a hard fight.")


def is_generated(tour_id: str) -> bool:
    return tour_id.startswith(PREFIX)


def seed_of(tour_id: str) -> int | None:
    """The seed in a generated tour's id, or None for any other tour."""
    if not is_generated(tour_id):
        return None
    try:
        return int(tour_id[len(PREFIX):])
    except ValueError:
        return None


def fresh_seed() -> int:
    return random.randrange(1, 1_000_000)


def current(content: ContentDB, folder: Path, seed: int | None = None) -> TourDef:
    """The generated tour to offer: the one under way in `folder` (the latest), else a new one (`seed` or fresh)."""
    best: tuple[float, int] | None = None
    if folder.is_dir():
        for f in folder.glob(f"{PREFIX}*.json"):
            n = seed_of(f.stem)
            st = TourState.load(folder, f.stem) if n is not None else None
            if n is not None and st is not None and not st.over:
                when = f.stat().st_mtime
                if best is None or when > best[0]:
                    best = (when, n)
    if best is not None:
        return generate_tour(content, best[1])
    return generate_tour(content, seed if seed is not None else fresh_seed())


def generate_tour(content: ContentDB, seed: int, faction: str = "federation") -> TourDef:
    """A tour of four stops and a boss against one adversary, the threat rising all the way."""
    rng = Rng(seed).derive("tour")
    enemy = rng.choice([f for f, fd in content.factions.items() if f != faction and fd.random])
    theirs = [c for c in content.classes_of(enemy, include_bases=False) if c.banks > 0]
    flagship = PLAYER_FLAGSHIP_CLASSES.get(faction) or max(content.classes_of(faction, include_bases=False),
                                                           key=lambda c: c.mass).id
    strength = content.classes[flagship].mass + BUDGET
    them = content.factions[enemy].name
    sector = rng.choice(SECTORS)
    starbase = rng.choice(STARBASES)
    systems = list(SYSTEMS)
    rng.shuffle(systems)
    picks = _situations(rng)
    stops: list[Stop] = []
    for i, sid in enumerate(picks):
        stops.append(_stop(content, rng, i, sid, theirs, them, strength * THREAT[i] * rng.uniform(0.95, 1.08),
                           systems[i], starbase))
    stops.append(_boss(content, rng, theirs, them, enemy, strength, systems[STOPS], starbase))
    title = f"{sector} patrol"
    return TourDef(
        id=f"{PREFIX}{seed}", title=title, sector=sector, faction=faction, flagship=flagship, budget=BUDGET,
        description=_articles(f"A patrol made fresh for you (number {seed}). {them} ships have been raiding through "
                              f"{sector}, and they will not take kindly to a starship hunting them. Five stops, "
                              f"each harder than the last, and at the end the {them} commander who sent them."),
        stops=tuple(stops), reinforcement_calls=2, reinforcements=_reinforcements(content, faction),
        starbase=starbase, resupply=0.5, source="generated",
    )


def _situations(rng: Rng) -> list[str]:
    """Four different situations, at least one of them a mission."""
    while True:
        picks = list(SITUATIONS)
        rng.shuffle(picks)
        picks = picks[:STOPS]
        if any(p in MISSIONS for p in picks):
            return picks


def _reinforcements(content: ContentDB, faction: str) -> tuple[str, ...]:
    ships = sorted((c for c in content.classes_of(faction, include_bases=False) if c.banks > 0), key=lambda c: c.mass)
    return tuple(c.id for c in ships[-3:-1]) or tuple(c.id for c in ships[-1:])


def _chart_y(rng: Rng, i: int) -> float:
    """Low on the chart, clear of the tour list, zigzagging so the route never runs through a stop's name."""
    return rng.uniform(0.78, 0.86) if i % 2 == 0 else rng.uniform(0.55, 0.62)


def _brief(sid: str) -> tuple[str, str]:
    _, title, brief = next(x for x in PATROL_SITUATIONS if x[0] == sid)
    return title, brief


def _stop(content: ContentDB, rng: Rng, i: int, sid: str, theirs: list[ShipClass], them: str, mass: float,
          system: str, starbase: str) -> Stop:
    title, brief = _brief(sid)
    ward = rng.choice(("Aldren", "Tamar Kessel", "Ardent Star", "Corvallis", "Halvorsen", "Ibsen", "Meridian", "Sato"))
    enemies: list[str] = []
    waves: list[WaveDef] = []
    center = (0.0, 12000.0)
    mission: MissionDef | None = None
    people = 0
    runner = ""
    if sid == "ambush":
        group = _fill(rng, theirs, mass, rng.choice((4, 4, 5)))
        half = len(group) // 2
        enemies, center = group[:half], (-10500.0, 3500.0)
        waves.append(WaveDef(tuple(group[half:]), at=0.0, center=(10500.0, 3500.0)))
    elif sid == "wolfpack":
        enemies = _fill(rng, theirs, mass, rng.choice((5, 6, 7)), 0.8)
    elif sid == "waves":
        enemies = _fill(rng, theirs, mass * 0.55, 3)
        side = rng.choice((-1.0, 1.0))
        waves.append(WaveDef(tuple(_fill(rng, theirs, mass * 0.5, 2 + (i >= 2))), at=160.0, after_clear=10.0,
                             center=(side * 12000.0, 4000.0),
                             message=f"Captain, a second {them} group is dropping out of warp!"))
    elif sid == "rescue":
        people = rng.choice((60, 80, 120, 150))
        enemies = _fill(rng, theirs, mass, rng.choice((3, 4)))
        center = (rng.uniform(-4000, 4000), 14000.0)
        mission = MissionDef("rescue", title=f"Rescue the crew of the {ward}", ward="federation.de", ward_name=ward,
                             at=(rng.uniform(-3000, 3000), -3000.0), people=people,
                             deadline=rng.choice((150.0, 180.0, 210.0)), hunters=1, calls=1, resupply=0.5)
    elif sid == "convoy":
        side = rng.choice((-1.0, 1.0))
        enemies = _fill(rng, theirs, mass, rng.choice((3, 4)), 0.85)
        center = (-side * 4000.0, 15000.0)
        mission = MissionDef("escort", title=f"Protect the {ward}", ward="federation.tn", ward_name=ward,
                             at=(side * 2000.0, -8000.0), to=(side * 26000.0, -8000.0), hunters=2, resupply=0.5)
    else:   # runner: the lightest makes for the edge with news of us, the rest stand in the way
        group = _fill(rng, theirs, mass, rng.choice((3, 4)))
        light = min(range(len(group)), key=lambda k: content.classes[group[k]].mass)
        group.insert(0, group.pop(light))
        enemies = group
        side = rng.choice((-1.0, 1.0))
        mission = MissionDef("intercept", runner=0, heading=(90.0 * side + rng.uniform(-30.0, 10.0) * side) % 360.0)
        runner = content.classes[group[0]].name
    text = brief.format(enemy=them, ward=ward, people=people, runner=runner)
    if RISING[i]:
        text += " " + RISING[i]
    choices: tuple[Choice, ...] = ()
    add: dict[str, tuple[str, ...]] = {}
    if i == 2:          # halfway: put in for repairs, and they gather
        extra = _fill(rng, theirs, mass * 0.25, 1)
        choices = (Choice("Press on", "Field repairs on the way. They get no time to gather.", transit=150.0,
                          flags=("pressed",)),
                   Choice(f"Refit at {starbase}", "Hull, systems, crews and magazines made good, but the "
                          f"{them} have time to send one more ship.", refit=True, transit=300.0, flags=("refit-2",)))
        add = {"refit-2": tuple(extra)}
    return Stop(id=f"stop-{i + 1}", title=title, system=system,
                chart=(0.1 + 0.18 * i, _chart_y(rng, i)),
                briefing=_articles(text), enemies=tuple(enemies),
                officer=OFFICERS[i % len(OFFICERS)], transit=float(rng.choice((120, 140, 160))),
                eta=float(rng.choice((120, 150, 180))), enemy_center=center, waves=tuple(waves), choices=choices,
                add=add, seed=rng.irange(1, 10**6), mission=mission)


def _boss(content: ContentDB, rng: Rng, theirs: list[ShipClass], them: str, enemy: str, strength: float,
          system: str, starbase: str) -> Stop:
    """The last stop: their heaviest ship under a named commander, her screen, and a wave behind them."""
    heavy = max(theirs, key=lambda c: c.mass)
    names = list(content.factions[enemy].captain_names)
    commander = rng.choice(names) if names else "their commander"
    screen = _fill(rng, theirs, max(heavy.mass * 0.6, strength * BOSS_THREAT - heavy.mass), rng.choice((2, 3)), 0.8)
    wave = _fill(rng, theirs, strength * BOSS_WAVE, rng.choice((2, 3)))
    extra = _fill(rng, theirs, strength * 0.15, 1)
    brief = (f"This is where the raids were planned. {commander}, whose ships we have been fighting all patrol, is "
             f"waiting at {system} aboard a {heavy.name.lower()}, with a screen around the flagship and more ships in "
             f"reserve. Beat the screen, take the flagship or destroy her, and the raids end here.")
    return Stop(
        id="boss", title=f"{commander}'s {heavy.name}", system=system, chart=(0.9, _chart_y(rng, STOPS)),
        briefing=_articles(brief), enemies=(heavy.id, *screen), officer="worf", transit=170.0, eta=90.0,
        enemy_center=(0.0, 12500.0),
        waves=(WaveDef(tuple(wave), after_clear=20.0, center=(rng.choice((-1.0, 1.0)) * 13000.0, 6000.0),
                       message=f"Captain, {commander}'s reserve is dropping out of warp!"),),
        choices=(Choice("Strike before they gather", f"A hard run to {system}. Less time for field repairs, but one "
                        "ship of her screen won't be there.", transit=90.0, flags=("struck-first",)),
                 Choice("Come in repaired", "A slower approach: more field repairs, but her reserve has time to grow.",
                        transit=260.0, flags=("came-slow",))),
        add={"came-slow": tuple(extra)}, drop={"struck-first": tuple(screen[-1:])},
        win_flag="boss-beaten", seed=rng.irange(1, 10**6), mission=None, commander=commander,
    )


__all__ = ["BOSS_THREAT", "PREFIX", "THREAT", "current", "fresh_seed", "generate_tour", "is_generated", "seed_of"]
