"""Officers flying for the captain and for each other, and showing what they are doing."""

from __future__ import annotations

import pygame
import pytest

from begin.battle import build_battle
from begin.crew.helm import incoming, plan_helm, threatened
from begin.crew.objectives import summary
from begin.presets import load_presets
from begin.sim.commands import (
    ConfigureAutoload,
    FireTorpedoes,
    SetHelm,
    SetObjective,
    TakeConn,
)
from begin.sim.world import World


def _duel(content):  # type: ignore[no-untyped-def]
    return build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())


def _incoming_salvo(content):  # type: ignore[no-untyped-def]
    w = World(content, seed=3)
    me = w.add_ship("federation.dn", 0, 0, 0)
    foe = w.add_ship("klingon.dr", 1, 8000, 6000, course=270)
    w.execute(SetHelm(ship_id=me.id, course=0, warp=4))
    w.execute(ConfigureAutoload(ship_id=foe.id, weapon="tube", prox=400, reload=True))
    w.run(4)
    assert w.execute(FireTorpedoes(ship_id=foe.id, target=me.id, count=4)) is None
    w.run(0.3)
    return w, me, foe


def _hurt(me) -> float:  # type: ignore[no-untyped-def]
    return me.structure_max - me.structure + sum(100.0 - s.strength for s in me.shields)


def test_the_helm_dodges_a_torpedo_aimed_at_where_we_would_be(content) -> None:  # type: ignore[no-untyped-def]
    held, me_h, _ = _incoming_salvo(content)
    held.run(5)
    assert _hurt(me_h) > 10      # holding course, the salvo hits

    w, me, foe = _incoming_salvo(content)
    obs = w.observe(me.side)
    threats = incoming(obs, me)
    assert threats and threatened(obs, me, threats) > 0
    plan = plan_helm(obs, me, obs.contact(foe.id), 6000.0, 9.0)
    assert plan is not None and plan.reason == "evade" and plan.dodged > 0
    assert plan.describe("Wraith").startswith("Evading 4 torpedoes")
    w.execute(SetHelm(ship_id=me.id, course=plan.course, warp=plan.warp))
    w.run(5)
    assert _hurt(me) < 1          # turning the moment it launched made it miss


def test_officers_report_what_they_are_doing(content) -> None:  # type: ignore[no-untyped-def]
    b = _duel(content)
    w, crew = b.world, b.crew
    me = w.ships[b.player_ship_id]
    foe = next(s for s in w.ships.values() if s.side != me.side)
    assert crew is not None and crew.activity(w.observe(me.side)) == []
    w.execute(TakeConn(ship_id=me.id, officer="spock"))
    w.execute(SetObjective(ship_id=me.id, group="shields", targets=(foe.id,), officer="seven"))
    kinds: dict[str, set[str]] = {"spock": set(), "seven": set()}
    progress = ""
    while w.time < 60 and not w.outcome.over:
        w.step()
        for a in crew.activity(w.observe(me.side)):
            kinds[a.officer_id].add(a.kind)
            if a.officer_id == "seven":
                assert a.role == f"Disable shields on {foe.name}"
                progress = a.progress or progress
            else:
                assert a.role == "conn" and a.plan is not None and a.doing
    assert kinds["spock"] & {"evade", "close", "open", "hold"}       # flying for Seven, not just weaving in
    assert kinds["seven"] & {"bait", "salvo"} and "load" in kinds["seven"]
    assert progress.startswith(foe.name) and ("shields out" in progress or progress.endswith("gone"))
    pl = crew.planners["seven"]
    assert pl.tally.get("rounds", 0) > 0 and "torpedoes in all" in summary(pl, w.tick, w.rules.ticks_per_cycle)


@pytest.fixture()
def scene(content):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme
    from begin.ui.battle_scene import BattleScene

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    sc = BattleScene(_duel(content), surf.get_size(), lambda: None, hidden={}, llm={})
    yield sc, surf
    sc.close()


def test_callouts_panel_and_summary(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    sc.run_console("spock, take the bridge")
    sc.run_console("seven, take out the wraith's shields")
    sc.paused = False
    sc.overlay = None
    while sc.world.time < 120 and not sc.world.outcome.over:
        sc.update(0.05)
        if int(sc.world.time * 20) % 200 == 0:
            sc.draw(surf)          # the panel and the map overlays draw without trouble
    said = [ln.text for ln in sc.log]
    assert any(t.startswith("Spock: Evading") or t.startswith("Spock: Closing on") for t in said)
    assert any(t.startswith("Seven of Nine: Salvo of") or t.startswith("Seven of Nine: One torpedo") for t in said)
    assert not any(t.startswith("Worf:") for t in said)          # Seven is the one firing, and she says so
    if not any(t.startswith("Wraith has been destroyed") for t in said):   # a heavy salvo can end it first
        assert any(t.startswith("Seven of Nine: That took") for t in said)


def test_without_an_objective_the_officer_flies_the_usual_way_but_still_dodges(content) -> None:  # type: ignore[no-untyped-def]
    b = _duel(content)
    w, crew = b.world, b.crew
    me = w.ships[b.player_ship_id]
    w.execute(TakeConn(ship_id=me.id, officer="spock"))
    seen = set()
    while w.time < 90 and not w.outcome.over:
        w.step()
        for a in crew.activity(w.observe(me.side)):
            seen.add(a.kind)
    assert seen <= {"approach", "fight", "evade", "hold"} and "approach" in seen
