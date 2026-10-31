"""Where a tour of duty stands: your squadron as it is now, the flags your choices set, the log [E].

`TourState` is what is saved after every fight (`config/tours/<tour id>.json`), so a tour can
be stopped between battles and taken up later. A `ShipRecord` is one ship of your squadron
between battles: the slow things that carry over (hull, systems, crew, magazines, morale).
Shields, batteries, heat and position reset every fight.
"""

from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..content.schema import ContentDB
from ..sim.rules import Rules
from ..sim.ship import REPAIR_CLASS, Kind, Ship, ShipStatus

ROLES = ("flagship", "escort", "prize", "reinforcement")
STARDATE_START = 47310.0
STARDATE_PER_STOP = 3.7
MORALE_SETTLE = 0.5         # between fights, morale moves this share of the way back to its baseline
SAVE_VERSION = 1


@dataclass
class ShipRecord:
    class_id: str
    name: str
    role: str = "escort"                 # flagship | escort | prize | reinforcement
    captain: str = ""
    hull: float = 1.0                    # share of the hull's full structure
    crew: int | None = None              # None = her full complement
    torps: int | None = None             # None = a full magazine
    probes: int | None = None
    morale: float | None = None          # None = her navy's usual
    damage: dict[str, int] = field(default_factory=dict)   # subsystem id -> % damage
    lost: bool = False
    lost_at: str = ""                    # the stop where she was lost
    joined: str = ""                     # the stop where she joined (prizes and reinforcements)
    reserve: bool = False                # kept at the starbase: misses fights, refits there
    kills: int = 0

    @property
    def active(self) -> bool:
        return not self.lost and not self.reserve

    def crew_now(self, content: ContentDB) -> int:
        return content.classes[self.class_id].crew if self.crew is None else self.crew

    def torps_now(self, content: ContentDB) -> int:
        return content.classes[self.class_id].torps_carried if self.torps is None else self.torps


@dataclass
class LogEntry:
    """One stop's page of the captain's log: each officer's station entry, each captain's report, and yours."""
    stop_id: str
    title: str
    stardate: float
    outcome: str                                    # "victory" | "defeat" | "withdrew" | ...
    stations: dict[str, str] = field(default_factory=dict)    # officer id -> their entry
    captains: dict[str, str] = field(default_factory=dict)    # ship name -> her captain's report
    captain: str = ""                               # the captain's entry: drafted, then yours to edit
    edited: bool = False                            # you've changed the captain's entry: never redraft it
    voiced: list[str] = field(default_factory=list)  # entries a language model has already written
    facts: dict[str, Any] = field(default_factory=dict)   # what happened, for the model to write from


@dataclass
class StopResult:
    stop_id: str
    outcome: str
    cycles: float
    kills: int = 0
    captured: list[str] = field(default_factory=list)
    lost: list[str] = field(default_factory=list)


@dataclass
class TourState:
    tour_id: str
    squadron: list[ShipRecord] = field(default_factory=list)
    stop: int = 0                                   # index of the next stop to fight
    flags: list[str] = field(default_factory=list)
    calls_left: int = 2
    pending: list[str] = field(default_factory=list)   # reinforcements requested from the Ready Room (class ids)
    choice: int | None = None                       # the choice made for the next stop
    log: list[LogEntry] = field(default_factory=list)
    results: list[StopResult] = field(default_factory=list)
    lessons: dict[str, float] = field(default_factory=dict)   # what the enemy has learned: caution, press
    over: str = ""                                  # "" while under way, then "won" | "lost"
    seed: int = 1

    # ------------------------------------------------------------ queries

    @property
    def flagship(self) -> ShipRecord:
        return next(r for r in self.squadron if r.role == "flagship")

    def active(self) -> list[ShipRecord]:
        """The ships that fight the next battle, flagship first."""
        ships = [r for r in self.squadron if r.active]
        return sorted(ships, key=lambda r: r.role != "flagship")

    def stardate(self) -> float:
        return round(STARDATE_START + STARDATE_PER_STOP * len(self.results), 1)

    # ------------------------------------------------------------ saving

    def to_json(self) -> dict[str, Any]:
        d = dataclasses.asdict(self)
        d["version"] = SAVE_VERSION
        return d

    @staticmethod
    def from_json(d: dict[str, Any]) -> TourState:
        d = dict(d)
        d.pop("version", None)
        d["squadron"] = [ShipRecord(**r) for r in d.get("squadron", [])]
        d["log"] = [LogEntry(**e) for e in d.get("log", [])]
        d["results"] = [StopResult(**r) for r in d.get("results", [])]
        return TourState(**d)

    def save(self, folder: Path) -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"{self.tour_id}.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.to_json(), indent=1))
        tmp.replace(path)
        return path

    @staticmethod
    def load(folder: Path, tour_id: str) -> TourState | None:
        path = folder / f"{tour_id}.json"
        try:
            return TourState.from_json(json.loads(path.read_text()))
        except (OSError, ValueError, TypeError, KeyError):
            return None


# ------------------------------------------------------------------ ships in and out of battle

def apply_record(ship: Ship, rec: ShipRecord) -> None:
    """Make a freshly built ship the ship the record says she is."""
    ship.structure = max(1.0, ship.structure_max * rec.hull)
    if rec.crew is not None:
        ship.crew = rec.crew
    if rec.torps is not None:
        ship.torps_remaining = rec.torps
    if rec.probes is not None:
        ship.probes_remaining = rec.probes
    if rec.morale is not None:
        ship.morale = rec.morale
    for sub in ship.subsystems():
        d = rec.damage.get(sub.sid)
        if d:
            sub.damage = max(0, min(100, int(d)))
    if rec.captain:
        ship.captain = rec.captain


def harvest(ship: Ship, rec: ShipRecord, side: int | None = None) -> None:
    """After the battle: write back what she has left. A ship destroyed, abandoned, surrendered or boarded
    and taken by the enemy (her side changed) is lost."""
    gone = ship.status in (ShipStatus.DESTROYED, ShipStatus.DERELICT, ShipStatus.CAPTURED, ShipStatus.SURRENDERED) \
        or ship.crew <= 0 or (side is not None and ship.side != side)
    rec.lost = rec.lost or gone
    rec.hull = round(max(0.0, ship.structure / max(1.0, ship.structure_max)), 4)
    rec.crew = max(0, ship.crew)
    loaded_t = sum(1 for t in ship.tubes if t.loaded is not None)
    loaded_p = sum(1 for lch in ship.launchers if lch.loaded is not None)
    rec.torps = ship.torps_remaining + loaded_t        # what's in the tubes goes back in the magazine
    rec.probes = ship.probes_remaining + loaded_p
    rec.morale = round(ship.morale, 1)
    rec.damage = {s.sid: s.damage for s in ship.subsystems() if s.damage > 0}
    rec.kills += ship.stats.kills
    if rec.role != "flagship":       # the flagship's captain is you
        rec.captain = ship.captain or rec.captain


def record_of(ship: Ship, role: str, joined: str) -> ShipRecord:
    """A ship that joined during the battle (a prize or a reinforcement), as a new record."""
    rec = ShipRecord(ship.cls.id, ship.name, role=role, captain=ship.captain, joined=joined)
    harvest(ship, rec)
    rec.kills = 0
    return rec


def resupply(rec: ShipRecord, content: ContentDB, share: float) -> None:
    """A supply ship meets the squadron on the way: torpedoes and probes, up to `share` of a full load more."""
    if rec.lost or share <= 0:
        return
    cls = content.classes[rec.class_id]
    if rec.torps is not None:
        rec.torps = min(cls.torps_carried, rec.torps + int(round(cls.torps_carried * share)))
        if rec.torps >= cls.torps_carried:
            rec.torps = None
    if rec.probes is not None:
        rec.probes = min(cls.probes_carried, rec.probes + int(round(cls.probes_carried * share)))
        if rec.probes >= cls.probes_carried:
            rec.probes = None


def transit(rec: ShipRecord, content: ContentDB, rules: Rules, cycles: float) -> None:
    """Field repairs on the way to the next stop: the crews work on systems and patch the hull [R §10 rates].

    Uses the expected repair rate (the game rolls uniform 0..2 per tick, so on average the class rate),
    scaled by the surviving crew. The hull can only be patched to the field limit; a base does the rest.
    """
    if rec.lost:
        return
    cls = content.classes[rec.class_id]
    crew = rec.crew_now(content)
    eff = crew / max(1, cls.crew)
    if eff < 0.1:
        return
    for sid, dmg in list(rec.damage.items()):
        kind = _kind_of(sid)
        rate = cls.repair.rate(REPAIR_CLASS[kind]) if kind is not None else 1.0
        left = dmg - rate * eff * cycles
        if left <= 0:
            del rec.damage[sid]
        else:
            rec.damage[sid] = int(round(left))
    limit = rules.hull_field_limit
    if rec.hull < limit:
        rec.hull = round(min(limit, rec.hull + rules.hull_repair_rate * eff * cycles), 4)
    if rec.morale is not None:
        base = _morale_base(content, rec)
        rec.morale = round(base + (rec.morale - base) * MORALE_SETTLE, 1)


def refit(rec: ShipRecord, content: ContentDB) -> None:
    """A starbase puts her right: hull, systems, a full crew and full magazines."""
    if rec.lost:
        return
    rec.hull = 1.0
    rec.damage = {}
    rec.crew = None
    rec.torps = None
    rec.probes = None
    if rec.morale is not None:
        rec.morale = max(rec.morale, _morale_base(content, rec))


def _morale_base(content: ContentDB, rec: ShipRecord) -> float:
    return content.factions[content.classes[rec.class_id].faction].morale_start


def _kind_of(sid: str) -> Kind | None:
    word = sid.rstrip("0123456789")
    try:
        return Kind(word)
    except ValueError:
        return None


def fleet_cost(class_id: str, content: ContentDB) -> int:
    """What a ship costs from the squadron budget: her mass, rounded."""
    return int(round(content.classes[class_id].mass))


__all__ = [
    "LogEntry", "ROLES", "ShipRecord", "StopResult", "TourState", "apply_record", "fleet_cost", "harvest",
    "record_of", "refit", "resupply", "transit",
]
