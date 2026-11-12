"""Torpedo and probe launch, guidance, fuses and blasts [R §7, §8, §13].

Proximity fuses are checked with swept closest-approach tests each tick
(relative motion of weapon and ship), which removes Begin's sampling
artifact where a fast torpedo could stride past a tight proximity [E].
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ...core.angles import bearing, in_arc, norm360
from ..events import Detonation, Message, ProbeLaunched, Tone, TorpedoLaunched
from ..ordnance import Probe, Torpedo
from ..ship import Launcher, Ship, Tube
from .damage import Aim, DamageKind, apply_damage

if TYPE_CHECKING:
    from ...content.schema import TorpedoDef
    from ..rules import Rules
    from ..world import World


# ------------------------------------------------------------- solutions

def intercept_bearing(
    sx: float, sy: float, tx: float, ty: float, tvx: float, tvy: float, speed: float
) -> float:
    """Bearing that intercepts a constant-velocity target (Begin's lead, solved exactly).

    Begin's tube lead `asin(sin(angle_off) × v_target / v_torp)` is the
    same constant-velocity intercept; we solve the quadratic directly.
    """
    rx, ry = tx - sx, ty - sy
    a = tvx * tvx + tvy * tvy - speed * speed
    b = 2.0 * (rx * tvx + ry * tvy)
    c = rx * rx + ry * ry
    t: float | None = None
    if abs(a) < 1e-9:
        if abs(b) > 1e-9:
            t = -c / b
    else:
        disc = b * b - 4 * a * c
        if disc >= 0:
            sq = math.sqrt(disc)
            cands = [x for x in ((-b - sq) / (2 * a), (-b + sq) / (2 * a)) if x > 0]
            t = min(cands) if cands else None
    if t is None or t <= 0:
        return bearing(rx, ry)
    return bearing(rx + tvx * t, ry + tvy * t)


def tube_origin(ship: Ship, tube: Tube | Launcher) -> tuple[float, float]:
    return ship.hull_to_world(*tube.mount.pos)


def tube_solution(world: World, ship: Ship, tube: Tube, target_id: int | None) -> float | None:
    """World bearing a tube would launch on, or None if arcs are on (`Rules.tube_arcs`) and it lies outside."""
    loaded = tube.loaded
    if loaded is None:
        return None
    spec = world.content.torpedoes[loaded.ordnance]
    ox, oy = tube_origin(ship, tube)
    if target_id is None:
        aim = norm360(ship.course + tube.mark)
    else:
        track = world.track(ship.side, target_id)
        if track is None:
            return None
        tx, ty, vx, vy = track
        if spec.homing:
            aim = bearing(tx - ox, ty - oy)
        else:
            aim = intercept_bearing(ox, oy, tx, ty, vx, vy, spec.velocity * world.rules.units_per_warp)
    aim = norm360(aim + tube.dispersion)
    rel = norm360(aim - ship.course)
    if world.rules.tube_arcs and not in_arc(rel, tube.mount.arc_center, tube.mount.arc_width):
        return None
    return aim


# ------------------------------------------------------------- launches

def launch_torpedoes(
    world: World,
    ship: Ship,
    tubes: list[Tube],
    target_id: int | None,
    selector: str | None = None,
    fan: float = 0.0,
) -> int:
    """Fire the given loaded tubes. Returns the number of torpedoes launched."""
    rules = world.rules
    rng = world.rng
    n = len(tubes)
    fired = 0
    salvo: dict[tuple[str, float], Torpedo] = {}
    for k, tube in enumerate(tubes):
        loaded = tube.loaded
        if loaded is None:
            continue
        aim = tube_solution(world, ship, tube, target_id)
        if aim is None:
            continue
        if fan > 0 and n > 1:
            aim = norm360(aim - fan / 2 + fan * k / (n - 1))
        soph = ship.sophistication
        # fire-control solution error shrinks with computer quality [E]
        aim = norm360(aim + rng.gauss(0.0, (1.0 - soph) * 2.0))
        spec = world.content.torpedoes[loaded.ordnance]
        tube.loaded = None
        tube.charge = 0.0
        tube.mark = norm360(aim - ship.course)
        ox, oy = tube_origin(ship, tube)
        # one launch at one target with the same ordnance and prox forms a torpedo group [M]
        key = (spec.id, loaded.prox)
        fired += 1
        if fan <= 0 and key in salvo:
            salvo[key].salvo += 1  # Begin torpedo group [R]
            continue
        vel = spec.velocity * (1.0 + rng.uniform(-spec.speed_variance, spec.speed_variance))
        torp = Torpedo(
            id=world.new_id(), owner=ship.id, side=ship.side, spec=spec, x=ox, y=oy, course=aim,
            velocity=vel, prox=loaded.prox, arm=spec.arm_time, fuse=spec.max_time_fuse,
            strength=spec.max_time_fuse, target=target_id if spec.homing else None,
            aim_ship=target_id if selector else None, target_subsystem=selector,
        )
        torp.trail.append((ox, oy))
        salvo[key] = torp
        world.torpedoes.append(torp)
        world.emit(TorpedoLaunched(world.tick, ship.id, torp.id, tube.index, 1, spec.id))
    if fired:
        ship.stats.torpedoes_fired += fired
        ship.reveal_time = max(ship.reveal_time, rules.cloak_reveal_cycles)
        if target_id is not None:
            world.note_torpedo_pressure(target_id, fired)
            _mark_blind(world, ship, list(salvo.values()) if fan <= 0 else world.torpedoes[-fired:], target_id)
    return fired


def _mark_blind(world: World, ship: Ship, torps: list[Torpedo], target_id: int | None) -> None:
    """[E] Rounds fired at a ship our sensors can't see go to its last known position. Tell the captain so,
    and mark them, so that how they end (a hit, a burst on nothing, a fuse run out) is reported too."""
    if target_id is None or ship.side != world.player_side or world.is_visible(ship.side, target_id):
        return
    for t in torps:
        if t.spec.reveal_radius <= 0:
            t.blind = target_id
    if not any(t.blind is not None for t in torps):
        return
    pos = world.apparent_position(ship.side, target_id)
    where = f" (bearing {_fix(ship, pos)})" if pos is not None else ""
    n = sum(t.salvo for t in torps if t.blind is not None)
    world.emit(Message(world.tick, f"No sensor lock on {_name(world, ship.side, target_id)}: "
                                   f"{'torpedo' if n == 1 else f'{n} torpedoes'} going to her last known position{where}.",
                       Tone.CAUTION, ship_id=ship.id, visible_to=frozenset({ship.side})))


def _name(world: World, side: int, ship_id: int) -> str:
    """The ship's name if we know it, as the crew would say it."""
    s = world.ships.get(ship_id)
    c = world.intel.get(side)
    contact = c.contacts.get(ship_id) if c is not None else None
    if s is not None and contact is not None and contact.identified:
        return f"the {s.name}"
    return "the contact"


def _fix(ship: Ship, pos: tuple[float, float]) -> str:
    return f"{bearing(pos[0] - ship.x, pos[1] - ship.y):.0f}, range {math.hypot(pos[0] - ship.x, pos[1] - ship.y):,.0f}"


def report_blind_shots(world: World, done: list[tuple[Torpedo, str, set[int]]]) -> None:
    """[E] Tell the captain how rounds fired at an unseen ship ended: one line per firing ship.

    `done` holds (torpedo, how it ended, ships its blast reached); how it ended is "burst" or "fizzled".
    Without this, a miss in the dark is silent and a hit shows nothing, so the captain can't tell either.
    """
    by_owner: dict[int, list[tuple[Torpedo, str, set[int]]]] = {}
    for item in done:
        if item[0].blind is not None:
            by_owner.setdefault(item[0].owner, []).append(item)
    for owner_id, items in by_owner.items():
        owner = world.ships.get(owner_id)
        if owner is None or not owner.exists:
            continue
        target = items[0][0].blind
        assert target is not None
        name = _name(world, owner.side, target)
        enemies = {sid for _, _, hit in items for sid in hit
                   if (s := world.ships.get(sid)) is not None and s.side != owner.side}
        hit = next(((t, hit) for t, _, hit in items if target in hit), None)
        if hit is not None:
            t = hit[0]
            text = (f"Torpedo hit at bearing {_fix(owner, (t.x, t.y))}: that was {name}. "
                    f"She shows through her cloak for a moment.") if _cloaked(world, target) else (
                    f"Torpedo hit {name} at bearing {_fix(owner, (t.x, t.y))}.")
            tone = Tone.GOOD
        elif enemies:
            t = items[0][0]
            text = f"Torpedo hit something at bearing {_fix(owner, (t.x, t.y))}, but not {name}."
            tone = Tone.GOOD
        else:
            n = sum(t.salvo for t, _, _ in items)
            t = items[0][0]
            shot = [x for x, how, _ in items if x.shot_down]
            if shot:
                text = (f"Torpedo shot down at bearing {_fix(owner, (shot[0].x, shot[0].y))}. "
                        f"Someone's point defense is close by.")
            elif all(how == "fizzled" for _, how, _ in items):
                text = (f"{'Torpedo' if n == 1 else f'{n} torpedoes'} ran out of fuse with no hit. "
                        f"No sign of {name} where we aimed.")
            else:
                text = (f"{'Torpedo' if n == 1 else f'{n} torpedoes'} burst at bearing {_fix(owner, (t.x, t.y))} "
                        f"with nothing in reach. No sign of {name} there.")
            tone = Tone.CAUTION
        world.emit(Message(world.tick, text, tone, ship_id=owner.id, visible_to=frozenset({owner.side})))


def _cloaked(world: World, ship_id: int) -> bool:
    s = world.ships.get(ship_id)
    return s is not None and s.cloaked


def launch_probe(
    world: World, ship: Ship, launcher: Launcher, target_id: int | None, course: float | None
) -> Probe | None:
    loaded = launcher.loaded
    if loaded is None:
        return None
    spec = world.content.probes[loaded.ordnance]
    ox, oy = tube_origin(ship, launcher)
    if target_id is not None:
        pos = world.apparent_position(ship.side, target_id)
        if pos is None:
            return None
        crs = bearing(pos[0] - ox, pos[1] - oy)
    else:
        crs = norm360(course if course is not None else ship.course)
    launcher.loaded = None
    launcher.prep = 0.0
    tgt = world.ships.get(target_id) if target_id is not None else None
    probe = Probe(
        id=world.new_id(), owner=ship.id, side=ship.side, spec=spec, code=loaded.code, x=ox, y=oy,
        course=crs, prox=loaded.prox, arm=spec.arm_time, fuse=loaded.time, target=target_id,
        deliberate_target=tgt is not None and tgt.side == ship.side,
    )
    probe.trail.append((ox, oy))
    world.probes.append(probe)
    ship.stats.probes_launched += 1
    world.emit(ProbeLaunched(world.tick, ship.id, probe.id, probe.code))
    return probe


# ------------------------------------------------------------- flight

def fly_ordnance(world: World, dt: float, prev: dict[int, tuple[float, float]]) -> None:
    """Guide, move and fuse every torpedo and probe for one tick."""
    upw = world.rules.units_per_warp
    ships = [s for s in world.ships.values() if s.exists and s.docked_to is None]

    for t in world.torpedoes:
        if t.detonate or t.fizzle:
            continue
        if t.target is not None:  # homing (plasma) turns almost instantly [M]
            pos = world.apparent_position(t.side, t.target)
            if pos is not None:
                t.course = bearing(pos[0] - t.x, pos[1] - t.y)
        x0, y0 = t.x, t.y
        r = math.radians(t.course)
        step = t.velocity * upw * dt
        t.x += math.sin(r) * step
        t.y += math.cos(r) * step
        was_armed = t.armed
        t.arm -= dt
        if t.armed:
            if was_armed:
                t.fuse -= dt
                if t.spec.is_plasma:
                    t.strength -= dt
            hit = _sweep_hits(t.x, t.y, x0, y0, t.prox, ships, prev, side=None, deliberate=None, step=step)
            if hit is not None:
                t.x, t.y = _fuse_point(world, x0, y0, t.x, t.y, hit)
                t.detonate = True
                continue
            if t.fuse <= 0.0:
                if t.spec.reveal_radius > 0 or t.burst_at_fuse:
                    t.detonate = True  # [E] a round fused for a point bursts where its fuse runs out
                else:
                    t.fizzle = True  # torpedoes expire quietly [R]
        if len(t.trail) == 0 or math.hypot(t.x - t.trail[-1][0], t.y - t.trail[-1][1]) > 120:
            t.trail.append((t.x, t.y))
            if len(t.trail) > 8:
                del t.trail[0]

    for p in world.probes:
        if p.detonate:
            continue
        if p.target is not None:
            pos = world.apparent_position(p.side, p.target)
            if pos is not None:
                p.course = bearing(pos[0] - p.x, pos[1] - p.y)
        x0, y0 = p.x, p.y
        r = math.radians(p.course)
        step = p.spec.velocity * upw * dt
        p.x += math.sin(r) * step
        p.y += math.cos(r) * step
        was_armed = p.armed
        p.arm -= dt
        if p.armed:
            if was_armed:
                p.fuse -= dt
            deliberate = p.target if p.deliberate_target else None
            hit = _sweep_hits(p.x, p.y, x0, y0, p.prox, ships, prev, side=p.side, deliberate=deliberate, step=step)
            if hit is not None:
                p.x, p.y = _fuse_point(world, x0, y0, p.x, p.y, hit)
                p.detonate = True
                continue
            if p.fuse <= 0.0:
                p.detonate = True  # probes blow up on expiry [R]
        if len(p.trail) == 0 or math.hypot(p.x - p.trail[-1][0], p.y - p.trail[-1][1]) > 90:
            p.trail.append((p.x, p.y))
            if len(p.trail) > 14:
                del p.trail[0]


def _sweep_hits(
    x1: float, y1: float, x0: float, y0: float, prox: float, ships: list[Ship],
    prev: dict[int, tuple[float, float]], side: int | None, deliberate: int | None, step: float,
) -> float | None:
    """Earliest path fraction (0..1) at which a ship comes inside the proximity fuse, or None.

    Motion is swept continuously in each ship's frame, so fast weapons can't
    tunnel through a target between ticks.
    """
    reach = prox + step + 1500.0
    best: float | None = None
    for s in ships:
        if side is not None and s.side == side and s.id != deliberate:
            continue
        if abs(s.x - x1) > reach or abs(s.y - y1) > reach:
            continue
        sx0, sy0 = prev.get(s.id, (s.x, s.y))
        rx, ry = x0 - sx0, y0 - sy0
        dx, dy = (x1 - s.x) - rx, (y1 - s.y) - ry
        c = rx * rx + ry * ry - prox * prox
        if c <= 0.0:
            frac = 0.0
        else:
            a = dx * dx + dy * dy
            if a < 1e-12:
                continue
            b = 2.0 * (rx * dx + ry * dy)
            disc = b * b - 4.0 * a * c
            if disc < 0.0:
                continue
            frac = (-b - math.sqrt(disc)) / (2.0 * a)
            if not 0.0 <= frac <= 1.0:
                continue
        if best is None or frac < best:
            best = frac
    return best


def _fuse_point(world: World, x0: float, y0: float, x1: float, y1: float, entry: float) -> tuple[float, float]:
    """Where the fuse fires: Begin samples fuses once per sub-cycle, so the
    weapon goes off somewhere between entering the fuse radius and the next
    sample [R]. We draw that sample phase from the battle RNG."""
    f = entry + world.rng.unit() * (1.0 - entry)
    return x0 + (x1 - x0) * f, y0 + (y1 - y0) * f


# ------------------------------------------------------------- blasts

def resolve_detonations(world: World) -> None:
    """Blast every detonating weapon; chains continue until quiet [R §7, §13]."""
    ended: list[tuple[Torpedo, str, set[int]]] = []   # how each torpedo ended, for the blind-shot report
    for _ in range(64):  # chain guard
        boom_t = [t for t in world.torpedoes if t.detonate]
        boom_p = [p for p in world.probes if p.detonate]
        quiet = [t for t in world.torpedoes if t.fizzle and not t.detonate]
        if quiet:
            world.torpedoes = [t for t in world.torpedoes if not (t.fizzle and not t.detonate)]
            ended.extend((t, "fizzled", set()) for t in quiet)
        if not boom_t and not boom_p:
            break
        world.torpedoes = [t for t in world.torpedoes if not t.detonate]
        world.probes = [p for p in world.probes if not p.detonate]
        for t in boom_t:
            if t.spec.reveal_radius > 0:
                reveal_burst(world, t)
                continue
            kind = DamageKind.SHIELD_BORE if t.spec.is_shield_bore else (
                DamageKind.PLASMA if t.spec.is_plasma else DamageKind.BLAST)
            cause = "intercepted" if t.shot_down else "fuse" if t.burst_at_fuse and t.fuse <= 0.0 else "proximity"
            reached = blast(world, t.x, t.y, t.yield_, "torpedo", t.owner, t.salvo, kind,
                            t.target if t.target is not None else t.aim_ship, t.target_subsystem, cause=cause,
                            radius_scale=t.spec.blast_scale)
            ended.append((t, "burst", reached))
        for p in boom_p:
            blast(world, p.x, p.y, p.yield_, "probe", p.owner, 1, DamageKind.BLAST, p.target, None)
    if any(t.blind is not None for t, _, _ in ended):
        report_blind_shots(world, ended)


def reveal_burst(world: World, t: Torpedo) -> None:
    """[E] A detector round's particle cloud: cloaked ships inside it show on sensors for a while."""
    r = t.spec.reveal_radius
    world.emit(Detonation(world.tick, t.x, t.y, r, "tachyon", 0.0))
    found = 0
    for s in world.ships.values():
        if s.alive and s.cloaked and math.hypot(s.x - t.x, s.y - t.y) <= r:
            s.reveal_time = max(s.reveal_time, t.spec.reveal_cycles)
            found += 1
    owner = world.ships.get(t.owner)
    if owner is not None:
        text = (f"Tachyon burst: {found} cloaked ship{'s' if found != 1 else ''} lit up for "
                f"{t.spec.reveal_cycles:.0f} cycles." if found else "Tachyon burst: no cloaked ships in the cloud.")
        world.emit(Message(world.tick, text, Tone.GOOD if found else Tone.CAUTION, ship_id=owner.id,
                           visible_to=frozenset({owner.side})))


def blast_radius(spec: TorpedoDef, rules: Rules) -> float:
    """[R] how far a warhead's blast reaches: yield × splash multiplier × radius per damage
    (× the design's own blast scale [E])."""
    return spec.damage * rules.splash_mult * rules.splash_radius_per_damage * spec.blast_scale


def suggested_prox(spec: TorpedoDef, target_max_warp: float, rules: Rules) -> float:
    """[E] A proximity setting that catches an agile target yet still delivers most of the blast.

    A round bursts as soon as its target comes within the proximity setting, and blast damage
    falls to nothing at the blast radius, so a fuse near the radius (Mark 7: 500 of 500) only
    grazes. Begin's AI used warp × 50; we cap it at half the blast radius (about 70% damage).
    """
    want = min(target_max_warp * 50.0, blast_radius(spec, rules) * 0.5, spec.max_prox)
    return max(rules.prox_floor, want)


def launch_at_point(world: World, ship: Ship, tube: Tube, x: float, y: float, prox: float | None = None,
                    target: int | None = None, subsystem: str | None = None) -> Torpedo | None:
    """Fire one tube's round straight at a point, fused to burst there [E].

    Used for detector rounds, and for ordinary torpedoes burst beside or between
    ships (`prox` overrides the round's proximity setting; `target` and
    `subsystem` aim the blast at one ship's systems, as an aimed torpedo would).
    """
    loaded = tube.loaded
    if loaded is None:
        return None
    spec = world.content.torpedoes[loaded.ordnance]
    ox, oy = tube_origin(ship, tube)
    aim = bearing(x - ox, y - oy)
    speed = spec.velocity * world.rules.units_per_warp
    travel = math.hypot(x - ox, y - oy) / max(1.0, speed)
    tube.loaded = None
    tube.charge = 0.0
    tube.mark = norm360(aim - ship.course)
    torp = Torpedo(
        id=world.new_id(), owner=ship.id, side=ship.side, spec=spec, x=ox, y=oy, course=aim,
        velocity=spec.velocity, prox=loaded.prox if prox is None else prox, arm=min(spec.arm_time, travel),
        fuse=max(0.05, travel - spec.arm_time), strength=spec.max_time_fuse, aim_ship=target,
        target_subsystem=subsystem, burst_at_fuse=True,
    )
    torp.trail.append((ox, oy))
    world.torpedoes.append(torp)
    world.emit(TorpedoLaunched(world.tick, ship.id, torp.id, tube.index, 1, spec.id))
    ship.stats.torpedoes_fired += 1
    ship.reveal_time = max(ship.reveal_time, world.rules.cloak_reveal_cycles)
    _mark_blind(world, ship, [torp], target)
    return torp


def blast(
    world: World,
    x: float,
    y: float,
    yield_: float,
    source: str,
    owner: int | None,
    salvo: int = 1,
    kind: DamageKind = DamageKind.BLAST,
    target: int | None = None,
    selector: str | None = None,
    exclude: int | None = None,
    cause: str = "",
    radius_scale: float = 1.0,
) -> set[int]:
    """[R] total = yield × 5; radius = total × 10; dmg = total × sqrt(1 − d/radius).

    Returns the ships the blast reached."""
    if yield_ <= 0:
        return set()
    rules = world.rules
    total = yield_ * rules.splash_mult
    radius = total * rules.splash_radius_per_damage * radius_scale
    world.emit(Detonation(world.tick, x, y, radius, source, yield_ * salvo, owner, cause))
    att = world.ships.get(owner) if owner is not None else None
    hit_any = False
    reached: set[int] = set()
    for s in list(world.ships.values()):
        if s.id == exclude or not s.exists or s.docked_to is not None:
            continue
        d = math.hypot(s.x - x, s.y - y)
        if d >= radius:
            continue
        reached.add(s.id)
        dmg = total * math.sqrt(1.0 - d / radius)
        aim = None
        if selector and target == s.id and att is not None:
            aim = Aim(selector, rules.aimed_torpedo_accuracy * att.sophistication
                      * (1.0 + rules.morale_accuracy * att.morale_factor))
        for _ in range(max(1, salvo)):
            if not s.exists:
                break
            apply_damage(world, s, dmg, x, y, kind, owner, aim)
        if att is not None and s.side != att.side:
            hit_any = True
    if att is not None and hit_any:
        if source == "torpedo":
            att.stats.torpedo_hits += salvo
        elif source == "probe":
            att.stats.probe_hits += 1
    # any energy sets off other ordnance; plasma bleeds [R]
    for t in world.torpedoes:
        if t.detonate or t.fizzle:
            continue
        d = math.hypot(t.x - x, t.y - y)
        if d < radius:
            if t.spec.is_plasma:
                t.strength -= total * math.sqrt(1.0 - d / radius)
                if t.strength <= 0:
                    t.fizzle = True
            else:
                t.detonate = True
    for p in world.probes:
        if not p.detonate and math.hypot(p.x - x, p.y - y) < radius:
            p.detonate = True
            p.remote = True
    return reached
