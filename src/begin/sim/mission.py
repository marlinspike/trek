"""Missions: a battle with a goal beyond holding the field [E].

A battle may carry one mission. The battle still ends the old way, when one side holds the field; the mission is
a second question the battle answers, and Starfleet's assessment judges both (session/assessment.py).

Three kinds:

* **rescue**: a stricken ship of ours (the *ward*) can't move and has people aboard. Any of our ships within
  transporter range of her, with the shield facing her lowered, takes people off every cycle (the same rule
  `transport` uses). The people ride in the rescuing ship (`Ship.evacuees`) and die with her. A deadline, if set,
  is when the ward is lost with whoever is still aboard.
* **escort**: the ward sails for a point at her own speed. She must get there; then she goes to warp.
* **intercept**: one enemy ship (the *runner*) makes for the edge on a set heading. She must not escape.

Hunters: some enemy ships are given the ward as their ordered target (the lever `tell <ally> attack` pulls for
our own ships), so the ward is in real danger. When she is gone, they fight as usual.

A ward is not a combatant: she doesn't hold the field, doesn't escape by distance, and doesn't count as one of a
tour stop's friends.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from ..core.angles import bearing
from .allies import AllyStanding
from .events import Message, Tone
from .ship import ShipStatus

if TYPE_CHECKING:
    from .world import World

KINDS = ("rescue", "escort", "intercept")
RESCUE_RATE = 0.06            # share of a transporter's lift (beam_cap) each working transporter moves a cycle
ARRIVE_RANGE = 1500.0         # an escorted ship this close to her destination has made it
SUCCESS_SHARE = 0.75          # a rescue that saves this share of the people counts as a success


@dataclass(frozen=True)
class MissionDef:
    """A mission as written in a tour stop, a preset or a patrol."""

    kind: str
    title: str = ""                          # what the HUD calls it: "Protect the Tamar Kessel"
    ward: str = "federation.tn"              # rescue/escort: the class of the ship to save
    ward_name: str = ""
    at: tuple[float, float] = (0.0, 0.0)     # rescue/escort: where the ward starts
    people: int = 0                          # rescue: people aboard
    deadline: float = 0.0                    # rescue: cycles until she is lost (0: none)
    to: tuple[float, float] = (0.0, 0.0)     # escort: her destination
    runner: int = 0                          # intercept: which enemy ship runs (index in the enemy list)
    heading: float = 0.0                     # intercept: the runner's course
    runner_pace: float = 0.6                 # intercept: her best warp as a share of our fastest ship's (laden, nursing her drives)
    hunters: int = 1                         # rescue/escort: enemy ships that go for the ward
    flag: str = ""                           # a tour flag set when the mission succeeds
    calls: int = 0                           # on a tour: Starfleet reinforcement calls earned by success
    resupply: float = 0.0                    # on a tour: share of a full magazine the squadron gets back on success

    def __post_init__(self) -> None:
        if self.kind not in KINDS:
            raise ValueError(f"Unknown mission kind '{self.kind}' (expected one of {', '.join(KINDS)}).")

    @staticmethod
    def from_dict(d: dict[str, Any]) -> MissionDef:
        def pair(key: str) -> tuple[float, float]:
            v = d.get(key, (0.0, 0.0))
            return (float(v[0]), float(v[1]))

        return MissionDef(
            kind=str(d["kind"]), title=str(d.get("title", "")), ward=str(d.get("ward", "federation.tn")),
            ward_name=str(d.get("ward_name", "")), at=pair("at"), people=int(d.get("people", 0)),
            deadline=float(d.get("deadline", 0.0)), to=pair("to"), runner=int(d.get("runner", 0)), runner_pace=float(d.get("runner_pace", 0.6)),
            heading=float(d.get("heading", 0.0)), hunters=int(d.get("hunters", 1)), flag=str(d.get("flag", "")),
            calls=int(d.get("calls", 0)), resupply=float(d.get("resupply", 0.0)))

    def heading_title(self, ward: str = "", runner: str = "") -> str:
        """The goal as the HUD shows it."""
        if self.title:
            return self.title
        if self.kind == "rescue":
            return f"Rescue the crew of the {ward or 'stricken ship'}"
        if self.kind == "escort":
            return f"Protect the {ward or 'convoy'}"
        return f"Stop the {runner or 'runner'} before she escapes"


@dataclass
class Mission:
    """A mission under way in one battle (`World.mission`)."""

    spec: MissionDef
    side: int                                # the side the mission belongs to (the player's)
    ward_id: int | None = None
    runner_id: int | None = None
    hunter_ids: list[int] = field(default_factory=list)
    aboard: int = 0                          # rescue: people still on the ward
    rescued: int = 0                         # rescue: people taken off the ward
    lost: int = 0                            # rescue: people who died aboard the ward
    lost_carried: int = 0                    # rescue: people who died with the ship that took them off
    state: str = "open"                      # "open" | "done" | "failed"
    reason: str = ""                         # how it ended, in a sentence
    beaming: bool = False                    # rescue: someone was taking people off this cycle
    blocked: str = ""                        # rescue: why nobody is beaming, when someone is close ("shield")
    started_at: float = 0.0
    ended_at: float = -1.0
    carriers: dict[int, int] = field(default_factory=dict)   # rescue: ship id -> people aboard her
    fraction: dict[int, float] = field(default_factory=dict)  # rescue: part-people carried between steps
    told: set[str] = field(default_factory=set)               # one-time messages already given
    after_battle: int = 0                    # rescue: people taken off once the enemy was gone (not under fire)
    runner_warp: float | None = None         # intercept: the best warp the runner can make (she carries the news, not a fight)

    @property
    def kind(self) -> str:
        return self.spec.kind

    @property
    def open(self) -> bool:
        return self.state == "open"

    @property
    def saved(self) -> int:
        """People safe: taken off and still alive."""
        return max(0, self.rescued - self.lost_carried)

    @property
    def dead(self) -> int:
        """Everyone the rescue lost, aboard the ward or with the ship that carried them."""
        return self.lost + self.lost_carried

    def time_left(self, now: float) -> float | None:
        """Rescue: cycles before the ward is lost (None without a deadline)."""
        if self.spec.kind != "rescue" or self.spec.deadline <= 0:
            return None
        return max(0.0, self.started_at + self.spec.deadline - now)

    def share_saved(self) -> float:
        total = self.spec.people
        return self.saved / total if total > 0 else 0.0

    def succeeded(self) -> bool:
        return self.state == "done"


# ------------------------------------------------------------------ setting it up

def install(world: World, spec: MissionDef, side: int, enemy_ids: list[int]) -> Mission:
    """Put the mission into a freshly built battle: the ward, the runner's orders, the hunters."""
    m = Mission(spec, side, started_at=world.time)
    if spec.kind in ("rescue", "escort"):
        x, y = spec.at
        course = bearing(spec.to[0] - x, spec.to[1] - y) if spec.kind == "escort" else 0.0
        ward = world.add_ship(spec.ward, side, x, y, course=course, warp=0.0, name=spec.ward_name or None)
        ward.ward = True
        ward.hold_fire = True
        m.ward_id = ward.id
        if spec.kind == "rescue":
            m.aboard = spec.people
            ward.desired_warp = 0.0
            world.ally_orders[ward.id] = AllyStanding(movement="stop", hold_fire=True, issued=world.tick)
        else:
            world.ally_orders[ward.id] = AllyStanding(movement="course", move_value=course, hold_fire=True,
                                                      issued=world.tick)
        # the hunters: the enemy ships nearest her, as many as the mission says
        live = [world.ships[i] for i in enemy_ids if i in world.ships]
        live.sort(key=lambda s: math.hypot(s.x - x, s.y - y))
        for s in live[: max(0, spec.hunters)]:
            world.ally_orders[s.id] = AllyStanding(target=ward.id, issued=world.tick)
            m.hunter_ids.append(s.id)
    else:
        if enemy_ids:
            rid = enemy_ids[min(max(0, spec.runner), len(enemy_ids) - 1)]
            m.runner_id = rid
            world.ally_orders[rid] = AllyStanding(movement="course", move_value=spec.heading % 360.0,
                                                  issued=world.tick)
            runner = world.ships[rid]
            runner.desired_course = spec.heading % 360.0
            ours = [s.cls.max_warp for s in world.ships.values() if s.side == side and s.alive and not s.cls.is_base]
            if ours and spec.runner_pace > 0:
                m.runner_warp = max(1.0, max(ours) * spec.runner_pace)
    world.mission = m
    return m


# ------------------------------------------------------------------ each step

def update_mission(world: World, dt: float) -> None:
    """Run the mission one step: beam people across, steer the convoy, and see whether it is won or lost."""
    m = world.mission
    if m is None or not m.open:
        return
    if m.kind == "rescue":
        _rescue(world, m, dt)
    elif m.kind == "escort":
        _escort(world, m)
    else:
        _intercept(world, m)
    _carriers_lost(world, m)


def _say(world: World, text: str, tone: Tone, side: int | None = None) -> None:
    world.emit(Message(world.tick, text, tone, speaker="Mission",
                       visible_to=None if side is None else frozenset({side})))


def _finish(world: World, m: Mission, state: str, reason: str, tone: Tone) -> None:
    m.state = state
    m.reason = reason
    m.ended_at = world.time
    _say(world, reason, tone, m.side)


def _rescue(world: World, m: Mission, dt: float) -> None:
    ward = world.ships.get(m.ward_id) if m.ward_id is not None else None
    if ward is None or not ward.exists or ward.side != m.side or ward.status != ShipStatus.ACTIVE:
        if m.aboard > 0:
            m.lost += m.aboard
            name = ward.name if ward is not None else "the ship"
            who = f"{m.aboard} people still aboard" if m.aboard != 1 else "one person still aboard"
            m.aboard = 0
            _close_rescue(world, m, f"The {name} is lost with {who}.")
        return
    ward.desired_warp = 0.0
    left = m.time_left(world.time)
    if left is not None and left <= 0 and m.aboard > 0:
        m.lost += m.aboard
        n = m.aboard
        m.aboard = 0
        world.destroy_ship(ward, "her reactor failed")
        _close_rescue(world, m, f"The {ward.name}'s reactor has failed. {n} people were still aboard.")
        return
    from .systems.damage import relative_bearing_from

    m.beaming = False
    m.blocked = ""
    for s in world.ships.values():
        if not s.alive or s.side != m.side or s.id == ward.id or s.ward or s.cls.craft:
            continue
        working = sum(1 for t in s.transporters if not t.destroyed)
        if working <= 0:
            continue
        d = math.hypot(ward.x - s.x, ward.y - s.y)
        if d > world.rules.beam_range:
            continue
        own = s.shield_for_bearing(relative_bearing_from(s, ward.x, ward.y))
        if own is not None and own.effective > 0:
            m.blocked = "shield"
            continue
        rate = working * s.cls.beam_cap * RESCUE_RATE * dt
        take = min(m.aboard, _whole(m, s.id, rate))
        if take <= 0:
            m.beaming = True
            continue
        m.aboard -= take
        m.rescued += take
        s.evacuees += take
        m.carriers[s.id] = m.carriers.get(s.id, 0) + take
        m.beaming = True
    if m.beaming:
        m.blocked = ""
        if "beaming" not in m.told:
            m.told.add("beaming")
            _say(world, f"Transporter rooms are taking people off the {ward.name}: {m.aboard} still aboard.", Tone.GOOD,
                 m.side)
    elif m.blocked == "shield" and "shield" not in m.told:
        m.told.add("shield")
        _say(world, f"We are in transporter range of the {ward.name}. Lower the shield facing her to beam her people "
                    "across.", Tone.CAUTION, m.side)
    if left is not None and m.aboard > 0 and left <= 30 and "late" not in m.told:
        m.told.add("late")
        _say(world, f"The {ward.name}'s reactor will fail in {left:.0f} cycles. {m.aboard} people are still aboard.",
             Tone.ALERT, m.side)
    if m.aboard <= 0:
        _close_rescue(world, m, "")


def _whole(m: Mission, ship_id: int, amount: float) -> int:
    """People come across whole: carry the fraction from step to step."""
    acc = m.fraction.get(ship_id, 0.0) + amount
    n = int(acc)
    m.fraction[ship_id] = acc - n
    return n


def _close_rescue(world: World, m: Mission, lead: str) -> None:
    saved = m.saved
    total = m.spec.people
    if total <= 0:
        return
    if saved >= total:
        _finish(world, m, "done", (lead + " " if lead else "") + f"All {total} people are safe aboard.", Tone.GOOD)
    elif saved >= total * SUCCESS_SHARE:
        _finish(world, m, "done", (lead + " " if lead else "") + f"{saved} of {total} people were saved.", Tone.GOOD)
    else:
        _finish(world, m, "failed", (lead + " " if lead else "") + f"{saved} of {total} people were saved.",
                Tone.ALERT)


def _escort(world: World, m: Mission) -> None:
    ward = world.ships.get(m.ward_id) if m.ward_id is not None else None
    if ward is None or ward.status in (ShipStatus.DESTROYED, ShipStatus.DERELICT):
        _finish(world, m, "failed", f"The {ward.name if ward else 'convoy'} has been destroyed.", Tone.ALERT)
        return
    if ward.side != m.side or ward.status in (ShipStatus.SURRENDERED, ShipStatus.CAPTURED):
        _finish(world, m, "failed", f"The {ward.name} has been taken.", Tone.ALERT)
        return
    tx, ty = m.spec.to
    d = math.hypot(tx - ward.x, ty - ward.y)
    if d <= ARRIVE_RANGE:
        world.escape_ship(ward, f"The {ward.name} has reached safety and gone to warp.")
        _finish(world, m, "done", f"The {ward.name} is safe.", Tone.GOOD)
        return
    st = world.ally_orders.get(ward.id)
    course = bearing(tx - ward.x, ty - ward.y)
    if st is not None and st.movement == "course":
        st.move_value = course          # keep her pointed at the destination as she weaves


def _intercept(world: World, m: Mission) -> None:
    r = world.ships.get(m.runner_id) if m.runner_id is not None else None
    if r is None:
        return
    if m.runner_warp is not None and r.alive and r.desired_warp > m.runner_warp:
        r.desired_warp = m.runner_warp
        r.warp = min(r.warp, m.runner_warp)
    if r.status == ShipStatus.ESCAPED:
        _finish(world, m, "failed", f"The {r.name} has escaped.", Tone.ALERT)
    elif r.status in (ShipStatus.DESTROYED, ShipStatus.DERELICT):
        _finish(world, m, "done", f"The {r.name} will not get away.", Tone.GOOD)
    elif r.status == ShipStatus.SURRENDERED or r.side == m.side:
        _finish(world, m, "done", f"The {r.name} is ours.", Tone.GOOD)
    elif r.alive and not r.can_move():
        _finish(world, m, "done", f"The {r.name} is dead in space: she can't run.", Tone.GOOD)


def _carriers_lost(world: World, m: Mission) -> None:
    """People rescued die with the ship that carried them."""
    for sid, n in list(m.carriers.items()):
        s = world.ships.get(sid)
        if s is not None and (s.status in (ShipStatus.DESTROYED, ShipStatus.DERELICT) or s.side != m.side):
            m.lost_carried += n
            m.carriers.pop(sid)
            s.evacuees = 0


def battle_over(world: World) -> None:
    """The battle has ended: settle the mission. If our side holds the field, whoever is still waiting is safe."""
    m = world.mission
    if m is None or not m.open:
        return
    ours = world.outcome.winner == m.side
    if m.kind == "rescue":
        ward = world.ships.get(m.ward_id) if m.ward_id is not None else None
        if ours and ward is not None and ward.alive and m.aboard > 0:
            n = m.aboard
            m.aboard = 0
            m.rescued += n
            m.after_battle = n
            _close_rescue(world, m, f"With the enemy gone, the last {n} were taken off.")
        elif m.aboard > 0:
            m.lost += m.aboard
            m.aboard = 0
            _close_rescue(world, m, f"We had to leave the {ward.name if ward else 'ship'}.")
        else:
            _close_rescue(world, m, "")
    elif m.kind == "escort":
        ward = world.ships.get(m.ward_id) if m.ward_id is not None else None
        if ours and ward is not None and ward.alive:
            _finish(world, m, "done", f"With the enemy gone, the {ward.name} goes on her way.", Tone.GOOD)
        else:
            _finish(world, m, "failed", f"The {ward.name if ward else 'convoy'} did not get through.", Tone.ALERT)
    else:
        r = world.ships.get(m.runner_id) if m.runner_id is not None else None
        if r is not None and r.side != m.side and r.alive and r.can_move() and not ours:
            _finish(world, m, "failed", f"The {r.name} is still out there.", Tone.ALERT)
        else:
            _finish(world, m, "done", f"The {r.name if r else 'runner'} did not get away.", Tone.GOOD)


__all__ = ["KINDS", "Mission", "MissionDef", "battle_over", "install", "update_mission"]
