"""The GPU compositor, on an offscreen OpenGL context (skipped where there is none).

A presenter must never change what the game drew, only add light: the panels pass through untouched, weapon
light gets a soft halo, and the vignette darkens only the edge of the map.
"""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
moderngl = pytest.importorskip("moderngl")

import pygame  # noqa: E402

from begin.ui import gfx  # noqa: E402
from begin.ui.glpresent import Compositor  # noqa: E402


def _context() -> moderngl.Context:
    for kw in ({"standalone": True, "backend": "egl"}, {"standalone": True}):
        try:
            return moderngl.create_context(require=330, **kw)
        except Exception:  # noqa: BLE001 - no GL here: skip
            continue
    pytest.skip("no offscreen OpenGL 3.3 context")


W, H = 320, 180


@pytest.fixture()
def gpu() -> tuple[moderngl.Context, Compositor, moderngl.Framebuffer]:
    pygame.init()
    ctx = _context()
    comp = Compositor(ctx)
    comp.resize((W, H))
    yield ctx, comp, ctx.simple_framebuffer((W, H))
    comp.release()
    ctx.release()


def _read(fbo: moderngl.Framebuffer) -> pygame.Surface:
    return pygame.image.frombytes(fbo.read(components=3), (W, H), "RGB", True)


def _frame() -> pygame.Surface:
    s = pygame.Surface((W, H))
    s.fill((20, 40, 60))
    s.fill((200, 100, 50), (10, 10, 30, 20))
    return s


def test_the_frame_passes_through_unchanged(gpu: tuple) -> None:
    ctx, comp, fbo = gpu
    frame = _frame()
    comp.draw(frame, [], None, fbo, (W, H))
    out = _read(fbo)
    for p in [(0, 0), (15, 15), (W - 1, H - 1), (100, 90)]:
        assert tuple(out.get_at(p))[:3] == tuple(frame.get_at(p))[:3]


def test_weapon_light_blooms_and_goes_away(gpu: tuple) -> None:
    ctx, comp, fbo = gpu
    frame = pygame.Surface((W, H))
    glow = pygame.Surface((W, H))
    glow.fill((255, 220, 120), (150, 80, 6, 6))
    lit = pygame.Rect(150, 80, 6, 6)
    comp.draw(frame, [(glow, lit)], None, fbo, (W, H))
    near, far = _read(fbo).get_at((147, 83)), _read(fbo).get_at((20, 20))
    assert near.r > 20 and near.g > 15                    # a halo round the light
    assert tuple(far)[:3] == (0, 0, 0)                     # nothing far from it
    comp.draw(frame, [(glow, lit)], None, fbo, (W, H), bloom=False)
    assert tuple(_read(fbo).get_at((147, 83)))[:3] == (0, 0, 0)
    comp.draw(frame, [], None, fbo, (W, H))                # the light is gone: so is the halo
    assert tuple(_read(fbo).get_at((147, 83)))[:3] == (0, 0, 0)


def test_the_vignette_touches_only_the_edge_of_the_map(gpu: tuple) -> None:
    ctx, comp, fbo = gpu
    frame = pygame.Surface((W, H))
    frame.fill((200, 200, 200))
    stage = pygame.Rect(0, 0, 200, H)
    comp.draw(frame, [], stage, fbo, (W, H))
    out = _read(fbo)
    assert out.get_at((2, 2)).r < 190                      # the map's corner is a little darker
    assert out.get_at((2, 2)).r > 140                      # ...but only a little
    assert out.get_at((100, 90)).r == 200                  # its middle is untouched
    assert out.get_at((260, 2)).r == 200                   # and so are the panels beside it


def test_light_is_offered_through_gfx() -> None:
    gfx.take_light()
    layer = pygame.Surface((10, 10))
    gfx.set_stage((0, 0, 8, 8))                             # the map starts its frame
    gfx.offer_light(layer, (1, 1, 2, 2))
    gfx.offer_light(layer, (0, 0, 0, 0))                    # nothing lit: ignored
    light, stage = gfx.take_light()
    assert len(light) == 1 and stage == pygame.Rect(0, 0, 8, 8)
    assert gfx.take_light() == ([], None)


def test_light_never_piles_up_when_frames_are_not_shown() -> None:
    layer = pygame.Surface((10, 10))
    for _ in range(50):                       # frames drawn headless: the map starts each one with its stage
        gfx.set_stage((0, 0, 8, 8))
        gfx.offer_light(layer, (1, 1, 2, 2))
    assert len(gfx.take_light()[0]) == 1
