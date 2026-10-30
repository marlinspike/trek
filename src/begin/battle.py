"""Battle setup: from a description of fleets to a running `World` with brains attached.

Used by Quick Battle (seeded random), Preset Battle (TOML presets) and
Custom Battle (the setup screen), and by headless tests and tournaments.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from .ai.captain import AICaptain
from .ai.computer import ShipComputer
from .ai.personality import Personality
from .content.schema import ContentDB
from .core.rng import Rng
from .crew.characters import load_officers
from .crew.officers import Crew, default_crew
from .paths import config_dir
from .sim.rules import DEFAULT_RULES, Rules
from .sim.ship import PDDoctrine
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
            c = AICaptain(old.id, old.side, Personality.roll(faction, prng), prng, phase=old.id % 2)
            self.captains[old.id] = c
            w.add_controller(c)
        if old is not None:
            old.delegated.clear()      # the officers come with the captain
        if self.crew is not None:
            self.crew.move_to(new.id)
        self.player_ship_id = new.id
        return None


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
            pers = Personality.roll(faction, prng, spec.personality)
            cap = AICaptain(ship.id, fleet.side, pers, prng, phase=ship.id % 2)
            captains[ship.id] = cap
            world.add_controller(cap)
    crew = None
    if player_ship is not None:
        crew = Crew(player_ship, setup.player_side, content, default_crew(load_officers(traits_file=config_dir() / "officers.toml")), world.rng.derive("crew"),
                    phase=1)
        world.add_controller(crew)
    return Battle(world, setup, player_ship, captains, computers, crew)


# The player's own ship always carries this name when it belongs to the faction (the player's wish).
PLAYER_FLAGSHIP_NAMES: dict[str, str] = {"federation": "Enterprise"}


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
    factions = [f for f in content.factions if f != player_faction]
    enemy = enemy_faction or rng.choice(factions)
    mine = [c for c in content.classes_of(player_faction, include_bases=False) if c.banks > 0 and c.era == "1.65"] or \
        [c for c in content.classes_of(player_faction, include_bases=False) if c.banks > 0]
    theirs = [c for c in content.classes_of(enemy, include_bases=False) if c.banks > 0]
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


__all__ = ["Battle", "BattleSetup", "FleetSpec", "MAX_OBJECTS", "PLAYER_FLAGSHIP_NAMES", "ShipSpec", "build_battle", "quick_battle"]
