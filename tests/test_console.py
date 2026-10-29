"""Console grammar: Begin long forms, terse forms and readable variants."""

from __future__ import annotations

import pytest

from begin.console.parser import ParseContext, parse
from begin.sim.commands import (
    ConfigureAutoload, FirePhasers, FireTorpedoes, LaunchProbe, Pursue, SelectTarget, SetFireMode, SetHelm,
    SetPointDefense, SetShields,
)
from begin.sim.ship import FireMode, PDDoctrine

from .conftest import make_world


@pytest.fixture()
def setup(content):  # type: ignore[no-untyped-def]
    w = make_world(content)
    me = w.add_ship("federation.hc", 0, 0, 0, name="Enterprise")
    foe = w.add_ship("klingon.bc", 1, 0, 3000, name="Gorkon")
    w.step()
    return w, me, foe


def p(w, me, text):  # type: ignore[no-untyped-def]
    return parse(text, ParseContext(me.id, w.observe(0)))


def test_terse_autoload(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, _ = setup
    r = p(w, me, "al tor al mk7 1200")
    assert r.error is None
    (c,) = r.commands
    assert isinstance(c, ConfigureAutoload)
    assert c.weapon == "tube" and c.mounts is None and c.ordnance == "mk7" and c.prox == 1200 and c.enabled
    # the sim gives contextual feedback: MK7's proximity tops out at 500
    reason = w.execute(c)
    assert reason is not None and "500" in reason


def test_readable_autoload(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, _ = setup
    r = p(w, me, "autoload all torpedo tubes with mk8 prox 400")
    (c,) = r.commands
    assert c.ordnance == "mk8" and c.prox == 400  # type: ignore[attr-defined]
    assert w.execute(c) is None
    r = p(w, me, "autoload probes 1 px2 300 20")
    (c,) = r.commands
    assert c.weapon == "launcher" and c.mounts == (0,) and c.prox == 300 and c.time == 20  # type: ignore[attr-defined]
    r = p(w, me, "al tor off")
    assert r.commands[0].enabled is False  # type: ignore[attr-defined]


def test_helm_forms(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, _ = setup
    for text in ("helm 90 warp 4", "h 90 4", "helm course 90 warp 4", "90 4"):
        (c,) = p(w, me, text).commands
        assert isinstance(c, SetHelm) and c.course == 90 and c.warp == 4, text
    (c,) = p(w, me, "warp 6").commands
    assert c.warp == 6 and c.course is None  # type: ignore[attr-defined]


def test_ship_names_and_prefixes(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, foe = setup
    (c,) = p(w, me, "pursue gor warp 5").commands
    assert isinstance(c, Pursue) and c.target == foe.id and c.warp == 5
    (c,) = p(w, me, "target gorkon propulsion").commands
    assert isinstance(c, SelectTarget) and c.subsystem == "propulsion"
    (c,) = p(w, me, f"target #{foe.id} engines").commands
    assert c.target == foe.id and c.subsystem == "propulsion"  # type: ignore[attr-defined]
    assert "No ship named" in (p(w, me, "target romulus").error or "")


def test_fire_forms(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, foe = setup
    (c,) = p(w, me, "fire phasers 1 2 spread 10").commands
    assert isinstance(c, FirePhasers) and c.banks == (0, 1) and c.spread == 10
    (c,) = p(w, me, "fp all s 20 at gorkon").commands
    assert c.banks is None and c.spread == 20 and c.target == foe.id  # type: ignore[attr-defined]
    (c,) = p(w, me, "ft 1-3").commands
    assert isinstance(c, FireTorpedoes) and c.tubes == (0, 1, 2)
    (c,) = p(w, me, "fire probes at gorkon").commands
    assert isinstance(c, LaunchProbe) and c.target == foe.id


def test_misc(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, _ = setup
    (c,) = p(w, me, "lower shields 1 2").commands
    assert isinstance(c, SetShields) and c.sectors == (0, 1) and not c.up
    (c,) = p(w, me, "mode phasers automatic").commands
    assert isinstance(c, SetFireMode) and c.mode == FireMode.AUTOMATIC
    (c,) = p(w, me, "pd aggressive reserve 5 6").commands
    assert isinstance(c, SetPointDefense) and c.doctrine == PDDoctrine.AGGRESSIVE and c.reserve == (4, 5)
    r = p(w, me, "time 4")
    assert r.actions == [("speed", 4.0)]
    assert p(w, me, "help").actions == [("manual", None)]
    assert p(w, me, "man tor").actions == [("manual", "tor")]
    assert "Unknown command" in (p(w, me, "frobnicate").error or "")


def test_range_command_parses(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, _ = setup
    assert p(w, me, "range 5000").actions == [("range", 5000.0)]
    assert p(w, me, "range").actions == [("range", None)]
    assert "between" in (p(w, me, "range 5").error or "")


def test_disable_enemy_systems_parses_in_any_word_order(setup) -> None:  # type: ignore[no-untyped-def]
    from begin.sim.commands import EndObjective, SetObjective, SetTubes

    w, me, foe = setup
    other = w.add_ship("romulan.bp", 1, 2000, 3000, name="Tal")
    w.step()
    w.step()
    c = p(w, me, "disable the klingons' shields").commands[0]
    assert isinstance(c, SetObjective) and c.group == "shields" and c.targets == (foe.id,)
    c = p(w, me, "disable gorkon's torpedoes").commands[0]
    assert isinstance(c, SetObjective) and c.group == "torpedoes" and c.targets == (foe.id,)
    c = p(w, me, "disarm them").commands[0]
    assert isinstance(c, SetObjective) and c.group == "weapons" and set(c.targets) == {foe.id, other.id}
    c = p(w, me, "cripple tal and gorkon engines").commands[0]
    assert isinstance(c, SetObjective) and c.group == "propulsion" and set(c.targets) == {foe.id, other.id}
    assert isinstance(p(w, me, "disable off").commands[0], EndObjective)
    assert isinstance(p(w, me, "disable tubes 1 2").commands[0], SetTubes)   # still your own tubes


def test_destroy_and_bait_commands(setup) -> None:  # type: ignore[no-untyped-def]
    from begin.sim.commands import FireBait, SetObjective

    w, me, foe = setup
    c = p(w, me, "destroy gorkon").commands[0]
    assert isinstance(c, SetObjective) and c.goal == "destroy" and c.targets == (foe.id,)
    c = p(w, me, "bait gorkon").commands[0]
    assert isinstance(c, FireBait) and c.target == foe.id
