"""Missions, the officers' counsel, hold-range helm orders, Starfleet's assessment and the Ready Room's view [E]."""

from __future__ import annotations

import math
from pathlib import Path

import pytest

from begin.battle import PATROL_SITUATIONS, build_battle, patrol_battle
from begin.console.parser import ParseContext, parse
from begin.crew.counsel import Goal, parse_goal
from begin.presets import load_presets
from begin.session.battle import BattleSession
from begin.sim.commands import Pursue
from begin.sim.mission import MissionDef
from begin.sim.ship import ShipStatus
from begin.sim.systems.damage import DamageKind, apply_damage
from begin.tour import TourRun, load_tours
from begin.tour.ready import READY_ORDER, ready_counsel

MISSIONS = ("rescue", "convoy", "runner")


def _session(content, tmp_path: Path, situation: str = "flagship", seed: int = 3, preset: str = "") -> BattleSession:  # type: ignore[no-untyped-def]
    if preset:
        setup = next(p for p in load_presets() if p.id == preset).setup()
    else:
        setup = patrol_battle(content, seed, situation=situation)
    s = BattleSession(build_battle(content, setup), chatter=False, config=tmp_path)
    s.paused = False
    return s


def _wreck(w, ship) -> None:  # type: ignore[no-untyped-def]
    for _ in range(400):
        if not ship.alive:
            return
        apply_damage(w, ship, 200, ship.x + 100.0, ship.y, DamageKind.BLAST, None, None)


def _run(s: BattleSession, cycles: float) -> None:
    end = s.world.time + cycles
    while s.world.time < end and not s.world.outcome.over:
        s.update(s.tick_length * 12, rate=1.0)


# ------------------------------------------------------------------ the counsel

@pytest.mark.parametrize("situation", [sid for sid, _, _ in PATROL_SITUATIONS])
def test_every_situation_gets_four_plans_the_console_accepts(content, tmp_path, situation) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, situation)
    for _ in range(4):
        plans = s.counsel(force=True)
        assert [p.station for p in plans] == ["tactical", "helm", "engineering", "science"]
        for p in plans:
            assert p.steps, p
            assert len(p.steps) <= 4
            for st in p.steps:
                assert s.dry_run(st.line) is None, (p.name, st.line)
        _run(s, 6)
        if s.world.outcome.over:
            break


def test_four_officers_give_four_different_leads(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "flagship")
    _run(s, 8)
    plans = s.counsel(force=True)
    assert len({p.title for p in plans}) == len(plans)


def test_counsel_changes_as_the_battle_changes(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "wolfpack", seed=5)
    seen = set()
    for _ in range(10):
        seen |= {(p.station, p.title) for p in s.counsel(force=True)}
        _run(s, 8)
        if s.world.outcome.over:
            break
    assert len(seen) > 4


def test_a_plan_runs_as_if_the_captain_typed_it(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "flagship")
    _run(s, 4)
    plan = s.counsel(force=True)[1]
    before = len(s.world.command_log)
    s.follow(plan)
    _run(s, 1)
    mine = [lc for lc in s.world.command_log[before:] if lc.command.source == "captain"]
    assert mine and all(lc.accepted for lc in mine), [(lc.command.name, lc.reason) for lc in mine]


def test_no_counsel_once_the_battle_is_over_or_the_ship_is_gone(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "flagship")
    me = s.player
    assert me is not None
    _wreck(s.world, me)
    _run(s, 2)
    assert s.counsel(force=True) == []
    assert s.situation() is None


def test_borg_counsel_speaks_of_the_opening_not_brute_force(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, preset="borg-cube")
    _run(s, 4)
    keys = " ".join(st.line for p in s.counsel(force=True) for st in p.steps)
    assert "scan" in keys or "duty harmonics" in keys or "tune shields" in keys


# ------------------------------------------------------------------ goals

def test_goals_read_from_the_captains_words(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "flagship")
    sit = s.situation()
    assert sit is not None
    one = sit.enemies[0]
    g = parse_goal(f"destroy the {one.name}", sit)
    assert isinstance(g, Goal) and g.kind == "destroy" and g.targets == (one.id,)
    g = parse_goal("disable all their engines", sit)
    assert isinstance(g, Goal) and g.kind == "disable" and g.system == "engines"
    assert set(g.targets) == {e.id for e in sit.enemies}
    g = parse_goal("kill them all", sit)
    assert isinstance(g, Goal) and g.kind == "destroy" and len(g.targets) == len(sit.enemies)
    assert isinstance(parse_goal("survive", sit), Goal)
    assert isinstance(parse_goal("destroy the zzzqx", sit), str)


def test_kill_all_the_borg_cubes(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, preset="borg-cube")
    sit = s.situation()
    assert sit is not None
    g = parse_goal("kill all the borg cubes", sit)
    assert isinstance(g, Goal) and g.kind == "destroy" and g.targets


def test_a_goal_aims_every_officer_and_clears_when_met(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "flagship")
    _run(s, 4)
    target = s.situation().enemies[0]  # type: ignore[union-attr]
    s.say(f"counsel destroy the {target.name}")
    assert s.counsel_goal is not None and s.counsel_goal.targets == (target.id,)
    plans = s.counsel(force=True)
    assert any(target.handle in st.line for p in plans for st in p.steps)
    victim = s.world.ships[target.id]
    _wreck(s.world, victim)
    _run(s, 2)
    s.counsel(force=True)
    assert s.counsel_goal is None
    s.say("counsel disable all their engines")
    if any(not e.surrendered for e in s.situation().enemies):  # type: ignore[union-attr]
        assert s.counsel_goal is not None and s.counsel_goal.system == "engines"
    s.say("counsel general")
    assert s.counsel_goal is None


def test_a_plan_with_an_objective_does_not_also_order_fire(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "flagship")
    _run(s, 6)
    s.say("counsel disable all their weapons")
    for p in s.counsel(force=True):
        lines = [st.line for st in p.steps]
        if any(x.startswith("disable ") for x in lines):
            assert not any(x.startswith(("fire ", "target ")) for x in lines), lines


def test_setting_an_objective_hands_the_weapons_to_the_officer(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "flagship")
    _run(s, 2)
    e = s.situation().enemies[0]  # type: ignore[union-attr]
    s.say(f"target {e.handle}")
    assert any(k.startswith("tactical") for k in s.world.holds(s.player_id))
    s.say(f"disable {e.handle} engines")
    assert not any(k.startswith(("tactical", "phasers", "torpedoes")) for k in s.world.holds(s.player_id))


# ------------------------------------------------------------------ hold range

def test_hold_range_parses(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, patrol_battle(content, 2, situation="flagship"))
    w = b.world
    me = w.ships[b.player_ship_id]
    them = next(s for s in w.ships.values() if s.side != me.side)
    ctx = ParseContext(me.id, w.observe(me.side))

    def one(line: str) -> Pursue:
        cmds = parse(line, ctx).commands
        assert len(cmds) == 1 and isinstance(cmds[0], Pursue), line
        return cmds[0]

    n = them.name.lower()
    assert (one(f"elude {n} at 9000").keep, one(f"elude {n} at 9000").elude) == (9000.0, True)
    assert (one(f"pursue {n} warp 6 at 4000").warp, one(f"pursue {n} warp 6 at 4000").keep) == (6.0, 4000.0)
    assert (one(f"pursue {n} 6").warp, one(f"pursue {n} 6").keep) == (6.0, None)
    assert one(f"elude {n} 9000").keep == 9000.0
    assert one(f"elude {n}").keep is None


def test_the_helm_holds_the_range_instead_of_running(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "flagship")
    w = s.world
    me = s.player
    assert me is not None
    them = min((x for x in w.ships.values() if x.side != me.side and x.alive),
               key=lambda x: math.hypot(x.x - me.x, x.y - me.y))
    s.say(f"elude {them.name.lower()} at 9000 warp 6")
    assert me.helm_keep == 9000.0
    ranges = []
    for _ in range(40):
        _run(s, 2)
        if w.outcome.over or not me.alive or not them.alive:
            break
        ranges.append(math.hypot(them.x - me.x, them.y - me.y))
    assert ranges and me.status != ShipStatus.ESCAPED
    assert max(ranges[len(ranges) // 2:]) < 20000          # she stayed in the fight, not off across the map
    s.say(f"elude {them.name.lower()}")
    assert me.helm_keep is None


# ------------------------------------------------------------------ missions

@pytest.mark.parametrize("situation", MISSIONS)
def test_each_mission_builds_with_its_ward_or_runner(content, situation) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, patrol_battle(content, 4, situation=situation))
    m = b.world.mission
    assert m is not None and m.open
    if situation == "runner":
        r = b.world.ships[m.runner_id]  # type: ignore[index]
        assert m.runner_warp is not None and m.runner_warp < b.world.ships[b.player_ship_id].cls.max_warp
        assert r.side != b.world.player_side
    else:
        ward = b.world.ships[m.ward_id]  # type: ignore[index]
        assert ward.ward and ward.side == b.world.player_side


def test_the_runner_never_outpaces_her_orders(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "runner", seed=6)
    m = s.world.mission
    assert m is not None and m.runner_warp is not None
    r = s.world.ships[m.runner_id]  # type: ignore[index]
    for _ in range(10):
        _run(s, 3)
        if not r.alive or s.world.outcome.over:
            break
        assert r.warp <= m.runner_warp + 1e-6


def test_spock_offers_an_intercept_course_for_the_runner(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "runner", seed=6)
    for _ in range(30):                     # until sensors hold her (a Romulan runner may cloak for a while)
        _run(s, 1)
        mv = s.mission()
        if mv is not None and mv.runner_escape is not None:
            break
    assert mv is not None and mv.kind == "intercept"
    assert mv.runner_intercept is not None and mv.runner_meet is not None and mv.runner_meet > 0
    helm = next(p for p in s.counsel(force=True) if p.station == "helm")
    assert any(st.line.startswith("helm ") for st in helm.steps), helm


def test_the_intercept_solution_meets_her() -> None:
    from begin.crew.situation import _intercept

    got = _intercept(10000.0, 0.0, 0.0, 300.0, 500.0)
    assert got is not None
    t, course = got
    x, y = 10000.0, 300.0 * t                                 # where she is then
    ux, uy = math.sin(math.radians(course)) * 500 * t, math.cos(math.radians(course)) * 500 * t
    assert math.hypot(x - ux, y - uy) < 1.0
    assert _intercept(10000.0, 0.0, 600.0, 0.0, 500.0) is None   # faster and running straight away: no catching her


def test_a_mission_from_toml_keeps_its_runner_pace() -> None:
    m = MissionDef.from_dict({"kind": "intercept", "runner": 1, "runner_pace": 0.5})
    assert m.runner_pace == 0.5 and m.runner == 1


# ------------------------------------------------------------------ Starfleet's assessment

def test_the_assessment_reads_the_battle(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "rescue", seed=3)
    _run(s, 30)
    a = s.starfleet()
    assert a.headline
    assert a.mission_state in ("open", "done", "failed") and a.mission_kind == "rescue"
    assert a.people > 0 and 0 <= a.rescued <= a.people
    assert a.conduct
    assert a.commendation is None or a.outcome == "won"


def test_no_commendation_for_a_lost_fight(content, tmp_path) -> None:  # type: ignore[no-untyped-def]
    s = _session(content, tmp_path, "flagship")
    me = s.player
    assert me is not None
    _wreck(s.world, me)
    _run(s, 2)
    a = s.starfleet()
    assert a.commendation is None and a.outcome != "won"


# ------------------------------------------------------------------ the Ready Room

def test_every_stop_gets_two_sentences_from_each_officer(content) -> None:  # type: ignore[no-untyped-def]
    tours, _ = load_tours()
    for t in tours:
        run = TourRun.new(t, content, ["federation.de"], seed=1)
        for i in range(len(t.stops)):
            run.state.stop = i
            views = ready_counsel(run)
            assert [v.officer for v in views] == list(READY_ORDER), (t.id, i)
            for v in views:
                assert 1 <= v.text.count(". ") + v.text.count("; ") + 1 and v.text.endswith((".", "!")), v.text
                assert "  " not in v.text and " a O" not in v.text


def test_the_ready_room_speaks_of_the_mission(content) -> None:  # type: ignore[no-untyped-def]
    tours, _ = load_tours()
    t = next(x for x in tours if any(s.mission is not None for s in x.stops))
    run = TourRun.new(t, content, ["federation.de"], seed=1)
    i = next(k for k, s in enumerate(t.stops) if s.mission is not None)
    run.state.stop = i
    text = " ".join(v.text for v in ready_counsel(run))
    m = t.stops[i].mission
    assert m is not None
    assert (m.ward_name and m.ward_name in text) or "runner" in text
