"""How the weapons are divided between two ships [E]: the judgement behind "Worf, engage the Talon and the Wraith".

`divide` looks at where each ship is and what each of our banks and tubes can reach, and chooses one of five ways:

- **all**: everything on one ship (the other is out of reach, or nothing bears on her);
- **weapons**: phasers on the ship inside phaser range, torpedoes on the one only torpedoes can reach;
- **tubes**: phasers on one, the tubes divided between both (both inside the torpedo window);
- **phasers**: the banks divided (each on the ship it bears on), the tubes on one;
- **both**: banks and tubes both divided.

Which ship comes first: one we have already crippled (her hull a third gone or worse) so she is finished off, else
the nearer. When the tubes are divided she gets the larger share if she is the bigger ship. A bank or tube goes to
the ship its arc covers; the rest make up the numbers. Nothing here fires: the split is a set of per-mount locks
(`SplitFire`), and the officer (crew/objectives.py `plan_engage`), the captain's F and T, or assisted fire send
each mount at its own ship. Pure functions of what our side can see, so the console's `split <ship> <ship>` uses
the same judgement as the officers.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from ..ai.computer import torpedo_envelope
from ..console.readback import runs, split_words
from ..core.angles import bearing, in_arc, norm360
from ..sim.observation import ContactView, Observation
from ..sim.ship import BankRole, Ship
from ..sim.systems.phasers import bank_bears_point

FINISH_HULL = 0.67          # a ship with this share of her hull or less left is finished off first
BIG_SHARE = 0.75            # the bigger ship's share of the tubes when they are divided (else half)
BIG_MASS = 1.5              # "bigger": this many times the other's mass
TORPEDO_REACH = 0.85        # share of the torpedo envelope's far edge counted as in reach (as fire control does)
KINDS = ("all", "weapons", "tubes", "phasers", "both")


@dataclass(frozen=True)
class Division:
    """Which of our banks and tubes go to which ship. Indices are zero-based; every usable mount is on one."""

    kind: str                                 # one of KINDS
    primary: int                              # the ship that comes first
    banks: dict[int, tuple[int, ...]]         # target -> banks
    tubes: dict[int, tuple[int, ...]]         # target -> tubes
    why: str = ""                             # the reason, in a few words ("the Wraith is out of phaser range")

    def key(self) -> tuple[object, ...]:
        """What makes two divisions the same, for an officer who doesn't re-plan for nothing."""
        return (self.kind, self.primary, tuple(sorted(self.banks.items())), tuple(sorted(self.tubes.items())))

    def targets(self) -> list[int]:
        return list(dict.fromkeys([self.primary, *self.banks, *self.tubes]))

    def words(self, name_of: Callable[[int], str]) -> str:
        """The split as an officer reads it back: "Tubes 1-4 on the Talon, 5-8 on the Wraith; phasers on the Talon."""
        return split_words(self.banks, self.tubes, name_of)


def hull_left(c: ContactView | None) -> float | None:
    """Her hull as our hits and scans have shown it, 0 to 1; None if we haven't seen it."""
    if c is None:
        return None
    if c.assessed is not None and c.assessed.hull is not None:
        return c.assessed.hull
    return c.scan.structure_frac if c.scan is not None else None


def _tube_bears(obs: Observation, ship: Ship, i: int, c: ContactView) -> bool:
    t = ship.tubes[i]
    if not obs.rules.tube_arcs:
        return True
    rel = norm360(bearing(c.x - ship.x, c.y - ship.y) - ship.course)
    return in_arc(rel, t.mount.arc_center, t.mount.arc_width)


def torpedo_reach(obs: Observation, ship: Ship, c: ContactView) -> tuple[float, float]:
    """(nearest, farthest) range at which our torpedoes arm and still reach her; (0, 0) with no tubes."""
    if not ship.tubes:
        return (0.0, 0.0)
    t0 = next((t for t in ship.tubes if t.loaded is not None), ship.tubes[0])
    code = t0.loaded.ordnance if t0.loaded is not None else (t0.load_ordnance or ship.cls.torpedo)
    spec = obs.content.torpedoes.get(code)
    if spec is None:
        return (0.0, 0.0)
    return torpedo_envelope(ship, c.x, c.y, c.vx, c.vy, spec.velocity, spec.arm_time, spec.max_time_fuse,
                            obs.rules.units_per_warp)


def divide(obs: Observation, ship: Ship, targets: Sequence[int]) -> Division | None:
    """How best to divide our weapons between `targets` (the first two we can see); None if we see none."""
    seen = [c for t in dict.fromkeys(targets) if (c := obs.contact(t)) is not None and (c.visible or c.exhaust)
            and t not in obs.gone()][:2]
    if not seen:
        return None
    banks = [i for i, b in enumerate(ship.banks) if b.role != BankRole.DEFENSE]
    tubes = list(range(len(ship.tubes)))
    if len(seen) == 1:
        c = seen[0]
        return Division("all", c.id, {c.id: tuple(banks)} if banks else {}, {c.id: tuple(tubes)} if tubes else {})
    a, b = seen

    def dist(c: ContactView) -> float:
        return c.distance_to(ship.x, ship.y)

    # who comes first: the one already crippled (the worse of two), else the nearer
    def crippled(h: float | None) -> bool:
        return h is not None and h <= FINISH_HULL

    ha, hb = hull_left(a), hull_left(b)
    if crippled(hb) and (not crippled(ha) or (hb or 0.0) < (ha or 0.0)):
        a, b = b, a
    elif not crippled(ha) and dist(b) < dist(a):
        a, b = b, a
    first_why = "finishing her off" if crippled(hull_left(a)) else "the nearer"
    reach = ship.cls.banks_range
    in_ph = {c.id: dist(c) <= reach for c in (a, b)}
    lo_hi = {c.id: torpedo_reach(obs, ship, c) for c in (a, b)}
    in_tp = {c.id: lo_hi[c.id][1] > 0 and lo_hi[c.id][0] * 0.9 <= dist(c) <= lo_hi[c.id][1] * TORPEDO_REACH
             for c in (a, b)}

    # phasers: each bank on the ship it bears on, if both are in range; else all on the one in range (or the first)
    bank_to: dict[int, list[int]] = {a.id: [], b.id: []}
    if in_ph[a.id] and in_ph[b.id]:
        for i in banks:
            bk = ship.banks[i]
            on_a = bank_bears_point(ship, bk, a.x, a.y)
            on_b = bank_bears_point(ship, bk, b.x, b.y)
            bank_to[b.id if on_b and not on_a else a.id].append(i)
    else:
        bank_to[b.id if in_ph[b.id] and not in_ph[a.id] else a.id] = list(banks)

    # torpedoes
    tube_to: dict[int, list[int]] = {a.id: [], b.id: []}
    phasers_only_a = in_ph[a.id] and not in_ph[b.id]
    phasers_only_b = in_ph[b.id] and not in_ph[a.id]
    if in_tp[a.id] and in_tp[b.id] and not (phasers_only_a or phasers_only_b):
        mass_a = a.cls.mass if a.cls is not None else 1.0
        mass_b = b.cls.mass if b.cls is not None else 1.0
        share = BIG_SHARE if mass_a >= BIG_MASS * mass_b else 1 - BIG_SHARE if mass_b >= BIG_MASS * mass_a else 0.5
        want_a = max(1, min(len(tubes) - 1, round(len(tubes) * share))) if len(tubes) > 1 else len(tubes)
        only_b = [i for i in tubes if _tube_bears(obs, ship, i, b) and not _tube_bears(obs, ship, i, a)]
        only_a = [i for i in tubes if _tube_bears(obs, ship, i, a) and not _tube_bears(obs, ship, i, b)]
        rest = [i for i in tubes if i not in only_a and i not in only_b]
        tube_to[a.id] = list(only_a)
        tube_to[b.id] = list(only_b)
        for i in rest:                       # the low numbers to the first ship, as a captain would count them out
            (tube_to[a.id] if len(tube_to[a.id]) < want_a else tube_to[b.id]).append(i)
    elif phasers_only_a and in_tp[b.id]:
        tube_to[b.id] = list(tubes)          # phasers on the near one, torpedoes on the one only torpedoes reach
    elif phasers_only_b and in_tp[a.id]:
        tube_to[a.id] = list(tubes)
    elif in_tp[b.id] and not in_tp[a.id]:
        tube_to[b.id] = list(tubes)
    else:
        tube_to[a.id] = list(tubes)

    bank_split = all(bank_to[c.id] for c in (a, b))
    tube_split = all(tube_to[c.id] for c in (a, b))
    phasers_on = next((c for c in (a, b) if bank_to[c.id]), a)
    tubes_on = next((c for c in (a, b) if tube_to[c.id]), a)
    if bank_split and tube_split:
        kind, why = "both", "both are in reach of everything"
    elif tube_split:
        kind, why = "tubes", f"both are inside torpedo range; phasers on {first_why}"
    elif bank_split:
        kind, why = "phasers", "our banks bear on both"
    elif banks and tubes and phasers_on.id != tubes_on.id:
        kind, why = "weapons", "one is inside phaser range, the other only in torpedo range"
    else:
        kind = "all"
        on = a if bank_to[a.id] or tube_to[a.id] else b
        other = b if on is a else a
        why = (f"nothing reaches the {other.label} yet" if not in_ph[other.id] and not in_tp[other.id]
               else f"{first_why} first")
    first = on.id if kind == "all" else a.id
    return Division(kind, first, {t: tuple(v) for t, v in bank_to.items() if v},
                    {t: tuple(v) for t, v in tube_to.items() if v}, why)


def worth_splitting(obs: Observation, ship: Ship) -> tuple[int, int] | None:
    """Two enemies in reach at once while every weapon is on one of them: (the one we're on, the other), else None.
    Used by the tactical officer's proposal and the counsel."""
    tgt = ship.target
    if tgt is None or not ship.tubes and len(ship.banks) < 2:
        return None
    c = obs.contact(tgt)
    if c is None or not c.visible:
        return None
    locks = {b.lock for b in ship.banks if b.lock is not None} | {t.lock for t in ship.tubes if t.lock is not None}
    if len(locks) > 1:
        return None                               # already split
    others = [o for o in obs.hostile_contacts() if o.id != tgt and o.visible and o.id not in obs.gone()
              and o.cls is not None and o.cls.mass > 0]
    if not others:
        return None
    o = min(others, key=lambda x: x.distance_to(ship.x, ship.y))
    d = divide(obs, ship, (tgt, o.id))
    if d is None or d.kind == "all":
        return None
    return tgt, o.id


__all__ = ["BIG_MASS", "BIG_SHARE", "Division", "FINISH_HULL", "KINDS", "divide", "hull_left", "runs", "split_words",
           "torpedo_reach", "worth_splitting"]

