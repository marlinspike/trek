"""Aimed fire, the crew decks, and taking an enemy ship: knock a shield down, kill her crew, board her, keep her."""

from __future__ import annotations

from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle
from begin.console.parser import ParseContext, parse
from begin.sim.commands import SelectTarget, Transport
from begin.sim.ship import ShipStatus
from begin.sim.systems.damage import Aim, DamageKind, apply_damage
from begin.sim.world import World


def _pair(content):  # type: ignore[no-untyped-def]
    w = World(content, seed=4)
    fed = w.add_ship("federation.hc", 0, 0, 0, name="Enterprise")
    kl = w.add_ship("klingon.bc", 1, 0, 600, name="Votek")
    w.run(1.0)
    return w, fed, kl


def _volley(w, fed, kl, selector: str | None, n: int = 4) -> None:  # type: ignore[no-untyped-def]
    aim = Aim(selector, 0.6) if selector else None
    for _ in range(n):
        apply_damage(w, kl, 14, fed.x, fed.y, DamageKind.PHASER, fed.id, aim)


def _sel(w, me, text):  # type: ignore[no-untyped-def]
    res = parse(text, ParseContext(me.id, w.observe(0)))
    assert res.error is None, res.error
    return [c for c in res.commands if isinstance(c, SelectTarget)][0].subsystem


def test_systems_can_be_named_the_way_a_captain_would(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, kl = _pair(content)
    assert _sel(w, fed, "target votek warp core") == "power"
    assert _sel(w, fed, "target votek life support") == "crew"
    assert _sel(w, fed, "target votek shield generators") == "shields"
    assert _sel(w, fed, "target votek engines") == "propulsion"
    assert _sel(w, fed, "target votek hull") is None
    fed.target = kl.id
    assert _sel(w, fed, "aim at life support") == "crew"
    assert _sel(w, fed, "aim warp core") == "power"
    bad = parse("target votek tea service", ParseContext(fed.id, w.observe(0)))
    assert bad.error is not None and "life support" in bad.error      # it says what you can aim at


def test_aimed_fire_knocks_out_the_system_it_is_aimed_at(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, kl = _pair(content)
    for sh in kl.shields:
        sh.up = False
    for _ in range(6):
        _volley(w, fed, kl, "shields")
    assert any(sh.destroyed for sh in kl.shields)                   # a shield generator is gone for good
    assert all(d.damage < 50 for d in kl.drives)                    # and stray hits stay stray


def test_fire_on_the_crew_decks_kills_crew_and_spares_the_hull(content) -> None:  # type: ignore[no-untyped-def]
    w1, f1, k1 = _pair(content)
    w2, f2, k2 = _pair(content)
    for k in (k1, k2):
        for sh in k.shields:
            sh.up = False
    for _ in range(3):
        _volley(w1, f1, k1, None)
        _volley(w2, f2, k2, "crew")
    assert k2.crew < k1.crew - 60                                    # grave casualties
    assert k2.structure > k1.structure                               # and her hull mostly whole


def test_boarders_beam_through_any_shield_that_is_down(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, kl = _pair(content)
    for sh in fed.shields:
        sh.up, sh.effective = False, 0.0
    assert w.execute(Transport(ship_id=fed.id, target=kl.id, count=20)) is not None   # all of hers are up
    kl.shields[3].effective = 0.0                     # one down, though not the one facing us
    kl.shields[3].up = False
    assert w.execute(Transport(ship_id=fed.id, target=kl.id, count=20)) is None
    assert kl.boarders == 20


def test_a_derelict_drops_her_shields_and_can_be_taken(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, kl = _pair(content)
    w.lose_all_hands(kl, "casualties", fed.id)
    assert kl.status == ShipStatus.DERELICT and all(not sh.up for sh in kl.shields)
    for sh in fed.shields:
        sh.up, sh.effective = False, 0.0
    assert w.execute(Transport(ship_id=fed.id, target=kl.id, count=30)) is None
    w.run(2.0)
    assert kl.status == ShipStatus.ACTIVE and kl.side == fed.side and kl.crew == 30


def test_a_prize_crew_needs_only_a_little_life_support(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, kl = _pair(content)
    for r in kl.reactors:
        r.damage = 100
    kl.crew = 30
    w.run(6.0)
    assert kl.crew == 30 and kl.status == ShipStatus.ACTIVE    # the warp drives' spill keeps 30 people breathing


def test_a_captured_ship_joins_your_side_and_you_can_take_command(content) -> None:  # type: ignore[no-untyped-def]
    setup = BattleSetup([FleetSpec(side=0, player=True, center=(0.0, 0.0), ships=[ShipSpec("federation.hc")]),
                         FleetSpec(side=1, center=(0.0, 700.0),
                                   ships=[ShipSpec("klingon.bc", x=0.0, y=700.0), ShipSpec("klingon.bc", x=0.0, y=40000.0)])],
                        seed=3)
    b = build_battle(content, setup)
    w = b.world
    me = w.ships[b.player_ship_id]
    prize = min((s for s in w.ships.values() if s.side == 1), key=lambda s: abs(s.y - me.y))
    old_captain = b.captains[prize.id]
    w.lose_all_hands(prize, "casualties", me.id)
    for sh in me.shields:
        sh.up, sh.effective = False, 0.0
    assert w.execute(Transport(ship_id=me.id, target=prize.id, count=40)) is None
    w.run(2.0)
    assert prize.side == me.side and prize.alive
    assert old_captain not in w.controllers                          # her old captain let go of her
    assert b.captains[prize.id] in w.controllers and b.captains[prize.id].side == me.side
    assert not w.outcome.over                                        # the other Klingon is still out there
    assert b.transfer_command(prize.id) is None                      # 'beam <her>': you take command
    assert b.player_ship_id == prize.id
