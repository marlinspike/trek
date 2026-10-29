"""Balance runs over the curated presets: `begin --balance N`.

Every preset is fought N times with different seeds. The player's ship gets an
AI captain like everyone else, so the numbers measure the scenario, not the
player. A battle that is still going after `max_cycles` counts as a stalemate.
"""

from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass, field

from ..ai.captain import AICaptain
from ..ai.personality import Personality
from ..battle import build_battle
from ..content import default_content
from ..presets import load_presets


@dataclass
class PresetResult:
    preset: str
    wins: int = 0          # the player's side won
    losses: int = 0
    stalemates: int = 0
    cycles: list[float] = field(default_factory=list)

    @property
    def games(self) -> int:
        return self.wins + self.losses + self.stalemates

    def line(self) -> str:
        avg = sum(self.cycles) / max(1, len(self.cycles))
        return (f"{self.preset:20s} player wins {self.wins:2d}/{self.games:<2d}  losses {self.losses:2d}  "
                f"stalemates {self.stalemates:2d}  avg {avg:5.0f} cycles")


def run_preset(preset_id: str, seed: int, max_cycles: float = 1500.0) -> tuple[str, float]:
    """One battle; returns ('win' | 'loss' | 'stalemate', cycles fought) from the player's side."""
    content = default_content()
    preset = next(p for p in load_presets() if p.id == preset_id)
    setup = dataclasses.replace(preset.setup(), seed=seed)
    b = build_battle(content, setup)
    w = b.world
    me = b.player_ship_id
    assert me is not None
    ship = w.ships[me]
    prng = w.rng.derive(f"captain:{me}")
    w.add_controller(AICaptain(me, ship.side, Personality.roll(content.factions[ship.faction], prng), prng,
                               phase=me % 2))
    limit = int(max_cycles * w.rules.ticks_per_cycle)
    while w.tick < limit and not w.outcome.over:
        w.step()
    if not w.outcome.over:
        return "stalemate", w.time
    return ("win" if w.outcome.winner == ship.side else "loss"), w.time


def run_balance(n: int, presets: list[str] | None = None, max_cycles: float = 1500.0) -> list[PresetResult]:
    ids = presets or [p.id for p in load_presets()]
    out: list[PresetResult] = []
    t0 = time.perf_counter()
    for pid in ids:
        r = PresetResult(pid)
        for seed in range(1, n + 1):
            result, cycles = run_preset(pid, seed, max_cycles)
            r.cycles.append(cycles)
            if result == "win":
                r.wins += 1
            elif result == "loss":
                r.losses += 1
            else:
                r.stalemates += 1
        print(r.line(), flush=True)
        out.append(r)
    print(f"\n{sum(r.games for r in out)} battles in {time.perf_counter() - t0:.0f}s")
    return out


__all__ = ["PresetResult", "run_balance", "run_preset"]
