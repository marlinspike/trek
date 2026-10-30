"""The battle map's big effects: a ship destroyed blows apart where she died, and hits flare on shields and hulls."""

from __future__ import annotations

import tempfile

import pygame

from begin.battle import build_battle
from begin.content import default_content
from begin.presets import load_presets


def test_a_ship_destroyed_in_view_blows_apart_where_she_was(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setenv("BEGIN_HOME", tempfile.mkdtemp())
    from begin.ui.battle_scene import BattleScene

    pygame.init()
    surf = pygame.display.set_mode((1600, 900))
    presets = {p.id: p for p in load_presets()}
    sc = BattleScene(build_battle(default_content(), presets["border-incident"].setup()), (1600, 900), lambda: None,
                     hidden={}, llm={})
    sc.overlay = None
    sc.paused = False
    me = sc.player
    enemy = next(s for s in sc.world.ships.values() if s.id != me.id)
    for _ in range(40):
        sc.update(0.05)
        sc.overlay = None
    enemy.x, enemy.y = me.x + 500, me.y - 250
    for _ in range(10):
        sc.update(0.05)
        sc.overlay = None
        sc.draw(surf)
    x, y = enemy.x, enemy.y
    sc.world.destroy_ship(enemy, "test", me.id)
    for _ in range(4):
        sc.update(0.05)
        sc.overlay = None
        sc.draw(surf)
    wrecks = sc.view.wrecks
    assert len(wrecks) == 1 and (wrecks[0].x, wrecks[0].y) == (x, y)   # where she really was
    assert wrecks[0].blast.chunks                                     # her hull, torn into pieces
    for _ in range(100):
        sc.update(0.05)
        sc.overlay = None
    assert not sc.view.wrecks                                         # and then it is over
