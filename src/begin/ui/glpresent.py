"""The GPU presenter: a sharp frame at the screen's real density, with soft bloom and a calm vignette [E].

The window is opened by SDL with high density allowed, so on a Retina Mac, a Windows display at 150% or 200%
or a scaled Wayland desktop the layout stays in points while the frame is drawn in real pixels (`gfx.SCALE`).
The scenes still draw with pygame on the CPU; each frame is uploaded to a texture (about half a millisecond for
a 3200 × 1800 frame) and drawn by one shader, which also:

- **blooms weapon light**: the glow layer the map adds under phaser beams, disruptor bolts and blasts
  (`gfx.offer_light`) is shrunk to a quarter, blurred, and added back as a soft halo. Only that light blooms,
  never text or panels, so the screen stays calm;
- **darkens the edge of the map a little** (`gfx.set_stage`), like a viewscreen, and leaves the panels alone.

Needs moderngl and OpenGL 3.3, which every Mac since 2012 and any Windows or Linux driver of the last decade
provides; `ui/present.open_presenter` falls back to software rendering without them.
"""

from __future__ import annotations

import ctypes
import math
import ctypes.util
import glob
import os
import sys
from typing import Any

import moderngl
import pygame

from . import gfx
from .present import CAPTION

BLOOM_STRENGTH = 2.5      # how much of the blurred light is added back
VIGNETTE = 0.14            # how much darker the very corner of the map gets (0: none)
BLOOM_DOWN = 4             # the bloom is blurred at a quarter of the frame's logical size
SOFTWARE_GL = ("llvmpipe", "softpipe", "swiftshader", "gdi generic", "basic render", "software rasterizer")

_VERT = """
#version 330
out vec2 uv;
void main() {
    vec2 p = vec2(float((gl_VertexID << 1) & 2), float(gl_VertexID & 2));
    uv = p;
    gl_Position = vec4(p * 2.0 - 1.0, 0.0, 1.0);
}
"""

_DOWN = """
#version 330
uniform sampler2D src;       // with mipmaps: each level is the average of the one above
uniform float lod;           // the level as small as the bloom texture
in vec2 uv;
out vec4 color;
void main() {
    color = vec4(textureLod(src, uv, lod).rgb, 1.0);
}
"""

_BLUR = """
#version 330
uniform sampler2D src;
uniform vec2 step;           // one texel along the blur's direction
in vec2 uv;
out vec4 color;
const float w[5] = float[](0.2270270, 0.1945946, 0.1216216, 0.0540540, 0.0162162);
void main() {
    vec3 c = texture(src, uv).rgb * w[0];
    for (int i = 1; i < 5; ++i) {
        c += texture(src, uv + step * float(i)).rgb * w[i];
        c += texture(src, uv - step * float(i)).rgb * w[i];
    }
    color = vec4(c, 1.0);
}
"""

_COMPOSE = """
#version 330
uniform sampler2D frame;
uniform sampler2D bloom;
uniform float bloom_k;
uniform vec4 stage;          // the map, in uv of the frame (x0, y0, x1, y1), top-down; empty: no vignette
uniform float vignette;
in vec2 uv;
out vec4 color;
void main() {
    vec2 t = vec2(uv.x, 1.0 - uv.y);                 // the frame is stored top row first
    vec3 c = texture(frame, t).rgb + texture(bloom, t).rgb * bloom_k;
    if (vignette > 0.0 && t.x > stage.x && t.x < stage.z && t.y > stage.y && t.y < stage.w) {
        vec2 q = (t - stage.xy) / (stage.zw - stage.xy) * 2.0 - 1.0;     // -1..1 across the map
        float d = length(q * vec2(0.85, 1.0));
        c *= 1.0 - vignette * smoothstep(0.85, 1.45, d);
    }
    color = vec4(min(c, vec3(1.0)), 1.0);
}
"""


def _sdl() -> Any | None:
    """The SDL library pygame loaded, for the one thing pygame doesn't expose: the drawable size in pixels."""
    here = os.path.dirname(pygame.__file__)
    roots = [here, os.path.join(here, ".dylibs"), os.path.join(here, os.pardir, "pygame_ce.libs"),
             os.path.join(here, os.pardir, "pygame.libs"), getattr(sys, "_MEIPASS", "")]
    names = ("libSDL2-2.0*.dylib", "libSDL2-2*.so*", "libSDL2.so*", "SDL2.dll")
    found = [p for r in roots if r for n in names for p in glob.glob(os.path.join(r, n))]
    found += [p for p in (ctypes.util.find_library("SDL2"),) if p]
    for path in found:
        try:
            lib = ctypes.CDLL(path)
            lib.SDL_GetWindowFromID.restype = ctypes.c_void_p
            lib.SDL_GetWindowFromID.argtypes = [ctypes.c_uint32]
            lib.SDL_GL_GetDrawableSize.argtypes = [ctypes.c_void_p, ctypes.POINTER(ctypes.c_int),
                                                   ctypes.POINTER(ctypes.c_int)]
            return lib
        except (OSError, AttributeError):
            continue
    return None


class Compositor:
    """The GPU half, apart from any window: a frame and its light in, the finished picture out.

    Works on any moderngl context, so it can be tested with an offscreen one.
    """

    def __init__(self, ctx: moderngl.Context) -> None:
        self.ctx = ctx
        self._down = ctx.program(vertex_shader=_VERT, fragment_shader=_DOWN)
        self._blur = ctx.program(vertex_shader=_VERT, fragment_shader=_BLUR)
        self._compose = ctx.program(vertex_shader=_VERT, fragment_shader=_COMPOSE)
        # one empty vertex array per program: the triangle that covers the screen comes from gl_VertexID
        self._vaos = {p: ctx.vertex_array(prog, []) for p, prog in
                      (("down", self._down), ("blur", self._blur), ("compose", self._compose))}
        self._textures: list[moderngl.Texture] = []
        self.size = (0, 0)
        self.density = 1.0

    def resize(self, size: tuple[int, int], density: float = 1.0) -> None:
        """Textures for frames of `size` physical pixels at `density` (so the halo is the same size on any
        screen)."""
        if size == self.size and density == self.density:
            return
        self.density = density
        for tex in self._textures:
            tex.release()
        ctx, (pw, ph) = self.ctx, size
        self.size = size
        self.frame = ctx.texture((pw, ph), 4)
        self.light = ctx.texture((pw, ph), 4)
        down = max(1, round(BLOOM_DOWN * density))
        small = (max(1, pw // down), max(1, ph // down))
        self._a, self._b = ctx.texture(small, 4), ctx.texture(small, 4)
        self._textures = [self.frame, self.light, self._a, self._b]
        for tex in self._textures:
            tex.filter = (moderngl.LINEAR, moderngl.LINEAR)
            tex.repeat_x = tex.repeat_y = False
        self.frame.swizzle = self.light.swizzle = "BGR1"         # pygame keeps pixels as B, G, R, (A or unused)
        self._light_fbo = ctx.framebuffer([self.light])
        self._fa, self._fb = ctx.framebuffer([self._a]), ctx.framebuffer([self._b])
        self._light_fbo.clear()
        self._fa.clear()
        self._light_rows: tuple[int, int] | None = None
        self._lit = False

    def draw(self, frame: pygame.Surface, light: list[tuple[pygame.Surface, pygame.Rect]],
             stage: pygame.Rect | None, target: moderngl.Framebuffer, viewport: tuple[int, int],
             bloom: bool = True) -> None:
        """Show `frame` (a surface of `self.size` physical pixels) on `target`, blooming `light` (screen-sized
        glow layers and the logical rects lit on them) and darkening the edges of `stage` (logical)."""
        self.frame.write(frame.get_buffer())
        lit = bloom and self._upload_light(light)
        if lit:
            self._bloom()
        elif self._lit:
            self._fa.clear()
        self._lit = lit

        target.use()
        self.ctx.viewport = (0, 0, *viewport)
        self.frame.use(0)
        self._a.use(1)
        p = self._compose
        p["frame"] = 0
        p["bloom"] = 1
        p["bloom_k"] = BLOOM_STRENGTH if lit else 0.0
        w, h = frame.get_size()                                   # logical, as the stage is
        if bloom and stage is not None and stage.w > 0 and stage.h > 0:
            p["stage"] = (stage.left / w, stage.top / h, stage.right / w, stage.bottom / h)
            p["vignette"] = VIGNETTE
        else:
            p["stage"] = (0.0, 0.0, 0.0, 0.0)
            p["vignette"] = 0.0
        self._vaos["compose"].render(moderngl.TRIANGLES, vertices=3)

    def release(self) -> None:
        for tex in self._textures:
            tex.release()
        self._textures = []

    def _upload_light(self, light: list[tuple[pygame.Surface, pygame.Rect]]) -> bool:
        """Copy the rows of the glow layer that were lit (and those lit last time, now dark) to the GPU."""
        prev = self._light_rows
        layer = light[0][0] if light else None
        lsize = (layer.get_physical_size() if isinstance(layer, gfx.Canvas) else layer.get_size()) if layer else None
        if layer is None or lsize != self.size:
            if prev is not None:
                self._light_fbo.clear()
                self._light_rows = None
            return False
        rows = light[0][1].unionall([r for _, r in light[1:]])
        s = layer.density if isinstance(layer, gfx.Canvas) else 1.0
        ph = self.size[1]
        y0 = max(0, int(rows.top * s) - 2)
        y1 = min(ph, int(rows.bottom * s + 0.999) + 2)
        if prev is not None:
            y0, y1 = min(y0, prev[0]), max(y1, prev[1])
        if y1 <= y0:
            return False
        pitch = layer.get_pitch()
        buf = memoryview(layer.get_buffer())[y0 * pitch:y1 * pitch]     # whole rows: one contiguous block
        self.light.write(buf, viewport=(0, y0, self.size[0], y1 - y0))
        self._light_rows = (y0, y1)
        return True

    def _bloom(self) -> None:
        small = self._a.size
        self._fa.use()
        self.ctx.viewport = (0, 0, *small)
        self.light.build_mipmaps()          # every light pixel counts, however thin the beam
        self.light.use(0)
        self._down["src"] = 0
        self._down["lod"] = math.log2(max(1.0, self.size[0] / small[0]))
        self._vaos["down"].render(moderngl.TRIANGLES, vertices=3)
        for _ in range(2):
            for src, dst, step in ((self._a, self._fb, (1.0 / small[0], 0.0)),
                                   (self._b, self._fa, (0.0, 1.0 / small[1]))):
                dst.use()
                src.use(0)
                self._blur["src"] = 0
                self._blur["step"] = step
                self._vaos["blur"].render(moderngl.TRIANGLES, vertices=3)


class GLPresenter:
    """A high-density OpenGL window showing frames through a `Compositor`."""

    name = "gpu"

    def __init__(self, size: tuple[int, int], icon: pygame.Surface | None, bloom: bool = True,
                 allow_software_gl: bool = False) -> None:
        # ask for OpenGL 3.3 core: macOS gives only 2.1 to a window that doesn't, and moderngl needs 3.3
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MAJOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_MINOR_VERSION, 3)
        pygame.display.gl_set_attribute(pygame.GL_CONTEXT_PROFILE_MASK, pygame.GL_CONTEXT_PROFILE_CORE)
        if sys.platform == "darwin":
            pygame.display.gl_set_attribute(pygame.GL_CONTEXT_FLAGS, pygame.GL_CONTEXT_FORWARD_COMPATIBLE_FLAG)
        self.window = pygame.Window(CAPTION, size, opengl=True, resizable=True, allow_high_dpi=True)
        try:
            self.ctx = moderngl.create_context(require=330)
            renderer = str(self.ctx.info.get("GL_RENDERER", "OpenGL"))
            if not allow_software_gl and any(s in renderer.lower() for s in SOFTWARE_GL):
                raise RuntimeError(f"OpenGL is drawn on the CPU here ({renderer}), slower than pygame's own")
            if icon is not None:
                self.window.set_icon(icon)
            self.bloom = bloom
            self.target: moderngl.Framebuffer = self.ctx.screen     # where frames go (a test may swap in its own)
            self.compositor = Compositor(self.ctx)
            self._lib = _sdl()
            points = self.window.size
            # GL starts with its viewport on the whole drawable: the density, if SDL can't be asked directly
            self._ratio = self.ctx.viewport[2] / max(1, points[0])
            self._resize(points)
            self.note = f"GPU rendering at {self.density:g}x ({renderer})"
        except Exception:
            self.window.destroy()
            raise

    def _drawable(self, points: tuple[int, int]) -> tuple[int, int]:
        """The window's size in real pixels."""
        if self._lib is not None:
            w, h = ctypes.c_int(0), ctypes.c_int(0)
            win = self._lib.SDL_GetWindowFromID(self.window.id)
            if win:
                self._lib.SDL_GL_GetDrawableSize(win, ctypes.byref(w), ctypes.byref(h))
                if w.value > 0 and h.value > 0:
                    return w.value, h.value
        return round(points[0] * self._ratio), round(points[1] * self._ratio)

    def _resize(self, points: tuple[int, int]) -> None:
        self.points = (max(1, points[0]), max(1, points[1]))
        self.pixels = self._drawable(self.points)
        self.density = max(1.0, round(self.pixels[0] / self.points[0], 3))
        gfx.set_scale(self.density)
        self._screen = gfx.Canvas(self.points) if self.density > 1.0 else pygame.Surface(self.points)
        phys = self._screen.get_physical_size() if isinstance(self._screen, gfx.Canvas) else self.points
        self.compositor.resize(phys, self.density)

    # ------------------------------------------------------------ the Presenter protocol

    @property
    def screen(self) -> pygame.Surface:
        return self._screen

    def size(self) -> tuple[int, int]:
        return self.points

    def events(self) -> list[pygame.event.Event]:
        out: list[pygame.event.Event] = []
        for ev in pygame.event.get():
            if ev.type == pygame.WINDOWCLOSE:
                out.append(pygame.event.Event(pygame.QUIT))
            elif ev.type == pygame.VIDEORESIZE:
                continue                                # the display module's; this window reports its own
            elif ev.type in (pygame.WINDOWSIZECHANGED, getattr(pygame, "WINDOWDISPLAYCHANGED", -1)):
                size = self.window.size
                if size != self.points or self._drawable(size) != self.pixels:
                    self._resize(size)
                    out.append(pygame.event.Event(pygame.VIDEORESIZE, w=size[0], h=size[1], size=size))
            else:
                out.append(ev)
        return out

    def present(self) -> None:
        light, stage = gfx.take_light()
        self.compositor.draw(self._screen, light, stage, self.target, self.pixels, self.bloom)
        self.window.flip()

    def close(self) -> None:
        try:
            self.compositor.release()
            self.ctx.release()
        finally:
            self.window.destroy()


__all__ = ["Compositor", "GLPresenter"]
