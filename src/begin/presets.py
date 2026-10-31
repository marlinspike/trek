"""Curated preset battles loaded from content/data/presets.toml."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from .battle import BattleSetup, FleetSpec, ShipSpec
from .sim.arrivals import Arrival

PRESETS_FILE = Path(__file__).resolve().parent / "content" / "data" / "presets.toml"


@dataclass(frozen=True)
class Preset:
    id: str
    title: str
    description: str
    seed: int
    fleets: tuple[dict, ...]  # type: ignore[type-arg]
    waves: tuple[dict, ...] = ()  # type: ignore[type-arg]

    def setup(self, seed: int | None = None) -> BattleSetup:
        fleets = []
        for f in self.fleets:
            center = f.get("center")
            fleets.append(FleetSpec(
                side=int(f["side"]), player=bool(f.get("player", False)),
                center=(float(center[0]), float(center[1])) if center else None,
                ships=[ShipSpec(cid) for cid in f["ships"]],
            ))
        return BattleSetup(fleets, seed=self.seed if seed is None else seed, title=self.title,
                           description=self.description, arrivals=[wave_arrival(w) for w in self.waves])


def wave_arrival(w: dict) -> Arrival:  # type: ignore[type-arg]
    """A later wave from its TOML table: side, ships, and when (`at`, `after_clear`) and where (`center`) it arrives."""
    cx, cy = (float(v) for v in w.get("center", (0.0, 16000.0)))
    heading = float(w["heading"]) if "heading" in w else math.degrees(math.atan2(-cx, -cy)) % 360.0
    return Arrival(side=int(w.get("side", 1)), ships=tuple(w["ships"]), kind=str(w.get("kind", "wave")),
                   at=float(w["at"]) if "at" in w else None,
                   after_clear=float(w["after_clear"]) if "after_clear" in w else None,
                   at_x=cx, at_y=cy, heading=heading, message=str(w.get("message", "")))


def load_presets(path: Path = PRESETS_FILE) -> list[Preset]:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    return [Preset(p["id"], p["title"], p["description"], int(p["seed"]), tuple(p["fleets"]), tuple(p.get("waves", ())))
            for p in data["preset"]]


__all__ = ["Preset", "load_presets", "wave_arrival"]
