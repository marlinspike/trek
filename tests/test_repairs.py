"""Hull repairs, the officer who directs the repair crews, and what the HUD shows of it."""

from __future__ import annotations

import pygame
import pytest

from begin.battle import build_battle
from begin.console.parser import ParseContext, parse
from begin.presets import load_presets
from begin.sim.commands import Authority, Dock, ManageRepairs, SetRepairPriority
from begin.sim.ship import HULL, Kind
from begin.sim.systems.repair import in_battle, under_repair
from begin.sim.world import World


def _holed(content, enemy_at: float | None = None):  # type: ignore[no-untyped-def]
    w = World(content, seed=2)
    me = w.add_ship("federation.dn", 0, 0, 0)
    if enemy_at is not None:
        w.add_ship("klingon.dr", 1, 0, enemy_at)
    me.structure = me.structure_max * 0.4
    return w, me


def _hull(me) -> float:  # type: ignore[no-untyped-def]
    return me.structure / me.structure_max


def test_the_hull_is_patched_slowly_in_battle_faster_out_of_it_and_only_fully_at_a_base(content) -> None:  # type: ignore[no-untyped-def]
    quiet, me = _holed(content)
    assert not in_battle(quiet, me) and under_repair(quiet, me)[1]
    quiet.run(20)
    gained = _hull(me) - 0.4
    assert 0.06 < gained < 0.10                          # 0.4% a cycle with a full crew

    hot, me2 = _holed(content, enemy_at=6000)
    assert in_battle(hot, me2)
    hot.run(20)
    assert 0 < _hull(me2) - 0.4 < gained * 0.4           # a quarter of the rate under fire

    quiet.run(200)
    assert _hull(me) == pytest.approx(0.75)              # crews in space stop at 75%
    assert not under_repair(quiet, me)[1]

    w = World(content, seed=2)
    base = w.add_ship("federation.sb", 0, 0, 0)
    me3 = w.add_ship("federation.dn", 0, 500, 0)
    me3.structure = me3.structure_max * 0.4
    assert w.execute(Dock(ship_id=me3.id, host=base.id)) is None
    w.run(40)
    assert _hull(me3) > 0.9                              # a base restores it, past the field limit


def test_hull_priority_and_handing_repairs_to_an_officer(content) -> None:  # type: ignore[no-untyped-def]
    w, me = _holed(content)
    def cmds(text: str):  # type: ignore[no-untyped-def]
        return parse(text, ParseContext(me.id, w.observe(0))).commands

    (c,) = cmds("repair hull")
    assert isinstance(c, SetRepairPriority) and c.kind == HULL
    a, _ = _holed(content)
    a.run(10)
    w.execute(c)
    w.run(10)
    assert _hull(me) > _hull(a.ships[me.id]) + 0.05     # four times the rate

    (c,) = cmds("repair auto spock")
    assert isinstance(c, ManageRepairs) and c.officer == "spock"
    assert cmds("repair manual")[0].officer == ""   # type: ignore[attr-defined]
    w.execute(c)
    assert me.repairs_by == "spock"
    w.execute(SetRepairPriority(ship_id=me.id, kind=Kind.SHIELD, issuer=Authority.CAPTAIN))
    assert me.repairs_by == ""                          # the captain's own priority takes them back


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


def test_spock_reports_damage_and_directs_the_crews_when_asked(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    me = sc.player
    sc.paused = False
    sc.overlay = None
    for sub in list(me.subsystems())[:3]:
        sub.damage = 60
    me.structure = me.structure_max * 0.55
    for _ in range(10):
        sc.update(0.05)
    said = [ln for ln in sc.log if ln.text.startswith("Spock: Captain,")]
    assert said and "need repairs" in said[-1].text and "hull at 55%" in said[-1].text
    sc.run_console("spock, manage repairs")
    assert me.repairs_by == "spock"
    for _ in range(40):
        sc.update(0.05)
    assert me.repair_priority is not None
    assert any(ln.text.startswith("Spock: Repair crews to") for ln in sc.log)
    sc.draw(surf)
    sc.overlay = "damage"
    sc.draw(surf)
    sc.run_console("spock, I'll handle repairs")
    assert me.repairs_by == ""
