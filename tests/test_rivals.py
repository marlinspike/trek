"""Returning enemy captains (tour/rivals.py) [E]: the ones who got away come back, sharper, and remember us."""

from __future__ import annotations

import os

import pytest

from begin.battle import build_battle
from begin.crew.career import Career
from begin.sim.events import Message
from begin.sim.ship import ShipStatus
from begin.tour import TourRun, load_tours
from begin.tour.generate import generate_tour
from begin.tour.rivals import COMPETENCE, SHARPER, TOP, Rival, RivalBook, personality


def _tour(tid: str = "border-patrol"):  # type: ignore[no-untyped-def]
    return next(t for t in load_tours()[0] if t.id == tid)


def _kor(**kw) -> Rival:  # type: ignore[no-untyped-def]
    d = {"name": "Kor", "faction": "klingon", "ship_class": "klingon.bc", "ship_name": "Klothos", "place": "Archanis IV",
         "tour": "Border Patrol"}
    d.update(kw)
    return Rival(**d)


def test_rivals_are_kept_in_the_career_and_bad_entries_are_skipped() -> None:
    store: dict[str, object] = {"rivals": [{"name": "Kor", "faction": "klingon", "ship_class": "klingon.bc",
                                            "ship_name": "Klothos"}, {"nonsense": 1}]}
    book = RivalBook(Career(store))
    assert [r.name for r in book.rivals] == ["Kor"]
    book.rivals[0].met = 3
    book.save()
    assert RivalBook(Career(store)).rivals[0].met == 3


def test_they_get_sharper_every_time_we_meet() -> None:
    assert _kor(met=1).competence() == pytest.approx(COMPETENCE + SHARPER)
    assert _kor(met=40).competence() == TOP
    assert personality(_kor(met=2))["competence"] == pytest.approx(COMPETENCE + 2 * SHARPER)


def test_the_rival_who_returns_is_from_the_navy_we_face_and_still_free(content) -> None:  # type: ignore[no-untyped-def]
    book = RivalBook(Career({}))
    klingon_stop = next(s for s in _tour().stops if s.id == "border")        # a Klingon battle cruiser and escorts
    assert book.for_stop(klingon_stop, content, set()) is None
    book.rivals += [_kor(), _kor(name="Kang", met=3), _kor(name="Koloth", met=5, fate="destroyed"),
                    Rival("Tomalak", "romulan", "romulan.bp", "Decius")]
    assert book.for_stop(klingon_stop, content, set()).name == "Kang"      # the one we know best, and alive


@pytest.mark.parametrize("trust,speaker,words", [
    (0.0, "Computer", "a captain we have fought before"),
    (12.0, "Worf", "We fought them twice, last at Archanis IV."),
    (35.0, "Worf", "Last time they broke off and ran when the fight turned."),
])
def test_what_the_bridge_knows_of_them_rides_on_trust(trust: float, speaker: str, words: str) -> None:
    career = Career({"trust": {"worf": trust}})
    who, said = RivalBook(career).recognition(_kor(met=2))
    assert who == speaker and words in said
    if trust < 30:
        assert "Last time" not in said


def _fight(content, run):  # type: ignore[no-untyped-def]
    fight = run.launch()
    battle = build_battle(content, fight.setup)
    run.prepare(battle)
    return fight, battle


def test_a_rival_takes_the_heaviest_ship_hails_us_and_the_bridge_knows_them(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, [], seed=2)
    run.state.stop = 1                                                     # the Klingon on the border
    run.rivals = RivalBook(Career({"trust": {"worf": 35.0}}))
    run.rivals.rivals.append(_kor(met=1))
    title, text = run.briefing()
    assert "Kor commands the Klingon flagship here: we meet again." in text
    fight, battle = _fight(content, run)
    w = battle.world
    enemies = [s for s in w.ships.values() if s.side != w.player_side]
    heaviest = max(enemies, key=lambda s: s.cls.mass)
    assert fight.rival is not None and heaviest.captain == "Kor"
    said = [e for e in w.events if isinstance(e, Message)]
    assert any(e.speaker == f"Kor, {heaviest.name}" and "Archanis IV" in e.text for e in said)
    assert any(e.speaker == "Worf" and "broke off and ran" in e.text for e in said)


def test_a_generated_boss_is_the_rival_when_there_is_one(content) -> None:  # type: ignore[no-untyped-def]
    tour = generate_tour(content, 5)
    boss = tour.stops[-1]
    faction = content.classes[boss.enemies[0]].faction
    run = TourRun.new(tour, content, [], seed=1)
    run.state.stop = len(tour.stops) - 1
    run.rivals = RivalBook(Career({}))
    title, text = run.briefing()
    assert boss.commander and boss.commander in title and boss.commander in text
    run.rivals.rivals.append(Rival("Velar", faction, boss.enemies[0], "Vengeance"))
    title, text = run.briefing()
    assert "Velar" in title and boss.commander not in text
    fight, battle = _fight(content, run)
    assert battle.world.ships[next(s.id for s in battle.world.ships.values() if s.captain == "Velar")].cls.id == boss.enemies[0]


def test_the_stops_named_commander_captains_the_heaviest_ship(content) -> None:  # type: ignore[no-untyped-def]
    tour = generate_tour(content, 5)
    run = TourRun.new(tour, content, [], seed=1)
    run.state.stop = len(tour.stops) - 1
    _, battle = _fight(content, run)
    assert any(s.captain == tour.stops[-1].commander for s in battle.world.ships.values())


def test_a_commander_who_gets_away_becomes_a_rival_and_one_destroyed_is_done(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, [], seed=2)
    run.state.stop = 1
    book = run.rivals = RivalBook(Career({}))
    fight, battle = _fight(content, run)
    w = battle.world
    boss = max((s for s in w.ships.values() if s.side != w.player_side), key=lambda s: s.cls.mass)
    boss.status = ShipStatus.ESCAPED
    news = book.after_battle(battle, "Archanis IV", "Border Patrol", None)
    assert boss.captain in news and "got away" in news
    rival = book.find(boss.captain, "klingon")
    assert rival is not None and rival.habit == "escaped" and rival.at_large

    # they come back, and this time we finish it
    run2 = TourRun.new(_tour(), content, [], seed=3)
    run2.state.stop = 1
    run2.rivals = book
    fight2, battle2 = _fight(content, run2)
    assert fight2.rival is rival
    ship = next(s for s in battle2.world.ships.values() if s.captain == rival.name)
    ship.status = ShipStatus.DESTROYED
    news = book.after_battle(battle2, "Kessik", "Border Patrol", fight2.rival)
    assert "will not trouble us again" in news and rival.fate == "destroyed" and rival.met == 2
    assert book.for_stop(_tour().stops[1], content, set()) is None


def test_a_rival_taken_prisoner_is_done_too(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, [], seed=2)
    run.state.stop = 1
    book = run.rivals = RivalBook(Career({}))
    book.rivals.append(_kor())
    fight, battle = _fight(content, run)
    next(s for s in battle.world.ships.values() if s.captain == "Kor").status = ShipStatus.CAPTURED
    assert book.after_battle(battle, "Kessik", "Border Patrol", fight.rival) == "Kor is our prisoner at last."
    assert book.rivals[0].fate == "captured"


def test_finishing_a_stop_records_rivals_for_the_ready_room(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, [], seed=2)
    run.state.stop = 1
    run.rivals = RivalBook(Career({}))
    fight, battle = _fight(content, run)
    w = battle.world
    for s in w.ships.values():
        if s.side != w.player_side:
            s.status = ShipStatus.ESCAPED
    w.run(1.0)
    run.finish(battle)
    assert "got away" in run.rival_news and run.rivals.rivals


@pytest.fixture()
def screen():  # type: ignore[no-untyped-def]
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
    pygame = pytest.importorskip("pygame")
    pygame.init()
    from begin.ui import theme

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    return pygame.display.set_mode((1024, 700))


def test_the_ready_room_briefs_a_returning_rival(content, screen) -> None:  # type: ignore[no-untyped-def]
    from begin.settings import Settings
    from begin.ui.tour_scene import TourScene

    settings = Settings()
    settings.career = {"rivals": [{"name": "Kor", "faction": "klingon", "ship_class": "klingon.bc",
                                   "ship_name": "Klothos", "place": "Archanis IV"}]}
    ts = TourScene(content, settings, lambda run: None, lambda: None)
    ts.open()
    ts.tour_i = next(i for i, t in enumerate(ts.tours) if t.id == "border-patrol")
    ts.new_tour()
    ts.commission()
    assert ts.run is not None and ts.run.rivals is not None
    ts.run.state.stop = 1
    ts.update(0.1)
    ts.draw(screen)
    assert "Kor" in ts.run.briefing()[1]
