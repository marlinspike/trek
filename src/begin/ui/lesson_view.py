"""The lesson card: on a Shakedown Cruise stop, what the officer is teaching and the step you are on [E].

It takes the mission card's place in the map's top right corner (a teaching stop has no mission), and like the
mission card it shows in full for a few seconds when there is news (a new step), then folds to one line. Rest the
pointer on the line to see it all. Drawing only: the lesson is `tour/drill.py`'s.
"""

from __future__ import annotations

import pygame

from ..tour.drill import LessonView
from . import gfx, theme
from .counsel_view import MISSION_W


def lines(v: LessonView) -> tuple[str, str]:
    """What the card says: the step (or that the lesson is learned), and how to do it."""
    s = v.current
    if s is None:
        return "Lesson learned", "Fight on as you like."
    return s.say, f"To do it: {s.do}." if s.do else ""


def draw_lesson(surf: pygame.Surface, top_right: tuple[int, int], v: LessonView) -> pygame.Rect:
    """The lesson card in full, its top right corner at `top_right`. Returns its rect."""
    pad = 12
    inner = MISSION_W - 2 * pad
    say, do = lines(v)
    say_lines = theme.clip_lines(theme.wrap(say, 12, inner), 3, 12, inner)
    do_lines = theme.clip_lines(theme.wrap(do, 12, inner), 2, 12, inner) if do else []
    h = 24 + 22 + 12 + 17 * (len(say_lines) + len(do_lines)) + (4 if do_lines else 0) + 8
    box = pygame.Rect(top_right[0] - MISSION_W, top_right[1], MISSION_W, h)
    theme.shadow(surf, box, 6)
    gfx.draw.rect(surf, theme.BG_PANEL_HI, box, border_radius=6)
    gfx.draw.rect(surf, theme.dim(theme.CREW, 0.7), box, 1, border_radius=6)
    gfx.draw.line(surf, theme.CREW, (box.x + 10, box.y + 1), (box.x + 46, box.y + 1), 2)
    n = len(v.steps)
    tag = "LESSON  ·  LEARNED" if v.learned else f"LESSON  ·  STEP {v.step + 1} OF {n}"
    theme.text(surf, tag, (box.x + pad, box.y + 6), theme.TEXT_DIM, 11, "display", weight="medium")
    y = box.y + 24
    theme.text(surf, theme.fit(v.title, 15, inner, weight="medium"), (box.x + pad, y), theme.TEXT, 15, weight="medium")
    y += 22
    _dots(surf, box.x + pad, y + 2, v)
    y += 12
    for ln in say_lines:
        theme.text(surf, ln, (box.x + pad, y), theme.TEXT, 12)
        y += 17
    if do_lines:
        y += 4
        for ln in do_lines:
            theme.text(surf, ln, (box.x + pad, y), theme.CREW, 12)
            y += 17
    return box


def draw_lesson_strip(surf: pygame.Surface, top_right: tuple[int, int], v: LessonView) -> pygame.Rect:
    """The lesson card folded to one line while another card has the map. Returns its rect."""
    box = pygame.Rect(top_right[0] - MISSION_W, top_right[1], MISSION_W, 26)
    theme.shadow(surf, box, 4)
    gfx.draw.rect(surf, theme.BG_PANEL_HI, box, border_radius=6)
    gfx.draw.rect(surf, theme.dim(theme.CREW, 0.6), box, 1, border_radius=6)
    tag = "LESSON"
    theme.text(surf, tag, (box.x + 12, box.y + 7), theme.TEXT_DIM, 10, "display", weight="medium")
    x = box.x + 18 + theme.text_width(tag, 10, "display", "medium")
    s = v.current
    words = "learned" if s is None else (s.do or s.say)
    room = box.right - 12 - x - 40
    theme.text(surf, theme.fit(words[:1].upper() + words[1:], 12, room), (x, box.y + 5), theme.TEXT, 12)
    theme.text(surf, f"{min(v.step, len(v.steps))}/{len(v.steps)}", (box.right - 12, box.y + 5), theme.TEXT_DIM, 12,
               "mono", anchor="topright")
    return box


def _dots(surf: pygame.Surface, x: int, y: int, v: LessonView) -> None:
    """One dot a step: filled when done, ringed for the one now."""
    for i in range(len(v.steps)):
        cx = x + 4 + i * 14
        if i < v.step:
            gfx.draw.circle(surf, theme.GOOD, (cx, y + 3), 4)
        elif i == v.step:
            gfx.draw.circle(surf, theme.CREW, (cx, y + 3), 4, 1)
        else:
            gfx.draw.circle(surf, theme.dim(theme.TEXT_DIM, 0.6), (cx, y + 3), 3, 1)


__all__ = ["draw_lesson", "draw_lesson_strip", "lines"]
