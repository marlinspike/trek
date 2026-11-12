"""Faint stars far beyond the battle, in layers that drift at different rates (parallax)."""

from __future__ import annotations

import math
import random

import pygame

STAR_TILE = 512           # pixels: the starfield repeats at this size
STAR_LAYERS = ((0.004, 110, 0.4), (0.009, 50, 0.6), (0.016, 20, 0.85))   # (parallax px/unit, stars per tile, brightness)
NEBULA_TILE = 1024        # pixels: the faint gas behind the stars repeats at this size
NEBULA_PARALLAX = 0.002   # it is further off than any star: it hardly moves as the view pans
NEBULA_SEED = 1764
_NEBULAE: dict[tuple[int, int, int], pygame.Surface] = {}   # built once, shared
# (cells across the tile, tint at full density): broad clouds of two colours, and finer wisps through them
NEBULA_LAYERS = ((5, (11, 4, 19)), (7, (2, 12, 16)), (19, (5, 5, 10)))


def _soft_noise(rng: random.Random, cells: int, size: int) -> pygame.Surface:
    """Grey cloud that tiles seamlessly: a `cells` × `cells` random grid, smoothly interpolated with wrap-round
    at an eighth of the size, then blown up as a ring of copies and cut from the middle (a whole number of
    pixels per sample, so the cut edges line up exactly with the copies beside them)."""
    grid = [[rng.random() ** 2.2 for _ in range(cells)] for _ in range(cells)]   # mostly dark, the odd bright patch
    n = size // 8
    small = pygame.Surface((n, n))
    for y in range(n):
        fy = y * cells / n
        y0 = int(fy)
        ty = (1 - math.cos((fy - y0) * math.pi)) / 2
        row0, row1 = grid[y0 % cells], grid[(y0 + 1) % cells]
        for x in range(n):
            fx = x * cells / n
            x0 = int(fx)
            tx = (1 - math.cos((fx - x0) * math.pi)) / 2
            a = row0[x0 % cells] + (row0[(x0 + 1) % cells] - row0[x0 % cells]) * tx
            b = row1[x0 % cells] + (row1[(x0 + 1) % cells] - row1[x0 % cells]) * tx
            v = int(255 * (a + (b - a) * ty))
            small.set_at((x, y), (v, v, v))
    ring = pygame.Surface((n * 3, n * 3))
    for gy in range(3):
        for gx in range(3):
            ring.blit(small, (gx * n, gy * n))
    blur = getattr(pygame.transform, "gaussian_blur", None)    # pygame-ce 2.2+: rounds off the grid's corners
    if blur is not None:
        ring = blur(ring, max(2, n // cells // 2))
    big = pygame.transform.smoothscale(ring, (size * 3, size * 3))
    return big.subsurface((size, size, size, size)).copy()


class Starfield:
    def __init__(self, seed: int = 1701) -> None:
        self.seed = seed
        self._tiles: list[pygame.Surface] = []

    def nebula(self, base: tuple[int, int, int]) -> pygame.Surface:
        """The backdrop tile: the field's own colour with faint clouds of gas through it. Built once per
        colour, the first time it is drawn (under half a second), and shared by every starfield after."""
        tile = _NEBULAE.get(base)
        if tile is None:
            rng = random.Random(NEBULA_SEED)
            tile = pygame.Surface((NEBULA_TILE, NEBULA_TILE))
            tile.fill(base)
            for cells, tint in NEBULA_LAYERS:
                cloud = _soft_noise(rng, cells, NEBULA_TILE)
                cloud.fill(tint, special_flags=pygame.BLEND_MULT)   # 255 grey → the full tint, black → nothing
                tile.blit(cloud, (0, 0), special_flags=pygame.BLEND_ADD)
            _NEBULAE[base] = tile = tile.convert() if pygame.display.get_surface() is not None else tile
        return tile

    def backdrop(self, surf: pygame.Surface, rect: pygame.Rect, cx: float, cy: float, base: tuple[int, int, int]) -> None:
        """Paint `rect` with the backdrop as seen from world point (cx, cy): it replaces a plain fill."""
        tile = self.nebula(base)
        ox = int(-cx * NEBULA_PARALLAX) % NEBULA_TILE
        oy = int(cy * NEBULA_PARALLAX) % NEBULA_TILE
        y = rect.top - NEBULA_TILE + oy
        while y < rect.bottom:
            x = rect.left - NEBULA_TILE + ox
            while x < rect.right:
                surf.blit(tile, (x, y))
                x += NEBULA_TILE
            y += NEBULA_TILE

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


__all__ = ["NEBULA_TILE", "STAR_LAYERS", "STAR_TILE", "Starfield"]
