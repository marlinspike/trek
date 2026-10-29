from __future__ import annotations

import pytest

from begin.content import default_content
from begin.content.schema import ContentDB
from begin.sim.world import World


@pytest.fixture(autouse=True)
def _private_config(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep tests away from the project's own config/ folder."""
    monkeypatch.setenv("BEGIN_HOME", str(tmp_path_factory.mktemp("config")))


@pytest.fixture(scope="session")
def content() -> ContentDB:
    return default_content()


def make_world(content: ContentDB, seed: int = 1, **kw: object) -> World:
    return World(content, seed=seed, **kw)  # type: ignore[arg-type]


def charge_all(world: World, cycles: float = 8.0) -> None:
    """Let every ship charge banks and load tubes without moving."""
    world.run(cycles)
