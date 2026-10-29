"""Helm: warp acceleration, turning, pursue/elude, movement [R §2]."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

from ...core.angles import bearing, norm360, turn_delta
from ..ship import HelmMode, Ship

if TYPE_CHECKING:
    from ..world import World


def update_helm(world: World, ship: Ship, dt: float) -> None:
    rules = world.rules
    cls = ship.cls

    # pursue / elude re-aim at the (sensor-apparent) target position
    if ship.helm_mode != HelmMode.COURSE and ship.helm_target is not None:
        pos = world.apparent_position(ship.side, ship.helm_target)
        if pos is None:
            ship.helm_mode = HelmMode.COURSE
            ship.helm_target = None
        else:
            b = bearing(pos[0] - ship.x, pos[1] - ship.y)
            ship.desired_course = b if ship.helm_mode == HelmMode.PURSUE else norm360(b + 180.0)

    # desired warp clamp [R]: [-1, max attainable]
    maxw = ship.max_attainable_warp
    desired = max(rules.min_warp if maxw > 0 else 0.0, min(ship.desired_warp, maxw))
    diff = desired - ship.warp
    if abs(diff) < rules.warp_snap:
        ship.warp = desired
    elif desired <= 1.0 and ship.warp <= 1.0:
        # [R] instant below warp 1; [E] we still ramp over one tick-sized step for smooth motion
        ship.warp = desired
    elif diff > 0:
        rate = cls.w1accel / ship.warp if ship.warp >= 1.0 else cls.w1accel
        ship.warp += min(rate * dt, diff)
    else:
        ship.warp -= min(cls.decel * dt, -diff)

    # turning [R]: w1turn / warp per cycle, shortest way.
    # [E] at warp <= 1 Begin snaps instantly; we turn at the warp-1 rate so
    # real-time motion stays continuous (most classes still turn in < 2 s).
    d = turn_delta(ship.course, ship.desired_course)
    if d != 0.0:
        if cls.w1turn <= 0.0:
            return
        rate = cls.w1turn / max(abs(ship.warp), 1.0) * dt
        if abs(d) <= rate:
            ship.course = norm360(ship.desired_course)
        else:
            ship.course = norm360(ship.course + math.copysign(rate, d))


def move_ship(world: World, ship: Ship, dt: float) -> None:
    if ship.docked_to is not None:
        host = world.ships.get(ship.docked_to)
        if host is not None:
            ship.x, ship.y = host.x, host.y
            ship.warp = 0.0
            return
    v = ship.warp * world.rules.units_per_warp * dt
    r = math.radians(ship.course)
    ship.x += math.sin(r) * v
    ship.y += math.cos(r) * v
