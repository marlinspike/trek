"""Facts the simulation reports after they happen.

Events never mutate state. Renderers, the message log, AI memory, the
debrief and replays consume them. Each event carries the tick on which it
happened; `visible_to` is the set of sides allowed to learn about it
(None = public, e.g. an explosion anyone could see).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class Tone(str, Enum):
    INFO = "info"
    GOOD = "good"
    CAUTION = "caution"
    ALERT = "alert"
    CREW = "crew"


@dataclass(slots=True)
class Event:
    tick: int


@dataclass(slots=True)
class Message(Event):
    text: str
    tone: Tone = Tone.INFO
    speaker: str = ""
    ship_id: int | None = None
    visible_to: frozenset[int] | None = None


@dataclass(slots=True)
class CommandRejected(Event):
    ship_id: int
    command: str
    reason: str
    issuer: str


@dataclass(slots=True)
class PhaserFired(Event):
    ship_id: int
    bank: int
    origin: tuple[float, float]
    facing: float          # world bearing of the beam axis
    spread: float
    range: float
    hits: list[int] = field(default_factory=list)          # ship ids hit
    end: tuple[float, float] = (0.0, 0.0)                  # where the beam visibly ends
    defensive: bool = False


@dataclass(slots=True)
class TorpedoLaunched(Event):
    ship_id: int
    torpedo_id: int
    tube: int
    count: int
    ordnance: str


@dataclass(slots=True)
class ProbeLaunched(Event):
    ship_id: int
    probe_id: int
    code: str


@dataclass(slots=True)
class Detonation(Event):
    x: float
    y: float
    radius: float
    source: str            # "torpedo", "probe", "ship", "destruct"
    yield_: float


@dataclass(slots=True)
class OrdnanceDestroyed(Event):
    x: float
    y: float
    kind: str              # "torpedo" | "probe"
    by_ship: int | None


@dataclass(slots=True)
class ShieldHit(Event):
    ship_id: int
    sector: int
    absorbed: float
    penetrated: float
    collapsed: bool


@dataclass(slots=True)
class HullHit(Event):
    ship_id: int
    amount: float
    crew_lost: int
    attacker: int | None


@dataclass(slots=True)
class SubsystemDamaged(Event):
    ship_id: int
    sid: str
    label: str
    damage: int
    destroyed: bool
    targeted: bool


@dataclass(slots=True)
class SubsystemRepaired(Event):
    ship_id: int
    sid: str
    label: str


@dataclass(slots=True)
class ShipStatusChanged(Event):
    ship_id: int
    status: str
    cause: str
    by_ship: int | None = None


@dataclass(slots=True)
class ContactChanged(Event):
    side: int
    ship_id: int
    acquired: bool


@dataclass(slots=True)
class ScanCompleted(Event):
    ship_id: int
    target_id: int


@dataclass(slots=True)
class DeflectorPulsed(Event):
    ship_id: int
    x: float
    y: float
    facing: float          # compass bearing of the cone's centre
    arc: float             # full width, degrees
    range: float
    found: int             # cloaked ships lit up


@dataclass(slots=True)
class ObjectiveEnded(Event):
    ship_id: int
    officer: str
    goal: str
    group: str
    targets: tuple[int, ...]
    outcome: str           # "done" | "impossible" | "cancelled"
    reason: str = ""


@dataclass(slots=True)
class ProjectCompleted(Event):
    ship_id: int
    project: str
    tube: int | None       # where a designed round was loaded
