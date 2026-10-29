"""Post-battle assessment [M scoring idea, E formula and wording].

Begin scored "own condition relative to the enemy's, multiplied by the
starting odds", with seven verdict tiers per nation (thresholds 15, 5, 2,
0, −2, −5). We keep the shape: each side's fighting value is the sum over
its ships of design strength × condition; the score is the enemy's loss
minus our loss (in tenths of starting value) scaled by the starting odds.
Destroying a ship and killing its crew count the same, as in Begin.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .ship import Ship, ShipStatus
from .world import World

VERDICT_THRESHOLDS = (15.0, 5.0, 2.0, 0.0, -2.0, -5.0)
VERDICTS = (
    "A legendary victory. Command will be telling this one for years.",
    "A decisive victory.",
    "A clear victory.",
    "Marginally in your favour.",
    "Inconclusive. Neither side can claim much.",
    "A defeat. Command expects a full report.",
    "A disaster. There will be an inquiry.",
)


def design_value(ship: Ship) -> float:
    cls = ship.cls
    return 1.0 + cls.banks * cls.banks_range / 1000.0 + cls.tubes * 6.0 + cls.mass / 40.0


def condition(ship: Ship) -> float:
    """0..1 fighting condition as the debrief sees it."""
    if ship.status in (ShipStatus.DESTROYED, ShipStatus.DERELICT, ShipStatus.CAPTURED):
        return 0.0
    if ship.status == ShipStatus.SURRENDERED:
        return 0.05
    hull = max(0.0, ship.structure) / max(1.0, ship.structure_max)
    crew = ship.crew / max(1, ship.cls.crew)
    weapons = [s.health for s in (*ship.banks, *ship.tubes)]
    w = sum(weapons) / len(weapons) if weapons else 1.0
    c = 0.45 * hull + 0.3 * crew + 0.25 * w
    if ship.status == ShipStatus.ESCAPED:
        c *= 0.6  # left the field
    return c


@dataclass
class SideResult:
    side: int
    start_value: float
    end_value: float
    ships: int
    lost: int
    escaped: int
    surrendered: int
    disabled: int

    @property
    def loss(self) -> float:
        return 0.0 if self.start_value <= 0 else 1.0 - self.end_value / self.start_value


@dataclass
class Assessment:
    start_values: dict[int, float] = field(default_factory=dict)
    start_owner: dict[int, int] = field(default_factory=dict)  # ship id -> original side

    @staticmethod
    def begin(world: World) -> Assessment:
        a = Assessment()
        for s in world.ships.values():
            a.start_values[s.side] = a.start_values.get(s.side, 0.0) + design_value(s)
            a.start_owner[s.id] = s.side
        return a

    def sides(self, world: World) -> dict[int, SideResult]:
        out: dict[int, SideResult] = {}
        for side, sv in self.start_values.items():
            out[side] = SideResult(side, sv, 0.0, 0, 0, 0, 0, 0)
        for s in world.ships.values():
            side = self.start_owner.get(s.id, s.side)
            r = out.setdefault(side, SideResult(side, 0.0, 0.0, 0, 0, 0, 0, 0))
            r.ships += 1
            if s.side != side:
                r.lost += 1  # captured by the enemy
                continue
            r.end_value += design_value(s) * condition(s)
            if s.status in (ShipStatus.DESTROYED, ShipStatus.DERELICT):
                r.lost += 1
            elif s.status == ShipStatus.ESCAPED:
                r.escaped += 1
            elif s.status == ShipStatus.SURRENDERED:
                r.surrendered += 1
            elif s.alive and (not s.can_move() or not s.weapons_operational()):
                r.disabled += 1
        return out

    def score(self, world: World, side: int) -> float:
        res = self.sides(world)
        me = res.get(side)
        if me is None:
            return 0.0
        enemies = [r for s, r in res.items() if s != side]
        if not enemies:
            return 0.0
        e_start = sum(r.start_value for r in enemies)
        e_end = sum(r.end_value for r in enemies)
        e_loss = 0.0 if e_start <= 0 else 1.0 - e_end / e_start
        odds = e_start / max(1e-6, me.start_value)
        return (e_loss - me.loss) * 10.0 * odds

    @staticmethod
    def verdict(score: float) -> str:
        for th, text in zip(VERDICT_THRESHOLDS, VERDICTS):
            if score >= th:
                return text
        return VERDICTS[-1]


__all__ = ["Assessment", "SideResult", "VERDICTS", "condition", "design_value"]
