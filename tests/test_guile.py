"""The scripted captain of `--tour-test`'s "+guile" row beats a cube the way the manual teaches (2026-11-14)."""

from __future__ import annotations

from begin.battle import start
from begin.sim.ship import ShipStatus
from begin.tools.guile import GuileCaptain, fight
from begin.tools.tours import _default_escorts, _has_borg
from begin.tour import TourRun, load_tours


def _collective():  # type: ignore[no-untyped-def]
    return next(t for t in load_tours()[0] if t.id == "the-collective")


def test_guile_puts_the_cube_to_sleep_and_her_core_takes_her(content) -> None:  # type: ignore[no-untyped-def]
    t = _collective()
    won = 0
    for seed in (3, 8):                                       # fresh on the cube, the script wins about half
        run = TourRun.new(t, content, _default_escorts(t, content), seed=seed, difficulty="captain")
        run.state.stop = len(t.stops) - 1                     # straight to the cube, fresh
        fight_ = run.launch()
        battle = start(content, fight_.setup, run.difficulty)
        run.prepare(battle)
        assert GuileCaptain.wanted(battle)
        fight(battle, "spock", 400.0)
        w = battle.world
        cube = next(s for s in w.ships.values() if s.cls.id == "borg.cu")
        me = w.ships[battle.player_ship_id]
        won += cube.status == ShipStatus.DESTROYED and me.alive
    assert won == 2


def test_the_probes_and_spheres_are_left_to_the_officers_and_only_borg_tours_get_a_guile_row(content) -> None:  # type: ignore[no-untyped-def]
    t = _collective()
    run = TourRun.new(t, content, [], seed=1)
    battle = start(content, run.launch().setup, run.difficulty)
    assert not GuileCaptain.wanted(battle)                   # the first stop: probes only
    assert _has_borg(t, content)
    assert not _has_borg(next(x for x in load_tours()[0] if x.id == "border-patrol"), content)
