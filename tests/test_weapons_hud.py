"""The weapons readout: every tube's load and mark, the torpedo line on every window size, and point defense.

Found 2026-11-14: since #23 the Weapons panel folded into a tab at the default 1600×900 window, so a captain
could no longer see which tubes were loaded or with what. These keep it from slipping away again.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from begin.sim.ship import LoadedTorpedo, PDDoctrine  # noqa: E402
from begin.ui import theme  # noqa: E402
from begin.ui.hud import TargetPanel, WeaponsPanel, torpedo_summary, tube_state  # noqa: E402

SIZES = [(1024, 640), (1280, 800), (1440, 860), (1600, 900), (1920, 1080)]


def _scene(content, size=(1600, 900), preset="dreadnought-duel"):  # type: ignore[no-untyped-def]
    from begin.battle import build_battle
    from begin.presets import load_presets
    from begin.ui.battle_scene import BattleScene

    pygame.init()
    presets = {p.id: p for p in load_presets()}
    return BattleScene(build_battle(content, presets[preset].setup()), size, lambda: None)


def test_each_tube_says_what_it_holds_or_is_arming(content) -> None:  # type: ignore[no-untyped-def]
    sc = _scene(content)
    ship = sc.player
    assert ship is not None and len(ship.tubes) >= 4
    for t in ship.tubes:
        t.loaded, t.charge, t.load_ordnance, t.autoload = None, 40.0, "mk7", True
    ship.tubes[0].loaded = LoadedTorpedo(ordnance="mk8", prox=200.0)
    assert tube_state(ship, 1) == ("arming", "MK7")
    ship.tubes[2].autoload = False
    ship.tubes[2].manual_load_pending = False
    assert tube_state(ship, 2) == ("empty", "MK7")
    ship.tubes[3].damage = 40
    assert tube_state(ship, 3)[0] == "damaged"
    loaded, n, marks = torpedo_summary(ship)
    assert n == len(ship.tubes)
    assert tube_state(ship, 0) == ("loaded", "MK8") and loaded == 1 and marks == "MK8/MK7"
    ship.torps_remaining = 0
    assert tube_state(ship, 1)[0] == "dry"


def test_weapons_stay_in_the_column_at_the_default_and_laptop_windows(content) -> None:  # type: ignore[no-untyped-def]
    for size in ((1600, 900), (1440, 860), (1920, 1080)):
        sc = _scene(content, size)
        shown = sc.column_panels(sc.col_rect.height)
        assert any(isinstance(p, WeaponsPanel) for p in shown), size
    sc = _scene(content, (1600, 900))
    assert any(isinstance(p, TargetPanel) for p in sc.column_panels(sc.col_rect.height))   # all four at the default


def test_the_torpedo_line_and_point_defense_are_on_screen_at_every_size(content) -> None:  # type: ignore[no-untyped-def]
    for size in SIZES:
        surf = pygame.display.set_mode(size)
        sc = _scene(content, size)
        sc.paused = False
        for _ in range(240):              # long enough for the tubes to load
            sc.update(1 / 30)
        sc.paused = True
        sc.overlay = None
        with theme.watching() as ink:
            sc.draw(surf)
        words = [k.text for k in ink if k.kind in ("text", "label")]
        screen = pygame.Rect(0, 0, *size)
        assert "Torpedoes" in words, size
        line = next(k for k in ink if "loaded" in k.text and "/" in k.text)
        assert screen.contains(line.rect) and "MK7" in line.text, (size, line.text)
        pd = [h for h in sc.ui.hotspots if "Point defense" in h.tooltip]
        assert pd and all(screen.contains(h.rect) for h in pd), size


def test_the_weapons_panel_shows_every_tubes_mark_and_a_point_defense_button(content) -> None:  # type: ignore[no-untyped-def]
    surf = pygame.display.set_mode((1600, 900))
    sc = _scene(content)
    sc.paused = False
    for _ in range(240):
        sc.update(1 / 30)
    sc.paused = True
    sc.overlay = None
    ship = sc.player
    assert ship is not None
    with theme.watching() as ink:
        sc.draw(surf)
    weapons = next(k.rect for k in ink if k.kind == "panel" and any(
        j.text.upper() == "WEAPONS" and k.rect.contains(j.rect) for j in ink if j.kind != "panel"))
    marks = [k for k in ink if k.text in ("MK7", "MK8") and weapons.contains(k.rect)]
    assert len(marks) == len(ship.tubes)
    tips = [h for h in sc.ui.hotspots if h.tooltip.startswith("Tube ")]
    assert len(tips) == len(ship.tubes) and all("loaded, MK7" in h.tooltip for h in tips)
    pd = [h for h in sc.ui.hotspots if "Point defense" in h.tooltip and weapons.contains(h.rect)]
    assert len(pd) == 1
    before = ship.pd_doctrine
    pd[0].action()
    sc.update(1 / 30)
    assert ship.pd_doctrine != before
    pd[0].right()                         # type: ignore[misc]
    sc.update(1 / 30)
    assert ship.pd_doctrine == PDDoctrine.OFF
    sc.draw(surf)
    pd = [h for h in sc.ui.hotspots if "Point defense" in h.tooltip and weapons.contains(h.rect)]
    pd[0].right()                         # type: ignore[misc]
    sc.update(1 / 30)
    assert ship.pd_doctrine == PDDoctrine.BALANCED
