"""Starting squadrons (tour/squadrons.py) [E]: earned through officers' trust and tours won, escorts and perks only."""

from __future__ import annotations

import os

import pytest

from begin.crew.career import Career
from begin.tour import TourRun, load_tours, squadrons
from begin.tour.state import TourState


def _tour(tid: str = "border-patrol"):  # type: ignore[no-untyped-def]
    return next(t for t in load_tours()[0] if t.id == tid)


def test_every_squadron_is_federation_escorts_that_fit_a_budget(content) -> None:  # type: ignore[no-untyped-def]
    for sq in squadrons.SQUADRONS:
        assert sq.escorts and all(content.classes[c].faction == "federation" for c in sq.escorts)
        assert "federation.dn" not in sq.escorts           # the flagship is the tour's, never a squadron's
        assert sq.cost(content) <= 260 and all(p in squadrons.PERKS for p in sq.perks)
        assert sq.describe(content) and sq.requirement()
    assert squadrons.offered(content, "federation") == list(squadrons.SQUADRONS)
    assert squadrons.offered(content, "klingon") == []


def test_trust_and_tours_won_earn_squadrons() -> None:
    career = Career({})
    assert [s.key for s in squadrons.SQUADRONS if s.unlocked(career)] == ["line"]
    career.add("worf", 30)                      # Trusted
    assert squadrons.BY_KEY["worf"].unlocked(career) and not squadrons.BY_KEY["geordi"].unlocked(career)
    before = Career(dict(career.store))
    assert squadrons.record_win(career, "orion-run", 7)
    assert not squadrons.record_win(career, "orion-run", 7)          # the same tour counts once
    assert squadrons.tours_won(career) == 1
    assert [s.key for s in squadrons.newly_unlocked(before, career)] == ["detachment"]
    assert squadrons.BY_KEY["worf"].requirement() == "Worf's trust (Trusted)"
    assert squadrons.BY_KEY["detachment"].requirement() == "1 tour won"


def test_liaison_brings_a_call_and_veterans_keep_their_spirits(content) -> None:  # type: ignore[no-untyped-def]
    tour = _tour()
    plain = TourRun.new(tour, content, ["federation.hc"], seed=3)
    sq = squadrons.BY_KEY["detachment"]
    run = TourRun.new(tour, content, list(sq.escorts), seed=3, squadron=sq)
    assert run.state.calls_left == plain.state.calls_left + 1
    assert run.state.perks == ["veteran", "liaison"] and run.state.squadron_key == "detachment"
    base = content.factions["federation"].morale_start
    escort = next(r for r in run.state.squadron if r.role == "escort")
    assert escort.morale == pytest.approx(base + squadrons.VETERAN_MORALE)
    assert run.state.flagship.morale is None                          # the flagship is untouched
    escort.morale = base - 20.0                                       # a hard fight
    after = next(r for r in run.projected() if r.role == "escort")
    assert after.morale == pytest.approx(base + squadrons.VETERAN_MORALE)


def test_a_tender_brings_more_torpedoes_between_stops(content) -> None:  # type: ignore[no-untyped-def]
    tour = _tour()
    sq = squadrons.BY_KEY["geordi"]
    runs = [TourRun.new(tour, content, list(sq.escorts), seed=3, squadron=s) for s in (None, sq)]
    for run in runs:
        for r in run.state.squadron:
            if r.role == "escort":
                r.torps = 0
    got = [sum(r.torps or 0 for r in run.projected() if r.role == "escort") for run in runs]
    assert got[1] > got[0]
    assert squadrons.resupply_bonus(runs[1].state) == squadrons.TENDER_RESUPPLY


def test_an_old_save_without_squadrons_still_loads(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_tour(), content, [], seed=1)
    d = run.state.to_json()
    d.pop("perks")
    d.pop("squadron_key")
    state = TourState.from_json(d)
    assert state.perks == [] and state.squadron_key == ""


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


def test_the_squadron_page_offers_earned_squadrons(content, screen) -> None:  # type: ignore[no-untyped-def]
    from begin.settings import Settings
    from begin.ui.tour_scene import TourScene

    settings = Settings()
    settings.career = {"trust": {"worf": 35.0}}
    ts = TourScene(content, settings, lambda run: None, lambda: None)
    ts.open()
    ts.tour_i = next(i for i, t in enumerate(ts.tours) if t.id == "border-patrol")
    ts.new_tour()
    ts.update(0.1)
    ts.draw(screen)
    assert not any("La Forge trusts" in h.tooltip for h in ts.ui.hotspots)     # not earned: not clickable
    worf = next(h for h in ts.ui.hotspots if "drilled with Worf" in h.tooltip)
    worf.action()
    assert ts.escorts == ["federation.de", "federation.de"] and ts.group() is squadrons.BY_KEY["worf"]
    ts.draw(screen)
    ts.escorts.pop()                         # send one back: it is no longer that squadron
    assert ts.group() is None
    ts.escorts.append("federation.de")
    ts.commission()
    assert ts.run is not None and ts.run.state.perks == ["veteran"]
    ts.draw(screen)


def test_a_tour_won_is_counted_and_may_earn_a_squadron(content, screen) -> None:  # type: ignore[no-untyped-def]
    from begin.settings import Settings
    from begin.ui.tour_scene import TourScene

    settings = Settings()
    ts = TourScene(content, settings, lambda run: None, lambda: None)
    run = TourRun.new(_tour("orion-run"), content, [], seed=9)
    run.state.over = "won"
    ts._count_win(run)
    assert squadrons.tours_won(Career(settings.career)) == 1
    assert "Starfleet detachment" in ts.note
    ts.note = ""
    ts._count_win(run)                       # the same tour again: no double count, no new note
    assert squadrons.tours_won(Career(settings.career)) == 1 and ts.note == ""
