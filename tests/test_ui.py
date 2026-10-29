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
