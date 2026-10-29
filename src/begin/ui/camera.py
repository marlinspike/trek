"""World ↔ screen transform for the tactical map (compass world: +y is up on screen)."""

from __future__ import annotations

from dataclasses import dataclass

import pygame


@dataclass
class Camera:
    rect: pygame.Rect
    cx: float = 0.0
    cy: float = 0.0
    zoom: float = 0.05          # pixels per world unit
    min_zoom: float = 0.0005
    max_zoom: float = 1.2
    follow: int | None = None   # ship id to keep centred

    def to_screen(self, x: float, y: float) -> tuple[float, float]:
        return (self.rect.centerx + (x - self.cx) * self.zoom, self.rect.centery - (y - self.cy) * self.zoom)

    def to_world(self, sx: float, sy: float) -> tuple[float, float]:
        return (self.cx + (sx - self.rect.centerx) / self.zoom, self.cy - (sy - self.rect.centery) / self.zoom)

    def zoom_at(self, factor: float, sx: float, sy: float) -> None:
        wx, wy = self.to_world(sx, sy)
        self.zoom = max(self.min_zoom, min(self.max_zoom, self.zoom * factor))
        nx, ny = self.to_world(sx, sy)
        if self.follow is None:
            self.cx += wx - nx
            self.cy += wy - ny

    def pan_pixels(self, dx: float, dy: float) -> None:
        self.follow = None
        self.cx -= dx / self.zoom
        self.cy += dy / self.zoom

    def visible(self, x: float, y: float, margin: float = 60.0) -> bool:
        sx, sy = self.to_screen(x, y)
        r = self.rect
        return r.left - margin <= sx <= r.right + margin and r.top - margin <= sy <= r.bottom + margin

    def world_span(self) -> float:
        return self.rect.width / self.zoom


__all__ = ["Camera"]
