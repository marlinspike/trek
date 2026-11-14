"""The on-ramp: Ensign, Captain and Admiral, and the Shakedown Cruise that teaches one system a stop (2026-11-14)."""

from __future__ import annotations

import os

import pytest

from begin.battle import BattleSetup, FleetSpec, ShipSpec, at_difficulty, build_battle
from begin.difficulty import DIFFICULTIES, LEVELS, change, level, scaled
from begin.presets import load_presets
from begin.sim.arrivals import Arrival
from begin.sim.mission import MissionDef
from begin.tour import TourRun, load_tours
from begin.tour.drill import CHECKS, Drill, Facts, Step

# ------------------------------------------------------------------ difficulty


def test_a_third_more_or_fewer_and_never_none() -> None:
    assert [change(n, -1 / 3) for n in range(1, 7)] == [0, -1, -1, -1, -2, -2]
    assert [change(n, 1 / 3) for n in range(1, 7)] == [0, 1, 1, 1, 2, 2]
    assert scaled(3, set(), level("ensign")) == [0, 1]
    assert scaled(3, {0}, level("ensign")) == [0, 1, 2] or len(scaled(3, {0}, level("ensign"))) == 2
    assert scaled(4, {0}, level("ensign")) == [0, 1, 2]          # the starbase stays; a ship comes off the end
    assert scaled(3, set(), level("admiral")) == [0, 1, 2, 2]       # more escorts, never a second flagship
    assert scaled(6, set(), level("admiral")) == [0, 1, 2, 3, 4, 5, 5, 4]
    assert scaled(2, set(), level("admiral"), named={1}) == [0, 1, 0]  # a named captain's ship is never repeated
    assert scaled(3, set(), level("admiral"), named={2}) == [0, 1, 2, 1]
    assert scaled(2, set(), level("ensign"), keep=2) == [0, 1]   # a runner is never the ship taken away
    assert level("nonsense").key == "captain" and level(None).key == "captain"
    assert LEVELS == tuple(DIFFICULTIES)


def test_every_preset_at_every_level_keeps_the_enterprise_a_dreadnought(content) -> None:  # type: ignore[no-untyped-def]
    for p in load_presets():
        counts = {}
        skill = {}
        for key in LEVELS:
            setup = at_difficulty(content, p.setup(), key)
            b = build_battle(content, setup)
            me = b.world.ships[b.player_ship_id]
            assert me.cls.id == "federation.dn", (p.id, key)
            mine = [s for s in b.world.ships.values() if s.side == setup.player_side]
            assert len(mine) == sum(len(f.ships) for f in p.setup().fleets if f.side == setup.player_side)
            foes = [s for s in b.world.ships.values() if s.side != setup.player_side]
            counts[key] = len(foes) + sum(len(a.ships) for a in setup.arrivals if a.side != setup.player_side)
            caps = [b.captains[s.id].personality for s in foes if s.id in b.captains]
            skill[key] = sum(c.competence + c.crew_competence for c in caps) / max(1, len(caps))
            assert all(c.competence <= 1.0 and c.crew_competence >= 0.0 for c in caps)
        assert counts["ensign"] <= counts["captain"] <= counts["admiral"], (p.id, counts)
        assert skill["ensign"] < skill["captain"] < skill["admiral"] or skill["admiral"] >= 1.99, (p.id, skill)
        assert counts["ensign"] >= 1


def test_a_custom_battle_keeps_its_fleets_and_waves_scale_with_the_enemy(content) -> None:  # type: ignore[no-untyped-def]
    mine = FleetSpec(0, [ShipSpec("federation.dn")], player=True)
    theirs = FleetSpec(1, [ShipSpec("klingon.fr") for _ in range(3)])
    custom = BattleSetup([mine, theirs], fixed_fleets=True)
    assert len(at_difficulty(content, custom, "admiral").fleets[1].ships) == 3
    assert at_difficulty(content, custom, "admiral").difficulty == "admiral"
    wave = Arrival(1, ("klingon.fr", "klingon.fr", "klingon.fr"), at=40.0, names=("Gorkon", None, None))
    help_ = Arrival(0, ("federation.de",), kind="reinforcement", at=60.0)
    s = at_difficulty(content, BattleSetup([mine, theirs], arrivals=[wave, help_]), "admiral")
    assert len(s.fleets[1].ships) == 4 and s.fleets[1].ships[3].name is None
    assert len(s.arrivals[0].ships) == 4 and s.arrivals[0].names[0] == "Gorkon" and s.arrivals[0].names[3] is None
    assert s.arrivals[1] == help_                                  # our own help never changes
    run = MissionDef(kind="intercept", runner=2)
    s = at_difficulty(content, BattleSetup([mine, theirs], mission=run), "ensign")
    assert len(s.fleets[1].ships) == 3                             # the runner (the third) is kept
    rival = FleetSpec(1, [ShipSpec("klingon.fr"), ShipSpec("klingon.fr"), ShipSpec("klingon.bc", captain="Kor")])
    s = at_difficulty(content, BattleSetup([mine, rival]), "ensign")
    assert [x.captain for x in s.fleets[1].ships].count("Kor") == 1     # a rival is never the ship sent home
    s = at_difficulty(content, BattleSetup([mine, FleetSpec(1, [ShipSpec("klingon.bc", captain="Kor")] * 3)]), "admiral")
    assert [x.captain for x in s.fleets[1].ships].count("Kor") == 3     # ... nor cloned (the added ship has none)
    big = BattleSetup([mine, FleetSpec(1, [ShipSpec("klingon.fr") for _ in range(57)])])
    assert sum(len(f.ships) for f in at_difficulty(content, big, "admiral").fleets) <= 60


# ------------------------------------------------------------------ the drill


def test_the_drill_gives_a_step_praises_it_and_moves_on() -> None:
    d = Drill("Helm", "spock", (Step("Warp three, please.", "press W", "warp", "Warp three."),
                                Step("Fire!", "press F", "phasers", "Hit."), Step("Win.", "", "win", "Done.")))
    assert d.update(Facts(cycle=0.0)) == ["Warp three, please."]
    assert d.update(Facts(cycle=1.0)) == []
    assert d.update(Facts(cycle=2.0, warp=5.0, warp_change=2.0)) == ["Warp three."]
    assert d.update(Facts(cycle=3.0, warp=5.0, warp_change=2.0)) == []        # a breath between steps
    assert d.update(Facts(cycle=5.5, warp=5.0, warp_change=2.0)) == ["Fire!"]
    assert d.update(Facts(cycle=60.0)) == ["When you are ready, Captain: press F."]
    assert d.update(Facts(cycle=120.0)) == []                                 # reminded once only
    assert d.update(Facts(cycle=121.0, phaser_shots=1, beaten=True)) == ["Hit.", "Done."]   # won at once: no gap
    assert d.view().learned and d.view().current is None


def test_a_step_already_done_is_not_taught() -> None:
    d = Drill("Shields", "geordi", (Step("Raise them.", "press G", "shields_up", "Up."),))
    assert d.update(Facts(cycle=0.0, shields_up=6)) == ["Up."]
    with pytest.raises(ValueError):
        Step("?", "", "dance")
    assert {"warp", "turn", "target", "phaser_hit", "torpedo", "torpedo_hit", "shields_up", "reinforce",
            "shields_trim", "boost", "delegate", "counsel", "follow", "win"} <= set(CHECKS)


# ------------------------------------------------------------------ the Shakedown Cruise


def _shakedown():  # type: ignore[no-untyped-def]
    tours, problems = load_tours(user_dir=None)
    assert not problems
    assert tours[0].id == "shakedown"                        # the first tour on the list
    return tours[0]


def test_the_shakedown_teaches_one_system_a_stop_in_order() -> None:
    t = _shakedown()
    assert t.flagship == "federation.dn"
    assert [s.lesson_title for s in t.stops] == ["Helm and phasers", "Torpedoes", "Shields and power",
                                                 "Your officers and their counsel"]
    taught = [{x.done for x in s.lesson} for s in t.stops]
    assert {"warp", "turn", "phaser_hit"} <= taught[0] and {"torpedo", "torpedo_hit"} <= taught[1]
    assert {"shields_up", "reinforce", "shields_trim", "boost"} <= taught[2]
    assert {"delegate", "counsel", "follow"} <= taught[3]
    assert all(s.lesson[-1].done == "win" and s.mission is None for s in t.stops)


def test_a_lesson_is_fought_as_written_whatever_the_difficulty(content) -> None:  # type: ignore[no-untyped-def]
    t = _shakedown()
    run = TourRun.new(t, content, [], seed=3)
    run.state.stop = 2
    fight = run.launch()
    assert fight.setup.fixed_fleets
    s = at_difficulty(content, fight.setup, "admiral")
    assert [len(f.ships) for f in s.fleets] == [len(f.ships) for f in fight.setup.fleets]


pygame = pytest.importorskip("pygame")


def test_the_lesson_runs_in_battle_and_its_card_stays_clear(content) -> None:  # type: ignore[no-untyped-def]
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    from begin.ui import theme
    from begin.ui.battle_scene import BattleScene
    from tests.test_calm_screens import collisions

    t = _shakedown()
    for size in ((1024, 640), (1280, 800), (1920, 1080)):
        surf = pygame.display.set_mode(size)
        run = TourRun.new(t, content, [], seed=3)
        fight = run.launch()
        sc = BattleScene(build_battle(content, fight.setup), size, lambda: None)
        sc.campaign.join_tour(run)
        heard: list[str] = []
        sc.session.subscribe(lambda n: heard.append(getattr(n, "text", "")))
        sc.paused = False
        sc.overlay = None
        for _ in range(40):
            sc.update(1 / 30)
        lesson = sc.campaign.lesson()
        assert lesson is not None and lesson.step == 0 and "W raises our speed" in " ".join(heard)
        sc.run_console("warp 5")
        for _ in range(120):
            sc.update(1 / 10)
        assert sc.campaign.lesson().step >= 1                              # type: ignore[union-attr]
        sc.draw(surf)
        with theme.watching() as ink:
            sc.draw(surf)
        assert sc.stage.shown in ("mission", "subtitle", "urgent", "comms", None)
        assert not collisions(ink, surf, skip=sc.map_rect), size
        assert any(k.text.startswith("LESSON") for k in ink), size
        sc.paused = True                                   # the PAUSED banner and the cards keep apart
        sc.draw(surf)
        sc.draw(surf)
        cards = [c for c in sc.stage.cards if c is not None and c.width > 0]
        for i, a in enumerate(cards):
            for b in cards[i + 1:]:
                o = a.clip(b)
                assert o.width <= 2 or o.height <= 2, (size, tuple(a), tuple(b))
        sc.close()


def test_difficulty_is_on_the_menu_and_in_settings(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    pygame.init()
    from begin.settings import Settings
    from begin.ui import theme
    from begin.ui.menu_scene import MenuScene
    from tests.test_calm_screens import collisions

    st = Settings()
    for size in ((1024, 640), (1280, 800), (1920, 1080)):
        surf = pygame.display.set_mode(size)
        m = MenuScene(content, st, lambda s: None, lambda: None)
        m.draw(surf)
        hot = [h for h in m.ui.hotspots if "Ensign, Captain, Admiral" in h.tooltip]
        assert hot and surf.get_rect().contains(hot[0].rect), size
        hot[0].action()
        assert st.difficulty == "admiral"
        hot[0].action()
        assert st.difficulty == "ensign"
        m.open_settings("battle")
        with theme.watching() as ink:
            m.draw(surf)
        assert any(k.text == "Difficulty" for k in ink)
        assert not collisions(ink, surf), size
        st.difficulty = "captain"


def test_a_lesson_keeps_the_officers_suggestions_back_unless_it_teaches_them(content) -> None:  # type: ignore[no-untyped-def]
    """Found by the 2026-11-14 pressure test: in "First light" Worf offered "Target her? (Y makes it so)" while
    Spock's lesson card was asking for W. Only warnings interrupt a lesson; the officers' own lesson keeps them."""
    t = _shakedown()
    for stop, quiet in zip(t.stops, (True, True, True, False)):
        from begin.tour.drill import Drill
        d = Drill(stop.lesson_title, stop.officer, stop.lesson)
        assert d.quiet_bridge is quiet, stop.id
    run = TourRun.new(t, content, [], seed=3)
    fight = run.launch()
    from begin.session.battle import BattleSession
    s = BattleSession(build_battle(content, fight.setup))
    s.join_tour(run)
    s.paused = False
    offered = []
    for _ in range(300):
        s.update(0.1, 1.0)
        if s.proposal is not None:
            offered.append(s.proposal)
    assert all(p.urgent for p in offered), [p.text for p in offered]
