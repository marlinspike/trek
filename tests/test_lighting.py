"""Weapon light on hulls, shadows under cards, and the smooth shapes of beams and torpedoes."""

from __future__ import annotations

from types import SimpleNamespace

import pygame
import pytest

from begin.ui import blast, gfx, theme
from begin.ui.effects import Light
from begin.ui.tactical import HULL_LIGHT_MAX, TacticalView


@pytest.fixture(autouse=True)
def _lighting() -> object:
    gfx.set_lighting(True)
    yield
    gfx.set_lighting(True)


def _light_at(lights: list[Light], x: float, y: float, size: float = 20) -> tuple[theme.Color, float] | None:
    return TacticalView._light_on(SimpleNamespace(_lights=lights), x, y, size)  # type: ignore[arg-type]


def test_light_falls_off_with_distance_and_is_capped() -> None:
    red = Light(100, 100, 80, (255, 60, 40), 0.9)
    near, far = _light_at([red], 110, 100), _light_at([red], 170, 100)
    assert near is not None and far is not None
    assert near[1] > far[1] and near[0] == (255, 60, 40)
    assert _light_at([red], 300, 100) is None                     # out of reach: unlit
    many = _light_at([red] * 10, 100, 100)
    assert many is not None and many[1] == HULL_LIGHT_MAX         # never washed out


def test_lit_art_adds_light_only_where_the_art_is() -> None:
    pygame.init()
    surf = pygame.Surface((40, 40))
    surf.fill((10, 10, 10))
    art = pygame.Surface((10, 10), pygame.SRCALPHA)
    art.fill((0, 0, 0, 0))
    pygame.draw.rect(art, (100, 100, 100, 255), (2, 2, 6, 6))
    rect = art.get_rect(topleft=(5, 5))
    TacticalView._light_art(surf, (art, rect), ((255, 200, 120), 0.8))
    assert surf.get_at((10, 10))[0] > 10                          # on the hull: brighter
    assert surf.get_at((5, 5))[:3] == (10, 10, 10)                # off it: untouched
    assert surf.get_at((30, 30))[:3] == (10, 10, 10)


def test_shadow_follows_the_lighting_switch() -> None:
    pygame.init()
    surf = pygame.Surface((120, 120))
    surf.fill((80, 80, 80))
    card = pygame.Rect(30, 30, 60, 40)
    gfx.set_lighting(False)
    theme.shadow(surf, card)
    assert surf.get_at((60, card.bottom + 3))[:3] == (80, 80, 80)
    gfx.set_lighting(True)
    theme.shadow(surf, card)
    assert surf.get_at((60, card.bottom + 3))[0] < 80             # a soft shadow just below the card
    assert surf.get_at((5, 5))[:3] == (80, 80, 80)                # and nothing far away


def test_small_halos_are_round() -> None:
    pygame.init()
    h = blast.halo(6, (255, 255, 255))
    w = h.get_width()
    c = w // 2
    across = h.get_at((c + 4, c))[0]
    diagonal = h.get_at((c + round(4 / 2 ** 0.5), c + round(4 / 2 ** 0.5)))[0]
    assert abs(across - diagonal) <= 24                           # same distance, about the same light
    assert h.get_at((c, c))[0] > across > h.get_at((0, 0))[0]
