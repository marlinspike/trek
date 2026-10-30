"""The showpiece Enterprise: baked sprites load, and menu flybys move, fire and draw."""

from __future__ import annotations

import math

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


def test_each_pass_is_a_straight_line_at_one_heading() -> None:
    surf = _display()
    f = Flybys(seed=8)
    seen = 0
    while seen < 3:
        f.update(0.05, surf.get_size())
        p = f.current
        if p is None or p.t > 0.05:
            continue
        seen += 1
        pts = [p.at(u / 20) for u in range(21)]
        assert len({h for _, _, h in pts}) == 1                    # one heading, one sprite, all pass long
        (x0, y0, _), (x1, y1, _) = pts[0], pts[-1]
        for x, y, _ in pts:                                         # every point on the line from start to end
            assert abs((x1 - x0) * (y - y0) - (y1 - y0) * (x - x0)) < 1e-6 * max(1.0, abs(x1 - x0) + abs(y1 - y0)) ** 2
        speed = math.hypot(x1 - x0, y1 - y0) / p.duration
        assert speed < 140                                          # a slow glide, in pixels a second


def test_torpedo_salvos_come_often_and_stay_in_view() -> None:
    surf = _display()
    w, h = surf.get_size()
    f = Flybys(seed=21)
    passes, salvos, seen = 0, 0, 0.0
    last = None
    while passes < 8:
        f.update(0.05, (w, h))
        if f.current is not None and f.current is not last:
            last = f.current
            passes += 1
            salvos += any(kind == "torpedo" for _, kind, _ in f.current.fires)
        if any(s.kind == "torpedo" and s.trail and 0 <= s.pos[0] <= w and 0 <= s.pos[1] <= h for s in f.shots):
            seen += 0.05
    assert salvos >= 3                                  # firing passes take turns to lead with torpedoes
    assert seen >= 2.0                                  # and the torpedoes are on screen long enough to see


def test_symbols_fall_back_from_the_display_font() -> None:
    from begin.ui import theme

    _display()
    assert theme.render("QUICK BATTLE", theme.TEXT, 16, "display").get_width() > 0
    pause = theme.render("❚❚ Pause", theme.TEXT, 12, "display")
    assert pause.get_width() == theme.render("❚❚ Pause", theme.TEXT, 12, "ui").get_width()
