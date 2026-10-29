"""Curated preset battles loaded from content/data/presets.toml."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

from .battle import BattleSetup, FleetSpec, ShipSpec

PRESETS_FILE = Path(__file__).resolve().parent / "content" / "data" / "presets.toml"


@dataclass(frozen=True)
class Preset:
    id: str
    title: str
    description: str
    seed: int
    fleets: tuple[dict, ...]  # type: ignore[type-arg]

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
                           description=self.description)


def load_presets(path: Path = PRESETS_FILE) -> list[Preset]:
    with open(path, "rb") as fh:
        data = tomllib.load(fh)
    return [Preset(p["id"], p["title"], p["description"], int(p["seed"]), tuple(p["fleets"])) for p in data["preset"]]


__all__ = ["Preset", "load_presets"]
