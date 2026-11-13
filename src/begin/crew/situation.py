"""The battle as the bridge officers see it: one `Situation`, built from our side's `Observation` [E].

The counsel (crew/counsel.py) reasons from this and nothing else, so the officers know exactly what the AI and the
coach know: our own ship in full, the enemy as sensors, scans and our own hits have shown her, the mission, and
what Starfleet can still send. Building it changes nothing.

Every number here is one a captain could read off the panels; the point of gathering them is that each officer can
reason about all of them at once: whose envelope beats whose, which shield is freshest, how close a captain is to
giving way, how long the ward has.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field

from ..ai.captain import strength
from ..ai.computer import torpedo_envelope
from ..content.schema import ShipClass, TorpedoDef
from ..core.angles import bearing, norm360
from ..sim.observation import ContactView, Observation
from ..sim.ship import Ship
from ..sim.systems.disposition import Reading
from ..help.coach import HelpContext, Tip, tips as coach_tips

SHIELD_FACINGS = (0.0, 60.0, 300.0, 120.0, 240.0, 180.0)   # an enemy's shield sectors as scans number them
NEAR = 8000.0                     # ordnance this close is "inbound"
WATCH = 30000.0                   # contacts farther than this hardly matter to the next stretch of the fight


@dataclass(frozen=True)
class ShieldView:
    index: int                    # 0-based; the console counts from 1
    facing: float                 # degrees off our bow it covers
    effective: float              # 0..100 (0 when lowered or destroyed)
    up: bool
    destroyed: bool
    reinforced: bool


@dataclass(frozen=True)
class EnemyView:
    """One hostile contact, with everything the officers can say about her."""

    id: int
    name: str                     # what the console calls her ("Gr'oth", or "#12" before she is identified)
    cls: ShipClass | None
    faction: str                  # "" until identified
    range: float
    bearing: float                # absolute bearing from us
    rel: float                    # degrees off our bow
    closing: float                # units a cycle she is closing on us (negative: opening)
    threat: float                 # Begin's strength score, scaled by the hull we think she has left
    style: str                    # her navy's signature tactic: charge, feint, raid, hive, or ""
    visible: bool
    cloaked_hint: bool            # lost at close range: probably cloaked
    exhaust: bool                 # placed only by her plasma trail
    hull: float | None            # fraction left, from a scan or our hits
    shields: tuple[float, ...] | None    # % per sector from a scan or our hits (-1: down)
    shield_to_us: float | None    # % of the sector facing us
    weakest: int | None           # 0-based sector index of her weakest shield
    banks_ready: int | None       # from a scan
    tubes_loaded: int | None
    scanned: bool
    reading: Reading | None       # how her captain reads, when we can read her
    surrendered: bool
    withdrawing: bool
    our_env: tuple[float, float] | None    # our torpedo envelope against her (min, max)
    her_env: tuple[float, float] | None    # hers against us, with the torpedo her class carries
    her_phaser_range: float
    her_torpedo: TorpedoDef | None
    max_warp: float
    pd_discipline: float          # her navy's point-defense discipline (low: wastes banks on a lone torpedo)
    surrender_willingness: float
    hunter: bool = False          # going for the ward
    runner: bool = False          # running for the edge with her report
    hive: bool = False
    dormant: float = 0.0
    opening: str = ""             # a Borg ship's shields can be passed: "stolen", "harmonic" or ""
    weak_point: str | None = None
    adapted: float = 0.0          # how far she has learned our phasers (0..1)

    @property
    def handle(self) -> str:
        """Her name as typed at the console."""
        return self.name.lower()


@dataclass(frozen=True)
class AllyView:
    id: int
    name: str
    hull: float
    order: str                    # her standing order, in a word ("attack", "escort", "")
    tubes_loaded: int
    range: float


@dataclass(frozen=True)
class MissionView:
    kind: str                     # rescue | escort | intercept
    state: str                    # open | done | failed
    title: str
    ward_id: int | None = None
    ward_name: str = ""
    ward_x: float = 0.0
    ward_y: float = 0.0
    ward_range: float = math.inf  # from us
    ward_bearing: float = 0.0
    ward_hull: float = 1.0
    ward_shield: ShieldView | None = None    # our shield facing her
    aboard: int = 0
    saved: int = 0
    people: int = 0
    time_left: float | None = None
    beaming: bool = False
    blocked: str = ""
    to: tuple[float, float] = (0.0, 0.0)
    to_range: float = 0.0         # escort: the ward's distance from safety
    runner_id: int | None = None
    runner_escape: float | None = None      # intercept: cycles before the runner is clear at her speed
    runner_intercept: float | None = None   # intercept: the course that meets her at our best warp (None: we can't)
    runner_meet: float | None = None        # intercept: cycles to meet her on that course
    hunter_ids: tuple[int, ...] = ()


@dataclass(frozen=True)
class Situation:
    """Our side's picture of the fight, now."""

    time: float
    ship: Ship
    name: str
    faction: str
    hull: float                   # fraction left
    crew: int
    morale: float
    shields: tuple[ShieldView, ...]
    facing: ShieldView | None     # toward the main threat
    freshest: ShieldView | None
    battery: float                # fraction of capacity
    power_net: float              # generation less use (negative: draining)
    tubes: int                    # working
    tubes_loaded: int
    torps_left: int
    torpedo: TorpedoDef | None    # the type in the tubes
    torpedo_types: tuple[TorpedoDef, ...]
    banks: int
    banks_ready: int
    phaser_range: float
    launchers_loaded: int
    probes_left: int
    max_warp: float
    cruise: float
    warp: float
    heat: float                   # hottest drive / limit
    leaking: bool                 # our own drive is venting plasma: cloaked or not, they can follow it
    can_cloak: bool
    cloaked: bool
    evasive: bool
    transporters: int
    beam_cap: int
    delegated: frozenset[str]
    conn: str
    objectives: tuple[str, ...]   # goals under way
    projects: frozenset[str]
    deflector: bool               # the deflector pulse is built and charged
    boost: bool
    target: int | None
    hold_fire: bool
    duty: str
    tuning: float
    remodulating: bool
    pd: str
    evacuees: int
    prisoners: int
    enemies: tuple[EnemyView, ...]          # nearest first, visible and lost alike
    allies: tuple[AllyView, ...]
    inbound: int                  # enemy torpedoes and probes within NEAR
    inbound_plasma: bool
    trails: int                   # plasma trails on sensors
    mission: MissionView | None
    calls_left: int = 0           # on a tour: Starfleet reinforcements still to ask for
    eta: float = 0.0              # and how long they take
    ours: float = 0.0             # our side's strength (Begin's score)
    theirs: float = 0.0           # theirs, as we see it
    damaged: tuple[tuple[str, float], ...] = ()     # our systems below full health: (label, health 0..1)
    tips: tuple[Tip, ...] = ()    # the tactical coach's reading of the same picture (help/coach.py)
    focus: tuple[int, ...] = ()   # the ships a captain's goal is about: the officers plan around these first
    notes: dict[str, float] = field(default_factory=dict)

    # ------------------------------------------------------------- reading it

    @property
    def fighting(self) -> list[EnemyView]:
        """Enemies still in the fight that we can place."""
        return [e for e in self.enemies if not e.surrendered and (e.visible or e.cloaked_hint or e.exhaust)]

    @property
    def top_warp(self) -> float:
        """The warp to order when speed matters: her rated best (power decides how much of it she gets)."""
        return self.ship.cls.max_warp

    @property
    def main_threat(self) -> EnemyView | None:
        """The ship to plan around: the captain's goal first, else the most dangerous one within reach."""
        live = [e for e in self.fighting if e.visible]
        goal = [e for e in live if e.id in self.focus]
        return max(goal or live, key=lambda e: e.threat / (1.0 + e.range / 20000.0), default=None)

    def enemy(self, sid: int | None) -> EnemyView | None:
        return next((e for e in self.enemies if e.id == sid), None)

    @property
    def target_view(self) -> EnemyView | None:
        return self.enemy(self.target)

    def shield_toward(self, x: float, y: float) -> ShieldView | None:
        rel = norm360(bearing(x - self.ship.x, y - self.ship.y) - self.ship.course)
        return _sector(self.shields, rel)

    @property
    def outgunned(self) -> bool:
        return self.theirs > self.ours * 1.15


def _sector(shields: tuple[ShieldView, ...], rel: float) -> ShieldView | None:
    if not shields:
        return None
    return min(shields, key=lambda s: abs((rel - s.facing + 180.0) % 360.0 - 180.0))


def _style(obs: Observation, cls: ShipClass | None, sid: int) -> str:
    if cls is None:
        return ""
    if obs.is_hive(sid):
        return "hive"
    f = obs.content.factions.get(cls.faction)
    doc = f.doctrine if f is not None else None
    if doc is None or not doc.styles:
        return ""
    return max(doc.styles, key=lambda k: doc.styles[k])


def _closing(s: Ship, c: ContactView, upw: float) -> float:
    vx, vy = s.velocity(upw)
    rx, ry = c.x - s.x, c.y - s.y
    d = math.hypot(rx, ry) or 1.0
    return ((vx - c.vx) * rx + (vy - c.vy) * ry) / d


def _enemy(obs: Observation, s: Ship, c: ContactView, torp: TorpedoDef | None, hunters: set[int],
           runner: int | None) -> EnemyView:
    content = obs.content
    upw = obs.rules.units_per_warp
    d = c.distance_to(s.x, s.y)
    brg = bearing(c.x - s.x, c.y - s.y)
    cls = c.cls
    hull: float | None = None
    shields: tuple[float, ...] | None = None
    if c.scan is not None:
        hull = c.scan.structure_frac
        shields = tuple(c.scan.shields)
    if c.assessed is not None:
        if c.assessed.hull is not None and (c.scan is None or c.assessed.tick >= c.scan.tick):
            hull = c.assessed.hull
        if shields is None and any(x is not None for x in c.assessed.shields):
            shields = tuple(-1.0 if x is None else x for x in c.assessed.shields)
    to_us: float | None = None
    weakest: int | None = None
    if shields:
        rel_them = norm360(bearing(s.x - c.x, s.y - c.y) - c.course)
        face = min(range(min(len(shields), len(SHIELD_FACINGS))),
                   key=lambda i: abs((rel_them - SHIELD_FACINGS[i] + 180) % 360 - 180))
        to_us = max(0.0, shields[face])
        weakest = min(range(len(shields)), key=lambda i: shields[i])
    her_torp = content.torpedoes.get(cls.torpedo) if cls is not None and cls.torpedo else None
    our_env = None
    if torp is not None:
        our_env = torpedo_envelope(s, c.x, c.y, c.vx, c.vy, torp.velocity, torp.arm_time, torp.max_time_fuse, upw)
    her_env = None
    if her_torp is not None and cls is not None and cls.tubes > 0:
        # her shot at us is ours at her, mirrored: our motion toward her is what closes it
        vx, vy = s.velocity(upw)
        rx, ry = s.x - c.x, s.y - c.y
        dd = math.hypot(rx, ry) or 1.0
        closing = her_torp.velocity * upw - (vx * rx + vy * ry) / dd
        if closing > 0:
            her_env = (her_torp.arm_time * closing, (her_torp.arm_time + her_torp.max_time_fuse) * closing)
    score = strength(cls.banks, cls.banks_range, cls.tubes) if cls is not None else 6.0
    fac = content.factions.get(cls.faction) if cls is not None else None
    doc = fac.doctrine if fac is not None else None
    hive = obs.is_hive(c.id)
    demeanour = obs.demeanour(c.id)
    adapted = obs.adaptation(c.id, s.id).get("phaser", 0.0) if hive else 0.0
    return EnemyView(
        id=c.id, name=obs.name_of(c.id), cls=cls, faction=cls.faction if cls is not None else "", range=d,
        bearing=brg, rel=norm360(brg - s.course), closing=_closing(s, c, upw),
        threat=score * (0.25 + 0.75 * (hull if hull is not None else 1.0)), style=_style(obs, cls, c.id),
        visible=c.visible, cloaked_hint=c.cloaked_hint, exhaust=c.exhaust, hull=hull, shields=shields,
        shield_to_us=to_us, weakest=weakest,
        banks_ready=c.scan.charged_banks if c.scan is not None else None,
        tubes_loaded=c.scan.loaded_tubes if c.scan is not None else None, scanned=c.scan is not None,
        reading=obs.read_captain(c.id, s.id) if c.visible and c.identified and not hive else None,
        surrendered=c.id in obs.surrendered(), withdrawing=demeanour == "withdrawing",
        our_env=our_env if our_env and our_env[1] > 0 else None, her_env=her_env,
        her_phaser_range=cls.banks_range if cls is not None and cls.banks else 0.0, her_torpedo=her_torp,
        max_warp=cls.max_warp if cls is not None else 0.0,
        pd_discipline=fac.pd_discipline if fac is not None else 0.7,
        surrender_willingness=doc.surrender_willingness if doc is not None else 0.0,
        hunter=c.id in hunters, runner=c.id == runner, hive=hive, dormant=obs.dormant(c.id) if hive else 0.0,
        opening=obs.opening(c.id) if hive else "", weak_point=obs.weak_point(c.id) if hive else None,
        adapted=adapted,
    )


def _shields(s: Ship) -> tuple[ShieldView, ...]:
    return tuple(ShieldView(sh.index, sh.facing, sh.effective if sh.up and not sh.destroyed else 0.0, sh.up,
                            sh.destroyed, bool(sh.reinforced)) for sh in s.shields)


def _mission(obs: Observation, s: Ship, shields: tuple[ShieldView, ...]) -> MissionView | None:
    m = obs.mission()
    if m is None:
        return None
    w = obs.own(m.ward_id) if m.ward_id is not None else None
    ward_name = w.name if w is not None else m.spec.ward_name
    runner_name = obs.name_of(m.runner_id) if m.runner_id is not None else ""
    title = m.spec.heading_title(ward_name, runner_name)
    common = dict(kind=m.kind, state=m.state, title=title, hunter_ids=tuple(h for h in m.hunter_ids
                                                                             if h not in obs.gone()))
    if w is not None and w.alive:
        rel = norm360(bearing(w.x - s.x, w.y - s.y) - s.course)
        to = m.spec.to
        return MissionView(**common, ward_id=w.id, ward_name=w.name, ward_x=w.x, ward_y=w.y,  # type: ignore[arg-type]
                           ward_range=math.hypot(w.x - s.x, w.y - s.y), ward_bearing=bearing(w.x - s.x, w.y - s.y),
                           ward_hull=max(0.0, w.structure) / max(1.0, w.structure_max), ward_shield=_sector(shields, rel),
                           aboard=m.aboard, saved=m.saved, people=m.spec.people, time_left=m.time_left(obs.time),
                           beaming=m.beaming, blocked=m.blocked, to=to, to_range=math.hypot(to[0] - w.x, to[1] - w.y))
    if m.kind == "intercept" and m.runner_id is not None:
        c = obs.contact(m.runner_id)
        esc = None
        if c is not None and c.visible:
            # clear of everything of ours by the escape distance, at her speed
            ours = obs.own_ships()
            gap = min((math.hypot(c.x - o.x, c.y - o.y) for o in ours), default=0.0)
            speed = max(1.0, math.hypot(c.vx, c.vy))
            esc = max(0.0, (obs.rules.escape_distance - gap) / speed) + obs.rules.escape_cycles
            meet = _intercept(c.x - s.x, c.y - s.y, c.vx, c.vy, s.cls.max_warp * obs.rules.units_per_warp)
            if meet is not None:
                t, course = meet
                return MissionView(**common, runner_id=m.runner_id, runner_escape=esc,  # type: ignore[arg-type]
                                   runner_intercept=course, runner_meet=t)
        return MissionView(**common, runner_id=m.runner_id, runner_escape=esc)  # type: ignore[arg-type]
    return MissionView(**common, ward_name=ward_name, aboard=m.aboard, saved=m.saved,  # type: ignore[arg-type]
                       people=m.spec.people)


def _intercept(dx: float, dy: float, vx: float, vy: float, speed: float) -> tuple[float, float] | None:
    """(cycles, course) to meet a ship at (dx, dy) from us moving at (vx, vy) a cycle, flying at `speed`; None if
    we can't catch her. Solves |d + v t| = speed t for the soonest t > 0."""
    a = vx * vx + vy * vy - speed * speed
    b = 2.0 * (dx * vx + dy * vy)
    c = dx * dx + dy * dy
    if abs(a) < 1e-9:
        if b >= 0:
            return None
        t = -c / b
    else:
        disc = b * b - 4 * a * c
        if disc < 0:
            return None
        r = math.sqrt(disc)
        ts = [t for t in ((-b - r) / (2 * a), (-b + r) / (2 * a)) if t > 0]
        if not ts:
            return None
        t = min(ts)
    return t, bearing(dx + vx * t, dy + vy * t)


def mission_view(obs: Observation, ship: Ship) -> MissionView | None:
    """Our mission as the officers see it from the flagship (for the HUD's mission card)."""
    return _mission(obs, ship, _shields(ship))


def build(obs: Observation, ship: Ship, calls_left: int = 0, eta: float = 0.0) -> Situation:
    """The situation as our side sees it now, from the flagship."""
    s = ship
    content = obs.content
    fac = content.factions.get(s.faction)
    torp_ids = list(fac.torpedoes) if fac is not None else []
    loaded_type = next((t.load_ordnance for t in s.tubes if t.load_ordnance), "") or s.cls.torpedo
    torp = content.torpedoes.get(loaded_type) if loaded_type else None
    m = obs.mission()
    hunters = set(m.hunter_ids) if m is not None else set()
    runner = m.runner_id if m is not None else None
    gone = obs.gone()
    enemies = [_enemy(obs, s, c, torp, hunters, runner) for c in obs.hostile_contacts()
               if c.id not in gone and c.distance_to(s.x, s.y) < WATCH * 2]
    enemies.sort(key=lambda e: e.range)
    shields = _shields(s)
    live = [e for e in enemies if e.visible and not e.surrendered]
    main = max(live, key=lambda e: e.threat / (1.0 + e.range / 20000.0), default=None)
    facing = None
    if main is not None:
        facing = _sector(shields, main.rel)
    up = [x for x in shields if not x.destroyed]
    freshest = max(up, key=lambda x: x.effective, default=None)
    cap = s.battery_capacity()
    drives = [d for d in s.drives if not d.destroyed]
    heat = max((d.temp for d in drives), default=0.0) / max(1.0, obs.rules.temp_limit)
    allies = []
    for a in obs.own_ships():
        if a.id == s.id or a.ward or a.cls.craft:
            continue
        st = obs.ally_order(a.id)
        order = ""
        if st is not None:
            order = "attack" if st.target is not None else (st.movement or "")
        allies.append(AllyView(a.id, a.name, max(0.0, a.structure) / max(1.0, a.structure_max), order,
                               sum(1 for t in a.tubes if t.loaded is not None), math.hypot(a.x - s.x, a.y - s.y)))
    threats = [o for o in obs.threats() if math.hypot(o.x - s.x, o.y - s.y) < NEAR]
    plasma_ids = {t.id for t in content.torpedoes.values() if t.warhead_type == 2}
    inbound_plasma = any(o.kind == "torpedo" and _is_plasma(content, o.faction, plasma_ids) for o in threats)
    ours = sum(strength(o.cls.banks, o.cls.banks_range, o.cls.tubes) * max(0.0, o.structure) / max(1.0, o.structure_max)
               for o in obs.own_ships() if not o.ward and not o.cls.craft)
    theirs = sum(e.threat for e in live)
    return Situation(
        time=obs.time, ship=s, name=s.name, faction=s.faction,
        hull=max(0.0, s.structure) / max(1.0, s.structure_max), crew=s.crew, morale=s.morale,
        shields=shields, facing=facing, freshest=freshest,
        battery=s.battery_charge() / cap if cap > 0 else 0.0, power_net=s.power.net,
        tubes=sum(1 for t in s.tubes if t.intact), tubes_loaded=sum(1 for t in s.tubes if t.intact and t.loaded is not None),
        torps_left=s.torps_remaining, torpedo=torp,
        torpedo_types=tuple(content.torpedoes[t] for t in torp_ids if t in content.torpedoes and not content.torpedoes[t].special),
        banks=sum(1 for b in s.banks if b.intact),
        banks_ready=sum(1 for b in s.banks if b.intact and b.enabled and b.charge >= s.cls.banks_charge - 1e-6),
        phaser_range=s.cls.banks_range,
        launchers_loaded=sum(1 for lch in s.launchers if lch.loaded), probes_left=s.probes_remaining,
        max_warp=s.max_attainable_warp, cruise=s.cls.cruise_warp, warp=s.warp, heat=heat,
        leaking=obs.leaking(s.id), can_cloak=s.cls.can_cloak and s.cloak is not None and not s.cloak.destroyed,
        cloaked=s.cloaked, evasive=s.evasive,
        transporters=sum(1 for t in s.transporters if not t.destroyed), beam_cap=s.cls.beam_cap,
        delegated=frozenset(s.delegated), conn=s.conn or "",
        objectives=tuple(o.goal for o in s.objectives), projects=frozenset(s.projects),
        deflector=bool(s.deflector_ready) and s.deflector_cooldown <= 0, boost=s.engine_boost > 0,
        target=s.target, hold_fire=s.hold_fire, duty=s.duty or "", tuning=s.tuning, remodulating=s.remodulating > 0,
        pd=s.pd_doctrine.value, evacuees=s.evacuees, prisoners=s.prisoners,
        enemies=tuple(enemies), allies=tuple(sorted(allies, key=lambda a: a.range)), inbound=len(threats),
        inbound_plasma=inbound_plasma, trails=len(obs.plasma()), mission=_mission(obs, s, shields),
        calls_left=calls_left, eta=eta, ours=ours, theirs=theirs,
        damaged=tuple((x.label, x.health) for x in s.subsystems() if x.health < 1.0),
        tips=tuple(coach_tips(HelpContext(content, obs, s))),
    )


def _is_plasma(content: object, faction: str, plasma_ids: set[str]) -> bool:
    f = getattr(content, "factions", {}).get(faction)
    return f is not None and any(t in plasma_ids for t in f.torpedoes)


__all__ = ["AllyView", "EnemyView", "MissionView", "ShieldView", "Situation", "build", "mission_view"]
