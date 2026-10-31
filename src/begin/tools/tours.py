"""Headless tours: `begin --tour-test N` plays every tour N times with AI captains on every ship.

The player's flagship is flown by its officers (Spock has the conn), every choice takes the first
option, and one reinforcement is called in the finale. It measures the tours, not the player.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from ..battle import build_battle
from ..content import default_content
from ..sim.commands import TakeConn
from ..tour import TourRun, check_tour, load_tours

MAX_CYCLES = 1500.0


@dataclass
class TourResult:
    tour: str
    won: int = 0
    lost: int = 0
    stops: list[int] = field(default_factory=list)       # stops won in each run
    bases_held: int = 0

    def line(self) -> str:
        n = self.won + self.lost
        avg = sum(self.stops) / max(1, len(self.stops))
        return f"{self.tour:16s} tours won {self.won:2d}/{n:<2d}  average stops won {avg:4.1f}  finale bases held {self.bases_held}"


def play(run: TourRun, officer: str = "spock", call: bool = True) -> None:
    """Fight every stop of the tour until it is won or lost."""
    while not run.over:
        if run.needs_choice():
            run.choose(0)
        fight = run.launch()
        battle = build_battle(run.content, fight.setup)
        run.prepare(battle)
        w = battle.world
        me = battle.player_ship_id
        if me is not None:
            w.execute(TakeConn(ship_id=me, officer=officer))
        if call and fight.stop.finale and run.state.calls_left > 0:
            run.reinforcement_arrival(battle, w.ships.get(me) if me is not None else None)
        limit = int(MAX_CYCLES * w.rules.ticks_per_cycle)
        while w.tick < limit and not w.outcome.over:
            w.step()
        if not w.outcome.over:
            w.end_simulation("The engagement was broken off.")
        run.finish(battle)


def run_tours(n: int, officer: str = "spock") -> list[TourResult]:
    content = default_content()
    tours, problems = load_tours()
    for p in problems:
        print("problem:", p)
    out = []
    t0 = time.perf_counter()
    for tour in tours:
        for p in check_tour(tour, set(content.classes)):
            print("problem:", p)
        r = TourResult(tour.id)
        for seed in range(1, n + 1):
            escorts = _default_escorts(tour, content)
            run = TourRun.new(tour, content, escorts, seed=seed)
            play(run, officer)
            r.won += run.state.over == "won"
            r.lost += run.state.over != "won"
            r.stops.append(sum(1 for x in run.state.results if x.outcome == "victory"))
            r.bases_held += bool(run.state.results) and run.state.results[-1].outcome == "victory" and \
                tour.stops[-1].finale and len(run.state.results) == len(tour.stops)
        print(r.line(), flush=True)
        out.append(r)
    print(f"\n{sum(x.won + x.lost for x in out)} tours in {time.perf_counter() - t0:.0f}s")
    return out


def _default_escorts(tour, content) -> list[str]:  # type: ignore[no-untyped-def]
    """What a sensible captain picks: the biggest escorts that fit the budget."""
    from ..tour.state import fleet_cost

    options = sorted((c for c in content.classes_of(tour.faction, include_bases=False) if c.banks > 0),
                     key=lambda c: -c.mass)
    left = tour.budget
    out: list[str] = []
    for c in options:
        while fleet_cost(c.id, content) <= left and len(out) < 3:
            out.append(c.id)
            left -= fleet_cost(c.id, content)
    return out


__all__ = ["TourResult", "play", "run_tours"]
