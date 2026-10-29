"""Every command example from the Begin manual (pp. 8-25, Appendix D) parses and does what the manual says.

Ship names in the manual's examples are swapped for ships in this test fleet:
allies Agena, Terra, Altair (and Starbase Rigel); enemies Zantha, Bismark, Eagle.
"""

from __future__ import annotations

import pytest

from begin.console.parser import ParseContext, parse
from begin.sim.commands import (
    AllyOrder, ConfigureAutoload, ControlProbe, FirePhasers, FireTorpedoes, LaunchProbe, LoadTubes, LockWeapons,
    Pursue, Scan, SelfDestruct, SetBanks, SetHelm, SetShields, SetTubes, Transport, TurnMounts,
)

from .conftest import make_world


@pytest.fixture()
def fleet(content):  # type: ignore[no-untyped-def]
    w = make_world(content)
    me = w.add_ship("federation.dn", 0, 0, 0, name="Enterprise")
    allies = {
        "agena": w.add_ship("federation.de", 0, 1500, 0, name="Agena"),
        "terra": w.add_ship("federation.de", 0, -1500, 0, name="Terra"),
        "altair": w.add_ship("federation.hc", 0, 0, -2000, name="Altair"),
        "rigel": w.add_ship("federation.sb", 0, 0, -6000, name="Rigel"),
    }
    foes = {
        "zantha": w.add_ship("klingon.bc", 1, 0, 9000, name="Zantha"),
        "bismark": w.add_ship("klingon.fr", 1, 3000, 9000, name="Bismark"),
        "eagle": w.add_ship("romulan.bp", 1, -3000, 9000, name="Eagle"),
    }
    w.step()
    return w, me, allies, foes


def run(w, me, text):  # type: ignore[no-untyped-def]
    r = parse(text, ParseContext(me.id, w.observe(0)))
    assert r.error is None, f"{text!r}: {r.error}"
    return r


# ------------------------------------------------------------------ every example in the manual

MANUAL_EXAMPLES = [
    # helm (p. 9)
    "helm course 60 warp 6", "helm 225 3", "pursue the zantha warp 4", "pursue bismark 2", "elude eagle warp 8",
    "elude zantha 7",
    # chart and report (pp. 9-10)
    "chart", "chart on", "chart off", "chart from the agena", "report",
    # status damage / scan ship (p. 11)
    "damage", "status damage", "scan zantha",
    # range (p. 11)
    "range 15000", "display 15000", "scan 15000",
    # fleet (p. 12)
    "status fleet", "fleet",
    # phasers (pp. 12-14)
    "fire phasers 1 2 3 spread 10", "fire all phasers 45", "phaser all 45",
    "lock banks on zantha", "lock all banks on eagle", "lock banks 1 2 and 3 on bismark",
    "turn banks to 180", "turn all banks to 0", "turn banks 1 2 to 90",
    "status banks", "banks", "disable banks 2 3 4", "enable all banks",
    # torpedoes (pp. 14-16)
    "fire torpedo 1 2", "fire all torpedoes", "torp all",
    "lock tubes on eagle 0", "lock tubes 1 2 on zantha 24", "lock all tubes on bismark with a dispersion of 45",
    "turn tubes to 180", "turn all tubes to 0", "turn tubes 1 2 to 90",
    "status tubes", "tubes", "load tubes prox 500", "load tubes 1 2 350", "load all tubes prox 425",
    "unload tubes 1 2", "unload all tubes", "disable tubes 1 2", "enable all tubes",
    # probes (pp. 17-19)
    "fire probes 1 course 180", "probe all at zantha", "probe all course 180",
    "load launchers 1 prox 500 time 20", "load all launchers 450 15", "load probes 200 10",
    "unload all launchers", "unload launchers 1", "status probes", "status launchers", "launchers",
    # shields (pp. 19-20)
    "raise shields 1 2 3 4", "raise all", "lower all shields", "drop shields 1 2 3", "lower 1 2 3",
    "status shields", "shields",
    # transport, destruct, library, help (pp. 20-22)
    "beam agena", "beam to the terra", "transport altair",
    "self destruct 10", "destruct 5", "abort", "destruct abort",
    "computer ship klingon frigate", "computer torpedo mkvii", "computer probe pxii", "computer ship", "computer",
    "help",
    # ally orders (pp. 22-25)
    "tell the agena to attack the zantha", "order agena course 90", "order terra escort altair at 5000",
    "tell the terra report", "tell agena target bismark", "tell agena hold fire", "tell agena open fire",
    "tell agena disengage", "tell agena retreat", "tell agena cancel", "tell agena torpedo zantha",
    "tell agena phaser zantha", "tell agena probe zantha", "tell agena withdraw", "tell agena run",
    # Begin 2.0 (Appendix D)
    "repair warp", "repair all", "tractor zantha", "tractor off", "board zantha", "dock rigel on", "dock rigel off",
    "cloak on", "cloak off", "reenforce 1",
    "tell agena board bismark 20", "tell agena tow terra rigel", "tell agena tractor terra", "tell agena release",
    "tell agena approach zantha 4000", "tell agena dock rigel", "tell agena join 1",
    "tell agena leave", "tell agena stop", "tell agena defend altair", "tell rigel recover terra",
    "group", "chart all", "chart by name", "chart by distance", "chart by nation", "chart agena on", "chart agena off",
    "text", "key F5 fire all phasers 10",
    "quit",
]


@pytest.mark.parametrize("text", MANUAL_EXAMPLES)
def test_manual_example_parses(fleet, text) -> None:  # type: ignore[no-untyped-def]
    w, me, *_ = fleet
    r = run(w, me, text)
    assert r.commands or r.actions or r.display or r.info, text


# ------------------------------------------------------------------ short forms

def test_short_forms(fleet) -> None:  # type: ignore[no-untyped-def]
    w, me, _, foes = fleet
    (c,) = run(w, me, "fir tor al").commands
    assert isinstance(c, FireTorpedoes) and c.tubes is None
    (c,) = run(w, me, "fir tor 1,2,3").commands
    assert isinstance(c, FireTorpedoes) and c.tubes == (0, 1, 2)
    (c,) = run(w, me, "fir tor 1 2 3").commands
    assert c.tubes == (0, 1, 2)  # type: ignore[attr-defined]
    (c,) = run(w, me, "fi ph al 20").commands
    assert isinstance(c, FirePhasers) and c.banks is None and c.spread == 20
    (c,) = run(w, me, "tor 2").commands
    assert isinstance(c, FireTorpedoes) and c.tubes == (1,)
    (c,) = run(w, me, "pur zan 3").commands
    assert isinstance(c, Pursue) and c.target == foes["zantha"].id and c.warp == 3
    (c,) = run(w, me, "loc ban 1 2 on zan").commands
    assert isinstance(c, LockWeapons) and c.banks == (0, 1) and c.target == foes["zantha"].id
    (c,) = run(w, me, "dro sh 1").commands
    assert isinstance(c, SetShields) and c.sectors == (0,) and not c.up
    (c,) = run(w, me, "sel des 12").commands
    assert isinstance(c, SelfDestruct) and c.cycles == 12
    assert "ambiguous" in (parse("lo", ParseContext(me.id, w.observe(0))).error or "")


# ------------------------------------------------------------------ the forms do what the manual says

def test_phaser_and_torpedo_forms(fleet) -> None:  # type: ignore[no-untyped-def]
    w, me, _, foes = fleet
    (c,) = run(w, me, "fire all phasers 45").commands
    assert isinstance(c, FirePhasers) and c.banks is None and c.spread == 45
    (c,) = run(w, me, "lock banks 1 2 and 3 on bismark").commands
    assert isinstance(c, LockWeapons) and c.banks == (0, 1, 2) and c.phasers and not c.torpedoes
    assert c.target == foes["bismark"].id
    (c,) = run(w, me, "lock all tubes on bismark with a dispersion of 45").commands
    assert c.tubes is None and c.torpedoes and not c.phasers and c.dispersion == 45  # type: ignore[attr-defined]
    (c,) = run(w, me, "lock tubes on eagle 0").commands
    assert c.dispersion == 0 and c.target == foes["eagle"].id  # type: ignore[attr-defined]
    (c,) = run(w, me, "turn banks 1 2 to 90").commands
    assert isinstance(c, TurnMounts) and c.banks == (0, 1) and c.mark == 90
    (c,) = run(w, me, "turn banks to 6").commands
    assert c.mark == 6 and c.banks is None  # type: ignore[attr-defined]


def test_tube_and_launcher_management(fleet) -> None:  # type: ignore[no-untyped-def]
    w, me, _, _ = fleet
    cfg, load = run(w, me, "load tubes 1 2 350").commands
    assert isinstance(cfg, ConfigureAutoload) and cfg.mounts == (0, 1) and cfg.prox == 350
    assert isinstance(load, LoadTubes) and load.weapon == "tube"
    cfg, load = run(w, me, "load all launchers 450 15").commands
    assert cfg.weapon == "launcher" and cfg.prox == 450 and cfg.time == 15  # type: ignore[attr-defined]
    # disable tubes really stops tube charging (it used to disable phaser banks)
    (c,) = run(w, me, "disable tubes 1 2").commands
    assert isinstance(c, SetTubes) and c.tubes == (0, 1) and not c.enabled
    assert w.execute(c) is None
    assert not me.tubes[0].enabled and not me.tubes[1].enabled and all(b.enabled for b in me.banks)
    (c,) = run(w, me, "disable banks 2 3").commands
    assert isinstance(c, SetBanks) and c.banks == (1, 2)
    # unload launchers empties the launcher (it used to unload torpedo tubes)
    w.run(12)
    assert any(lch.loaded for lch in me.launchers)
    before = me.probes_remaining
    loaded = sum(1 for lch in me.launchers if lch.loaded)
    (c,) = run(w, me, "unload all launchers").commands
    assert w.execute(c) is None
    assert not any(lch.loaded for lch in me.launchers)
    assert me.probes_remaining == before + loaded
    w.run(5)
    assert not any(lch.loaded for lch in me.launchers), "launchers stay empty until loaded again"


def test_probe_control_by_code(fleet) -> None:  # type: ignore[no-untyped-def]
    w, me, _, foes = fleet
    w.run(12)
    (c,) = run(w, me, "probe all course 180").commands
    assert isinstance(c, LaunchProbe) and c.course == 180 and c.count > 1
    assert w.execute(c) is None
    code = w.probes[0].code
    (c,) = run(w, me, f"turn probe {code} course 90").commands
    assert isinstance(c, ControlProbe) and c.code == code.lower() and c.course == 90
    assert w.execute(c) is None and w.probes[0].course == 90
    (c,) = run(w, me, "lock all probes on the zantha").commands
    assert c.code is None and c.target == foes["zantha"].id  # type: ignore[attr-defined]
    assert w.execute(c) is None and all(p.target == foes["zantha"].id for p in w.probes)
    r = run(w, me, "status probes")
    assert r.display[0] == "PROBE STATUS:" and any(code in line for line in r.display)
    (c,) = run(w, me, f"detonate {code}").commands
    assert c.detonate and c.code == code.lower()  # type: ignore[attr-defined]


def test_status_displays_follow_the_manual(fleet) -> None:  # type: ignore[no-untyped-def]
    w, me, _, _ = fleet
    w.run(3)
    assert run(w, me, "report").display[0] == "SHIP NAME: Enterprise"
    dmg = run(w, me, "status damage").display
    assert dmg[0] == "SHIP NAME: Enterprise" and any(line.startswith("SHIELDS:") for line in dmg)
    assert run(w, me, "banks").display[0] == "BANK STATUS:"
    assert run(w, me, "tubes").display[0] == "TUBE STATUS:"
    assert run(w, me, "launchers").display[0] == "LAUNCHER STATUS:"
    sh = run(w, me, "shields").display
    assert sh[0] == "SHIELDS STATUS:" and len(sh) == 2 + len(me.shields)
    fl = run(w, me, "status fleet").display
    assert fl[0].startswith("ALLY") and any("Agena" in line for line in fl)
    assert any("Frigate" in line for line in run(w, me, "computer ship klingon").display)
    assert run(w, me, "computer torpedo mkvii").display[0].startswith("Federation Mark 7")
    assert run(w, me, "computer probe pxii").display[0].startswith("Federation Probe X-2")


def test_scan_range_and_ship(fleet) -> None:  # type: ignore[no-untyped-def]
    w, me, _, foes = fleet
    assert run(w, me, "scan 15000").actions == [("range", 15000.0)]
    (c,) = run(w, me, "scan zantha").commands
    assert isinstance(c, Scan) and c.target == foes["zantha"].id


def test_beam_trades_ships_or_moves_crew(fleet) -> None:  # type: ignore[no-untyped-def]
    w, me, allies, foes = fleet
    assert run(w, me, "beam to the agena").actions == [("transfer", allies["agena"].id)]
    (c,) = run(w, me, "beam agena 20").commands
    assert isinstance(c, Transport) and c.count == 20
    (c,) = run(w, me, "board zantha 30").commands
    assert isinstance(c, Transport) and c.target == foes["zantha"].id and c.count == 30


def test_tell_orders_and_groups(fleet) -> None:  # type: ignore[no-untyped-def]
    w, me, allies, foes = fleet
    (c,) = run(w, me, "tell the agena to attack the zantha").commands
    assert isinstance(c, AllyOrder) and c.ally == allies["agena"].id and c.order == "attack"
    assert c.target == foes["zantha"].id
    (c,) = run(w, me, "order terra escort altair at 5000").commands
    assert c.order == "escort" and c.target == allies["altair"].id and c.value == 5000  # type: ignore[attr-defined]
    (c,) = run(w, me, "tell agena hold fire").commands
    assert c.order == "hold"  # type: ignore[attr-defined]
    (c,) = run(w, me, "tell agena hold course 270").commands
    assert c.order == "course" and c.value == 270  # type: ignore[attr-defined]
    (c,) = run(w, me, "tell agena tow terra to rigel").commands
    assert c.order == "tow" and c.target == allies["terra"].id and c.destination == allies["rigel"].id  # type: ignore[attr-defined]
    rep = run(w, me, "tell the terra report").display
    assert rep[0] == "SHIP NAME: Terra" and any(line.startswith("MISSION") for line in rep)
    # groups: join, then order the group by number
    for name in ("agena", "terra"):
        (c,) = run(w, me, f"tell {name} join 2").commands
        assert w.execute(c) is None
    cmds = run(w, me, "tell 2 attack bismark").commands
    assert {c.ally for c in cmds} == {allies["agena"].id, allies["terra"].id}  # type: ignore[attr-defined]
    assert "Group 2" in run(w, me, "group").display[0]


def test_unreasonable_ally_orders_are_refused(fleet) -> None:  # type: ignore[no-untyped-def]
    w, me, allies, foes = fleet
    (c,) = run(w, me, "tell agena escort zantha").commands
    assert "not one of ours" in (w.execute(c) or "")
    (c,) = run(w, me, "tell agena attack terra").commands
    assert "one of ours" in (w.execute(c) or "")
    (c,) = run(w, me, "tell agena recover terra").commands
    assert "no docking bays" in (w.execute(c) or "")
