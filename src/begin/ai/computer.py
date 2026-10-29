"""The ship's computer: point defense and assisted/automatic fire control.

It runs for every ship, player and AI alike, at the computer authority
level, so a captain's explicit order always wins. Sophistication buys
concrete capabilities rather than combat bonuses:

* reaction time before a new threat is engaged,
* how far ahead it predicts a threat's closest approach,
* how precisely it lays a defensive beam on a small target,
* how well it judges a good offensive shot for assisted/automatic mounts.

Everything it knows comes from the side's `Observation`.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from ..core.angles import ang_dist, bearing, norm360
from ..core.rng import Rng
from ..sim.commands import Authority, Command, FirePhasers, FireTorpedoes
from ..sim.observation import Observation, OrdnanceView
from ..sim.ship import BankRole, FireMode, PDDoctrine, Ship
from ..sim.systems.phasers import bank_bears, bank_origin, bank_ready
from .trace import Trace


@dataclass
class ThreatTrack:
    first_seen: int
    engaged: int = 0


@dataclass
class ShipComputer:
    ship_id: int
    side: int
    rng: Rng
    period: int = 1
    phase: int = 0
    tracks: dict[int, ThreatTrack] = field(default_factory=dict)
    trace: Trace = field(default_factory=lambda: Trace(limit=60))
    last_offense_tick: int = -999

    def think(self, obs: Observation) -> Iterable[Command]:
        ship = obs.own(self.ship_id)
        if ship is None or not ship.alive or ship.crew <= 0:
            return []
        out: list[Command] = []
        out.extend(self._point_defense(obs, ship))
        if obs.tick - self.last_offense_tick >= 5:
            out.extend(self._fire_control(obs, ship))
        return out

    # ---------------------------------------------------------------- defense

    def _reaction_ticks(self, ship: Ship, obs: Observation) -> int:
        soph = ship.sophistication
        return int(round((0.15 + (1.0 - soph) * 1.2) * obs.rules.ticks_per_cycle))

    def _horizon(self, ship: Ship) -> float:
        """Cycles of look-ahead for closest-approach prediction."""
        return 0.8 + 2.2 * ship.sophistication

    def _danger(self, ship: Ship, o: OrdnanceView, obs: Observation) -> tuple[float, float] | None:
        """(time to closest approach, miss distance) if this threat will pass within its fuse range."""
        r = math.radians(o.course)
        vx, vy = math.sin(r) * o.speed, math.cos(r) * o.speed
        svx, svy = ship.velocity(obs.rules.units_per_warp)
        rx, ry = o.x - ship.x, o.y - ship.y
        dvx, dvy = vx - svx, vy - svy
        dv2 = dvx * dvx + dvy * dvy
        t = 0.0 if dv2 < 1e-9 else max(0.0, -(rx * dvx + ry * dvy) / dv2)
        if t > self._horizon(ship):
            return None
        mx, my = rx + dvx * t, ry + dvy * t
        miss = math.hypot(mx, my)
        if o.kind == "probe" and o.target is not None:
            miss = 0.0  # homing
        if miss > o.prox * 1.15 + 50:
            return None
        return t, miss

    def _point_defense(self, obs: Observation, ship: Ship) -> list[Command]:
        doctrine = ship.pd_doctrine
        if doctrine == PDDoctrine.OFF or not ship.banks:
            self.tracks.clear()
            return []
        threats = obs.threats()
        live = {o.id for o in threats}
        for k in [k for k in self.tracks if k not in live]:
            del self.tracks[k]
        react = self._reaction_ticks(ship, obs)
        rng_ = ship.cls.banks_range
        cands: list[tuple[float, OrdnanceView]] = []
        for o in threats:
            d = math.hypot(o.x - ship.x, o.y - ship.y)
            if d > rng_ * 1.6:
                continue
            tr = self.tracks.setdefault(o.id, ThreatTrack(obs.tick))
            if obs.tick - tr.first_seen < react:
                continue
            danger = self._danger(ship, o, obs)
            if danger is None or d > rng_ * 0.95:
                continue
            t, _ = danger
            if doctrine == PDDoctrine.CONSERVATIVE and t > 0.8:
                continue
            cands.append((t, o))
        if not cands:
            return []
        cands.sort(key=lambda c: c[0])
        allowed_roles = {BankRole.DEFENSE}
        if doctrine in (PDDoctrine.BALANCED, PDDoctrine.AGGRESSIVE):
            allowed_roles.add(BankRole.FLEX)
        if doctrine == PDDoctrine.AGGRESSIVE:
            allowed_roles.add(BankRole.OFFENSE)
        reserved_exist = any(b.role == BankRole.DEFENSE and b.intact for b in ship.banks)
        if doctrine == PDDoctrine.CONSERVATIVE and not reserved_exist and cands[0][0] < 0.5:
            allowed_roles.add(BankRole.FLEX)  # nothing reserved: one flex bank against an imminent hit
        out: list[Command] = []
        used: set[int] = set()
        for t, o in cands:
            soph = ship.sophistication
            brg_true = bearing(o.x - ship.x, o.y - ship.y)
            for i, b in enumerate(ship.banks):
                if i in used or not bank_ready(ship, b) or b.role not in allowed_roles:
                    continue
                # balanced doctrine keeps flex banks for offense unless the threat is serious
                if (doctrine == PDDoctrine.BALANCED and b.role == BankRole.FLEX and reserved_exist
                        and o.yield_ < 8 and t > 0.6):
                    continue
                ox, oy = bank_origin(ship, b)
                brg = bearing(o.x - ox, o.y - oy)
                if not bank_bears(ship, b, brg):
                    continue
                if math.hypot(o.x - ox, o.y - oy) >= rng_ * 0.97:
                    continue
                aim = norm360(brg + self.rng.gauss(0.0, (1.0 - soph) * 4.0))
                spread = 10.0 + (1.0 - soph) * 12.0
                if ang_dist(aim, brg) > spread / 2:
                    spread = min(45.0, ang_dist(aim, brg) * 2 + 4)
                if self._friendly_in_cone(obs, ship, ox, oy, aim, spread, math.hypot(o.x - ox, o.y - oy)):
                    continue
                used.add(i)
                out.append(FirePhasers(ship_id=ship.id, banks=(i,), at_bearing=aim, spread=spread, defensive=True,
                                       issuer=Authority.COMPUTER, source="point defense"))
                self.trace.add(obs.tick, f"PD: bank {i + 1} at {o.kind} {o.id} (t={t:.1f}c)")
                if doctrine == PDDoctrine.CONSERVATIVE and not reserved_exist:
                    return out
                break
        return out

    @staticmethod
    def _friendly_in_cone(obs: Observation, ship: Ship, ox: float, oy: float, aim: float, spread: float, reach: float) -> bool:
        for s in obs.own_ships():
            if s.id == ship.id:
                continue
            d = math.hypot(s.x - ox, s.y - oy)
            if d < reach + 300 and ang_dist(bearing(s.x - ox, s.y - oy), aim) < spread / 2 + 3:
                return True
        return False

    # ---------------------------------------------------------------- offense

    def _fire_control(self, obs: Observation, ship: Ship) -> list[Command]:
        modes_b = {b.fire_mode for b in ship.banks}
        modes_t = {t.fire_mode for t in ship.tubes}
        if FireMode.ASSISTED not in modes_b | modes_t and FireMode.AUTOMATIC not in modes_b | modes_t:
            return []
        holds = obs.holds(ship.id)
        out: list[Command] = []
        target = ship.target
        auto_target = target
        if auto_target is None or obs.contact(auto_target) is None:
            hostile = [c for c in obs.hostile_contacts() if c.visible]
            if hostile:
                auto_target = min(hostile, key=lambda c: c.distance_to(ship.x, ship.y)).id
        soph = ship.sophistication
        # phasers: fire when the shot is good (well inside range, all chosen banks charged)
        for mode, tgt in ((FireMode.ASSISTED, target), (FireMode.AUTOMATIC, auto_target)):
            if tgt is None or "phasers" in holds:
                continue
            c = obs.contact(tgt)
            if c is None:
                continue
            banks = tuple(i for i, b in enumerate(ship.banks)
                          if b.fire_mode == mode and b.role != BankRole.DEFENSE and bank_ready(ship, b))
            if not banks:
                continue
            d = c.distance_to(ship.x, ship.y)
            good = ship.cls.banks_range * (0.45 + 0.35 * soph)
            if d > good:
                continue
            bearing_ok = tuple(i for i in banks
                               if bank_bears(ship, ship.banks[i], bearing(c.x - ship.x, c.y - ship.y)))
            if not bearing_ok:
                continue
            spread = 10.0 if d < ship.cls.banks_range * 0.5 else 20.0
            out.append(FirePhasers(ship_id=ship.id, banks=bearing_ok, target=tgt, spread=spread,
                                   issuer=Authority.COMPUTER, source=f"fire control ({mode.value})"))
            self.trace.add(obs.tick, f"FC: phasers {','.join(str(i + 1) for i in bearing_ok)} at {c.label} ({d:,.0f})")
            self.last_offense_tick = obs.tick
        # torpedoes: fire inside the torpedo envelope
        for mode, tgt in ((FireMode.ASSISTED, target), (FireMode.AUTOMATIC, auto_target)):
            if tgt is None or "torpedoes" in holds:
                continue
            c = obs.contact(tgt)
            if c is None:
                continue
            tubes = tuple(i for i, t in enumerate(ship.tubes) if t.fire_mode == mode and t.loaded is not None)
            if not tubes:
                continue
            spec = obs.content.torpedoes[ship.tubes[tubes[0]].loaded.ordnance]  # type: ignore[union-attr]
            lo, hi = torpedo_envelope(ship, c.x, c.y, c.vx, c.vy, spec.velocity, spec.arm_time, spec.max_time_fuse,
                                      obs.rules.units_per_warp)
            d = c.distance_to(ship.x, ship.y)
            if not (lo <= d <= hi * (0.35 + 0.3 * soph)):
                continue
            # magazine discipline: wait for the full salvo and don't pile onto torpedoes already inbound
            mode_tubes = [t for t in ship.tubes if t.fire_mode == mode and t.intact]
            if len(tubes) < len(mode_tubes) or obs.torpedo_pressure(tgt) > 25:
                continue
            out.append(FireTorpedoes(ship_id=ship.id, tubes=tubes, target=tgt, issuer=Authority.COMPUTER,
                                     source=f"fire control ({mode.value})"))
            self.trace.add(obs.tick, f"FC: torpedoes at {c.label} ({d:,.0f})")
            self.last_offense_tick = obs.tick
        return out


def torpedo_envelope(
    ship: Ship, tx: float, ty: float, tvx: float, tvy: float, v_torp: float, arm: float, fuse: float, upw: float
) -> tuple[float, float]:
    """Begin's firing envelope [R]: closing = v_torp + v_tgt·cos(angle); min = arm·closing, max = (arm+fuse)·closing."""
    rx, ry = tx - ship.x, ty - ship.y
    d = math.hypot(rx, ry) or 1.0
    # target speed component toward us (positive = closing)
    v_toward = -(tvx * rx + tvy * ry) / d
    closing = v_torp * upw + v_toward
    if closing <= 0:
        return (0.0, 0.0)
    return arm * closing, (arm + fuse) * closing


__all__ = ["ShipComputer", "torpedo_envelope"]
