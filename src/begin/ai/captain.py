"""AI captain: Begin 2.0's decoded ship AI, adapted to real time [R + E].

The decision tree follows the reconstruction (fireflyk64 AI_AND_COMBAT.md
and `ai/behavior.rs`): reflexes, morale, target scoring with distance
bands, phaser and torpedo fire discipline, weapon-dominance maneuvering
(phaser range vs torpedo standoff with weaving) and temperature panic.

Remake additions [E]:
* it sees only its side's `Observation` (fog of war, stale tracks, cloaks);
* layered cadence: reflexes every couple of ticks, tactics at the crew's
  reaction cadence, strategy (target choice, morale) once a cycle;
* captain competence and creativity gate subsystem targeting, shield
  reinforcement and probe use; doctrine biases weapons, focus and surrender;
* every decision is written to a trace.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Iterable

from ..core.angles import ang_dist, bearing, norm360
from ..core.rng import Rng
from ..sim.commands import (
    Authority, Command, ConfigureAutoload, Dock, FirePhasers, FireTorpedoes, LaunchProbe, ReinforceShield,
    SelectTarget, SelfDestruct, SetCloak, SetHelm, SetShields, Surrender, Tractor, Transport,
)
from ..sim.allies import DEFAULT_APPROACH_RANGE, DEFAULT_ESCORT_RANGE, DEFEND_RANGE, AllyStanding
from ..sim.observation import ContactView, Observation
from ..sim.ship import Ship
from ..sim.systems.phasers import bank_bears, bank_ready
from .computer import torpedo_envelope
from .personality import Personality
from .trace import Trace

# decoded constants [R] (constants.rs)
AI_DISTANCE_BANDS = (3.0, 1.9, 1.75, 1.5, 1.4, 1.3, 1.2, 1.15, 1.125, 1.1)
AI_SCORE_BAND_WIDTH = 2000.0
AI_FAR_BAND_MULT = 0.5
AI_TARGET_STICKINESS = 1.25
AI_STALE_CONTACT_MULT = 0.1
AI_PHASER_SPREAD = 10.0
AI_FF_TOLERANCE = 5.0
AI_AGGR_FIRE_BIAS = 0.1
AI_RETREAT_DAMAGE = 0.75
AI_RETREAT_RECOVER = 0.5
AI_TEMP_PANIC_ENTER = 0.85
AI_TEMP_PANIC_EXIT = 0.4
AI_TEMP_NORM_BASE = 12.0
AI_TEMP_NORM_RANGE = 28.0
AI_APPROACH_CONE = 10.0
AI_APPROACH_WARP_AGGR = 4.0
AI_JINK_LEAD_OFFSET = 20.0
AI_WEAVE_THREAT_RANGE = 25000.0
AI_WEAVE_DIST_DIV = 833.33
AI_WEAVE_AMP_MAX = 31.0
AI_WEAVE_AGGR_BASE = 1.1
AI_SIDESTEP = 90.0
AI_STANDOFF_OPEN_ANGLE = 70.0     # [E] degrees off dead astern when opening to torpedo standoff
AI_FANATIC_RAM = 0.9
AI_BATTERY_CRAWL = 0.25
STRENGTH_DIVISOR = 1000.0


def strength(banks: int, bank_range: float, tubes: int) -> float:
    return 1.0 + banks * bank_range / STRENGTH_DIVISOR + tubes * 6.0


@dataclass
class AICaptain:
    ship_id: int
    side: int
    personality: Personality
    rng: Rng
    period: int = 2
    phase: int = 0
    trace: Trace = field(default_factory=Trace)

    target: int | None = None
    retreating: bool = False
    overheat_latch: bool = False
    weave_side: float = 1.0
    last_tactics: int = -999
    last_strategy: int = -999
    last_helm: tuple[float, float] | None = None
    autoload_set_for: int | None = None
    last_shield_reinforce: int | None = None
    last_stand: bool = False
    order_seen: int = -1
    order_done: bool = False   # the current movement order has been carried out (tow delivered, party beamed)

    # ------------------------------------------------------------ entry

    def think(self, obs: Observation) -> Iterable[Command]:
        ship = obs.own(self.ship_id)
        if ship is None or not ship.alive or ship.crew <= 0:
            return []
        out: list[Command] = []
        tpc = obs.rules.ticks_per_cycle
        if obs.tick - self.last_strategy >= tpc:
            self.last_strategy = obs.tick
            out.extend(self._strategy(obs, ship))
        if obs.tick - self.last_tactics >= self.personality.reaction_ticks:
            self.last_tactics = obs.tick
            out.extend(self._tactics(obs, ship))
        return out

    def _cmd(self, cls: type[Command], ship: Ship, **kw: object) -> Command:
        return cls(ship_id=ship.id, issuer=Authority.AI_CAPTAIN, source=f"Captain {ship.captain}".strip(), **kw)  # type: ignore[arg-type]

    def _log(self, obs: Observation, text: str) -> None:
        self.trace.add(obs.tick, text)

    # ------------------------------------------------------------ strategy: morale and target

    def damage_ratio(self, ship: Ship) -> float:
        """[R] 1 − current fighting strength / design strength (crew counts ×4)."""
        cls = ship.cls
        op_banks = sum(1 for b in ship.banks if b.intact)
        op_tubes = sum(1 for t in ship.tubes if t.intact)
        now = 1.0 + op_banks * cls.banks_range / STRENGTH_DIVISOR + op_tubes * 6.0 + ship.crew / max(1, cls.crew) * 4.0
        mx = 1.0 + cls.banks * cls.banks_range / STRENGTH_DIVISOR + cls.tubes * 6.0 + 4.0
        hull = 1.0 - max(0.0, ship.structure) / max(1.0, ship.structure_max)
        return max(0.0, 1.0 - now / mx, hull * 0.9)  # [E] structural damage also counts

    def _strategy(self, obs: Observation, ship: Ship) -> list[Command]:
        out: list[Command] = []
        p = self.personality
        dmg = self.damage_ratio(ship)
        threshold = p.bravery * AI_RETREAT_DAMAGE * p.doctrine.retreat_threshold_scale
        if not self.retreating and dmg > threshold:
            self.retreating = True
            self._log(obs, f"morale broken: damage {dmg:.2f} > {threshold:.2f}; retreating")
        st = obs.ally_order(ship.id)
        if st is not None and st.movement == "run":
            self.retreating = True  # told to run: never rejoins until the order is cancelled
        elif self.retreating and dmg < p.bravery * AI_RETREAT_RECOVER:
            self.retreating = False
            self._log(obs, "recovered nerve; re-engaging")

        # last stand: fanatics (and crippled ships of a self-destruct doctrine) blow themselves up
        if (not self.last_stand and ship.self_destruct < 0 and dmg > 0.8
                and (p.fanaticism > AI_FANATIC_RAM or (not ship.can_move() and
                     self.rng.unit() < 0.02 * p.doctrine.self_destruct))):
            self.last_stand = True
            self._log(obs, "last stand: self-destruct and ram")
            out.append(self._cmd(SelfDestruct, ship, cycles=6.0))

        # surrender when beaten and unable to run
        if (self.retreating and not ship.can_move() and dmg > 0.7 and not self.last_stand
                and self.rng.unit() < 0.05 * p.doctrine.surrender_willingness * (1.0 - p.bravery * 0.5)):
            self._log(obs, "striking colours")
            out.append(self._cmd(Surrender, ship))
            return out

        # target choice
        forced = st.target if st is not None else None
        if st is not None and st.movement == "defend" and st.move_target is not None:
            ward = obs.own(st.move_target)
            if ward is not None:
                near = [c for c in obs.hostile_contacts() if c.visible]
                if near:
                    forced = min(near, key=lambda c: c.distance_to(ward.x, ward.y)).id
        best, best_score = None, 0.0
        for c in obs.hostile_contacts():
            if c.side is not None and c.side == self.side:
                continue
            s = self._score(obs, ship, c)
            if forced is not None and c.id == forced:
                s *= 100.0
            if s > best_score:
                best, best_score = c, s
        new_target = best.id if best is not None else None
        if new_target != self.target:
            self._log(obs, f"target -> {best.label if best else 'none'} (score {best_score:.1f})")
            self.target = new_target
        if self.target is not None and ship.target != self.target:
            sub = self._subsystem_choice(obs, ship, best)
            out.append(self._cmd(SelectTarget, ship, target=self.target, subsystem=sub))
        # proximity tuned to the target's agility [R]: min(max warp × 50, design max)
        if best is not None and best.cls is not None and ship.tubes and self.autoload_set_for != best.id:
            spec = obs.content.torpedoes.get(ship.tubes[0].load_ordnance or ship.cls.torpedo)
            if spec is not None:
                prox = max(obs.rules.prox_floor, min(best.cls.max_warp * 50.0, spec.max_prox))
                out.append(self._cmd(ConfigureAutoload, ship, weapon="tube", prox=prox))
                self.autoload_set_for = best.id
        return out

    def _score(self, obs: Observation, ship: Ship, c: ContactView) -> float:
        """Begin's target score [R]: threat strength × distance band × modifiers."""
        if c.cls is not None:
            sc = c.scan
            banks = sc.charged_banks if sc is not None else c.cls.banks
            tubes = sc.loaded_tubes if sc is not None else c.cls.tubes
            st = strength(banks, c.cls.banks_range, tubes)
        else:
            st = strength(4, 2000.0, 2)
        d = c.distance_to(ship.x, ship.y)
        band = int(d // AI_SCORE_BAND_WIDTH)
        mult = AI_DISTANCE_BANDS[band] if band < len(AI_DISTANCE_BANDS) else 1.0
        if d >= 20000:
            mult *= AI_FAR_BAND_MULT
        score = st * mult
        if d < ship.cls.banks_range:
            score *= 2.0
        if c.id == self.target:
            score *= AI_TARGET_STICKINESS
        if any(o.friendly and o.kind == "probe" and o.target == c.id for o in obs.ordnance()):
            score *= 0.5
        if not c.visible:
            score *= AI_STALE_CONTACT_MULT
        # doctrine: focus on the side's common target
        focus = self.personality.doctrine.focus_fire
        if any(s.target == c.id for s in obs.own_ships() if s.id != ship.id):
            score *= 1.0 + 0.5 * focus
        return score

    def _subsystem_choice(self, obs: Observation, ship: Ship, c: ContactView | None) -> str | None:
        """Competent captains of disabling doctrines aim at weapons or engines [E]."""
        p = self.personality
        if c is None or not p.doctrine.prefers_disabling:
            return None
        if p.competence < 0.55 or self.rng.unit() > p.creativity + 0.2:
            return None
        return "weapons" if self.rng.unit() < 0.6 else "propulsion"

    # ------------------------------------------------------------ tactics

    def _tactics(self, obs: Observation, ship: Ship) -> list[Command]:
        out: list[Command] = []
        c = obs.contact(self.target) if self.target is not None else None
        st = obs.ally_order(ship.id)
        if st is not None and st.issued != self.order_seen:
            self.order_seen = st.issued
            self.order_done = False
            self.last_helm = None
        hold_fire = st is not None and st.hold_fire
        # a running ship still uses its weapons while an enemy is in range (manual p. 23)
        if c is not None and not hold_fire:
            out.extend(self._weapons(obs, ship, c, st))
        out.extend(self._shields(obs, ship, c))
        out.extend(self._cloak(obs, ship, c))
        handled = False
        if st is not None:
            handled = self._standing_orders(obs, ship, c, st, out)
        if not handled:
            helm = self._maneuver(obs, ship, c, st)
            if helm is not None:
                out.append(helm)
        return out

    def _friendly_blocks(self, obs: Observation, ship: Ship, brg: float, rng_: float, tol: float) -> bool:
        for s in obs.own_ships():
            if s.id == ship.id:
                continue
            d = math.hypot(s.x - ship.x, s.y - ship.y)
            if d < rng_ and ang_dist(bearing(s.x - ship.x, s.y - ship.y), brg) < tol:
                return True
        return False

    def _weapons(self, obs: Observation, ship: Ship, c: ContactView, st: AllyStanding | None = None) -> list[Command]:
        p = self.personality
        out: list[Command] = []
        d = c.distance_to(ship.x, ship.y)
        brg = bearing(c.x - ship.x, c.y - ship.y)

        # phasers [R]: aggressive captains wait for an alpha strike, timid ones fire half now
        if ship.banks and d < ship.cls.banks_range:
            charged = [i for i, b in enumerate(ship.banks) if bank_ready(ship, b) and b.role.value != "defense"
                       and bank_bears(ship, b, brg)]
            op = [i for i, b in enumerate(ship.banks) if b.intact and b.enabled and b.role.value != "defense"
                  and bank_bears(ship, b, brg)]
            if charged and not self._friendly_blocks(obs, ship, brg, ship.cls.banks_range, AI_FF_TOLERANCE):
                n = 0
                if self.rng.unit() + AI_AGGR_FIRE_BIAS <= p.aggression:
                    if len(charged) == len(op):
                        n = len(charged)
                else:
                    n = (len(charged) + 1) // 2
                # snap fire: exactly enough to break a scanned shield (competent captains) [R]
                n = self._snap_count(obs, ship, c, charged, n)
                if n > 0:
                    spread = AI_PHASER_SPREAD if p.competence > 0.35 else 30.0
                    out.append(self._cmd(FirePhasers, ship, banks=tuple(charged[:n]), target=c.id, spread=spread))
                    self._log(obs, f"phasers x{n} at {c.label} ({d:,.0f})")

        # torpedoes [R]: inside the envelope, volley sized by torpedo pressure
        loaded = [i for i, t in enumerate(ship.tubes) if t.loaded is not None]
        if loaded:
            spec = obs.content.torpedoes[ship.tubes[loaded[0]].loaded.ordnance]  # type: ignore[union-attr]
            lo, hi = torpedo_envelope(ship, c.x, c.y, c.vx, c.vy, spec.velocity, spec.arm_time,
                                      spec.max_time_fuse, obs.rules.units_per_warp)
            if lo <= d <= hi * (0.6 + 0.3 * p.competence):
                pressure = obs.torpedo_pressure(c.id)
                op_tubes = sum(1 for t in ship.tubes if t.intact)
                tmax = c.cls.max_warp if c.cls is not None else 6.0
                if self.rng.unit() < 0.1:
                    volley = 0
                elif op_tubes == 1 or spec.homing:
                    volley = 1
                elif tmax < 2.0 or pressure < 30 or pressure > 80:
                    volley = op_tubes
                elif pressure > 60:
                    volley = 0 if self.rng.unit() < 0.35 else 1
                else:
                    volley = op_tubes // 2
                tol = (12.0 + (AI_JINK_LEAD_OFFSET if pressure > 80 else 0.0)) / 2.0
                volley = min(volley, len(loaded))  # fire what is loaded rather than wait for a full volley
                if volley > 0 and not self._friendly_blocks(obs, ship, brg, hi, tol):
                    fan = AI_JINK_LEAD_OFFSET if (pressure > 80 and not spec.homing and volley > 1) else 0.0
                    out.append(self._cmd(FireTorpedoes, ship, tubes=tuple(loaded[:volley]), target=c.id, fan=fan))
                    self._log(obs, f"torpedoes x{volley} at {c.label} ({d:,.0f}, pressure {pressure:.0f})")

        # probes [R]: launch when the target is slow or has no charged banks; doctrine scales use
        loaded_p = [i for i, lch in enumerate(ship.launchers) if lch.loaded is not None]
        if loaded_p:
            pspec = obs.content.probes[ship.launchers[loaded_p[0]].loaded.ordnance]  # type: ignore[union-attr]
            reach = pspec.velocity * obs.rules.units_per_warp * pspec.max_time_fuse * 0.7
            chasing = sum(1 for o in obs.ordnance() if o.friendly and o.kind == "probe" and o.target == c.id)
            slow = c.cls is not None and c.cls.max_warp < pspec.velocity
            sc = c.scan
            no_banks = sc is not None and sc.charged_banks == 0
            want = (d < reach and chasing <= p.aggression * 6 and
                    (no_banks or (slow and self.rng.unit() < p.doctrine.probe_use * (0.5 + p.creativity) * 0.25)))
            if st is not None and st.weapon == "probe":
                # ordered to probe: release only with a good chance of a hit (manual p. 24)
                want = chasing == 0 and (d < reach * 0.4 or (slow and d < reach * 0.7))
            if want and pspec.damage > 0:
                out.append(self._cmd(LaunchProbe, ship, launchers=(loaded_p[0],), target=c.id))
                self._log(obs, f"probe at {c.label}")
        return out

    def _snap_count(self, obs: Observation, ship: Ship, c: ContactView, charged: list[int], n: int) -> int:
        """Fire exactly enough banks to break the facing shield, if a scan says how strong it is."""
        if c.scan is None or c.cls is None or self.personality.competence < 0.5:
            return n
        rel = norm360(bearing(ship.x - c.x, ship.y - c.y) - c.course)
        facings = (0.0, 60.0, 300.0, 120.0, 240.0, 180.0)
        k = min(range(len(facings)), key=lambda i: ang_dist(rel, facings[i]))
        if k >= len(c.scan.shields):
            return n
        sh = c.scan.shields[k]
        if sh < 0:
            return max(n, 1)  # shield down: any hit goes through
        capacity = c.cls.shield_strength * sh / 100.0
        d = c.distance_to(ship.x, ship.y)
        per = ship.cls.banks_charge * (45.0 / AI_PHASER_SPREAD) * math.sqrt(max(0.0, 1.0 - d / ship.cls.banks_range)) * 0.5
        if per <= 0:
            return n
        need = int(capacity // per) + 1
        if need <= len(charged):
            return need
        return n

    # ------------------------------------------------------------ shields and cloak

    def _shields(self, obs: Observation, ship: Ship, c: ContactView | None) -> list[Command]:
        p = self.personality
        if c is None or not ship.shields or p.competence < 0.5:
            return []
        if ship.power.shields_starved:
            return []
        if ship.battery_charge() < ship.battery_capacity() * 0.4:
            if self.last_shield_reinforce is not None:
                self.last_shield_reinforce = None
                return [self._cmd(ReinforceShield, ship, sector=None)]
            return []
        rel = norm360(bearing(c.x - ship.x, c.y - ship.y) - ship.course)
        sh = ship.shield_for_bearing(rel)
        if sh is None or sh.destroyed:
            return []
        d = c.distance_to(ship.x, ship.y)
        if d < ship.cls.banks_range * 2.5 and self.last_shield_reinforce != sh.index:
            self.last_shield_reinforce = sh.index
            return [self._cmd(ReinforceShield, ship, sector=sh.index)]
        return []

    def _cloak(self, obs: Observation, ship: Ship, c: ContactView | None) -> list[Command]:
        if ship.cloak is None or not ship.cloak.intact or self.personality.doctrine.cloak_ambush <= 0:
            return []
        if c is None:
            return []
        d = c.distance_to(ship.x, ship.y)
        loaded = any(t.loaded is not None for t in ship.tubes)
        # Romulan habit: cloak while closing or reloading, decloak to strike
        want = (d > ship.cls.banks_range * 2.0 and not loaded) or self.retreating
        if want and not ship.cloaked and self.rng.unit() < self.personality.doctrine.cloak_ambush:
            self._log(obs, "cloaking")
            return [self._cmd(SetCloak, ship, on=True)]
        if ship.cloaked and loaded and not self.retreating:
            spec = obs.content.torpedoes.get(ship.tubes[0].load_ordnance or ship.cls.torpedo)
            if spec is not None:
                _, hi = torpedo_envelope(ship, c.x, c.y, c.vx, c.vy, spec.velocity, spec.arm_time,
                                         spec.max_time_fuse, obs.rules.units_per_warp)
                if d < hi * 0.7:
                    self._log(obs, "decloaking to strike")
                    return [self._cmd(SetCloak, ship, on=False)]
        return []

    # ------------------------------------------------------------ standing orders from the flagship

    def _position_of(self, obs: Observation, sid: int | None) -> tuple[float, float, float, float] | None:
        """(x, y, course, warp) of an own ship or a contact, as this side knows it."""
        if sid is None:
            return None
        s = obs.own(sid)
        if s is not None:
            return s.x, s.y, s.course, s.warp
        c = obs.contact(sid)
        if c is not None:
            return c.x, c.y, c.course, c.warp
        return None

    def _keep_range(self, obs: Observation, ship: Ship, pos: tuple[float, float, float, float], want: float,
                    slack: float = 1000.0) -> Command | None:
        """Close to / open to `want` from a point, then match its course and speed (escort rule, manual p. 23)."""
        x, y, crs, w = pos
        d = math.hypot(x - ship.x, y - ship.y)
        brg = bearing(x - ship.x, y - ship.y)
        speed = self.combat_speed(ship, obs)
        if d > want + slack:
            return self._helm(obs, ship, brg, speed)
        if d < want - slack:
            return self._helm(obs, ship, brg + 180.0, max(1.0, min(speed, w + 1.0)))
        return self._helm(obs, ship, crs, max(0.0, min(speed, w)))

    def _standing_orders(self, obs: Observation, ship: Ship, c: ContactView | None, st: AllyStanding,
                         out: list[Command]) -> bool:
        """Carry out the flagship's movement order. Returns True when it decided the helm."""
        rules = obs.rules
        # a base told to recover a ship brings it aboard once it is alongside
        if st.recover is not None:
            guest = obs.own(st.recover)
            if guest is not None and guest.docked_to is None and \
                    math.hypot(guest.x - ship.x, guest.y - ship.y) <= rules.dock_range:
                out.append(Dock(ship_id=guest.id, host=ship.id, issuer=Authority.AI_CAPTAIN, source=f"{ship.name} recovery"))
        m = st.movement
        if m is None or m == "run" or ship.cls.is_base or not ship.can_move():
            return False  # run is handled by the normal retreat behaviour
        speed = self.combat_speed(ship, obs)
        if m == "stop":
            out.extend(filter(None, [self._helm(obs, ship, ship.desired_course, 0.0)]))
            return True
        if m == "course":
            base = st.move_value or 0.0
            threat = min((h.distance_to(ship.x, ship.y) for h in obs.hostile_contacts() if h.visible), default=1e9)
            torps = any(not o.friendly for o in obs.ordnance())
            if threat < AI_WEAVE_THREAT_RANGE or torps:
                cmd = self._weave(obs, ship, base, threat)  # zig-zag around the course for self-defence
            else:
                cmd = self._helm(obs, ship, base, speed)
            out.extend(filter(None, [cmd]))
            return True
        if m == "withdraw":
            near = [h for h in obs.hostile_contacts() if h.visible]
            if not near:
                out.extend(filter(None, [self._helm(obs, ship, ship.desired_course, 0.0)]))
                return True
            h = min(near, key=lambda k: k.distance_to(ship.x, ship.y))
            d = h.distance_to(ship.x, ship.y)
            reach = 12000.0
            if h.cls is not None and h.cls.tubes > 0:
                spec = obs.content.torpedoes.get(h.cls.torpedo)
                if spec is not None:
                    reach = spec.velocity * rules.units_per_warp * (spec.arm_time + spec.max_time_fuse)
            brg = bearing(h.x - ship.x, h.y - ship.y)
            if d < reach * 1.1:
                cmd = self._weave(obs, ship, brg + 180.0, d)
            elif d > reach * 1.5:
                cmd = self._helm(obs, ship, brg, speed)
            else:
                cmd = self._helm(obs, ship, brg, 0.0)  # in reserve, facing the enemy
            out.extend(filter(None, [cmd]))
            return True
        pos = self._position_of(obs, st.move_target)
        if pos is None:
            return False  # lost the ship: fight on normally
        d = math.hypot(pos[0] - ship.x, pos[1] - ship.y)
        if m == "escort":
            out.extend(filter(None, [self._keep_range(obs, ship, pos, st.move_value or DEFAULT_ESCORT_RANGE)]))
            return True
        if m == "defend":
            out.extend(filter(None, [self._keep_range(obs, ship, pos, DEFEND_RANGE, 600.0)]))
            return True
        if m == "approach":
            out.extend(filter(None, [self._keep_range(obs, ship, pos, st.move_value or DEFAULT_APPROACH_RANGE, 400.0)]))
            return True
        if m == "dock":
            if ship.docked_to == st.move_target:
                return True
            if d <= rules.dock_range * 0.9:
                out.extend(filter(None, [self._helm(obs, ship, ship.course, 0.0)]))
                out.append(self._cmd(Dock, ship, host=st.move_target))
            else:
                out.extend(filter(None, [self._keep_range(obs, ship, pos, rules.dock_range * 0.5, rules.dock_range * 0.3)]))
            return True
        if m in ("tractor", "tow"):
            if ship.tractor_target != st.move_target:
                if self.order_done:
                    out.extend(filter(None, [self._helm(obs, ship, ship.course, 0.0)]))
                    return True
                if d <= rules.tractor_range * 0.8:
                    out.append(self._cmd(Tractor, ship, target=st.move_target))
                out.extend(filter(None, [self._keep_range(obs, ship, pos, rules.tractor_range * 0.5, rules.tractor_range * 0.25)]))
                return True
            if m == "tractor":
                out.extend(filter(None, [self._helm(obs, ship, ship.course, 0.0)]))
                return True
            dest = self._position_of(obs, st.destination)
            if dest is None:
                return False
            dd = math.hypot(dest[0] - ship.x, dest[1] - ship.y)
            if dd < 3000.0:
                out.append(self._cmd(Tractor, ship, target=None))
                self.order_done = True
                return True
            out.extend(filter(None, [self._helm(obs, ship, bearing(dest[0] - ship.x, dest[1] - ship.y), min(speed, 3.0))]))
            return True
        if m == "board":
            if self.order_done:
                return False  # party away: carry on fighting
            t = obs.contact(st.move_target) if st.move_target is not None else None
            if t is None:
                return False
            if d <= rules.beam_range * 0.8:
                from ..sim.systems.damage import relative_bearing_from

                own = ship.shield_for_bearing(relative_bearing_from(ship, t.x, t.y))
                if own is not None and own.up:
                    out.append(self._cmd(SetShields, ship, sectors=(own.index,), up=False))
                else:
                    party = min(st.party, max(0, ship.crew - 6))
                    if party > 0:
                        out.append(self._cmd(Transport, ship, target=t.id, count=party))
                    out.append(self._cmd(SetShields, ship, sectors=None, up=True))
                    self.order_done = True
                out.extend(filter(None, [self._helm(obs, ship, bearing(t.x - ship.x, t.y - ship.y), max(1.0, t.warp))]))
            else:
                out.extend(filter(None, [self._helm(obs, ship, bearing(t.x - ship.x, t.y - ship.y), speed)]))
            return True
        return False

    # ------------------------------------------------------------ maneuver

    def combat_speed(self, ship: Ship, obs: Observation) -> float:
        """[R] max warp × drive health × efficiency, with temperature panic hysteresis."""
        maxw = ship.max_attainable_warp
        cap = ship.battery_capacity()
        if maxw <= 1.0 or (cap > 0 and ship.battery_charge() / cap < AI_BATTERY_CRAWL):
            return min(1.0, maxw)
        max_dmg = max((d.damage for d in ship.drives), default=0)
        w = maxw * (100 - max_dmg) / 100.0 * ship.cls.warp_efficiency
        max_temp = max((d.temp for d in ship.drives if not d.destroyed), default=12.0)
        norm = (max_temp - AI_TEMP_NORM_BASE) / AI_TEMP_NORM_RANGE
        if norm > AI_TEMP_PANIC_ENTER:
            self.overheat_latch = True
        if self.overheat_latch:
            if norm < AI_TEMP_PANIC_EXIT:
                self.overheat_latch = False
            else:
                w *= 0.5 if norm > AI_TEMP_PANIC_ENTER else 0.9
        return max(1.0, w)

    def _helm(self, obs: Observation, ship: Ship, course: float, warp: float) -> Command | None:
        course = norm360(course)
        warp = max(0.0, warp)
        if self.last_helm is not None and ang_dist(self.last_helm[0], course) < 2 and abs(self.last_helm[1] - warp) < 0.2:
            return None
        self.last_helm = (course, warp)
        return self._cmd(SetHelm, ship, course=course, warp=warp)

    def _weave(self, obs: Observation, ship: Ship, base: float, d: float) -> Command | None:
        """[R] weave around a base bearing; amplitude grows as the attacker gets closer."""
        self.weave_side = -self.weave_side
        amp = 0.0
        if d < AI_WEAVE_THREAT_RANGE:
            cap = (AI_WEAVE_AGGR_BASE - self.personality.aggression) * max(0.0, AI_WEAVE_AMP_MAX - d / AI_WEAVE_DIST_DIV)
            amp = self.rng.uniform(0.0, max(0.0, cap))
        course = norm360(base + self.weave_side * amp)
        warp = self.combat_speed(ship, obs)
        turn = ang_dist(ship.course, course)
        cur = max(1.0, abs(ship.warp))
        if turn > (ship.cls.w1turn / cur) * 2.0:
            warp = max(1.0, min(warp, ship.cls.w1turn * 2.0 / turn))
        return self._helm(obs, ship, course, warp)

    def _maneuver(self, obs: Observation, ship: Ship, c: ContactView | None,
                  st: AllyStanding | None = None) -> Command | None:
        if ship.cls.is_base or not ship.can_move() or ship.docked_to is not None:
            return None
        if c is None:
            # wander [R]: hold course at cruise, occasionally sidestep
            turn = 0.0
            if self.rng.unit() < 0.05:
                turn = AI_SIDESTEP if self.rng.unit() < 0.5 else -AI_SIDESTEP
            return self._helm(obs, ship, ship.desired_course + turn, ship.cls.cruise_warp)
        d = c.distance_to(ship.x, ship.y)
        brg = bearing(c.x - ship.x, c.y - ship.y)
        if self.retreating:
            return self._weave(obs, ship, brg + 180.0, d)
        if self.last_stand:
            return self._helm(obs, ship, brg, ship.max_attainable_warp)  # ram

        p = self.personality
        bias = p.doctrine.weapon_bias
        my_ph = strength(sum(1 for b in ship.banks if b.intact), ship.cls.banks_range, 0) - 1.0
        armed = ship.torps_remaining > 0  # magazine empty: the last loads go when they bear, but close for phasers
        my_tp = sum(1 for t in ship.tubes if t.intact) * 6.0 if armed else 0.0  # out of torpedoes: close for phasers
        if c.cls is not None:
            their_ph = c.cls.banks * c.cls.banks_range / STRENGTH_DIVISOR
            their_tp = c.cls.tubes * 6.0
        else:
            their_ph, their_tp = 8.0, 12.0
        ph_dom = 0.0 if my_ph <= 0 else (1000.0 if their_ph <= 0 else my_ph / their_ph) * bias.get("phaser", 1.0)
        tp_dom = 0.0 if my_tp <= 0 else (1000.0 if their_tp <= 0 else my_tp / their_tp) * bias.get("torpedo", 1.0)
        weapon = st.weapon if st is not None else None
        if weapon == "probe" and ship.launchers:
            pspec = obs.content.probes.get(ship.launchers[0].load_ordnance or ship.cls.probe)
            if pspec is not None:
                reach = pspec.velocity * obs.rules.units_per_warp * pspec.max_time_fuse * 0.4
                return self._weave(obs, ship, brg if d > reach else brg + 90.0 * self.weave_side, d)
        if weapon == "phaser":
            ph_dom, tp_dom = max(ph_dom, 1.0) * 1000.0, tp_dom
        elif weapon == "torpedo":
            ph_dom, tp_dom = ph_dom, max(tp_dom, 1.0) * 1000.0

        if ph_dom > 0 and ph_dom > tp_dom:
            rng_ = ship.cls.banks_range
            if d < rng_:
                rel = norm360(brg - ship.course)
                sh = ship.shield_for_bearing(rel)
                if sh is None or sh.effective < AI_APPROACH_CONE:
                    return self._helm(obs, ship, self.rng.uniform(0, 360), self.combat_speed(ship, obs))  # jink
                return self._helm(obs, ship, brg, c.warp + 1.0)
            if d > rng_ * 2.0:
                return self._weave(obs, ship, brg, d)
            return self._helm(obs, ship, brg, c.warp + p.aggression * AI_APPROACH_WARP_AGGR)
        if tp_dom > 0:
            spec = obs.content.torpedoes.get(ship.tubes[0].load_ordnance or ship.cls.torpedo) if ship.tubes else None
            if spec is not None:
                lo, hi = torpedo_envelope(ship, c.x, c.y, c.vx, c.vy, spec.velocity, spec.arm_time,
                                          spec.max_time_fuse, obs.rules.units_per_warp)
                standoff = lo + (1.0 - p.aggression) * (hi - lo) * 0.6
                if d < standoff:
                    # open the range obliquely, not straight away: running dead astern only invites a chase
                    side = 1.0 if ship.id % 2 else -1.0
                    return self._weave(obs, ship, brg + 180.0 - side * AI_STANDOFF_OPEN_ANGLE, d)
                return self._weave(obs, ship, brg, d)
        return self._helm(obs, ship, ship.course, 0.0)  # helpless: full stop


__all__ = ["AICaptain", "strength"]
