"""The Borg on the map [E]: how far a hive ship has adapted to our weapons, a ship gone dark with her relay
cut, the system her relay runs through once Seven has found it, and a core going critical.

Drawing only: `hive_mark` reads what our side knows from the `Observation`; `tactical.py` places it.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

import pygame

from ..sim.observation import Observation
from . import gfx, theme

ADAPT_SHOWN = 0.05          # adaptation below this isn't worth a mark
CRITICAL_FILL_PX = 420      # a blast reach wider than this on screen is drawn as a ring only
CRITICAL_LABEL_PX = 40      # the countdown sits this far below the ship


@dataclass(frozen=True)
class HiveMark:
    phaser: float           # 0..1: how far her hive has learned our phasers (the frequency we fire now)
    torpedo: float          # ... and our torpedoes
    dormant: float          # cycles before her drones wake (0: awake)
    relay: str              # the system her vinculum relay runs through, once we know it ("" until then)


def hive_mark(obs: Observation, cid: int, me: int | None) -> HiveMark | None:
    """What our side knows of one Borg contact, or None if she isn't one (or we can't tell yet)."""
    if not obs.is_hive(cid):
        return None
    adapt = obs.adaptation(cid, me) if me is not None else {}
    relay = obs.weak_point(cid) or ""
    stem = relay.rstrip("0123456789")
    return HiveMark(adapt.get("phaser", 0.0), adapt.get("torpedo", 0.0), obs.dormant(cid),
                    f"{stem} {relay[len(stem):]}".strip() if relay else "")


def adaptation_rings(overlay: pygame.Surface, sx: float, sy: float, rad: float, m: HiveMark, clock: float) -> None:
    """Two thin green arcs round her, sweeping clockwise from the bow as the hive learns: the outer one our
    phasers, the inner our torpedoes. A full ring is a weapon she shrugs off. The arcs creep as they grow."""
    if m.dormant > 0:
        return
    for k, (frac, width) in enumerate(((m.phaser, 2), (m.torpedo, 1))):
        if frac < ADAPT_SHOWN:
            continue
        r = rad + 8 - k * 5
        box = pygame.Rect(0, 0, int(r * 2), int(r * 2))
        box.center = (int(sx), int(sy))
        glow = 0.75 + 0.25 * math.sin(clock * (1.0 + 2.0 * frac))
        hot = theme.mix(theme.HIVE, (255, 255, 255), 0.35 * max(0.0, frac - 0.6) / 0.4)
        top = math.pi / 2
        gfx.draw.arc(overlay, (*theme.HIVE, 26), box, 0, math.tau, 1)
        gfx.draw.arc(overlay, (*hot, int(170 * glow)), box, top - math.tau * min(1.0, frac), top, width)


def dormant_veil(overlay: pygame.Surface, sx: float, sy: float, rad: float, left: float, clock: float) -> None:
    """A ship gone dark: a slow dim breath of green over her, the hive's light failing, a little faster as she
    nears waking."""
    beat = 0.5 + 0.5 * math.sin(clock * (1.0 + 4.0 / max(1.0, left)))
    gfx.draw.circle(overlay, (*theme.BG, 110), (int(sx), int(sy)), int(rad * 0.9))
    gfx.draw.circle(overlay, (*theme.HIVE, int(18 + 22 * beat)), (int(sx), int(sy)), int(rad + 4), 1)


def critical_ring(surf: pygame.Surface, overlay: pygame.Surface, sx: float, sy: float, reach: float, left: float,
                  clock: float, label: str) -> None:
    """A ship about to go up: the reach of the blast, pulsing faster as the moment comes, and the time left."""
    rate = 2.0 + 10.0 / max(0.5, left)
    beat = 0.5 + 0.5 * math.sin(clock * rate)
    if 6 < reach < 6000:
        if reach < CRITICAL_FILL_PX:          # a wash of red only where it doesn't cover the whole map
            gfx.draw.circle(overlay, (*theme.ALERT, int(12 + 20 * beat)), (int(sx), int(sy)), int(reach))
        gfx.draw.circle(overlay, (*theme.ALERT, int(120 + 100 * beat)), (int(sx), int(sy)), int(reach), 2)
    theme.text(surf, f"{label}  {left:.1f}", (sx, sy + CRITICAL_LABEL_PX), theme.mix(theme.ALERT, (255, 255, 255),
               0.3 * beat), 12, weight="semibold", anchor="midtop")


__all__ = ["HiveMark", "adaptation_rings", "critical_ring", "dormant_veil", "hive_mark"]
