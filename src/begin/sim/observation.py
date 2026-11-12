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
from .ship import Ship, ShipStatus
from .systems.sensors import Assessment, ScanRecord

if TYPE_CHECKING:
    from .allies import AllyStanding
    from .systems.disposition import Reading
    from .world import Outcome, PendingScan, World


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
    assessed: Assessment | None = None   # her condition as our own hits have shown it, kept current
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
    count: int = 1              # rounds flying together in this group (a salvo), which anyone can count
    faction: str = ""           # whose make it is: anyone can tell a race's torpedoes by their look [E]


def _make(w: World, owner: int | None) -> str:
    s = w.ships.get(owner) if owner is not None else None
    return s.faction if s is not None else ""


class Observation:
    __slots__ = ("_w", "side", "tick", "time", "rules", "content", "outcome", "_contacts", "_ordnance", "_events")

    def __init__(self, world: World, side: int) -> None:
        self._w = world
        self.side = side
        self.tick = world.tick
        self.time = world.time
        self.rules: Rules = world.rules
        self.content: ContentDB = world.content
        self.outcome: Outcome = world.outcome     # who won, once it is over: public knowledge
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
                        assessed=c.assessed,
                    )
            self._contacts = out
        return self._contacts

    def contact(self, ship_id: int) -> ContactView | None:
        return self.contacts().get(ship_id)

    def gone(self) -> set[int]:
        """Ships out of the fight, which everyone can tell: destroyed, escaped, surrendered or derelict."""
        return {sid for sid, s in self._w.ships.items() if not s.alive}

    def surrendered(self) -> set[int]:
        """Ships that have struck their colours, which everyone can tell: shields down, waiting to be boarded [E]."""
        return {sid for sid, s in self._w.ships.items() if s.status.value == "surrendered"}

    def countdowns(self) -> list[tuple[int, float, float, float, float]]:
        """Self-destructs in their last five cycles, which the ship announces to everyone [R]: (ship id, x, y,
        cycles left, blast radius). Positions are as this side knows them; a ship we cannot place is left out."""
        w = self._w
        rules = w.rules
        out: list[tuple[int, float, float, float, float]] = []
        for s in w.ships.values():
            if not s.exists or not 0.0 < s.self_destruct <= 5.0:
                continue
            if s.side == self.side:
                x, y = s.x, s.y
            else:
                c = self.contact(s.id)
                if c is None:
                    continue
                x, y = c.x, c.y
            from .systems.power import warp_budget

            energy = warp_budget(s) / rules.destruct_divisor + s.cls.destruct
            out.append((s.id, x, y, s.self_destruct, energy * rules.splash_mult * rules.splash_radius_per_damage))
        return out

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
                    t.target if mine else None, count=t.salvo, faction=_make(w, t.owner),
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
                    p.code if mine else "", p.fuse if mine else 0.0, faction=_make(w, p.owner),
                ))
            self._ordnance = out
        return self._ordnance

    def threats(self) -> list[OrdnanceView]:
        return [o for o in self.ordnance() if not o.friendly]

    # ------------------------------------------------------------- what a crew can see for itself

    def pending_scan(self, ship_id: int) -> PendingScan | None:
        """The scan one of our own ships has under way, if any."""
        own = self.own(ship_id)
        return self._w.pending_scan(ship_id) if own is not None else None

    def repairs(self, ship_id: int) -> tuple[set[str], bool]:
        """What the repair crews on one of our ships are working on now, and whether the hull is among it."""
        from .systems.repair import under_repair

        own = self.own(ship_id)
        return under_repair(self._w, own) if own is not None else (set(), False)

    def our_boarders(self, ship_id: int) -> int:
        """How many of our people are fighting aboard another ship (they report in)."""
        s = self._w.ships.get(ship_id)
        return s.boarders if s is not None and s.boarders > 0 and s.boarder_side == self.side else 0

    def name_of(self, ship_id: int) -> str:
        """A ship as this side knows her: her name if she is ours or identified, else her contact number."""
        own = self._w.ships.get(ship_id)
        if own is not None and own.side == self.side:
            return own.name
        c = self.contact(ship_id)
        if c is not None and c.identified:
            return c.label.split(" (")[0]
        return f"#{ship_id}"

    def fate(self, ship_id: int) -> str:
        """'alive', 'surrendered' or 'gone' for a ship this side has seen (an outcome everyone can see)."""
        s = self._w.ships.get(ship_id)
        if s is None or not s.exists:
            return "gone"
        if s.status == ShipStatus.SURRENDERED:
            return "surrendered"
        return "alive" if s.alive else "gone"

    def demeanour(self, ship_id: int) -> str:
        """How an enemy captain's mood shows in how they fight, as our officers read it: '' when nothing shows."""
        from .systems import disposition

        s = self._w.ships.get(ship_id)
        if s is None or not s.exists or s.side == self.side or not self._w.is_visible(self.side, ship_id):
            return ""
        if s.status == ShipStatus.SURRENDERED:
            return "surrendered"
        return "withdrawing" if s.mood.terms else (disposition.shows(s) or "")

    def read_captain(self, ship_id: int, by: int) -> Reading | None:
        """Our officers' read of an enemy captain (resolve, fear, anger), as one of our ships sees them."""
        from .systems.disposition import reading

        me, s = self.own(by), self._w.ships.get(ship_id)
        if me is None or s is None or not s.alive or s.side == self.side:
            return None
        return reading(self._w, me, s)

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
