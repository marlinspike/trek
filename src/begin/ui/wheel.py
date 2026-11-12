"""The command wheel [E]: right-click a ship (or press E for your target) and pick an order.

The wheel only adds a way of giving orders: every slice is a console line (from
`content/data/wheel.toml`, or the captain's own `config/wheel.toml`), the
console runs it, and the log shows the line, so the captain learns the console
by using the wheel. Right-clicking empty space still steers, and Shift+right-click
still pursues.

Eight slices, clockwise from the top, the same for every enemy so the hand
learns where things are: Phasers, Torpedoes, Disable, Close to, Hail, Board,
Elude, Target. A slice with choices of its own (Disable: shields, weapons,
engines, warp core) opens a second ring when the mouse rests on it. Our own
ships and our own ship have wheels of their own. Keys 1-8 pick a slice too;
Esc, a right-click or a click outside closes it.
"""

from __future__ import annotations

import math
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from . import theme
from .subtitles import STATION_COLOR, station_mark
from . import gfx

WHEEL_FILE = Path(__file__).resolve().parent.parent / "content" / "data" / "wheel.toml"
INNER, OUTER, RING = 36, 118, 176      # radii: the hub, the slices, the second ring
OPEN_TIME = 0.14                       # seconds the wheel takes to open


@dataclass
class Slice:
    label: str
    line: str = ""
    station: str | None = None
    ring: list[Slice] = field(default_factory=list)


def _slice(d: dict[str, object], station: str | None = None) -> Slice:
    st = d.get("station", station)
    raw = d.get("ring")
    ring = raw if isinstance(raw, list) else []
    return Slice(str(d.get("label", "?")), str(d.get("line", "")), str(st) if st else None,
                 [_slice(r, str(st) if st else None) for r in ring if isinstance(r, dict)])


def load_wheels(override: Path | None = None) -> dict[str, list[Slice]]:
    """{'enemy': [...], 'ally': [...], 'own': [...]}: the captain's file wins, kind by kind."""
    wheels: dict[str, list[Slice]] = {}
    for path in (WHEEL_FILE, override):
        if path is None or not path.exists():
            continue
        try:
            data = tomllib.loads(path.read_text())
        except (OSError, tomllib.TOMLDecodeError):
            continue
        for kind in ("enemy", "ally", "own"):
            rows = data.get(kind)
            if isinstance(rows, list) and rows:
                wheels[kind] = [_slice(r) for r in rows if isinstance(r, dict)][:8]
    return wheels


def fill(line: str, ship: str, me: str, target: str | None) -> str:
    return line.replace("{ship}", ship).replace("{me}", me).replace("{target}", target or ship)


class CommandWheel:
    def __init__(self, ship_id: int, kind: str, name: str, slices: list[Slice], center: tuple[int, int]) -> None:
        self.ship_id = ship_id
        self.kind = kind
        self.name = name
        self.slices = slices
        self.center = center
        self.age = 0.0
        self.hover: int | None = None
        self.sub: int | None = None        # the slice whose second ring is open
        self.sub_hover: int | None = None

    # ------------------------------------------------------------ geometry

    def _angles(self, i: int, n: int) -> tuple[float, float]:
        """Start and end angle of slice i (degrees clockwise from the top)."""
        w = 360.0 / n
        return i * w - w / 2, i * w + w / 2

    def _sub_angles(self, j: int) -> tuple[float, float]:
        assert self.sub is not None
        n = len(self.slices)
        a0, a1 = self._angles(self.sub, n)
        ring = self.slices[self.sub].ring
        span = max(a1 - a0, 26.0 * len(ring))
        mid = (a0 + a1) / 2
        w = span / len(ring)
        s = mid - span / 2 + j * w
        return s, s + w

    @staticmethod
    def _in(a: float, lo: float, hi: float) -> bool:
        a = (a - lo) % 360.0
        return a < (hi - lo)

    def locate(self, pos: tuple[int, int]) -> tuple[str, int | None]:
        """('slice', i), ('ring', j), ('hub', None) or ('out', None) for a screen point."""
        dx, dy = pos[0] - self.center[0], pos[1] - self.center[1]
        r = math.hypot(dx, dy)
        ang = math.degrees(math.atan2(dx, -dy)) % 360.0
        if r < INNER:
            return "hub", None
        if r <= OUTER:
            for i in range(len(self.slices)):
                if self._in(ang, *self._angles(i, len(self.slices))):
                    return "slice", i
        if r <= RING + 10 and self.sub is not None:
            for j in range(len(self.slices[self.sub].ring)):
                if self._in(ang, *self._sub_angles(j)):
                    return "ring", j
        return "out", None

    # ------------------------------------------------------------ input

    def move(self, pos: tuple[int, int]) -> None:
        where, i = self.locate(pos)
        if where == "slice":
            self.hover = i
            self.sub_hover = None
            self.sub = i if i is not None and self.slices[i].ring else None
        elif where == "ring":
            self.sub_hover = i
        else:
            self.hover = None if where == "hub" else self.hover
            self.sub_hover = None

    def chosen(self) -> Slice | None:
        """What a click now would run: the ring choice under the mouse, else the slice (unless it only opens a ring)."""
        if self.sub is not None and self.sub_hover is not None:
            return self.slices[self.sub].ring[self.sub_hover]
        if self.hover is not None and not self.slices[self.hover].ring:
            return self.slices[self.hover]
        return None

    def click(self, pos: tuple[int, int]) -> Slice | str | None:
        """A left click: the slice to run, 'stay' (it opened a ring), or None (outside: close)."""
        self.move(pos)
        where, _ = self.locate(pos)
        pick = self.chosen()
        if pick is not None:
            return pick
        if where in ("slice", "hub", "ring"):
            return "stay"
        return None

    def key(self, n: int) -> Slice | str | None:
        """Keys 1-8: that slice (or, with a ring open, that choice in it)."""
        if self.sub is not None and self.hover == self.sub and 0 <= n < len(self.slices[self.sub].ring):
            return self.slices[self.sub].ring[n]
        if 0 <= n < len(self.slices):
            s = self.slices[n]
            if s.ring:
                self.hover = self.sub = n
                return "stay"
            return s
        return None

    # ------------------------------------------------------------ drawing

    def draw(self, surf: pygame.Surface, preview: str | None, dt: float) -> None:
        self.age += dt
        k = min(1.0, self.age / OPEN_TIME)
        ease = 1 - (1 - k) ** 3
        cx, cy = self.center
        size = OUTER + (RING - OUTER if self.sub is not None else 0) + 20
        layer = gfx.Surface((size * 2, size * 2), pygame.SRCALPHA)
        o = (size, size)
        n = len(self.slices)
        r_out = INNER + (OUTER - INNER) * ease
        for i, s in enumerate(self.slices):
            a0, a1 = self._angles(i, n)
            col = STATION_COLOR.get(s.station or "", theme.FRIEND)
            hot = i == self.hover
            fillc = (*theme.mix(theme.BG_PANEL, col, 0.32 if hot else 0.06), int(236 * ease))
            _sector(layer, o, INNER, r_out, a0 + 1.2, a1 - 1.2, fillc)
            _arc(layer, o, r_out - 1, a0 + 1.2, a1 - 1.2, (*theme.mix(theme.BORDER, col, 0.9 if hot else 0.35), int(255 * ease)),
                 2 if hot else 1)
        if self.sub is not None:
            parent = self.slices[self.sub]
            col = STATION_COLOR.get(parent.station or "", theme.FRIEND)
            for j, _ in enumerate(parent.ring):
                a0, a1 = self._sub_angles(j)
                hot = j == self.sub_hover
                fillc = (*theme.mix(theme.BG_PANEL, col, 0.36 if hot else 0.1), 238)
                _sector(layer, o, OUTER + 4, RING, a0 + 1.0, a1 - 1.0, fillc)
                _arc(layer, o, RING - 1, a0 + 1.0, a1 - 1.0, (*theme.mix(theme.BORDER, col, 0.9 if hot else 0.4), 255),
                     2 if hot else 1)
        gfx.draw.circle(layer, (*theme.BG_PANEL_HI, int(240 * ease)), o, INNER - 3)
        gfx.draw.circle(layer, (*theme.BORDER_HI, int(255 * ease)), o, INNER - 3, 1)
        surf.blit(layer, (cx - size, cy - size))
        if k < 1.0:
            return
        for i, s in enumerate(self.slices):
            a0, a1 = self._angles(i, n)
            mid = math.radians((a0 + a1) / 2)
            rr = (INNER + OUTER) / 2 + 4
            px, py = cx + math.sin(mid) * rr, cy - math.cos(mid) * rr
            col = STATION_COLOR.get(s.station or "", theme.FRIEND)
            hot = i == self.hover
            if s.station:
                station_mark(surf, s.station, (px, py - 11), 5, col if hot else theme.dim(col, 0.75))
            label = s.label + (" ›" if s.ring else "")
            theme.text(surf, label, (px, py + 1), theme.TEXT if hot else theme.TEXT_DIM, 12,
                       weight="semibold" if hot else "medium", anchor="midtop")
            theme.text(surf, str(i + 1), (cx + math.sin(mid) * (OUTER - 10), cy - math.cos(mid) * (OUTER - 10)),
                       theme.TEXT_FAINT, 10, "mono", anchor="center")
        if self.sub is not None:
            for j, s in enumerate(self.slices[self.sub].ring):
                a0, a1 = self._sub_angles(j)
                mid = math.radians((a0 + a1) / 2)
                rr = (OUTER + RING) / 2 + 2
                px, py = cx + math.sin(mid) * rr, cy - math.cos(mid) * rr
                hot = j == self.sub_hover
                theme.text(surf, s.label, (px, py), theme.TEXT if hot else theme.TEXT_DIM, 12,
                           weight="semibold" if hot else "medium", anchor="center")
        theme.text(surf, _short(self.name), (cx, cy), theme.TEXT, 11, weight="semibold", anchor="center")
        if preview:
            msg = "› " + preview
            w = theme.text_width(msg, 12, "mono") + 20
            box = pygame.Rect(0, 0, w, 24)
            box.midtop = (cx, cy + size - 14)
            gfx.draw.rect(surf, theme.BG_INPUT, box, border_radius=4)
            gfx.draw.rect(surf, theme.BORDER_HI, box, 1, border_radius=4)
            theme.text(surf, msg, (box.x + 10, box.y + 4), theme.FRIEND, 12, "mono")


def _short(name: str) -> str:
    return name if len(name) <= 11 else name[:10] + "…"


def _sector(surf: pygame.Surface, o: tuple[int, int], r0: float, r1: float, a0: float, a1: float,
            col: tuple[int, int, int, int]) -> None:
    steps = max(3, int((a1 - a0) / 4))
    pts = []
    for k in range(steps + 1):
        a = math.radians(a0 + (a1 - a0) * k / steps)
        pts.append((o[0] + math.sin(a) * r1, o[1] - math.cos(a) * r1))
    for k in range(steps, -1, -1):
        a = math.radians(a0 + (a1 - a0) * k / steps)
        pts.append((o[0] + math.sin(a) * r0, o[1] - math.cos(a) * r0))
    gfx.draw.polygon(surf, col, pts)


def _arc(surf: pygame.Surface, o: tuple[int, int], r: float, a0: float, a1: float, col: tuple[int, int, int, int],
         width: int) -> None:
    steps = max(3, int((a1 - a0) / 4))
    pts = [(o[0] + math.sin(math.radians(a0 + (a1 - a0) * k / steps)) * r,
            o[1] - math.cos(math.radians(a0 + (a1 - a0) * k / steps)) * r) for k in range(steps + 1)]
    gfx.draw.lines(surf, col, False, pts, width)


__all__ = ["CommandWheel", "Slice", "WHEEL_FILE", "fill", "load_wheels"]
