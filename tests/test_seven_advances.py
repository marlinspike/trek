"""Seven's advancements (2026-11-14): Borg technology won on The Collective tour, which the officers offer to bring
online against the Borg, and the captain can order with `design sensors`, `design guided` or `design adaptive`."""

from __future__ import annotations

import dataclasses
from pathlib import Path

from begin.ai.captain import AICaptain
from begin.ai.personality import Personality
from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle, start
from begin.crew.proposals import candidates
from begin.core.rng import Rng
from begin.presets import load_presets
from begin.session.battle import BattleSession
from begin.sim import collective
from begin.sim.commands import LaunchProbe, Scan, StartProject
from begin.sim.events import Message
from begin.sim.ship import LoadedTorpedo
from begin.sim.systems.ordnance import launch_torpedoes
from begin.tools.tours import _default_escorts
from begin.tour import TourRun, load_tours
from begin.tour.state import TourState


def _borg(content, enemy: str = "borg.sp"):  # type: ignore[no-untyped-def]
    b = build_battle(content, BattleSetup([FleetSpec(0, [ShipSpec("federation.dn", x=0.0, y=0.0, course=0.0)], player=True),
                                           FleetSpec(1, [ShipSpec(enemy, x=0.0, y=9000.0, course=180.0)])], seed=3))
    w = b.world
    return b, w, w.ships[b.player_ship_id], next(s for s in w.ships.values() if s.side == 1)


def _design(w, us, project: str) -> None:  # type: ignore[no-untyped-def]
    w.execute(StartProject(ship_id=us.id, project=project))
    for _ in range(int(30 * w.rules.ticks_per_cycle)):
        if project in us.borg_tech:
            return
        w.step()


def _collective():  # type: ignore[no-untyped-def]
    return next(t for t in load_tours()[0] if t.id == "the-collective")


def test_seven_can_build_nothing_until_the_tour_gives_her_borg_technology(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, _ = _borg(content)
    w.execute(StartProject(ship_id=us.id, project="sensors"))
    assert "sensors" not in us.projects
    collective.insight(w, us.side).advances = {"sensors"}
    w.execute(StartProject(ship_id=us.id, project="sensors"))
    assert "sensors" in us.projects


def test_borg_sensors_double_what_each_scan_tells_us(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, them = _borg(content)
    collective.on_scan(w, us, them, "seven")
    plain = collective.insight(w, us.side).survey(them.id).progress
    collective.insight(w, us.side).surveys.clear()
    us.borg_tech.add("sensors")
    collective.on_scan(w, us, them, "seven")
    assert collective.insight(w, us.side).survey(them.id).progress == plain * collective.SENSOR_GAIN


def test_borg_tuned_torpedoes_fly_faster_at_a_hive_ship(content) -> None:  # type: ignore[no-untyped-def]
    def speed(guided: bool) -> float:
        _, w, us, them = _borg(content)
        if guided:
            us.borg_tech.add("guided")
        tube = us.tubes[0]
        spec = w.content.torpedoes[us.cls.torpedo]
        tube.loaded = LoadedTorpedo(spec.id, spec.max_prox)
        spec_speed = spec.velocity
        launch_torpedoes(w, us, [tube], them.id)
        return w.torpedoes[-1].velocity / spec_speed
    assert speed(True) > speed(False) * 1.3


def test_adaptive_shields_stop_their_transporters_at_once_and_survive_a_shift(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, them = _borg(content)
    collective.insight(w, us.side).advances = {"adaptive"}
    assert us.tuning == 0.0
    _design(w, us, "adaptive")
    assert "adaptive" in us.borg_tech
    assert us.tuning >= collective.TUNE_BLOCKS_BEAMING
    assert collective.can_beam_through(w, them, us) is not None
    rules = collective.rules_of(w, them)
    assert rules is not None
    collective.mind(w, them.faction).blocked = rules.shift_after * 10      # the hive shifts its beams
    collective.learn(w, us, them, "phaser", 10.0, 5.0)
    assert us.tuning >= collective.TUNE_BLOCKS_BEAMING


def test_seven_offers_her_advancements_and_the_counsel_plans_them(content, tmp_path: Path) -> None:  # type: ignore[no-untyped-def]
    setup = next(p for p in load_presets() if p.id == "borg-cube").setup()
    s = BattleSession(build_battle(content, setup), chatter=False, config=tmp_path)
    s.paused = False
    w = s.world
    me = w.ships[s.battle.player_ship_id]
    officers = {o.station: o for o in s.bridge.officers()}
    obs = w.observe(me.side)
    assert not any(p.line.startswith("design sensors") for p in candidates(obs, me, officers))
    collective.insight(w, me.side).advances = {"sensors", "guided", "adaptive"}
    obs = w.observe(me.side)
    offer = next(p for p in candidates(obs, me, officers) if p.line.startswith("design"))
    assert offer.station == "science" and offer.line == "design sensors"
    lines = [st.line for p in s.counsel(force=True) for st in p.steps]
    assert "design sensors" in lines
    s.run_console(offer.line)                              # what Y on the proposal runs
    assert "sensors" in me.projects
    s.close()


def _said(battle) -> list[str]:  # type: ignore[no-untyped-def]
    said: list[str] = []
    orig = battle.world.emit

    def emit(ev):  # type: ignore[no-untyped-def]
        if isinstance(ev, Message):
            said.append(ev.text)
        return orig(ev)
    battle.world.emit = emit
    return said


def test_the_collective_has_all_three_online_from_the_first_borg_battle(content) -> None:  # type: ignore[no-untyped-def]
    """Reuben (2026-11-14): "the Enterprise obviously needs its upgrades immediately"."""
    t = _collective()
    assert set(t.advances) == set(collective.ADVANCES)
    run = TourRun.new(t, content, _default_escorts(t, content), seed=2, difficulty="captain")
    assert run.state.advances == list(t.advances)
    battle = start(content, run.launch().setup, run.difficulty)
    said = _said(battle)
    run.prepare(battle)
    me = battle.world.ships[battle.player_ship_id]
    assert me.borg_tech == set(collective.ADVANCES)
    assert me.tuning >= collective.TUNE_BLOCKS_BEAMING
    assert any("advancements are online" in x for x in said)
    obs = battle.world.observe(me.side)
    assert not any(p.line.startswith("design") for p in candidates(obs, me, {}))   # nothing left to offer
    # a tour saved before the upgrades existed gets them too
    old = TourState.from_json({k: v for k, v in run.state.to_json().items() if k != "advances"})
    run2 = TourRun(t, old, content)
    battle = start(content, run2.launch().setup, run2.difficulty)
    run2.prepare(battle)
    assert battle.world.ships[battle.player_ship_id].borg_tech == set(collective.ADVANCES)


def test_a_stop_can_still_give_an_advancement_for_a_win(content) -> None:  # type: ignore[no-untyped-def]
    t = _collective()
    stops = (dataclasses.replace(t.stops[0], advances=("sensors",)),) + t.stops[1:]
    t = dataclasses.replace(t, advances=(), stops=stops)
    run = TourRun.new(t, content, _default_escorts(t, content), seed=2, difficulty="captain")
    battle = start(content, run.launch().setup, run.difficulty)
    run.prepare(battle)
    assert not battle.world.ships[battle.player_ship_id].borg_tech
    w = battle.world
    for s in list(w.ships.values()):
        if s.side != w.player_side:
            w.destroy_ship(s, "test", None)
    w.step()
    entry = run.finish(battle)
    assert run.state.advances == ["sensors"]
    assert "design sensors" in entry.stations["seven"]
    battle = start(content, run.launch().setup, run.difficulty)
    run.prepare(battle)
    assert battle.world.ships[battle.player_ship_id].borg_tech == {"sensors"}


def test_old_saves_load_with_no_advancements() -> None:
    d = TourState("the-collective").to_json()
    d.pop("advances")
    assert TourState.from_json(d).advances == []


def test_a_careful_captain_never_launches_a_probe_their_beams_can_burst_on_us(content) -> None:  # type: ignore[no-untyped-def]
    """At the Kerrigan Rift the officers fired probes at a sphere 2,500 out: her beams burst them beside the
    Enterprise, and the blasts killed her. A competent captain keeps probes for targets that can't do that."""
    launched = {}
    for competence in (0.9, 0.2):
        b = build_battle(content, BattleSetup([FleetSpec(0, [ShipSpec("federation.dn", x=0.0, y=0.0, course=0.0)], player=True),
                                               FleetSpec(1, [ShipSpec("klingon.bc", x=0.0, y=2600.0, course=180.0)])], seed=3))
        w = b.world
        us = w.ships[b.player_ship_id]
        them = next(s for s in w.ships.values() if s.side == 1)
        p = dataclasses.replace(Personality.roll(content.factions["federation"], Rng(1)), competence=competence,
                                aggression=1.0)
        cap = AICaptain(us.id, us.side, p, Rng(2))
        n = 0
        for k in range(200):
            if k % 40 == 0:
                w.execute(Scan(ship_id=us.id, target=them.id))
            for bank in them.banks:
                bank.charge = 0.0                          # no charged banks: Begin's cue to launch a probe
            them.desired_warp = 0.0
            them.x, them.y = 0.0, us.y + 2600.0            # inside her beams' reach of the probe's blast
            for c in cap.think(w.observe(us.side)):
                n += isinstance(c, LaunchProbe)
                w.execute(c)
            w.step()
        launched[competence] = n
    assert launched[0.9] == 0 and launched[0.2] > 0


def test_borg_tuned_torpedoes_hit_harder_and_the_hive_learns_them_slowly(content) -> None:  # type: ignore[no-untyped-def]
    """Reuben asked (2026-11-14) whether they were explosive enough. They weren't: the cube learned them in full
    in every fight, after which each hit did a quarter of its damage."""
    def after(guided: bool) -> tuple[float, float]:
        _, w, us, them = _borg(content, "borg.cu")
        if guided:
            us.borg_tech.add("guided")
        first = collective.incoming(w, them, us, "torpedo")[0]
        collective.learn(w, them, us, "torpedo", 500.0, 500.0)
        return first, collective.mind(w, them.faction).level(collective.weapon_key("torpedo", us))
    (plain_hit, plain_learned), (tuned_hit, tuned_learned) = after(False), after(True)
    assert tuned_hit == plain_hit * collective.GUIDED_DAMAGE
    assert tuned_learned < plain_learned * 0.5


def test_officers_aim_at_a_found_relay_and_load_harmonics_once_cracked(content) -> None:  # type: ignore[no-untyped-def]
    from begin.sim.commands import TakeConn

    _, w, us, them = _borg(content, "borg.sp")
    w.execute(TakeConn(ship_id=us.id, officer="spock"))
    for _ in range(40):
        collective.on_scan(w, us, them, "seven")             # her relay and her harmonics are ours
    aimed = harmonics = False
    for _ in range(int(30 * w.rules.ticks_per_cycle)):
        w.step()
        aimed = aimed or (us.target == them.id and us.target_subsystem == "relay")
        harmonics = harmonics or "harmonic" in us.projects or any(
            t.loaded is not None and t.loaded.ordnance == "harmonic" for t in us.tubes)
        if aimed and harmonics:
            break
    assert aimed and harmonics
