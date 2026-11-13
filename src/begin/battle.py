"""Battle setup: from a description of fleets to a running `World` with brains attached.

Used by Quick Battle (seeded random), Preset Battle (TOML presets) and
Custom Battle (the setup screen), and by headless tests and tournaments.
"""

from __future__ import annotations

import dataclasses
import math
from dataclasses import dataclass, field

from .ai.captain import AICaptain
from .ai.collective import BorgCaptain
from .ai.computer import ShipComputer
from .ai.personality import Personality
from .content.schema import ContentDB, ShipClass
from .core.rng import Rng
from .crew.characters import load_officers
from .crew.officers import Crew, default_crew
from .paths import config_dir
from .sim.arrivals import Arrival
from .sim.events import Event
from .sim.mission import MissionDef, install as install_mission
from .sim.rules import DEFAULT_RULES, Rules
from .sim.ship import PDDoctrine, Ship
from .sim.world import World

MAX_OBJECTS = 60  # Begin's ship limit


@dataclass
class ShipSpec:
    class_id: str
    name: str | None = None
    x: float | None = None
    y: float | None = None
    course: float | None = None
    personality: dict[str, float] | None = None


@dataclass
class FleetSpec:
    side: int
    ships: list[ShipSpec] = field(default_factory=list)
    player: bool = False             # the player commands this side's flagship (ships[0])
    center: tuple[float, float] | None = None


@dataclass
class BattleSetup:
    fleets: list[FleetSpec]
    seed: int = 1
    title: str = "Battle"
    description: str = ""
    rules: Rules = DEFAULT_RULES
    arrivals: list[Arrival] = field(default_factory=list)   # waves and reinforcements that join later [E]
    personalities: dict[int, dict[str, float]] = field(default_factory=dict)  # side -> captains' leanings (a tour's memory) [E]
    mission: MissionDef | None = None   # a goal beyond holding the field: rescue, escort or intercept (sim/mission.py) [E]

    @property
    def player_side(self) -> int:
        for f in self.fleets:
            if f.player:
                return f.side
        return -1


@dataclass
class Battle:
    world: World
    setup: BattleSetup
    player_ship_id: int | None
    captains: dict[int, AICaptain]
    computers: dict[int, ShipComputer]
    crew: Crew | None = None          # the player's bridge officers (delegated stations)
    deeds: list[Event] = field(default_factory=list)   # objectives and projects finished (the UI's record, for a tour's log)

    def adopt(self, ship: Ship) -> None:
        """A captured ship joins her new side: a fresh ship computer, and a captain from the prize crew.

        On the player's side she is one of your ships: `tell` her what to do, or `beam <her>` to take command.
        """
        w = self.world
        self.captains.pop(ship.id, None)
        self.computers.pop(ship.id, None)
        comp = ShipComputer(ship.id, ship.side, w.rng.derive(f"computer:{ship.id}:{w.tick}"), phase=ship.id % 2)
        self.computers[ship.id] = comp
        w.add_controller(comp)
        if ship.id != self.player_ship_id:
            cap = _crew_in_command(w, ship.id)
            self.captains[ship.id] = cap
            w.add_controller(cap)

    def commission(self, ship: Ship) -> None:
        """A ship that warped in mid-battle gets a computer and a captain of her own navy [E]."""
        w = self.world
        faction = w.content.factions[ship.faction]
        ship.pd_doctrine = PDDoctrine(faction.doctrine.point_defense)
        comp = ShipComputer(ship.id, ship.side, w.rng.derive(f"computer:{ship.id}"), phase=ship.id % 2)
        self.computers[ship.id] = comp
        w.add_controller(comp)
        prng = w.rng.derive(f"captain:{ship.id}")
        cap = _captain_class(faction)(ship.id, ship.side,
                                      Personality.roll(faction, prng, self.setup.personalities.get(ship.side)),
                                      prng, phase=ship.id % 2)
        self.captains[ship.id] = cap
        w.add_controller(cap)

    def transfer_command(self, new_id: int) -> str | None:
        """Begin's `beam <ally>`: the player moves to a functional ally within transporter range.

        The ally's captain steps aside and a captain takes over the ship the player left.
        Returns a reason when the transfer is not possible.
        """
        w = self.world
        old = w.ships.get(self.player_ship_id) if self.player_ship_id is not None else None
        new = w.ships.get(new_id)
        if new is None or not new.alive or new.crew <= 0:
            return "That ship cannot take you aboard."
        if old is not None and new.side != old.side:
            return f"{new.name} is not one of ours."
        if old is not None and new.id == old.id:
            return "You are already aboard."
        if old is not None and old.exists:
            d = math.hypot(new.x - old.x, new.y - old.y)
            if d > w.rules.beam_range:
                return f"{new.name} is out of transporter range ({d:,.0f} > {w.rules.beam_range:,.0f})."
            if not any(not t.destroyed for t in old.transporters) and not any(not t.destroyed for t in new.transporters):
                return "No working transporters."
        cap = self.captains.pop(new.id, None)
        if cap is not None and cap in w.controllers:
            w.controllers.remove(cap)
        w.ally_orders.pop(new.id, None)
        if old is not None and old.alive and old.crew > 0:
            faction = w.content.factions[old.faction]
            prng = w.rng.derive(f"captain:{old.id}:{w.tick}")
            c = _captain_class(faction)(old.id, old.side, Personality.roll(faction, prng), prng, phase=old.id % 2)
            self.captains[old.id] = c
            w.add_controller(c)
        if old is not None:
            old.delegated.clear()      # the officers come with the captain
        if self.crew is not None:
            self.crew.move_to(new.id)
        self.player_ship_id = new.id
        return None


def _crew_in_command(w: World, ship_id: int) -> AICaptain:
    s = w.ships[ship_id]
    prng = w.rng.derive(f"captain:{ship_id}:{w.tick}")
    # the prize crew fights the way their own navy does
    faction = next((o.faction for o in w.ships.values() if o.side == s.side and o.id != ship_id), s.faction)
    fd = w.content.factions[faction]
    return _captain_class(fd)(ship_id, s.side, Personality.roll(fd, prng), prng, phase=ship_id % 2)


def _captain_class(faction: object) -> type[AICaptain]:
    """The hive sends its own kind of captain [E]."""
    return BorgCaptain if getattr(faction, "collective", None) is not None else AICaptain


def build_battle(content: ContentDB, setup: BattleSetup) -> Battle:
    total = sum(len(f.ships) for f in setup.fleets)
    if total > MAX_OBJECTS:
        raise ValueError(f"Too many ships ({total}); Begin's limit is {MAX_OBJECTS}.")
    world = World(content, rules=setup.rules, seed=setup.seed, player_side=setup.player_side)
    flagship_name = _player_flagship_name(content, setup)
    if flagship_name:
        world.reserved_names.add(flagship_name)  # no other ship draws the flagship's name
    rng = Rng(setup.seed).derive("setup")
    n = len(setup.fleets)
    player_ship: int | None = None
    captains: dict[int, AICaptain] = {}
    computers: dict[int, ShipComputer] = {}
    for fi, fleet in enumerate(setup.fleets):
        if fleet.center is not None:
            cx, cy = fleet.center
        else:
            ang = math.radians(180.0 + 360.0 * fi / max(1, n))
            r = 14000.0 if n > 1 else 0.0
            cx, cy = math.sin(ang) * r, math.cos(ang) * r
        face = math.degrees(math.atan2(-cx, -cy)) % 360.0 if (cx or cy) else 0.0
        for si, spec in enumerate(fleet.ships):
            if spec.x is not None and spec.y is not None:
                x, y = spec.x, spec.y
            else:
                # line abreast, perpendicular to the facing
                off = (si - (len(fleet.ships) - 1) / 2.0) * 1800.0
                pr = math.radians(face + 90.0)
                jitter = rng.uniform(-300, 300)
                x, y = cx + math.sin(pr) * off + jitter, cy + math.cos(pr) * off + rng.uniform(-300, 300)
            course = spec.course if spec.course is not None else face
            cls = content.classes[spec.class_id]
            warp = 0.0 if cls.is_base else min(cls.cruise_warp, 3.0)
            name = spec.name or (flagship_name if fleet.player and si == 0 else None)
            ship = world.add_ship(spec.class_id, fleet.side, x, y, course=course, warp=warp, name=name)
            faction = content.factions[cls.faction]
            ship.pd_doctrine = PDDoctrine(faction.doctrine.point_defense)
            comp = ShipComputer(ship.id, fleet.side, world.rng.derive(f"computer:{ship.id}"), phase=ship.id % 2)
            computers[ship.id] = comp
            world.add_controller(comp)
            if fleet.player and si == 0:
                player_ship = ship.id
                continue
            prng = world.rng.derive(f"captain:{ship.id}")
            leanings = {**setup.personalities.get(fleet.side, {}), **(spec.personality or {})}
            pers = Personality.roll(faction, prng, leanings or None)
            cap = _captain_class(faction)(ship.id, fleet.side, pers, prng, phase=ship.id % 2)
            captains[ship.id] = cap
            world.add_controller(cap)
    if setup.mission is not None and setup.player_side >= 0:
        enemies = [s.id for s in world.ships.values() if s.side != setup.player_side]
        m = install_mission(world, setup.mission, setup.player_side, enemies)
        if m.ward_id is not None:
            ward = world.ships[m.ward_id]
            faction = content.factions[ward.cls.faction]
            ward.pd_doctrine = PDDoctrine(faction.doctrine.point_defense)
            comp = ShipComputer(ward.id, ward.side, world.rng.derive(f"computer:{ward.id}"), phase=ward.id % 2)
            computers[ward.id] = comp
            world.add_controller(comp)
            prng = world.rng.derive(f"captain:{ward.id}")
            cap = _captain_class(faction)(ward.id, ward.side, Personality.roll(faction, prng), prng, phase=ward.id % 2)
            captains[ward.id] = cap
            world.add_controller(cap)
    crew = None
    if player_ship is not None:
        roster = load_officers(traits_file=config_dir() / "officers.toml")
        crew = Crew(player_ship, setup.player_side, content, default_crew(roster), world.rng.derive("crew"), roster=roster,
                    phase=1)
        world.add_controller(crew)
    battle = Battle(world, setup, player_ship, captains, computers, crew)
    world.on_capture = battle.adopt
    world.on_arrival = battle.commission
    world.arrivals = [dataclasses.replace(a, ship_ids=[]) for a in setup.arrivals]
    return battle


# The player's own ship always carries this name when it belongs to the faction (the player's wish).
PLAYER_FLAGSHIP_NAMES: dict[str, str] = {"federation": "Enterprise"}
# ... and, unless the player configures otherwise, is this class: the Enterprise is a Dreadnought (the player's rule).
PLAYER_FLAGSHIP_CLASSES: dict[str, str] = {"federation": "federation.dn"}


def _player_flagship_name(content: ContentDB, setup: BattleSetup) -> str | None:
    for f in setup.fleets:
        if f.player and f.ships and not f.ships[0].name:
            return PLAYER_FLAGSHIP_NAMES.get(content.classes[f.ships[0].class_id].faction)
    return None


def quick_battle(content: ContentDB, seed: int, player_faction: str = "federation",
                 enemy_faction: str | None = None, size: int = 1, enemies: int = 2) -> BattleSetup:
    """A seeded random engagement: the player's ship (plus wingmen) against `enemies` ships per player ship.

    The enemy group is sized to roughly the player's mass, split evenly across its ships.
    """
    rng = Rng(seed).derive("quick")
    factions = [f for f, fd in content.factions.items() if f != player_faction and fd.random]
    enemy = enemy_faction or rng.choice(factions)
    mine = [c for c in content.classes_of(player_faction, include_bases=False) if c.banks > 0 and c.era == "1.65"] or \
        [c for c in content.classes_of(player_faction, include_bases=False) if c.banks > 0]
    theirs = [c for c in content.classes_of(enemy, include_bases=False) if c.banks > 0]
    default = PLAYER_FLAGSHIP_CLASSES.get(player_faction)
    if default in content.classes:
        flagship = content.classes[default]
    else:
        flagship = max(mine, key=lambda c: c.mass) if size <= 1 else rng.choice(mine)
    player = FleetSpec(0, [ShipSpec(flagship.id)], player=True)
    budget = flagship.mass * size * rng.uniform(0.85, 1.25)
    for _ in range(size - 1):
        player.ships.append(ShipSpec(rng.choice(mine).id))
    enemy_ships: list[ShipSpec] = []
    spent = 0.0
    count = max(1, enemies * size)
    for slot in range(count):
        share = (budget - spent) / (count - slot)
        options = [c for c in theirs if 0.65 * share <= c.mass <= 1.35 * share] or \
            [min(theirs, key=lambda c: abs(c.mass - share))]
        c = rng.choice(options)
        enemy_ships.append(ShipSpec(c.id))
        spent += c.mass
    return BattleSetup(
        fleets=[player, FleetSpec(1, enemy_ships)], seed=seed,
        title=f"Quick battle #{seed}",
        description=f"{content.factions[player_faction].name} vs {content.factions[enemy].name}",
    )


def _fill(rng: Rng, classes: list[ShipClass], budget: float, count: int, lean: float = 1.0) -> list[str]:
    """`count` ships of these classes adding up to about `budget` mass; `lean` below 1 favours the lighter."""
    out: list[str] = []
    spent = 0.0
    for slot in range(count):
        share = max(1.0, (budget - spent) / (count - slot)) * lean
        options = [c for c in classes if 0.65 * share <= c.mass <= 1.35 * share] or \
            [min(classes, key=lambda c: abs(c.mass - share))]
        c = rng.choice(options)
        out.append(c.id)
        spent += c.mass
    return out


# A patrol's situations [E]: (id, title, briefing). The briefing is what the captain reads at battle stations.
PATROL_SITUATIONS = (
    ("ambush", "Ambush", "Two {enemy} groups were waiting either side of the patrol lane. Turn to face one and the other "
                         "is on your stern."),
    ("wolfpack", "Wolf pack", "A pack of light {enemy} ships, fast and many. Thin them out before they swarm you."),
    ("waves", "Second wave", "A {enemy} patrol, and long-range sensors show more coming. Finish the first group "
                             "quickly; the second will not wait."),
    ("escort", "Escort", "You have wingmen this time, and the {enemy} have brought more to match. Use them: 'tell "
                         "<ship> attack <target>'."),
    ("flagship", "Flagship", "A {enemy} heavy and her escorts. The heavy is the prize; the escorts will make you pay for "
                             "going straight at her."),
    # [E] missions (sim/mission.py): a goal beyond holding the field
    ("rescue", "Distress call", "The {ward} is crippled and drifting with {people} aboard, and a {enemy} group has found "
                                "her first. Get her people off: within transporter range, with the shield facing her "
                                "lowered. Her reactor will not last long."),
    ("convoy", "Convoy", "The freighter {ward} is making for the shipping lane and a {enemy} group means to take her. Get "
                         "her through: she sails at her own speed, and she can't fight."),
    ("runner", "Runner", "A {enemy} group, and one of them, the {runner}, is making for the edge of the sector with "
                         "what she has seen of us. She must not get away."),
)
WARD_NAMES = ("Aldren", "Tamar Kessel", "Ardent Star", "Corvallis", "Halvorsen", "Ibsen", "Meridian", "Sato")


def _articles(text: str) -> str:
    """'a Orion' -> 'an Orion'."""
    import re

    return re.sub(r"\b([Aa]) (?=[AEIOU])", lambda m: m.group(1) + "n ", text)


def patrol_battle(content: ContentDB, seed: int, player_faction: str = "federation",
                  situation: str | None = None) -> BattleSetup:
    """A seeded random patrol [E]: one of several situations (an ambush from two sides, a wolf pack, a second
    wave, an escort mission, a flagship and her screen), against a random enemy, so that no two patrols play
    alike. The player's flagship is the usual one (the Enterprise as a Dreadnought for the Federation)."""
    rng = Rng(seed).derive("patrol")
    sid, title, brief = next((x for x in PATROL_SITUATIONS if x[0] == situation), None) or rng.choice(PATROL_SITUATIONS)
    enemy = rng.choice([f for f, fd in content.factions.items() if f != player_faction and fd.random])
    mine = [c for c in content.classes_of(player_faction, include_bases=False) if c.banks > 0]
    theirs = [c for c in content.classes_of(enemy, include_bases=False) if c.banks > 0]
    default = PLAYER_FLAGSHIP_CLASSES.get(player_faction)
    flagship = content.classes[default] if default in content.classes else max(mine, key=lambda c: c.mass)
    player = FleetSpec(0, [ShipSpec(flagship.id)], player=True, center=(0.0, -11000.0))
    mass = flagship.mass * rng.uniform(0.95, 1.15)
    fleets = [player]
    arrivals: list[Arrival] = []
    if sid == "ambush":
        group = _fill(rng, theirs, mass * 1.3, rng.choice((4, 4, 5)))
        half = len(group) // 2
        player.center = (0.0, -2000.0)
        fleets += [FleetSpec(1, [ShipSpec(c) for c in group[:half]], center=(-10500.0, 3500.0)),
                   FleetSpec(1, [ShipSpec(c) for c in group[half:]], center=(10500.0, 3500.0))]
    elif sid == "wolfpack":
        fleets.append(FleetSpec(1, [ShipSpec(c) for c in _fill(rng, theirs, mass * 1.35, rng.choice((6, 7, 8)), 0.8)],
                                center=(0.0, 12000.0)))
    elif sid == "waves":
        fleets.append(FleetSpec(1, [ShipSpec(c) for c in _fill(rng, theirs, mass * 0.8, 3)], center=(0.0, 11000.0)))
        x = rng.choice((-1.0, 1.0)) * 12000.0
        arrivals.append(Arrival(side=1, ships=tuple(_fill(rng, theirs, mass * 0.75, 3)), at=160.0, after_clear=10.0,
                                at_x=x, at_y=4000.0, heading=math.degrees(math.atan2(-x, -4000.0)) % 360.0,
                                message=f"Captain, a second {content.factions[enemy].name} group is dropping out of warp!"))
    elif sid == "escort":
        light = sorted(mine, key=lambda c: c.mass)[: max(1, len(mine) // 2)]
        wings = [rng.choice(light).id for _ in range(rng.choice((1, 2)))]
        player.ships += [ShipSpec(c) for c in wings]
        extra = sum(content.classes[c].mass for c in wings)
        fleets.append(FleetSpec(1, [ShipSpec(c) for c in _fill(rng, theirs, (mass + extra) * 1.25, 3 + len(wings))],
                                center=(0.0, 12000.0)))
    elif sid == "flagship":
        heavy = max(theirs, key=lambda c: c.mass)
        screen = _fill(rng, theirs, max(heavy.mass * 0.8, mass * 1.9 - heavy.mass), rng.choice((3, 4)), 0.7)
        fleets.append(FleetSpec(1, [ShipSpec(heavy.id)] + [ShipSpec(c) for c in screen], center=(0.0, 12500.0)))
    ward = rng.choice(WARD_NAMES)
    people = 0
    runner = ""
    mission: MissionDef | None = None
    if sid == "rescue":
        people = rng.choice((60, 80, 120, 150))
        group = _fill(rng, theirs, mass * 1.0, rng.choice((3, 4)))
        fleets.append(FleetSpec(1, [ShipSpec(c) for c in group], center=(rng.uniform(-4000, 4000), 14000.0)))
        mission = MissionDef("rescue", title=f"Rescue the crew of the {ward}", ward="federation.de", ward_name=ward,
                             at=(rng.uniform(-3000, 3000), -3000.0), people=people,
                             deadline=rng.choice((150.0, 180.0, 210.0)), hunters=1)
    elif sid == "convoy":
        group = _fill(rng, theirs, mass * 1.05, rng.choice((3, 4)), 0.85)
        side = rng.choice((-1.0, 1.0))
        fleets.append(FleetSpec(1, [ShipSpec(c) for c in group], center=(-side * 4000.0, 15000.0)))
        mission = MissionDef("escort", title=f"Protect the {ward}", ward="federation.tn", ward_name=ward,
                             at=(side * 2000.0, -8000.0), to=(side * 26000.0, -8000.0), hunters=2)
    elif sid == "runner":
        group = _fill(rng, theirs, mass * 1.1, rng.choice((3, 4)))
        lightest = min(range(len(group)), key=lambda i: content.classes[group[i]].mass)
        courier = group.pop(lightest)              # the runner is the one sent with the news: the lightest
        side = rng.choice((-1.0, 1.0))
        # she is out on the flank, already turning for home; the rest stand between us and her
        fleets.append(FleetSpec(1, [ShipSpec(courier)], center=(side * 9000.0, 3000.0)))
        fleets.append(FleetSpec(1, [ShipSpec(c) for c in group], center=(0.0, 12000.0)))
        mission = MissionDef("intercept", runner=0, heading=(90.0 * side + rng.uniform(-30.0, 10.0) * side) % 360.0)
        runner = content.classes[courier].name
    return BattleSetup(fleets=fleets, seed=seed, arrivals=arrivals,
                       title=f"Patrol #{seed}: {title}",
                       description=_articles(brief.format(enemy=content.factions[enemy].name, ward=ward,
                                                          people=people, runner=runner)),
                       mission=mission)


__all__ = ["Battle", "BattleSetup", "FleetSpec", "MAX_OBJECTS", "PATROL_SITUATIONS", "PLAYER_FLAGSHIP_CLASSES",
           "PLAYER_FLAGSHIP_NAMES", "ShipSpec", "build_battle", "patrol_battle", "quick_battle"]
