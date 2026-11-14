"""Generated tours of duty (tour/generate.py) [E]: a fresh patrol each time, rising to a boss."""

from __future__ import annotations

import os

import pytest

from begin.battle import PLAYER_FLAGSHIP_CLASSES, build_battle
from begin.tour import TourRun
from begin.tour.generate import BOSS_THREAT, PREFIX, THREAT, current, generate_tour, is_generated, seed_of
from begin.tour.model import check_tour

SEEDS = range(1, 41)


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


def test_the_same_seed_makes_the_same_tour_and_the_seed_is_in_its_id(content) -> None:  # type: ignore[no-untyped-def]
    a, b = generate_tour(content, 1234), generate_tour(content, 1234)
    assert a == b and a.id == f"{PREFIX}1234" and is_generated(a.id) and seed_of(a.id) == 1234
    assert generate_tour(content, 1235) != a
    assert seed_of("border-patrol") is None and seed_of(f"{PREFIX}x") is None


@pytest.mark.parametrize("seed", SEEDS)
def test_every_generated_tour_is_sound(content, seed: int) -> None:  # type: ignore[no-untyped-def]
    t = generate_tour(content, seed)
    assert check_tour(t, set(content.classes)) == []
    assert t.flagship == PLAYER_FLAGSHIP_CLASSES["federation"] == "federation.dn"      # always the Dreadnought
    assert len(t.stops) == len(THREAT) + 1
    assert any(s.mission is not None for s in t.stops)
    factions = {content.classes[c].faction for s in t.stops for c in (*s.enemies, *(x for w in s.waves for x in w.ships))}
    assert len(factions) == 1 and "federation" not in factions                          # one adversary, the whole way
    assert len({s.system for s in t.stops}) == len(t.stops)
    assert [s.chart[0] for s in t.stops] == sorted(s.chart[0] for s in t.stops)       # the chart runs left to right


@pytest.mark.parametrize("seed", SEEDS)
def test_the_last_stop_is_their_commander_in_their_heaviest_ship(content, seed: int) -> None:  # type: ignore[no-untyped-def]
    t = generate_tour(content, seed)
    boss = t.stops[-1]
    adversary = content.classes[boss.enemies[0]].faction
    heaviest = max((c for c in content.classes_of(adversary, include_bases=False) if c.banks > 0), key=lambda c: c.mass)
    assert boss.enemies[0] == heaviest.id and boss.win_flag == "boss-beaten"
    assert boss.waves and boss.waves[0].after_clear is not None                         # a reserve behind the screen
    assert len(boss.choices) == 2 and len(t.stops[2].choices) == 2


def _threat(content, stop, flags=frozenset()) -> float:  # type: ignore[no-untyped-def]
    return sum(content.classes[c].mass for c in (*stop.enemy_ships(set(flags)), *(x for w in stop.waves for x in w.ships)))


def test_the_threat_rises_to_the_boss(content) -> None:  # type: ignore[no-untyped-def]
    assert list(THREAT) == sorted(THREAT) and BOSS_THREAT > THREAT[-1]
    first = last = boss = 0.0
    for seed in SEEDS:
        t = generate_tour(content, seed)
        first += _threat(content, t.stops[0])
        last += _threat(content, t.stops[-2])
        boss += _threat(content, t.stops[-1])
    assert first < last < boss


def test_the_choices_change_the_fight(content) -> None:  # type: ignore[no-untyped-def]
    t = generate_tour(content, 7)
    mid, boss = t.stops[2], t.stops[-1]
    assert _threat(content, mid, {"refit-2"}) > _threat(content, mid)
    assert any(c.refit for c in mid.choices)
    assert _threat(content, boss, {"struck-first"}) < _threat(content, boss) < _threat(content, boss, {"came-slow"})


def test_a_generated_tour_flies_like_any_other(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    t = generate_tour(content, 3)
    run = TourRun.new(t, content, ["federation.hc"], seed=5)
    fight = run.launch()
    battle = build_battle(content, fight.setup)
    run.prepare(battle)
    me = battle.world.ships[battle.player_ship_id]
    assert me.cls.id == "federation.dn"
    battle.world.run(3.0)
    run.state.save(tmp_path)
    assert (tmp_path / f"{t.id}.json").is_file()


def test_the_tour_on_offer_is_the_one_under_way(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    fresh = current(content, tmp_path, seed=11)
    assert fresh.id == f"{PREFIX}11"
    run = TourRun.new(generate_tour(content, 42), content, [], seed=1)
    run.state.save(tmp_path)
    assert current(content, tmp_path, seed=11).id == f"{PREFIX}42"     # resume it, whatever seed was asked for
    run.state.over = "won"
    run.state.save(tmp_path)
    assert current(content, tmp_path, seed=11).id == f"{PREFIX}11"     # finished: a new one again


def test_the_tours_page_offers_a_generated_tour_and_another(content, screen) -> None:  # type: ignore[no-untyped-def]
    from begin.settings import Settings
    from begin.ui.tour_scene import TourScene

    ts = TourScene(content, Settings(), lambda run: None, lambda: None)
    ts.open()
    gen = [t for t in ts.tours if is_generated(t.id)]
    assert len(gen) == 1
    ts.tour_i = ts.tours.index(gen[0])
    ts.update(0.1)
    ts.draw(screen)
    again = next(h for h in ts.ui.hotspots if h.tooltip.startswith("Make a different patrol"))
    old = gen[0].id
    for _ in range(3):              # a fresh seed can repeat, in principle; three in a row can't reasonably
        again.action()
        if ts.tour.id != old:
            break
    assert ts.tour is not None and is_generated(ts.tour.id) and ts.tour.id != old
    ts.draw(screen)
