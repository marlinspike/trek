"""How an officer meets a standing objective, such as "disable their shields" [E].

`sim/objectives.py` records what the captain asked for; this module is the
officer's plan, run every time the crew thinks. It only issues ordinary
commands at OFFICER authority, so anything the captain orders still wins for
a while, then the officer carries on.

Disabling, Seven's way:

- keep a fresh scan of each ship, because that is how she knows it worked;
- target the chosen systems (she leaves the helm to the captain or the helm officer);
- fire aimed phasers whenever banks are charged and bear;
- fire torpedoes as one full salvo from just outside arming range, so the
  enemy's point defense has little time to react and too many rounds to
  stop, each round fused to burst on a ring around where the target will
  be, so a dodge in any direction still lands inside a blast;
- when two targets are close together, burst torpedoes between them so one
  salvo hits both;
- if a target cloaks, hunt it with the deflector pulse or tachyon detector.

To add a goal: write a planner `(Planner, obs, ship, objective) -> list[Command]`
and register it in `PLANNERS`.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..sim.commands import (
    Authority, Command, EndObjective, FireAtPoint, FireBait, FirePhasers, Scan, SelectTarget,
)
from ..sim.objectives import Objective
from ..sim.observation import ContactView, Observation
from ..sim.ship import TARGETABLE_GROUPS, Ship
from ..sim.systems.phasers import bank_bears_point, bank_ready

if TYPE_CHECKING:
    from .officers import OfficerBrain

# share of a group's systems that must be off line: every weapon, for a ship to be harmless; most shield
# generators, since a ship with two of six shields left can only cover a third of its hull
DISABLED_SHARE: dict[str, float] = {"shields": 0.66}
SCAN_STALE = 8.0         # cycles before a target's scan is too old to judge by
DONE_SCAN_AGE = 4.0      # the scan that confirms success must be this fresh


def group_state(c: ContactView | None, group: str) -> tuple[int, int] | None:
    """(systems in the group, how many are knocked out) from our latest scan; None if never scanned."""
    if c is None or c.scan is None:
        return None
    kinds = {k.value for k in TARGETABLE_GROUPS[group]}
    hits = [dmg for sid, dmg in c.scan.subsystems.items() if sid.rstrip("0123456789") in kinds]
    if not hits:
        return (0, 0)
    return len(hits), sum(1 for d in hits if d > 0)   # a damaged system is off line until repaired


def baitable(obs: Observation, c: ContactView) -> bool:
    """Will this ship's point defense spend several banks on a lone torpedo? Judged from what Seven
    knows: its race's habits, and from a scan, how many of its crew are left [E]."""
    if c.cls is None:
        return False
    faction = obs.content.factions.get(c.cls.faction)
    discipline = faction.pd_discipline if faction is not None else 0.7
    if c.scan is not None:
        discipline *= 0.5 + 0.5 * max(0.0, min(1.0, c.scan.crew / max(1, c.cls.crew)))
    return discipline < 0.6


def disabled(c: ContactView | None, group: str) -> bool:
    st = group_state(c, group)
    return st is not None and st[0] > 0 and st[1] >= math.ceil(st[0] * DISABLED_SHARE.get(group, 1.0) - 1e-9)


@dataclass
class Planner:
    """One officer's working state for the objectives they hold."""

    officer_id: str
    title: str
    last_scan: dict[int, int] = field(default_factory=dict)
    last_volley: int = -10 ** 9

    def _cmd(self, cls: type[Command], ship: Ship, **kw: object) -> Command:
        return cls(ship_id=ship.id, issuer=Authority.OFFICER, source=self.title, **kw)  # type: ignore[arg-type]

    def think(self, obs: Observation, ship: Ship, brain: OfficerBrain | None) -> list[Command]:
        out: list[Command] = []
        for o in list(ship.objectives):
            if (o.officer or "") not in ("", self.officer_id):
                continue
            plan = PLANNERS.get(o.goal)
            if plan is not None:
                out.extend(plan(self, obs, ship, o, brain))
        return out


def _alive(obs: Observation, tid: int) -> bool:
    """Still in the fight as far as we know: lost contacts count, destroyed or escaped ships don't."""
    return tid not in obs.gone()


def plan_disable(p: Planner, obs: Observation, ship: Ship, o: Objective, brain: OfficerBrain | None) -> list[Command]:
    rules = obs.rules
    tpc = rules.ticks_per_cycle
    contacts = {t: obs.contact(t) for t in o.targets}
    alive = [t for t in o.targets if _alive(obs, t)]
    destroy = o.goal == "destroy"
    aim = None if destroy else o.group
    if not alive:
        if destroy:
            return [p._cmd(EndObjective, ship, group=o.group, outcome="done")]
        return [p._cmd(EndObjective, ship, group=o.group, outcome="impossible",
                       reason="none of them are left to disable")]
    if not ship.weapons_operational():
        return [p._cmd(EndObjective, ship, group=o.group, outcome="impossible", reason="we have no working weapons")]
    remaining = alive if destroy else [t for t in alive if not disabled(contacts[t], o.group)]
    fresh = all(contacts[t] is not None and contacts[t].scan is not None  # type: ignore[union-attr]
                and obs.tick - contacts[t].scan.tick <= DONE_SCAN_AGE * tpc for t in alive)  # type: ignore[union-attr]
    if not remaining and fresh:
        return [p._cmd(EndObjective, ship, group=o.group, outcome="done")]

    out: list[Command] = []
    # science: keep the scans fresh, the stalest first (one scan at a time)
    reach_scan = ship.sensor_range() * rules.scan_range_fraction
    if not any(obs.tick - t < 3 * tpc for t in p.last_scan.values()):
        stale = []
        for t in alive:
            c = contacts[t]
            if c is None or not c.visible or c.distance_to(ship.x, ship.y) > reach_scan:
                continue
            age = (obs.tick - c.scan.tick) / tpc if c.scan is not None else 10 ** 6
            if age > (DONE_SCAN_AGE if t not in remaining else SCAN_STALE):
                stale.append((-age, t))
        if stale:
            _, t = min(stale)
            p.last_scan[t] = obs.tick
            out.append(p._cmd(Scan, ship, target=t))

    if not remaining:
        return out   # waiting on a confirming scan
    visible = [t for t in remaining if contacts[t] is not None and contacts[t].visible]  # type: ignore[union-attr]
    if not visible:
        # every target out of sight: if they cloaked, Spock and Seven know how to find them
        if brain is not None:
            out.extend(brain._collaborate(obs, ship))
        return out
    primary = min(visible, key=lambda t: contacts[t].distance_to(ship.x, ship.y))  # type: ignore[union-attr]
    c = contacts[primary]
    assert c is not None
    d = c.distance_to(ship.x, ship.y)

    # tactical: the chosen systems on the nearest target
    if ship.target != primary or ship.target_subsystem != aim:
        out.append(p._cmd(SelectTarget, ship, target=primary, subsystem=aim))
    # she leaves the helm to whoever has it: the captain, or the helm officer
    bank_range = ship.cls.banks_range
    # phasers, tightly focused for accuracy
    if ship.banks and d < bank_range:
        ready = tuple(i for i, b in enumerate(ship.banks) if bank_ready(ship, b) and b.role.value != "defense"
                      and bank_bears_point(ship, b, c.x, c.y))
        if ready:
            out.append(p._cmd(FirePhasers, ship, banks=ready, target=primary, subsystem=aim, spread=10.0))
    # torpedoes, burst where point defense won't expect them
    shot = _torpedo_shot(p, obs, ship, o, primary, [t for t in visible if t != primary])
    if shot is not None:
        out.append(shot)
    return out


def _torpedo_shot(p: Planner, obs: Observation, ship: Ship, o: Objective, primary: int,
                  others: list[int]) -> Command | None:
    rules = obs.rules
    tpc = rules.ticks_per_cycle
    loaded = [t for t in ship.tubes if t.loaded is not None and t.intact and t.enabled
              and not obs.content.torpedoes[t.loaded.ordnance].special]
    usable = [t for t in ship.tubes if t.intact and t.enabled]
    # a full salvo saturates point defense; don't dribble single rounds
    if not loaded or len(loaded) < max(1, len(usable) // 2) or obs.tick - p.last_volley < 3 * tpc:
        return None
    spec = obs.content.torpedoes[loaded[0].loaded.ordnance]  # type: ignore[union-attr]
    speed = spec.velocity * rules.units_per_warp
    reach = speed * (spec.arm_time + spec.max_time_fuse) * 0.9
    blast_r = spec.damage * rules.splash_mult * rules.splash_radius_per_damage
    c = obs.contact(primary)
    if c is None or blast_r <= 0:
        return None
    destroy = o.goal == "destroy"
    if not destroy and c.scan is not None and c.scan.structure_frac < 0.3:
        return None   # the asked-for job is to disable it, not to finish it off: phasers only from here
    if ship.pending_volley is not None:
        return None   # a bait volley is under way

    def lead(cv: ContactView, t: float) -> tuple[float, float]:
        return cv.x + cv.vx * t, cv.y + cv.vy * t

    d_now = c.distance_to(ship.x, ship.y)
    # close enough that the target can't wander far while the salvo flies, far enough for it to arm
    if d_now > min(reach, speed * (spec.arm_time + 1.5)) or d_now < speed * spec.arm_time * 1.15:
        return None
    tof = d_now / speed
    px, py = lead(c, tof)
    tof = math.hypot(px - ship.x, py - ship.y) / speed
    px, py = lead(c, tof)

    # a ring of bursts around the predicted position covers a dodge in any direction; each burst is
    # close enough to hurt (blast damage falls off with the square root of distance)
    ring = blast_r * 0.45
    prox = max(rules.prox_floor, ring * 0.8)   # a round passing nearer the hull than its burst point goes off early
    point, spread = (px, py), ring
    # a second target close enough that bursts between them hit both
    for other in others:
        oc = obs.contact(other)
        if oc is None:
            continue
        ox, oy = lead(oc, tof)
        gap = math.hypot(ox - px, oy - py)
        if 2 * ring < gap < blast_r * 1.6:
            point, spread = ((px + ox) / 2, (py + oy) / 2), min(ring, gap / 4)
            break
    paired = point != (px, py)
    # a lone, trigger-happy target: one torpedo to draw its point defense, the rest while its banks recharge
    if not paired and len(loaded) >= 3 and speed * spec.arm_time * 1.3 < d_now < reach * 0.8 and baitable(obs, c):
        p.last_volley = obs.tick
        return p._cmd(FireBait, ship, target=primary, subsystem=None if destroy else o.group)
    d = math.hypot(point[0] - ship.x, point[1] - ship.y)
    if d > reach or d < speed * spec.arm_time * 1.1:
        return None
    # don't catch ourselves or a friend in the blast
    for s in obs.own_ships():
        if math.hypot(s.x - point[0], s.y - point[1]) < blast_r + spread + 100:
            return None
    p.last_volley = obs.tick
    return p._cmd(FireAtPoint, ship, x=point[0], y=point[1], prox=prox, target=primary,
                  subsystem=None if destroy else o.group, spread=spread)


Plan = Callable[[Planner, Observation, Ship, Objective, "OfficerBrain | None"], list[Command]]
PLANNERS: dict[str, Plan] = {"disable": plan_disable, "destroy": plan_disable}


__all__ = ["PLANNERS", "Planner", "baitable", "disabled", "group_state", "plan_disable"]
