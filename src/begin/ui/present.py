"""Putting a finished frame on the screen [E].

The scenes draw a frame on `presenter.screen`, a surface of the window's logical size, and the presenter shows it.
There are two:

- `SoftwarePresenter` is pygame's own window, drawn at one pixel per logical pixel. It is what the game always
  used, it needs nothing but pygame, and the tests and screenshots use it.
- `GLPresenter` (ui/glpresent.py) opens a high-density OpenGL window through moderngl. The frame is drawn at the
  screen's real density (`gfx.SCALE`), so text and hulls are sharp on a Retina or 4K display, and the GPU adds
  a soft bloom round weapon light and a calm vignette at the edge of the map.

`open_presenter` picks one from the `renderer` setting: "auto" uses the GPU when moderngl, OpenGL 3.3 and a real
graphics card are there and falls back to software otherwise (OpenGL drawn on the CPU, as in a virtual machine,
is slower than pygame's own drawing); "gpu" uses OpenGL even on the CPU; "software" never tries. Any failure
falls back with the reason in `presenter.note`. Nothing in the game depends on which one runs.
"""

from __future__ import annotations

import os
from typing import Protocol

import pygame

from . import gfx

CAPTION = "Begin : Trek — tactical starship simulation"
RENDERERS = ("auto", "gpu", "software")


class Presenter(Protocol):
    name: str                  # "gpu" or "software"
    density: float             # physical pixels per logical pixel
    note: str                  # what is drawing, for the terminal
    why: str                   # why the graphics card isn't drawing, when it was tried and failed ("" otherwise)
    bloom: bool                # glow round weapon light and the vignette (GPU only)

    @property
    def screen(self) -> pygame.Surface: ...
    def size(self) -> tuple[int, int]: ...
    def events(self) -> list[pygame.event.Event]: ...
    def present(self) -> None: ...
    def close(self) -> None: ...


class SoftwarePresenter:
    """pygame's display window at one pixel per logical pixel."""

    name = "software"
    density = 1.0
    bloom = False

    def __init__(self, size: tuple[int, int], icon: pygame.Surface | None, why: str = "") -> None:
        gfx.set_scale(1.0)
        if icon is not None:
            pygame.display.set_icon(icon)
        self._screen = pygame.display.set_mode(size, pygame.RESIZABLE)
        pygame.display.set_caption(CAPTION)
        self.why = why
        self.note = f"software rendering: the graphics card isn't drawing ({why})" if why else "software rendering"

    @property
    def screen(self) -> pygame.Surface:
        return pygame.display.get_surface() or self._screen

    def size(self) -> tuple[int, int]:
        return self.screen.get_size()

    def events(self) -> list[pygame.event.Event]:
        return pygame.event.get()

    def present(self) -> None:
        gfx.take_light()                     # no bloom here: the light is already in the frame
        pygame.display.flip()

    def close(self) -> None:
        pass


class DisplayControl(Protocol):
    """What the Display page may do: read how frames are shown, turn the glow on or off at once, and restart
    the game so a new renderer takes over (a window can't change renderer while it is open)."""

    @property
    def presenter(self) -> Presenter: ...
    @property
    def started_with(self) -> str: ...
    def set_bloom(self, on: bool) -> None: ...
    def restart(self) -> None: ...


RENDERER_INFO: dict[str, tuple[str, str]] = {
    "auto": ("Automatic", "The graphics card when it can, at the screen's full sharpness; pygame's own drawing "
                          "when it can't (no OpenGL 3.3, or OpenGL drawn on the processor)."),
    "gpu": ("Graphics card", "Always OpenGL, even where it is drawn on the processor (slower there). Sharp on "
                             "Retina and 4K screens, with the glow round weapon light."),
    "software": ("Software", "pygame's own drawing, one pixel per point, as the game always drew. Softer on "
                             "high-density screens; works everywhere."),
}


def relaunch_command(argv: list[str], orig_argv: list[str], executable: str, frozen: bool) -> list[str]:
    """The command that starts this game again the way it was started (minus a one-off `--renderer`, so the
    setting just chosen applies)."""
    args = argv[1:] if frozen else orig_argv[1:]
    out: list[str] = []
    skip = False
    for a in args:
        if skip:
            skip = False
            continue
        if a == "--renderer":
            skip = True
            continue
        if a.startswith("--renderer="):
            continue
        out.append(a)
    return [executable, *out]


def prepare(renderer: str) -> None:
    """Hints that must be set before pygame starts its video system."""
    if renderer != "software":
        # Windows: lay the window out in points and hand us the real pixels, as macOS does, instead of letting
        # Windows stretch a blurry low-density window.
        os.environ.setdefault("SDL_WINDOWS_DPI_SCALING", "1")


def open_presenter(renderer: str, size: tuple[int, int], icon: pygame.Surface | None,
                   bloom: bool = True) -> Presenter:
    renderer = renderer if renderer in RENDERERS else "auto"
    if renderer == "software" or os.environ.get("SDL_VIDEODRIVER") == "dummy":
        return SoftwarePresenter(size, icon)
    try:
        from .glpresent import GLPresenter

        return GLPresenter(size, icon, bloom=bloom, allow_software_gl=renderer == "gpu")
    except Exception as e:  # noqa: BLE001 - any failure to get a GPU window means software, never a crash
        why = str(e) if isinstance(e, RuntimeError) and str(e) else f"{type(e).__name__}: {e}"
        return SoftwarePresenter(size, icon, why=why)


__all__ = ["CAPTION", "DisplayControl", "Presenter", "RENDERERS", "RENDERER_INFO", "SoftwarePresenter",
           "open_presenter", "prepare", "relaunch_command"]
