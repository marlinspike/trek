"""The authoritative simulation: owns every piece of mutable battle state.

One `step()` advances one fixed tick (1/10 of a Begin cycle). Rendering,
input, AI and officers never touch state directly: they read observations
and submit typed commands, which the world validates and applies at a
well-defined point in the step. Everything random draws from the world's
seeded stream, so a battle is fully reproducible from (content, rules,
setup, seed, command log).

Step order:
  1. sensors refresh each side's contact picture
  2. controllers whose cadence is due think and queue commands
  3. queued commands are validated and applied (authority holds enforced)
  4. power, shields and weapon charging per ship
  5. helm and movement (tractor towing applied after movement)
  6. ordnance flight, fusing and blasts
  7. repair, scans, self-destruct, boarding, cloak reveal decay
  8. escape and battle outcome checks
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Iterable, Protocol

from ..content.schema import ContentDB
from ..core.rng import Rng
from .arrivals import Arrival, update_arrivals, waves_pending
from .allies import MOVEMENT_ORDERS, WEAPON_ORDERS, AllyStanding
from .commands import AllyOrder, Authority, Command, Rejected, fire_target, offensive_fire
from .events import CommandRejected, Event, Message, ShipStatusChanged, SubsystemDamaged, Tone
from .factory import build_ship
from .ordnance import Probe, Torpedo
from .projects import update_projects
from .rules import DEFAULT_RULES, Rules
from .ship import HelmMode, LoadedProbe, Launcher, Mood, Ship, ShipStatus, Subsystem
from .systems import sensors as sensors_sys
from .systems.helm import move_ship, update_helm
from .systems.ordnance import blast, fly_ordnance, resolve_detonations
from .systems.power import update_power, warp_budget
from .systems.morale import update_morale
from .systems.disposition import update_disposition
from .systems.repair import update_repair

if TYPE_CHECKING:
    from .observation import Observation

TONES = {t.value: t for t in Tone}


class Controller(Protocol):
    """Anything that issues commands on a cadence: AI captain, ship computer, officer.

    Controllers receive only an `Observation` (their side's knowledge), never
    the world itself.
    """

    side: int
    period: int  # ticks between decisions
    phase: int   # tick offset so controllers don't all think on the same tick

    def think(self, obs: Observation) -> Iterable[Command]: ...


@dataclass(slots=True)
class PendingScan:
    ship_id: int
    target_id: int
    done_tick: int


@dataclass(slots=True)
class Outcome:
    over: bool = False
    winner: int | None = None   # side, or None for mutual destruction / disengagement
    tick: int = 0
    reason: str = ""


@dataclass(slots=True)
class LoggedCommand:
    tick: int
    command: Command
    accepted: bool
    reason: str = ""


@dataclass
class World:
    content: ContentDB
    rules: Rules = DEFAULT_RULES
    seed: int = 1
    player_side: int = 0

    tick: int = 0
    ships: dict[int, Ship] = field(default_factory=dict)
    torpedoes: list[Torpedo] = field(default_factory=list)
    probes: list[Probe] = field(default_factory=list)
    intel: dict[int, sensors_sys.SideIntel] = field(default_factory=dict)
    controllers: list[Controller] = field(default_factory=list)
    outcome: Outcome = field(default_factory=Outcome)
    reserved_names: set[str] = field(default_factory=set)      # never drawn at random (the player's flagship)

    events: list[Event] = field(default_factory=list)          # since last take_events()
    step_events: list[Event] = field(default_factory=list)     # produced by the last step
    morale_events: list[Event] = field(default_factory=list)   # not yet weighed by the morale system [E]
    command_log: list[LoggedCommand] = field(default_factory=list)
    ally_orders: dict[int, AllyStanding] = field(default_factory=dict)
    torpedo_pressure: dict[int, float] = field(default_factory=dict)
    side_names: dict[int, str] = field(default_factory=dict)
    on_capture: Callable[[Ship], None] | None = None           # gives a captured ship to her new side's brains
    arrivals: list[Arrival] = field(default_factory=list)      # waves and reinforcements still to come [E]
    faith_broken: dict[int, set[int]] = field(default_factory=dict)   # side -> ships it fired on after a surrender or truce [E]
    on_arrival: Callable[[Ship], None] | None = None           # gives an arriving ship her captain and computer

    _next_id: int = 1
    _queue: list[Command] = field(default_factory=list)
    _holds: dict[tuple[int, str], tuple[Authority, int]] = field(default_factory=dict)
    _scans: list[PendingScan] = field(default_factory=list)
    _probe_serial: int = 0
    _obs_cache: dict[int, Observation] = field(default_factory=dict)
    _prize_since: float = -1.0   # when the last enemy was left helpless, waiting to be boarded

    def __post_init__(self) -> None:
        self.rng = Rng(self.seed)
        self._names_rng = self.rng.derive("names")

    # ------------------------------------------------------------ setup

    def new_id(self) -> int:
        i = self._next_id
        self._next_id += 1
        return i

    @property
    def time(self) -> float:
        """Elapsed battle time in cycles."""
        return self.tick * self.rules.dt

    def add_ship(
        self,
        class_id: str,
        side: int,
        x: float,
        y: float,
        course: float = 0.0,
        warp: float = 0.0,
        name: str | None = None,
        captain: str | None = None,
    ) -> Ship:
        cls = self.content.classes[class_id]
        faction = self.content.factions[cls.faction]
        if name is None:
            used = {s.name for s in self.ships.values()} | self.reserved_names
            free = [n for n in cls.ship_names if n not in used]
            name = self._names_rng.choice(free) if free else f"{cls.abbrev}-{self._next_id}"
        if captain is None:
            captain = self._names_rng.choice(list(faction.captain_names)) if faction.captain_names else ""
        ship = build_ship(self.content, self.rules, self.new_id(), class_id, side, name, captain, x, y, course, warp)
        self.ships[ship.id] = ship
        self.intel.setdefault(side, sensors_sys.SideIntel(side))
        self.side_names.setdefault(side, faction.name)
        update_power(self, ship, self.rules.dt)  # settle max warp and shields before the first tick
        sensors_sys.update_sensors(self)
        return ship

    def add_controller(self, c: Controller) -> None:
        self.controllers.append(c)
        seat = getattr(c, "seat", None)
        if callable(seat):
            seat(self)          # an AI captain takes command: the ship's mood gets their temperament [E]

    # ------------------------------------------------------------ events

    def emit(self, ev: Event) -> None:
        self.events.append(ev)
        self.step_events.append(ev)
        self.morale_events.append(ev)

    def take_events(self) -> list[Event]:
        out = self.events
        self.events = []
        return out

    def say(self, ship: Ship, text: str, tone: str = "info", public: bool = False, speaker: str | None = None) -> None:
        self.emit(Message(self.tick, text, TONES.get(tone, Tone.INFO), speaker=speaker if speaker is not None else ship.name,
                          ship_id=ship.id, visible_to=None if public else frozenset({ship.side})))

    def label(self, side: int, ship_id: int) -> str:
        s = self.ships.get(ship_id)
        if s is None:
            return f"contact {ship_id}"
        if s.side == side:
            return s.name
        c = self.intel.get(side, sensors_sys.SideIntel(side)).contacts.get(ship_id)
        if c is not None and c.identified:
            return f"{s.name} ({s.cls.abbrev})"
        return f"unidentified contact {ship_id}"

    # ------------------------------------------------------------ sensor facade

    def apparent_position(self, side: int, ship_id: int) -> tuple[float, float] | None:
        return sensors_sys.apparent_position(self, side, ship_id)

    def track(self, side: int, ship_id: int) -> tuple[float, float, float, float] | None:
        return sensors_sys.track(self, side, ship_id)

    def is_visible(self, side: int, ship_id: int) -> bool:
        return sensors_sys.is_visible(self, side, ship_id)

    def intel_quality(self, side: int, ship_id: int) -> float:
        return sensors_sys.intel_quality(self, side, ship_id)

    def observe(self, side: int) -> Observation:
        """The read-only picture one side is entitled to (cached per tick)."""
        from .observation import Observation

        obs = self._obs_cache.get(side)
        if obs is None or obs.tick != self.tick:
            obs = Observation(self, side)
            self._obs_cache[side] = obs
        return obs

    # ------------------------------------------------------------ commands

    def submit(self, cmd: Command) -> None:
        """Queue a command for the start of the next step."""
        self._queue.append(cmd)

    def execute(self, cmd: Command) -> str | None:
        """Validate and apply a command now. Returns the rejection reason, or None."""
        ship = self.ships.get(cmd.ship_id)
        reason: str | None = None
        if ship is not None and ship.spared and cmd.issuer >= Authority.CAPTAIN and (
                offensive_fire(cmd) or getattr(cmd, "hull", False) is True):
            # the captain fires on a ship they had disabled, or says "target her hull": she is fair game again,
            # even if this shot can't go (the banks still charging)
            ship.spared.discard(fire_target(cmd, ship))
        if ship is None or not ship.exists:
            reason = "That ship is no longer under command."
        elif cmd.needs_crew and (ship.crew <= 0 or ship.status != ShipStatus.ACTIVE):
            reason = f"{ship.name} is not responding ({ship.status.value})."
        else:
            reason = self._held(cmd)
            if reason is None:
                try:
                    cmd.validate(self, ship)
                except Rejected as r:
                    reason = str(r)
        self.command_log.append(LoggedCommand(self.tick, cmd, reason is None, reason or ""))
        if reason is not None:
            self.emit(CommandRejected(self.tick, cmd.ship_id, cmd.name, reason, cmd.source))
            if cmd.issuer >= Authority.CAPTAIN and ship is not None:
                self.emit(Message(self.tick, f"Unable to comply: {reason}", Tone.CAUTION, speaker=cmd.source,
                                  ship_id=ship.id, visible_to=frozenset({ship.side})))
            return reason
        assert ship is not None
        cmd.apply(self, ship)
        if ship.hold_fire and cmd.issuer >= Authority.CAPTAIN and offensive_fire(cmd):
            ship.hold_fire = False          # the captain firing is weapons free again
        if cmd.issuer >= Authority.CAPTAIN:
            until = self.tick + int(self.rules.captain_hold_cycles * self.rules.ticks_per_cycle)
            for ch in cmd.channels():
                self._holds[(ship.id, ch)] = (cmd.issuer, until)
        return None

    def _held(self, cmd: Command) -> str | None:
        ship = self.ships.get(cmd.ship_id)
        if ship is not None and ship.hold_fire and cmd.issuer < Authority.CAPTAIN and offensive_fire(cmd):
            return "Holding fire on the captain's order."
        if (ship is not None and ship.spared and cmd.issuer < Authority.CAPTAIN and offensive_fire(cmd)
                and fire_target(cmd, ship) in ship.spared):
            return "Holding fire on her: the captain wanted her disabled, not destroyed."
        for ch in cmd.channels():
            h = self._holds.get((cmd.ship_id, ch))
            if h is None:
                continue
            auth, until = h
            if until < self.tick:
                del self._holds[(cmd.ship_id, ch)]
                continue
            if cmd.issuer < auth:
                return f"Captain's order holds {ch.split('.')[0]} control."
        return None

    def release_holds(self, ship_id: int, prefix: str = "") -> None:
        """Hand channels back to automation (delegating a station)."""
        for key in [k for k in self._holds if k[0] == ship_id and k[1].startswith(prefix)]:
            del self._holds[key]

    def holds(self, ship_id: int) -> dict[str, float]:
        """Remaining hold time (cycles) per channel, for the UI."""
        out = {}
        for (sid, ch), (_, until) in self._holds.items():
            if sid == ship_id and until >= self.tick:
                out[ch] = (until - self.tick) * self.rules.dt
        return out

    # ------------------------------------------------------------ the step

    def step(self) -> None:
        if self.outcome.over:
            return
        rules = self.rules
        dt = rules.dt
        self.step_events = []

        sensors_sys.update_sensors(self)

        for c in self.controllers:
            if c.period > 0 and (self.tick - c.phase) % c.period == 0:
                for cmd in c.think(self.observe(c.side)):
                    self._queue.append(cmd)
        queue, self._queue = self._queue, []
        for cmd in queue:
            self.execute(cmd)

        ships = list(self.ships.values())
        for s in ships:
            if s.exists:
                update_power(self, s, dt)

        prev: dict[int, tuple[float, float]] = {}
        for s in ships:
            if not s.exists:
                continue
            prev[s.id] = (s.x, s.y)
            if s.status != ShipStatus.ACTIVE or s.crew <= 0:
                s.desired_warp = 0.0
                s.helm_mode = HelmMode.COURSE
            update_helm(self, s, dt)
        for s in ships:
            if s.exists and s.docked_to is None:
                move_ship(self, s, dt)
        self._tow(prev)
        for s in ships:
            if s.exists and s.docked_to is not None:
                move_ship(self, s, dt)

        fly_ordnance(self, dt, prev)
        resolve_detonations(self)

        cycle_edge = (self.tick + 1) % rules.ticks_per_cycle == 0
        for s in ships:
            if not s.exists:
                continue
            update_repair(self, s, dt)
            update_projects(self, s, dt)
            s.reveal_time = max(0.0, s.reveal_time - dt)
            s.deflector_cooldown = max(0.0, s.deflector_cooldown - dt)
            if s.pending_volley is not None and self.tick >= s.pending_volley[0]:
                self._follow_up(s)
            self._self_destruct(s, dt)
            if cycle_edge and s.boarders > 0:
                self._boarding(s)
            if self.tick % 5 == 0 and s.docked_to is None:
                s.trail.append((s.x, s.y))
                if len(s.trail) > 24:
                    del s.trail[0]
        self._complete_scans()
        update_disposition(self, self.morale_events, dt)   # captains weigh what they saw before the crews do
        update_morale(self, dt)
        for k in list(self.torpedo_pressure):
            self.torpedo_pressure[k] *= 1.0 - 0.2 * dt
            if self.torpedo_pressure[k] < 0.05:
                del self.torpedo_pressure[k]

        self._escapes(dt)
        self.tick += 1
        update_arrivals(self)
        self._check_outcome()

    def _follow_up(self, ship: Ship) -> None:
        """The volley behind a bait torpedo [E]: every loaded tube, at the same target."""
        from .commands import Authority, FireTorpedoes

        _, target, sub, issuer = ship.pending_volley  # type: ignore[misc]
        ship.pending_volley = None
        if not ship.alive or (target is not None and (target not in self.ships or not self.ships[target].alive)):
            return
        self.execute(FireTorpedoes(ship_id=ship.id, target=target, subsystem=sub, issuer=Authority(issuer),
                                   source="bait follow-up"))

    def run(self, cycles: float) -> None:
        for _ in range(int(round(cycles * self.rules.ticks_per_cycle))):
            if self.outcome.over:
                break
            self.step()

    # ------------------------------------------------------------ state changes used by systems

    def _set_status(self, ship: Ship, status: ShipStatus, cause: str, by: int | None, text: str, tone: Tone) -> None:
        ship.status = status
        ship.self_destruct = -1.0
        ship.tractor_target = None
        ship.cloaked = False
        self.emit(ShipStatusChanged(self.tick, ship.id, status.value, cause, by))
        self.emit(Message(self.tick, text, tone, ship_id=ship.id))
        for other in self.ships.values():
            if other.tractor_target == ship.id and status in (ShipStatus.DESTROYED, ShipStatus.ESCAPED):
                other.tractor_target = None
            if other.helm_target == ship.id and status in (ShipStatus.DESTROYED, ShipStatus.ESCAPED):
                other.helm_target = None
                other.helm_mode = HelmMode.COURSE
            if other.target == ship.id and status in (ShipStatus.DESTROYED, ShipStatus.ESCAPED):
                other.target = None
                other.target_subsystem = None
                for b in other.banks:
                    if b.lock == ship.id:
                        b.lock = None
                for t in other.tubes:
                    if t.lock == ship.id:
                        t.lock = None

    def _credit(self, ship: Ship, attacker: int | None) -> None:
        att = self.ships.get(attacker) if attacker is not None else None
        if att is not None and att.side != ship.side:
            att.stats.kills += 1

    def destroy_ship(self, ship: Ship, cause: str, attacker: int | None = None, breakup: bool = True) -> None:
        if ship.status == ShipStatus.DESTROYED:
            return
        was_alive = ship.status == ShipStatus.ACTIVE
        energy = warp_budget(ship) / self.rules.destruct_divisor
        ship.structure = min(ship.structure, 0.0)
        ship.crew = 0
        self._set_status(ship, ShipStatus.DESTROYED, cause, attacker, f"{ship.name} has been destroyed ({cause}).", Tone.ALERT)
        if was_alive:
            self._credit(ship, attacker)
        for other in self.ships.values():
            if other.docked_to == ship.id:
                other.docked_to = None
        if breakup and energy > 0:
            blast(self, ship.x, ship.y, energy, "ship", attacker, exclude=ship.id)

    def lose_all_hands(self, ship: Ship, cause: str, attacker: int | None = None) -> None:
        if ship.status in (ShipStatus.DESTROYED, ShipStatus.DERELICT):
            return
        was_alive = ship.status == ShipStatus.ACTIVE
        ship.stats.crew_lost += ship.crew
        ship.crew = 0
        ship.desired_warp = 0.0
        for sh in ship.shields:
            sh.up = False          # nobody left to keep them up: she can be boarded [E]
            sh.effective = 0.0
        self._set_status(ship, ShipStatus.DERELICT, cause, attacker,
                         f"{ship.name} is adrift: no surviving crew ({cause}).", Tone.ALERT)
        if was_alive:
            self._credit(ship, attacker)

    def surrender(self, ship: Ship) -> None:
        if ship.status != ShipStatus.ACTIVE:
            return
        ship.desired_warp = 0.0
        for sh in ship.shields:
            sh.up = False
            sh.reinforced = False
        for b in ship.banks:
            b.enabled = False
            b.lock = None
        for t in ship.tubes:
            t.enabled = False
            t.lock = None
        ship.surrender_time = self.time
        self._set_status(ship, ShipStatus.SURRENDERED, "surrender", None,
                         f"{ship.name} has lowered its shields and surrenders.", Tone.CAUTION)

    def destroy_subsystem(self, ship: Ship, sub: Subsystem, cause: str) -> None:
        if sub.destroyed:
            return
        sub.damage = 100
        sub.repair_progress = 0.0
        sub.on_damaged()
        ship.stats.subsystems_disabled += 1
        self.emit(SubsystemDamaged(self.tick, ship.id, sub.sid, sub.label, 100, True, False))
        self.emit(Message(self.tick, f"{ship.name}: {sub.label.lower()} {cause} and failed!", Tone.ALERT,
                          speaker="Engineering", ship_id=ship.id, visible_to=frozenset({ship.side})))

    def load_probe(self, ship: Ship, launcher: Launcher) -> None:
        if ship.probes_remaining <= 0 or launcher.loaded is not None:
            return
        spec = self.content.probes.get(launcher.load_ordnance) or self.content.probes.get(ship.cls.probe)
        if spec is None:
            return
        r = self.rules
        prox = launcher.load_prox if launcher.load_prox > 0 else spec.max_prox
        prox = max(r.probe_prox_floor, min(spec.max_prox, prox))
        tm = launcher.load_time if launcher.load_time > 0 else spec.max_time_fuse
        tm = max(r.probe_time_floor, min(spec.max_time_fuse, tm))
        self._probe_serial += 1
        code = f"{ship.cls.abbrev[:1].upper()}{self._probe_serial:02d}"
        launcher.loaded = LoadedProbe(spec.id, prox, tm, code)
        launcher.prep = 0.0
        launcher.manual_load_pending = False
        ship.probes_remaining -= 1

    def note_torpedo_pressure(self, target_id: int, n: int) -> None:
        """Torpedoes recently aimed at a target; AI uses it to spread fire and lead [R]."""
        self.torpedo_pressure[target_id] = self.torpedo_pressure.get(target_id, 0.0) + 10.0 * n

    def begin_scan(self, ship: Ship, target_id: int) -> None:
        dur = sensors_sys.scan_duration(ship)
        self._scans = [s for s in self._scans if s.ship_id != ship.id]
        self._scans.append(PendingScan(ship.id, target_id, self.tick + max(1, int(dur * self.rules.ticks_per_cycle))))
        self.say(ship, f"Scanning {self.label(ship.side, target_id)}…", "info", speaker="Science")

    def _complete_scans(self) -> None:
        keep = []
        for sc in self._scans:
            if sc.done_tick > self.tick:
                keep.append(sc)
                continue
            ship = self.ships.get(sc.ship_id)
            tgt = self.ships.get(sc.target_id)
            if ship is None or tgt is None or not ship.alive or not tgt.exists:
                continue
            if not self.is_visible(ship.side, tgt.id) or ship.sensors is None or ship.sensors.destroyed:
                self.say(ship, "Scan interrupted: contact lost.", "caution", speaker="Science")
                continue
            sensors_sys.perform_scan(self, ship, tgt)
            self.say(ship, f"Scan of {tgt.name} complete.", "good", speaker="Science")
        self._scans = keep

    def pending_scan(self, ship_id: int) -> PendingScan | None:
        for sc in self._scans:
            if sc.ship_id == ship_id:
                return sc
        return None

    def transport(self, ship: Ship, target: Ship, count: int) -> None:
        cap = ship.cls.beam_cap * sum(1 for t in ship.transporters if not t.destroyed)
        n = max(0, min(count, cap, ship.crew - 6))
        if n <= 0:
            return
        ship.crew -= n
        if target.side == ship.side:
            room = max(0, target.cls.crew - target.crew)
            moved = min(n, room)
            target.crew += moved
            ship.crew += n - moved
            self.say(ship, f"{moved} crew beamed to {target.name}.", "good")
        else:
            if target.boarders > 0 and target.boarder_side != ship.side:
                target.boarders = 0
            target.boarders += n
            target.boarder_side = ship.side
            self.say(ship, f"Boarding party of {n} beamed aboard {target.name}.", "alert", public=True)

    def standing(self, ship_id: int) -> AllyStanding:
        return self.ally_orders.setdefault(ship_id, AllyStanding())

    def deliver_order(self, ship: Ship, order: AllyOrder) -> None:
        """Apply a `tell` order to the ally's standing orders and have the ally acknowledge it [R + E]."""
        ally = self.ships[order.ally]
        st = self.standing(ally.id)
        st.issued = self.tick
        o = order.order
        tname = self.ships[order.target].name if order.target is not None else ""
        reply = ""
        if o in MOVEMENT_ORDERS:
            st.movement = o
            st.move_target = order.target
            st.move_value = order.value
            st.destination = order.destination
            st.party = int(order.value) if o == "board" and order.value is not None else 0
            if o == "board" and not st.party:
                st.party = max(6, int(ally.crew * 0.25))
            if o == "defend":
                st.target = None
            reply = {
                "escort": f"Escorting {tname}" + (f" at {order.value:,.0f}" if order.value else "") + ".",
                "course": f"Holding course {order.value:.0f}." if order.value is not None else "",
                "run": "Running from the enemy.",
                "withdraw": "Withdrawing out of torpedo range.",
                "approach": f"Approaching {tname}" + (f" to {order.value:,.0f}" if order.value else "") + ".",
                "defend": f"Defending {tname}.",
                "dock": f"Docking with {tname}.",
                "tractor": f"Moving to put a tractor beam on {tname}.",
                "tow": f"Towing {tname} to {self.ships[order.destination].name if order.destination else '?'}.",
                "board": f"Closing to board {tname} with {st.party} crew.",
                "stop": "All stop.",
            }[o]
        elif o == "attack":
            st.movement = None
            st.move_target = None
            st.target = order.target
            reply = f"Attacking {tname}."
        elif o == "target":
            st.target = order.target
            reply = f"Targeting {tname}."
        elif o == "disengage":
            st.target = None
            reply = "Selecting our own targets."
        elif o == "cancel":
            st.movement = None
            st.move_target = None
            reply = "Movement orders cancelled."
        elif o == "hold":
            st.hold_fire = True
            reply = "Holding fire."
        elif o == "open":
            st.hold_fire = False
            reply = "Weapons free."
        elif o in WEAPON_ORDERS:
            st.weapon = o
            if order.target is not None:
                st.target = order.target
            reply = f"Favouring {o}s" + (f" against {tname}" if tname else "") + "."
        elif o == "release":
            ally.tractor_target = None
            if st.movement in ("tractor", "tow"):
                st.movement = None
            reply = "Tractor beam released."
        elif o == "undock":
            ally.docked_to = None
            if st.movement == "dock":
                st.movement = None
            reply = "Undocking."
        elif o == "join":
            st.group = int(order.value or 0)
            reply = f"Joining group {st.group}."
        elif o == "leave":
            st.group = None
            reply = "Leaving the group."
        elif o == "recover":
            st.recover = order.target
            reply = f"Standing by to recover {tname}."
        elif o == "eject":
            if order.target is not None:
                self.ships[order.target].docked_to = None
            reply = f"{tname} released from the docking bay."
        elif o == "report":
            reply = "Report transmitted."
        self.say(ally, reply or f"Acknowledged: {o}.", "info", speaker=ally.name)

    # ------------------------------------------------------------ per-tick specials

    def _tow(self, prev: dict[int, tuple[float, float]]) -> None:
        """Tractor beams: the target follows the tower's motion by the pull ratio [R]."""
        r = self.rules
        for s in self.ships.values():
            if s.tractor_target is None or not s.alive:
                continue
            t = self.ships.get(s.tractor_target)
            if t is None or not t.exists or s.tractor is None or not s.tractor.intact:
                s.tractor_target = None
                continue
            d = math.hypot(t.x - s.x, t.y - s.y)
            ratio = s.cls.tractor_strength / max(1.0, t.cls.mass) * max(0.0, 1.0 - 0.5 * d / r.tractor_range)
            if d > r.tractor_range * 1.25 or ratio < 0.1:
                s.tractor_target = None
                self.say(s, f"Tractor beam lost {t.name}.", "caution")
                continue
            k = min(1.0, ratio)
            sx0, sy0 = prev.get(s.id, (s.x, s.y))
            tx0, ty0 = prev.get(t.id, (t.x, t.y))
            mdx, mdy = s.x - sx0, s.y - sy0
            odx, ody = t.x - tx0, t.y - ty0
            t.x += (mdx - odx) * k
            t.y += (mdy - ody) * k

    def _self_destruct(self, ship: Ship, dt: float) -> None:
        if ship.self_destruct < 0 or not ship.exists:
            return
        before = ship.self_destruct
        ship.self_destruct -= dt
        if math.floor(before) != math.floor(ship.self_destruct) and 0 < before <= 5.0:
            self.say(ship, f"Self-destruct in {math.ceil(ship.self_destruct)}…", "alert", public=True)
        if ship.self_destruct <= 0:
            energy = warp_budget(ship) / self.rules.destruct_divisor + ship.cls.destruct
            ship.self_destruct = -1.0
            x, y = ship.x, ship.y
            self.destroy_ship(ship, "self-destruct", None, breakup=False)
            blast(self, x, y, energy, "destruct", ship.id, exclude=ship.id)

    def _boarding(self, ship: Ship) -> None:
        """One cycle of boarding combat [R]: rounds = rand × boarders, rolled against the boarders' nation."""
        attacker_side = ship.boarder_side
        if ship.status == ShipStatus.SURRENDERED:
            # [E] she struck her colours: her crew lay down their arms, and a party of six takes her without a shot
            if ship.boarders >= 6:
                self._capture(ship, attacker_side, prisoners=True)
            return
        level = 0.5
        for s in self.ships.values():
            if s.side == attacker_side:
                level = self.content.factions[s.faction].dogma.boarding
                break
        rounds = int(self.rng.unit() * ship.boarders) + 1
        for _ in range(rounds):
            if ship.boarders <= 0 or ship.crew <= 0:
                break
            if self.rng.unit() < level * (ship.boarders / (ship.boarders + ship.crew)) * 2:
                ship.crew -= 1
                ship.stats.crew_lost += 1
            else:
                ship.boarders -= 1
        if ship.boarders <= 0:
            ship.boarders = 0
            self.say(ship, f"Boarders on {ship.name} have been repelled.", "good", public=True)
        elif ship.crew < 6 and ship.boarders >= 6:
            self._capture(ship, attacker_side)
        elif ship.crew <= 0:
            self.lose_all_hands(ship, "boarders")

    def _capture(self, ship: Ship, side: int, prisoners: bool = False) -> None:
        """The boarders hold the ship: she joins their side with them as her crew [R], under a new captain [E].

        `prisoners`: she had surrendered, so her crew are taken prisoner rather than fought [E].
        """
        old = ship.side
        held = ship.crew if prisoners else 0
        if prisoners:
            ship.prisoners += held
        else:
            ship.stats.crew_lost += ship.crew          # the last defenders
        ship.mood = Mood()                            # a new crew, a new captain's mind
        ship.side = side
        ship.crew = ship.boarders
        ship.boarders = 0
        ship.boarder_side = -1
        ship.target = None
        ship.target_subsystem = None
        ship.desired_warp = 0.0
        ship.helm_mode = HelmMode.COURSE
        ship.status = ShipStatus.ACTIVE
        ship.life_failure_time = 0.0
        ship.repair_priority = None
        for b in ship.banks:
            b.lock = None
            b.enabled = True        # a surrendered ship's weapons were made safe; her new crew arms them again
        for t in ship.tubes:
            t.lock = None
            t.enabled = True
        # her old side's brains let go of her; the new side's take over (see `on_capture`)
        self.controllers = [c for c in self.controllers if getattr(c, "ship_id", None) != ship.id]
        self.ally_orders.pop(ship.id, None)
        for intel in self.intel.values():
            c = intel.contacts.get(ship.id)
            if c is not None:
                c.assessed = None
        self.emit(ShipStatusChanged(self.tick, ship.id, ShipStatus.CAPTURED.value, f"captured from side {old}", None))
        if held:
            self.emit(Message(self.tick, f"{ship.name} has been taken without a fight by the "
                              f"{self.side_names.get(side, 'boarders')}. Her crew of {held} are prisoners of war, held "
                              f"under guard; a prize crew of {ship.crew} has her.", Tone.GOOD, ship_id=ship.id))
        else:
            self.emit(Message(self.tick, f"{ship.name} has been captured by the {self.side_names.get(side, 'boarders')}! "
                              f"A prize crew of {ship.crew} holds her.", Tone.ALERT, ship_id=ship.id))
        if self.on_capture is not None:
            self.on_capture(ship)

    def _escapes(self, dt: float) -> None:
        r = self.rules
        for s in self.ships.values():
            if not s.alive or s.cls.is_base or s.docked_to is not None:
                s.escape_time = 0.0  # bases can't leave, and a docked ship goes where its base goes
                continue
            enemies = [e for e in self.ships.values() if e.alive and e.side != s.side]
            if not enemies:
                s.escape_time = 0.0
                continue
            nearest = min(math.hypot(e.x - s.x, e.y - s.y) for e in enemies)
            home = any(b.alive and b.side == s.side and b.cls.is_base and math.hypot(b.x - s.x, b.y - s.y) < r.escape_distance / 2
                       for b in self.ships.values())
            if nearest > r.escape_distance and not home:   # a ship guarding her base hasn't left [E]
                s.escape_time += dt
                if s.escape_time >= r.escape_cycles:
                    self._set_status(s, ShipStatus.ESCAPED, "escaped", None,
                                     f"{s.name} has left the battle area.", Tone.CAUTION)
            else:
                s.escape_time = 0.0

    def _prize_open(self, alive_sides: set[int]) -> bool:
        """The last enemy is a derelict or has struck her colours: the victor has a while to board her [E]."""
        prizes = [s for s in self.ships.values() if s.exists and s.side not in alive_sides
                  and s.status in (ShipStatus.DERELICT, ShipStatus.SURRENDERED) and not s.cls.is_base]
        fighting = any(s.boarders > 0 for s in self.ships.values() if s.exists)
        if (not prizes and not fighting) or self.player_side not in alive_sides:
            return False
        if self._prize_since < 0:
            self._prize_since = self.time
            names = ", ".join(s.name for s in prizes)
            if prizes:
                self.emit(Message(self.tick, f"{names} lies helpless. You have {self.rules.prize_window:.0f} cycles to "
                                  "board and take her, or the battle ends.", Tone.CAUTION))
        return fighting or self.time - self._prize_since < self.rules.prize_window

    def _check_outcome(self) -> None:
        sides = {s.side for s in self.ships.values() if s.alive}
        all_sides = {s.side for s in self.ships.values()}
        if len(all_sides) < 2 or len(sides) > 1:
            return
        if waves_pending(self) and self.player_side in sides:
            return          # the next wave is on its way: the lull is a breather, not the end
        if self._prize_open(sides):
            return
        o = self.outcome
        o.over = True
        o.tick = self.tick
        if sides:
            o.winner = next(iter(sides))
            o.reason = f"{self.side_names.get(o.winner, 'Side ' + str(o.winner))} holds the field."
        else:
            o.winner = None
            o.reason = "No combatants remain."
        self.emit(Message(self.tick, f"Battle over: {o.reason}", Tone.INFO))

    def end_simulation(self, reason: str = "Simulation ended by the captain.") -> None:
        """Begin's `quit`: stop at the end of the current cycle and go to the evaluation."""
        if self.outcome.over:
            return
        o = self.outcome
        o.over = True
        o.tick = self.tick
        o.winner = None
        o.reason = reason
        self.emit(Message(self.tick, reason, Tone.INFO))

    # ------------------------------------------------------------ queries

    def ships_of(self, side: int, alive_only: bool = True) -> list[Ship]:
        return [s for s in self.ships.values() if s.side == side and (s.alive if alive_only else s.exists)]

    def sides(self) -> list[int]:
        return sorted({s.side for s in self.ships.values()})


__all__ = ["Controller", "LoggedCommand", "Outcome", "PendingScan", "World"]
