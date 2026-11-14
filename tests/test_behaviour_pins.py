"""Pins on exactly what some long functions did before they were broken up [E].

Readbacks, the Ready Room's counsel, the AI captains' standing orders and manoeuvres, the names and lines the map
draws beside ships, and the command line were each one long function. These tests were written against the old
functions, cover the branches the rest of the suite left thin, and keep the smaller functions saying and doing the
same. A test here that fails after a change means the change altered behaviour; if that was the intent, update the
pinned value.
"""

from __future__ import annotations

import dataclasses
import math

import pygame
import pytest

from begin.ai.captain import AICaptain
from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle
from begin.console.readback import readback
from begin.sim.allies import AllyStanding
from begin.sim.commands import (
    AllyOrder, CeaseFire, Command, ConfigureAutoload, DelegateStation, DeflectorPulse, Dock, EndObjective, EngineBoost,
    Evasive, FireBait, FirePhasers, FireTorpedoes, LaunchProbe, LoadTubes, LockWeapons, ManageRepairs, OpenFire, Pursue,
    ReinforceShield, Remodulate, Scan, SelectTarget, SelfDestruct, SetBanks, SetCloak, SetHelm, SetObjective,
    SetPhaserSpread, SetPointDefense, SetRepairPriority, SetShields, StandDown, StartProject, Surrender, TakeConn, Tractor,
    Transport, TurnMounts,
)
from begin.sim.ship import BankRole, PDDoctrine
from begin.tour import TourRun, load_tours
from begin.tour.ready import ready_counsel

NAMES = {7: "Hydra", 8: "Kestrel", 9: "Agena"}


def _name(sid: int) -> str:
    return NAMES.get(sid, f"#{sid}")


# ------------------------------------------------------------------ readbacks: one case for every phrase

READBACKS: list[tuple[Command, str]] = [
    (SetHelm(ship_id=1, course=359.6), "Course 000."),
    (SetHelm(ship_id=1), "Holding course."),
    (SetHelm(ship_id=1, course=None, warp=2.5), "Warp 2.5."),
    (SetHelm(ship_id=1, course=90, warp=0.0), "Course 090, warp 0."),
    (Pursue(ship_id=1, target=8), "Pursuing the Kestrel."),
    (Evasive(ship_id=1, on=False), "Evasive manoeuvres ended."),
    (Evasive(ship_id=1, on=True), "Evasive manoeuvres; I'll dodge their torpedoes."),
    (Dock(ship_id=1, host=9), "Docking with the Agena."),
    (Dock(ship_id=1, host=None), "Undocking."),
    (FirePhasers(ship_id=1, banks=(3,), at_bearing=45.0), "Firing phaser 4 on bearing 045."),
    (FirePhasers(ship_id=1, target=None, spread=12.5), "Firing all phasers at the target, spread 12.5."),
    (FireBait(ship_id=1, target=7), "One torpedo as bait at the Hydra, the rest to follow."),
    (FireTorpedoes(ship_id=1, tubes=(0, 1), count=1, target=7, subsystem="hull"), "Firing 1 torpedo at the Hydra."),
    (FireTorpedoes(ship_id=1, count=3, target=None), "Firing 3 torpedoes at the target."),
    (LaunchProbe(ship_id=1, course=90.0), "Launching a probe on course 090."),
    (LaunchProbe(ship_id=1, target=8, count=2), "Launching 2 probes at the Kestrel."),
    (LaunchProbe(ship_id=1), "Launching a probe at the target."),
    (SelectTarget(ship_id=1, target=None), "Target cleared."),
    (SelectTarget(ship_id=1, target=7, subsystem="engines", lock_weapons=True),
     "Targeting the Hydra, aiming for her engines; weapons locked."),
    (SelectTarget(ship_id=1, target=7, subsystem="hull"), "Targeting the Hydra; weapons locked."),
    (LockWeapons(ship_id=1, target=7, banks=(0, 1, 3), tubes=(2,), torpedoes=True),
     "Phasers 1, 2 and 4 and tube 3 locked on the Hydra."),
    (LockWeapons(ship_id=1, target=None, phasers=False), "Weapons locked on the target."),
    (TurnMounts(ship_id=1, mark=12.5), "Turning mounts to mark 12.5."),
    (SetPhaserSpread(ship_id=1, spread=20.0), "Phaser spread 20."),
    (SetBanks(ship_id=1, banks=(0,), enabled=False), "Phaser 1 disabled."),
    (SetBanks(ship_id=1, enabled=True), "all Phasers enabled."),
    (SetBanks(ship_id=1, banks=(1, 2), role=BankRole.DEFENSE), "Phasers 2 and 3 set to defense."),
    (LoadTubes(ship_id=1, tubes=(1,), unload=True), "Unloading tube 2."),
    (LoadTubes(ship_id=1, weapon="launcher"), "Loading all launchers."),
    (ConfigureAutoload(ship_id=1, weapon="tube", enabled=False), "Autoload off for the tubes."),
    (ConfigureAutoload(ship_id=1, weapon="launcher", ordnance="mk7"), "Autoload on for the launchers with MK7."),
    (SetPointDefense(ship_id=1, doctrine=PDDoctrine.OFF), "Point defense off."),
    (SetShields(ship_id=1, sectors=None, up=True), "Raising all shields."),
    (SetShields(ship_id=1, sectors=(0, 5), up=False), "Lowering shields 1 and 6."),
    (ReinforceShield(ship_id=1, sector=None), "Shield reinforcement off."),
    (ReinforceShield(ship_id=1, sector=2), "Reinforcing shield 3."),
    (SetRepairPriority(ship_id=1, kind=None), "Repair crews spread across the ship."),
    (SetRepairPriority(ship_id=1, kind="tubes"), "Repair crews to the tubes first."),  # type: ignore[arg-type]
    (ManageRepairs(ship_id=1, officer=True), "Repairs are mine, Captain."),
    (ManageRepairs(ship_id=1, officer=False), "Repair crews answer to you, Captain."),
    (SetCloak(ship_id=1, on=True), "Cloaking."),
    (SetCloak(ship_id=1, on=False), "Decloaking."),
    (Scan(ship_id=1, target=8), "Scanning the Kestrel."),
    (SetObjective(ship_id=1, goal="disable", group="engines", targets=(7,)),
     "Knocking out the engines on the Hydra, then sparing her."),
    (SetObjective(ship_id=1, goal="disable", group="shields", targets=(7, 8)), "Knocking out the shields on 2 ships."),
    (SetObjective(ship_id=1, goal="hunt", targets=(8,)), "Hunting for the Kestrel."),
    (SetObjective(ship_id=1, goal="strike", group="hull", targets=(7,)),
     "Sweep and strike: the moment the seeker lands, a salvo into the Hydra."),
    (SetObjective(ship_id=1, goal="strike", group="shields", targets=(7, 8, 9)),
     "Sweep and strike: the moment the seeker lands, a salvo into 3 ships's shields."),
    (SetObjective(ship_id=1, goal="capture", targets=(7,)), "Standing order: capture the Hydra."),
    (EndObjective(ship_id=1), "Standing order ended."),
    (StartProject(ship_id=1, project="seeker"), "Starting work on the seeker."),
    (DeflectorPulse(ship_id=1), "Pulsing the deflector."),
    (EngineBoost(ship_id=1, on=True), "A team to the engines. Other repairs slow while they work."),
    (EngineBoost(ship_id=1, on=False), "Engine team back to repairs."),
    (CeaseFire(ship_id=1), "Ceasing fire. Point defense stays on."),
    (OpenFire(ship_id=1), "Weapons free."),
    (StandDown(ship_id=1), "Standing down. Every station is yours."),
    (DelegateStation(ship_id=1, station="helm"), "Helm is mine, Captain."),
    (DelegateStation(ship_id=1, station="comms", on=False), "Comms is yours, Captain."),
    (TakeConn(ship_id=1, officer=True), "I have the bridge."),
    (TakeConn(ship_id=1, officer=False), "You have the bridge, Captain."),
    (Tractor(ship_id=1, target=9), "Tractor beam on the Agena."),
    (Tractor(ship_id=1, target=None), "Tractor beam released."),
    (Transport(ship_id=1, target=7, count=20), "Beaming 20 to the Hydra."),
    (AllyOrder(ship_id=1, ally=9, order="attack", target=7), "Signalling the Agena: attack on the Hydra."),
    (AllyOrder(ship_id=1, ally=9, order="stop"), "Signalling the Agena: stop."),
    # orders without a phrase of their own fall back to the command's own description
    (Surrender(ship_id=1), "Surrender."),
    (SelfDestruct(ship_id=1, cycles=5.0), "Destruct."),
    (Remodulate(ship_id=1), "Remodulate phasers."),
]


@pytest.mark.parametrize(("cmd", "said"), READBACKS, ids=[f"{type(c).__name__}-{i}" for i, (c, _) in enumerate(READBACKS)])
def test_every_readback_phrase(cmd: Command, said: str) -> None:
    assert readback(cmd, _name) == said


# ------------------------------------------------------------------ the Ready Room, on stops the shipped tours don't have

def _ready(content, enemies: tuple[str, ...], escorts: list[str], flagship: str | None = None, torps: int | None = None,
           calls: int | None = None) -> dict[str, str]:  # type: ignore[no-untyped-def]
    tours, _ = load_tours()
    t = next(x for x in tours if x.id == "border-patrol")
    stop = dataclasses.replace(t.stops[0], enemies=enemies, choices=(), waves=(), mission=None, add={}, drop={})
    tour = dataclasses.replace(t, stops=(stop,) + t.stops[1:], flagship=flagship or t.flagship,
                               resupply=0.0 if torps is not None else t.resupply)
    run = TourRun.new(tour, content, escorts, seed=1)
    run.state.stop = 0
    if torps is not None:
        for r in run.state.squadron:
            r.torps = torps
    if calls is not None:
        run.state.calls_left = calls
    return {v.officer: v.text for v in ready_counsel(run)}


def test_the_ready_room_before_an_empty_rendezvous(content) -> None:  # type: ignore[no-untyped-def]
    said = _ready(content, (), ["federation.de"])
    assert said["worf"] == "Sensors show no enemy at the rendezvous yet. I do not trust an empty sky."
    assert said["spock"] == "With no contact to plot, I will hold a course that keeps our options open."
    assert said["geordi"] == ("Every ship should arrive at full strength. The Sirius carries only 35 torpedoes; she will run "
                              "dry long before we do, so her salvos are for finishing a ship, not long shots.")
    assert said["seven"] == ("Sensors read nothing at the rendezvous. A full scan early will show where their shields are "
                             "weakest.")


def test_the_ready_room_before_one_ship_and_before_two_alike(content) -> None:  # type: ignore[no-untyped-def]
    one = _ready(content, ("federation.de",), ["federation.de"])
    assert one["worf"] == ("We have the stronger force. Press them hard and they will break. Bring every tube to bear on "
                           "her and do not let her recharge.")
    assert one["spock"] == ("I expect a conventional approach; the first exchange will be decided by who controls the "
                            "range.")
    assert one["seven"] == ("Sensors read a Federation destroyer at the rendezvous. A full scan early will show where "
                            "their shields are weakest.")
    two = _ready(content, ("federation.de", "federation.de"), ["federation.de"])
    assert two["worf"] == ("We have the stronger force. Press them hard and they will break. Concentrate on one ship at a "
                           "time; a wounded enemy still fires, a destroyed one does not.")
    assert two["seven"] == ("Sensors read two Federation ships at the rendezvous: two destroyers. A full scan early will "
                            "show where their shields are weakest.")


def test_the_ready_room_on_low_magazines_and_on_calling_starfleet(content) -> None:  # type: ignore[no-untyped-def]
    foes = ("klingon.bc", "klingon.fr")
    low = _ready(content, foes, [], flagship="federation.hc", torps=5)
    assert low["worf"] == ("The odds are close to even. The side that concentrates its fire will carry the day. Destroy "
                           "the battle cruiser first; without her the rest are only escorts.")
    assert low["geordi"] == "The Enterprise should arrive at full strength. We are down to 5 torpedoes; make every one count."
    assert low["seven"] == ("Sensors read two Klingon ships at the rendezvous: a battle cruiser and a frigate. A full scan "
                            "early will show where their shields are weakest.")
    call = _ready(content, foes, [], flagship="federation.hc")
    assert call["geordi"] == "The Enterprise should arrive at full strength. Call Starfleet now and their ship meets us there."
    quiet = _ready(content, foes, [], flagship="federation.hc", calls=0)
    assert quiet["geordi"] == "The Enterprise should arrive at full strength. Engineering is ready for whatever you need."


# ------------------------------------------------------------------ AI captains: standing orders and the helm

def _fleet(content, enemy_at: tuple[float, float] = (0.0, 30000.0)):  # type: ignore[no-untyped-def]
    setup = BattleSetup([
        FleetSpec(0, [ShipSpec("federation.hc", "Enterprise", 0, 0, 0),
                      ShipSpec("federation.de", "Agena", 2000, 0, 0),
                      ShipSpec("federation.de", "Terra", -2000, 0, 0),
                      ShipSpec("federation.sb", "Rigel", 0, -8000, 0)], player=True),
        FleetSpec(1, [ShipSpec("klingon.fr", "Zantha", enemy_at[0], enemy_at[1], 180)]),
    ], seed=3)
    b = build_battle(content, setup)
    w = b.world
    ships = {s.name: s for s in w.ships.values()}
    caps = {c.ship_id: c for c in w.controllers if isinstance(c, AICaptain)}
    return w, ships, caps


def test_a_base_brings_aboard_a_ship_alongside(content) -> None:  # type: ignore[no-untyped-def]
    w, ships, caps = _fleet(content)
    rigel, terra = ships["Rigel"], ships["Terra"]
    terra.x, terra.y = rigel.x + 100.0, rigel.y
    out: list[Command] = []
    decided = caps[rigel.id]._standing_orders(w.observe(0), rigel, None, AllyStanding(recover=terra.id), out)
    assert decided is False
    assert len(out) == 1 and isinstance(out[0], Dock) and out[0].ship_id == terra.id and out[0].host == rigel.id
    assert out[0].source == "Rigel recovery"


def test_a_withdrawal_with_no_enemy_in_sight_holds_still(content) -> None:  # type: ignore[no-untyped-def]
    w, ships, caps = _fleet(content, enemy_at=(0.0, 400000.0))
    agena = ships["Agena"]
    obs = w.observe(0)
    assert not [h for h in obs.hostile_contacts() if h.visible]
    out: list[Command] = []
    assert caps[agena.id]._standing_orders(obs, agena, None, AllyStanding(movement="withdraw"), out) is True
    assert len(out) == 1 and isinstance(out[0], SetHelm) and out[0].warp == 0.0
    assert out[0].course == pytest.approx(agena.desired_course % 360.0)


@pytest.mark.parametrize("standing", [
    AllyStanding(movement="escort", move_target=999),                  # her charge is gone
    AllyStanding(movement="dance", move_target=1),                     # no such order
])
def test_orders_about_a_ship_we_cannot_place_leave_the_helm_alone(content, standing: AllyStanding) -> None:  # type: ignore[no-untyped-def]
    w, ships, caps = _fleet(content)
    agena = ships["Agena"]
    if standing.movement == "dance":
        standing = dataclasses.replace(standing, move_target=ships["Terra"].id)
    out: list[Command] = []
    assert caps[agena.id]._standing_orders(w.observe(0), agena, None, standing, out) is False
    assert out == []


def test_a_tow_with_nowhere_to_go_and_a_boarding_with_nobody_to_board(content) -> None:  # type: ignore[no-untyped-def]
    w, ships, caps = _fleet(content)
    agena, terra = ships["Agena"], ships["Terra"]
    agena.tractor_target = terra.id
    out: list[Command] = []
    tow = AllyStanding(movement="tow", move_target=terra.id, destination=999)
    assert caps[agena.id]._standing_orders(w.observe(0), agena, None, tow, out) is False
    assert out == []
    board = AllyStanding(movement="board", move_target=terra.id)      # one of ours: never a contact to board
    assert caps[agena.id]._standing_orders(w.observe(0), agena, None, board, out) is False
    assert out == []


def test_a_last_stand_rams_her_at_full_warp(content) -> None:  # type: ignore[no-untyped-def]
    w, ships, caps = _fleet(content, enemy_at=(3000.0, 6000.0))
    w.run(1.0)
    zantha = ships["Zantha"]
    cap = caps[zantha.id]
    obs = w.observe(zantha.side)
    c = next(k for k in obs.contacts().values() if k.visible)
    cap.last_stand, cap.retreating, cap.pressing, cap.smart = True, False, False, False
    cap.last_helm = None
    cmd = cap._maneuver(obs, zantha, c)
    assert isinstance(cmd, SetHelm)
    want = math.degrees(math.atan2(c.x - zantha.x, c.y - zantha.y)) % 360.0
    assert cmd.course == pytest.approx(want, abs=1e-6)
    assert cmd.warp == pytest.approx(zantha.max_attainable_warp)


def test_a_contact_of_unknown_class_is_weighed_as_a_middling_ship(content) -> None:  # type: ignore[no-untyped-def]
    w, ships, caps = _fleet(content, enemy_at=(3000.0, 6000.0))
    w.run(1.0)
    zantha = ships["Zantha"]
    cap = caps[zantha.id]
    cap.personality = dataclasses.replace(cap.personality, style="")    # no signature tactic: the weapons decide
    cap.smart = False
    obs = w.observe(zantha.side)
    c = next(k for k in obs.contacts().values() if k.visible)
    for cls in (c.cls, None):
        cap.last_helm = None
        cmd = cap._maneuver(obs, zantha, dataclasses.replace(c, cls=cls))
        assert isinstance(cmd, SetHelm)
        assert (round(cmd.course, 4), round(cmd.warp, 4)) == (207.9679, 6.72)


# ------------------------------------------------------------------ the map: what is written beside each ship

@pytest.fixture
def written(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    from begin.ui import tactical

    said: list[str] = []
    real_label, real_text = tactical.theme.label, tactical.theme.text

    def label(surf, text, *a, **k):  # type: ignore[no-untyped-def]
        said.append(text)
        return real_label(surf, text, *a, **k)

    def text(surf, s, *a, **k):  # type: ignore[no-untyped-def]
        said.append(s)
        return real_text(surf, s, *a, **k)

    monkeypatch.setattr(tactical.theme, "label", label)
    monkeypatch.setattr(tactical.theme, "text", text)
    return said


def _map(content):  # type: ignore[no-untyped-def]
    from begin.ui.camera import Camera
    from begin.ui.tactical import TacticalView

    pygame.init()
    b = build_battle(content, BattleSetup([
        FleetSpec(0, [ShipSpec("federation.dn", "Enterprise", 0.0, 0.0, 0.0), ShipSpec("federation.de", "Agena", 2500.0, 0.0, 0.0)],
                  player=True),
        FleetSpec(1, [ShipSpec("klingon.bc", "Gorkon", 0.0, 5000.0, 180.0)])], seed=3))
    w = b.world
    w.run(2.0)
    view = TacticalView(Camera(pygame.Rect(0, 0, 900, 600), zoom=0.05))
    surf = pygame.Surface((900, 600))
    overlay = pygame.Surface((900, 600), pygame.SRCALPHA)
    return w, view, surf, overlay


def _flush(view) -> None:  # type: ignore[no-untyped-def]
    view._place_names()
    for name in view._names:
        name()
    view._names = []


def test_what_the_map_writes_beside_a_contact(content, written: list[str]) -> None:  # type: ignore[no-untyped-def]
    w, view, surf, overlay = _map(content)
    obs = w.observe(0)
    c = next(iter(obs.contacts().values()))
    cases = [
        (c, ["Gorkon (BC)"]),
        (dataclasses.replace(c, visible=False, age=7.0), ["Gorkon (BC)", "lost 7s"]),
        (dataclasses.replace(c, cls=None, identified=False), ["?", f"#{c.id}"]),
        (dataclasses.replace(c, haze=0.6, uncertainty=3000.0), ["~Gorkon (BC)"]),
        (dataclasses.replace(c, exhaust=True, visible=False, uncertainty=900.0), ["~Gorkon (BC)", "EXHAUST · rough fix"]),
        (dataclasses.replace(c, solution=6.0), ["Gorkon (BC)", "FIRING SOLUTION · 6s"]),
    ]
    for cv, want in cases:
        written.clear()
        view._label_rects = []
        view._contact(surf, cv, (cv.x, cv.y, 180.0), False, None, overlay, None)
        _flush(view)
        assert written == want, (cv, written)
    written.clear()
    view._label_rects = []
    view._contact(surf, c, (c.x, c.y, 180.0), True, "shields", overlay, None)
    _flush(view)
    assert written == ["⌖ shields", "Gorkon (BC)"]
    assert view._lock[0] == c.id and view._sounds[-1][0] == "lock"


def test_what_the_map_writes_beside_our_own_ships(content, written: list[str]) -> None:  # type: ignore[no-untyped-def]
    import copy

    w, view, surf, overlay = _map(content)
    obs = w.observe(0)
    me = next(s for s in w.ships.values() if s.name == "Enterprise")
    agena = next(s for s in w.ships.values() if s.name == "Agena")

    def say(s, player: bool) -> list[str]:  # type: ignore[no-untyped-def]
        written.clear()
        view._label_rects = []
        view._own_ship(surf, overlay, s, (s.x, s.y, s.course), player, obs, False, {})
        _flush(view)
        return list(written)

    assert say(me, True) == ["Enterprise", f"w{me.warp:.1f}"]
    cloaked = copy.deepcopy(me)
    cloaked.cloaked = True
    assert say(cloaked, True) == ["Enterprise", f"w{me.warp:.1f}", "CLOAKED"]
    boarded = copy.deepcopy(agena)
    boarded.boarders, boarded.boarder_side = 11, 1
    assert say(boarded, False) == ["Agena", "boarders aboard: 11"]
    docked = copy.deepcopy(agena)
    docked.docked_to = me.id
    assert say(docked, False) == ["Agena · docked"]
    view._label_more = {agena.id: 2}
    assert say(agena, False) == ["Agena  +2"]
    view._label_quiet = {agena.id}
    assert say(agena, False) == []


# ------------------------------------------------------------------ the command line

def test_the_command_line_screenshots_and_refuses_an_unknown_preset(tmp_path, capsys) -> None:  # type: ignore[no-untyped-def]
    from begin.__main__ import main

    assert main(["--preset", "nope", "--screenshot", str(tmp_path / "x.png")]) == 2
    assert "Unknown preset 'nope'." in capsys.readouterr().err
    shot = tmp_path / "quick.png"
    assert main(["--quick", "5", "--screenshot", str(shot), "--console", "target nearest; @1", "--overlay", "crew",
                 "--zoom", "0.05", "--size", "800x600"]) == 0
    assert shot.is_file() and f"saved {shot}" in capsys.readouterr().out
    assert main(["--llm-usage"]) == 0
