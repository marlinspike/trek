"""The Collective [E]: how the Borg fight, and how a crew learns to fight them.

Everything here applies only to a faction with `collective` rules (factions.toml). The idea is one rule: the
Borg punish attrition. They learn the weapons that hurt them, grow back what is cut away, and take crews rather
than kill them, so trading shots loses. What wins is learning first and then landing a decisive blow.

**Adaptation.** Each hive in a battle keeps one `Mind`, shared by all its ships: a level from 0 to 1 for every
weapon that has hurt it, keyed by weapon family and by the side (and, for phasers, the frequency) that fired it.
Every hit teaches them in proportion to the damage it carried (`CollectiveRules.adapt` is the damage that
teaches them completely), and a weapon they have learned does `1 - (1 - floor) × level` of its damage. Potshots
teach them for free; a held, massed volley lands before they can answer. A remodulated phaser is a new
frequency starting at zero, but each one is learned faster than the last (`relearn`), less so when Seven's
random pattern chose it (`Ship.freq_pattern`).

**Our shields.** An officer on the "shields" duty tunes our shield harmonics against the hive's beams
(`Ship.tuning`, up to `tune_cut` off their damage). Tuned past half, the shields also stop their transporters.
The hive answers: once our tuning has turned aside `shift_after` damage, they shift their beam's frequency and
the tuning falls back.

**What scans teach us.** Each scan of a hive ship by our side adds to a `Survey` of her: Seven learns most from
each, the captain least. Half way, we know her weak point: an innocent-looking system that carries her vinculum
relay. All the way, we hold her shield harmonics, and harmonic torpedoes go straight through her shields.

**The weak point.** Destroy it and her drones fall dormant for `sleep_cycles`: no weapons, no shields, no
helm, no regeneration, no learning. Then she can be boarded (sim/away.py) or taken apart: a drive or reactor
destroyed while she sleeps sets off a chain reaction (awake, only `chain` of the time). When she wakes the relay
has been rerouted through another system, and what we knew of it is gone.

**A strike through an opening.** Fire aimed at one system that reaches a hive ship's hull without touching a
shield (her harmonics, stolen or cracked, or a facing whose shield is down or destroyed) is not a sweep through a
city of drones: the gunners can see exactly what they are hitting. It wrecks the system (`strike_*` rules), the
drones mend it slowly, and a drive or reactor it destroys can set her off however whole her hull. So power wins
against a cube when guile opens the way first: find the harmonics or batter one facing down, then put a full salvo
into her shields, her drives or her crew decks. Under a cloak she can neither beam drones to us nor lock her beams
on, so cloak, strike and cloak again finishes a crippled ship.

**Stolen harmonics.** An away team that takes the hive's shield harmonics (sim/away.py) lets every weapon of our
side pass their shields untouched and unlearned, for `grace` hits; then they notice, and the theft is spent.

**Drones.** A hive ship beams drones through shields (unless they are tuned against her). Aboard, every
defender they beat becomes a drone unless the Doctor's inoculation holds, and established drones seize systems
one by one unless Spock has encrypted the computer or Seven has severed them from the hive. Security teams and
sealed sections fight them; once the last is gone the seized systems come back, damaged.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ..content.schema import CollectiveRules
from .events import HiveEvent, Message, Tone
from .ship import Kind, Ship, ShipStatus, Subsystem

if TYPE_CHECKING:
    from .world import World

FAMILIES = ("phaser", "torpedo", "harmonic", "probe")
THRESHOLDS = (0.5, 0.85)                  # adaptation levels the officers call out
SKILL = {"seven": 1.0, "spock": 0.75}     # how much an officer gets from the hive's tricks; anyone else 0.5
SURVEY_STEP = 0.2                         # survey per scan, × skill × experience
WEAK_AT = 0.5                             # survey at which we know her weak point
CODE_AT = 1.0                             # ... and hold her shield harmonics
TUNE_CYCLES = 24.0                        # cycles for Seven to tune the shields from nothing to full
TUNE_BLOCKS_BEAMING = 0.5                 # tuning at which their transporters can't lock on
SECURITY_CYCLES = 20.0
SEAL_COOLDOWN = 40.0
REMODULATE_CYCLES = 1.5
CHAIN_FUSE = 5.0                          # cycles from a core going critical to the ship breaking up
CHAIN_RADIUS = 1.2                        # × an ordinary blast's reach: a cube's core going is seen for light-years
CHAIN_HULL = 0.5                          # awake, only a ship this badly hurt can go up from one lost core
RELEARN_CAP = 3                           # frequencies learned before they learn new ones no faster
DRONES_SETTLE = 4                         # drones aboard before they start seizing systems
# drones go for the ship's eyes and hands first, her heart last
SEIZE_ORDER = (Kind.TRANSPORTER, Kind.SENSORS, Kind.SHIELD, Kind.TUBE, Kind.PHASER, Kind.LAUNCHER, Kind.TRACTOR,
               Kind.IMPULSE, Kind.DRIVE, Kind.BATTERY, Kind.REACTOR, Kind.COMPUTER)


def skill(officer: str) -> float:
    return SKILL.get(officer, 0.5)


@dataclass
class Mind:
    """One hive's memory in this battle: what it has adapted to and who has hurt it."""

    faction: str
    levels: dict[str, float] = field(default_factory=dict)      # weapon key -> 0..1
    called: set[str] = field(default_factory=set)               # "key@threshold" already announced
    threat: dict[int, float] = field(default_factory=dict)      # enemy ship -> damage it has done us (decays)
    blocked: float = 0.0                                        # damage our tuned shields turned aside
    noticed: set[int] = field(default_factory=set)              # small craft the hive has noticed
    carried: dict[str, float] = field(default_factory=dict)     # levels it arrived with (a tour's memory)
    last_hurt: dict[int, int] = field(default_factory=dict)     # side -> tick it last hurt us

    def level(self, key: str) -> float:
        return self.levels.get(key, 0.0)

    def family_level(self, family: str, side: int) -> float:
        """The best level against any weapon of this family from this side (what the officers report)."""
        pre = f"{family}:{side}"
        return max((v for k, v in self.levels.items() if k == pre or k.startswith(pre + ":")), default=0.0)


@dataclass
class Survey:
    progress: float = 0.0       # 0..CODE_AT
    weak_told: bool = False
    code_told: bool = False


@dataclass
class Insight:
    """What one side has learned of the hives it faces."""

    surveys: dict[int, Survey] = field(default_factory=dict)    # hive ship -> what our scans have shown
    harmonics: int = 0                                          # hits left with stolen harmonics
    harmonic_faction: str = ""
    experience: float = 1.0                                     # × each scan's worth (a tour's learning)
    heists: int = 0                                             # times an away team has got aboard this battle
    vigilance: float = 0.0                                      # how hard the hive watches small craft (a tour's crossings)

    def survey(self, ship_id: int) -> Survey:
        return self.surveys.setdefault(ship_id, Survey())

    def knows_weak(self, ship_id: int) -> bool:
        s = self.surveys.get(ship_id)
        return s is not None and s.progress >= WEAK_AT

    def has_code(self, ship_id: int) -> bool:
        s = self.surveys.get(ship_id)
        return s is not None and s.progress >= CODE_AT


# ------------------------------------------------------------------ who is a hive

def rules_of(world: World, ship: Ship) -> CollectiveRules | None:
    f = world.content.factions.get(ship.faction)
    return f.collective if f is not None else None


def is_hive(world: World, ship: Ship) -> bool:
    return rules_of(world, ship) is not None


def mind(world: World, faction: str) -> Mind:
    return world.minds.setdefault(faction, Mind(faction))


def insight(world: World, side: int) -> Insight:
    return world.insight.setdefault(side, Insight())


def weapon_key(family: str, attacker: Ship | None) -> str:
    if attacker is None:
        return ""
    if family == "phaser":
        return f"phaser:{attacker.side}:{attacker.phaser_freq}"
    return f"{family}:{attacker.side}"


# ------------------------------------------------------------------ damage

def incoming(world: World, target: Ship, attacker: Ship | None, family: str) -> tuple[float, bool]:
    """(× damage, passes the shields) for a hit on `target` by `attacker` with a weapon of `family`."""
    if attacker is None or not family or attacker.side == target.side:
        return 1.0, False
    rules = rules_of(world, target)
    if rules is not None:
        ins = world.insight.get(attacker.side)
        if ins is not None and ins.harmonics > 0 and ins.harmonic_faction == target.faction:
            return 1.0, True                         # stolen harmonics: straight through, and nothing learned
        pierce = family == "harmonic" and ins is not None and ins.has_code(target.id)
        if family == "harmonic" and not pierce:
            family = "torpedo"                      # a harmonic round tuned to someone else: just a torpedo
        lvl = mind(world, target.faction).level(weapon_key(family, attacker))
        return 1.0 - (1.0 - rules.floor) * lvl, pierce
    att_rules = rules_of(world, attacker)
    if att_rules is not None and target.tuning > 0.0:
        return 1.0 - att_rules.tune_cut * target.tuning, False
    return 1.0, False


def learn(world: World, target: Ship, attacker: Ship | None, family: str, raw: float, landed: float) -> None:
    """After a hit: the hive learns from it, or counts what our tuned shields turned aside."""
    if attacker is None or not family or attacker.side == target.side:
        return
    rules = rules_of(world, target)
    if rules is not None:
        target.last_attacker = attacker.id
        m = mind(world, target.faction)
        m.last_hurt[attacker.side] = world.tick
        m.threat[attacker.id] = m.threat.get(attacker.id, 0.0) + landed
        ins = world.insight.get(attacker.side)
        if ins is not None and ins.harmonics > 0 and ins.harmonic_faction == target.faction:
            ins.harmonics -= 1
            if ins.harmonics == 0:
                world.emit(HiveEvent(world.tick, target.id, "noticed", attacker.id))
            return
        if target.dormant > 0:
            return                                   # asleep: nothing is learned
        if family == "harmonic" and not (ins is not None and ins.has_code(target.id)):
            family = "torpedo"
        key = weapon_key(family, attacker)
        teach = rules.adapt.get(family, 0.0)
        if teach <= 0:
            return
        speed = 1.0
        if family == "phaser":
            mastered = sum(1 for k, v in m.levels.items()
                           if k.startswith(f"phaser:{attacker.side}:") and k != key and v >= 0.5)
            speed += rules.relearn * min(mastered, RELEARN_CAP) * attacker.freq_pattern
        before = m.level(key)
        after = min(1.0, before + raw / teach * speed)
        m.levels[key] = after
        for th in THRESHOLDS:
            tag = f"{key}@{th}"
            if before < th <= after and tag not in m.called:
                m.called.add(tag)
                world.emit(HiveEvent(world.tick, target.id, "adapted", attacker.id, f"{family}:{th}"))
        return
    att_rules = rules_of(world, attacker)
    if att_rules is not None and target.tuning > 0.0 and landed < raw:
        m = mind(world, attacker.faction)
        m.blocked += raw - landed
        if m.blocked >= att_rules.shift_after * (0.6 + 0.6 * skill(target.duty_by)):
            m.blocked = 0.0
            for s in world.ships.values():
                if s.side == target.side and s.tuning > 0:
                    s.tuning *= 0.35
            world.emit(HiveEvent(world.tick, attacker.id, "shift", target.id, target.duty_by))


def strike_rules(world: World, target: Ship, attacker: Ship | None) -> CollectiveRules | None:
    """The hive's rules when aimed fire from `attacker` that reached `target`'s hull untouched by a shield is a
    strike through an opening; None when `target` is no hive ship, or the fire was not an enemy's."""
    if attacker is None or attacker.side == target.side:
        return None
    return rules_of(world, target)


def struck(world: World, ship: Ship, sub: Subsystem, rules: CollectiveRules, attacker: int | None) -> None:
    """A strike through an opening hit `sub`: it is slow to mend, and if it is wrecked the bridge hears of it. A
    drive or reactor wrecked this way can set her off, however whole her hull."""
    sub.struck = True
    if not sub.destroyed:
        return
    world.emit(HiveEvent(world.tick, ship.id, "struck", attacker, sub.label))
    if sub.kind in (Kind.DRIVE, Kind.REACTOR) and ship.critical <= 0 and ship.dormant <= 0 \
            and world.rng.unit() < rules.strike_chain:
        ship.critical = CHAIN_FUSE
        world.emit(HiveEvent(world.tick, ship.id, "critical", attacker, f"{CHAIN_FUSE:.0f}"))


# ------------------------------------------------------------------ scans

def on_scan(world: World, ship: Ship, target: Ship, by: str) -> None:
    """A completed scan of a hive ship adds to what our side knows of her."""
    if not is_hive(world, target) or ship.side == target.side:
        return
    ins = insight(world, ship.side)
    sv = ins.survey(target.id)
    if sv.progress >= CODE_AT:
        return
    sv.progress = min(CODE_AT, sv.progress + SURVEY_STEP * skill(by) * ins.experience)
    found = ""
    if sv.progress >= WEAK_AT and not sv.weak_told and target.weak_point:
        sv.weak_told = True
        found = "weak"
    if sv.progress >= CODE_AT and not sv.code_told:
        sv.code_told = True
        found = "code"
    # the bridge says what was found (crew/borg_talk.py): `detail` is "<found or progress>|<who scanned>"
    world.emit(HiveEvent(world.tick, target.id, "surveyed", ship.id, f"{found or f'{sv.progress:.2f}'}|{by}"))


# ------------------------------------------------------------------ setup and each tick

def commission(world: World, ship: Ship) -> None:
    """A hive ship joins the battle: hide her vinculum relay in one of her minor systems."""
    rules = rules_of(world, ship)
    if rules is None:
        return
    ship.weak_point = _pick_weak(world, ship, rules, exclude="")
    ship.morale = ship.morale_base = 100.0
    mind(world, ship.faction)


def _pick_weak(world: World, ship: Ship, rules: CollectiveRules, exclude: str) -> str:
    options = [s for s in ship.subsystems() if s.kind.value in rules.weak_kinds and s.sid != exclude and not s.destroyed]
    if not options:
        options = [s for s in ship.subsystems() if s.sid != exclude and s.kind not in (Kind.SHIELD,)]
    rng = world.rng.derive(f"vinculum:{ship.id}:{world.tick}")
    return rng.choice(options).sid if options else ""


def update(world: World, dt: float) -> None:
    """Once a tick: dormancy, regeneration, the weak point and chain reactions, our tuning, boarding cooldowns."""
    for ship in list(world.ships.values()):
        if not ship.exists:
            continue
        rules = rules_of(world, ship)
        if rules is not None:
            _hive_ship(world, ship, rules, dt)
        else:
            _our_ship(world, ship, dt)
    for m in world.minds.values():
        for k in list(m.threat):
            m.threat[k] *= 1.0 - 0.02 * dt
            if m.threat[k] < 1.0 or k not in world.ships or not world.ships[k].alive:
                del m.threat[k]


def _hive_ship(world: World, ship: Ship, rules: CollectiveRules, dt: float) -> None:
    if not ship.alive:
        return
    ship.beam_ready = max(0.0, ship.beam_ready - dt)
    # the relay failed: the drones fall asleep
    weak = ship.subsystem(ship.weak_point) if ship.weak_point else None
    if ship.dormant <= 0 and weak is not None and weak.destroyed:
        ship.dormant = rules.sleep_cycles
        world.emit(HiveEvent(world.tick, ship.id, "dormant", ship.last_attacker, f"{rules.sleep_cycles:.0f}"))
    if ship.dormant > 0:
        _dark(ship)
        ship.dormant -= dt
        if ship.dormant <= 0:
            ship.dormant = 0.0
            for sh in ship.shields:
                sh.up = True
            old = ship.weak_point
            if weak is not None and weak.destroyed:
                weak.damage = 60
                weak.repair_progress = 0.0
            ship.weak_point = _pick_weak(world, ship, rules, exclude=old)
            for side, ins in world.insight.items():
                sv = ins.surveys.get(ship.id)
                if sv is not None and sv.progress >= WEAK_AT:
                    sv.progress = min(sv.progress, WEAK_AT - 0.01)
                    sv.weak_told = False
                    sv.code_told = sv.code_told and sv.progress >= CODE_AT
            world.emit(HiveEvent(world.tick, ship.id, "waking"))
    else:
        m = world.minds.get(ship.faction)
        hurt = max(m.last_hurt.values(), default=-10 ** 9) if m is not None else -10 ** 9
        rate = rules.regen_hull * (rules.regen_hurt if (world.tick - hurt) * world.rules.dt < rules.regen_quiet else 1.0)
        ship.structure = min(ship.structure_max, ship.structure + rate * ship.structure_max * dt)
    # a destroyed core can take the whole ship with it: she goes critical, and breaks up a few seconds later
    if ship.critical > 0:
        ship.critical -= dt
        if ship.critical <= 0:
            chain_reaction(world, ship)
            return
    cores = sum(1 for s in (*ship.drives, *ship.reactors) if s.destroyed)
    if cores > ship.cores_lost:
        fresh = cores - ship.cores_lost
        ship.cores_lost = cores
        hurt = ship.structure < ship.structure_max * CHAIN_HULL
        p = 1.0 if ship.dormant > 0 else rules.chain if hurt else 0.0
        if ship.critical <= 0 and any(world.rng.unit() < p for _ in range(fresh)):
            ship.critical = CHAIN_FUSE
            world.emit(HiveEvent(world.tick, ship.id, "critical", ship.last_attacker, f"{CHAIN_FUSE:.0f}"))
    elif cores < ship.cores_lost:
        ship.cores_lost = cores       # the drones repaired one


def _dark(ship: Ship) -> None:
    """A dormant hive ship: nothing aboard is awake to run her."""
    for sh in ship.shields:
        sh.up = False
        sh.effective = 0.0
    for b in ship.banks:
        b.charge = 0.0
    for t in ship.tubes:
        t.charge = 0.0
    ship.desired_warp = 0.0
    ship.tractor_target = None


def chain_reaction(world: World, ship: Ship) -> None:
    """Her core goes: the ship breaks up in a blast big enough to hurt anyone close."""
    from .systems.ordnance import blast

    rules = rules_of(world, ship)
    x, y = ship.x, ship.y
    world.emit(HiveEvent(world.tick, ship.id, "chain", ship.last_attacker))
    world.destroy_ship(ship, "chain reaction", ship.last_attacker, breakup=False)
    if rules is not None:
        blast(world, x, y, chain_energy(ship), "ship", ship.last_attacker, exclude=ship.id,
              cause="chain reaction", radius_scale=CHAIN_RADIUS)


def chain_energy(ship: Ship) -> float:
    return ship.cls.destruct_energy * 0.5


def _our_ship(world: World, ship: Ship, dt: float) -> None:
    if ship.wounded and ship.mending > 0:
        ship.mending -= dt
        if ship.mending <= 0:      # the Doctor sends them back to duty, against his better judgement
            ship.mending = 0.0
            back = ",".join(sorted(ship.wounded))
            ship.wounded = set()
            world.emit(HiveEvent(world.tick, ship.id, "mended", None, back))
    ship.remodulating = max(0.0, ship.remodulating - dt)
    ship.security = max(0.0, ship.security - dt)
    ship.seal_ready = max(0.0, ship.seal_ready - dt)
    if ship.duty == "shields" and ship.alive and ship.duty_by not in ship.away:
        ship.tuning = min(1.0, ship.tuning + dt / TUNE_CYCLES * skill(ship.duty_by))


# ------------------------------------------------------------------ drones

def can_beam_through(world: World, hive: Ship, target: Ship) -> str | None:
    """Why a hive ship can't beam drones onto `target` now (None: she can)."""
    if target.tuning >= TUNE_BLOCKS_BEAMING:
        return f"{target.name}'s shields are tuned against our transporters."
    if hive.dormant > 0:
        return "Dormant."
    return None


def board_round(world: World, ship: Ship, rules: CollectiveRules) -> None:
    """One cycle of drones against a crew: beaten defenders join the drones, unless inoculated."""
    level = world.content.factions[world_faction(world, ship.boarder_side)].dogma.boarding
    if ship.severed:
        level *= 0.5
    if ship.security > 0:
        level *= 0.6
    if ship.inoculated:
        level *= 0.8
    rounds = int(world.rng.unit() * ship.boarders) + 1
    for _ in range(rounds):
        if ship.boarders <= 0 or ship.crew <= 0:
            break
        if world.rng.unit() < level * (ship.boarders / (ship.boarders + ship.crew)) * 2:
            ship.crew -= 1
            if not ship.inoculated and world.rng.unit() < rules.assimilate:
                ship.boarders += 1
                ship.assimilated += 1
            else:
                ship.stats.crew_lost += 1
        else:
            ship.boarders -= 1
    if ship.boarders > 0 and not ship.encrypted and not ship.severed and ship.boarders >= DRONES_SETTLE:
        share = ship.boarders / max(1, ship.boarders + ship.crew)
        if world.rng.unit() < rules.takeover * (0.5 + share * 2.0):
            _seize(world, ship)
    if ship.boarders <= 0:
        ship.boarders = 0
        release(world, ship)


def world_faction(world: World, side: int) -> str:
    for s in world.ships.values():
        if s.side == side and is_hive(world, s):
            return s.faction
    return next((s.faction for s in world.ships.values() if s.side == side), "borg")


def _seize(world: World, ship: Ship) -> None:
    for kind in SEIZE_ORDER:
        free = [s for s in ship.subsystems() if s.kind == kind and not s.assimilated]
        if not free:
            continue
        sub = free[0]
        sub.assimilated = True
        sub.damage = 100
        sub.repair_progress = 0.0
        sub.on_damaged()
        if kind == Kind.CLOAK:
            ship.cloaked = False
        world.emit(HiveEvent(world.tick, ship.id, "seized", None, sub.label))
        world.emit(Message(world.tick, f"Drones have taken {sub.label.lower()}. It no longer answers.", Tone.ALERT,
                           speaker="Security", ship_id=ship.id, visible_to=frozenset({ship.side})))
        if kind == Kind.COMPUTER:
            world.emit(Message(world.tick, "They are in the main computer. We are losing the ship.", Tone.ALERT,
                               speaker="Security", ship_id=ship.id, visible_to=frozenset({ship.side})))
        return


def fresh(world: World, ship_id: int, callout: str, cycles: float) -> bool:
    """May this callout be said again? Each is said at most once every `cycles`, so a long fight stays calm."""
    key = (ship_id, callout)
    last = world.said.get(key)
    if last is not None and world.tick - last < cycles * world.rules.ticks_per_cycle:
        return False
    world.said[key] = world.tick
    return True


def release(world: World, ship: Ship) -> None:
    """The drones aboard are gone: every system they held comes back to us, damaged."""
    back = [s for s in ship.subsystems() if s.assimilated]
    for s in back:
        s.assimilated = False
        s.damage = 60
        s.repair_progress = 0.0
    ship.severed = False
    world.emit(HiveEvent(world.tick, ship.id, "repelled"))
    if not back and not fresh(world, ship.id, "repelled", 20.0):
        return
    extra = (f" {len(back)} systems are ours again, damaged." if len(back) > 1 else
             f" {back[0].label} is ours again, damaged." if back else "")
    world.emit(Message(world.tick, f"The last drones aboard {ship.name} have been stopped.{extra}", Tone.GOOD,
                       speaker="Security", ship_id=ship.id, visible_to=frozenset({ship.side})))


def seal_section(world: World, ship: Ship) -> tuple[int, int]:
    """Geordi seals the sections the drones hold and vents them: most of them die, and some of ours with them."""
    killed = int(math.ceil(ship.boarders * 0.45))
    ours = min(ship.crew - 6, max(1, int(ship.crew * 0.02))) if ship.crew > 6 else 0
    ship.boarders = max(0, ship.boarders - killed)
    ship.crew -= max(0, ours)
    ship.stats.crew_lost += max(0, ours)
    ship.seal_ready = SEAL_COOLDOWN
    if ship.boarders <= 0:
        release(world, ship)
    return killed, max(0, ours)


# ------------------------------------------------------------------ words

def survey_of(world: World, side: int, ship_id: int) -> Survey | None:
    ins = world.insight.get(side)
    return ins.surveys.get(ship_id) if ins is not None else None


def assimilated_ship(world: World, ship: Ship) -> None:
    """The drones hold the ship: she belongs to the hive now."""
    world.emit(HiveEvent(world.tick, ship.id, "assimilated"))
    world.emit(Message(world.tick, f"{ship.name} has been assimilated.", Tone.ALERT, ship_id=ship.id))


def dormant_or_dark(ship: Ship) -> bool:
    return ship.dormant > 0 or ship.status != ShipStatus.ACTIVE


__all__ = [
    "CODE_AT", "FAMILIES", "Insight", "Mind", "SKILL", "Survey", "TUNE_BLOCKS_BEAMING", "WEAK_AT", "board_round",
    "can_beam_through", "chain_reaction", "commission", "fresh", "incoming", "insight", "is_hive", "learn", "mind", "on_scan", "strike_rules", "struck",
    "release", "rules_of", "seal_section", "skill", "survey_of", "update", "weapon_key",
]
