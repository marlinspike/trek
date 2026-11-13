"""The Borg storyline [E]: the hive, Seven's work, away teams, the cloak refit and the plasma hunt, the bridge's
words for all of it, and the tour that strings it together."""

from __future__ import annotations

import pygame
import pytest

from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle
from begin.console.plain import plain_order
from begin.help.coach import HelpContext, tips
from begin.sim import collective
from begin.sim.commands import AwayTeam, FireSeeker, Hail, Remodulate, SetCloak, SetDuty, SetHelm, StartProject, Sweep
from begin.sim.events import HailAnswered, HiveEvent
from begin.sim.ship import ShipStatus
from begin.tour import TourRun, load_tours


def _borg(content, enemy: str = "borg.sp", seed: int = 3, me: str = "federation.dn", y: float = 9000.0):  # type: ignore[no-untyped-def]
    b = build_battle(content, BattleSetup([FleetSpec(0, [ShipSpec(me, x=0.0, y=0.0, course=0.0)], player=True),
                                           FleetSpec(1, [ShipSpec(enemy, x=0.0, y=y, course=180.0)])], seed=seed))
    w = b.world
    us = w.ships[b.player_ship_id]
    them = next(s for s in w.ships.values() if s.side == 1)
    return b, w, us, them


# ------------------------------------------------------------------ the hive

def test_the_hive_learns_a_weapon_and_a_new_frequency_starts_from_nothing(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, them = _borg(content)
    fresh, _ = collective.incoming(w, them, us, "phaser")
    assert fresh == pytest.approx(1.0)
    collective.learn(w, them, us, "phaser", 5000.0, 5000.0)
    learned, _ = collective.incoming(w, them, us, "phaser")
    assert learned < 0.5
    assert any(isinstance(e, HiveEvent) and e.kind == "adapted" for e in w.events)
    us.phaser_freq += 1                                     # what a remodulation does
    again, _ = collective.incoming(w, them, us, "phaser")
    assert again == pytest.approx(1.0)


def test_remodulating_takes_the_charge_off_the_banks(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, _ = _borg(content)
    w.run(8.0)
    freq = us.phaser_freq
    assert w.submit(Remodulate(ship_id=us.id)) is None
    w.step()
    assert us.phaser_freq != freq and us.remodulating > 0


def test_scans_find_the_relay_and_then_the_harmonics(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, them = _borg(content)
    obs = w.observe(0)
    assert obs.weak_point(them.id) is None
    for _ in range(40):
        collective.on_scan(w, us, them, "seven")
    obs = w.observe(0)
    assert obs.weak_point(them.id) == them.weak_point
    assert collective.insight(w, 0).has_code(them.id)
    pierce = collective.incoming(w, them, us, "harmonic")[1]
    assert pierce                                           # harmonic torpedoes go straight through her shields


def test_destroying_the_relay_puts_her_to_sleep_and_she_wakes_with_a_new_one(content) -> None:  # type: ignore[no-untyped-def]
    _, w, _, them = _borg(content)
    old = them.weak_point
    them.subsystem(old).damage = 100
    w.step()
    assert them.dormant > 0
    assert not any(sh.up for sh in them.shields)
    assert all(b.charge == 0 for b in them.banks)
    w.run(them.dormant + 2.0)
    assert them.dormant == 0 and them.weak_point and them.weak_point != old


def test_the_borg_never_take_terms(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, them = _borg(content)
    for intent in ("surrender", "withdraw", "surrender", "withdraw", "talk"):
        cmd = Hail(ship_id=us.id, target=them.id, intent=intent, persuasion=1.5, threat=True)
        assert w.submit(cmd) is None
        w.step()
        ev = cmd.answered
        assert isinstance(ev, HailAnswered) and ev.outcome in ("refuse", "silence", "talk")
        w.run(12.0)                                          # let the channel cool between hails
    assert them.status == ShipStatus.ACTIVE and not them.hold_fire


# ------------------------------------------------------------------ Seven's duties and the away team

def test_seven_tunes_the_shields_on_duty(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, _ = _borg(content)
    assert w.submit(SetDuty(ship_id=us.id, duty="shields")) is None
    w.run(30.0)
    assert us.duty == "shields" and us.tuning > 0.3


def test_an_away_team_takes_a_shuttle_across(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, them = _borg(content, y=4000.0)
    assert w.submit(AwayTeam(ship_id=us.id, target=them.id, task="survey")) is None
    w.step()
    ops = w.observe(0).away_ops()
    assert len(ops) == 1 and ops[0].task == "survey"


# ------------------------------------------------------------------ the cloak refit and the plasma hunt

def test_the_refit_fires_from_her_cloak(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, them = _borg(content, enemy="klingon.bc", me="federation.dnc", y=20000.0)
    assert us.cls.can_cloak and getattr(us.cls, "cloak_fire", False)
    assert w.submit(SetCloak(ship_id=us.id, on=True)) is None
    w.run(10.0)
    assert not w.is_visible(1, us.id)


def test_a_damaged_drive_at_warp_leaves_a_trail_a_seeker_can_follow(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, BattleSetup([FleetSpec(0, [ShipSpec("federation.dn", x=0.0, y=0.0, course=0.0)], player=True),
                                           FleetSpec(1, [ShipSpec("romulan.bp", x=3000.0, y=12000.0, course=90.0)])], seed=3))
    w = b.world
    us = w.ships[b.player_ship_id]
    rom = next(s for s in w.ships.values() if s.side == 1)
    for d in rom.drives:
        d.damage = 50
    w.controllers = [c for c in w.controllers if getattr(c, "ship_id", None) != rom.id]
    w.submit(SetCloak(ship_id=rom.id, on=True))
    w.submit(SetHelm(ship_id=rom.id, course=90.0, warp=4.0))
    w.submit(SetHelm(ship_id=us.id, course=0.0, warp=0.0))
    assert w.submit(StartProject(ship_id=us.id, project="seeker")) is None
    w.run(25.0)
    obs = w.observe(0)
    assert obs.plasma().get(rom.id)                        # her trail shows, though she doesn't
    assert w.submit(Sweep(ship_id=us.id)) is None
    w.step()
    assert w.submit(FireSeeker(ship_id=us.id, target=rom.id)) is None


# ------------------------------------------------------------------ words, tips and looks

@pytest.mark.parametrize("said, order", [
    ("take a shuttle over to the sphere", "away"),
    ("look for exhaust", "sweep"),
    ("program a torpedo to follow her exhaust", "design seeker"),
    ("scan for harmonics", "duty harmonics"),
])
def test_plain_words_for_the_borg_and_the_hunt(said: str, order: str) -> None:
    assert plain_order(said).startswith(order)


def test_the_coach_knows_the_hive(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, them = _borg(content)
    us.target = them.id
    w.run(2.0)
    titles = [t.title for t in tips(HelpContext(content, w.observe(0), us))]
    assert "Learn the hive" in titles and "Tune the shields" in titles
    for _ in range(20):
        collective.on_scan(w, us, them, "seven")
    titles = [t.title for t in tips(HelpContext(content, w.observe(0), us))]
    assert "Hit the relay" in titles
    them.subsystem(them.weak_point).damage = 100
    w.step()
    titles = [t.title for t in tips(HelpContext(content, w.observe(0), us))]
    assert titles and titles[0] == "She sleeps"


def test_borg_torpedoes_and_cutting_beams_draw() -> None:
    from begin.ui.beams import Beam
    from begin.ui.camera import Camera
    from begin.ui.torpedo_art import draw_round

    surf = pygame.Surface((200, 200))
    overlay = pygame.Surface((200, 200), pygame.SRCALPHA)
    draw_round(surf, overlay, 100, 100, 45.0, (90, 255, 120), "borg", 5.0, 0.3, 7)
    beam = Beam(0, 0, 1000, 0, 10.0, (150, 255, 140), style="cutter")
    plain = Beam(0, 0, 1000, 0, 10.0, (150, 255, 140))
    assert beam.life > plain.life * 2                       # a cutting beam lingers on the hull
    cam = Camera(pygame.Rect(0, 0, 200, 200), cx=500.0, zoom=0.15)
    for t in (0.05, 0.4, 0.9):
        beam.age = t
        beam.draw(surf, overlay, cam, t)


def test_the_hive_has_its_own_sounds() -> None:
    from begin.ui.audio import SOUNDS

    for name in ("cutter", "hive"):
        assert len(SOUNDS[name]()) > 1000


# ------------------------------------------------------------------ the tour

def _collective():  # type: ignore[no-untyped-def]
    return next(t for t in load_tours(user_dir=None)[0] if t.id == "the-collective")


def _fight(run, content):  # type: ignore[no-untyped-def]
    fight = run.launch()
    b = build_battle(content, fight.setup)
    run.prepare(b)
    return fight, b


def _win(b) -> None:  # type: ignore[no-untyped-def]
    for s in b.world.ships.values():
        if s.side == 1:
            s.status = ShipStatus.DESTROYED
    b.world.run(2.0)


def test_the_hive_remembers_us_from_stop_to_stop(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_collective(), content, [], seed=3)
    fight, b = _fight(run, content)
    w = b.world
    us = w.ships[fight.ship_ids[0]]
    them = next(s for s in w.ships.values() if s.side == 1)
    collective.learn(w, them, us, "phaser", 5000.0, 5000.0)
    learned = collective.mind(w, them.faction).level(collective.weapon_key("phaser", us))
    _win(b)
    run.finish(b)
    assert run.hive_met() and any("Collective remembers" in ln for ln in run.lesson_lines())
    fight2, b2 = _fight(run, content)
    us2 = b2.world.ships[fight2.ship_ids[0]]
    carried = collective.mind(b2.world, them.faction).level(collective.weapon_key("phaser", us2))
    assert 0 < carried < learned


def test_the_treaty_choice_fits_the_cloak_and_starfleet_asks_about_it(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_collective(), content, [], seed=3)
    for _ in range(2):
        _, b = _fight(run, content)
        _win(b)
        run.finish(b)
    assert run.needs_choice()
    labels = [c.label for c in run.stop.choices]
    run.choose(next(i for i, lab in enumerate(labels) if "cloak" in lab.lower()))
    assert run.projected()[0].class_id == "federation.dnc"
    msg = run.request_from_ready_room()
    assert "cloak" in msg and run.state.cloak_questions == 1
    fight, b = _fight(run, content)
    assert b.world.ships[fight.ship_ids[0]].cls.can_cloak


def test_an_assimilated_flagship_ends_the_tour(content) -> None:  # type: ignore[no-untyped-def]
    run = TourRun.new(_collective(), content, [], seed=3)
    fight, b = _fight(run, content)
    w = b.world
    us = w.ships[fight.ship_ids[0]]
    us.crew, us.boarders, us.boarder_side = 3, 30, 1
    w._capture(us, 1)
    w.run(1.0)
    entry = run.finish(b)
    assert entry.outcome == "assimilated" and run.state.over == "lost"
    assert "Collective" in entry.captain
