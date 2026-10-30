"""Faint stars far beyond the battle, in layers that drift at different rates (parallax)."""

from __future__ import annotations

import random

import pygame

STAR_TILE = 512           # pixels: the starfield repeats at this size
STAR_LAYERS = ((0.004, 110, 0.4), (0.009, 50, 0.6), (0.016, 20, 0.85))   # (parallax px/unit, stars per tile, brightness)


class Starfield:
    def __init__(self, seed: int = 1701) -> None:
        self.seed = seed
        self._tiles: list[pygame.Surface] = []

    def _make(self) -> None:
        rng = random.Random(self.seed)
        for _, count, bright in STAR_LAYERS:
            tile = pygame.Surface((STAR_TILE, STAR_TILE))
            for _ in range(count):
                level = bright * rng.uniform(0.35, 1.0)
                tint = rng.choice(((200, 215, 255), (255, 240, 220), (230, 235, 255)))
                col = tuple(int(c * level * 0.8) for c in tint)
                x, y = rng.randrange(STAR_TILE), rng.randrange(STAR_TILE)
                tile.set_at((x, y), col)
                if level > 0.7:
                    dim = tuple(c // 3 for c in col)
                    for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                        tile.set_at(((x + dx) % STAR_TILE, (y + dy) % STAR_TILE), dim)
            tile.set_colorkey((0, 0, 0), pygame.RLEACCEL)   # mostly empty: blits skip the dark runs
            self._tiles.append(tile)

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, cx: float, cy: float) -> None:
        """The stars as seen from world point (cx, cy): each layer offset by its own parallax."""
        if not self._tiles:
            self._make()
        for (parallax, _, _), tile in zip(STAR_LAYERS, self._tiles):
            ox = int(-cx * parallax) % STAR_TILE
            oy = int(cy * parallax) % STAR_TILE
            y = rect.top - STAR_TILE + oy
            while y < rect.bottom:
                x = rect.left - STAR_TILE + ox
                while x < rect.right:
                    surf.blit(tile, (x, y))
                    x += STAR_TILE
                y += STAR_TILE


__all__ = ["STAR_LAYERS", "STAR_TILE", "Starfield"]
