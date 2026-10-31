"""Baked, lit sprites for every ship class but the heavy cruiser (which has its own, `showpiece.py`).

`tools/render_fleet.py` builds them from each class's hull in `hulls.toml`: one per 30° of
heading so the light stays put on screen while a ship turns, on a square canvas centred on the
hull origin, `art_px(length)` sprite pixels per hull unit. A class without baked art falls
back to its outline, as before.
"""

from __future__ import annotations

from functools import lru_cache

import pygame

from .showpiece import SHIP_DIR

FLEET_DIR = SHIP_DIR / "fleet"
BAKED = 12                          # sprites per class, one per 30° of heading
HAND_BUILT = frozenset({"federation.hc"})


def art_px(length: float) -> float:
    """Sprite pixels per hull unit for a class `length` world units long: about her size at full zoom."""
    return max(2.5, min(5.0, round(length * 1.25 / 100.0 * 2) / 2))


def sprite_name(cls_id: str, heading: int) -> str:
    return f"{cls_id.replace('.', '-')}-{heading:03d}.png"


@lru_cache(maxsize=None)
def _baked(cls_id: str, i: int) -> pygame.Surface | None:
    try:
        img = pygame.image.load(str(FLEET_DIR / sprite_name(cls_id, i * 360 // BAKED)))
        return img.convert_alpha() if pygame.display.get_surface() is not None else img
    except (FileNotFoundError, pygame.error, OSError):
        return None


@lru_cache(maxsize=None)
def has_art(cls_id: str) -> bool:
    return cls_id not in HAND_BUILT and (FLEET_DIR / sprite_name(cls_id, 0)).exists()


@lru_cache(maxsize=256)
def fleet_image(cls_id: str, heading: float, scale: float) -> pygame.Surface | None:
    """The class at a heading (degrees clockwise from up) and scale (1 = as baked), lit from the upper left
    whatever her heading. Its centre is the hull origin. None when the class has no baked art."""
    if not has_art(cls_id):
        return None
    img = _baked(cls_id, round(heading / (360.0 / BAKED)) % BAKED)
    if img is None:
        return None
    return pygame.transform.rotozoom(img, -heading, scale)
