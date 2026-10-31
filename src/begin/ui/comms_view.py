"""The comms card and the enemy captains' moods on the map [E].

When the captain hails a ship, or an enemy captain hails us, a card in the top
right of the map shows who is on the channel: their race's emblem, name, ship
and class, their mood as a coloured chip, our officers' read of their resolve,
fear and anger, and the last few words exchanged. Buttons under it make the
common demands in one click, or take a surrendered ship.

On the map, a channel being opened draws a pulse of rings travelling from our
ship to theirs; every enemy captain we have heard from wears a small mark by
their ship: a flame when enraged, a falling chevron when shaken, a wave when
wavering, a white flag once they have surrendered, an arrow while they leave.
Each mark has its own shape as well as its own colour, so they can be told
apart without colour.
"""

from __future__ import annotations

import math
from functools import partial
from typing import TYPE_CHECKING, Callable

import pygame

from ..crew.hails import Channel, Comms, mood_label
from ..sim.ship import ShipStatus
from ..sim.systems import disposition
from . import theme
from .camera import Camera
from .tour_art import wrap

if TYPE_CHECKING:
    from ..sim.world import World
    from .widgets import UI

CARD_W = 360
SHOW_CYCLES = 45.0          # a quiet channel stays on the card this long
WAVE_SECONDS = 2.4          # how long the hailing rings run after the captain speaks

MOOD_COLOR: dict[str, theme.Color] = {
    "enraged": (238, 92, 70),
    "shaken": (236, 176, 70),
    "broken": (236, 150, 90),
    "wavering": (120, 176, 255),
    "calm": (150, 170, 196),
    "surrendered": (236, 240, 246),
    "withdrawing": (140, 200, 180),
    "unknown": (120, 136, 160),
}
FACTION_ACCENT: dict[str, theme.Color] = {
    "klingon": (214, 74, 60), "romulan": (70, 196, 150), "orion": (200, 110, 230), "federation": (90, 170, 255),
}
DEMANDS = (
    ("Demand surrender", "Lower your shields and prepare to be boarded. Your crew will be treated as prisoners of war."),
    ("Order them off", "Leave this sector now and we will hold our fire."),
)


def mood_color(mood: str) -> theme.Color:
    return MOOD_COLOR.get(mood, MOOD_COLOR["unknown"])


# ------------------------------------------------------------------ marks

def mood_mark(surf: pygame.Surface, mood: str, x: float, y: float, s: float = 7.0, t: float = 0.0) -> None:
    """A small mark for a captain's mood, centred on (x, y): its shape alone tells the moods apart."""
    col = mood_color(mood)
    if mood == "enraged":            # a flame
        flick = 1.0 + 0.12 * math.sin(t * 9.0)
        pts = [(x, y - s * 1.3 * flick), (x + s * 0.8, y + s * 0.2), (x + s * 0.45, y + s), (x - s * 0.45, y + s),
               (x - s * 0.8, y + s * 0.2)]
        pygame.draw.polygon(surf, col, pts)
        pygame.draw.polygon(surf, (255, 214, 140), [(x, y - s * 0.3), (x + s * 0.35, y + s * 0.6), (x - s * 0.35, y + s * 0.6)])
    elif mood in ("shaken", "broken"):   # a falling chevron
        for k in (0.0, 0.7) if mood == "broken" else (0.0,):
            oy = y + k * s
            pygame.draw.lines(surf, col, False, [(x - s, oy - s * 0.5), (x, oy + s * 0.4), (x + s, oy - s * 0.5)], 3)
    elif mood == "wavering":          # a wave
        pts = [(x - s + i * s / 4, y + math.sin(i * 1.3 + t * 3.0) * s * 0.45) for i in range(9)]
        pygame.draw.lines(surf, col, False, pts, 2)
    elif mood == "surrendered":      # a white flag
        pygame.draw.line(surf, (200, 206, 216), (x - s * 0.7, y - s * 1.2), (x - s * 0.7, y + s * 1.1), 2)
        wave = math.sin(t * 4.0) * s * 0.15
        pygame.draw.polygon(surf, col, [(x - s * 0.6, y - s * 1.2), (x + s, y - s * 0.95 + wave), (x + s * 0.9, y - s * 0.2 + wave),
                                        (x - s * 0.6, y - s * 0.35)])
    elif mood == "withdrawing":      # an arrow away
        pygame.draw.line(surf, col, (x - s, y), (x + s * 0.6, y), 2)
        pygame.draw.polygon(surf, col, [(x + s, y), (x + s * 0.3, y - s * 0.6), (x + s * 0.3, y + s * 0.6)])
    else:                             # composed: a steady ring
        pygame.draw.circle(surf, col, (int(x), int(y)), int(s * 0.7), 2)


def draw_map(surf: pygame.Surface, cam: Camera, world: World, side: int, player_id: int | None, comms: Comms,
             now: float, clip: pygame.Rect) -> None:
    """Mood marks by the enemy ships we have heard from, and the rings of a channel being opened."""
    old = surf.get_clip()
    surf.set_clip(clip)
    for s in world.ships.values():
        if not s.exists or s.side == side or not world.is_visible(side, s.id):
            continue
        ch = comms.channels.get(s.id)
        # a captain's mood shows in how they fight, so our officers can tell when it is strong; once we have
        # spoken with them we know them better
        mood = ("surrendered" if s.status == ShipStatus.SURRENDERED else
                "withdrawing" if s.mood.terms else disposition.shows(s) or (ch.mood if ch is not None else ""))
        if not mood or mood in ("captured", "destroyed", "gone", "adrift", "unknown"):
            continue
        pos = world.apparent_position(side, s.id)
        if pos is None:
            continue
        sx, sy = cam.to_screen(*pos)
        if not clip.collidepoint(sx, sy):
            continue
        r = 18 + max(0.0, 40 * cam.zoom * 2.0)
        mx, my = sx - r - 12, sy - r - 6
        halo = pygame.Surface((30, 30), pygame.SRCALPHA)
        pygame.draw.circle(halo, (*theme.BG, 170), (15, 15), 13)
        pygame.draw.circle(halo, (*mood_color(mood), 110), (15, 15), 13, 1)
        surf.blit(halo, (mx - 15, my - 15))
        mood_mark(surf, mood, mx, my, 6.0, now)
    # the channel being opened: rings run from our ship to theirs, and pulse around them while they answer
    me = world.ships.get(player_id) if player_id is not None else None
    focus = comms.channels.get(comms.focus) if comms.focus is not None else None
    if me is not None and focus is not None:
        t = world.ships.get(focus.ship_id)
        pos = world.apparent_position(side, focus.ship_id) if t is not None else None
        age = now - comms.opened_at
        if pos is not None and (focus.status == "hailing" or age < WAVE_SECONDS):
            ax, ay = cam.to_screen(me.x, me.y)
            bx, by = cam.to_screen(*pos)
            overlay = pygame.Surface(clip.size, pygame.SRCALPHA)
            ox, oy = clip.x, clip.y
            col = theme.HAIL
            d = math.hypot(bx - ax, by - ay)
            if d > 1:
                for i in range(4):
                    f = ((now * 0.7 + i / 4) % 1.0)
                    px, py = ax + (bx - ax) * f, ay + (by - ay) * f
                    alpha = int(170 * math.sin(math.pi * f))
                    pygame.draw.circle(overlay, (*col, alpha), (int(px - ox), int(py - oy)), int(5 + 6 * f), 2)
                n = int(d // 14)
                for k in range(0, n, 2):
                    p0 = (ax + (bx - ax) * k / n - ox, ay + (by - ay) * k / n - oy)
                    p1 = (ax + (bx - ax) * (k + 1) / n - ox, ay + (by - ay) * (k + 1) / n - oy)
                    pygame.draw.line(overlay, (*col, 60), p0, p1, 1)
            for i in range(3):
                f = (now * 0.8 + i / 3) % 1.0
                pygame.draw.circle(overlay, (*col, int(150 * (1 - f))), (int(bx - ox), int(by - oy)), int(14 + 34 * f), 2)
            surf.blit(overlay, clip.topleft)
    surf.set_clip(old)


# ------------------------------------------------------------------ the card

def emblem(surf: pygame.Surface, faction: str, cx: int, cy: int, r: int) -> None:
    """A plain geometric badge for the race (not any studio's insignia)."""
    acc = FACTION_ACCENT.get(faction, (160, 170, 190))
    pygame.draw.circle(surf, theme.mix(theme.BG, acc, 0.22), (cx, cy), r)
    pygame.draw.circle(surf, acc, (cx, cy), r, 2)
    k = r * 0.62
    if faction == "klingon":           # three blades
        for i in range(3):
            a = math.radians(90 + i * 120)
            tip = (cx + math.cos(a) * k, cy - math.sin(a) * k)
            l = (cx + math.cos(a + 2.6) * k * 0.35, cy - math.sin(a + 2.6) * k * 0.35)
            rr = (cx + math.cos(a - 2.6) * k * 0.35, cy - math.sin(a - 2.6) * k * 0.35)
            pygame.draw.polygon(surf, acc, [tip, l, (cx, cy), rr])
    elif faction == "romulan":         # spread wings
        pygame.draw.polygon(surf, acc, [(cx, cy - k * 0.2), (cx - k, cy - k * 0.6), (cx - k * 0.6, cy + k * 0.2),
                                        (cx, cy + k * 0.6), (cx + k * 0.6, cy + k * 0.2), (cx + k, cy - k * 0.6)])
    elif faction == "orion":           # a four-point star
        pygame.draw.polygon(surf, acc, [(cx, cy - k), (cx + k * 0.25, cy - k * 0.25), (cx + k, cy),
                                        (cx + k * 0.25, cy + k * 0.25), (cx, cy + k), (cx - k * 0.25, cy + k * 0.25),
                                        (cx - k, cy), (cx - k * 0.25, cy - k * 0.25)])
    else:                              # an arrowhead
        pygame.draw.polygon(surf, acc, [(cx, cy - k), (cx + k * 0.7, cy + k * 0.8), (cx, cy + k * 0.35),
                                        (cx - k * 0.7, cy + k * 0.8)])


def showing(comms: Comms, world: World) -> Channel | None:
    ch = comms.channels.get(comms.focus) if comms.focus is not None else None
    if ch is None:
        return None
    quiet = (world.tick - ch.tick) / world.rules.ticks_per_cycle
    if ch.status == "hailing" or quiet < SHOW_CYCLES or comms.pinned:
        return ch
    return None


def draw_card(surf: pygame.Surface, top_right: tuple[int, int], world: World, side: int, player_id: int | None,
              comms: Comms, ui: UI, now: float, run: Callable[[str], None]) -> pygame.Rect | None:
    """The comms card; returns the area it covers."""
    ch = showing(comms, world)
    if ch is None:
        return None
    s = world.ships.get(ch.ship_id)
    me = world.ships.get(player_id) if player_id is not None else None
    if s is None:
        return None
    mood = "surrendered" if s.status == ShipStatus.SURRENDERED else ch.mood
    acc = FACTION_ACCENT.get(ch.faction, theme.HAIL)
    x0, y0 = top_right[0] - CARD_W, top_right[1]
    pad = 12
    inner = CARD_W - 2 * pad
    # what goes in it, to size it first
    talk: list[tuple[str, theme.Color, str]] = []
    for who, text in ch.lines[-3:]:
        if who == "us":
            talk.extend((ln, theme.FRIEND, "regular") for ln in wrap(f"You: {text}", 12, inner))
        elif who == "them":
            talk.extend((ln, theme.HAIL, "regular") for ln in wrap(f"{ch.captain}: {text}", 12, inner))
        else:
            talk.extend((ln, theme.TEXT_DIM, "regular") for ln in wrap(text, 12, inner))
    talk = talk[-7:]
    live = s.alive or s.status == ShipStatus.SURRENDERED
    buttons = live and me is not None and me.alive
    h = 26 + 54 + 8 + (3 * 16 + 6 if s.alive else 0) + len(talk) * 16 + 8 + (30 if buttons else 0) + 6
    box = pygame.Rect(x0, y0, CARD_W, h)
    pulse = 0.5 + 0.5 * math.sin(now * math.tau / 1.6)
    pygame.draw.rect(surf, theme.BG_PANEL_HI, box, border_radius=6)
    edge = theme.mix(theme.dim(acc, 0.7), theme.HAIL, 0.5 * pulse) if ch.status == "hailing" else theme.dim(acc, 0.7)
    pygame.draw.rect(surf, edge, box, 1, border_radius=6)
    pygame.draw.line(surf, acc, (box.x + 10, box.y + 1), (box.x + 46, box.y + 1), 2)
    # header: channel state, with a live dot
    state = {"hailing": "HAILING…", "open": "CHANNEL OPEN", "closed": "CHANNEL CLOSED"}.get(ch.status, ch.status.upper())
    dot = theme.HAIL if ch.status != "closed" else theme.TEXT_FAINT
    if ch.status == "hailing":
        dot = theme.mix(theme.BG, theme.HAIL, 0.4 + 0.6 * pulse)
    pygame.draw.circle(surf, dot, (box.x + pad + 4, box.y + 13), 4)
    theme.text(surf, state, (box.x + pad + 14, box.y + 6), theme.TEXT_DIM, 11, "display", weight="medium")
    others = [c for c in comms.visible() if c.ship_id != ch.ship_id][:3]
    cx = box.right - 30
    close = pygame.Rect(box.right - 24, box.y + 4, 18, 18)
    theme.text(surf, "×", close.center, theme.TEXT_DIM, 15, anchor="center")
    ui.add(close, comms.dismiss, "Close the comms card (it comes back when someone hails)")
    for o in reversed(others):           # other channels: click a chip to bring it up
        w = theme.text_width(o.ship, 10) + 22
        chip = pygame.Rect(cx - w, box.y + 5, w, 16)
        cx -= w + 4
        if chip.x < box.x + 120:
            break
        pygame.draw.rect(surf, theme.BG_INPUT, chip, border_radius=8)
        pygame.draw.rect(surf, theme.dim(mood_color(o.mood), 0.8), chip, 1, border_radius=8)
        pygame.draw.circle(surf, mood_color(o.mood), (chip.x + 8, chip.centery), 3)
        theme.text(surf, o.ship, (chip.x + 14, chip.y + 2), theme.TEXT_DIM, 10)
        ui.add(chip, partial(comms.show, o.ship_id), f"{o.title} {o.captain} ({o.ship}): {mood_label(o.mood)}")
    y = box.y + 26
    # who: emblem, name, ship and class, and the mood chip
    emblem(surf, ch.faction, box.x + pad + 22, y + 24, 22)
    nx = box.x + pad + 54
    name = f"{ch.title} {ch.captain}" if ch.captain and ch.captain != "unknown" else ch.title
    theme.text(surf, name, (nx, y + 2), theme.TEXT, 17, "display", weight="medium")
    theme.text(surf, f"{ch.ship}  ·  {ch.cls_name}", (nx, y + 25), theme.TEXT_DIM, 12)
    label = mood_label(mood).upper()
    mcol = mood_color(mood)
    cw = theme.text_width(label, 10, weight="semibold") + 30
    chip = pygame.Rect(box.right - pad - cw, y + 2, cw, 20)
    pygame.draw.rect(surf, theme.mix(theme.BG, mcol, 0.2), chip, border_radius=10)
    pygame.draw.rect(surf, mcol, chip, 1, border_radius=10)
    mood_mark(surf, mood, chip.x + 11, chip.centery, 5.0, now)
    theme.text(surf, label, (chip.x + 21, chip.y + 4), mcol, 10, weight="semibold")
    y += 54 + 8
    # our read of them: resolve, fear, anger
    if s.alive and me is not None:
        r = disposition.reading(world, me, s)
        for what, v, col, tip in (
                ("Resolve", r.resolve, (150, 170, 220), "How hard they are to talk round. Every loss they watch wears it down."),
                ("Fear", r.fear, MOOD_COLOR["shaken"], "Their losses, damage, crew morale and the odds. Fear makes them yield."),
                ("Anger", r.anger, MOOD_COLOR["enraged"], "Anger makes them fight on and refuse terms. It cools with time.")):
            theme.text(surf, what, (box.x + pad, y), theme.TEXT_DIM, 11)
            bar = pygame.Rect(box.x + pad + 62, y + 4, inner - 62, 7)
            theme.bar(surf, bar, v, col)
            ui.add(pygame.Rect(box.x + pad, y, inner, 15), lambda: None, f"{what}: {tip} (our officers' read)")
            y += 16
        y += 6
    for line, col, weight in talk:
        theme.text(surf, line, (box.x + pad, y), col, 12, weight=weight)
        y += 16
    y += 8
    if buttons:
        say_w = 62
        bw = (inner - say_w - 12) // 2
        if s.status == ShipStatus.SURRENDERED:
            ui.button(surf, pygame.Rect(box.x + pad, y, inner, 24), f"Board and take the {s.name}",
                      lambda: run(f"capture {s.name}"),
                      "Your officer closes, lowers our facing shield and beams a party across. Her crew don't "
                      "resist: they become prisoners of war.", accent=theme.CREW)
        else:
            for i, (label_, words) in enumerate(DEMANDS):
                ui.button(surf, pygame.Rect(box.x + pad + i * (bw + 6), y, bw, 24), label_,
                          partial(run, f"hail #{s.id} {words}"), f'Say: "{words}"', accent=theme.HAIL, size=11)
            ui.button(surf, pygame.Rect(box.right - pad - say_w, y, say_w, 24), "Say…",
                      lambda: run(f"\0type:hail {s.name} "), "Type your own words to this captain", accent=theme.HAIL,
                      size=11)
    return box


__all__ = ["draw_card", "draw_map", "emblem", "mood_color", "mood_mark", "showing"]
