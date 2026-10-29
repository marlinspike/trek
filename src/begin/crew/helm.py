"""How an officer at the helm flies the ship in a fight [E].

The AI captain's helm (weave toward the target, open to torpedo standoff) is
good enough for enemy ships, but an officer flying for the captain is asked for
more: get out of the way of incoming torpedoes, keep the ship out of harm's
way, and give whoever is working the weapons the best chance.

`plan_helm` tries a spread of helm orders (course and warp), predicts where
each takes the ship over the next few seconds with the ship's real turn and
acceleration limits, and scores the outcome:

- incoming torpedoes: each one is flown along its straight course; a helm
  order whose path passes within its proximity fuse (plus a margin) is
  penalised by the warhead. Torpedoes are aimed at where the ship would be
  if it held its course, so turning or changing speed as soon as one is
  launched is what makes it miss;
- range: the distance the weapons officer wants (just inside torpedo reach
  for a salvo, out of the enemy's phaser reach while reloading);
- shields: the strongest shield toward the enemy, a weak one away.

The winner becomes an ordinary `SetHelm`, and the plan's reason is what the
officer reports ("Evading two torpedoes, coming to 270").
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..core.angles import bearing, norm360, turn_delta
from ..sim.observation import ContactView, Observation, OrdnanceView
from ..sim.ship import Ship

STEP = 0.25            # seconds per prediction step
HORIZON = 4.0          # seconds of prediction for range and facing
THREAT_LOOK = 6.0      # seconds a torpedo is followed
MARGIN = 150.0         # units beyond a torpedo's proximity fuse that still counts as too close
THREAT_RANGE = 9000.0  # torpedoes further than this are ignored
KNIFE_FIGHT = 1.5      # × the enemy's phaser range: inside this, a faster enemy is fought, not outrun
REL_COURSES = (0.0, 30.0, -30.0, 60.0, -60.0, 90.0, -90.0, 135.0, -135.0, 180.0)


@dataclass(frozen=True)
class HelmPlan:
    course: float
    warp: float
    reason: str             # "evade" | "close" | "open" | "hold", or the captain's own "approach" | "fight"
    threats: int            # torpedoes that would have hit on the old course
    dodged: int             # of those, how many miss on the new one
    want: float             # the range being kept
    range_now: float
    since: int = 0          # tick this kind of manoeuvre began

    def describe(self, target: str) -> str:
        if self.reason == "evade":
            n = "a torpedo" if self.threats == 1 else f"{self.threats} torpedoes"
            return f"Evading {n}, coming to {self.course:.0f} warp {self.warp:.0f}"
        if self.reason == "close":
            return f"Closing on {target} to {self.want:,.0f}"
        if self.reason == "open":
            return f"Opening the range from {target} to {self.want:,.0f}"
        if self.reason == "fight":
            return f"Fighting {target} at close range, strongest shield toward it"
        if self.reason == "approach":
            return f"Closing on {target}, weaving ({self.range_now:,.0f} away)"
        if self.range_now <= 0:
            return f"Holding course {self.course:.0f} warp {self.warp:.0f}"
        return f"Holding {target} at {self.range_now:,.0f}, best shield toward it"


def _path(ship: Ship, course: float, warp: float, upw: float, seconds: float) -> list[tuple[float, float]]:
    """Where the ship will be every STEP seconds under this helm order (the helm system's own limits)."""
    cls = ship.cls
    x, y, crs, w = ship.x, ship.y, ship.course, ship.warp
    want = max(0.0, min(warp, ship.max_attainable_warp))
    out: list[tuple[float, float]] = []
    for _ in range(int(seconds / STEP)):
        diff = want - w
        if abs(diff) < 0.05 or (want <= 1.0 and w <= 1.0):
            w = want
        elif diff > 0:
            w += min((cls.w1accel / w if w >= 1.0 else cls.w1accel) * STEP, diff)
        else:
            w -= min(cls.decel * STEP, -diff)
        d = turn_delta(crs, course)
        if d and cls.w1turn > 0:
            rate = cls.w1turn / max(abs(w), 1.0) * STEP
            crs = norm360(course) if abs(d) <= rate else norm360(crs + math.copysign(rate, d))
        r = math.radians(crs)
        x += math.sin(r) * w * upw * STEP
        y += math.cos(r) * w * upw * STEP
        out.append((x, y))
    return out


def _miss(path: list[tuple[float, float]], t: OrdnanceView) -> float:
    """The closest this torpedo comes to the ship along the predicted path."""
    r = math.radians(t.course)
    vx, vy = math.sin(r) * t.speed, math.cos(r) * t.speed
    best = math.hypot(t.x - path[0][0], t.y - path[0][1]) if path else 1e9
    for i, (x, y) in enumerate(path):
        k = (i + 1) * STEP
        best = min(best, math.hypot(t.x + vx * k - x, t.y + vy * k - y))
        # between samples the torpedo moves far: check the segment's closest point too
        k0 = i * STEP
        ax, ay = t.x + vx * k0 - x, t.y + vy * k0 - y
        sx, sy = vx * STEP, vy * STEP
        seg = sx * sx + sy * sy
        if seg > 0:
            u = max(0.0, min(1.0, -(ax * sx + ay * sy) / seg))
            best = min(best, math.hypot(ax + sx * u, ay + sy * u))
    return best


def incoming(obs: Observation, ship: Ship) -> list[OrdnanceView]:
    """Enemy torpedoes close enough to matter and not flying away from us."""
    out = []
    for t in obs.threats():
        if t.kind != "torpedo":
            continue
        dx, dy = ship.x - t.x, ship.y - t.y
        d = math.hypot(dx, dy)
        if d > THREAT_RANGE:
            continue
        r = math.radians(t.course)
        if d > 1500 and (math.sin(r) * dx + math.cos(r) * dy) <= 0:
            continue   # heading away
        out.append(t)
    return out


def threatened(obs: Observation, ship: Ship, threats: list[OrdnanceView]) -> int:
    """How many of these torpedoes would go off on us if the helm held its present order."""
    if not threats:
        return 0
    return _danger(_path(ship, ship.desired_course, ship.desired_warp, obs.rules.units_per_warp, THREAT_LOOK), threats)[1]


def _danger(path: list[tuple[float, float]], threats: list[OrdnanceView]) -> tuple[float, int]:
    cost, hits = 0.0, 0
    for t in threats:
        m = _miss(path, t)
        zone = t.prox + MARGIN
        if m < zone + 300.0:
            cost += t.yield_ * t.count * min(1.0, (zone + 300.0 - m) / 300.0)
        if m < zone:
            hits += t.count     # a salvo flies as one group: count its rounds
    return cost, hits


def plan_helm(obs: Observation, ship: Ship, c: ContactView | None, want: float | None,
              max_warp: float) -> HelmPlan | None:
    """The best helm order for the next few seconds, or None when there is nothing to fly against."""
    threats = incoming(obs, ship)
    if c is None and not threats:
        return None
    upw = obs.rules.units_per_warp
    look = max(HORIZON, THREAT_LOOK if threats else HORIZON)
    base = ship.desired_course
    courses = {norm360(base + d) for d in REL_COURSES}
    if c is not None:
        brg = bearing(c.x - ship.x, c.y - ship.y)
        courses |= {norm360(brg + d) for d in (0.0, 45.0, -45.0, 90.0, -90.0, 135.0, -135.0, 180.0)}
    top = max(1.0, min(max_warp, ship.max_attainable_warp))
    warps = sorted({round(top, 1), round(max(1.0, top * 0.6), 1), round(max(1.0, top * 0.3), 1), 0.0,
                    round(min(top, max(0.0, ship.desired_warp)), 1)})
    hold = _path(ship, ship.desired_course, ship.desired_warp, upw, look)
    _, threatened = _danger(hold, threats)
    best: tuple[float, float, float, int] | None = None
    h_idx = int(HORIZON / STEP) - 1
    for crs in courses:
        for w in warps:
            path = _path(ship, crs, w, upw, look)
            danger, hits = _danger(path, threats)
            score = -danger
            if c is not None:
                px, py = path[h_idx]
                tx, ty = c.x + c.vx * HORIZON, c.y + c.vy * HORIZON
                d = math.hypot(tx - px, ty - py)
                if want is not None:
                    score -= 4.0 * abs(d - want) / 1000.0
                # shields: the sector facing the enemy at the end of the turn, weighted by how hurt it is
                rel = norm360(bearing(tx - px, ty - py) - crs)
                sh = ship.shield_for_bearing(rel)
                if sh is not None:
                    score -= 2.0 * (1.0 - max(0.0, sh.effective) / 100.0)
            # a small preference for the order already given keeps the helm steady when nothing better is on offer
            if abs(turn_delta(crs, ship.desired_course)) < 1 and abs(w - ship.desired_warp) < 0.2:
                score += 0.3
            if best is None or score > best[0]:
                best = (score, crs, w, hits)
    assert best is not None
    _, crs, w, hits = best
    d_now = c.distance_to(ship.x, ship.y) if c is not None else 0.0
    if threatened and hits < threatened:
        reason = "evade"
    elif want is not None and c is not None and d_now > want + 600:
        reason = "close"
    elif want is not None and c is not None and d_now < want - 600:
        reason = "open"
    else:
        reason = "hold"
    return HelmPlan(crs, w, reason, threatened, threatened - hits, want or 0.0, d_now)


def support_range(obs: Observation, ship: Ship, c: ContactView) -> float | None:
    """The range that gives the weapons officer her torpedo shot: when a salvo is loaded, just inside torpedo
    reach and outside the enemy's phasers. None when there is no salvo to set up (then the captain's usual
    helm does the rest), or in a knife fight with a faster ship, which can't be held off."""
    rules = obs.rules
    loaded = [t for t in ship.tubes if t.intact and t.enabled and t.loaded is not None]
    usable = [t for t in ship.tubes if t.intact and t.enabled]
    if not usable or ship.torps_remaining <= 0 or len(loaded) < max(1, len(usable) // 2):
        return None
    their_banks = c.cls.banks_range if c.cls is not None else 2200.0
    d = c.distance_to(ship.x, ship.y)
    faster = c.cls is not None and c.cls.max_warp >= ship.max_attainable_warp
    if faster and d < their_banks * KNIFE_FIGHT:
        return None
    spec = obs.content.torpedoes.get(loaded[0].loaded.ordnance)  # type: ignore[union-attr]
    if spec is None:
        return None
    speed = spec.velocity * rules.units_per_warp
    lo = speed * spec.arm_time * 1.3
    hi = min(speed * (spec.arm_time + spec.max_time_fuse) * 0.9, speed * (spec.arm_time + 1.5))
    want = max(lo + 300.0, min(hi - 500.0, lo + (hi - lo) * 0.3), their_banks + 600.0)
    if faster and d < want:
        return None   # a faster ship can't be outrun: opening the range would only show it our stern
    return want


__all__ = ["HelmPlan", "incoming", "plan_helm", "support_range", "threatened"]
