"""Where ships' names go on the map, so a crowded fight stays readable [E].

Every name on the map asks for a spot beside its ship; once every hull is drawn, the asks are placed in order
of how much they matter: our own ship, the target and the selected ally first, then the rest, nearest to us
first. Each name tries the places round its ship (right, left, the four corners, then a row further out) and
takes the first that covers no other name, no other ship and none of the map's own writing. A name keeps the
side it had last frame while that side is still clear, so names don't hop about as ships move. A name with
nowhere clear to go is left out (its ship is still drawn, and the contacts list has it), except the ones that
matter most, which are pushed down a row at a time until they fit.

Pure geometry: no drawing, so it is quick to test.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

import pygame

GAP = 2                # pixels kept between two names
EDGE = 4               # pixels kept from the map's edge
NAME_ROW = 8           # a name sits this far above its ship's centre line
HULL_COST = 1.0        # a name over another ship's hull
OWN_COST = 3.0         # a name over its own ship (only when pushed in by the map's edge)
CHROME_COST = 6.0      # a name over the map's own writing (the clock, the title)
SLOT_COST = 0.02       # a little for each place further down the list, so the first clear one wins
KEEP_BONUS = 0.5       # the place a name had last frame, while it is still clear


@dataclass(frozen=True, slots=True)
class Ask:
    """A name that wants a place. `x`, `y`: her centre on screen; `clear`: how far from her centre the name
    must start to clear her art; `reach`: the right-most member of her group, if she names one."""
    key: int
    x: float
    y: float
    clear: float
    w: int
    h: int
    rank: tuple[float, ...] = (9.0,)
    must: bool = False
    reach: float | None = None


@dataclass(frozen=True, slots=True)
class Spot:
    x: int
    y: int
    w: int
    h: int
    slot: int

    @property
    def rect(self) -> pygame.Rect:
        return pygame.Rect(self.x, self.y, self.w, self.h)

    @property
    def right_side(self) -> bool:
        return self.slot in (0, 2, 3, 6, 7, 10)


def slots(a: Ask) -> list[tuple[int, float, float]]:
    """The places a name may go, in the order it tries them, by a fixed number (so a name can keep its place)."""
    c, w, h = a.clear, a.w, a.h
    rx = max(a.x, a.reach if a.reach is not None else a.x) + c        # right of her (and of her group)
    lx = a.x - c - w
    top = a.y - NAME_ROW
    d = c * 0.7
    step = h + GAP
    return [(0, rx, top), (1, lx, top),
            (2, a.x + d, a.y - d - h), (3, a.x + d, a.y + d), (4, a.x - d - w, a.y - d - h), (5, a.x - d - w, a.y + d),
            (6, rx, top + step), (7, rx, top - step), (8, lx, top + step), (9, lx, top - step),
            (10, rx, top + 2 * step), (11, lx, top + 2 * step)]


def _hull_hit(r: pygame.Rect, x: float, y: float, rad: float) -> bool:
    nx = min(max(x, r.left), r.right)
    ny = min(max(y, r.top), r.bottom)
    return (nx - x) ** 2 + (ny - y) ** 2 < rad * rad


@dataclass
class Placer:
    """Places a frame's names; remembers where each went, so it can keep its place next frame."""
    last: dict[int, int] = field(default_factory=dict)

    def place(self, asks: list[Ask], area: pygame.Rect, hulls: list[tuple[int, float, float, float]],
              keep_out: Sequence[pygame.Rect] = ()) -> dict[int, Spot]:
        """A spot for each name that has one. `hulls`: (key, x, y, radius) of every ship drawn."""
        placed: dict[int, Spot] = {}
        taken: list[pygame.Rect] = []
        for a in sorted(asks, key=lambda a: (not a.must, a.rank, a.key)):
            if not area.collidepoint(a.x, a.y):
                continue                     # off the map: no half a name cut by its edge
            spot = self._best(a, area, hulls, keep_out, taken)
            if spot is None and a.must:
                spot = self._pushed(a, area, taken)
            if spot is None:
                continue
            placed[a.key] = spot
            taken.append(spot.rect.inflate(GAP, GAP))
        self.last = {k: s.slot for k, s in placed.items()}
        return placed

    def _best(self, a: Ask, area: pygame.Rect, hulls: list[tuple[int, float, float, float]],
              keep_out: Sequence[pygame.Rect], taken: list[pygame.Rect]) -> Spot | None:
        best: tuple[float, Spot] | None = None
        kept = self.last.get(a.key)
        for i, (slot, x, y) in enumerate(slots(a)):
            r = _fit(pygame.Rect(int(x), int(y), a.w, a.h), area)
            if r.collidelist(taken) >= 0:
                continue
            cost = i * SLOT_COST - (KEEP_BONUS if slot == kept else 0.0)
            for key, hx, hy, hr in hulls:
                if _hull_hit(r, hx, hy, hr):
                    cost += OWN_COST if key == a.key else HULL_COST
            cost += CHROME_COST * sum(1 for k in keep_out if r.colliderect(k))
            if best is None or cost < best[0]:
                best = (cost, Spot(r.x, r.y, r.w, r.h, slot))
        return best[1] if best is not None else None

    @staticmethod
    def _pushed(a: Ask, area: pygame.Rect, taken: list[pygame.Rect]) -> Spot:
        """A name that must show: on her right, pushed down past the names in the way (or up, at the map's foot)."""
        slot, x, y = slots(a)[0]
        r = _fit(pygame.Rect(int(x), int(y), a.w, a.h), area)
        for _ in range(16):
            hit = r.collidelist(taken)
            if hit < 0:
                break
            r.top = taken[hit].bottom + 1
        if r.bottom > area.bottom - GAP:
            r.bottom = area.bottom - GAP
            for _ in range(16):
                hit = r.collidelist(taken)
                if hit < 0:
                    break
                r.bottom = taken[hit].top - 1
        return Spot(r.x, r.y, r.w, r.h, slot)


def _fit(r: pygame.Rect, area: pygame.Rect) -> pygame.Rect:
    r.left = max(area.left + EDGE, min(r.left, area.right - EDGE - r.width))
    r.top = max(area.top + GAP, min(r.top, area.bottom - GAP - r.height))
    return r


def fade(n_names: int, distance: float, must: bool, near: float, far: float) -> float:
    """How much a name fades (0 none, up to `FADE_MAX`): only in a crowded fight, and more the farther the ship
    is from ours. A quiet map, and the names that matter most, never fade."""
    if must:
        return 0.0
    crowd = min(1.0, max(0.0, (n_names - CROWD_FROM) / CROWD_SPAN))
    away = min(1.0, max(0.0, (distance - near) / max(1.0, far - near)))
    return FADE_MAX * crowd * away


CROWD_FROM = 6        # names on the map before any of them fade
CROWD_SPAN = 6        # ... and how many more before distant ones fade fully
FADE_MAX = 0.55


__all__ = ["Ask", "Placer", "Spot", "fade", "slots"]
