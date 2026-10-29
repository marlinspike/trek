"""Headless UI checks (pygame dummy video driver)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from begin.battle import build_battle  # noqa: E402
from begin.presets import load_presets  # noqa: E402
from begin.ui.battle_scene import BattleScene  # noqa: E402


@pytest.fixture()
def scene(content):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme

    theme.font.cache_clear()  # fonts must belong to the live pygame session
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    b = build_battle(content, load_presets()[0].setup())
    sc = BattleScene(b, surf.get_size(), lambda: None)
    return sc, surf


def test_range_command_sets_display_range(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    sc.run_console("range 5000")
    assert abs(sc.display_range() - 5000) < 1
    sc.run_console("range 40000")
    assert abs(sc.display_range() - 40000) < 1
    sc.draw(surf)  # renders at the new scale


def test_console_orders_reach_the_ship(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    sc.run_console("helm 90 warp 4")
    assert sc.player is not None and sc.player.desired_course == 90 and sc.player.desired_warp == 4
    sc.paused = False
    for _ in range(30):
        sc.update(1 / 60)
    sc.draw(surf)
    assert sc.world.tick > 0


def test_text_never_raises_on_unrenderable_strings(scene):
    _, surf = scene
    from begin.ui import theme

    for s in ("", "Orders also work while paused.", "​", "▶ Run ❚❚"):
        r = theme.text(surf, s, (10, 10), theme.TEXT_FAINT, 11)
        assert r.height >= 0


def test_bundled_fonts_render():
    import pygame
    from begin.ui import theme

    pygame.font.init()
    theme.font.cache_clear()
    for (family, weight) in theme._FONT_FILES:
        assert (theme.FONT_DIR / theme._FONT_FILES[(family, weight)]).exists()
        assert theme.text_width("Orders also work while paused.", 11, family, weight) > 0


def test_console_displays_chart_keys_and_quit(scene):  # type: ignore[no-untyped-def]
    sc, surf = scene
    sc.run_console("status banks")
    assert sc.printout is not None and sc.printout[0] == "BANK STATUS:"
    sc.run_console("chart by distance")
    assert sc.printout is not None and "WARP COURSE" in sc.printout[0]
    sc.run_console("key F5 fire all phasers 10; status tubes")
    assert sc.keys["F5"] == "fire all phasers 10; status tubes"
    assert sc.run_key("F5")
    assert sc.printout is not None and sc.printout[0] == "TUBE STATUS:"
    sc.draw(surf)  # the printout renders
    sc.run_console("quit")
    assert sc.world.outcome.over and sc.overlay == "debrief"


def test_hit_report_sums_up_a_volley() -> None:
    from begin.sim.events import HullHit, ShieldHit, SubsystemDamaged
    from begin.ui.hit_report import HitReport

    r = HitReport(1)
    r.ingest([ShieldHit(10, 7, 0, 50.0, 0.0, False, 1, 87.0), ShieldHit(10, 7, 0, 50.0, 0.0, False, 1, 76.0),
              ShieldHit(10, 9, 0, 50.0, 0.0, False, 2, 50.0)], 10)
    assert r.due(12, 10, {7: "Wraith"}) == []
    assert r.due(20, 10, {7: "Wraith"}) == ["Hits on Wraith: 2, all absorbed (shield 1 now 76%)."]
    r.ingest([ShieldHit(30, 7, 1, 20.0, 30.0, True, 1, 0.0), HullHit(30, 7, 30.0, 0, 1),
              SubsystemDamaged(30, 7, "phaser2", "Phaser 2", 40, False, False)], 30)
    assert r.due(40, 10, {}) == ["Hits on #7: 1, shield 2 now 0%; shield 2 collapsed; 30 damage to the hull; Phaser 2 hit."]


def test_coach_warns_when_proximity_is_wider_than_the_blast(content) -> None:  # type: ignore[no-untyped-def]
    from begin.help.coach import HelpContext, tips
    from begin.sim.commands import ConfigureAutoload, SelectTarget
    from begin.sim.world import World

    w = World(content, seed=1)
    me = w.add_ship("federation.dn", 0, 0, 0)
    dr = w.add_ship("klingon.dr", 1, 0, 6000)
    w.execute(ConfigureAutoload(ship_id=me.id, weapon="tube", prox=500))
    w.execute(SelectTarget(ship_id=me.id, target=dr.id))
    w.step()
    t = next(t for t in tips(HelpContext(content, w.observe(0), me)) if t.title == "Proximity fuse")
    assert t.priority == 1 and "barely scratch" in t.text and t.commands == ["autoload tor prox 250"]
