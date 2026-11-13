"""[E] The bridge's everyday words work with no language model connected: 'red alert', 'come about', 'full speed
ahead', 'attack', 'retreat', 'target the nearest enemy', 'make it so'. Found by the full-game sweep, where each of
these came back as 'Unknown command' or found 'No ship named nearest'."""

from __future__ import annotations

import pytest

from begin.console.parser import ParseContext, parse
from begin.sim.commands import OpenFire, Pursue, SelectTarget, SetHelm
from begin.sim.world import World


def _pair(content):  # type: ignore[no-untyped-def]
    w = World(content, seed=4)
    fed = w.add_ship("federation.hc", 0, 0, 0, name="Enterprise")
    near = w.add_ship("klingon.bc", 1, 0, 6000, name="Votek")
    w.add_ship("klingon.bc", 1, 0, 15000, name="Gorkon")
    w.run(1.0)
    return w, fed, near


def _cmds(w, me, text):  # type: ignore[no-untyped-def]
    res = parse(text, ParseContext(me.id, w.observe(0)))
    assert res.error is None, f"{text!r}: {res.error}"
    return res.commands


@pytest.mark.parametrize("text", ["target nearest enemy", "target the nearest", "lock onto the nearest enemy",
                                  "target the closest one"])
def test_the_nearest_enemy_can_be_named(content, text: str) -> None:  # type: ignore[no-untyped-def]
    w, fed, near = _pair(content)
    sel = [c for c in _cmds(w, fed, text) if isinstance(c, SelectTarget)]
    assert sel and sel[0].target == near.id


def test_her_and_the_target_mean_our_target_else_the_nearest(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, near = _pair(content)
    assert [c.target for c in _cmds(w, fed, "pursue the target") if isinstance(c, Pursue)] == [near.id]
    gorkon = next(s for s in w.ships.values() if s.name == "Gorkon")
    fed.target = gorkon.id
    assert [c.target for c in _cmds(w, fed, "pursue her") if isinstance(c, Pursue)] == [gorkon.id]


@pytest.mark.parametrize("text,course,warp", [
    ("set course 180", 180.0, None), ("heading 270", 270.0, None), ("turn to 090", 90.0, None),
    ("come about", 180.0, None), ("bring us about", 180.0, None), ("hard to port", 270.0, None),
    ("turn right", 90.0, None), ("turn left 45", 315.0, None), ("go to warp 5", None, 5.0),
    ("warp factor 4", None, 4.0), ("full stop", None, 0.0), ("all stop", None, 0.0),
])
def test_helm_in_plain_words(content, text: str, course, warp) -> None:  # type: ignore[no-untyped-def]
    w, fed, _ = _pair(content)
    fed.course = 0.0
    helm = [c for c in _cmds(w, fed, text) if isinstance(c, SetHelm)]
    assert helm and helm[0].course == course and helm[0].warp == warp


def test_full_speed_is_her_best_warp(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, _ = _pair(content)
    for text in ("full speed ahead", "maximum warp", "punch it"):
        assert [c.warp for c in _cmds(w, fed, text) if isinstance(c, SetHelm)] == [fed.cls.max_warp]


def test_attack_retreat_and_fire_at_will(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, near = _pair(content)
    kinds = [type(c) for c in _cmds(w, fed, "attack")]
    assert SelectTarget in kinds and Pursue in kinds and OpenFire in kinds
    run = [c for c in _cmds(w, fed, "get us out of here") if isinstance(c, Pursue)]
    assert run and run[0].elude and run[0].target == near.id
    assert [type(c) for c in _cmds(w, fed, "fire at will")] == [OpenFire]


@pytest.mark.parametrize("text", ["red alert", "yellow alert", "damage report", "how are the shields?",
                                  "what's our status?", "where is the enemy?", "what do you recommend?",
                                  "manage repairs", "point defense high", "zoom in", "zoom out", "fire everything",
                                  "keep firing", "slow down", "speed up", "close to 3000", "take us in"])
def test_everyday_bridge_words_are_understood(content, text: str) -> None:  # type: ignore[no-untyped-def]
    w, fed, _ = _pair(content)
    res = parse(text, ParseContext(fed.id, w.observe(0)))
    assert res.error is None, f"{text!r}: {res.error}"
    assert res.commands or res.actions or res.display, text


def test_make_it_so_takes_the_proposal(content) -> None:  # type: ignore[no-untyped-def]
    from begin.battle import build_battle
    from begin.crew.proposals import Proposal
    from begin.presets import load_presets
    from begin.session.battle import BattleSession

    s = BattleSession(build_battle(content, load_presets()[0].setup()))
    enemy = next(c for c in s.observe().hostile_contacts())
    s.proposal = Proposal("worf", "Worf", "tactical", "Target her?", f"target #{enemy.id}")
    s.run_console("Make it so.")
    assert s.proposal is None and s.player is not None and s.player.target == enemy.id
