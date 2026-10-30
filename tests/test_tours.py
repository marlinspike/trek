"""Tours of duty: arrivals and waves, carry-over between stops, reinforcements, the log, saving, the screens."""

from __future__ import annotations

import os

import pytest

from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle
from begin.console.parser import parse, ParseContext
from begin.sim.arrivals import Arrival
from begin.sim.events import ShipArrived
from begin.sim.ship import ShipStatus
from begin.tour import TourRun, TourState, check_tour, load_tours
from begin.tour.log import markdown, read_markdown_edits, write_markdown
from begin.tour.model import parse_tour
from begin.tour.state import ShipRecord, refit, transit
from begin.tools.tours import play


def _tour(tid: str = "orion-run"):  # type: ignore[no-untyped-def]
    tours, problems = load_tours()
    assert not problems
    return next(t for t in tours if t.id == tid)


def _wreck(world, side: int) -> None:  # type: ignore[no-untyped-def]
    for s in world.ships.values():
        if s.side == side and s.alive:
            s.status = ShipStatus.DESTROYED


# ------------------------------------------------------------------ arrivals and waves

def _waves_setup() -> BattleSetup:
    return BattleSetup(
        [FleetSpec(0, [ShipSpec("federation.hc")], player=True, center=(0.0, -12000.0)),
         FleetSpec(1, [ShipSpec("klingon.fr")], center=(0.0, 12000.0))],
        seed=3,
        arrivals=[Arrival(1, ("klingon.fr",), after_clear=20.0, at_x=0, at_y=15000),
                  Arrival(1, ("klingon.es",), after_clear=30.0, at_x=5000, at_y=15000)])


def test_waves_come_in_order_after_a_lull_and_hold_the_battle_open(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, _waves_setup())
    w = b.world
    _wreck(w, 1)
    w.run(5.0)
    assert not w.outcome.over                             # two waves still to come
    assert not w.arrivals[0].arrived
    w.run(20.0)
    assert w.arrivals[0].arrived and not w.arrivals[1].arrived    # the second waits for the first to be beaten
    events = w.take_events()
    assert any(isinstance(e, ShipArrived) and e.kind == "wave" for e in events)
    new = w.ships[w.arrivals[0].ship_ids[0]]
    assert new.side == 1 and new.id in b.captains          # an AI captain takes her
    _wreck(w, 1)
    w.run(10.0)
    assert not w.arrivals[1].arrived                       # its own lull starts when the field is cleared again
    w.run(25.0)
    assert w.arrivals[1].arrived
    _wreck(w, 1)
    w.run(2.0)
    assert w.outcome.over and w.outcome.winner == 0


def test_an_arrival_by_the_clock_and_its_eta(content) -> None:  # type: ignore[no-untyped-def]
    setup = _waves_setup()
    setup.arrivals = [Arrival(0, ("federation.de",), kind="reinforcement", at=12.0, at_x=0, at_y=-20000, names=("Lexington",))]
    b = build_battle(content, setup)
    w = b.world
    assert w.arrivals[0].eta(w) == pytest.approx(12.0)
    w.run(13.0)
    a = w.arrivals[0]
    assert a.arrived and w.ships[a.ship_ids[0]].name == "Lexington" and w.ships[a.ship_ids[0]].side == 0


# ------------------------------------------------------------------ carry-over

def test_damage_crew_and_torpedoes_carry_to_the_next_stop(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, ["federation.de"], seed=5)
    fight = run.launch()
    b = build_battle(content, fight.setup)
    run.prepare(b)
    w = b.world
    flag = w.ships[fight.ship_ids[0]]
    flag.structure = flag.structure_max * 0.4
    flag.crew -= 100
    flag.torps_remaining = 3
    for t in flag.tubes:
        t.loaded = None
    sub = next(iter(flag.subsystems()))
    sub.damage = 80
    _wreck(w, 1)
    w.run(2.0)
    entry = run.finish(b)
    rec = run.state.flagship
    assert rec.hull == pytest.approx(0.4, abs=0.01)
    assert rec.crew == content.classes["federation.hc"].crew - 100
    assert rec.torps == 3 and rec.damage[sub.sid] == 80
    assert entry.outcome == "victory" and run.state.stop == 1
    # the next fight starts after the transit: repairs on the way, a supply ship, and her captain's damage as it was
    nxt = run.launch()
    b2 = build_battle(content, nxt.setup)
    run.prepare(b2)
    f2 = b2.world.ships[nxt.ship_ids[0]]
    assert 0.4 < f2.structure / f2.structure_max <= run.rules.hull_field_limit + 1e-6
    assert f2.crew == rec.crew and f2.torps_remaining > 3
    assert next(s for s in f2.subsystems() if s.sid == sub.sid).damage < 80


def test_transit_patches_to_the_field_limit_and_a_refit_does_the_rest(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, [], seed=1)
    rec = ShipRecord("federation.de", "Hood", hull=0.3, crew=150, torps=2, damage={"reactor1": 60})
    transit(rec, content, run.rules, 10000.0)
    assert rec.hull == pytest.approx(run.rules.hull_field_limit) and not rec.damage and rec.crew == 150
    refit(rec, content)
    assert rec.hull == 1.0 and rec.crew is None and rec.torps is None


def test_a_lost_ship_stays_lost_and_losing_the_flagship_ends_the_tour(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, ["federation.in"], seed=2)
    fight = run.launch()
    b = build_battle(content, fight.setup)
    run.prepare(b)
    _wreck(b.world, 0)
    b.world.run(2.0)
    entry = run.finish(b)
    assert entry.outcome == "lost" and run.state.over == "lost"
    assert all(r.lost and r.lost_at == "convoy" for r in run.state.squadron)
    assert "has been lost" in entry.captain


# ------------------------------------------------------------------ reinforcements

def test_starfleet_answers_a_call_in_battle_and_the_ship_joins_the_squadron(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, [], seed=4)
    fight = run.launch()
    b = build_battle(content, fight.setup)
    run.prepare(b)
    w = b.world
    calls = run.state.calls_left
    a, msg = run.reinforcement_arrival(b, w.ships[b.player_ship_id])
    assert a is not None and "ETA" in msg and run.state.calls_left == calls - 1
    assert a.at is not None and a.at >= fight.stop.eta * 0.85 - 1e-6
    while not a.arrived:
        w.step()
    assert w.ships[a.ship_ids[0]].side == w.player_side
    _wreck(w, 1)
    w.run(2.0)
    run.finish(b)
    joined = [r for r in run.state.squadron if r.role == "reinforcement"]
    assert len(joined) == 1 and joined[0].joined == "convoy"
    a2, msg2 = run.reinforcement_arrival(b, None)
    assert a2 is None


def test_a_call_from_the_ready_room_meets_us_at_the_stop(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, [], seed=4)
    msg = run.request_from_ready_room()
    assert "Starfleet is sending" in msg and run.state.pending
    fight = run.launch()
    stop = fight.stop
    late = stop.eta - run.transit_cycles()
    mine = fight.setup.fleets[0]
    if late <= 0:
        assert len(mine.ships) == 2
    else:
        assert any(a.tag == "starfleet" and a.at == pytest.approx(late) for a in fight.setup.arrivals)
    assert not run.state.pending


def test_request_reinforcements_parses_without_stealing_reinforce(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, _waves_setup())
    ctx = ParseContext(b.player_ship_id, b.world.observe(0))
    assert parse("request reinforcements", ctx).actions == [("reinforcements", None)]
    assert parse("reinforcements", ctx).actions == [("reinforcements", None)]
    assert parse("reinforce 1", ctx).commands and not parse("reinforce 1", ctx).actions


# ------------------------------------------------------------------ whole tours, saving, the log

def test_a_whole_tour_plays_to_its_end_with_a_page_of_log_for_every_stop(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, ["federation.de"], seed=1)
    play(run)
    st = run.state
    assert st.over in ("won", "lost")
    assert len(st.log) == len(st.results) >= 1
    e = st.log[0]
    assert set(e.stations) == {"spock", "worf", "geordi", "seven"} and e.captain.startswith("Captain's log, stardate")
    grade, lines = run.rating()
    assert grade and len(lines) == 5


def test_save_load_and_the_markdown_log_round_trip(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, ["federation.in"], seed=1)
    play(run)
    run.state.save(tmp_path)
    back = TourState.load(tmp_path, run.tour.id)
    assert back is not None and back.to_json() == run.state.to_json()
    write_markdown(run, tmp_path)
    md = (tmp_path / f"{run.tour.id}-log.md").read_text()
    assert md == markdown(run)
    first = run.state.log[0]
    md = md.replace(first.captain, "We did well today. I'll say no more.")
    (tmp_path / f"{run.tour.id}-log.md").write_text(md)
    assert read_markdown_edits(back, tmp_path) == 1
    assert back.log[0].captain == "We did well today. I'll say no more." and back.log[0].edited


def test_a_tour_of_your_own_replaces_a_shipped_one_and_bad_ones_are_reported(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    (tmp_path / "mine.toml").write_text('''
[[tour]]
id = "orion-run"
title = "My Orion Run"
flagship = "federation.hc"
[[tour.stop]]
id = "one"
title = "One"
enemies = ["orion.ra"]

[[tour]]
id = "broken"
title = "Broken"
flagship = "federation.hc"
[[tour.stop]]
id = "x"
title = "X"
enemies = ["klingon.nonesuch"]
''')
    (tmp_path / "bad.toml").write_text("this is not toml = = =")
    tours, problems = load_tours(tmp_path)
    by_id = {t.id: t for t in tours}
    assert by_id["orion-run"].title == "My Orion Run" and by_id["orion-run"].source == "mine.toml"
    assert any("bad.toml" in p for p in problems)
    assert check_tour(by_id["broken"], set(content.classes)) == ["Broken: unknown ship class 'klingon.nonesuch'"]


def test_shipped_tours_name_only_real_ships(content) -> None:  # type: ignore[no-untyped-def]
    tours, problems = load_tours()
    assert not problems and len(tours) >= 3
    for t in tours:
        assert check_tour(t, set(content.classes)) == []
        assert TourRun.budget_left(t, content, []) == t.budget


def test_choices_waves_and_flags(content) -> None:  # type: ignore[no-untyped-def]
    t = parse_tour({"id": "t", "title": "T", "flagship": "federation.hc", "stop": [{
        "id": "s", "title": "S", "enemies": ["klingon.fr"], "add": {"refit": ["klingon.bc"]},
        "choice": [{"label": "Refit", "refit": True, "transit": 300, "flags": ["refit"]}, {"label": "Go"}],
        "wave": [{"ships": ["klingon.dr"], "after_clear": 60, "unless_flag": "beaten"},
                 {"ships": ["klingon.bc"], "after_clear": 60, "if_flag": "beaten"}]}]})
    run = TourRun.new(t, content, [], seed=1)
    assert run.needs_choice()
    run.state.flagship.hull = 0.5
    run.choose(0)
    assert run.transit_cycles() == 300 and run.projected()[0].hull == 1.0
    fight = run.launch()
    assert [s.class_id for s in fight.setup.fleets[-1].ships] == ["klingon.fr", "klingon.bc"]
    assert [a.ships for a in fight.setup.arrivals] == [("klingon.dr",)]
    assert run.state.flags == ["refit"]


# ------------------------------------------------------------------ the AI at a starbase

def test_a_badly_hurt_ai_ship_docks_at_its_base_between_waves(content) -> None:  # type: ignore[no-untyped-def]
    setup = BattleSetup(
        [FleetSpec(0, [ShipSpec("federation.hc"), ShipSpec("federation.de")], player=True, center=(0.0, -6000.0)),
         FleetSpec(0, [ShipSpec("federation.sb")], center=(0.0, -4000.0)),
         FleetSpec(1, [ShipSpec("klingon.fr")], center=(0.0, 30000.0))],
        seed=9, arrivals=[Arrival(1, ("klingon.bc",), after_clear=200.0, at_x=0, at_y=30000)])
    b = build_battle(content, setup)
    w = b.world
    de = next(s for s in w.ships.values() if s.cls.id == "federation.de")
    de.structure = de.structure_max * 0.3
    _wreck(w, 1)
    for _ in range(int(150 * w.rules.ticks_per_cycle)):
        w.step()
        if de.docked_to is not None:
            break
    assert de.docked_to is not None


# ------------------------------------------------------------------ the screens

@pytest.fixture()
def screen():  # type: ignore[no-untyped-def]
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame = pytest.importorskip("pygame")
    pygame.init()
    from begin.ui import theme

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    return pygame.display.set_mode((1440, 860))


class _Writer:
    """A stand-in language model: every officer writes 'In my own words.'"""
    name = "fake"

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        return "In my own words."


def test_the_tour_screens_from_the_list_to_the_end(content, screen) -> None:  # type: ignore[no-untyped-def]
    import pygame

    from begin.llm.service import LLMService
    from begin.ui.settings import Settings
    from begin.ui.tour_scene import TourScene, tours_dir

    launched: list[TourRun] = []
    ts = TourScene(content, Settings(), launched.append, lambda: None)
    ts.open()
    ts.tour_i = next(i for i, t in enumerate(ts.tours) if t.id == "orion-run")
    for page in ("tours", "squadron"):
        ts.page = page
        ts.update(0.1)
        ts.draw(screen)
    ts.escorts = ["federation.de"]
    ts.commission()
    assert ts.page == "ready" and (tours_dir() / "orion-run.json").is_file()
    ts._reinforce()
    assert ts.run is not None and ts.run.state.pending and "Starfleet" in ts.note
    ts.update(0.1)
    ts.draw(screen)
    ts._launch()
    assert launched == [ts.run]
    run = ts.run
    fight = run.launch()           # what the app does with the launch
    b = build_battle(content, fight.setup)
    run.prepare(b)
    _wreck(b.world, 1)
    b.world.run(2.0)
    run.finish(b)
    ts.voices = LLMService(_Writer(), workers=1)
    ts.after_battle(run)
    assert ts.page == "log" and ts.writing()
    # you rewrite your entry while the officers are still writing theirs: yours is kept
    ts._start_edit()
    ts.edit_buf = "A short engagement. The crew did well."
    ts.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_RETURN, mod=0))
    for _ in range(200):
        ts.update(0.02)
        if not ts.writing():
            break
        import time

        time.sleep(0.01)
    e = run.state.log[-1]
    assert e.edited and e.captain == "A short engagement. The crew did well."
    assert e.stations["spock"] == "In my own words." and "spock" in e.voiced and "captain" not in e.voiced
    md = (tours_dir() / "orion-run-log.md").read_text()
    assert "A short engagement. The crew did well." in md and "In my own words." in md
    ts.draw(screen)
    ts.page = "ready"
    ts.draw(screen)
    run.state.over = "won"
    ts.page = "end"
    ts.draw(screen)
    # and it is there to continue the next time
    ts2 = TourScene(content, Settings(), launched.append, lambda: None)
    state = ts2.saved(run.tour)
    assert state is not None and state.log[-1].edited
