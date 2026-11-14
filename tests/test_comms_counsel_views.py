"""The comms card and map marks (ui/comms_view.py), and the counsel panel and mission card (ui/counsel_view.py).

Drawn headless; the checks are what a player relies on: something is drawn, the card is shown when it should be,
the buttons say and do the right thing, and the panel fits the room it is given."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle  # noqa: E402
from begin.crew.counsel import Plan, Step  # noqa: E402
from begin.crew.hails import Channel  # noqa: E402
from begin.crew.situation import MissionView  # noqa: E402
from begin.session.battle import BattleSession  # noqa: E402
from begin.ui import comms_view, counsel_view, theme  # noqa: E402
from begin.ui.camera import Camera  # noqa: E402
from begin.ui.widgets import UI  # noqa: E402


@pytest.fixture()
def surf():  # type: ignore[no-untyped-def]
    pygame.init()
    theme.font.cache_clear()
    theme._fallback.cache_clear()
    return pygame.Surface((1400, 900))


@pytest.fixture()
def session(content):  # type: ignore[no-untyped-def]
    setup = BattleSetup([FleetSpec(0, [ShipSpec("federation.dn", x=0.0, y=0.0)], player=True),
                         FleetSpec(1, [ShipSpec("klingon.bc", x=0.0, y=6000.0, course=180.0)])], seed=7)
    s = BattleSession(build_battle(content, setup), hidden={}, llm={}, career={})
    s.world.step()
    s.obs = s.observe()
    return s


def _drew(surf, fn) -> bool:  # type: ignore[no-untyped-def]
    """Whether `fn` changed any pixel."""
    surf.fill((0, 0, 0))
    before = pygame.image.tobytes(surf, "RGB")
    fn()
    return pygame.image.tobytes(surf, "RGB") != before


def _enemy(session):  # type: ignore[no-untyped-def]
    return next(s for s in session.world.ships.values() if s.side == 1)


def _channel(session, status: str = "open", mood: str = "shaken") -> Channel:  # type: ignore[no-untyped-def]
    them = _enemy(session)
    ch = Channel(them.id, "Kor", "Captain", them.name, "klingon", them.cls.name, status=status, mood=mood,
                 tick=session.obs.tick)
    ch.lines += [("us", "Stand down."), ("them", "Never!"), ("note", "They are charging weapons.")]
    session.comms.channels[them.id] = ch
    session.comms.focus = them.id
    return ch


def _cam() -> Camera:
    cam = Camera(pygame.Rect(0, 0, 1000, 800), zoom=0.05)
    cam.cx, cam.cy = 0.0, 3000.0
    return cam


# ------------------------------------------------------------------ comms

@pytest.mark.parametrize("mood", sorted(comms_view.MOOD_COLOR))
def test_every_mood_has_a_mark(surf, mood: str) -> None:  # type: ignore[no-untyped-def]
    assert _drew(surf, lambda: comms_view.mood_mark(surf, mood, 50, 50, 7.0, 1.0))
    assert comms_view.mood_color(mood) == comms_view.MOOD_COLOR[mood]


def test_an_unknown_mood_reads_as_unknown() -> None:
    assert comms_view.mood_color("bemused") == comms_view.MOOD_COLOR["unknown"]


@pytest.mark.parametrize("faction", ["klingon", "romulan", "orion", "federation", "borg"])
def test_every_race_has_an_emblem(surf, faction: str) -> None:  # type: ignore[no-untyped-def]
    assert _drew(surf, lambda: comms_view.emblem(surf, faction, 60, 60, 22))


def test_the_card_shows_a_live_or_pinned_channel_and_hides_a_quiet_one(session) -> None:  # type: ignore[no-untyped-def]
    assert comms_view.showing(session.comms, session.obs) is None          # nothing focused
    ch = _channel(session)
    assert comms_view.showing(session.comms, session.obs) is ch
    ch.tick = session.obs.tick - int((comms_view.SHOW_CYCLES + 1) * session.obs.rules.ticks_per_cycle)
    assert comms_view.showing(session.comms, session.obs) is None          # quiet too long
    session.comms.show(ch.ship_id)
    assert comms_view.showing(session.comms, session.obs) is ch            # the captain asked for it
    session.comms.dismiss()
    assert comms_view.showing(session.comms, session.obs) is None


def test_the_card_offers_demands_and_your_own_words(surf, session) -> None:  # type: ignore[no-untyped-def]
    ch = _channel(session, status="hailing")
    ui = UI()
    said: list[str] = []
    box = comms_view.draw_card(surf, (1380, 20), session.obs, session.player_id, session.comms, ui, 1.0, said.append)
    assert box is not None and box.right == 1380 and box.width == comms_view.CARD_W
    labels = {h.tooltip for h in ui.hotspots}
    assert any(t.startswith('Say: "Lower your shields') for t in labels)
    for h in ui.hotspots:
        if h.tooltip.startswith('Say: "') or h.tooltip == "Type your own words to this captain":
            h.action()
    assert said[0] == f"hail #{ch.ship_id} {comms_view.DEMANDS[0][1]}"
    assert said[-1].startswith("\0type:hail ")
    assert any(t.startswith("Resolve:") for t in labels)                  # our officers' read of the captain


def test_the_card_lists_other_channels_as_chips(surf, session) -> None:  # type: ignore[no-untyped-def]
    ch = _channel(session)
    other = Channel(999, "Koloth", "Commander", "IKS Gr'oth", "klingon", "Cruiser", mood="enraged", tick=0)
    session.comms.channels[999] = other
    ui = UI()
    comms_view.draw_card(surf, (1380, 20), session.obs, session.player_id, session.comms, ui, 0.0, lambda s: None)
    chip = next(h for h in ui.hotspots if "Koloth" in h.tooltip)
    chip.action()
    assert session.comms.focus == 999 and session.comms.pinned
    session.comms.focus = ch.ship_id
    close = next(h for h in ui.hotspots if h.tooltip.startswith("Close the comms card"))
    close.action()
    assert session.comms.focus is None


def test_a_surrendered_ship_offers_to_board_her(surf, session, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    ch = _channel(session, mood="surrendered")
    monkeypatch.setattr(type(session.obs), "fate", lambda self, sid: "surrendered")
    ui = UI()
    said: list[str] = []
    comms_view.draw_card(surf, (1380, 20), session.obs, session.player_id, session.comms, ui, 0.0, said.append)
    board = next(h for h in ui.hotspots if "prisoners of war" in h.tooltip)
    board.action()
    assert said == [f"capture {session.obs.name_of(ch.ship_id)}"]


def test_a_lost_ship_shows_the_card_without_buttons(surf, session, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _channel(session, status="closed")
    monkeypatch.setattr(type(session.obs), "fate", lambda self, sid: "destroyed")
    ui = UI()
    box = comms_view.draw_card(surf, (1380, 20), session.obs, session.player_id, session.comms, ui, 0.0, lambda s: None)
    assert box is not None
    assert not any(h.tooltip.startswith("Say") for h in ui.hotspots)


def test_the_map_marks_moods_and_runs_hailing_rings(surf, session, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    _channel(session, status="hailing", mood="wavering")
    monkeypatch.setattr(type(session.obs), "demeanour", lambda self, sid: "")
    cam, clip = _cam(), pygame.Rect(0, 0, 1000, 800)
    assert _drew(surf, lambda: comms_view.draw_map(surf, cam, session.obs, session.player_id, session.comms, 3.0, clip))
    # a mood we don't show and no channel being opened: nothing at all
    session.comms.channels.clear()
    session.comms.focus = None
    monkeypatch.setattr(type(session.obs), "demeanour", lambda self, sid: "gone")
    assert not _drew(surf, lambda: comms_view.draw_map(surf, cam, session.obs, session.player_id, session.comms, 3.0, clip))


# ------------------------------------------------------------------ counsel

def _plan(i: int, station: str = "tactical", steps: int = 3, reason: str = "Because it is the right thing.") -> Plan:
    return Plan(station, "worf", f"Officer{i}", "The sword", f"Plan {i}", reason,
                tuple(Step(f"fire phasers {n}", f"step {n}") for n in range(steps)))


def test_counsel_takes_the_room_it_needs_and_runs_plans_and_steps(surf) -> None:  # type: ignore[no-untyped-def]
    area = counsel_view.counsel_rect(pygame.Rect(0, 0, 1000, 800))
    plans = [_plan(i, st) for i, st in enumerate(("tactical", "helm", "engineering", "science"))]
    ui = UI()
    ran: list[tuple[str, str]] = []
    closed: list[int] = []
    box = counsel_view.draw_counsel(surf, area, plans, ui, lambda p: ran.append((p.title, "all")),
                                    lambda p, line: ran.append((p.title, line)), lambda: closed.append(1),
                                    {"fire phasers 0": 0.5}, 1.0, False, goal="hold the line",
                                    clear_goal=lambda: closed.append(2))
    assert box.height <= area.height and box.width == area.width
    for h in ui.hotspots:
        h.action()
    assert ("Plan 0", "all") in ran and ("Plan 3", "fire phasers 2") in ran
    assert closed == [1, 2]


def test_counsel_with_nothing_to_advise_says_so(surf) -> None:  # type: ignore[no-untyped-def]
    ui = UI()
    box = counsel_view.draw_counsel(surf, pygame.Rect(0, 0, 400, 600), [], ui, lambda p: None,
                                    lambda p, s: None, lambda: None, {}, 0.0, True)
    assert box.height < 200


def test_counsel_in_a_short_window_folds_steps_into_tooltips(surf) -> None:  # type: ignore[no-untyped-def]
    plans = [_plan(i, steps=8, reason="A long reason. " * 20) for i in range(4)]
    ui = UI()
    box = counsel_view.draw_counsel(surf, pygame.Rect(0, 0, 340, 300), plans, ui, lambda p: None,
                                    lambda p, s: None, lambda: None, {}, 0.0, True)
    assert box.height <= 300
    assert sum("Run all of" in h.tooltip for h in ui.hotspots) == 4         # every plan stays in view...
    assert all("Steps: fire phasers 0" in h.tooltip for h in ui.hotspots if h.tooltip.startswith("A long reason"))
    assert not any("run just this step" in h.tooltip for h in ui.hotspots)  # ... its steps in the tooltip


def _mission(**kw) -> MissionView:  # type: ignore[no-untyped-def]
    base = {"kind": "rescue", "state": "open", "title": "Save the Kobayashi Maru"}
    base.update(kw)
    return MissionView(**base)


@pytest.mark.parametrize("m,stand,col", [
    (_mission(state="done", people=40, saved=30), "Mission accomplished.", theme.GOOD),
    (_mission(state="failed", people=40, saved=10), "Mission failed.", theme.ALERT),
    (_mission(kind="escort", state="done"), "Mission accomplished.", theme.GOOD),
    (_mission(people=40, saved=10, aboard=5, beaming=True, ward_id=3), "10 of 40 safe, 5 aboard", theme.GOOD),
    (_mission(people=40, ward_id=3, blocked="shield"), "0 of 40 safe, 0 aboard", theme.CAUTION),
    (_mission(people=40, ward_id=3, ward_range=8000.0, time_left=20.0), "0 of 40 safe, 0 aboard  ·  20 cycles left",
     theme.ALERT),
    (_mission(people=40), "0 of 40 safe, 0 aboard", theme.TEXT_DIM),
    (_mission(kind="escort", to_range=5000.0, ward_hull=0.4, hunter_ids=(1, 2)), "5,000 from safety  ·  hull 40%",
     theme.CAUTION),
    (_mission(kind="intercept", runner_escape=42.0), "She is running: clear in about 42 cycles.", theme.CAUTION),
    (_mission(kind="intercept"), "She is running: position unknown.", theme.CAUTION),
])
def test_the_mission_card_reads_how_it_stands(m: MissionView, stand: str, col) -> None:  # type: ignore[no-untyped-def]
    got = counsel_view.mission_lines(m)
    assert got[0] == stand and got[2] == col


def test_escort_hunters_are_counted() -> None:
    assert counsel_view.mission_lines(_mission(kind="escort", hunter_ids=(4,)))[1] == "1 ship hunting her"
    assert counsel_view.mission_lines(_mission(kind="escort"))[1] == "No one is hunting her now."


@pytest.mark.parametrize("m", [
    _mission(people=40, ward_id=3, ward_range=8000.0, time_left=20.0), _mission(state="done", people=40, saved=40),
    _mission(state="failed"), _mission(kind="intercept", runner_escape=9.0),
])
def test_the_mission_card_draws_at_its_corner(surf, m: MissionView) -> None:  # type: ignore[no-untyped-def]
    box = counsel_view.draw_mission(surf, (1380, 60), m, 0.4)
    assert box.right == 1380 and box.y == 60 and box.width == counsel_view.MISSION_W


def test_mission_marks_find_the_ward_the_runner_and_safety(surf) -> None:  # type: ignore[no-untyped-def]
    cam, clip = _cam(), pygame.Rect(0, 0, 1000, 800)
    poses = {3: (0.0, 3000.0, 0.0), 4: (500.0, 3500.0, 0.0)}
    esc = _mission(kind="escort", ward_id=3, to=(200.0, 2800.0))
    assert _drew(surf, lambda: counsel_view.draw_marks(surf, cam, esc, poses, clip, 0.0))
    run = _mission(kind="intercept", runner_id=4)
    assert _drew(surf, lambda: counsel_view.draw_marks(surf, cam, run, poses, clip, 0.0))
    over = _mission(kind="intercept", runner_id=4, state="done")
    assert not _drew(surf, lambda: counsel_view.draw_marks(surf, cam, over, poses, clip, 0.0))
