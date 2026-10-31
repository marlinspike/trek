"""Entry point: `python -m begin` (or the `begin` script).

Extra options exist for development and testing:
  --preset ID            jump straight into a preset battle
  --quick SEED           jump into a seeded quick battle
  --screenshot PATH      render headlessly after --cycles of simulated time and save a PNG
  --tournament N         run N headless AI-vs-AI quick battles and print a summary
  --balance N            fight every preset N times, AI on both sides, and print win rates
  --tour-test N          fly every tour of duty N times with the officers in command, and print how they went
  --llm KEY=VALUE ...    save the officers' language model settings (e.g. provider=ollama model=lfm3 think=off)
  --llm-test             ask Spock one question through the configured model and print the answer
  --llm-usage            print the language model's token totals (with log_tokens=on)
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="begin", description="Begin: a tactical starship simulation (remake)")
    ap.add_argument("--preset")
    ap.add_argument("--quick", type=int)
    ap.add_argument("--size", default=None, help="window size, e.g. 1600x900")
    ap.add_argument("--screenshot")
    ap.add_argument("--cycles", type=float, default=0.0)
    ap.add_argument("--overlay", default=None, help="for screenshots: help, damage, scan, debrief, manual[:<topic>], fleet[:<ally>], crew")
    ap.add_argument("--console", default=None, help="for screenshots: console commands separated by ';' ('@5' runs 5 cycles)")
    ap.add_argument("--zoom", type=float, default=None, help="for screenshots: map zoom (pixels per unit)")
    ap.add_argument("--tournament", type=int)
    ap.add_argument("--balance", type=int)
    ap.add_argument("--tour-test", type=int, metavar="N")
    ap.add_argument("--llm", nargs="+", metavar="KEY=VALUE")
    ap.add_argument("--llm-test", nargs="?", const="Spock, what do you recommend?", metavar="QUESTION")
    ap.add_argument("--llm-usage", action="store_true")
    args = ap.parse_args(argv)

    if args.llm_usage:
        from .tools.llm import usage

        return usage()

    if args.llm or args.llm_test:
        from .tools.llm import configure, test
        from .llm.providers.base import LLMError

        try:
            if args.llm:
                configure(args.llm)
            return test(args.llm_test) if args.llm_test else 0
        except LLMError as e:
            print(e, file=sys.stderr)
            return 2

    if args.balance:
        from .tools.balance import run_balance

        run_balance(args.balance)
        return 0

    if args.tour_test:
        from .tools.tours import run_tours

        run_tours(args.tour_test)
        return 0

    if args.tournament:
        from .tools.tournament import run_tournament

        run_tournament(args.tournament)
        return 0

    size = None
    if args.size:
        w, h = args.size.lower().split("x")
        size = (int(w), int(h))

    from .ui.app import App

    app = App(size=size, headless=bool(args.screenshot))
    scene = None
    if args.preset:
        from .presets import load_presets

        match = [p for p in load_presets() if p.id == args.preset]
        if not match:
            print(f"Unknown preset '{args.preset}'.", file=sys.stderr)
            return 2
        scene = app.start_battle(match[0].setup())
    elif args.quick is not None:
        from .battle import quick_battle

        scene = app.start_battle(quick_battle(app.content, args.quick))

    if args.screenshot:
        import pygame

        if scene is not None:
            scene.overlay = None
            for cmd in (args.console or "").split(";"):
                cmd = cmd.strip()
                if cmd.startswith("@"):  # '@5' lets 5 cycles pass before the next command
                    scene.paused = False
                    for _ in range(int(float(cmd[1:]) * 60)):
                        scene.update(1 / 60)
                elif cmd:
                    scene.run_console(cmd)
            scene.paused = False
            steps = int(args.cycles * 60)
            for _ in range(steps):
                scene.update(1 / 60)
            scene.paused = True if args.cycles <= 0 else scene.paused
            if args.overlay and args.overlay.startswith("manual"):
                scene.open_manual(args.overlay.partition(":")[2] or None)
            elif args.overlay and args.overlay.startswith("fleet"):
                allies = scene.allies()
                want = args.overlay.partition(":")[2].lower()
                pick = next((a for a in allies if a.name.lower().startswith(want)), allies[0] if allies else None)
                if pick is not None:
                    scene.select_ally(pick.id)
            elif args.overlay == "crew":
                from .ui.hud import CrewPanel

                scene.side_tabs.show(CrewPanel)
            elif args.overlay:
                scene.overlay = args.overlay
            if args.zoom:
                scene.cam.zoom = args.zoom
        app.scene.update(0.0)
        app.scene.draw(app.screen)
        pygame.image.save(app.screen, args.screenshot)
        print(f"saved {args.screenshot}")
        return 0

    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
