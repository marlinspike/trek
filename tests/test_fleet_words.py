"""Fleet orders and officer requests in everyday words, with no language model (the deep sweep, 2026-11-13):
'all ships, attack the Gorkon', 'Yorktown, defend me', 'more power to the engines', 'reinforce the aft shields'."""

from __future__ import annotations

import pytest

from begin.console.parser import ParseContext, parse
from begin.sim.commands import AllyOrder, EngineBoost, Pursue, ReinforceShield, SetHelm, SetRepairPriority
from begin.sim.world import World


def _fleet(content):  # type: ignore[no-untyped-def]
    w = World(content, seed=4)
    me = w.add_ship("federation.hc", 0, 0, 0, name="Enterprise")
    a = w.add_ship("federation.hc", 0, 2000, 0, name="Yorktown")
    b = w.add_ship("federation.hc", 0, -2000, 0, name="Excalibur")
    w.add_ship("klingon.bc", 1, 0, 6000, name="Gorkon")
    w.run(1.0)
    return w, me, a, b


def _cmds(w, me, text):  # type: ignore[no-untyped-def]
    res = parse(text, ParseContext(me.id, w.observe(0)))
    assert res.error is None, f"{text!r}: {res.error}"
    return res.commands


def _gorkon(w):  # type: ignore[no-untyped-def]
    return next(s for s in w.ships.values() if s.name == "Gorkon")


@pytest.mark.parametrize("text,order", [
    ("all ships, attack the Gorkon", "attack"), ("fleet, form up on me", "escort"), ("squadron, hold fire", "hold"),
    ("wingmen, open fire", "open"), ("all ships fall back", "run"),
    ("tell all escort me", "escort"), ("fleet, cover me", "escort"),
])
def test_an_order_to_the_fleet_reaches_every_ally(content, text: str, order: str) -> None:  # type: ignore[no-untyped-def]
    w, me, a, b = _fleet(content)
    got = [c for c in _cmds(w, me, text) if isinstance(c, AllyOrder)]
    assert sorted(c.ally for c in got) == sorted([a.id, b.id])
    assert {c.order for c in got} == {order}
    if order == "attack":
        assert {c.target for c in got} == {_gorkon(w).id}


def test_the_fleet_reports_in(content) -> None:  # type: ignore[no-untyped-def]
    w, me, _, _ = _fleet(content)
    res = parse("task force, report", ParseContext(me.id, w.observe(0)))
    shown = " ".join(res.display)
    assert res.error is None and "Yorktown" in shown and "Excalibur" in shown


def test_a_bare_fleet_still_shows_the_fleet(content) -> None:  # type: ignore[no-untyped-def]
    w, me, _, _ = _fleet(content)
    assert not any(isinstance(c, AllyOrder) for c in _cmds(w, me, "fleet"))


@pytest.mark.parametrize("text,order", [
    ("Yorktown, defend me", "defend"), ("yorktown attack the gorkon", "attack"), ("Yorktown, fall back", "run"),
    ("tell yorktown to fall back", "run"), ("Yorktown, escort me", "escort"), ("Yorktown, attack my target", "attack"),
])
def test_an_ally_answers_to_its_name(content, text: str, order: str) -> None:  # type: ignore[no-untyped-def]
    w, me, a, _ = _fleet(content)
    me.target = _gorkon(w).id
    got = [c for c in _cmds(w, me, text) if isinstance(c, AllyOrder)]
    assert [(c.ally, c.order) for c in got] == [(a.id, order)]


@pytest.mark.parametrize("text", ["more power to the engines", "divert power to engines"])
def test_power_to_the_engines_is_the_boost(content, text: str) -> None:  # type: ignore[no-untyped-def]
    w, me, _, _ = _fleet(content)
    assert any(isinstance(c, EngineBoost) for c in _cmds(w, me, text))


@pytest.mark.parametrize("text,sector", [
    ("reinforce the aft shields", 5), ("divert power to the aft shields", 5), ("reinforce forward", 0),
    ("strengthen the forward shields", 0), ("reinforce 2", 1),
])
def test_a_shield_side_can_be_named(content, text: str, sector: int) -> None:  # type: ignore[no-untyped-def]
    w, me, _, _ = _fleet(content)
    me.course = 0.0
    got = [c for c in _cmds(w, me, text) if isinstance(c, ReinforceShield)]
    assert [c.sector for c in got] == [sector]


def test_plain_reinforce_faces_the_enemy(content) -> None:  # type: ignore[no-untyped-def]
    w, me, _, _ = _fleet(content)
    me.course = 0.0
    got = [c for c in _cmds(w, me, "reinforce the shields") if isinstance(c, ReinforceShield)]
    want = me.shield_for_bearing(0.0).index       # the Gorkon lies dead ahead
    assert [c.sector for c in got] == [want]


@pytest.mark.parametrize("text,check", [
    ("give me warp 8", lambda c: isinstance(c, SetHelm) and c.warp == 8.0),
    ("ahead full", lambda c: isinstance(c, SetHelm) and c.warp is not None and c.warp > 8),
    ("lay in a course for the Gorkon", lambda c: isinstance(c, Pursue)),
    ("can you get the warp drive back?", lambda c: isinstance(c, SetRepairPriority)),
])
def test_everyday_helm_and_repair_words(content, text: str, check) -> None:  # type: ignore[no-untyped-def]
    w, me, _, _ = _fleet(content)
    assert any(check(c) for c in _cmds(w, me, text)), text
