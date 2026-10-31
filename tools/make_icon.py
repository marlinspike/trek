"""Draw the app icon from the game's own Enterprise art.

Writes packaging/icon.png (1024 px), packaging/icon.icns (macOS), packaging/icon.ico
(Windows) and src/begin/assets/icon.png (256 px, the game window's icon).
Run from the project root: python tools/make_icon.py   (needs pygame-ce and Pillow)
"""

from __future__ import annotations

import os
import random
import sys
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import pygame  # noqa: E402
from PIL import Image  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
SHIP = ROOT / "src" / "begin" / "assets" / "ships" / "heavy-cruiser-000.png"
SIZE = 1024
TILE = 824                 # Apple's icon grid: an 824 px rounded square centred on a 1024 canvas
RADIUS = 185
ANGLE = -38                # the ship flies up and to the right


def draw() -> pygame.Surface:
    pygame.init()
    pygame.display.set_mode((1, 1))
    canvas = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    tile = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    # deep space: a vertical blend from navy to near black, with a faint glow behind the ship
    for y in range(TILE):
        t = y / TILE
        c = (int(18 - 10 * t), int(34 - 22 * t), int(70 - 46 * t))
        pygame.draw.line(tile, c, (0, y), (TILE, y))
    glow = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    for r in range(TILE // 2, 0, -6):
        a = int(46 * (1 - r / (TILE / 2)) ** 2)
        pygame.draw.circle(glow, (80, 150, 255, a), (TILE // 2, TILE // 2), r)
    tile.blit(glow, (0, 0))
    rng = random.Random(47)
    for _ in range(140):
        x, y = rng.randrange(TILE), rng.randrange(TILE)
        b = rng.randrange(90, 230)
        rad = 1 if rng.random() < 0.85 else 2
        pygame.draw.circle(tile, (b, b, min(255, b + 20)), (x, y), rad)
    ship = pygame.image.load(str(SHIP)).convert_alpha()
    ship = pygame.transform.rotozoom(ship, ANGLE, 1.0)
    scale = TILE * 0.86 / max(ship.get_size())
    ship = pygame.transform.smoothscale(ship, (round(ship.get_width() * scale), round(ship.get_height() * scale)))
    tile.blit(ship, ship.get_rect(center=(TILE // 2, TILE // 2 + 6)))
    # round the corners
    mask = pygame.Surface((TILE, TILE), pygame.SRCALPHA)
    pygame.draw.rect(mask, (255, 255, 255, 255), mask.get_rect(), border_radius=RADIUS)
    tile.blit(mask, (0, 0), special_flags=pygame.BLEND_RGBA_MIN)
    pygame.draw.rect(tile, (110, 150, 210, 90), tile.get_rect(), width=3, border_radius=RADIUS)
    # a soft drop shadow under the tile, as macOS icons have
    shadow = pygame.Surface((SIZE, SIZE), pygame.SRCALPHA)
    off = (SIZE - TILE) // 2
    for i in range(24, 0, -2):
        pygame.draw.rect(shadow, (0, 0, 0, 7), pygame.Rect(off - i, off - i + 12, TILE + 2 * i, TILE + 2 * i),
                         border_radius=RADIUS + i)
    canvas.blit(shadow, (0, 0))
    canvas.blit(tile, (off, off))
    return canvas


def to_pil(surf: pygame.Surface) -> Image.Image:
    return Image.frombytes("RGBA", surf.get_size(), pygame.image.tobytes(surf, "RGBA"))


def main() -> int:
    img = to_pil(draw())
    out = ROOT / "packaging"
    img.save(out / "icon.png")
    img.save(out / "icon.icns")
    # Windows shows icons small, so give it the tile without the macOS margin
    off = (SIZE - TILE) // 2
    square = img.crop((off, off, off + TILE, off + TILE))
    square.save(out / "icon.ico", sizes=[(s, s) for s in (16, 24, 32, 48, 64, 128, 256)])
    square.resize((256, 256), Image.LANCZOS).save(ROOT / "src" / "begin" / "assets" / "icon.png")
    print("wrote", ", ".join(str(p.relative_to(ROOT)) for p in (out / "icon.png", out / "icon.icns", out / "icon.ico")))
    return 0


if __name__ == "__main__":
    sys.exit(main())
