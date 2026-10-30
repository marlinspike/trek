"""The showpiece Enterprise: baked sprites load, and menu flybys move, fire and draw."""

from __future__ import annotations

import pygame

from begin.ui import showpiece
from begin.ui.showpiece import BAKED, Flybys, ship_image, sprite


def _display() -> pygame.Surface:
    pygame.init()
    return pygame.display.set_mode((1280, 800))


def test_every_baked_heading_loads() -> None:
    _display()
    for i in range(BAKED):
        img = sprite(i)
        assert img is not None and img.get_width() > 100 and img.get_height() > img.get_width()
    turned = ship_image(47.0, 0.5)
    assert turned is not None and turned.get_bounding_rect().width > 0


def test_a_flyby_crosses_fires_and_draws() -> None:
    surf = _display()
    played: list[str] = []
    f = Flybys(seed=3, sound=lambda name, level, pan: played.append(name))
    kinds: set[str] = set()
    for _ in range(4000):
        f.update(0.05, surf.get_size())
        kinds |= {s.kind for s in f.shots}
        if f.shots:
            surf.fill((0, 0, 0))
            f.draw(surf)
        if kinds == {"phaser", "torpedo"}:
            break
    assert kinds == {"phaser", "torpedo"} and {"phaser", "launch"} <= set(played)
    assert surf.get_bounding_rect().width > 0


def test_flybys_fall_back_quietly_without_sprites(monkeypatch) -> None:  # type: ignore[no-untyped-def]
    surf = _display()
    showpiece.ship_image.cache_clear()
    monkeypatch.setattr(showpiece, "sprite", lambda i: None)
    try:
        f = Flybys(seed=5)
        for _ in range(400):
            f.update(0.05, surf.get_size())
            f.draw(surf)
    finally:
        showpiece.ship_image.cache_clear()
