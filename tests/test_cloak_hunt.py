"""Fighting a cloaked ship: blind torpedo reports, the crew calling cloaks, and 'find <ship>' [E]."""

from __future__ import annotations

import dataclasses

import pygame
import pytest

from begin.core.rng import Rng
from begin.crew.characters import load_officers
from begin.crew.officers import Crew, default_crew
from begin.sim.commands import (
    Authority, CeaseFire, DeflectorPulse, EndObjective, FireSpecialRound, FireTorpedoes, SelectTarget, SetObjective, StartProject,
)
from begin.sim.events import Message

from .conftest import make_world, scenario_presets


def _texts(w) -> list[str]:  # type: ignore[no-untyped-def]
    return [e.text for e in w.take_events() if isinstance(e, Message)]


def _cloaked_romulan(content, y: float = 6000.0):  # type: ignore[no-untyped-def]
    """A Federation heavy cruiser that saw a Romulan Bird of Prey, the Talon, before she cloaked."""
    w = make_world(content, seed=3)
    hc = w.add_ship("federation.hc", 0, 0, 0)
    bp = w.add_ship("romulan.bp", 1, 0, y, course=180)
    bp.name = "Talon"
    bp.desired_warp = bp.warp = 0.0
    w.run(8)                  # tubes loaded, the Talon seen and identified
    bp.cloaked = True
    w.run(0.5)
    w.take_events()
    return w, hc, bp


def test_a_blind_torpedo_says_it_has_no_lock_and_how_the_miss_ended(content) -> None:  # type: ignore[no-untyped-def]
    w, hc, bp = _cloaked_romulan(content)
    c = w.observe(0).contact(bp.id)
    assert c is not None and not c.visible and c.cloaked_hint
    bp.x += 25000             # she slipped away under the cloak: the torpedoes find nothing at her last fix
    w.execute(FireTorpedoes(ship_id=hc.id, target=bp.id, issuer=Authority.CAPTAIN))
    said = _texts(w)
    assert any("No sensor lock on the Talon" in t and "last known position" in t for t in said)
    w.run(20)
    said = _texts(w)
    assert any(("ran out of fuse" in t or "nothing in reach" in t) and "Talon" in t for t in said), said


def test_a_blind_torpedo_hit_is_reported_and_shows_her(content) -> None:  # type: ignore[no-untyped-def]
    w, hc, bp = _cloaked_romulan(content)
    w.execute(FireTorpedoes(ship_id=hc.id, target=bp.id, issuer=Authority.CAPTAIN))
    seen = False
    said: list[str] = []
    for _ in range(12 * w.rules.ticks_per_cycle):
        w.step()
        said += _texts(w)
        c = w.observe(0).contact(bp.id)
        seen = seen or bool(c is not None and c.visible)
        if any("Torpedo hit" in t for t in said) and seen:
            break
    assert any("Torpedo hit" in t and "Talon" in t for t in said), said
    assert seen               # the hit shows her for a few cycles, long enough to aim
    assert w.rules.cloak_hit_reveal_cycles > w.rules.cloak_reveal_cycles


def test_seen_targets_get_no_blind_reports(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content, seed=3)
    hc = w.add_ship("federation.hc", 0, 0, 0)
    bp = w.add_ship("romulan.bp", 1, 0, 6000, course=180)
    w.run(8)
    w.take_events()
    w.execute(FireTorpedoes(ship_id=hc.id, target=bp.id, issuer=Authority.CAPTAIN))
    w.run(12)
    assert not any("sensor lock" in t or "No sign of" in t for t in _texts(w))


def test_hunt_parses_a_name_or_finds_the_lost_ship(content) -> None:  # type: ignore[no-untyped-def]
    from begin.console.parser import NOTHING_LOST, ParseContext, parse

    w, hc, bp = _cloaked_romulan(content)
    ctx = ParseContext(hc.id, w.observe(0))
    for line in ("hunt talon", "find the talon", "locate her", "hunt", "seek tal", "hunt for the cloaked ship"):
        res = parse(line, ctx)
        assert res.error is None, (line, res.error)
        cmd = res.commands[0]
        assert isinstance(cmd, SetObjective) and cmd.goal == "hunt" and cmd.targets == (bp.id,), line
    off = parse("hunt off", ctx).commands[0]
    assert isinstance(off, EndObjective) and off.group == "hunt"
    assert "No ship named" in (parse("find gorkon", ctx).error or "")
    # "fi" is still fire: the hunt verb never takes over a firing abbreviation
    assert not any(isinstance(c, SetObjective) for c in parse("fi tor", ctx).commands)
    bp.cloaked = False
    w.run(0.5)
    assert parse("hunt", ParseContext(hc.id, w.observe(0))).error == NOTHING_LOST


def test_seven_hunts_the_talon_until_she_shows_then_targets_her(content) -> None:  # type: ignore[no-untyped-def]
    w, hc, bp = _cloaked_romulan(content, y=8000)
    crew = Crew(hc.id, 0, content, default_crew(load_officers()), Rng(1))
    w.execute(CeaseFire(ship_id=hc.id))
    w.execute(SetObjective(ship_id=hc.id, goal="hunt", group="hunt", targets=(bp.id,), officer="seven"))
    assert hc.hold_fire                       # a hunt fires nothing, so it doesn't lift a cease fire
    cmds = crew.think(w.observe(0))
    assert any(isinstance(c, StartProject) and c.project == "tachyon" for c in cmds)
    assert not any(isinstance(c, FireTorpedoes) for c in cmds)
    for c in cmds:
        w.execute(c)
    fired = found = False
    for _ in range(60):
        w.run(1)
        for c in crew.think(w.observe(0)):
            fired = fired or isinstance(c, (FireSpecialRound, DeflectorPulse))
            found = found or isinstance(c, EndObjective) and c.outcome == "done"
            w.execute(c)
        if found:
            break
    assert fired and found                    # a tachyon field at her projected position lit her up
    assert hc.target == bp.id and not hc.objectives
    act = crew.activity(w.observe(0))
    assert not any(a.kind == "hunt" for a in act)


def test_a_hunt_does_not_stop_the_weapons_officer(content) -> None:  # type: ignore[no-untyped-def]
    """Worf keeps fighting the ship in sight while Seven looks for the one that cloaked."""
    w = make_world(content, seed=3)
    hc = w.add_ship("federation.hc", 0, 0, 0)
    bp = w.add_ship("romulan.bp", 1, 0, 8000, course=180)
    kl = w.add_ship("klingon.bc", 1, 2000, 4000, course=180)
    w.run(8)
    bp.cloaked = True
    w.run(0.5)
    crew = Crew(hc.id, 0, content, default_crew(load_officers()), Rng(1))
    from begin.sim.commands import DelegateStation

    w.execute(DelegateStation(ship_id=hc.id, station="tactical", on=True))
    w.execute(SetObjective(ship_id=hc.id, goal="hunt", group="hunt", targets=(bp.id,), officer="seven"))
    cmds = crew.think(w.observe(0))
    assert any(isinstance(c, StartProject) for c in cmds)                 # Seven looks
    assert any(isinstance(c, SelectTarget) and c.target == kl.id for c in cmds)
    assert any(isinstance(c, FireTorpedoes) for c in cmds)                # and Worf fights on


@pytest.fixture()
def scene(content):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.battle import build_battle
    from begin.ui import theme
    from begin.ui.battle_scene import BattleScene

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    b = build_battle(content, scenario_presets()[0].setup())
    for ship in b.world.ships.values():
        if ship.side != b.world.ships[b.player_ship_id].side:
            ship.name = "Talon"
    sc = BattleScene(b, surf.get_size(), lambda: None, hidden={}, llm={})
    return sc, surf


def _said(sc, who: str) -> list[str]:  # type: ignore[no-untyped-def]
    return [ln.text for ln in sc.log if ln.text.startswith(who + ":")]


def _step(sc, cycles: float) -> None:  # type: ignore[no-untyped-def]
    for _ in range(int(cycles * sc.session.world.rules.ticks_per_cycle)):
        sc.session.world.step()
        sc.session._drain_events()


def _cloak(sc):  # type: ignore[no-untyped-def]
    foe = next(s for s in sc.session.world.ships.values() if s.side != sc.player.side)
    foe.x, foe.y = sc.player.x, sc.player.y + 7000
    foe.cls = dataclasses.replace(foe.cls, can_cloak=True)
    foe.desired_warp = 0.0
    _step(sc, 2)
    foe.cloaked = True
    return foe


def test_seven_calls_the_cloak_and_finds_the_talon_by_name(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    _cloak(sc)
    _step(sc, 1)
    seven = _said(sc, "Seven of Nine")
    assert any("Talon" in t and "cloak" in t and "find" in t for t in seven), seven
    sc.run_console("seven, where is the talon?")
    # straight from the sensor log: the last fix, or where she is if she has just fired and shown herself
    assert any("Last fix" in t or "is at bearing" in t for t in _said(sc, "Seven of Nine")[len(seven):])
    sc.run_console("seven, find the Talon")
    o = sc.player.objectives[0]
    assert o.goal == "hunt" and o.officer == "seven"
    assert len(_said(sc, "Seven of Nine")) > len(seven) + 1
    sc.draw(surf)
    sc.run_console("hunt off")
    assert not sc.player.objectives


def test_find_said_to_nobody_goes_to_the_science_officer(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    _cloak(sc)
    _step(sc, 1)
    sc.run_console("find talon")
    assert sc.player.objectives and sc.player.objectives[0].officer == "seven"
