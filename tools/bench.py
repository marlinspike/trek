"""Measure how fast the game draws and simulates: `python tools/bench.py [--size 2560x1440] [--profile]`.

Two measurements, both headless:

- frames: the real battle screen for a few presets, timing the update (input, simulation, officers)
  separately from drawing. 60 fps leaves 16.7 ms a frame for both.
- ticks: even AI-vs-AI fleets of growing size, timing one simulation tick plus one observation.

Timings depend on the machine, so compare runs on the same computer before and after a change.
`--profile` prints the costliest functions of the Fleet Action frame run.
"""

from __future__ import annotations

import argparse
import cProfile
import os
import pstats
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

FRAME_PRESETS = ("border-incident", "starbase-defense", "fleet-action")
FLEET_SIZES = (2, 7, 15, 30)       # ships a side; Begin's limit is 60 in all
FED = ("federation.hc", "federation.dn", "federation.de", "federation.in")
KLINGON = ("klingon.dr", "klingon.bc", "klingon.fr", "klingon.es")


def _summary(xs: list[float]) -> str:
    xs = sorted(xs)
    return f"mean {1000 * statistics.mean(xs):6.2f} ms   p95 {1000 * xs[int(0.95 * (len(xs) - 1))]:6.2f} ms"


def frames(size: tuple[int, int], n: int, profile: bool) -> None:
    from begin.presets import load_presets
    from begin.ui.app import App

    app = App(size=size, headless=True)
    presets = {p.id: p for p in load_presets()}
    print(f"Frames ({n} per preset, {size[0]}x{size[1]}, 1x speed)")
    for pid in FRAME_PRESETS:
        scene = app.start_battle(presets[pid].setup())
        scene.overlay = None
        scene.paused = False
        prof = cProfile.Profile() if profile and pid == "fleet-action" else None
        update: list[float] = []
        draw: list[float] = []
        if prof is not None:
            prof.enable()
        for _ in range(n):
            t0 = time.perf_counter()
            scene.update(1 / 60)
            t1 = time.perf_counter()
            scene.draw(app.screen)
            update.append(t1 - t0)
            draw.append(time.perf_counter() - t1)
            if scene.world.outcome.over:
                break
        if prof is not None:
            prof.disable()
        print(f"  {pid:18} {len(scene.world.ships):2} ships   update {_summary(update)}   draw {_summary(draw)}")
        scene.close()
        if prof is not None:
            pstats.Stats(prof).sort_stats("tottime").print_stats(20)


def ticks(n: int) -> None:
    from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle
    from begin.content import default_content

    content = default_content()
    print(f"Ticks (up to {n} per fleet size, AI on both sides)")
    for k in FLEET_SIZES:
        setup = BattleSetup([FleetSpec(0, [ShipSpec(FED[i % 4]) for i in range(k)], player=True, center=(0, -12000)),
                             FleetSpec(1, [ShipSpec(KLINGON[i % 4]) for i in range(k)], center=(0, 12000))], seed=3)
        world = build_battle(content, setup).world
        done = 0
        t = time.perf_counter()
        while done < n and not world.outcome.over:
            world.step()
            world.observe(0)
            done += 1
        print(f"  {2 * k:2} ships   {1000 * (time.perf_counter() - t) / max(1, done):6.2f} ms a tick")


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--size", default="1600x900", help="window size for the frame run")
    ap.add_argument("--frames", type=int, default=1200, help="frames per preset")
    ap.add_argument("--ticks", type=int, default=600, help="ticks per fleet size")
    ap.add_argument("--profile", action="store_true")
    args = ap.parse_args()
    w, h = (int(v) for v in args.size.lower().split("x"))
    frames((w, h), args.frames, args.profile)
    ticks(args.ticks)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
