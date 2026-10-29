"""The 2.0 extras on screen: the Fleet tab, tractor and boarding buttons, and their map markings (headless)."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from begin.battle import build_battle  # noqa: E402
from begin.presets import load_presets  # noqa: E402
from begin.ui.battle_scene import BattleScene  # noqa: E402
from begin.ui.hud import FleetPanel  # noqa: E402


@pytest.fixture()
def starbase(content):  # type: ignore[no-untyped-def]
    """Starbase Defense: the player's cruiser, a destroyer (Polaris) and a starbase (Tau)."""
    pygame.init()
    from begin.ui import theme

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1600, 900))
    preset = next(p for p in load_presets() if p.id == "starbase-defense")
    sc = BattleScene(build_battle(content, preset.setup()), surf.get_size(), lambda: None, hidden={}, llm={})
    sc.overlay = None
    return sc, surf


def _ally(sc: BattleScene, name: str):  # type: ignore[no-untyped-def]
    return next(a for a in sc.allies() if a.name.lower().startswith(name))


def _click(sc: BattleScene, surf: pygame.Surface, starts: str) -> None:
    """Draw a frame, then press the button whose tooltip starts with `starts`."""
    sc.draw(surf)
    hits = [h for h in sc.ui.hotspots if h.tooltip.startswith(starts)]
    assert hits, f"no button '{starts}'"
    hits[-1].action()


def test_clicking_an_ally_opens_the_fleet_tab(starbase) -> None:  # type: ignore[no-untyped-def]
    sc, surf = starbase
    polaris = _ally(sc, "polaris")
    sc.draw(surf)
    x, y = sc.cam.to_screen(polaris.x, polaris.y)
    sc.cam.follow = None
    sc._left_click((int(x), int(y)))
    assert sc.selected_ally == polaris.id
    assert isinstance(sc.side_tabs.tabs[sc.side_tabs.active], FleetPanel)
    sc.draw(surf)


def test_fleet_buttons_give_standing_orders(starbase) -> None:  # type: ignore[no-untyped-def]
    sc, surf = starbase
    p = sc.player
    polaris = _ally(sc, "polaris")
    sc.select_ally(polaris.id)
    _click(sc, surf, "Stay with the flagship")
    st = sc.obs.ally_order(polaris.id)
    assert st is not None and st.movement == "escort" and st.move_target == p.id
    _click(sc, surf, "Hold fire until")
    assert st.hold_fire
    _click(sc, surf, "Weapons free")
    assert not st.hold_fire
    _click(sc, surf, "Join group 2")
    assert st.group == 2
    _click(sc, surf, "Leave group 2")
    assert st.group is None
    _click(sc, surf, "Go and dock with Tau")
    assert st.movement == "dock" and st.move_target == _ally(sc, "tau").id
    _click(sc, surf, "Status report from")
    assert sc.printout and any("Polaris" in line for line in sc.printout)


def test_attack_my_target_needs_a_target(starbase) -> None:  # type: ignore[no-untyped-def]
    sc, surf = starbase
    p = sc.player
    polaris = _ally(sc, "polaris")
    sc.select_ally(polaris.id)
    sc.draw(surf)
    assert not any(h.tooltip.startswith("Close and attack") for h in sc.ui.hotspots)  # disabled
    enemy = next(iter(sc.obs.contacts()))
    sc.run_console(f"target #{enemy}")
    _click(sc, surf, "Close and attack")
    st = sc.obs.ally_order(polaris.id)
    assert st is not None and st.target == enemy == p.target


def test_console_me_means_the_flagship(starbase) -> None:  # type: ignore[no-untyped-def]
    sc, _ = starbase
    sc.run_console("tell polaris defend me")
    st = sc.obs.ally_order(_ally(sc, "polaris").id)
    assert st is not None and st.movement == "defend" and st.move_target == sc.player_id


def test_dock_with_the_selected_base(starbase) -> None:  # type: ignore[no-untyped-def]
    sc, surf = starbase
    p = sc.player
    tau = _ally(sc, "tau")
    p.x, p.y = tau.x + 500, tau.y
    sc.select_ally(tau.id)
    _click(sc, surf, "Dock with Tau")
    assert p.docked_to == tau.id
    sc.draw(surf)  # 'docked' label on the map
    _click(sc, surf, "Dock with Tau")
    assert p.docked_to is None


def test_take_command_from_the_fleet_tab(starbase) -> None:  # type: ignore[no-untyped-def]
    sc, surf = starbase
    polaris = _ally(sc, "polaris")
    sc.player.x, sc.player.y = polaris.x + 500, polaris.y
    sc.select_ally(polaris.id)
    _click(sc, surf, "Beam aboard Polaris")
    assert sc.player_id == polaris.id


def test_tractor_and_board_buttons(starbase) -> None:  # type: ignore[no-untyped-def]
    sc, surf = starbase
    p = sc.player
    w = sc.world
    enemy = min((s for s in w.ships.values() if s.side != p.side), key=lambda s: s.cls.mass)
    enemy.x, enemy.y = p.x, p.y + 800
    sc.obs = w.observe(sc.side)
    sc.run_console(f"target #{enemy.id}")
    _click(sc, surf, "Tractor beam:")
    assert p.tractor_target == enemy.id
    sc.draw(surf)  # the beam on the map
    _click(sc, surf, "Tractor beam:")
    assert p.tractor_target is None
    # boarding needs both facing shields down; the button reports the refusal as a toast
    _click(sc, surf, f"Beam {p.boarding_party()} crew across")
    assert sc.toast is not None and "shield" in sc.toast[0]
    for sh in (*enemy.shields, *p.shields):
        sh.up, sh.effective = False, 0.0
    crew = p.crew
    _click(sc, surf, f"Beam {p.boarding_party()} crew across")
    assert p.crew < crew


def test_boarders_and_missions_draw(starbase) -> None:  # type: ignore[no-untyped-def]
    sc, surf = starbase
    polaris = _ally(sc, "polaris")
    polaris.boarders, polaris.boarder_side = 12, 1
    sc.run_console("tell polaris escort me")
    sc.select_ally(polaris.id)
    sc.draw(surf)


def test_boarding_party_default(starbase) -> None:  # type: ignore[no-untyped-def]
    sc, _ = starbase
    p = sc.player
    n = p.boarding_party()
    assert 6 <= n <= max(6, p.cls.beam_cap * max(1, len(p.transporters)))
    p.crew = 10
    assert p.boarding_party() == 6


def test_target_panel_lists_every_contact_on_sensors(starbase) -> None:  # type: ignore[no-untyped-def]
    """With no target the Target box lists each visible contact; a click targets it, and the rest stay one click away."""
    sc, surf = starbase
    p = sc.player
    assert p is not None
    sc.world.run(1)
    sc.obs = sc.world.observe(sc.side)
    seen = [c for c in sc.obs.contacts().values() if c.visible]
    assert len(seen) >= 2 and p.target is None
    sc.draw(surf)
    rows = [h for h in sc.ui.hotspots if h.tooltip.startswith("Target ")]
    assert len(rows) >= min(len(seen), 5)   # as many as fit, nearest first; the rest are a Tab away
    names = {c.label for c in seen}
    assert all(h.tooltip.removeprefix("Target ") in names for h in rows)
    rows[0].action()
    sc.obs = sc.world.observe(sc.side)
    assert p.target is not None
    sc.draw(surf)
    switch = [h for h in sc.ui.hotspots if h.tooltip.startswith("Switch target to")]
    assert len(switch) >= 1
