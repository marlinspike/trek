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
* every decision is written to a trace;
* it fights to its ship's strengths (`smart`): it weighs its own banks, tubes,
  warheads and shields against the target's, closes for phasers only when that
  is the better trade (or the target's shields or hull are gone), keeps a torpedo
  boat outside the target's phaser reach, stays out of a stronger enemy's reach
  when it is the faster ship, and turns a fresh shield toward the enemy when the
  one facing it fails.

Fighting as a force [E] (`smart`):
* captains prefer a target their scans show is already badly hurt, and leave a
  base for last while it still has mobile defenders close by;
* a second ship closing on a target its shipmate is already fighting comes in
  on the flank, so the two of them hit different shields;
* a damaged ship with a friendly base on the field docks to repair, then
  rejoins the fight;
* when nobody has landed a hit for a long while, the stronger side presses
  the attack and the weaker one leaves, so fights end instead of stalling.
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
from ..sim.systems.phasers import bank_bears_point, bank_ready
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
AI_KNIFE_FIGHT_RANGE = 1.5       # [E] × phaser range: inside it, fight rather than reopen the range
AI_BASE_STANDOFF = 0.6           # [E] × phaser range: the closest an attacker comes to a base
AI_STANDOFF_OPEN_ANGLE = 70.0     # [E] degrees off dead astern when opening to torpedo standoff
AI_FANATIC_RAM = 0.9
# fighting to the ship's strengths [E]
AI_KITE_MARGIN = 1.3             # × an enemy's phaser range: a torpedo boat keeps at least this far out
AI_SHIELD_BACK_OFF = 35.0        # % effective on the shield facing the enemy: below it, turn a fresh one toward it
# [E] an ally told (through the flagship's own orders) to disable a ship, not destroy her: Federation captains always
# obey; others when loyal and disciplined enough, on average, to put the flagship's wishes before a kill
ALLY_OBEY = 0.6
ALLY_DISABLE_TORPEDO_HULL = 0.5   # as our own officers: below half her hull, torpedoes would tear her apart
AI_CLOSE_HYSTERESIS = 1.15       # closing needs odds this much better than standing off, and the reverse
AI_TORP_HIT = 0.45               # rough chance a torpedo connects; homing ones more often
AI_TORP_HIT_HOMING = 0.7
AI_BATTERY_CRAWL = 0.25
# fighting as a force [E]
AI_DOCK_DAMAGE = 0.45            # damage ratio (or hull lost) at which a ship goes to a friendly base to repair
AI_UNDOCK_HULL = 0.9             # hull fraction a docked ship waits for before rejoining
AI_UNDOCK_SYSTEMS = 30           # % damage left on any weapon, drive or shield before it rejoins
AI_HOME_RANGE = 12000.0          # a ship with a friendly base fights within this of it, under its guns
AI_LULL_RANGE = 25000.0          # no enemy this close: a lull, time to dock and repair
AI_STALL_CYCLES = 100.0          # cycles with no damage done or taken by anyone on our side: the fight has stalled
AI_PRESS_EDGE = 0.8              # our strength / theirs at or above which a stalled side presses the attack
AI_FLANK_ANGLE = 40.0            # degrees off the direct bearing for the second ship on a target
AI_HURT_BONUS = 1.0              # target score × (1 + this × structure lost), from scans
AI_BASE_SCREENED = 0.5           # × score of a base while its mobile defenders are close by
AI_SCREEN_RANGE = 10000.0
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
    smart: bool = True         # [E] fight to the ship's strengths; False keeps Begin's weapon-dominance rule alone
    docking: bool = False      # [E] on the way to (or docked at) a friendly base for repairs
    pressing: bool = False     # [E] the fight stalled and we are the stronger side: close and finish it
    withdrawing: bool = False  # [E] the fight stalled and we are the weaker side: leave the field
    stall_mark: float = -1.0
    stall_since: int = 0
    wishes: tuple[frozenset[int], dict[int, str]] = (frozenset(), {})   # the flagship's: spared, and disabling

    def obeys_flagship(self, ship: Ship) -> bool:
        """Will this captain hold back from a kill because the flagship wants the ship disabled? [E]"""
        if ship.cls.faction == "federation":
            return True
        p = self.personality
        return (p.loyalty + p.discipline) / 2.0 >= ALLY_OBEY

    def _flagship_wishes(self, obs: Observation, ship: Ship) -> tuple[frozenset[int], dict[int, str]]:
        """What the other ships of our side, the player's above all, want done with enemy ships: those to spare
        (disabled already) and those being disabled, with the system. Empty for a captain who won't listen."""
        if not self.obeys_flagship(ship):
            return frozenset(), {}
        spare: set[int] = set()
        disable: dict[int, str] = {}
        for s in obs.own_ships():
            if s.id == ship.id:
                continue
            spare |= s.spared
            for o in s.objectives:
                if o.goal in ("disable", "capture"):
                    for t in o.targets:
                        disable.setdefault(t, "shields" if o.goal == "capture" else o.group)
        return frozenset(spare - set(disable)), disable

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

    def seat(self, world: object) -> None:
        """Taking command: the ship's mood takes this captain's temperament [E] (called by World.add_controller)."""
        from ..sim.systems.disposition import seat

        ship = getattr(world, "ships", {}).get(self.ship_id)
        if ship is not None:
            seat(ship, self.personality)

    def _cmd(self, cls: type[Command], ship: Ship, **kw: object) -> Command:
        return cls(ship_id=ship.id, issuer=Authority.AI_CAPTAIN, source=f"Captain {ship.captain}".strip(), **kw)  # type: ignore[arg-type]

    def _log(self, obs: Observation, text: str) -> None:
        self.trace.add(obs.tick, text)

    def helm_aggression(self, obs: Observation, ship: Ship) -> float:
        """How boldly the helm flies: how little it weaves and how fast it closes. Officers temper it [E].

        An enraged captain flies harder at us, a shaken one more warily [E]."""
        m = ship.mood
        return max(0.0, min(1.0, self.personality.aggression + 0.25 * m.anger - 0.25 * m.fear))

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
        self.wishes = self._flagship_wishes(obs, ship)
        dmg = self.damage_ratio(ship)
        # [E] a shaken crew makes a captain quicker to break off, a keen one slower
        m = ship.mood
        threshold = (p.bravery * AI_RETREAT_DAMAGE * p.doctrine.retreat_threshold_scale
                     * (1.0 + obs.rules.morale_nerve * ship.morale_factor)
                     * (1.0 - 0.5 * m.fear) * (1.0 + 0.6 * m.anger))   # [E] what they've watched happen to their side
        if m.terms == "withdraw" and not self.withdrawing and not ship.cls.is_base:
            self.withdrawing = self.retreating = True                  # [E] they agreed to leave over a hail
            self._log(obs, "agreed to withdraw: leaving the field, weapons cold")
        if not self.retreating and dmg > threshold:
            self.retreating = True
            self._log(obs, f"morale broken: damage {dmg:.2f} > {threshold:.2f}; retreating")
        if self.retreating and not self.withdrawing and m.fear > 0.6 and not ship.cls.is_base:
            self.withdrawing = True     # [E] cowed by what they've watched: they leave the field rather than hover
            self._log(obs, f"cowed (fear {m.fear:.2f}): leaving the field")
        st = obs.ally_order(ship.id)
        if st is not None and st.movement == "run":
            self.retreating = True  # told to run: never rejoins until the order is cancelled
        elif self.retreating and dmg < p.bravery * AI_RETREAT_RECOVER and not self.withdrawing:
            self.retreating = False
            self._log(obs, "recovered nerve; re-engaging")
        if self.smart:
            self._plan_repairs(obs, ship, dmg, st, out)
            self._check_stall(obs, ship)
            if self.retreating and not self.withdrawing and not ship.cls.is_base and all(
                    c.cls is not None and c.cls.is_base for c in obs.hostile_contacts() if c.visible):
                self.withdrawing = True   # beaten, and only a base left to fight: it won't follow, so leave for good
                self._log(obs, "only a base left against us: leaving the field")

        # last stand: fanatics (and crippled ships of a self-destruct doctrine) blow themselves up
        if (not self.last_stand and ship.self_destruct < 0 and dmg > 0.8
                and (p.fanaticism > AI_FANATIC_RAM or (not ship.can_move() and
                     self.rng.unit() < 0.02 * p.doctrine.self_destruct))):
            self.last_stand = True
            self._log(obs, "last stand: self-destruct and ram")
            out.append(self._cmd(SelfDestruct, ship, cycles=6.0))

        # surrender when beaten and unable to run; [E] or cowed by what they've seen, and still trusting us
        if (self.retreating and (not ship.can_move() or m.fear > 0.6) and dmg > 0.7 and not self.last_stand
                and self.rng.unit() < 0.05 * p.doctrine.surrender_willingness * (1.0 - p.bravery * 0.5)
                * (1.0 - 0.5 * ship.morale_factor) * (1.0 + 3.0 * m.fear) * (1.0 - m.distrust)):
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
        probed, focused = self._scoring_sets(obs, ship)
        for c in obs.hostile_contacts():
            if c.side is not None and c.side == self.side:
                continue
            s = self._score(obs, ship, c, probed, focused)
            if forced is not None and c.id == forced:
                s *= 100.0
            if s > best_score:
                best, best_score = c, s
        new_target = best.id if best is not None else None
        if new_target != self.target:
            self._log(obs, f"target -> {best.label if best else 'none'} (score {best_score:.1f})")
            self.target = new_target
        wanted = self.wishes[1].get(self.target) if self.target is not None else None
        if self.target is not None and (ship.target != self.target or
                                        (wanted is not None and ship.target_subsystem != wanted)):
            sub = wanted or self._subsystem_choice(obs, ship, best)
            out.append(self._cmd(SelectTarget, ship, target=self.target, subsystem=sub))
        # proximity tuned to the target's agility [R]: min(max warp × 50, design max)
        if best is not None and best.cls is not None and ship.tubes and self.autoload_set_for != best.id:
            spec = obs.content.torpedoes.get(ship.tubes[0].load_ordnance or ship.cls.torpedo)
            if spec is not None:
                prox = max(obs.rules.prox_floor, min(best.cls.max_warp * 50.0, spec.max_prox))
                out.append(self._cmd(ConfigureAutoload, ship, weapon="tube", prox=prox))
                self.autoload_set_for = best.id
        return out

    # ------------------------------------------------------------ fighting as a force [E]

    def repair_base(self, obs: Observation, ship: Ship) -> Ship | None:
        """The nearest friendly base with room to take this ship aboard."""
        bases = [b for b in obs.own_ships() if b.cls.is_base and b.cls.mass_capacity >= ship.cls.mass and b.id != ship.id]
        if not bases or ship.cls.is_base:
            return None
        return min(bases, key=lambda b: math.hypot(b.x - ship.x, b.y - ship.y))

    def dock_threshold(self, obs: Observation, ship: Ship) -> float:
        """Damage at which a ship breaks off to dock."""
        return AI_DOCK_DAMAGE

    def ready_to_rejoin(self, ship: Ship) -> bool:
        hull = ship.structure / max(1.0, ship.structure_max)
        vital = [*ship.banks, *ship.tubes, *ship.drives, *ship.shields, *ship.reactors]
        return hull >= AI_UNDOCK_HULL and all(x.damage < AI_UNDOCK_SYSTEMS for x in vital) and ship.crew > 0

    def _plan_repairs(self, obs: Observation, ship: Ship, dmg: float, st: AllyStanding | None,
                      out: list[Command]) -> None:
        """A badly hurt ship with a friendly base on the field goes and docks, and rejoins once she is fit."""
        ordered = st is not None and st.movement is not None
        base = self.repair_base(obs, ship)
        hull = ship.structure / max(1.0, ship.structure_max)
        if base is None or ordered or self.last_stand:
            if self.docking and ship.docked_to is None:
                self.docking = False
            return
        quiet = not any(c.visible and c.distance_to(ship.x, ship.y) < AI_LULL_RANGE for c in obs.hostile_contacts())
        if not self.docking and (dmg > self.dock_threshold(obs, ship) or hull < 1.0 - self.dock_threshold(obs, ship)):
            self.docking = True
            self.retreating = False
            self._log(obs, f"damage {dmg:.2f}, hull {hull:.0%}: going to {base.name} for repairs")
        elif not self.docking and quiet and ship.docked_to is None and not self.ready_to_rejoin(ship):
            self.docking = True       # a lull between attacks: use it to put her right at the base
            self._log(obs, f"lull in the fighting, hull {hull:.0%}: docking at {base.name} to repair")
        if self.docking and not self.withdrawing:
            self.retreating = False
        if self.docking and ship.docked_to is not None and self.ready_to_rejoin(ship):
            self.docking = False
            self.last_helm = None
            self._log(obs, "repaired: undocking to rejoin the fight")
            out.append(self._cmd(Dock, ship, host=None))

    def _stay_home(self, obs: Observation, ship: Ship, c: ContactView | None) -> Command | None:
        """With a friendly base on the field, fight near it [E]: don't chase an enemy far from its guns, and
        come back to it when there's nobody to fight. Returns the helm order, or None to fight as usual."""
        base = self.repair_base(obs, ship)
        if base is None:
            return None
        d_home = math.hypot(base.x - ship.x, base.y - ship.y)
        brg_home = bearing(base.x - ship.x, base.y - ship.y)
        if c is None:
            if d_home > AI_HOME_RANGE * 0.4:
                return self._helm(obs, ship, brg_home, min(self.combat_speed(ship, obs), max(1.0, d_home / 1500.0)))
            return self._helm(obs, ship, ship.course, 0.0)
        if d_home > AI_HOME_RANGE and c.distance_to(base.x, base.y) > AI_HOME_RANGE:
            return self._weave(obs, ship, brg_home, c.distance_to(ship.x, ship.y))
        return None

    def _go_dock(self, obs: Observation, ship: Ship) -> list[Command]:
        base = self.repair_base(obs, ship)
        if base is None:
            self.docking = False
            return []
        if ship.docked_to is not None:
            return []
        d = math.hypot(base.x - ship.x, base.y - ship.y)
        if d <= obs.rules.dock_range * 0.9:
            return [c for c in (self._helm(obs, ship, ship.course, 0.0), self._cmd(Dock, ship, host=base.id)) if c is not None]
        warp = self.combat_speed(ship, obs) if d > obs.rules.dock_range * 4 else max(1.0, min(3.0, d / 400.0))
        return [c for c in (self._helm(obs, ship, bearing(base.x - ship.x, base.y - ship.y), warp),) if c is not None]

    def _check_stall(self, obs: Observation, ship: Ship) -> None:
        """Nobody on our side has dealt or taken damage for a long while: press if we're stronger, else leave."""
        mark = sum(s.stats.damage_dealt + s.stats.damage_taken for s in obs.own_ships(alive_only=False))
        if mark != self.stall_mark:
            self.stall_mark = mark
            self.stall_since = obs.tick
            return
        if self.pressing or self.withdrawing:
            return
        if (obs.tick - self.stall_since) * obs.rules.dt < AI_STALL_CYCLES:
            return
        hostiles = [c for c in obs.hostile_contacts() if c.visible and c.cls is not None]
        if not hostiles:
            return
        ours = sum(strength(sum(1 for b in s.banks if b.intact), s.cls.banks_range, sum(1 for t in s.tubes if t.intact))
                   * max(0.1, s.structure / max(1.0, s.structure_max)) for s in obs.own_ships())
        theirs = sum(strength(cls.banks, cls.banks_range, cls.tubes) * (c.scan.structure_frac if c.scan is not None else 1.0)
                     for c in hostiles if (cls := c.cls) is not None)
        if ours >= theirs * AI_PRESS_EDGE:
            self.pressing = True
            self._log(obs, f"stalled {AI_STALL_CYCLES:.0f} cycles; stronger ({ours:.0f} vs {theirs:.0f}): pressing the attack")
        elif not ship.cls.is_base:
            self.withdrawing = self.retreating = True
            self._log(obs, f"stalled {AI_STALL_CYCLES:.0f} cycles; weaker ({ours:.0f} vs {theirs:.0f}): leaving the field")

    @staticmethod
    def _scoring_sets(obs: Observation, ship: Ship) -> tuple[set[int | None], set[int | None]]:
        """What `_score` needs about the whole side, gathered once per choice rather than once per contact
        (the scoring is otherwise quadratic in the number of ships)."""
        probed = {o.target for o in obs.ordnance() if o.friendly and o.kind == "probe"}
        focused = {o.target for o in obs.own_ships() if o.id != ship.id}
        return probed, focused

    def _score(self, obs: Observation, ship: Ship, c: ContactView, probed: set[int | None],
               focused: set[int | None]) -> float:
        """Begin's target score [R]: threat strength × distance band × modifiers. `probed` holds the contacts our
        probes are chasing, `focused` the targets of the side's other ships."""
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
        if c.id in self.wishes[0]:
            return 0.0      # the flagship disabled her and wants her spared
        if c.id == ship.mood.nemesis:
            score *= 1.0 + 1.5 * ship.mood.anger     # [E] the ship they blame for their friends
        if c.id in probed:
            score *= 0.5
        if not c.visible:
            score *= AI_STALE_CONTACT_MULT
        # doctrine: focus on the side's common target
        focus = self.personality.doctrine.focus_fire
        if c.id in focused:
            score *= 1.0 + 0.5 * focus
        if self.smart:
            # [E] finish what the scans show is hurt; leave a screened base for last
            if c.scan is not None:
                score *= 1.0 + AI_HURT_BONUS * (1.0 - c.scan.structure_frac)
            if c.cls is not None and c.cls.is_base and any(
                    o.id != c.id and o.visible and o.cls is not None and not o.cls.is_base
                    and o.distance_to(c.x, c.y) < AI_SCREEN_RANGE for o in obs.hostile_contacts()):
                score *= AI_BASE_SCREENED
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
        hold_fire = (st is not None and st.hold_fire) or ship.hold_fire   # [E] or they agreed to stand down
        # a running ship still uses its weapons while an enemy is in range (manual p. 23)
        if c is not None and not hold_fire:
            out.extend(self._weapons(obs, ship, c, st))
        out.extend(self._shields(obs, ship, c))
        out.extend(self._cloak(obs, ship, c))
        handled = False
        if st is not None:
            handled = self._standing_orders(obs, ship, c, st, out)
        if not handled and self.docking:
            out.extend(self._go_dock(obs, ship))
            handled = True
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
        if c.id in self.wishes[0]:
            return out          # spared on the flagship's word
        aim = self.wishes[1].get(c.id)     # the flagship is disabling her: just that system, and gently
        d = c.distance_to(ship.x, ship.y)
        brg = bearing(c.x - ship.x, c.y - ship.y)

        # phasers [R]: aggressive captains wait for an alpha strike, timid ones fire half now
        if ship.banks and d < ship.cls.banks_range:
            charged = [i for i, b in enumerate(ship.banks) if bank_ready(ship, b) and b.role.value != "defense"
                       and bank_bears_point(ship, b, c.x, c.y)]
            op = [i for i, b in enumerate(ship.banks) if b.intact and b.enabled and b.role.value != "defense"
                  and bank_bears_point(ship, b, c.x, c.y)]
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
                    out.append(self._cmd(FirePhasers, ship, banks=tuple(charged[:n]), target=c.id, spread=spread,
                                         subsystem=aim))
                    self._log(obs, f"phasers x{n} at {c.label} ({d:,.0f})")

        # torpedoes [R]: inside the envelope, volley sized by torpedo pressure
        loaded = [i for i, t in enumerate(ship.tubes) if t.loaded is not None]
        if aim is not None and c.scan is not None and c.scan.structure_frac <= ALLY_DISABLE_TORPEDO_HULL:
            loaded = []
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
                    out.append(self._cmd(FireTorpedoes, ship, tubes=tuple(loaded[:volley]), target=c.id, fan=fan,
                                         subsystem=aim))
                    self._log(obs, f"torpedoes x{volley} at {c.label} ({d:,.0f}, pressure {pressure:.0f})")

        # probes [R]: launch when the target is slow or has no charged banks; doctrine scales use
        loaded_p = [i for i, lch in enumerate(ship.launchers) if lch.loaded is not None and aim is None]
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
            cap = (AI_WEAVE_AGGR_BASE - self.helm_aggression(obs, ship)) * max(0.0, AI_WEAVE_AMP_MAX - d / AI_WEAVE_DIST_DIV)
            amp = self.rng.uniform(0.0, max(0.0, cap))
        course = norm360(base + self.weave_side * amp)
        warp = self.combat_speed(ship, obs)
        turn = ang_dist(ship.course, course)
        cur = max(1.0, abs(ship.warp))
        if turn > (ship.cls.w1turn / cur) * 2.0:
            warp = max(1.0, min(warp, ship.cls.w1turn * 2.0 / turn))
        return self._helm(obs, ship, course, warp)

    def _close_for_phasers(self, obs: Observation, ship: Ship, c: ContactView, d: float, brg: float) -> Command | None:
        rng_ = ship.cls.banks_range
        if c.cls is not None and c.cls.is_base and d < rng_ * AI_BASE_STANDOFF and not self.pressing:
            # [E] a base's banks cover every bearing, so sitting on top of one is suicide: stand off and shoot
            side = 1.0 if ship.id % 2 else -1.0
            return self._weave(obs, ship, brg + 180.0 - side * AI_STANDOFF_OPEN_ANGLE, d)
        if d < rng_:
            rel = norm360(brg - ship.course)
            sh = ship.shield_for_bearing(rel)
            if sh is None or sh.effective < AI_APPROACH_CONE:
                return self._helm(obs, ship, self.rng.uniform(0, 360), self.combat_speed(ship, obs))  # jink
            return self._helm(obs, ship, brg, c.warp + 1.0)
        if self.smart and d > rng_ * 1.2:
            # [E] a shipmate is already closer on this target: come in on her flank, onto another shield
            mate = next((s for s in obs.own_ships() if s.id != ship.id and s.target == c.id
                         and math.hypot(s.x - c.x, s.y - c.y) < d), None)
            if mate is not None:
                # swing to the other side of the line from the target than the one she is on
                cross = (mate.x - c.x) * (ship.y - c.y) - (mate.y - c.y) * (ship.x - c.x)
                brg = norm360(brg + (AI_FLANK_ANGLE if cross >= 0 else -AI_FLANK_ANGLE))
        if d > rng_ * 2.0:
            return self._weave(obs, ship, brg, d)
        return self._helm(obs, ship, brg, c.warp + self.helm_aggression(obs, ship) * AI_APPROACH_WARP_AGGR)

    def _maneuver(self, obs: Observation, ship: Ship, c: ContactView | None,
                  st: AllyStanding | None = None) -> Command | None:
        if ship.cls.is_base or not ship.can_move() or ship.docked_to is not None:
            return None
        if self.smart and not st and not self.retreating and not self.pressing:
            home = self._stay_home(obs, ship, c)
            if home is not None:
                return home
        if c is None and self.withdrawing:
            # [E] leaving the field with no enemy left on sensors: hold the course away, full speed, until clear
            return self._helm(obs, ship, ship.desired_course, ship.max_attainable_warp)
        if c is None:
            # wander [R]: hold course at cruise, occasionally sidestep
            turn = 0.0
            if self.rng.unit() < 0.05:
                turn = AI_SIDESTEP if self.rng.unit() < 0.5 else -AI_SIDESTEP
            return self._helm(obs, ship, ship.desired_course + turn, ship.cls.cruise_warp)
        d = c.distance_to(ship.x, ship.y)
        brg = bearing(c.x - ship.x, c.y - ship.y)
        if self.retreating:
            if self.withdrawing and d >= AI_WEAVE_THREAT_RANGE:
                return self._helm(obs, ship, norm360(brg + 180.0), ship.max_attainable_warp)   # [E] clear out
            return self._weave(obs, ship, brg + 180.0, d)
        if self.pressing and not st:
            return self._close_for_phasers(obs, ship, c, d, brg)
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

        knife_ok = True
        if self.smart and weapon is None:
            fresh = self._fresh_shield(obs, ship, c, d, brg)
            if fresh is not None:
                return fresh
            close, stand = self._odds(obs, ship, c)
            # [E] what this navy has learned on the tour: wary of our aimed fire, or sure our magazines are low
            close *= 1.0 + 0.6 * p.press - 0.4 * p.caution
            stand *= 1.0 + 0.4 * p.caution
            armed = ship.torps_remaining + sum(t.loaded is not None for t in ship.tubes) > 0 and tp_dom > 0
            quicker = c.cls is not None and ship.max_attainable_warp > c.cls.max_warp
            if armed and quicker and max(close, stand) < 1.0:
                ph_dom = 0.0                   # outgunned either way but faster: stay out of its reach, tubes only
            elif close > stand * AI_CLOSE_HYSTERESIS:
                ph_dom = max(ph_dom, tp_dom * 2.0, 1.0)
            elif armed and stand > close * AI_CLOSE_HYSTERESIS:
                ph_dom = min(ph_dom, tp_dom * 0.5)
            knife_ok = close >= stand
        if ph_dom > 0 and ph_dom > tp_dom:
            return self._close_for_phasers(obs, ship, c, d, brg)
        if tp_dom > 0:
            spec = obs.content.torpedoes.get(ship.tubes[0].load_ordnance or ship.cls.torpedo) if ship.tubes else None
            if spec is not None:
                lo, hi = torpedo_envelope(ship, c.x, c.y, c.vx, c.vy, spec.velocity, spec.arm_time,
                                          spec.max_time_fuse, obs.rules.units_per_warp)
                standoff = lo + (1.0 - p.aggression) * (hi - lo) * 0.6
                if self.smart and c.cls is not None and c.cls.banks:
                    # [E] a torpedo boat keeps outside the reach of the target's banks
                    standoff = max(standoff, min(c.cls.banks_range * AI_KITE_MARGIN, hi * 0.6))
                # [E] a faster enemy cannot be held off, and one already inside phaser reach must be fought there:
                # turning away only shows it the weaker shields and the tubes' blind arcs
                faster = c.cls is not None and c.cls.max_warp >= ship.max_attainable_warp
                if knife_ok and ph_dom > 0 and d < ship.cls.banks_range * AI_KNIFE_FIGHT_RANGE and (faster or d < lo):
                    return self._close_for_phasers(obs, ship, c, d, brg)
                if d < standoff:
                    # open the range obliquely, not straight away: running dead astern only invites a chase
                    side = 1.0 if ship.id % 2 else -1.0
                    return self._weave(obs, ship, brg + 180.0 - side * AI_STANDOFF_OPEN_ANGLE, d)
                return self._weave(obs, ship, brg, d)
        return self._helm(obs, ship, ship.course, 0.0)  # helpless: full stop

    # ------------------------------------------------------------ fighting to the ship's strengths [E]

    @staticmethod
    def phaser_rate(banks: int, charge: float, rate: float, rules: object, frac: float = 0.5) -> float:
        """Hull-and-shield damage a cycle from a ship's banks at `frac` of their range (the [R] phaser formula)."""
        mult = getattr(rules, "phaser_dam_mult", 45.0) / getattr(rules, "spread_min", 10.0) * getattr(rules, "phaser_half", 0.5)
        return banks * charge * mult * math.sqrt(max(0.0, 1.0 - frac)) / max(0.5, rate)

    @staticmethod
    def torpedo_rate(tubes: int, spec: object, rules: object) -> float:
        """Expected blast damage a cycle from a ship's tubes: yield × splash, by the chance of a hit, per reload."""
        if spec is None or tubes <= 0:
            return 0.0
        hit = AI_TORP_HIT_HOMING if getattr(spec, "homing", False) else AI_TORP_HIT
        hit *= min(1.0, getattr(spec, "max_prox", 500.0) / 600.0)
        blast = getattr(spec, "damage", 0.0) * getattr(rules, "splash_mult", 5.0) * getattr(spec, "blast_scale", 1.0)
        return tubes * blast * hit / max(0.5, getattr(spec, "charge_time", 3.0))

    @staticmethod
    def toughness(cls: object, rules: object) -> float:
        """Roughly how much punishment a class takes: what a shield soaks, plus the hull behind it."""
        hull = getattr(cls, "mass", 100.0) * getattr(rules, "hull_per_mass", 1.0) + getattr(rules, "hull_base", 0.0)
        return getattr(cls, "shield_strength", 200.0) * getattr(cls, "shield_absorption", 0.6) + hull + 1.0

    def _odds(self, obs: Observation, ship: Ship, c: ContactView) -> tuple[float, float]:
        """(our edge closing to phaser range, our edge standing off with torpedoes): damage dealt / taken."""
        rules = obs.rules
        spec = obs.content.torpedoes.get(ship.tubes[0].load_ordnance or ship.cls.torpedo) if ship.tubes else None
        tubes = sum(1 for t in ship.tubes if t.intact) if ship.torps_remaining > 0 or any(
            t.loaded is not None for t in ship.tubes) else 0
        my_tp = self.torpedo_rate(tubes, spec, rules)
        my_ph = self.phaser_rate(sum(1 for b in ship.banks if b.intact), ship.cls.banks_charge, ship.cls.banks_rate, rules)
        k = c.cls
        if k is not None:
            sc = c.scan
            banks = sc.charged_banks if sc is not None and obs.tick - sc.tick < 3 * rules.ticks_per_cycle else k.banks
            their_ph = self.phaser_rate(banks, k.banks_charge, k.banks_rate, rules)
            their_tp = self.torpedo_rate(k.tubes, obs.content.torpedoes.get(k.torpedo), rules)
        else:
            their_ph, their_tp = self.phaser_rate(4, 10.0, 3.0, rules), self.torpedo_rate(2, spec, rules)
        # how much punishment each can take: shields (by how much they soak) and hull
        tough = self.toughness(ship.cls, rules) / self.toughness(k if k is not None else ship.cls, rules)
        # up close the tubes still fire, but the arcs and the arming run cost about half of them
        close = (my_ph + 0.5 * my_tp + 1.0) / (their_ph + 0.5 * their_tp + 1.0) * tough
        stand = (my_tp + 1.0) / (their_tp + 1.0) * tough
        # a target that is already broken is worth closing on: shields down where we'd hit, or hull going
        sc = c.scan
        if sc is not None and (sc.structure_frac < 0.35 or (sc.shields and max(sc.shields) <= 10.0)):
            close *= 1.6
        return close, stand

    def _fresh_shield(self, obs: Observation, ship: Ship, c: ContactView, d: float, brg: float) -> Command | None:
        """The shield facing the enemy is nearly gone: turn a fresh one toward it (Begin's own advice) [E]."""
        facing = ship.shield_for_bearing(norm360(brg - ship.course))
        reach = c.cls.banks_range if c.cls is not None else 2000.0
        if facing is None or facing.effective >= AI_SHIELD_BACK_OFF * (1.0 + self.personality.caution) \
                or d > reach * AI_KITE_MARGIN * 1.5:
            return None
        best = max((sh for sh in ship.shields if sh.up), key=lambda sh: sh.effective, default=None)
        if best is None or best.effective < facing.effective + 20.0:
            return None
        self._log(obs, f"shield {facing.effective:.0f}%: turning shield {best.index + 1} to {c.label}")
        return self._helm(obs, ship, brg - best.facing, self.combat_speed(ship, obs))


__all__ = ["AICaptain", "strength"]
