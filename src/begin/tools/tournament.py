"""Headless AI-vs-AI quick battles for balance checks: `begin --tournament N`."""

from __future__ import annotations

import time
from collections import Counter

from ..battle import BattleSetup, FleetSpec, ShipSpec, build_battle
from ..content import default_content
from ..core.rng import Rng


def run_tournament(n: int, cycles: float = 600.0, seed: int = 1) -> dict[str, int]:
    content = default_content()
    rng = Rng(seed)
    factions = list(content.factions)
    wins: Counter[str] = Counter()
    games: Counter[str] = Counter()
    t0 = time.perf_counter()
    ticks = 0
    for i in range(n):
        fa, fb = rng.choice(factions), rng.choice(factions)
        while fb == fa:
            fb = rng.choice(factions)
        ca = rng.choice([c for c in content.classes_of(fa, include_bases=False) if c.banks > 0])
        cb = rng.choice([c for c in content.classes_of(fb, include_bases=False) if c.banks > 0])
        setup = BattleSetup([FleetSpec(0, [ShipSpec(ca.id)]), FleetSpec(1, [ShipSpec(cb.id)])], seed=seed * 1000 + i)
        b = build_battle(content, setup)
        b.world.run(cycles)
        ticks += b.world.tick
        games[ca.id] += 1
        games[cb.id] += 1
        o = b.world.outcome
        result = "draw"
        if o.over and o.winner is not None:
            win = ca.id if o.winner == 0 else cb.id
            wins[win] += 1
            result = win
        print(f"{i + 1:3d}. {ca.id:15s} vs {cb.id:15s} → {result:15s} ({b.world.time:.0f} cycles)")
    dt = time.perf_counter() - t0
    print(f"\n{n} battles, {ticks} ticks in {dt:.1f}s ({dt / max(1, ticks) * 1e6:.0f} µs/tick)")
    for cid in sorted(games, key=lambda c: -wins[c] / games[c]):
        print(f"  {cid:15s} {wins[cid]:3d}/{games[cid]:<3d} wins")
    return dict(wins)


__all__ = ["run_tournament"]
