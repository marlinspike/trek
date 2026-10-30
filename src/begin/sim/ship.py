"""Mutable ship state: the ship and its subsystems.

Every subsystem shares the `Subsystem` contract — identity, hull location,
damage and repair progress — so damage, repair, scanning and the UI treat
them uniformly. Behaviour lives in `begin.sim.systems.*`, which operate on
these records inside the authoritative `World` step.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from enum import Enum
from typing import Iterator, Literal

from ..content.schema import MountDef, ShipClass


class Kind(str, Enum):
    REACTOR = "reactor"
    BATTERY = "battery"
    DRIVE = "drive"
    IMPULSE = "impulse"
    SENSORS = "sensors"
    COMPUTER = "computer"
    SHIELD = "shield"
    PHASER = "phaser"
    TUBE = "tube"
    LAUNCHER = "launcher"
    TRANSPORTER = "transporter"
    TRACTOR = "tractor"
    CLOAK = "cloak"


# Begin's per-roll hit chances by class (sub_F820) [R]; computer is ours [E].
DAMAGE_WEIGHT: dict[Kind, float] = {
    Kind.SHIELD: 0.75, Kind.TUBE: 0.50, Kind.PHASER: 0.45, Kind.DRIVE: 0.40,
    Kind.REACTOR: 0.60, Kind.LAUNCHER: 0.20, Kind.BATTERY: 0.15, Kind.TRANSPORTER: 0.10,
    Kind.SENSORS: 0.10, Kind.CLOAK: 0.10, Kind.IMPULSE: 0.05, Kind.TRACTOR: 0.05,
    Kind.COMPUTER: 0.08,
}

# A repair priority is a kind of subsystem, or the hull itself [E].
HULL: Literal["hull"] = "hull"
RepairTarget = Kind | Literal["hull"]



def repair_words(p: RepairTarget | None, default: str = "all systems") -> str:
    """A repair priority in plain words: 'shield', 'hull', or the default when there is none."""
    return default if p is None else p.value if isinstance(p, Kind) else p


# Which repair-rate column of the class repairs each kind [R].
REPAIR_CLASS: dict[Kind, str] = {
    Kind.REACTOR: "reactor", Kind.BATTERY: "battery", Kind.DRIVE: "drive", Kind.IMPULSE: "impulse",
    Kind.SENSORS: "sensors", Kind.COMPUTER: "sensors", Kind.SHIELD: "shield", Kind.PHASER: "phaser",
    Kind.TUBE: "tube", Kind.LAUNCHER: "launcher", Kind.TRANSPORTER: "transporter",
    Kind.TRACTOR: "tractor", Kind.CLOAK: "cloak",
}

KIND_LABEL: dict[Kind, str] = {
    Kind.REACTOR: "Reactor", Kind.BATTERY: "Battery", Kind.DRIVE: "Warp drive",
    Kind.IMPULSE: "Impulse engine", Kind.SENSORS: "Sensors", Kind.COMPUTER: "Computer",
    Kind.SHIELD: "Shield", Kind.PHASER: "Phaser bank", Kind.TUBE: "Torpedo tube",
    Kind.LAUNCHER: "Probe launcher", Kind.TRANSPORTER: "Transporter", Kind.TRACTOR: "Tractor beam",
    Kind.CLOAK: "Cloaking device",
}

# Groups the player can target with subsystem fire.
TARGETABLE_GROUPS: dict[str, tuple[Kind, ...]] = {
    "propulsion": (Kind.DRIVE, Kind.IMPULSE),
    "weapons": (Kind.PHASER, Kind.TUBE, Kind.LAUNCHER),
    "phasers": (Kind.PHASER,),
    "torpedoes": (Kind.TUBE,),
    "shields": (Kind.SHIELD,),
    "power": (Kind.REACTOR, Kind.BATTERY),
    "sensors": (Kind.SENSORS, Kind.COMPUTER),
    "cloak": (Kind.CLOAK,),
}


@dataclass(slots=True, eq=False)
class Subsystem:
    sid: str
    kind: Kind
    index: int
    pos: tuple[float, float]  # hull design coordinates
    damage: int = 0
    repair_progress: float = 0.0

    @property
    def health(self) -> float:
        return (100 - self.damage) / 100.0

    @property
    def destroyed(self) -> bool:
        return self.damage >= 100

    @property
    def intact(self) -> bool:
        return self.damage == 0

    @property
    def label(self) -> str:
        base = KIND_LABEL[self.kind]
        return f"{base} {self.index + 1}" if self.kind not in _SINGLETONS else base

    def on_damaged(self) -> None:
        """Hook for kinds that lose transient state when hit."""


_SINGLETONS = {Kind.SENSORS, Kind.COMPUTER, Kind.IMPULSE, Kind.TRACTOR, Kind.CLOAK}


@dataclass(slots=True, eq=False)
class Reactor(Subsystem):
    pass


@dataclass(slots=True, eq=False)
class Battery(Subsystem):
    charge: float = 0.0

    @property
    def online(self) -> bool:
        # [R] a damaged battery is offline until repaired to 0%
        return self.damage == 0

    def on_damaged(self) -> None:
        self.charge = 0.0


@dataclass(slots=True, eq=False)
class Drive(Subsystem):
    temp: float = 12.0
    temp_rate: float = 0.0  # degrees per cycle, for the display


@dataclass(slots=True, eq=False)
class Shield(Subsystem):
    facing: float = 0.0        # centre of the 60° field, relative to the bow
    strength: float = 100.0    # % of design strength (temporary loss regenerates)
    effective: float = 100.0   # % actually absorbing this tick (0 when down or starved)
    up: bool = True
    reinforced: bool = False
    flash: float = 0.0         # seconds of hit glow remaining (presentation hint)

    @property
    def ceiling(self) -> float:
        return float(100 - self.damage)


class FireMode(str, Enum):
    """Who pulls the trigger on a weapon mount [E].

    MANUAL: fires only on an explicit order.
    ASSISTED: the ship computer fires at the captain's designated target
      when it has a good solution; it never chooses targets itself.
    AUTOMATIC: the computer chooses targets (designated target first) and fires.
    """

    MANUAL = "manual"
    ASSISTED = "assisted"
    AUTOMATIC = "automatic"


class PDDoctrine(str, Enum):
    """Automatic point defense posture [E]."""

    OFF = "off"
    CONSERVATIVE = "conservative"  # reserved (defense) banks only, imminent threats only
    BALANCED = "balanced"          # reserved banks, plus flex banks against dangerous salvos
    AGGRESSIVE = "aggressive"      # any idle bank engages any armed threat in range


class BankRole(str, Enum):
    OFFENSE = "offense"
    FLEX = "flex"
    DEFENSE = "defense"


@dataclass(slots=True, eq=False)
class PhaserBank(Subsystem):
    mount: MountDef = field(default_factory=lambda: MountDef((0.0, 0.0), 0.0, 360.0))
    charge: float = 0.0
    enabled: bool = True
    lock: int | None = None
    mark: float = 0.0         # relative bearing the bank points at
    spread: float = 45.0
    role: BankRole = BankRole.FLEX
    fire_mode: FireMode = FireMode.MANUAL

    def on_damaged(self) -> None:
        self.charge = 0.0
        self.lock = None


@dataclass(slots=True)
class LoadedTorpedo:
    ordnance: str
    prox: float


@dataclass(slots=True, eq=False)
class Tube(Subsystem):
    mount: MountDef = field(default_factory=lambda: MountDef((0.0, 0.0), 0.0, 360.0))
    charge: float = 0.0       # 0..100 %
    loaded: LoadedTorpedo | None = None
    enabled: bool = True
    lock: int | None = None
    mark: float = 0.0
    dispersion: float = 0.0   # fan offset applied to this tube's solution
    fire_mode: FireMode = FireMode.MANUAL
    # autoload configuration remembered per mount
    autoload: bool = True
    load_ordnance: str = ""
    load_prox: float = 0.0
    manual_load_pending: bool = False

    def on_damaged(self) -> None:
        # [R] a damaged tube loses its charge, lock and loaded torpedo
        self.charge = 0.0
        self.loaded = None
        self.lock = None


@dataclass(slots=True)
class LoadedProbe:
    ordnance: str
    prox: float
    time: float
    code: str


@dataclass(slots=True, eq=False)
class Launcher(Subsystem):
    mount: MountDef = field(default_factory=lambda: MountDef((0.0, 0.0), 180.0, 360.0))
    loaded: LoadedProbe | None = None
    prep: float = 0.0          # cycles of preparation accumulated for the next probe
    autoload: bool = True
    load_ordnance: str = ""
    load_prox: float = 0.0
    load_time: float = 0.0
    manual_load_pending: bool = False

    def on_damaged(self) -> None:
        if self.destroyed:
            self.loaded = None


class ShipStatus(str, Enum):
    ACTIVE = "active"
    DESTROYED = "destroyed"
    DERELICT = "derelict"       # all hands lost
    SURRENDERED = "surrendered"
    ESCAPED = "escaped"
    CAPTURED = "captured"


class HelmMode(str, Enum):
    COURSE = "course"
    PURSUE = "pursue"
    ELUDE = "elude"


@dataclass(slots=True)
class PowerReport:
    """Per-cycle power figures for displays and AI (eu per cycle)."""

    warp_budget: float = 0.0
    warp_used: float = 0.0
    reactor: float = 0.0
    generation: float = 0.0
    life_support: float = 0.0
    shields: float = 0.0
    cloak: float = 0.0
    tractor: float = 0.0
    weapons: float = 0.0
    stored: float = 0.0
    capacity: float = 0.0
    shields_starved: bool = False
    life_failing: bool = False

    @property
    def consumption(self) -> float:
        return self.life_support + self.shields + self.cloak + self.tractor + self.weapons

    @property
    def net(self) -> float:
        return self.generation - self.consumption


@dataclass(slots=True)
class BattleStats:
    damage_dealt: float = 0.0
    damage_taken: float = 0.0
    shield_damage_absorbed: float = 0.0
    hull_damage_taken: float = 0.0
    subsystems_disabled: int = 0
    phaser_shots: int = 0
    phaser_hits: int = 0
    torpedoes_fired: int = 0
    torpedo_hits: int = 0
    probes_launched: int = 0
    probe_hits: int = 0
    ordnance_intercepted: int = 0
    kills: int = 0
    crew_lost: int = 0


@dataclass(slots=True, eq=False)
class Ship:
    id: int
    name: str
    cls: ShipClass
    side: int
    faction: str
    captain: str
    x: float = 0.0
    y: float = 0.0
    course: float = 0.0
    desired_course: float = 0.0
    warp: float = 0.0
    desired_warp: float = 0.0
    helm_mode: HelmMode = HelmMode.COURSE
    helm_target: int | None = None
    max_attainable_warp: float = 0.0

    crew: int = 0
    structure: float = 0.0
    structure_max: float = 0.0
    armour: float = 0.0
    status: ShipStatus = ShipStatus.ACTIVE

    reactors: list[Reactor] = field(default_factory=list)
    batteries: list[Battery] = field(default_factory=list)
    drives: list[Drive] = field(default_factory=list)
    shields: list[Shield] = field(default_factory=list)
    banks: list[PhaserBank] = field(default_factory=list)
    tubes: list[Tube] = field(default_factory=list)
    launchers: list[Launcher] = field(default_factory=list)
    transporters: list[Subsystem] = field(default_factory=list)
    impulse: Subsystem | None = None
    sensors: Subsystem | None = None
    computer: Subsystem | None = None
    tractor: Subsystem | None = None
    cloak: Subsystem | None = None

    power: PowerReport = field(default_factory=PowerReport)
    life_failure_time: float = 0.0
    torps_remaining: int = 0
    magazine_empty_told: bool = False
    projects: dict[str, float] = field(default_factory=dict)   # crew projects under way: id -> cycles left
    probes_remaining: int = 0

    # fire control state shared by every controller of this ship
    target: int | None = None
    target_subsystem: str | None = None  # TARGETABLE_GROUPS key or a subsystem sid

    cloaked: bool = False
    reveal_time: float = 0.0           # cycles the ship stays visible after firing/being hit
    tractor_target: int | None = None
    docked_to: int | None = None
    boarders: int = 0
    boarder_side: int = -1
    self_destruct: float = -1.0        # cycles remaining, -1 = off
    repair_priority: RepairTarget | None = None
    evasive: bool = False              # the helm dodges incoming torpedoes on its own (Federation drill) [E]
    evasive_resume: tuple[float, float, HelmMode, int | None] | None = None   # the captain's order to go back to
    repairs_by: str = ""               # officer id directing the repair crews; "" = the captain [E]
    last_hull_hit: int = -10**9        # tick the hull last took damage: field repairs slow down under fire [E]
    delegated: set[str] = field(default_factory=set)  # bridge stations run by officers (crew/stations.py)
    pending_volley: tuple[int, int | None, str | None, int] | None = None  # bait follow-up: (tick, target, subsystem, issuer) [E]
    deflector_ready: bool = False      # the dish is set up for tachyon pulses [E]
    deflector_cooldown: float = 0.0    # cycles until the next pulse
    objectives: list = field(default_factory=list)  # sim.objectives.Objective: standing orders to officers [E]
    conn: str = ""                     # officer id in command of the whole bridge; "" = the captain [E]
    conn_saved: set[str] = field(default_factory=set)  # stations delegated before the officer took the bridge
    escape_time: float = 0.0
    surrender_time: float = 0.0

    base_sophistication: float = 0.5
    pd_doctrine: PDDoctrine = PDDoctrine.BALANCED
    stats: BattleStats = field(default_factory=BattleStats)
    trail: list[tuple[float, float]] = field(default_factory=list)

    # ------------------------------------------------------------- helpers

    @property
    def alive(self) -> bool:
        """Still a participant: can act and be acted upon as a combatant."""
        return self.status == ShipStatus.ACTIVE

    @property
    def exists(self) -> bool:
        """Still present in space (derelicts and surrendered ships remain)."""
        return self.status not in (ShipStatus.DESTROYED, ShipStatus.ESCAPED)

    def subsystems(self) -> Iterator[Subsystem]:
        yield from self.reactors
        yield from self.batteries
        yield from self.drives
        yield from self.shields
        yield from self.banks
        yield from self.tubes
        yield from self.launchers
        yield from self.transporters
        for s in (self.impulse, self.sensors, self.computer, self.tractor, self.cloak):
            if s is not None:
                yield s

    def subsystem(self, sid: str) -> Subsystem | None:
        for s in self.subsystems():
            if s.sid == sid:
                return s
        return None

    def heading(self) -> tuple[float, float]:
        r = math.radians(self.course)
        return math.sin(r), math.cos(r)

    def velocity(self, units_per_warp: float = 100.0) -> tuple[float, float]:
        hx, hy = self.heading()
        v = self.warp * units_per_warp
        return hx * v, hy * v

    def hull_to_world(self, px: float, py: float) -> tuple[float, float]:
        """Hull design coordinates -> world position."""
        s = self.cls.hull.scale
        r = math.radians(self.course)
        c, sn = math.cos(r), math.sin(r)
        hx, hy = px * s, py * s
        return self.x + hx * c + hy * sn, self.y - hx * sn + hy * c

    @property
    def sophistication(self) -> float:
        """Effective computer sophistication after damage."""
        if self.computer is None:
            return self.base_sophistication * 0.5
        return self.base_sophistication * (0.35 + 0.65 * self.computer.health)

    def can_move(self) -> bool:
        return self.max_attainable_warp > 0.0

    def boarding_party(self) -> int:
        """Default boarding party: a quarter of the crew, at least 6, at most what the transporters lift at once."""
        lift = self.cls.beam_cap * max(1, len(self.transporters))
        return int(max(6.0, min(lift, self.crew * 0.25)))

    def sensor_range(self) -> float:
        if self.sensors is None or self.sensors.destroyed:
            return 0.0
        return self.cls.rated_sensor_range * (0.5 + 0.5 * self.sensors.health)

    def battery_charge(self) -> float:
        return sum(b.charge for b in self.batteries if b.online)

    def battery_capacity(self) -> float:
        return sum(self.cls.battery_capacity for b in self.batteries if b.online)

    def weapons_operational(self) -> bool:
        return any(b.intact for b in self.banks) or any(t.intact for t in self.tubes) or any(
            l.intact for l in self.launchers
        )

    def shield_for_bearing(self, rel_bearing: float) -> Shield | None:
        """The shield covering a relative bearing (Begin face mask, §5)."""
        # the shield whose field centre is nearest; ties resolve to the first listed
        best: Shield | None = None
        best_d = 999.0
        for sh in self.shields:
            d = abs(((rel_bearing - sh.facing) + 180.0) % 360.0 - 180.0)
            if d < best_d - 1e-9:
                best, best_d = sh, d
        return best


__all__ = [
    "Battery", "BankRole", "FireMode", "PDDoctrine", "BattleStats", "DAMAGE_WEIGHT", "Drive", "HelmMode", "KIND_LABEL", "Kind",
    "HULL", "Launcher", "LoadedProbe", "LoadedTorpedo", "PhaserBank", "PowerReport", "REPAIR_CLASS",
    "Reactor", "RepairTarget", "repair_words", "Shield", "Ship", "ShipStatus", "Subsystem", "TARGETABLE_GROUPS", "Tube",
]
