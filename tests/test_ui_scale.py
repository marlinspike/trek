"""The interface size: larger on a big window that isn't Retina, chosen in Settings › Display (2026-11-14)."""

from __future__ import annotations

import pygame
import pytest

from begin.ui import gfx, present, zoom


def test_auto_grows_only_past_a_thousand_points_and_never_on_retina() -> None:
    assert zoom.auto(640) == zoom.auto(900) == zoom.auto(1000) == 1.0
    assert zoom.auto(1440) == 1.35
    assert 1.0 < zoom.auto(1200) < 1.35
    assert zoom.auto(2160) == 1.5                       # a 4K window unscaled: the largest
    assert zoom.auto(1440, density=2.0) == 1.0          # Retina already lays out in points
    assert zoom.chosen(1.3, 700) == 1.3 and zoom.chosen(0.0, 1440) == 1.35 and zoom.chosen("x", 900) == 1.0
    assert zoom.chosen(9, 900) == 1.5
    w, h = zoom.logical((2560, 1440), 1.35)
    assert (w, h) == (1896, 1067) and h >= 640          # every layout is checked down to 1024x640


def test_the_frame_is_laid_out_smaller_and_the_pointer_follows(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    p = present.open_presenter("auto", (2560, 1440), None)
    try:
        assert p.zoom == 1.35 and p.screen.get_size() == (1896, 1067) and gfx.ZOOM == 1.35
        ev = zoom.to_logical(pygame.event.Event(pygame.MOUSEBUTTONDOWN, pos=(1350, 675), button=1), p.zoom)
        assert ev.pos == (1000, 500) and ev.button == 1
        p.set_ui_scale(1.0)
        resized = [e for e in p.events() if e.type == pygame.VIDEORESIZE]
        assert resized and resized[0].size == (2560, 1440) and resized[0].window == (2560, 1440)
        assert p.screen.get_size() == (2560, 1440) and gfx.ZOOM == 1.0
        p.present()
    finally:
        gfx.set_zoom(1.0)
    small = present.open_presenter("auto", (1280, 800), None)
    assert small.zoom == 1.0 and small.screen.get_size() == (1280, 800)


def test_the_display_page_sets_the_size_and_the_window_keeps_its_own(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from begin.settings import Settings
    from begin.ui.app import App

    app = App(size=(2560, 1440), headless=True)
    try:
        assert app.screen.get_size() == (1896, 1067)
        app.menu.open_settings("display")
        app.frame(0.016)
        button = next(h for h in app.menu.ui.hotspots if h.tooltip.startswith("Larger, for a big monitor"))
        button.action()
        app.frame(0.016)
        assert app.settings.ui_scale == 1.3 and Settings.load().ui_scale == 1.3
        assert app.screen.get_size() == (1969, 1108)
        assert app.settings.window == (2560, 1440)            # the window, not the canvas, is remembered
    finally:
        gfx.set_zoom(1.0)
