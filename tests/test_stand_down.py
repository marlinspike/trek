"""Standing the officers down: once Spock is flying and Seven is shooting, the captain can always stop them,
one officer at a time or the whole bridge at once."""

from __future__ import annotations

from collections.abc import Iterator

import pygame
import pytest

from begin.battle import build_battle
from begin.console.parser import ParseContext, parse
from begin.crew.conversation import whole_bridge_stand_down
from begin.presets import load_presets
from begin.sim.commands import Authority, CeaseFire, DelegateStation, Pursue, SetHelm, StandDown, TakeConn
from begin.sim.events import PhaserFired, TorpedoLaunched
from begin.sim.ship import HelmMode

SETUPS = {
    "helm delegated": ["delegate helm"],
    "spock took the helm": ["spock, take the helm"],
    "every station delegated": ["delegate all"],
    "spock has the bridge": ["spock, take the conn"],
}


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
    me = sc.player
    enemy = next(s for s in b.world.ships.values() if s.id != me.id)
    enemy.x, enemy.y = me.x + 3000, me.y + 5000
    sc.run_console(f"target #{enemy.id}")
    for line in lines:
        sc.run_console(line)
    sc.run_console("seven, disable their shields")
    _run(sc, 10.0)
    assert me.objectives, "Seven should be working on their shields"
    return sc


def _run(sc, secs: float) -> None:  # type: ignore[no-untyped-def]
    for _ in range(int(secs * 20)):
        sc.update(0.05)
        sc.overlay = None


def _after(sc, *lines: str, secs: float = 20.0) -> tuple[int, int]:  # type: ignore[no-untyped-def]
    """Say the lines, run the battle; (offensive shots, helm orders from officers) in that time."""
    me, w = sc.player, sc.world
    start = len(w.command_log)
    shots: list[object] = []
    emit = w.emit

    def spy(e):  # type: ignore[no-untyped-def]
        if isinstance(e, (TorpedoLaunched, PhaserFired)) and e.ship_id == me.id and not getattr(e, "defensive", False):
            shots.append(e)
        return emit(e)

    w.emit = spy
    for line in lines:
        sc.run_console(line)
    _run(sc, secs)
    w.emit = emit
    helm = [lc for lc in w.command_log[start:] if lc.accepted and lc.command.ship_id == me.id
            and isinstance(lc.command, (SetHelm, Pursue)) and lc.command.issuer < Authority.CAPTAIN]
    return len(shots), len(helm)


@pytest.fixture(params=list(SETUPS))
def flying(request, content) -> Iterator[object]:  # type: ignore[no-untyped-def]
    """Spock flying the ship one way or another, and Seven attacking the enemy's shields."""
    sc = _scene(content, SETUPS[request.param])
    yield sc
    sc.close()


@pytest.mark.parametrize("line", ["spock, stop", "spock, stand down", "spock, stop flying", "helm, stand down",
                                  "spock, knock it off"])
def test_telling_spock_to_stop_hands_back_the_helm(flying, line: str) -> None:  # type: ignore[no-untyped-def]
    shots, helm = _after(flying, line)
    me = flying.player
    assert (shots, helm) == (0, 0)
    assert "helm" not in me.delegated and me.conn == ""
    assert me.hold_fire and not me.objectives
    assert me.helm_mode == HelmMode.COURSE          # not still chasing the enemy on his last order


@pytest.mark.parametrize("line", ["stand down", "everyone stop", "all stations, stand down", "all hands stand down",
                                  "belay all", "stop everything", "officers, belay that"])
def test_standing_the_whole_bridge_down_stops_everyone(flying, line: str) -> None:  # type: ignore[no-untyped-def]
    shots, helm = _after(flying, line)
    me = flying.player
    assert (shots, helm) == (0, 0)
    assert not me.delegated and me.conn == ""
    assert me.hold_fire and not me.objectives and me.pending_volley is None
    assert not me.evasive and me.helm_mode == HelmMode.COURSE


@pytest.mark.parametrize("line", ["seven, stop disabling their shields", "seven, forget the shields",
                                  "seven, stop attacking their shields", "seven, don't disable their shields",
                                  "seven, never mind the shields", "seven, quit shooting at them"])
def test_telling_seven_to_stop_never_sets_her_off_again(content, line: str) -> None:  # type: ignore[no-untyped-def]
    sc = _scene(content, [])
    shots, _ = _after(sc, line)
    assert shots == 0 and not sc.player.objectives and sc.player.hold_fire
    sc.close()


def test_a_cease_fire_to_seven_leaves_spock_flying_and_says_how_to_stop_him(content) -> None:  # type: ignore[no-untyped-def]
    sc = _scene(content, ["delegate helm"])
    shots, helm = _after(sc, "seven, cease fire")
    assert shots == 0 and helm > 0 and "helm" in sc.player.delegated     # weapons only: the helm stays his
    sc.run_console("cease fire")
    assert any("stand down" in line.text for line in sc.log[-4:])
    sc.close()


@pytest.mark.parametrize("line", ["assume all", "assume science"])
def test_taking_seven_s_station_back_ends_her_objective(content, line: str) -> None:  # type: ignore[no-untyped-def]
    sc = _scene(content, ["delegate science"])
    shots, _ = _after(sc, line)
    assert shots == 0 and not sc.player.objectives
    assert not sc.player.hold_fire          # a station taken back is not a cease fire: the captain may still shoot
    sc.close()


def test_i_have_the_helm_takes_it_back_without_holding_fire(content) -> None:  # type: ignore[no-untyped-def]
    sc = _scene(content, ["delegate helm"])
    _, helm = _after(sc, "spock, I have the helm")
    assert helm == 0 and "helm" not in sc.player.delegated and not sc.player.hold_fire
    sc.close()


def test_the_words(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, load_presets()[0].setup())
    ctx = ParseContext(b.player_ship_id, b.world.observe(0))
    assert isinstance(parse("stand down", ctx).commands[0], StandDown)
    assert isinstance(parse("stand down all", ctx).commands[0], StandDown)
    assert isinstance(parse("belay all", ctx).commands[0], StandDown)
    assert isinstance(parse("stop everything", ctx).commands[0], StandDown)
    assert isinstance(parse("belay", ctx).commands[0], CeaseFire)
    assert parse("stop", ctx).commands[0].name == "helm"                    # a bare stop is still all stop
    for said in ("everyone stop", "all hands, stand down", "bridge crew stand down", "everybody knock it off"):
        assert whole_bridge_stand_down(said), said
    for said in ("stop", "spock, stop", "stand down", "crew", "everyone fire"):
        assert not whole_bridge_stand_down(said), said


def test_stand_down_in_the_simulation(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    w, me = b.world, b.world.ships[b.player_ship_id]
    enemy = next(s for s in w.ships.values() if s.id != me.id)
    w.execute(DelegateStation(ship_id=me.id, station="tactical"))
    w.execute(TakeConn(ship_id=me.id, officer="spock"))
    w.execute(Pursue(ship_id=me.id, target=enemy.id, issuer=Authority.OFFICER))
    assert me.helm_mode == HelmMode.PURSUE
    assert w.execute(StandDown(ship_id=me.id)) is None
    assert not me.delegated and me.conn == "" and not me.conn_saved
    assert me.hold_fire and me.helm_mode == HelmMode.COURSE and me.helm_target is None


@pytest.mark.parametrize("line", ["I have nav", "i have navigation", "I have the helm", "I've got the helm",
                                  "spock, I have nav"])
def test_i_have_nav_takes_the_helm_back_and_ends_the_attack(flying, line: str) -> None:  # type: ignore[no-untyped-def]
    _, helm = _after(flying, line)
    me = flying.player
    assert helm == 0 and "helm" not in me.delegated and not me.objectives
    assert not me.hold_fire and me.helm_mode == HelmMode.COURSE


@pytest.mark.parametrize("line", ["I have fire", "I have weapons", "I have phasers", "I have torps",
                                  "i have torpedoes", "worf, I have weapons", "seven, I have weapons"])
def test_i_have_weapons_takes_tactical_back_and_ends_seven_s_attack(content, line: str) -> None:  # type: ignore[no-untyped-def]
    sc = _scene(content, ["delegate all"])
    shots, _ = _after(sc, line)
    me = sc.player
    assert shots == 0 and "tactical" not in me.delegated and not me.objectives
    assert "helm" in me.delegated               # only the weapons came back: Spock still flies
    assert not me.hold_fire                     # the guns are the captain's now, not held
    sc.close()


def test_i_have_the_conn_with_nobody_on_the_bridge_takes_every_station_back(content) -> None:  # type: ignore[no-untyped-def]
    sc = _scene(content, ["delegate all"])
    shots, helm = _after(sc, "I have the conn")
    assert (shots, helm) == (0, 0) and not sc.player.delegated and not sc.player.objectives
    sc.close()


@pytest.mark.parametrize("line", ["evasive", "Evasive", "evasive manoeuvres", "evasive maneuvers", "Evasive manuevers", "evasive action",
                                  "take evasive action", "spock, evasive manoeuvres", "spock, take evasive action"])
def test_evasive_manoeuvres_in_every_spelling(content, line: str) -> None:  # type: ignore[no-untyped-def]
    sc = _scene(content, [])
    sc.run_console(line)
    assert sc.player.evasive
    sc.close()


def test_i_have_words(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, load_presets()[0].setup())
    ctx = ParseContext(b.player_ship_id, b.world.observe(0))
    for said, stations in [("I have nav", ["helm"]), ("I have fire", ["tactical"]), ("I have weapons", ["tactical"]),
                           ("I have phasers", ["tactical"]), ("I have torps", ["tactical"]),
                           ("I have shields", ["engineering"]), ("I have sensors", ["science"]),
                           ("I have nav and weapons", ["helm", "tactical"]),
                           ("I have the conn", ["helm", "tactical", "engineering", "science"])]:
        cmds = parse(said, ctx).commands
        assert all(isinstance(c, DelegateStation) and not c.on for c in cmds), said
        assert [c.station for c in cmds if isinstance(c, DelegateStation)] == stations, said
    assert parse("I have bananas", ctx).error is not None
