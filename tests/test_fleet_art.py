"""Every ship class has baked, lit art, and the screens use it."""

from __future__ import annotations

import pygame

from begin.content.loader import default_content
from begin.ui import tactical
from begin.ui.fleet_art import BAKED, FLEET_DIR, HAND_BUILT, art_px, fleet_image, has_art, sprite_name
from begin.ui.tour_art import ship_art


def test_every_class_has_twelve_headings() -> None:
    for cid, cls in default_content().classes.items():
        if cid in HAND_BUILT:
            continue
        assert has_art(cid), cid
        for i in range(BAKED):
            assert (FLEET_DIR / sprite_name(cid, i * 30)).exists(), (cid, i)


def test_sprite_scale_matches_the_hull() -> None:
    pygame.init()
    cls = default_content().classes["klingon.bc"]
    img = fleet_image(cls.id, 0, 1.0)
    assert img is not None
    # the canvas is centred on the hull origin and spans the hull plus a margin
    assert img.get_width() == img.get_height()
    assert 100 * art_px(cls.hull.length) < img.get_width() < 130 * art_px(cls.hull.length)
    assert img.get_at((img.get_width() // 2, img.get_height() // 2)).a == 255     # solid hull at the origin


def test_tactical_and_tour_screens_draw_the_art() -> None:
    pygame.init()
    content = default_content()
    rom = content.classes["romulan.bp"]
    assert tactical._art(rom.id, rom.hull.length, 45.0, 2.0) is not None
    assert tactical._art("federation.hc", 270.0, 45.0, 2.0) is not None
    assert tactical._art("nobody.xx", 200.0, 0.0, 2.0) is None
    surf = pygame.Surface((400, 400), pygame.SRCALPHA)
    assert tactical.TacticalView._sprite(surf, rom, 200, 200, 30.0, 2.0)
    art = ship_art(content.classes["orion.ar"], 120, 30.0, hull=0.5, seed=3)
    assert art.get_width() > 120
