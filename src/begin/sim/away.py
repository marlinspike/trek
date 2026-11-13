"""Away teams [E]: officers who cross to a Borg ship to do what no weapon can.

Two ways across. A **shuttle** (`AwayTeam(by_shuttle=True)`) flies out from the ship and latches onto the hive
ship's hull. It works because the Borg ignore what doesn't threaten them, so it is safe only while something
bigger keeps them busy: if the ship that sent it goes quiet (no hits on the hive for a while, or cloaked), the
hive may notice the little craft. The **transporter** works only on a dormant ship within beaming range: her
shields are down and nobody aboard is awake to stop it.

Aboard, the team works at a task (`TASKS`): putting the vinculum relay out (her drones go dormant), stealing the
hive's shield harmonics (every weapon of our side passes their shields until they notice; Seven must be there),
wrecking her weapons, planting charges, a survey from inside (her shield harmonics and weak point), or, on a
dormant ship, bringing a drone home (the Doctor learns from them). The captain can hail the shuttle at any time
to change the task or call the team back (`ShuttleOrder`).

A team that is found out, or still aboard when the drones wake, never dies: they beam out, hurt, and spend a while in
sickbay until the Doctor sends them back (`MEND_CYCLES`). Stand-ins cover their stations (crew/officers.py).
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ..core.angles import bearing
from . import collective
from .events import HiveEvent, Message, Tone
from .ship import HelmMode, Ship, ShipStatus

if TYPE_CHECKING:
    from .world import World

# task -> (cycles of work aboard, what it is called, needs the ship dormant)
TASKS: dict[str, tuple[float, str, bool]] = {
    "relay": (12.0, "putting out her vinculum relay", False),
    "harmonics": (18.0, "taking the Collective's shield harmonics", False),
    "weapons": (12.0, "wrecking her weapons", False),
    "charges": (15.0, "planting charges", False),
    "survey": (10.0, "surveying her from inside", False),
    "rescue": (10.0, "bringing a drone home", True),
}
TASK_WORDS = {
    "relay": ("relay", "vinculum", "sabotage", "sleep", "dormant", "knock out", "put them to sleep"),
    "harmonics": ("harmonics", "steal", "shield code", "codes", "frequencies"),
    "weapons": ("weapons", "guns", "cutting beams", "disarm", "phasers", "disable weapons"),
    "charges": ("charges", "bomb", "bombs", "explosives", "blow", "self-destruct", "destroy"),
    "survey": ("survey", "scan", "study", "look around"),
    "rescue": ("rescue", "drone", "bring one", "prisoner", "abduct"),
}
LATCH_RANGE = 1300.0          # the shuttle latches on this close
HOME_RANGE = 1100.0           # ... and is taken back aboard this close to her ship
QUIET_CYCLES = 12.0           # no hits on the hive for this long and the decoy has gone quiet
NOTICE_QUIET = 0.07           # per cycle, while the decoy is quiet or cloaked
NOTICE_BASE = 0.006           # per cycle, while the decoy keeps them busy
NOTICE_REPEAT = 0.018         # per cycle, × earlier crossings this battle: they start watching small craft
CHARGE_FUSE = 8.0             # cycles from the team leaving to the charges going off
MEND_CYCLES = 75.0            # cycles the Doctor keeps a hurt away team in sickbay
SHUTTLE_NAMES = ("Galileo", "Copernicus", "Columbus", "Shenandoah", "Kepler", "Cochrane")


@dataclass
class AwayOp:
    mother: int                       # the ship that sent them
    target: int                       # the hive ship
    members: tuple[str, ...]          # officer ids
    task: str
    shuttle: int | None = None        # the shuttle's ship id (None: they beamed across)
    phase: str = "outbound"           # outbound | aboard | return | done
    work: float = 0.0                 # cycles of work left aboard
    noticed: bool = False
    recalled: bool = False
    result: str = ""                  # what came of it, in a few words
    started: int = 0                  # tick they set out

    @property
    def label(self) -> str:
        return TASKS[self.task][1]


def task_from_words(text: str) -> str | None:
    low = text.lower()
    for task, words in TASK_WORDS.items():
        if any(w in low for w in words):
            return task
    return None


def has_shuttles(ship: Ship) -> bool:
    """Big Federation ships carry shuttles."""
    return ship.faction == "federation" and ship.cls.crew >= 300 and not ship.cls.craft


def op_for(world: World, ship_id: int) -> AwayOp | None:
    """The away team a ship sent, or the one a shuttle carries."""
    for op in world.away_ops:
        if op.phase != "done" and (op.mother == ship_id or op.shuttle == ship_id):
            return op
    return None


def launch(world: World, mother: Ship, target: Ship, members: tuple[str, ...], task: str, by_shuttle: bool) -> AwayOp:
    op = AwayOp(mother.id, target.id, members, task, started=world.tick)
    op.work = TASKS[task][0] * (0.75 if "seven" in members and task in ("harmonics", "survey", "relay") else 1.0)
    mother.away |= set(members)
    ins = collective.insight(world, mother.side)
    if by_shuttle:
        brg = bearing(target.x - mother.x, target.y - mother.y)
        r = math.radians(brg)
        sx, sy = mother.x + math.sin(r) * 260.0, mother.y + math.cos(r) * 260.0
        used = sum(1 for o in world.away_ops if o.shuttle is not None)
        sh = world.add_ship("federation.sh", mother.side, sx, sy, course=brg, warp=0.0,
                            name=SHUTTLE_NAMES[used % len(SHUTTLE_NAMES)])
        sh.crew = len(members) + 2
        op.shuttle = sh.id
        _fly(sh, target, sh.cls.max_warp)
        world.emit(HiveEvent(world.tick, target.id, "shuttle", sh.id, task))
        world.say(mother, f"Shuttle {sh.name} away: {_names(members)}, {op.label}.", "good", speaker="Flight deck")
    else:
        op.phase = "aboard"
        ins.heists += 1
        world.emit(HiveEvent(world.tick, target.id, "boarded", mother.id, task))
        world.say(mother, f"Away team beamed aboard {target.name}: {_names(members)}, {op.label}.", "good",
                  speaker="Transporter room")
    world.away_ops.append(op)
    return op


def order(world: World, op: AwayOp, what: str, task: str = "") -> str:
    """The captain's word to the team over the comm: a new task, or come home. Returns their answer."""
    if what == "recall":
        if op.phase in ("return", "done"):
            return "We're already on our way back, Captain."
        op.recalled = True
        _head_home(world, op, "recalled")
        return "Understood. Breaking off and coming home."
    if task not in TASKS:
        return "Say again, Captain?"
    if task == "harmonics" and "seven" not in op.members:
        return "We'd need Seven for that, Captain."
    tgt = world.ships.get(op.target)
    if TASKS[task][2] and (tgt is None or tgt.dormant <= 0):
        return "Not while they're awake, Captain."
    op.task = task
    op.work = TASKS[task][0]
    return f"Acknowledged. We're {op.label}."


def update_away(world: World, dt: float) -> None:
    for op in world.away_ops:
        if op.phase != "done":
            _step(world, op, dt)


def _step(world: World, op: AwayOp, dt: float) -> None:
    mother = world.ships.get(op.mother)
    target = world.ships.get(op.target)
    sh = world.ships.get(op.shuttle) if op.shuttle is not None else None
    if op.shuttle is not None and (sh is None or not sh.alive):
        _caught(world, op, "the shuttle was destroyed")
        return
    if mother is None or not mother.alive:
        _finish(world, op)
        return
    if op.phase == "outbound":
        if target is None or not target.alive:
            _head_home(world, op, "the target is gone")
            return
        assert sh is not None
        _fly(sh, target, sh.cls.max_warp)
        if math.hypot(sh.x - target.x, sh.y - target.y) <= LATCH_RANGE:
            op.phase = "aboard"
            sh.docked_to = target.id
            sh.desired_warp = 0.0
            collective.insight(world, mother.side).heists += 1
            world.emit(HiveEvent(world.tick, target.id, "boarded", sh.id, op.task))
            world.say(mother, f"{sh.name} has latched on to {target.name}. The team is aboard: {op.label}.", "good",
                      speaker=_lead(op))
        return
    if op.phase == "aboard":
        if target is None or not target.alive:
            _head_home(world, op, "the ship came apart around them")
            return
        if TASKS[op.task][2] and target.dormant <= 0:
            _caught(world, op, "the drones woke")
            return
        if target.dormant <= 0 and world.rng.unit() < _notice_chance(world, op, mother) * dt:
            _caught(world, op, "a drone found them")
            return
        if target.dormant > 0 and target.dormant < dt * 1.5 and op.work > dt:
            _caught(world, op, "the drones woke")
            return
        op.work -= dt
        if op.work <= 0:
            _done(world, op, mother, target)
        return
    if op.phase == "return":
        if sh is None:
            _finish(world, op)
            return
        _fly(sh, mother, sh.cls.max_warp)
        if math.hypot(sh.x - mother.x, sh.y - mother.y) <= HOME_RANGE:
            _stow(world, sh, mother)
            _finish(world, op)


def decoy_quiet(world: World, mother: Ship, faction: str) -> bool:
    """The ship that sent them has stopped hurting the hive (or vanished under a cloak): nothing else to watch."""
    m = world.minds.get(faction)
    last = m.last_hurt.get(mother.side, -10**9) if m is not None else -10**9
    return mother.cloaked or (world.tick - last) * world.rules.dt >= QUIET_CYCLES


def _notice_chance(world: World, op: AwayOp, mother: Ship) -> float:
    tgt = world.ships.get(op.target)
    quiet = decoy_quiet(world, mother, tgt.faction if tgt is not None else "")
    ins = collective.insight(world, mother.side)
    return (NOTICE_QUIET if quiet else NOTICE_BASE) + NOTICE_REPEAT * max(0, ins.heists - 1) + 0.02 * ins.vigilance


def _done(world: World, op: AwayOp, mother: Ship, target: Ship) -> None:
    ins = collective.insight(world, mother.side)
    rules = collective.rules_of(world, target)
    lead = _lead(op)
    if op.task == "relay":
        sub = target.subsystem(target.weak_point)
        if sub is not None:
            world.destroy_subsystem(target, sub, "sabotaged")
        op.result = "relay out"
        world.say(mother, f"The vinculum relay is out. {target.name}'s drones are going dormant.", "good", speaker=lead)
    elif op.task == "harmonics":
        ins.harmonics = rules.grace if rules is not None else 14
        ins.harmonic_faction = target.faction
        op.result = "harmonics taken"
        world.emit(HiveEvent(world.tick, target.id, "harmonics", mother.id))
        world.say(mother, "I have the Collective's shield harmonics, Captain. Every weapon we have will pass their "
                          "shields, on every ship, until they notice. Make each shot count.", "good",
                  speaker="Seven of Nine")
    elif op.task == "weapons":
        for w in (*target.banks, *target.tubes):
            if not w.destroyed:
                w.damage = 100
                w.repair_progress = 0.0
                w.on_damaged()
        op.result = "weapons wrecked"
        world.say(mother, f"{target.name}'s weapons are wrecked. They will regenerate them, but not quickly.", "good",
                  speaker=lead)
    elif op.task == "charges":
        target.self_destruct = CHARGE_FUSE
        target.last_attacker = mother.id
        op.result = "charges set"
        world.say(mother, f"Charges set aboard {target.name}. They go in {CHARGE_FUSE:.0f} seconds: get clear.",
                  "good", speaker=lead)
    elif op.task == "survey":
        sv = ins.survey(target.id)
        sv.progress = max(sv.progress, collective.CODE_AT)
        sv.weak_told = sv.code_told = False
        collective.on_scan(world, mother, target, "seven")      # the findings, as a scan reports them
        op.result = "survey done"
    elif op.task == "rescue":
        mother.rescued += 1
        ins.experience += 0.25
        op.result = "drone rescued"
        world.say(mother, "We have one of them, Captain: a young drone, cut off from the hive. The Doctor is "
                          "waiting for him in sickbay.", "good", speaker=lead)
    world.emit(HiveEvent(world.tick, target.id, "done", mother.id, op.task))
    _head_home(world, op, "")


def _caught(world: World, op: AwayOp, why: str) -> None:
    mother = world.ships.get(op.mother)
    op.noticed = True
    op.result = f"caught: {why}"
    if mother is not None:
        mother.wounded |= set(op.members)
        mother.mending = MEND_CYCLES
        world.emit(HiveEvent(world.tick, op.target, "caught", mother.id, why))
        world.say(mother, f"The away team is in trouble: {why}. We beamed them out, hurt. "
                          f"{_names(op.members)} are in sickbay.", "alert", speaker="Transporter room")
    sh = world.ships.get(op.shuttle) if op.shuttle is not None else None
    if sh is not None and sh.alive:
        sh.docked_to = None
        sh.crew = 2
        tgt = world.ships.get(op.target)
        if tgt is not None:
            collective.mind(world, tgt.faction).noticed.add(sh.id)
        op.members = ()
        op.phase = "return"
        return
    _finish(world, op)


def _head_home(world: World, op: AwayOp, why: str) -> None:
    sh = world.ships.get(op.shuttle) if op.shuttle is not None else None
    mother = world.ships.get(op.mother)
    if why and mother is not None:
        world.say(mother, f"Away team coming home: {why}.", "info", speaker=_lead(op))
    if sh is None:
        _finish(world, op)
        return
    sh.docked_to = None
    op.phase = "return"


def _finish(world: World, op: AwayOp) -> None:
    mother = world.ships.get(op.mother)
    if mother is not None:
        mother.away -= set(op.members)
        if op.members and op.result and not op.noticed:
            world.say(mother, f"{_names(op.members)} back aboard.", "good", speaker="Flight deck")
    op.phase = "done"


def _stow(world: World, sh: Ship, mother: Ship) -> None:
    """The shuttle is back in her bay: she leaves the battle quietly."""
    sh.status = ShipStatus.ESCAPED
    sh.desired_warp = 0.0
    sh.docked_to = None
    world.emit(Message(world.tick, f"Shuttle {sh.name} is back aboard {mother.name}.", Tone.GOOD,
                       speaker="Flight deck", ship_id=mother.id, visible_to=frozenset({mother.side})))


def _fly(sh: Ship, to: Ship, warp: float) -> None:
    sh.helm_mode = HelmMode.PURSUE
    sh.helm_target = to.id
    sh.desired_warp = warp


def _lead(op: AwayOp) -> str:
    return {"worf": "Lieutenant Worf", "seven": "Seven of Nine"}.get(op.members[0], "Away team") if op.members \
        else "Away team"


def _names(members: tuple[str, ...]) -> str:
    names = [{"worf": "Worf", "seven": "Seven", "spock": "Spock", "geordi": "Geordi", "doctor": "the Doctor",
              "sulu": "Sulu", "chekov": "Chekov"}
             .get(m, m.title()) for m in members]
    return " and ".join(names) if len(names) <= 2 else ", ".join(names[:-1]) + " and " + names[-1]


__all__ = ["AwayOp", "HOME_RANGE", "LATCH_RANGE", "TASKS", "TASK_WORDS", "has_shuttles", "launch", "op_for",
           "decoy_quiet", "order", "task_from_words", "update_away"]
