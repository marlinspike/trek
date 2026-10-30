"""Cease fire: every way of saying it stops the guns, Seven's bait volley included."""

from __future__ import annotations

import time

import pygame
import pytest

from begin.battle import build_battle
from begin.console.parser import ParseContext, parse
from begin.console.translator import Translator
from begin.llm.service import LLMService
from begin.presets import load_presets
from begin.sim.commands import Authority, CeaseFire, FirePhasers, FireTorpedoes, OpenFire
from begin.sim.events import PhaserFired, TorpedoLaunched


@pytest.fixture()
def baiting(content):  # type: ignore[no-untyped-def]
    """A duel in which Seven, told to disable the enemy's shields, has just fired a bait torpedo."""
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
    sc.run_console("seven, disable their shields")
    for _ in range(600):
        sc.update(0.05)
        sc.overlay = None
        if me.pending_volley:
            break
    assert me.pending_volley and me.objectives
    yield sc
    sc.close()


def _shots_after(sc, line: str, secs: float = 20.0) -> list[str]:  # type: ignore[no-untyped-def]
    """Run a console line, then the battle, and list the player's offensive shots."""
    me, world = sc.player, sc.world
    shots: list[str] = []
    emit = world.emit

    def spy(e):  # type: ignore[no-untyped-def]
        if isinstance(e, (TorpedoLaunched, PhaserFired)) and e.ship_id == me.id and not getattr(e, "defensive", False):
            shots.append(type(e).__name__)
        return emit(e)

    world.emit = spy
    sc.run_console(line)
    for _ in range(int(secs * 20)):
        sc.update(0.05)
        sc.overlay = None
    return shots


@pytest.mark.parametrize("line", [
    "cease fire", "ceasefire", "hold fire", "stop firing", "belay",
    "seven, cease fire", "seven, stop firing", "seven, stop", "seven, belay that", "seven, stand down",
    "seven, cancel that", "worf, hold fire",
])
def test_every_way_of_saying_it_stops_the_bait(baiting, line: str) -> None:  # type: ignore[no-untyped-def]
    assert _shots_after(baiting, line) == []
    me = baiting.player
    assert me.hold_fire and not me.objectives and me.pending_volley is None


def test_stand_down_hands_the_station_back_too(baiting) -> None:  # type: ignore[no-untyped-def]
    baiting.run_console("delegate science")
    assert "science" in baiting.player.delegated
    _shots_after(baiting, "seven, stand down", 1.0)
    assert "science" not in baiting.player.delegated


def test_a_bare_stop_is_still_all_stop(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, load_presets()[0].setup())
    ctx = ParseContext(b.player_ship_id, b.world.observe(0))
    assert parse("stop", ctx).commands[0].name == "helm"
    assert isinstance(parse("stop shooting", ctx).commands[0], CeaseFire)
    assert isinstance(parse("open fire", ctx).commands[0], OpenFire)
    assert parse("hold course", ctx).error is not None


def test_the_hold_binds_officers_and_computer_until_the_captain_fires(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    w, me = b.world, b.world.ships[b.player_ship_id]
    enemy = next(s for s in w.ships.values() if s.id != me.id)
    enemy.x, enemy.y = me.x + 3000, me.y + 3000
    w.run(30)
    assert w.execute(CeaseFire(ship_id=me.id)) is None and me.hold_fire
    for issuer in (Authority.COMPUTER, Authority.OFFICER):
        assert w.execute(FireTorpedoes(ship_id=me.id, target=enemy.id, issuer=issuer)) == \
            "Holding fire on the captain's order."
    # point defense still shoots: it is never held
    pd = FirePhasers(ship_id=me.id, banks=(0,), at_bearing=0.0, defensive=True, issuer=Authority.COMPUTER)
    assert w._held(pd) is None
    assert w.execute(FireTorpedoes(ship_id=me.id, target=enemy.id)) is None   # the captain fires: weapons free
    assert not me.hold_fire
    w.execute(CeaseFire(ship_id=me.id))
    w.execute(OpenFire(ship_id=me.id))
    assert not me.hold_fire


class _Slow:
    """A language model that takes its time and then says to fire everything."""

    name = "slow"

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        time.sleep(0.4)
        return '{"commands": ["fire all torpedoes"], "say": "", "clarify": ""}'


def test_cease_fire_never_waits_on_the_model_and_drops_what_it_was_doing(baiting) -> None:  # type: ignore[no-untyped-def]
    sc = baiting
    sc.translator = Translator(LLMService(_Slow(), workers=1), "always")
    sc.run_console("give them everything we have")
    assert sc.translator.busy()
    sc.run_console("cease fire")
    assert not sc.translator.busy() and sc.player.hold_fire       # ran at once, the pending line forgotten
    time.sleep(0.6)
    assert _shots_after(sc, "status", 5.0) == []
