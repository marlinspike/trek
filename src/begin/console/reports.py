"""Begin's text displays: report, damage/scan, banks, tubes, launchers, probes, shields, fleet, chart, library.

Layouts follow the manual's sample screens (pp. 10-20) so a Begin player
recognises them; each returns plain lines for the console log (rendered in
a monospaced font). Everything is read from an `Observation`: own ships in
full, other ships only as far as sensors and scans reveal them.
"""

from __future__ import annotations

import math

from ..content.schema import ContentDB, ProbeDef, ShipClass, TorpedoDef
from ..core.angles import bearing, norm360
from ..sim.allies import AllyStanding
from ..sim.observation import ContactView, Observation
from ..sim.ship import HelmMode, Ship
from ..sim.systems.sensors import ScanRecord


def _pct(v: float) -> str:
    return f"{v:3.0f}%"


def _name(obs: Observation, sid: int | None) -> str:
    if sid is None:
        return ""
    s = obs.own(sid)
    if s is not None:
        return s.name
    c = obs.contact(sid)
    return c.label.split(" (")[0] if c is not None else f"#{sid}"


def _rel(ship: Ship, x: float, y: float) -> float:
    """Mark: degrees off our heading, 0-359."""
    return norm360(bearing(x - ship.x, y - ship.y) - ship.course)


def _pos(obs: Observation, sid: int | None) -> tuple[float, float] | None:
    if sid is None:
        return None
    s = obs.own(sid)
    if s is not None:
        return s.x, s.y
    c = obs.contact(sid)
    return (c.x, c.y) if c is not None else None


# ------------------------------------------------------------------ report / damage / scan

def navcom(obs: Observation, ship: Ship) -> str:
    if ship.docked_to is not None:
        return f"Docked with {_name(obs, ship.docked_to)}"
    if ship.helm_mode == HelmMode.PURSUE and ship.helm_target is not None:
        return f"Pursuing {_name(obs, ship.helm_target)}"
    if ship.helm_mode == HelmMode.ELUDE and ship.helm_target is not None:
        return f"Eluding {_name(obs, ship.helm_target)}"
    return "Manual Helm"


def condition(ship: Ship) -> float:
    subs = list(ship.subsystems())
    if not subs:
        return 100.0
    return sum(s.health for s in subs) / len(subs) * 100.0


def report_lines(obs: Observation, ship: Ship, standing: AllyStanding | None = None) -> list[str]:
    out = [
        f"SHIP NAME: {ship.name}",
        f"CLASS: {ship.cls.name}",
        f"SURVIVORS: {ship.crew}",
        f"CONDITION: {condition(ship):.0f}% Functional",
        f"NAVCOM: {navcom(obs, ship)}",
        f"COURSE: {ship.desired_course:.0f}. desired {ship.course:.0f}. current",
        f"WARP: {ship.desired_warp:.1f} desired {ship.warp:.1f} current",
    ]
    if standing is not None:
        names = {s.id: s.name for s in obs.own_ships(alive_only=False)}
        names.update({c.id: c.label.split(" (")[0] for c in obs.contacts().values()})
        tgt = _name(obs, standing.target) if standing.target is not None else _name(obs, ship.target)
        out.append(f"MISSION: {standing.mission(names)}")
        out.append(f"TARGET: {('(' + tgt + ')') if standing.target is not None else (tgt or '..')}")
    return out


def _marks(items: list[str]) -> str:
    return " ".join(items) if items else "--"


def damage_lines(obs: Observation, ship: Ship) -> list[str]:
    """`damage` / `status damage`: the full condition of one of our own ships (manual p. 11)."""
    cap = ship.cls.battery_capacity or 1.0
    drives = [d for d in ship.drives]
    live = [d for d in drives if not d.destroyed]
    temp = max((d.temp for d in live), default=0.0)
    p = ship.power
    return [
        f"SHIP NAME: {ship.name}",
        f"CLASS: {ship.cls.name}",
        f"SURVIVORS: {ship.crew}",
        "REACTORS: " + _marks(["XX" if r.destroyed else _pct(r.health * 100).strip() for r in ship.reactors]),
        "BATTERIES: " + _marks(["XX" if not b.online else f"{b.charge / cap * 100:.0f}" for b in ship.batteries]),
        "BANKS: " + _marks(["XX" if not b.intact else ("ch" if b.charge >= ship.cls.banks_charge - 1e-6 else "..")
                            for b in ship.banks]),
        "TUBES: " + _marks(["XX" if not t.intact else ("ld" if t.loaded is not None else "..") for t in ship.tubes]),
        "LAUNCHERS: " + _marks(["XX" if not lch.intact else ("ld" if lch.loaded is not None else "..")
                                for lch in ship.launchers]),
        "SHIELDS: " + _marks(["XX" if sh.destroyed else f"{sh.effective:.0f}%" for sh in ship.shields]),
        "WARP: " + _marks(["XX" if d.destroyed else _pct(d.health * 100).strip() for d in drives]),
        f"WARP TEMP: {temp:.0f}  LIMIT: 40",
        f"WARP POWER: {p.warp_used:.0f}",
        f"OTHER POWER: {p.consumption:.0f}",
        f"RESIDUAL POWER: {p.net:.0f}",
        "OTHER: " + _marks([f"{s.label} {'XX' if s.destroyed else _pct(s.health * 100).strip()}"
                            for s in (ship.impulse, ship.sensors, ship.computer, ship.tractor, ship.cloak) if s is not None]
                           + [f"transporters {sum(1 for t in ship.transporters if not t.destroyed)}/{len(ship.transporters)}"]),
    ]


SHIELD_SIDES = ("fore", "fore-stbd", "fore-port", "aft-stbd", "aft-port", "aft")   # shields 1-6 (ship.py)
BAR = 12


def bar(frac: float, width: int = BAR) -> str:
    """A gauge in the log: ■■■■□□□ (squares both bundled faces carry; ▰▱ would print as boxes)."""
    n = round(max(0.0, min(1.0, frac)) * width)
    return "\u25a0" * n + "\u25a1" * (width - n)


def sid_label(sid: str) -> str:
    """'transporter3' -> 'transporter 3'."""
    stem = sid.rstrip("0123456789")
    return f"{stem} {sid[len(stem):]}".strip() if stem != sid else sid


def scan_lines(obs: Observation, c: ContactView, me: Ship | None = None, before: ScanRecord | None = None) -> list[str]:
    """`scan <ship>`: what our last scan of another ship revealed, laid out to decide on [E]: hull and crew,
    each shield by side (the one facing us marked), weapons ready, drives, what changed since the scan before,
    and what it means. For a Borg ship, the hive's adaptation to our weapons, how far our harmonic survey has
    got, her weak point and her drones. Begin's own scan (manual p. 11) carried the same numbers, as a table."""
    name = c.label.split(" (")[0]
    if c.cls is None:
        return [f"SCAN  {name}", "Unidentified. Close in and scan again to learn more."]
    sc = c.scan
    cls: ShipClass = c.cls
    age = (obs.tick - sc.tick) * obs.rules.dt if sc is not None else 0.0
    title = name if name.lower().startswith(cls.name.lower()) else f"{name} · {cls.name}"
    out = [f"SCAN  {title}" + (f"   {age:.0f} s old · {sc.confidence * 100:.0f}% sure" if sc else "")]
    if sc is None:
        out.append("The scan is under way.")
        return out + _hive_lines(obs, c, me)

    def health(prefix: str, n: int) -> list[int]:
        return [100 - sc.subsystems.get(f"{prefix}{i + 1}", 0) for i in range(n)]

    out.append(f"HULL      {bar(sc.structure_frac)} {sc.structure_frac * 100:3.0f}%    CREW {sc.crew:,} of {cls.crew:,}")
    facing = _facing_us(c, me, len(sc.shields))
    cells = []
    for i, v in enumerate(sc.shields):
        side = SHIELD_SIDES[i] if len(sc.shields) == 6 and i < 6 else str(i + 1)
        mark = "*" if i == facing else ""
        cells.append(f"{side}{mark} {'down' if v < 0 else f'{v:.0f}%'}")
    if cells:
        out.append("SHIELDS   " + " · ".join(cells) + ("   (* faces us)" if facing is not None else ""))
    banks = health("phaser", cls.banks)
    tubes = health("tube", cls.tubes)
    live_b = sum(1 for h in banks if h > 0)
    live_t = sum(1 for h in tubes if h > 0)
    weapons = []
    if cls.banks:
        weapons.append(f"banks {min(sc.charged_banks, live_b)} charged of {live_b}" + (
            f" ({cls.banks - live_b} out)" if live_b < cls.banks else ""))
    if cls.tubes:
        weapons.append(f"tubes {min(sc.loaded_tubes, live_t)} loaded of {live_t}" + (
            f" ({cls.tubes - live_t} out)" if live_t < cls.tubes else ""))
    if cls.launchers:
        weapons.append(f"probes {sc.probes_loaded} ready")
    if weapons:
        out.append("WEAPONS   " + " · ".join(weapons))
    drives = health("drive", cls.drives)
    reactors = health("reactor", cls.reactors)
    out.append(f"POWER     reactors {sum(1 for h in reactors if h > 0)} of {cls.reactors} · "
               f"warp drives {sum(1 for h in drives if h > 0)} of {cls.drives}")
    if before is not None and before.tick != sc.tick:
        out.append("CHANGED   " + _changes(before, sc))
    out += _hive_lines(obs, c, me)
    advice = _advice(obs, c, me, sc, facing, banks, tubes, drives)
    if advice:
        out.append("READ      " + advice)
    return out


def _facing_us(c: ContactView, me: Ship | None, n: int) -> int | None:
    """Which of her shields faces us now (index), from her heading and where we are."""
    if me is None or n != 6:
        return None
    rel = norm360(bearing(me.x - c.x, me.y - c.y) - c.course)
    from ..sim.ship import SHIELD_FACINGS

    return min(range(6), key=lambda i: abs((rel - SHIELD_FACINGS[i] + 180.0) % 360.0 - 180.0))


def _changes(a: ScanRecord, b: ScanRecord) -> str:
    out = []
    dh = (b.structure_frac - a.structure_frac) * 100
    if abs(dh) >= 1:
        out.append(f"hull {dh:+.0f}%")
    if b.crew != a.crew:
        out.append(f"crew {b.crew - a.crew:+,}")
    for i, (x, y) in enumerate(zip(a.shields, b.shields)):
        side = SHIELD_SIDES[i] if len(b.shields) == 6 else str(i + 1)
        if x >= 0 > y:
            out.append(f"{side} shield down")
        elif y >= 0 > x:
            out.append(f"{side} shield back up")
    lost = [sid_label(k) for k, v in b.subsystems.items() if v >= 100 and a.subsystems.get(k, 0) < 100]
    fixed = [sid_label(k) for k, v in b.subsystems.items() if v < 100 and a.subsystems.get(k, 0) >= 100]
    if lost:
        out.append("lost " + ", ".join(lost[:4]) + (" ..." if len(lost) > 4 else ""))
    if fixed:
        out.append("repaired " + ", ".join(fixed[:3]))
    return " · ".join(out) or "nothing worth noting"


def _hive_lines(obs: Observation, c: ContactView, me: Ship | None) -> list[str]:
    """What a Borg ship shows to a crew that knows how to look [E]."""
    if not obs.is_hive(c.id):
        return []
    out = []
    if me is not None:
        ad = obs.adaptation(c.id, me.id)
        plural = {"phaser": "phasers", "torpedo": "torpedoes", "harmonic": "harmonics"}
        cells = [f"{plural.get(k, k)} {bar(v, 6)} {v * 100:.0f}%" for k, v in ad.items() if k != "harmonic" or v > 0]
        out.append("ADAPTED   " + " · ".join(cells))
    sv = obs.survey(c.id)
    from ..sim.collective import CODE_AT

    got = sv.progress / CODE_AT if sv is not None else 0.0
    weak = obs.weak_point(c.id)
    out.append(f"HARMONICS {bar(got)} {got * 100:3.0f}%" + ("   ready: 'design harmonic'" if got >= 1.0 else
                                                            "   each scan adds more; Seven reads them best"))
    out.append("RELAY     " + (f"runs through her {sid_label(weak)}: destroy it and her drones sleep" if weak else
                               "hidden; half the harmonic survey will find it"))
    dorm = obs.dormant(c.id)
    if dorm > 0:
        out.append(f"DORMANT   {dorm:.0f} s left: shields down, weapons cold. Board her, or hit her drives.")
    return out


def _advice(obs: Observation, c: ContactView, me: Ship | None, sc: ScanRecord, facing: int | None,
            banks: list[int], tubes: list[int], drives: list[int]) -> str:
    """A line on what the scan means for the captain: the opening it shows, and the danger."""
    tips = []
    if obs.is_hive(c.id) and me is not None:
        ad = obs.adaptation(c.id, me.id)
        if ad.get("phaser", 0.0) >= 0.5:
            tips.append("they have our phaser frequency: remodulate")
        if ad.get("torpedo", 0.0) >= 0.5:
            tips.append("torpedoes are losing their bite")
    down = [i for i, v in enumerate(sc.shields) if v < 0]
    if down and len(sc.shields) == 6:
        tips.append(f"her {SHIELD_SIDES[down[0]]} shield is down: put a volley there")
    elif sc.shields:
        weakest = min(range(len(sc.shields)), key=lambda i: sc.shields[i])
        if sc.shields[weakest] < 40 and len(sc.shields) == 6:
            tips.append(f"her {SHIELD_SIDES[weakest]} shield is weakest ({sc.shields[weakest]:.0f}%)")
    if drives and all(h <= 0 for h in drives):
        tips.append("no warp: she can't run or turn quickly")
    if banks and sc.charged_banks >= max(2, len(banks) // 2):
        tips.append(f"{sc.charged_banks} banks charged: expect a volley")
    if me is not None and not obs.is_hive(c.id) and 0 < sc.crew < me.boarding_party():
        tips.append(f"her crew is down to {sc.crew}: a boarding party could take her")
    return "; ".join(tips[:3]) + "." if tips else ""


# ------------------------------------------------------------------ weapon status tables

def banks_lines(obs: Observation, ship: Ship) -> list[str]:
    if not ship.banks:
        return [f"The {ship.cls.name} has no phaser banks."]
    out = ["BANK STATUS:", "Bank Level Control Mark Status   Spread Mode      Target"]
    full = ship.cls.banks_charge or 1.0
    for i, b in enumerate(ship.banks):
        if not b.intact:
            out.append(f"{i + 1:>4}   ..  damaged  ...  .....      ..")
            continue
        lvl = b.charge / full * 100
        pos = _pos(obs, b.lock)
        mark = _rel(ship, *pos) if pos is not None else norm360(b.mark)
        status = "charged" if lvl >= 99.9 else ("disabled" if not b.enabled else "drained")
        ctl = "locked" if b.lock is not None else "manual"
        role = "" if b.role.value == "flex" else f" [{b.role.value}]"
        out.append(f"{i + 1:>4} {lvl:4.0f}% {ctl:<7} {mark:4.0f} {status:<9} {b.spread:4.0f}  "
                   f"{b.fire_mode.value:<9} {_name(obs, b.lock)}{role}")
    return out


def tubes_lines(obs: Observation, ship: Ship) -> list[str]:
    if not ship.tubes:
        return [f"The {ship.cls.name} has no torpedo tubes."]
    out = ["TUBE STATUS:", "Tube Level Control Mark Content Prox Target"]
    for i, t in enumerate(ship.tubes):
        if not t.intact:
            out.append(f"{i + 1:>4}   ... damaged  ... .....   ... ...")
            continue
        pos = _pos(obs, t.lock)
        mark = _rel(ship, *pos) if pos is not None else norm360(t.mark)
        ctl = "locked" if t.lock is not None else ("off" if not t.enabled else "manual")
        content = t.loaded.ordnance if t.loaded is not None else "empty"
        prox = f"{t.loaded.prox:4.0f}" if t.loaded is not None else " ..."
        out.append(f"{i + 1:>4} {t.charge:4.0f}% {ctl:<7} {mark:4.0f} {content:<7} {prox} {_name(obs, t.lock) or '...'}")
    out.append(f"Torpedoes remaining: {ship.torps_remaining}")
    return out


def launchers_lines(obs: Observation, ship: Ship) -> list[str]:
    if not ship.launchers:
        return [f"The {ship.cls.name} has no probe launchers."]
    out = ["LAUNCHER STATUS:", "Launcher Status  Contents Prox Time Code"]
    for i, lch in enumerate(ship.launchers):
        if not lch.intact:
            out.append(f"{i + 1:>8} Damaged  ....     ...  ..   ....")
        elif lch.loaded is None:
            out.append(f"{i + 1:>8} Ready    empty    ...  ..   ....")
        else:
            lp = lch.loaded
            out.append(f"{i + 1:>8} Ready    {lp.ordnance:<8} {lp.prox:4.0f} {lp.time:3.0f}   {lp.code}")
    out.append(f"Probes remaining: {ship.probes_remaining}")
    return out


def probes_lines(obs: Observation, ship: Ship) -> list[str]:
    mine = [o for o in obs.ordnance() if o.kind == "probe" and o.owner == ship.id]
    if not mine:
        return ["No active probes."]
    out = ["PROBE STATUS:", "Code  Course Bearing Range Time Range/Target"]
    for o in mine:
        brg = bearing(o.x - ship.x, o.y - ship.y)
        rng = math.hypot(o.x - ship.x, o.y - ship.y)
        tgt = "..."
        if o.target is not None:
            p = _pos(obs, o.target)
            if p is not None:
                tgt = f"{math.hypot(p[0] - o.x, p[1] - o.y):5.0f} {_name(obs, o.target)}"
        out.append(f"{o.code:<5} {o.course:6.0f} {brg:7.0f} {rng:5.0f} {o.fuse:4.0f} {tgt}")
    return out


def shields_lines(obs: Observation, ship: Ship) -> list[str]:
    if not ship.shields:
        return [f"The {ship.cls.name} has no shields."]
    full = ship.cls.shield_strength
    out = ["SHIELDS STATUS:", "Shield Field Status  Functional   Effective    Regen."]
    for i, sh in enumerate(ship.shields):
        if sh.destroyed:
            out.append(f"{i + 1:>6} {sh.facing:5.0f} damaged   ..  ...      ...  ...")
            continue
        status = ("UP*" if sh.reinforced else "UP") if sh.up else "DOWN"
        func = full * sh.ceiling / 100.0
        eff = full * sh.effective / 100.0
        regen = ship.cls.shield_recharge * sh.health if sh.up and sh.effective < sh.ceiling else 0.0
        out.append(f"{i + 1:>6} {sh.facing:5.0f} {status:<6} {func:5.0f}eu {sh.ceiling:3.0f}% "
                   f"{eff:5.0f}eu {sh.effective:3.0f}% {regen:5.2f}%")
    if any(sh.reinforced for sh in ship.shields):
        out.append("* reinforced")
    return out


# ------------------------------------------------------------------ fleet, groups, chart

def fleet_lines(obs: Observation, flagship_id: int) -> list[str]:
    allies = [s for s in obs.own_ships() if s.id != flagship_id]
    if not allies:
        return ["You have no ally ships."]
    names = {s.id: s.name for s in obs.own_ships(alive_only=False)}
    names.update({c.id: c.label.split(" (")[0] for c in obs.contacts().values()})
    out = ["ALLY            TARGET          MISSION"]
    for a in allies:
        st = obs.ally_order(a.id)
        if st is not None and st.target is not None:
            tgt = f"({names.get(st.target, '?')})"
        else:
            tgt = names.get(a.target, "..") if a.target is not None else ".."
        mission = st.mission(names) if st is not None else ".."
        grp = f" [group {st.group}]" if st is not None and st.group is not None else ""
        out.append(f"{a.name + ':':<15} {tgt:<15} {mission}{grp}")
    return out


def group_lines(obs: Observation) -> list[str]:
    groups: dict[int, list[str]] = {}
    for s in obs.own_ships():
        st = obs.ally_order(s.id)
        if st is not None and st.group is not None:
            groups.setdefault(st.group, []).append(s.name)
    if not groups:
        return ["No groups. Use 'tell <ally> join <number>'."]
    return [f"Group {g}: {', '.join(sorted(n))}" for g, n in sorted(groups.items())]


def chart_lines(obs: Observation, origin: Ship | ContactView, flagship_id: int, sort: str = "name",
                hidden: frozenset[int] = frozenset(), everyone: bool = False) -> list[str]:
    """Begin's chart (manual p. 10): every ship's warp, course, and bearing/range/mark from the charted ship."""
    ox, oy = origin.x, origin.y
    oc = origin.course
    rows: list[tuple[str, str, float, str, Ship | ContactView]] = []
    for s in obs.own_ships():
        rows.append((s.name, obs.side_name(s.side), math.hypot(s.x - ox, s.y - oy), s.cls.abbrev, s))
    for c in obs.contacts().values():
        if c.side == obs.side:
            continue
        nation = obs.side_name(c.side) if c.side is not None else "?"
        label = c.label.split(" (")[0] if c.identified else f"#{c.id}"
        rows.append((label, nation, math.hypot(c.x - ox, c.y - oy), c.cls.abbrev if c.cls else "??", c))
    rows = [r for r in rows if everyone or r[4].id not in hidden]
    flag = [r for r in rows if r[4].id == flagship_id]
    rest = [r for r in rows if r[4].id != flagship_id]
    key = {"distance": lambda r: r[2], "nation": lambda r: (r[1], r[0])}.get(sort, lambda r: r[0].lower())
    rest.sort(key=key)
    nw = max([len(r[0]) + 1 for r in rows] + [10])
    out = [f"{'':<{nw}} WARP COURSE BEARING RANGE  MARK CLASS"]
    for name, _nation, d, abbrev, obj in flag + rest:
        warp, course = obj.warp, obj.course
        if obj.id == origin.id:
            helm = navcom(obs, obj) if isinstance(obj, Ship) else ""
            out.append(f"{name + ':':<{nw}} {warp:4.1f} {course:6.0f}. {helm}")
            continue
        brg = bearing(obj.x - ox, obj.y - oy)
        mark = round(norm360(brg - oc))
        if mark > 180:
            mark -= 360
        mark = mark or 0
        stale = "" if (isinstance(obj, Ship) or obj.visible) else " (last known)"
        out.append(f"{name + ':':<{nw}} {warp:4.1f} {course:6.0f}. {brg:6.0f}. {d:6.0f} {mark:5d}. {abbrev}{stale}")
    return out


# ------------------------------------------------------------------ library computer

def _class_lines(c: ShipClass, content: ContentDB) -> list[str]:
    nation = content.factions[c.faction].name
    return [
        f"{nation} {c.name} ({c.abbrev})",
        f"  Crew {c.crew}   Mass {c.mass:,.0f}   Max warp {c.max_warp:g}   Turn at warp 1: {c.w1turn:g}°/cycle",
        f"  Reactors {c.reactors} x {c.reactor_output:g}   Batteries {c.batteries} x {c.battery_capacity:g}",
        f"  Phaser banks {c.banks}: charge {c.banks_charge:g} over {c.banks_rate:g} cycles, range {c.banks_range:,.0f}",
        f"  Torpedo tubes {c.tubes} ({c.torpedo or '-'}, {c.torps_carried} carried)   "
        f"Probe launchers {c.launchers} ({c.probe or '-'}, {c.probes_carried} carried)",
        f"  Shields {c.shields} x {c.shield_strength:g}   Warp drives {c.drives}   Sensor range {c.scanner_range:,.0f}",
        f"  Transporters {c.transporters}   Tractor {'yes' if c.has_tractor else 'no'}   "
        f"Cloak {'yes' if c.can_cloak else 'no'}   Docking {'yes' if c.mass_capacity > 0 else 'no'}",
    ]


def _torp_lines(t: TorpedoDef) -> list[str]:
    kind = {0: "antimatter", 1: "shield-bore", 2: "plasma"}.get(t.warhead_type, "antimatter")
    return [
        f"{t.name} ({t.id})",
        f"  Warp {t.velocity:g} ±{t.speed_variance:g}   Warhead {t.damage:g} ({kind})   Arms after {t.arm_time:g} cycles",
        f"  Time fuse {t.max_time_fuse:g} cycles   Max proximity {t.max_prox:,.0f}   "
        f"{'Homing' if t.homing else 'Straight-running'}   Tube charge {t.charge_time:g} cycles",
    ]


def _probe_lines(p: ProbeDef) -> list[str]:
    return [
        f"{p.name} ({p.id})",
        f"  Warp {p.velocity:g}   Warhead {p.damage:g}   Arms after {p.arm_time:g} cycles   Time fuse {p.max_time_fuse:g} cycles",
        f"  Max proximity {p.max_prox:,.0f}   {'Homing' if p.homing else 'Straight'}"
        + (f"   Sensor range {p.scan_range:,.0f}" if p.scan_range else ""),
    ]


def _norm(word: str) -> str:
    w = word.lower().replace("-", "").replace("_", "")
    for r, d in (("viii", "8"), ("vii", "7"), ("ii", "2")):
        if w.endswith(r):
            return w[: -len(r)] + d
    return w


def library_lines(content: ContentDB, words: list[str]) -> list[str]:
    """`computer ship <nation> <class>` · `computer torpedo <class>` · `computer probe <class>`.

    Partial commands list the subjects that match, as in Begin (manual p. 21).
    """
    topics = {"ship": ("ship", "ships", "class"), "torpedo": ("torpedo", "torpedoes", "torp", "torps"),
              "probe": ("probe", "probes")}
    if not words:
        return ["LIBRARY COMPUTER: computer ship <nation> <class> · computer torpedo <class> · computer probe <class>",
                "Subjects: ships, torpedoes, probes."]
    topic = next((k for k, al in topics.items() if any(a.startswith(words[0]) for a in al)), None)
    rest = [w for w in words[1:] if w not in ("the", "class", "of")]
    if topic == "torpedo":
        hits = [t for t in content.torpedoes.values() if not rest or _norm(t.id).startswith(_norm(rest[0]))
                or all(w in t.name.lower() for w in rest)]
        if len(hits) == 1:
            return _torp_lines(hits[0])
        return ["Torpedoes: " + ", ".join(f"{t.id} ({t.name})" for t in hits)] if hits else ["No such torpedo."]
    if topic == "probe":
        probes = [p for p in content.probes.values() if not rest or _norm(p.id).startswith(_norm(rest[0]))
                  or all(w in p.name.lower() for w in rest)]
        if len(probes) == 1:
            return _probe_lines(probes[0])
        return ["Probes: " + ", ".join(f"{p.id} ({p.name})" for p in probes)] if probes else ["No such probe."]
    if topic == "ship":
        classes = list(content.classes.values())
        for w in rest:
            nations = [f for f, fac in content.factions.items()
                       if f.startswith(w) or fac.name.lower().startswith(w) or (w == "pirate" and f == "orion")]
            if nations:
                classes = [c for c in classes if c.faction in nations]
                continue
            classes = [c for c in classes if any(part.startswith(w) for part in c.name.lower().split())
                       or c.abbrev.lower() == w]
        if len(classes) == 1:
            return _class_lines(classes[0], content)
        if not classes:
            return ["No such ship class."]
        by_nation: dict[str, list[str]] = {}
        for c in classes:
            by_nation.setdefault(content.factions[c.faction].name, []).append(c.name)
        return [f"{n}: {', '.join(cs)}" for n, cs in by_nation.items()]
    return [f"The library has no subject '{words[0]}'. Subjects: ships, torpedoes, probes."]


__all__ = [
    "banks_lines", "chart_lines", "damage_lines", "fleet_lines", "group_lines", "launchers_lines", "library_lines",
    "probes_lines", "report_lines", "scan_lines", "shields_lines", "tubes_lines",
]


MORALE_WORDS = ("broken", "shaken", "steady", "confident", "high")


def morale_words(morale: float) -> str:
    """The crew's spirits in a word [E]."""
    return MORALE_WORDS[min(4, int(morale // 20))]


def morale_lines(obs: Observation) -> list[str]:
    """Morale aboard our own ships [E]; the enemy's spirits can only be guessed from how they fight."""
    out = ["Crew morale (0-100; 50 is neither help nor hindrance):"]
    for s in obs.own_ships():
        out.append(f"  {s.name:<16} {s.morale:5.0f}  {morale_words(s.morale)}"
                   f"   (usually {s.morale_base:.0f})")
    return out
