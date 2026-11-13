from __future__ import annotations

import sys

import pytest

from begin.content import default_content
from begin.content.schema import ContentDB
from begin.sim.world import World


@pytest.fixture(autouse=True)
def _private_config(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests away from the project's own config/ folder."""
    monkeypatch.setenv("BEGIN_HOME", str(tmp_path_factory.mktemp("config")))


@pytest.fixture(autouse=True)
def _fonts_of_a_live_pygame() -> None:
    """A test that runs the whole app ends with pygame.quit(), which leaves the font caches holding dead fonts;
    the next test on the same worker would draw with them ("Invalid font"). Start that test with empty caches."""
    theme = sys.modules.get("begin.ui.theme")
    if theme is not None:
        import pygame

        if not pygame.font.get_init():
            theme.font.cache_clear()
            theme._fallback.cache_clear()


@pytest.fixture(scope="session")
def content() -> ContentDB:
    return default_content()


def make_world(content: ContentDB, seed: int = 1, **kw: object) -> World:
    return World(content, seed=seed, **kw)  # type: ignore[arg-type]


def charge_all(world: World, cycles: float = 8.0) -> None:
    """Let every ship charge banks and load tubes without moving."""
    world.run(cycles)


def scenario_presets() -> list:  # type: ignore[type-arg]
    """The small fleets the scenario tests were written against (tests/scenarios.toml), not the tuned presets."""
    from pathlib import Path

    from begin.presets import load_presets

    return load_presets(Path(__file__).with_name("scenarios.toml"))
