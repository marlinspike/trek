"""Build ship state from content definitions.

Internal subsystems are placed on the hull from its anchors so the
location-aware damage model and the damage-assessment view agree on where
everything is. Weapon mounts come straight from the hull's mount list.
"""

from __future__ import annotations

import math

from ..content.schema import ContentDB, ShipClass
from .rules import Rules
from .ship import (
    Battery, Drive, Kind, Launcher, PhaserBank, Reactor, Shield, Ship, Subsystem, Tube,
)

# Begin's shield numbering: 1 fore, 2 fore-starboard, 3 fore-port, 4 aft-starboard, 5 aft-port, 6 aft.
SHIELD_FACINGS: tuple[float, ...] = (0.0, 60.0, 300.0, 120.0, 240.0, 180.0)


def _ring(center: tuple[float, float], n: int, radius: float, phase: float = 0.0) -> list[tuple[float, float]]:
    if n <= 1:
        return [center] * n
    out = []
    for i in range(n):
        a = math.radians(phase + 360.0 * i / n)
        out.append((center[0] + math.sin(a) * radius, center[1] + math.cos(a) * radius))
    return out


def _lerp(a: tuple[float, float], b: tuple[float, float], t: float) -> tuple[float, float]:
    return a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t


def _sid(kind: Kind, index: int, singleton: bool = False) -> str:
    return kind.value if singleton else f"{kind.value}{index + 1}"


def build_ship(
    content: ContentDB,
    rules: Rules,
    ship_id: int,
    class_id: str,
    side: int,
    name: str,
    captain: str = "",
    x: float = 0.0,
    y: float = 0.0,
    course: float = 0.0,
    warp: float = 0.0,
) -> Ship:
    cls: ShipClass = content.classes[class_id]
    hull = cls.hull
    faction = content.factions[cls.faction]
    core, aft, nose, bridge = hull.core, hull.aft, hull.nose, hull.bridge

    ship = Ship(
        id=ship_id, name=name, cls=cls, side=side, faction=cls.faction, captain=captain,
        x=x, y=y, course=course % 360.0, desired_course=course % 360.0, warp=warp, desired_warp=warp,
        crew=cls.crew, armour=cls.armour,
        structure=cls.mass * rules.hull_per_mass + rules.hull_base,
        structure_max=cls.mass * rules.hull_per_mass + rules.hull_base,
        torps_remaining=cls.torps_carried, probes_remaining=cls.probes_carried,
        base_sophistication=faction.computer_sophistication,
    )

    ship.reactors = [Reactor(_sid(Kind.REACTOR, i), Kind.REACTOR, i, p)
                     for i, p in enumerate(_ring(core, cls.reactors, 5.0))]
    ship.batteries = [Battery(_sid(Kind.BATTERY, i), Kind.BATTERY, i, p, charge=cls.battery_capacity)
                      for i, p in enumerate(_ring(_lerp(core, aft, 0.4), cls.batteries, 7.0, 45.0))]
    drive_spots = list(hull.nacelles) or [aft]
    ship.drives = [Drive(_sid(Kind.DRIVE, i), Kind.DRIVE, i, drive_spots[i % len(drive_spots)], temp=rules.temp_floor)
                   for i in range(cls.drives)]
    ship.shields = []
    for i in range(cls.shields):
        f = SHIELD_FACINGS[i % 6]
        a = math.radians(f)
        pos = (core[0] + math.sin(a) * 30.0, core[1] + math.cos(a) * 38.0)
        ship.shields.append(Shield(_sid(Kind.SHIELD, i), Kind.SHIELD, i, pos, facing=f))
    ship.banks = [PhaserBank(_sid(Kind.PHASER, i), Kind.PHASER, i, m.pos, mount=m, mark=m.arc_center)
                  for i, m in enumerate(hull.banks)]
    ship.tubes = [Tube(_sid(Kind.TUBE, i), Kind.TUBE, i, m.pos, mount=m, mark=m.arc_center,
                       load_ordnance=cls.torpedo)
                  for i, m in enumerate(hull.tubes)]
    ship.launchers = [Launcher(_sid(Kind.LAUNCHER, i), Kind.LAUNCHER, i, m.pos, mount=m,
                               load_ordnance=cls.probe)
                      for i, m in enumerate(hull.launchers)]
    ship.transporters = [Subsystem(_sid(Kind.TRANSPORTER, i), Kind.TRANSPORTER, i, p)
                         for i, p in enumerate(_ring(_lerp(core, bridge, 0.5), cls.transporters, 6.0, 90.0))]
    if cls.has_impulse:
        ship.impulse = Subsystem(_sid(Kind.IMPULSE, 0, True), Kind.IMPULSE, 0, aft)
    ship.sensors = Subsystem(_sid(Kind.SENSORS, 0, True), Kind.SENSORS, 0, nose)
    ship.computer = Subsystem(_sid(Kind.COMPUTER, 0, True), Kind.COMPUTER, 0, _lerp(bridge, core, 0.5))
    if cls.has_tractor:
        ship.tractor = Subsystem(_sid(Kind.TRACTOR, 0, True), Kind.TRACTOR, 0, _lerp(aft, core, 0.2))
    if cls.can_cloak:
        ship.cloak = Subsystem(_sid(Kind.CLOAK, 0, True), Kind.CLOAK, 0, _lerp(core, aft, 0.25))

    # a fresh ship starts with charged weapons only if the scenario asks; Begin starts empty
    return ship


__all__ = ["SHIELD_FACINGS", "build_ship"]
