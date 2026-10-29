"""Ally ships carry out `tell` orders the way the manual describes (pp. 22-25, Appendix D)."""

from __future__ import annotations

import math

from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle
from begin.console.parser import ParseContext, parse


def _battle(content, enemy_at=(0.0, 30000.0), loyal=1.0):  # type: ignore[no-untyped-def]
    pers = {"loyalty": loyal, "bravery": 1.0}
    setup = BattleSetup([
        FleetSpec(0, [ShipSpec("federation.hc", "Enterprise", 0, 0, 0),
                      ShipSpec("federation.de", "Agena", 2000, 0, 0, pers),
                      ShipSpec("federation.de", "Terra", -2000, 0, 0, pers),
                      ShipSpec("federation.sb", "Rigel", 0, -8000, 0, pers)], player=True),
        FleetSpec(1, [ShipSpec("klingon.fr", "Zantha", enemy_at[0], enemy_at[1], 180)]),
    ], seed=3)
    return build_battle(content, setup)


def order(b, text):  # type: ignore[no-untyped-def]
    w = b.world
    r = parse(text, ParseContext(b.player_ship_id, w.observe(0)))
    assert r.error is None, r.error
    for c in r.commands:
        assert w.execute(c) is None, text
    return r


def ship(b, name):  # type: ignore[no-untyped-def]
    return next(s for s in b.world.ships.values() if s.name == name)


def test_hold_course(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content)
    order(b, "tell agena course 90")
    b.world.run(20)
    a = ship(b, "Agena")
    assert abs(((a.course - 90) + 180) % 360 - 180) < 35
    assert a.x > 2000 + 1000


def test_escort_keeps_station(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content)
    order(b, "helm 0 warp 3")
    order(b, "order terra escort enterprise at 3000")
    b.world.run(60)
    t, e = ship(b, "Terra"), ship(b, "Enterprise")
    d = math.hypot(t.x - e.x, t.y - e.y)
    assert 1500 < d < 4500, d


def test_stop_and_cancel(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content)
    order(b, "tell agena stop")
    b.world.run(15)
    assert ship(b, "Agena").warp < 0.2
    order(b, "tell agena cancel")
    assert b.world.ally_orders[ship(b, "Agena").id].movement is None


def test_attack_sets_target_and_cancels_movement(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content, enemy_at=(0.0, 15000.0))
    order(b, "tell agena stop")
    order(b, "tell agena attack zantha")
    st = b.world.ally_orders[ship(b, "Agena").id]
    assert st.movement is None and st.target == ship(b, "Zantha").id
    b.world.run(3)
    assert ship(b, "Agena").target == ship(b, "Zantha").id


def test_withdraw_stays_out_of_torpedo_range(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content, enemy_at=(2000.0, 6000.0))
    order(b, "tell agena withdraw")
    b.world.run(40)
    a, z = ship(b, "Agena"), ship(b, "Zantha")
    assert math.hypot(a.x - z.x, a.y - z.y) > 9000


def test_hold_fire(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content, enemy_at=(2000.0, 3000.0))
    order(b, "tell agena hold fire")
    b.world.run(15)
    assert ship(b, "Agena").stats.phaser_shots == 0
    order(b, "tell agena open fire")
    assert not b.world.ally_orders[ship(b, "Agena").id].hold_fire


def test_dock_with_base(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content)
    order(b, "tell terra dock rigel")
    b.world.run(80)
    assert ship(b, "Terra").docked_to == ship(b, "Rigel").id
    order(b, "tell terra undock")
    assert ship(b, "Terra").docked_to is None


def test_beam_trades_ships(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content)
    old, new = ship(b, "Enterprise"), ship(b, "Agena")
    assert b.transfer_command(new.id) is None
    assert b.player_ship_id == new.id
    assert new.id not in b.captains and old.id in b.captains
    assert b.transfer_command(ship(b, "Rigel").id) is not None  # 8,000 away: out of transporter range


def test_quit_ends_the_simulation(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content)
    b.world.end_simulation()
    assert b.world.outcome.over


def test_tow_to_destination(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content)
    order(b, "tell terra stop")
    order(b, "tell agena tow terra to rigel")
    b.world.run(150)
    t, r = ship(b, "Terra"), ship(b, "Rigel")
    assert math.hypot(t.x - r.x, t.y - r.y) < 5000
    assert ship(b, "Agena").tractor_target is None  # released on arrival


def test_group_orders(content) -> None:  # type: ignore[no-untyped-def]
    b = _battle(content)
    order(b, "tell agena join 1")
    order(b, "tell terra join 1")
    r = order(b, "tell 1 course 180")
    assert len(r.commands) == 2
    assert all(b.world.ally_orders[ship(b, n).id].movement == "course" for n in ("Agena", "Terra"))
