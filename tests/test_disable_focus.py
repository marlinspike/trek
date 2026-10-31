"""Disabling means just that system: the officer focuses fire on it, stops when it is out, and the ship is
left crippled, not destroyed. Only an order to target the hull (or destroy her) finishes her."""

from __future__ import annotations

import pygame
import pytest

from begin.battle import build_battle
from begin.console.parser import ParseContext, parse
from begin.presets import load_presets
from begin.sim.commands import Authority, FirePhasers, LaunchProbe, OpenFire, SelectTarget, offensive_fire
from begin.sim.events import ObjectiveEnded


def _scene(content, lines: list[str]):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme
    from begin.ui.battle_scene import BattleScene

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    sc = BattleScene(b, surf.get_size(), lambda: None, hidden={}, llm={})
    sc.overlay, sc.paused = None, False
    enemy = next(s for s in b.world.ships.values() if s.side != sc.player.side)
    enemy.x, enemy.y = sc.player.x + 3000, sc.player.y + 5000
    sc.run_console(f"target #{enemy.id}")
    for line in lines:
        sc.run_console(line)
    return sc, enemy


def _run_until_done(sc, secs: float) -> int | None:  # type: ignore[no-untyped-def]
    """Run the battle; the tick the objective was met, if it was."""
    w = sc.world
    done: list[int] = []
    emit = w.emit

    def spy(e):  # type: ignore[no-untyped-def]
        if isinstance(e, ObjectiveEnded) and e.outcome == "done":
            done.append(e.tick)
        return emit(e)

    w.emit = spy
    for _ in range(int(secs * 20)):
        sc.update(0.05)
        sc.overlay = None
        if done:
            break
    w.emit = emit
    return done[0] if done else None


def _officer_shots(sc, start: int, at: int) -> list[object]:  # type: ignore[no-untyped-def]
    me = sc.player
    return [lc.command for lc in sc.world.command_log[start:] if lc.accepted and lc.command.ship_id == me.id
            and lc.command.issuer < Authority.CAPTAIN and offensive_fire(lc.command)]


@pytest.mark.parametrize("system", ["shields", "phasers", "engines"])
@pytest.mark.parametrize("setup", [[], ["delegate all"]])
def test_disabling_stops_at_the_system_and_spares_the_ship(content, system: str, setup: list[str]) -> None:  # type: ignore[no-untyped-def]
    sc, enemy = _scene(content, setup)
    sc.run_console(f"seven, disable their {system}")
    assert _run_until_done(sc, 150.0) is not None, f"{system} never knocked out"
    me = sc.player
    assert enemy.exists and enemy.structure > 0
    assert me.target_subsystem is None                  # by default we are back to aiming at the hull
    assert enemy.id in me.spared
    hull = enemy.structure
    start = len(sc.world.command_log)
    for _ in range(40 * 20):
        sc.update(0.05)
        sc.overlay = None
    assert _officer_shots(sc, start, enemy.id) == []    # Worf and the fire computer leave her alone
    assert enemy.exists and enemy.structure >= hull - 1e-6
    sc.close()


def test_disabling_torpedoes_never_destroys_her(content) -> None:  # type: ignore[no-untyped-def]
    sc, enemy = _scene(content, ["delegate all"])
    sc.run_console("seven, disable their torps")
    _run_until_done(sc, 150.0)
    assert enemy.exists and enemy.structure > 0
    sc.close()


def test_no_attack_probes_while_seven_is_disabling(content) -> None:  # type: ignore[no-untyped-def]
    sc, enemy = _scene(content, ["delegate tactical"])
    start = len(sc.world.command_log)
    sc.run_console("seven, disable their shields")
    _run_until_done(sc, 60.0)
    probes = [lc for lc in sc.world.command_log[start:] if lc.accepted and isinstance(lc.command, LaunchProbe)]
    assert probes == [] and enemy.exists
    sc.close()


def test_worf_can_be_told_to_disable_too(content) -> None:  # type: ignore[no-untyped-def]
    sc, enemy = _scene(content, [])
    sc.run_console("worf, disable their shields")
    assert [(o.goal, o.group, o.officer) for o in sc.player.objectives] == [("disable", "shields", "worf")]
    assert _run_until_done(sc, 150.0) is not None and enemy.exists
    sc.close()


@pytest.mark.parametrize("line", ["target her hull", "worf, target their hull", "aim at the hull", "fire phasers"])
def test_targeting_the_hull_or_firing_finishes_her(content, line: str) -> None:  # type: ignore[no-untyped-def]
    sc, enemy = _scene(content, ["delegate tactical"])
    sc.run_console("seven, disable their shields")
    assert _run_until_done(sc, 150.0) is not None
    assert enemy.id in sc.player.spared
    sc.run_console(line)
    assert enemy.id not in sc.player.spared
    start = len(sc.world.command_log)
    for _ in range(20 * 20):
        sc.update(0.05)
        sc.overlay = None
    assert _officer_shots(sc, start, enemy.id)          # Worf opens up on her again
    sc.close()


def test_spared_in_the_simulation(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    w, me = b.world, b.world.ships[b.player_ship_id]
    enemy = next(s for s in w.ships.values() if s.side != me.side)
    w.execute(SelectTarget(ship_id=me.id, target=enemy.id))
    me.spared.add(enemy.id)
    officer = FirePhasers(ship_id=me.id, target=enemy.id, issuer=Authority.OFFICER)
    assert w.execute(officer) == "Holding fire on her: the captain wanted her disabled, not destroyed."
    w.execute(SelectTarget(ship_id=me.id, target=enemy.id, subsystem="shields"))
    assert enemy.id in me.spared                         # aiming at a system doesn't release her
    w.execute(SelectTarget(ship_id=me.id, target=enemy.id, hull=True))
    assert enemy.id not in me.spared
    me.spared.add(enemy.id)
    w.execute(OpenFire(ship_id=me.id))
    assert not me.spared


def test_hull_is_the_default_and_named_on_purpose(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    me = b.world.ships[b.player_ship_id]
    enemy = next(s for s in b.world.ships.values() if s.side != me.side)
    me.target = enemy.id
    ctx = ParseContext(me.id, b.world.observe(me.side))
    plain = parse(f"target #{enemy.id}", ctx).commands[0]
    assert isinstance(plain, SelectTarget) and plain.subsystem is None and not plain.hull
    for said in ("target hull", "target their hull", "target the hull", f"target #{enemy.id} hull", "aim hull"):
        cmd = parse(said, ctx).commands[0]
        assert isinstance(cmd, SelectTarget) and cmd.target == enemy.id and cmd.subsystem is None and cmd.hull, said
    cmd = parse("target their shields", ctx).commands[0]
    assert isinstance(cmd, SelectTarget) and cmd.subsystem == "shields" and not cmd.hull
