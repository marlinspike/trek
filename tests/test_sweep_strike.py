"""Sweep and strike [E]: a seeker down a cloaked ship's plasma trail, a firing solution when it hits, and an aimed
salvo into the system the captain named, in one order: typed, shortened, in plain words or spoken to Seven."""

from __future__ import annotations

import pygame
import pytest

from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle
from begin.console.plain import is_strike, plain_order, split_orders
from begin.sim.commands import FireSeeker, SetCloak, SetHelm, StartProject, Sweep
from begin.sim.events import ObjectiveEnded, SeekerLock


def _battle(content, seed: int = 3):  # type: ignore[no-untyped-def]
    """The Enterprise, and the Talon: a Romulan Bird of Prey with a damaged warp drive, cloaked, running at warp 4."""
    b = build_battle(content, BattleSetup([FleetSpec(0, [ShipSpec("federation.dn", x=0.0, y=0.0, course=0.0)], player=True),
                                           FleetSpec(1, [ShipSpec("romulan.bp", x=3000.0, y=14000.0, course=90.0)])],
                                          seed=seed))
    w = b.world
    rom = next(s for s in w.ships.values() if s.side == 1)
    rom.name = "Talon"
    for d in rom.drives:
        d.damage = 50
    w.controllers = [c for c in w.controllers if getattr(c, "ship_id", None) != rom.id]
    w.submit(SetCloak(ship_id=rom.id, on=True))
    w.submit(SetHelm(ship_id=rom.id, course=90.0, warp=4.0))
    return b, w, w.ships[b.player_ship_id], rom


@pytest.fixture()
def scene(content):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme
    from begin.ui.battle_scene import BattleScene

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    b, w, us, rom = _battle(content)
    sc = BattleScene(b, surf.get_size(), lambda: None, hidden={}, llm={})
    _step(sc, 3)
    return sc, surf, w, us, rom


def _step(sc, cycles: float) -> None:  # type: ignore[no-untyped-def]
    w = sc.session.world
    for _ in range(int(cycles * w.rules.ticks_per_cycle)):
        w.step()
        sc.session._drain_events()


# ------------------------------------------------------------------ the simulation

def test_a_seeker_hit_gives_a_firing_solution_that_runs_out(content) -> None:  # type: ignore[no-untyped-def]
    _, w, us, rom = _battle(content)
    w.submit(SetHelm(ship_id=us.id, course=0.0, warp=0.0))
    assert w.submit(StartProject(ship_id=us.id, project="seeker")) is None
    w.run(20.0)
    assert w.submit(Sweep(ship_id=us.id)) is None
    w.step()
    assert not w.observe(0).contact(rom.id).visible                   # cloaked: only her trail shows
    assert w.submit(FireSeeker(ship_id=us.id, target=rom.id)) is None
    lock = None
    for _ in range(25 * w.rules.ticks_per_cycle):
        w.step()
        lock = next((e for e in w.take_events() if isinstance(e, SeekerLock)), None)
        if lock is not None:
            break
    assert lock is not None and lock.target == rom.id and lock.side == 0
    assert lock.cycles == w.rules.seeker_lock_cycles
    w.step()
    c = w.observe(0).contact(rom.id)
    assert c.visible and c.solution > 0                                # lit up, cloak or no cloak
    assert w.observe(1).contact(us.id) is None or w.observe(1).contact(us.id).solution == 0   # theirs is not
    w.run(w.rules.seeker_lock_cycles + w.rules.cloak_hit_reveal_cycles + 1.0)
    c = w.observe(0).contact(rom.id)
    assert c.solution == 0 and not c.visible                           # the window closed: she slipped away


# ------------------------------------------------------------------ the words

@pytest.mark.parametrize("said", [
    "sweep and strike the talon's shields", "Sweep strike talon shields", "seeker strike talon shields",
    "track her exhaust and hit her shields", "follow the talon's plasma trail and take out her shields",
    "fire a seeker at the talon and knock out her shields", "sweep, then strike her shields",
])
def test_plain_words_become_one_strike_order(said: str) -> None:
    assert is_strike(said)
    assert split_orders(said) == [said.strip()]                       # one order, not a sweep and then a strike
    line = plain_order(said)
    assert line.startswith("strike ") and "shields" in line


def test_other_plasma_orders_are_left_alone() -> None:
    for said in ("sweep for plasma", "fire a seeker at the talon", "look for exhaust"):
        assert not is_strike(said)
        assert not plain_order(said).startswith("strike")


@pytest.mark.parametrize("line, group", [
    ("strike talon shields", "shields"),
    ("sweep strike talon warp", "propulsion"),
    ("sweep and strike the talon's weapons", "weapons"),
    ("str tal sh", "shields"),                                     # the shortest form, like 'pu tal'
    ("strike tal eng", "propulsion"),
    ("strike talon", "hull"),                                      # nothing named: kill her
    ("strike", "hull"),                                            # no ship either: the one whose trail we see
    ("kill chain on the talon", "hull"),
])
def test_the_console_forms(scene, line: str, group: str) -> None:  # type: ignore[no-untyped-def]
    sc, surf, w, us, rom = scene
    sc.run_console(line)
    assert [(o.goal, o.group, o.targets) for o in us.objectives] == [("strike", group, (rom.id,))]
    assert us.objectives[0].officer == "seven"                        # said to nobody: the science officer's job
    sc.run_console("strike off")
    assert not us.objectives


# ------------------------------------------------------------------ the whole chain

def test_seven_sweeps_strikes_and_knocks_out_her_shields(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf, w, us, rom = scene
    sc.run_console("seven, sweep and strike the talon's shields")
    assert us.objectives and us.objectives[0].goal == "strike" and us.objectives[0].officer == "seven"
    lit = drawn = False
    for _ in range(90):
        _step(sc, 1)
        c = w.observe(0).contact(rom.id)
        if c is not None and c.solution > 0:
            lit = True
            if not drawn:
                sc.draw(surf)                                         # the firing window on the map
                drawn = True
        if not us.objectives:
            break
    log = [ln.text for ln in sc.log]
    assert lit and drawn
    assert any("Seeker away" in t for t in log), log
    assert any("Firing solution!" in t and "shields" in t for t in log), log
    assert any("Seeker hit" in t for t in log)
    assert not us.objectives
    assert any("no longer have working shields" in t or "lost their shields" in t for t in log), log
    assert not any("Say 'seeker'" in t for t in log)                  # she fires it herself: no advice to the captain


def test_the_strike_is_called_off_when_she_stops_leaking(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf, w, us, rom = scene
    sc.run_console("strike talon shields")
    rom.warp = rom.desired_warp = 0.0                                 # a smart captain: below warp, no plasma
    w.plasma.clear()
    reason = None
    for _ in range(80):
        _step(sc, 1)
        for e in w.take_events():
            if isinstance(e, ObjectiveEnded) and e.goal == "strike":
                reason = e.reason
        if not us.objectives:
            break
    assert not us.objectives
    log = " ".join(ln.text for ln in sc.log)
    assert "no plasma" in log or (reason is not None and "no plasma" in reason)


def test_the_counsel_recommends_it_when_she_leaks(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf, w, us, rom = scene
    plans = sc.session.counsel(force=True)
    lines = {p.name: [st.line for st in p.steps] for p in plans}
    assert any(ln.startswith("strike talon ") for ln in lines["Seven of Nine"]), lines
    assert any(ln.startswith("strike talon") for p in plans for ln in p.lines if p.station == "tactical"), lines
    for p in plans:
        for st in p.steps:
            assert sc.session.dry_run(st.line) is None, st.line
    sc.run_console("counsel disable the talon's engines")
    plans = sc.session.counsel(force=True)
    assert any(ln == "strike talon warp" for p in plans for ln in p.lines), [p.lines for p in plans]


def test_the_coach_points_at_it(scene) -> None:  # type: ignore[no-untyped-def]
    from begin.help.coach import HelpContext, tips

    sc, surf, w, us, rom = scene
    titles = [t.title for t in tips(HelpContext(w.content, w.observe(0), us))]
    assert "Her plasma gives her away" in titles
