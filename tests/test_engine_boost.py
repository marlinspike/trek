"""The engine boost: Geordi puts a team on the drives so they run hot for longer, and the other repairs slow."""

from __future__ import annotations

import pygame
import pytest

from begin.battle import build_battle
from begin.console.parser import ParseContext, parse
from begin.crew.intents import BOOST, BOOST_OFF
from begin.crew.proposals import candidates
from begin.presets import load_presets
from begin.sim.commands import EngineBoost, SetHelm
from begin.sim.events import EngineBoostEnded, Message
from begin.sim.ship import Kind
from begin.sim.world import World


def _flat_out(content, boost: bool) -> float:  # type: ignore[no-untyped-def]
    """Cycles at full warp until the first drive burns out."""
    w = World(content, seed=2)
    me = w.add_ship("federation.dn", 0, 0, 0)
    w.execute(SetHelm(ship_id=me.id, warp=99))
    if boost:
        assert w.execute(EngineBoost(ship_id=me.id)) is None
    t = 0.0
    while all(not d.destroyed for d in me.drives) and t < 100:
        w.run(0.1)
        t += 0.1
    return t


def test_the_boost_buys_forty_percent_more_running_before_the_drives_overheat(content) -> None:  # type: ignore[no-untyped-def]
    plain, boosted = _flat_out(content, False), _flat_out(content, True)
    assert boosted / plain == pytest.approx(1.4, rel=0.03)


def test_other_repairs_slow_while_the_team_is_on_the_engines_but_the_drives_do_not(content) -> None:  # type: ignore[no-untyped-def]
    def damaged(boost: bool):  # type: ignore[no-untyped-def]
        w = World(content, seed=3)
        me = w.add_ship("federation.dn", 0, 0, 0)
        me.structure = me.structure_max * 0.4
        for sub in me.subsystems():
            if sub.kind in (Kind.DRIVE, Kind.SHIELD):
                sub.damage = 80
        if boost:
            w.execute(EngineBoost(ship_id=me.id))
        w.run(20)
        drive = sum(80 - s.damage for s in me.subsystems() if s.kind == Kind.DRIVE)
        shield = sum(80 - s.damage for s in me.subsystems() if s.kind == Kind.SHIELD)
        return drive, shield, me.structure / me.structure_max - 0.4

    d0, s0, h0 = damaged(False)
    d1, s1, h1 = damaged(True)
    assert d1 == pytest.approx(d0, rel=0.35)              # the drives' own repairs carry on
    assert s1 < s0 * 0.75 and h1 == pytest.approx(h0 * 0.5, rel=0.05)


def test_the_boost_runs_its_time_then_the_team_goes_back_and_says_so(content) -> None:  # type: ignore[no-untyped-def]
    w = World(content, seed=2)
    me = w.add_ship("federation.dn", 0, 0, 0)
    w.add_ship("klingon.dr", 1, 0, 60000)
    assert w.execute(EngineBoost(ship_id=me.id)) is None
    assert "already on the engines" in (w.execute(EngineBoost(ship_id=me.id)) or "")
    seen: list = []
    for _ in range(int(w.rules.boost_cycles * w.rules.ticks_per_cycle) + 5):
        w.step()
        seen += w.step_events
    assert me.engine_boost == 0.0
    assert [e for e in seen if isinstance(e, EngineBoostEnded) and not e.lost]
    assert any(isinstance(e, Message) and "back on repairs" in e.text for e in seen)
    assert "already on repairs" in (w.execute(EngineBoost(ship_id=me.id, on=False)) or "")
    w.execute(EngineBoost(ship_id=me.id))
    assert w.execute(EngineBoost(ship_id=me.id, on=False)) is None and me.engine_boost == 0.0


def test_the_console_and_plain_words(content) -> None:  # type: ignore[no-untyped-def]
    w = World(content, seed=2)
    me = w.add_ship("federation.dn", 0, 0, 0)

    def cmd(text: str):  # type: ignore[no-untyped-def]
        res = parse(text, ParseContext(me.id, w.observe(0)))
        assert res.error is None, res.error
        (c,) = res.commands
        assert isinstance(c, EngineBoost)
        return c.on

    assert cmd("boost") and cmd("boost engines") and cmd("give me all she's got") and cmd("overdrive")
    assert not cmd("boost off")
    for said in ("give me all she's got", "give me all she’s got", "everything you've got", "boost the engines",
                 "eke 40% more out of the engines", "squeeze a little more out of the warp drive",
                 "put a team on the engines", "keep the engines from overheating", "run the engines hard"):
        assert BOOST.search(said), said
    for said in ("target their engines", "disable their engines", "all stop", "fire all phasers", "warp 9"):
        assert not BOOST.search(said), said
    for said in ("end the boost", "back to repairs", "send the team back to repairs", "boost off", "cancel the boost"):
        assert BOOST_OFF.search(said), said


@pytest.fixture()
def scene(content):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme
    from begin.ui.battle_scene import BattleScene

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    sc = BattleScene(b, surf.get_size(), lambda: None, hidden={}, llm={})
    yield sc, surf
    sc.close()


def test_geordi_takes_the_order_and_the_hud_shows_it(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    me = sc.player
    sc.paused = False
    sc.overlay = None
    list(me.subsystems())[3].damage = 40
    sc.run_console("worf, give me all she's got")         # said to anyone: engineering answers
    assert me.engine_boost > 0
    assert any(ln.text.startswith("La Forge:") and "repairs" in ln.text for ln in sc.log)
    for _ in range(10):
        sc.update(0.05)
    sc.draw(surf)                                         # the drives row and the slowed repairs draw
    sc.run_console("geordi, back to repairs")
    assert me.engine_boost == 0
    assert any(ln.text.startswith("La Forge:") and "repairs" in ln.text for ln in sc.log[-3:])
    sc.draw(surf)


def test_geordi_offers_the_boost_when_the_drives_run_hot(scene) -> None:  # type: ignore[no-untyped-def]
    sc, _ = scene
    me = sc.player
    obs = sc.obs
    officers = {o.station: o for o in sc.session.bridge.officers()}
    for d in me.drives:
        d.temp, d.temp_rate = obs.rules.temp_limit * 0.8, 1.0
    assert any(p.line == "boost" for p in candidates(obs, me, officers))
    me.engine_boost = 10.0
    assert not any(p.line == "boost" for p in candidates(obs, me, officers))
