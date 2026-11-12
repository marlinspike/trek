"""Choosing how frames reach the screen: the game always gets a window, whatever the machine has."""

from __future__ import annotations

import pygame
import pytest

from begin.ui import present


def test_headless_runs_use_software(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    p = present.open_presenter("auto", (320, 200), None)
    assert p.name == "software" and p.density == 1.0
    assert p.screen.get_size() == (320, 200)


def test_a_gpu_failure_falls_back_with_a_reason(monkeypatch: pytest.MonkeyPatch) -> None:
    pygame.init()
    monkeypatch.setenv("SDL_VIDEODRIVER", "x-not-dummy")    # so the GPU path is tried

    class Broken:
        def __init__(self, *a: object, **kw: object) -> None:
            raise RuntimeError("no OpenGL 3.3")

    import begin.ui.glpresent as glp
    monkeypatch.setattr(glp, "GLPresenter", Broken)
    monkeypatch.setattr(present, "SoftwarePresenter",
                        lambda size, icon, why="": type("S", (), {"name": "software", "why": why})())
    p = present.open_presenter("gpu", (320, 200), None)
    assert p.name == "software" and p.why == "no OpenGL 3.3"


def test_restart_keeps_how_the_game_was_started_but_not_a_one_off_renderer() -> None:
    cmd = present.relaunch_command(["x"], ["py", "-m", "begin", "--renderer", "software", "--size", "800x600"],
                                   "/usr/bin/python3", frozen=False)
    assert cmd == ["/usr/bin/python3", "-m", "begin", "--size", "800x600"]
    app = present.relaunch_command(["/Applications/Begin.app/Contents/MacOS/Begin", "--renderer=gpu"], [],
                                   "/Applications/Begin.app/Contents/MacOS/Begin", frozen=True)
    assert app == ["/Applications/Begin.app/Contents/MacOS/Begin"]


def test_the_display_page_switches_renderer_and_glow(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SDL_VIDEODRIVER", "dummy")
    from begin.settings import Settings
    from begin.ui.app import App

    app = App(size=(1280, 800), headless=True)
    app.menu.open_settings("display")
    app.frame(0.016)
    assert app.settings.renderer == "auto"
    button = next(h for h in app.menu.ui.hotspots if h.tooltip.startswith("Always OpenGL"))   # the graphics card
    button.action()
    assert app.settings.renderer == "gpu" and Settings.load().renderer == "gpu"
    app.frame(0.016)                                   # not what started: offers a restart
    assert any(h.tooltip.startswith("Close and reopen") for h in app.menu.ui.hotspots)
    app.set_bloom(False)
    assert Settings.load().bloom is False and app.presenter.bloom is False
    launched: list[list[str]] = []
    monkeypatch.setattr("subprocess.Popen", lambda cmd, **kw: launched.append(cmd))
    app.restart()
    app.run()
    assert launched and launched[0][0]
