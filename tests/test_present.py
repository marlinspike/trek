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
                        lambda size, icon, note="": type("S", (), {"name": "software", "note": note})())
    p = present.open_presenter("gpu", (320, 200), None)
    assert p.name == "software" and "no OpenGL 3.3" in p.note
