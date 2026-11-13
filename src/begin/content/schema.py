"""Typed content definitions loaded from TOML.

These are immutable descriptions of the universe (ship classes, ordnance,
factions). The simulation instantiates mutable state from them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

ShapeRole = Literal["hull", "nacelle", "detail"]


@dataclass(frozen=True, slots=True)
class Shape:
    kind: Literal["poly", "ellipse"]
    role: ShapeRole
    points: tuple[tuple[float, float], ...] = ()
    center: tuple[float, float] = (0.0, 0.0)
    radii: tuple[float, float] = (0.0, 0.0)


@dataclass(frozen=True, slots=True)
class MountDef:
    pos: tuple[float, float]
    arc_center: float
    arc_width: float


@dataclass(frozen=True, slots=True)
class HullDef:
    class_id: str
    length: float
    shapes: tuple[Shape, ...]
    bridge: tuple[float, float]
    core: tuple[float, float]
    nose: tuple[float, float]
    aft: tuple[float, float]
    nacelles: tuple[tuple[float, float], ...]
    banks: tuple[MountDef, ...]
    tubes: tuple[MountDef, ...]
    launchers: tuple[MountDef, ...]

    @property
    def scale(self) -> float:
        """World units per design unit."""
        return self.length / 100.0


@dataclass(frozen=True, slots=True)
class RepairRates:
    reactor: float
    battery: float
    phaser: float
    tube: float
    launcher: float
    drive: float
    shield: float
    transporter: float
    sensors: float
    cloak: float
    impulse: float
    tractor: float

    def rate(self, kind: str) -> float:
        return float(getattr(self, kind, 1.0))


@dataclass(frozen=True, slots=True)
class ShipClass:
    id: str
    name: str
    abbrev: str
    faction: str
    era: str
    torpedo: str
    probe: str
    crew: int
    mass: float
    max_warp: float
    w1accel: float
    decel: float
    warp_power_use: float
    w1turn: float
    destruct: float
    destruct_energy: float
    scanner_reflect: float
    scanner_range: float
    reactors: int
    reactor_output: float
    batteries: int
    battery_capacity: float
    banks: int
    banks_rate: float
    banks_charge: float
    banks_range: float
    tubes: int
    launchers: int
    drives: int
    warp_power: float
    warp_efficiency: float
    shields: int
    shield_strength: float
    shield_absorption: float
    shield_recharge: float
    shield_energy: float
    transporters: int
    beam_cap: int
    beam_range: float
    can_cloak: bool
    cloak_energy: float
    armour: float
    mass_capacity: float
    docked_repair_ratio: float
    life_support: int
    has_impulse: bool
    has_tractor: bool
    tractor_strength: float
    tractor_energy: float
    torps_carried: int
    probes_carried: int
    ship_names: tuple[str, ...]
    repair: RepairRates
    hull: HullDef
    sensor_scale: float = 1.0   # [E] the faction's sensor technology: × scanner_range
    craft: bool = False         # [E] a small craft (a shuttle): no combatant, so she never holds the field alone
    cloak_fire: bool = False    # [E] a cloak made to fire through (the Enterprise's refit): no lingering reveal
    story: bool = False         # [E] made for one story (the Enterprise's cloak refit): never offered in setups

    @property
    def rated_sensor_range(self) -> float:
        return self.scanner_range * self.sensor_scale

    @property
    def is_base(self) -> bool:
        return self.max_warp <= 0.0

    @property
    def cruise_warp(self) -> float:
        """Warp at which an undamaged drive holds a steady temperature (Begin's 'cruise')."""
        return self.max_warp * self.warp_efficiency

    @property
    def display_name(self) -> str:
        return self.name


@dataclass(frozen=True, slots=True)
class TorpedoDef:
    id: str
    name: str
    velocity: float
    damage: float
    arm_time: float
    max_time_fuse: float
    max_prox: float
    homing: bool
    speed_variance: float
    warhead_type: int  # 0 antimatter, 1 shield-bore, 2 plasma (decays)
    charge_time: float
    load_energy: float
    # [E] special designs (custom_ordnance.toml): a burst that lights up cloaked ships instead of damaging
    reveal_radius: float = 0.0
    reveal_cycles: float = 0.0
    special: bool = False         # never offered as a normal load; made by a crew project
    blast_scale: float = 1.0      # [E] × the blast radius Begin's formula gives (the warhead is unchanged)

    @property
    def is_plasma(self) -> bool:
        return self.warhead_type == 2

    @property
    def is_shield_bore(self) -> bool:
        return self.warhead_type == 1

    @property
    def short(self) -> str:
        return self.id.upper()


@dataclass(frozen=True, slots=True)
class ProbeDef:
    id: str
    name: str
    velocity: float
    damage: float
    arm_time: float
    max_time_fuse: float
    max_prox: float
    homing: bool
    scan_range: float

    @property
    def is_data_probe(self) -> bool:
        return self.scan_range > 0.0


@dataclass(frozen=True, slots=True)
class Dogma:
    aggression: float
    bravery: float
    loyalty: float
    fanaticism: float
    boarding: float
    deviation: float


@dataclass(frozen=True, slots=True)
class CaptainModel:
    competence: float
    competence_dev: float
    discipline: float
    creativity: float
    deviation: float


@dataclass(frozen=True, slots=True)
class Doctrine:
    id: str
    weapon_bias: dict[str, float]
    focus_fire: float
    probe_use: float
    retreat_threshold_scale: float
    surrender_willingness: float
    point_defense: str
    cloak_ambush: float
    self_destruct: float
    prefers_disabling: bool
    styles: dict[str, float] = field(default_factory=dict)   # [E] signature tactics: chance a captain fights this way


@dataclass(frozen=True, slots=True)
class CollectiveRules:
    """How a hive fights [E] (sim/collective.py): what makes the Borg the Borg. A faction with one adapts to
    the weapons that hurt it, regenerates, beams drones through shields and assimilates crews.

    adapt: per weapon family ("phaser", "torpedo", "harmonic", "probe"), the damage that teaches the whole
      hive to shrug that weapon off; a new phaser frequency is learned faster each time (`relearn`).
    floor: the share of a fully adapted weapon's damage that still gets through.
    strike_*: a strike through an opening (her shield harmonics, or a facing whose shield is down or destroyed)
      aimed at one system: the gunners can see exactly where it is, so each hit has at least `strike_rolls` goes
      at it, lands `strike_accuracy` of them (the crew decks too) and does `strike_damage` × the harm. The drones
      mend what such a strike wrecks at `strike_repair` × their speed, and a drive or reactor it destroys sets her
      off `strike_chain` of the time, however whole her hull.
    """

    adapt: dict[str, float] = field(default_factory=dict)
    floor: float = 0.12
    relearn: float = 0.6
    regen_hull: float = 0.004        # share of the structure grown back per cycle
    regen_hurt: float = 0.25         # ... × this while under fire (hurt in the last `regen_quiet` cycles)
    regen_quiet: float = 6.0
    assimilate: float = 0.65         # chance a defender beaten in a boarding round becomes a drone
    takeover: float = 0.18           # per cycle, × the drones' share of the bodies aboard: a system is seized
    party: int = 14                  # drones in one beam-over
    beam_every: float = 9.0          # cycles between beam-overs
    sleep_cycles: float = 50.0       # how long the drones stay dormant when the vinculum relay fails
    chain: float = 0.3               # chance a destroyed drive or reactor sets off the ship (certain while dormant)
    tune_cut: float = 0.6            # most of their beam's damage our tuned shields can turn aside
    shift_after: float = 140.0       # damage our tuning turns aside before they shift their beam's frequency
    grace: int = 14                  # hits with stolen shield harmonics before they notice
    weak_kinds: tuple[str, ...] = ("battery", "transporter", "launcher", "tractor")   # where the relay can hide
    strike_rolls: int = 2            # goes at the aimed system each hit through an opening gets, at least
    strike_accuracy: float = 0.9     # ... and the share of them that land on it
    strike_damage: float = 2.0       # × the harm each one does to the system
    strike_repair: float = 0.3       # × the drones' repair speed on a system wrecked that way
    strike_chain: float = 0.08       # chance a drive or reactor destroyed that way sets her off, hull or no hull


@dataclass(frozen=True, slots=True)
class Faction:
    id: str
    name: str
    long_name: str
    command: str
    doctrine: Doctrine
    torpedoes: tuple[str, ...]
    probes: tuple[str, ...]
    officer_names: tuple[str, ...]
    captain_names: tuple[str, ...]
    dogma: Dogma
    computer_sophistication: float
    captains: CaptainModel
    sensor_scale: float = 1.0
    pd_discipline: float = 0.7
    # [E] how this race's weapons look on the map: beam colour, how beams are drawn, torpedo colour
    phaser_color: tuple[int, int, int] = (255, 170, 90)
    phaser_style: str = "beam"          # "beam" (a steady line) | "pulse" (a string of bolts)
    torpedo_color: tuple[int, int, int] = (255, 120, 80)
    torpedo_style: str = "photon"       # "photon" | "disruptor" | "plasma" | "pulse": the round's look in flight
    # [E] special helm and bridge orders this race's crews are drilled in, e.g. "evasive"
    orders: tuple[str, ...] = ()
    # [E] crew morale: spirits at the start of a battle (0..100), and how much damage and losses shake them
    morale_start: float = 75.0
    morale_steadiness: float = 1.0
    # [E] how a race's captains take watching their allies battered (sim/systems/disposition.py):
    # temper 0 = they are cowed, 1 = they are enraged; obstinacy = how hard they are to talk round at the start
    temper: float = 0.5
    obstinacy: float = 0.5
    temperament_dev: float = 0.2
    # [E] a hive (the Borg): adaptation, regeneration, drones and assimilation (sim/collective.py)
    collective: CollectiveRules | None = None
    # [E] chosen for random battles and patrols; False keeps a race for stories, presets and its own mode
    random: bool = True


@dataclass(slots=True)
class ContentDB:
    classes: dict[str, ShipClass] = field(default_factory=dict)
    torpedoes: dict[str, TorpedoDef] = field(default_factory=dict)
    probes: dict[str, ProbeDef] = field(default_factory=dict)
    factions: dict[str, Faction] = field(default_factory=dict)

    def classes_of(self, faction: str, include_bases: bool = True) -> list[ShipClass]:
        out = [c for c in self.classes.values() if c.faction == faction and not c.story]
        if not include_bases:
            out = [c for c in out if not c.is_base]
        return sorted(out, key=lambda c: c.mass)

    def compatible_torpedoes(self, cls: ShipClass) -> list[TorpedoDef]:
        """Torpedo types a class's tubes can load: its native type plus faction variants."""
        if cls.tubes == 0 or not cls.torpedo:
            return []
        native = self.torpedoes[cls.torpedo]
        out = [native]
        faction = self.factions[cls.faction]
        for tid in faction.torpedoes:
            t = self.torpedoes.get(tid)
            if t is None or t is native:
                continue
            # tubes built for plasma can't take antimatter casings and vice versa
            if t.is_plasma == native.is_plasma:
                out.append(t)
        return out

    def compatible_probes(self, cls: ShipClass) -> list[ProbeDef]:
        if cls.launchers == 0 or not cls.probe:
            return []
        native = self.probes[cls.probe]
        out = [native]
        for pid in self.factions[cls.faction].probes:
            p = self.probes.get(pid)
            if p is not None and p is not native:
                out.append(p)
        return out
