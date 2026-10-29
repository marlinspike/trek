"""What one side is allowed to know.

AI captains, ship computers and officers receive an `Observation`, never the
`World`. Own ships are exposed in full (a crew knows its own ship); enemy
ships appear only as `ContactView`s built from that side's sensor picture,
so fog of war, cloaks, stale tracks and scan quality apply to the AI exactly
as they do to the player. Own-ship objects are shared references for speed
and must be treated as read-only: all changes go through commands.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..content.schema import ContentDB, ShipClass
from .events import ContactChanged, Event, Message
from .rules import Rules
from .ship import Ship
from .systems.sensors import ScanRecord

if TYPE_CHECKING:
    from .allies import AllyStanding
    from .world import World


@dataclass(frozen=True, slots=True)
class ContactView:
    id: int
    label: str
    visible: bool
    identified: bool
    side: int | None            # None until identified
    cls: ShipClass | None       # None until identified
    x: float
    y: float
    vx: float
    vy: float
    course: float
    warp: float
    age: float                  # cycles since last sensor update
    scan: ScanRecord | None
    cloaked_hint: bool          # we lost it at close range: probably cloaked
    haze: float = 0.0           # 0 = exact; up to 1 beyond rated sensor range
    uncertainty: float = 0.0    # possible position error, world units

    def distance_to(self, x: float, y: float) -> float:
        return math.hypot(self.x - x, self.y - y)


@dataclass(frozen=True, slots=True)
class OrdnanceView:
    id: int
    kind: str                   # "torpedo" | "probe"
    friendly: bool
    owner: int | None           # own side only
    x: float
    y: float
    course: float
    speed: float                # world units per cycle
    armed: bool
    yield_: float               # estimated warhead
    prox: float                 # own ordnance exact, hostile estimated from type
    target: int | None          # own ordnance only
    code: str = ""
    fuse: float = 0.0           # own ordnance: cycles until the time fuse expires


class Observation:
    __slots__ = ("_w", "side", "tick", "time", "rules", "content", "_contacts", "_ordnance", "_events")

    def __init__(self, world: World, side: int) -> None:
        self._w = world
        self.side = side
        self.tick = world.tick
        self.time = world.time
        self.rules: Rules = world.rules
        self.content: ContentDB = world.content
        self._contacts: dict[int, ContactView] | None = None
        self._ordnance: list[OrdnanceView] | None = None
        self._events: list[Event] | None = None

    # ------------------------------------------------------------- own side

    def own_ships(self, alive_only: bool = True) -> list[Ship]:
        return self._w.ships_of(self.side, alive_only)

    def own(self, ship_id: int) -> Ship | None:
        s = self._w.ships.get(ship_id)
        return s if s is not None and s.side == self.side else None

    def ally_order(self, ship_id: int) -> AllyStanding | None:
        """Standing orders the flagship has given one of our ships."""
        return self._w.ally_orders.get(ship_id)

    def side_name(self, side: int | None) -> str:
        return self._w.side_names.get(side, "?") if side is not None else "?"

    def holds(self, ship_id: int) -> dict[str, float]:
        return self._w.holds(ship_id)

    # ------------------------------------------------------------- contacts

    def contacts(self) -> dict[int, ContactView]:
        if self._contacts is None:
            w = self._w
            out: dict[int, ContactView] = {}
            intel = w.intel.get(self.side)
            if intel is not None:
                for cid, c in intel.contacts.items():
                    s = w.ships.get(cid)
                    if s is None or not s.exists or not c.ever:
                        continue
                    pos = w.apparent_position(self.side, cid)
                    if pos is None:
                        continue
                    age = (w.tick - c.last_tick) * w.rules.dt
                    vx, vy = (c.vx, c.vy) if c.visible or intel.dead_reckoning else (0.0, 0.0)
                    out[cid] = ContactView(
                        id=cid, label=w.label(self.side, cid), visible=c.visible, identified=c.identified,
                        side=s.side if c.identified else None, cls=s.cls if c.identified else None,
                        x=pos[0], y=pos[1], vx=vx, vy=vy, course=c.course, warp=c.warp, age=age,
                        scan=c.scan, cloaked_hint=(not c.visible and s.cls.can_cloak and c.identified),
                        haze=c.haze if c.visible else 0.0, uncertainty=c.uncertainty if c.visible else 0.0,
                    )
            self._contacts = out
        return self._contacts

    def contact(self, ship_id: int) -> ContactView | None:
        return self.contacts().get(ship_id)

    def hostile_contacts(self) -> list[ContactView]:
        """Contacts not known to be on our side (unidentified contacts count as hostile)."""
        return [c for c in self.contacts().values() if c.side is None or c.side != self.side]

    def torpedo_pressure(self, ship_id: int) -> float:
        return self._w.torpedo_pressure.get(ship_id, 0.0)

    # ------------------------------------------------------------- ordnance

    def ordnance(self) -> list[OrdnanceView]:
        if self._ordnance is None:
            w = self._w
            upw = w.rules.units_per_warp
            intel = w.intel.get(self.side)
            seen = intel.visible_ordnance if intel is not None else set()
            out: list[OrdnanceView] = []
            for t in w.torpedoes:
                if t.detonate or t.fizzle:
                    continue
                mine = t.side == self.side
                if not mine and t.id not in seen:
                    continue
                out.append(OrdnanceView(
                    t.id, "torpedo", mine, t.owner if mine else None, t.x, t.y, t.course, t.velocity * upw,
                    t.armed, t.yield_ if mine else t.spec.damage, t.prox if mine else t.spec.max_prox,
                    t.target if mine else None,
                ))
            for p in w.probes:
                if p.detonate:
                    continue
                mine = p.side == self.side
                if not mine and p.id not in seen:
                    continue
                out.append(OrdnanceView(
                    p.id, "probe", mine, p.owner if mine else None, p.x, p.y, p.course, p.spec.velocity * upw,
                    p.armed, p.spec.damage, p.prox if mine else p.spec.max_prox, p.target if mine else None,
                    p.code if mine else "", p.fuse if mine else 0.0,
                ))
            self._ordnance = out
        return self._ordnance

    def threats(self) -> list[OrdnanceView]:
        return [o for o in self.ordnance() if not o.friendly]

    # ------------------------------------------------------------- events

    def events(self) -> list[Event]:
        """Events from the last step this side is entitled to see."""
        if self._events is None:
            out = []
            for ev in self._w.step_events:
                vis = getattr(ev, "visible_to", None)
                if isinstance(ev, Message) and vis is not None and self.side not in vis:
                    continue
                if isinstance(ev, ContactChanged) and ev.side != self.side:
                    continue
                out.append(ev)
            self._events = out
        return self._events


__all__ = ["ContactView", "Observation", "OrdnanceView"]
