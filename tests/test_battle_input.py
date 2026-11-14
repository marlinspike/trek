"""The battle screen's keys and mouse (ui/battle/input.py), driven with real pygame events on a headless screen."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from begin.battle import build_battle  # noqa: E402
from begin.presets import load_presets  # noqa: E402
from begin.sim.ship import PDDoctrine  # noqa: E402
from begin.ui.battle.common import SPEEDS  # noqa: E402
from begin.ui.battle_scene import BattleScene  # noqa: E402


@pytest.fixture()
def sc(content):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    exits: list[int] = []
    scene = BattleScene(build_battle(content, load_presets()[0].setup()), surf.get_size(), lambda: exits.append(1))
    scene.exits = exits                    # type: ignore[attr-defined]
    scene.overlay = None
    scene.draw(surf)                       # lays out the clickable parts
    return scene


def _key(sc, key: int, mod: int = 0) -> None:  # type: ignore[no-untyped-def]
    sc.handle(pygame.event.Event(pygame.KEYDOWN, key=key, mod=mod, unicode=""))


def _type(sc, text: str) -> None:  # type: ignore[no-untyped-def]
    sc.handle(pygame.event.Event(pygame.TEXTINPUT, text=text))


def _settle(sc) -> None:  # type: ignore[no-untyped-def]
    """Let the session carry the orders out (one tick, paused clock or not)."""
    sc.session.world.step()
    sc.session.obs = sc.session.observe()


def test_helm_keys_turn_and_change_warp(sc) -> None:  # type: ignore[no-untyped-def]
    p = sc.player
    course, warp = p.desired_course, p.desired_warp
    _key(sc, pygame.K_d)
    assert p.desired_course == (course + 15) % 360
    _key(sc, pygame.K_a, pygame.KMOD_SHIFT)
    assert p.desired_course == (course + 10) % 360
    _key(sc, pygame.K_w)
    assert p.desired_warp == min(p.cls.max_warp, int(warp) + 1)
    _key(sc, pygame.K_s)
    _key(sc, pygame.K_s)
    assert p.desired_warp <= warp


def test_scene_keys_pause_speed_zoom_and_pan(sc) -> None:  # type: ignore[no-untyped-def]
    was = sc.paused
    _key(sc, pygame.K_SPACE)
    assert sc.paused is not was
    sc.speed = SPEEDS[1]
    _key(sc, pygame.K_PERIOD)
    assert sc.speed == SPEEDS[2]
    _key(sc, pygame.K_COMMA)
    _key(sc, pygame.K_COMMA)
    assert sc.speed == SPEEDS[0]
    z = sc.cam.zoom
    _key(sc, pygame.K_EQUALS)
    assert sc.cam.zoom > z
    _key(sc, pygame.K_MINUS)
    assert sc.cam.zoom == pytest.approx(z, rel=0.05)
    cx = sc.cam.cx
    sc.cam.follow = None
    _key(sc, pygame.K_LEFT)
    assert sc.cam.cx != cx
    _key(sc, pygame.K_c)
    assert sc.cam.follow == sc.player_id
    arcs = sc.view.show_arcs
    _key(sc, pygame.K_q)
    assert sc.view.show_arcs is not arcs
    _key(sc, pygame.K_F9)
    assert sc.omniscient
    _key(sc, pygame.K_m)
    assert sc.toast is not None and "Sound" in sc.toast[0]
    _key(sc, pygame.K_i)
    assert sc.overlay == "damage"


def test_targeting_keys_cycle_contacts_aim_and_scan(sc) -> None:  # type: ignore[no-untyped-def]
    p = sc.player
    sc.omniscient = True
    _key(sc, pygame.K_TAB)
    _settle(sc)
    first = p.target
    assert first is not None
    _key(sc, pygame.K_TAB, pygame.KMOD_SHIFT)
    _settle(sc)
    assert p.target is not None
    aim = p.target_subsystem
    _key(sc, pygame.K_r)
    _settle(sc)
    assert p.target_subsystem != aim
    _key(sc, pygame.K_x)                     # a scan of the target is under way (or refused politely)
    pd = p.pd_doctrine
    _key(sc, pygame.K_v)
    _settle(sc)
    assert p.pd_doctrine != pd and isinstance(p.pd_doctrine, PDDoctrine)
    assert sc.toast is not None and sc.toast[0].startswith("Point defense")
    up = any(sh.up for sh in p.shields)
    _key(sc, pygame.K_g)
    _settle(sc)
    assert any(sh.up for sh in p.shields) is not up


def test_no_contacts_says_so(sc, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    monkeypatch.setattr(type(sc.obs), "contacts", lambda self: {})     # what a blind sensor sweep shows
    sc._cycle_target(1)
    assert sc.toast is not None and sc.toast[0] == "No contacts on sensors."


def test_the_console_takes_typing_history_and_escape(sc) -> None:  # type: ignore[no-untyped-def]
    _key(sc, pygame.K_RETURN)
    assert sc.console_focus
    _type(sc, "helm 45")
    _key(sc, pygame.K_BACKSPACE)
    _type(sc, "5 warp 3")
    assert sc.console == "helm 45 warp 3"
    _key(sc, pygame.K_RETURN)
    assert sc.console == "" and sc.history[-1] == "helm 45 warp 3"
    assert sc.player.desired_course == 45 and sc.player.desired_warp == 3
    _key(sc, pygame.K_UP)
    assert sc.console == "helm 45 warp 3"
    _key(sc, pygame.K_DOWN)
    assert sc.console == ""
    _key(sc, pygame.K_RETURN)                # an empty line closes the console
    assert not sc.console_focus
    _key(sc, pygame.K_SLASH)
    _key(sc, pygame.K_ESCAPE)
    assert not sc.console_focus


def test_escape_closes_things_in_order_then_opens_the_menu(sc) -> None:  # type: ignore[no-untyped-def]
    sc.counsel_open = True
    _key(sc, pygame.K_ESCAPE)
    assert not sc.counsel_open
    sc.printout = ["a chart"]
    _key(sc, pygame.K_ESCAPE)
    assert sc.printout is None and not sc.chart_auto
    _key(sc, pygame.K_ESCAPE)
    assert sc.overlay == "menu"
    _key(sc, pygame.K_ESCAPE)
    assert sc.overlay is None
    sc.overlay = "debrief"
    _key(sc, pygame.K_a)                     # keys do nothing over the debrief...
    _key(sc, pygame.K_RETURN)                # ... but Enter leaves
    assert sc.exits == [1]
    _key(sc, pygame.K_ESCAPE)
    assert sc.exits == [1, 1]


def test_help_overlays_close_on_any_key(sc) -> None:  # type: ignore[no-untyped-def]
    sc.overlay = "help_brief"
    _key(sc, pygame.K_q)
    assert sc.overlay is None


def test_function_keys_and_ctrl_letters_run_the_captains_bindings(sc) -> None:  # type: ignore[no-untyped-def]
    sc._key_binding(None)                    # none yet: says how
    assert any("No keys defined" in ln.text for ln in sc.log)
    sc._key_binding(("F5", "helm 200"))
    sc._key_binding(("^b", "helm 210"))
    sc._key_binding(None)
    _key(sc, pygame.K_F5)
    assert sc.player.desired_course == 200
    _key(sc, pygame.K_b, pygame.KMOD_CTRL)
    assert sc.player.desired_course == 210
    sc._key_binding(("F5", ""))
    assert "F5" not in sc.keys and not sc.run_key("F5")


def test_the_manual_takes_keys_text_and_the_wheel(sc) -> None:  # type: ignore[no-untyped-def]
    _key(sc, pygame.K_h)
    assert sc.overlay == "manual"
    _type(sc, "torp")
    _key(sc, pygame.K_BACKSPACE)
    sc.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=-1))
    assert sc.overlay == "manual"            # the manual had every one of them
    sc._escape()
    assert sc.overlay is None


def test_dragging_pans_and_the_wheel_zooms_the_map(sc) -> None:  # type: ignore[no-untyped-def]
    c = sc.map_rect.center
    sc.cam.follow = None
    x0 = sc.cam.cx
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=c))
    sc.handle(pygame.event.Event(pygame.MOUSEMOTION, pos=(c[0] + 60, c[1]), rel=(60, 0), buttons=(1, 0, 0)))
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, button=1, pos=(c[0] + 60, c[1])))
    assert sc.cam.cx != x0 and sc.drag is None
    sc.ui.mouse = c
    z = sc.cam.zoom
    sc.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1))
    assert sc.cam.zoom > z
    sc.ui.mouse = sc.bottom_rect.center
    sc.log_scroll = 0
    for i in range(10):
        sc._log(f"line {i}")
    sc.handle(pygame.event.Event(pygame.MOUSEWHEEL, x=0, y=1))
    assert sc.log_scroll == 3


def test_a_middle_drag_and_a_click_on_the_console(sc) -> None:  # type: ignore[no-untyped-def]
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=2, pos=sc.map_rect.center))
    assert sc.dragged
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONUP, button=2, pos=sc.map_rect.center))
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=sc.console_rect.center))
    assert sc.console_focus
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(sc.map_rect.right + 2, sc.map_rect.bottom + 2)))
    assert not sc.console_focus


def test_a_right_click_on_empty_space_steers_there(sc) -> None:  # type: ignore[no-untyped-def]
    p = sc.player
    sx, sy = sc.cam.to_screen(p.x, p.y)
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(int(sx) + 120, int(sy))))
    assert p.desired_course == 90
    assert p.desired_warp > 0


def test_clicks_on_ships_target_enemies_and_select_allies(sc) -> None:  # type: ignore[no-untyped-def]
    p = sc.player
    sc.omniscient = True
    enemy = next(iter(sc.obs.contacts()))
    sc.view.pick = lambda obs, now, x, y: enemy          # whatever is under the mouse
    sc._left_click((10, 10))
    _settle(sc)
    assert p.target == enemy
    ally = next((s for s in sc.session.world.ships.values() if s.side == p.side and s.id != p.id), None)
    if ally is not None:
        sc.view.pick = lambda obs, now, x, y: ally.id
        sc._left_click((10, 10))
        assert sc.selected_ally == ally.id


def test_shift_right_click_on_a_ship_pursues_it(sc, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    p = sc.player
    enemy = next(s for s in sc.session.world.ships.values() if s.side != p.side)
    sc.view.pick = lambda obs, now, x, y: enemy.id
    monkeypatch.setattr(pygame.key, "get_mods", lambda: pygame.KMOD_SHIFT)
    sc._right_click((10, 10))
    assert p.helm_target == enemy.id


def test_resizing_lays_the_screen_out_again(sc) -> None:  # type: ignore[no-untyped-def]
    sc.handle(pygame.event.Event(pygame.VIDEORESIZE, w=1024, h=700, size=(1024, 700)))
    assert sc.size == (1024, 700) and sc.map_rect.right <= 1024


def test_y_and_n_answer_an_officers_proposal(sc, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    said: list[str] = []
    monkeypatch.setattr(sc.session, "accept_proposal", lambda: said.append("yes") or True)
    monkeypatch.setattr(sc.session, "belay_proposal", lambda: said.append("no") or True)
    _key(sc, pygame.K_y)
    _key(sc, pygame.K_n)
    sc.console_focus = True
    _key(sc, pygame.K_y, pygame.KMOD_CTRL)
    assert said == ["yes", "no", "yes"]


def test_with_the_counsel_open_number_keys_follow_a_plan(sc, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    picked: list[int] = []
    monkeypatch.setattr(sc, "follow_plan", lambda i: picked.append(i) or True)
    sc.counsel_open = True
    _key(sc, pygame.K_2)
    assert picked == [1]


def test_tab_completes_in_the_console(sc) -> None:  # type: ignore[no-untyped-def]
    sc.console_focus = True
    sc.console = "hel"
    _key(sc, pygame.K_TAB)
    _key(sc, pygame.K_TAB)                   # "hel" is help or helm: the second Tab picks one
    assert sc.console.strip() in ("help", "helm")


def test_clicks_over_the_debrief_go_to_its_buttons(sc) -> None:  # type: ignore[no-untyped-def]
    hits: list[int] = []
    sc.overlay = "menu"
    sc.ui.hit = lambda pos: type("H", (), {"action": lambda self=None: hits.append(1), "rect": None, "right": None})()
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5)))
    assert hits == [1]


def test_buttons_take_left_and_right_clicks(sc) -> None:  # type: ignore[no-untyped-def]
    hits: list[str] = []
    h = type("H", (), {})()
    h.action = lambda: hits.append("left")
    h.right = lambda: hits.append("right")
    h.rect = pygame.Rect(0, 0, 1, 1)
    sc.ui.hit = lambda pos: h
    sc.overlay = "help_brief"
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=1, pos=(5, 5)))
    assert sc.overlay is None
    sc.handle(pygame.event.Event(pygame.MOUSEBUTTONDOWN, button=3, pos=(5, 5)))
    assert hits == ["left", "right"]
