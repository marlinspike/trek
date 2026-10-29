"""In-flight ordnance: torpedoes and probes."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..content.schema import ProbeDef, TorpedoDef


@dataclass(slots=True, eq=False)
class Torpedo:
    id: int
    owner: int
    side: int
    spec: TorpedoDef
    x: float
    y: float
    course: float
    velocity: float          # warp
    prox: float
    arm: float               # cycles until armed
    fuse: float              # cycles of time fuse after arming
    strength: float          # plasma: remaining internal energy (yield scales with it)
    target: int | None = None
    salvo: int = 1
    target_subsystem: str | None = None
    detonate: bool = False   # set when a fuse or a hit triggers it
    fizzle: bool = False     # time fuse expired: removed quietly
    trail: list[tuple[float, float]] = field(default_factory=list)

    @property
    def armed(self) -> bool:
        return self.arm <= 0.0

    @property
    def yield_(self) -> float:
        """Warhead energy if it detonated now [R]."""
        if not self.armed:
            return 0.0
        if self.spec.is_plasma and self.spec.max_time_fuse > 0:
            return self.spec.damage * max(0.0, min(1.0, self.strength / self.spec.max_time_fuse))
        return self.spec.damage


@dataclass(slots=True, eq=False)
class Probe:
    id: int
    owner: int
    side: int
    spec: ProbeDef
    code: str
    x: float
    y: float
    course: float
    prox: float
    arm: float
    fuse: float
    target: int | None = None
    deliberate_target: bool = False  # locked on a same-side ship on purpose
    detonate: bool = False
    remote: bool = False             # detonated on command: bypasses the arming timer [R]
    trail: list[tuple[float, float]] = field(default_factory=list)

    @property
    def armed(self) -> bool:
        return self.arm <= 0.0

    @property
    def yield_(self) -> float:
        return self.spec.damage if (self.armed or self.remote or self.detonate) else 0.0
