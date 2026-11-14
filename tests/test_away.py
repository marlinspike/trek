"""Away teams (sim/away.py) [E]: every task done, every way a crossing goes wrong, and the comm to the team."""

from __future__ import annotations

import pytest

from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle
from begin.sim import away, collective
from begin.sim.events import HiveEvent, Message
from begin.sim.ship import ShipStatus


def _borg(content, y: float = 3000.0, enemy: str = "borg.sp"):  # type: ignore[no-untyped-def]
    b = build_battle(content, BattleSetup([FleetSpec(0, [ShipSpec("federation.dn", x=0.0, y=0.0, course=0.0)], player=True),
                                           FleetSpec(1, [ShipSpec(enemy, x=0.0, y=y, course=180.0)])], seed=5))
    w = b.world
    us = w.ships[b.player_ship_id]
    them = next(s for s in w.ships.values() if s.side == 1)
    return w, us, them


@pytest.fixture
def unseen(monkeypatch: pytest.MonkeyPatch) -> None:
    """The hive never notices a team unless a test says so."""
    monkeypatch.setattr(away, "NOTICE_BASE", 0.0)
    monkeypatch.setattr(away, "NOTICE_QUIET", 0.0)
    monkeypatch.setattr(away, "NOTICE_REPEAT", 0.0)


def _work(w, op, cycles: float = 40.0) -> None:  # type: ignore[no-untyped-def]
    """Run the team's clock alone (the world's AI would fight, which these tests don't need)."""
    dt = 0.5
    for _ in range(int(cycles / dt)):
        away.update_away(w, dt)
        if op.phase != "aboard":
            return


def _said(w) -> str:  # type: ignore[no-untyped-def]
    return " | ".join(getattr(e, "text", "") for e in w.events if isinstance(e, Message))


@pytest.mark.parametrize("words,task", [
    ("knock out the vinculum", "relay"), ("steal their shield codes", "harmonics"), ("disarm them", "weapons"),
    ("plant explosives", "charges"), ("look around", "survey"), ("bring one home, a prisoner", "rescue"),
    ("make tea", None),
])
def test_the_captains_words_name_a_task(words: str, task: str | None) -> None:
    assert away.task_from_words(words) == task


def test_only_big_federation_ships_carry_shuttles(content) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    assert away.has_shuttles(us)
    assert not away.has_shuttles(them)


def test_beaming_across_puts_them_aboard_at_once_and_seven_works_faster(content) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("seven", "worf"), "survey", by_shuttle=False)
    assert op.phase == "aboard" and op.shuttle is None
    assert op.work == pytest.approx(away.TASKS["survey"][0] * 0.75)
    assert us.away == {"seven", "worf"}
    assert collective.insight(w, us.side).heists == 1
    assert any(isinstance(e, HiveEvent) and e.kind == "boarded" for e in w.events)
    assert away.op_for(w, us.id) is op
    assert "beamed aboard" in _said(w)


def test_a_shuttle_flies_out_latches_on_and_comes_home(content, unseen) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("worf",), "weapons", by_shuttle=True)
    sh = w.ships[op.shuttle]
    assert op.phase == "outbound" and sh.name == away.SHUTTLE_NAMES[0] and sh.crew == 3
    assert away.op_for(w, sh.id) is op
    sh.x, sh.y = them.x, them.y - 500.0          # she has flown across
    away.update_away(w, 0.1)
    assert op.phase == "aboard" and sh.docked_to == them.id
    _work(w, op)
    assert op.result == "weapons wrecked" and op.phase == "return"
    assert all(b.damage == 100 for b in them.banks)
    sh.x, sh.y = us.x, us.y + 200.0              # and back again
    away.update_away(w, 0.1)
    assert op.phase == "done" and sh.status == ShipStatus.ESCAPED
    assert not us.away
    assert "back aboard" in _said(w)


def test_the_relay_task_puts_out_her_weak_point(content, unseen) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    weak = them.subsystem(them.weak_point)
    op = away.launch(w, us, them, ("worf",), "relay", by_shuttle=False)
    _work(w, op)
    assert op.result == "relay out" and weak is not None and weak.destroyed
    assert op.phase == "done"                    # no shuttle: they beam straight home


def test_seven_takes_the_harmonics_for_every_ship(content, unseen) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("seven",), "harmonics", by_shuttle=False)
    _work(w, op)
    ins = collective.insight(w, us.side)
    assert op.result == "harmonics taken" and ins.harmonics > 0 and ins.harmonic_faction == them.faction


def test_charges_start_her_countdown(content, unseen) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("worf",), "charges", by_shuttle=False)
    _work(w, op)
    assert op.result == "charges set" and them.self_destruct == away.CHARGE_FUSE and them.last_attacker == us.id


def test_a_survey_from_inside_gives_the_harmonics_and_weak_point(content, unseen) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("seven",), "survey", by_shuttle=False)
    _work(w, op)
    assert op.result == "survey done" and collective.insight(w, us.side).has_code(them.id)


def test_a_drone_comes_home_only_from_a_dormant_ship(content, unseen) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("worf",), "survey", by_shuttle=False)
    assert away.order(w, op, "task", "rescue") == "Not while they're awake, Captain."
    them.dormant = 60.0
    assert "bringing a drone home" in away.order(w, op, "task", "rescue")
    exp = collective.insight(w, us.side).experience
    _work(w, op)
    assert op.result == "drone rescued" and us.rescued == 1
    assert collective.insight(w, us.side).experience == pytest.approx(exp + 0.25)


def test_the_comm_to_the_team(content) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("worf",), "survey", by_shuttle=True)
    assert away.order(w, op, "task", "nonsense") == "Say again, Captain?"
    assert away.order(w, op, "task", "harmonics") == "We'd need Seven for that, Captain."
    assert away.order(w, op, "task", "weapons").startswith("Acknowledged")
    assert op.task == "weapons" and op.work == away.TASKS["weapons"][0]
    assert away.order(w, op, "recall") == "Understood. Breaking off and coming home."
    assert op.recalled and op.phase == "return"
    assert away.order(w, op, "recall") == "We're already on our way back, Captain."


def test_a_team_found_out_beams_home_hurt(content, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    monkeypatch.setattr(away, "NOTICE_QUIET", 1000.0)   # they will be found at once
    op = away.launch(w, us, them, ("worf", "geordi", "spock"), "survey", by_shuttle=False)
    away.update_away(w, 0.5)
    assert op.noticed and op.result == "caught: a drone found them" and op.phase == "done"
    assert us.wounded == {"worf", "geordi", "spock"} and us.mending == away.MEND_CYCLES
    assert "Worf, Geordi and Spock are in sickbay" in _said(w)


def test_a_shuttle_crew_caught_aboard_leaves_an_empty_shuttle_the_hive_watches(content, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("worf",), "survey", by_shuttle=True)
    sh = w.ships[op.shuttle]
    sh.x, sh.y = them.x, them.y
    away.update_away(w, 0.1)
    monkeypatch.setattr(away, "NOTICE_QUIET", 1000.0)
    away.update_away(w, 0.5)
    assert op.noticed and op.phase == "return" and op.members == () and sh.crew == 2
    assert sh.id in collective.mind(w, them.faction).noticed


def test_waking_drones_end_the_work(content, unseen) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    them.dormant = 0.5
    op = away.launch(w, us, them, ("worf",), "survey", by_shuttle=False)
    away.update_away(w, 0.5)
    assert op.result == "caught: the drones woke"
    w2, us2, them2 = _borg(content)
    them2.dormant = 60.0
    op2 = away.launch(w2, us2, them2, ("worf",), "rescue", by_shuttle=False)
    them2.dormant = 0.0
    away.update_away(w2, 0.5)
    assert op2.result == "caught: the drones woke"


def test_a_lost_shuttle_or_target_or_mother_ends_the_crossing(content, unseen) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("worf",), "survey", by_shuttle=True)
    w.ships[op.shuttle].status = ShipStatus.DESTROYED
    away.update_away(w, 0.1)
    assert op.result == "caught: the shuttle was destroyed"

    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("worf",), "survey", by_shuttle=True)
    them.status = ShipStatus.DESTROYED
    away.update_away(w, 0.1)
    assert op.phase == "return" and "the target is gone" in _said(w)

    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("worf",), "survey", by_shuttle=False)
    them.status = ShipStatus.DESTROYED
    away.update_away(w, 0.1)
    assert op.phase == "done" and "came apart around them" in _said(w)

    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("worf",), "survey", by_shuttle=False)
    us.status = ShipStatus.DESTROYED
    away.update_away(w, 0.1)
    assert op.phase == "done" and away.op_for(w, us.id) is None


def test_the_hive_watches_harder_when_the_decoy_goes_quiet(content) -> None:  # type: ignore[no-untyped-def]
    w, us, them = _borg(content)
    op = away.launch(w, us, them, ("worf",), "survey", by_shuttle=False)
    assert away.decoy_quiet(w, us, them.faction)          # nobody has hurt the hive yet
    quiet = away._notice_chance(w, op, us)
    collective.mind(w, them.faction).last_hurt[us.side] = w.tick
    busy = away._notice_chance(w, op, us)
    assert busy < quiet
    us.cloaked = True
    assert away.decoy_quiet(w, us, them.faction)
    us.cloaked = False
    collective.insight(w, us.side).heists = 3                # they have seen small craft before
    assert away._notice_chance(w, op, us) > busy
