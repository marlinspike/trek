"""Targeting and stop orders under pressure: punctuation, typos, several orders in one line, orders to more than
one officer, orders given mid-attack, and answers from a language model that arrive after a cease fire."""

from __future__ import annotations

import threading
import time

import pygame
import pytest

from begin.battle import build_battle
from begin.console.parser import ParseContext, parse
from begin.console.translator import Translator
from begin.llm.service import LLMService
from begin.presets import load_presets
from begin.sim.commands import (
    CeaseFire, DelegateStation, Evasive, FirePhasers, SelectTarget, SetHelm, SetObjective, StandDown,
)
from begin.sim.events import ObjectiveEnded, PhaserFired, TorpedoLaunched


def _parsing(content, preset: str = "dreadnought-duel"):  # type: ignore[no-untyped-def]
    b = build_battle(content, next(p for p in load_presets() if p.id == preset).setup())
    me = b.world.ships[b.player_ship_id]
    enemies = [s for s in b.world.ships.values() if s.side != me.side]
    me.target = enemies[0].id

    def run(said: str):  # type: ignore[no-untyped-def]
        return parse(said, ParseContext(me.id, b.world.observe(me.side)))

    return run, me, enemies


def _scene(content, lines: list[str] = [], seed: int | None = None):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme
    from begin.ui.battle_scene import BattleScene

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup(seed))
    sc = BattleScene(b, surf.get_size(), lambda: None, hidden={}, llm={})
    sc.overlay, sc.paused = None, False
    enemy = next(s for s in b.world.ships.values() if s.side != sc.player.side)
    enemy.x, enemy.y = sc.player.x + 3000, sc.player.y + 5000
    sc.run_console(f"target #{enemy.id}")
    for line in lines:
        sc.run_console(line)
    return sc, enemy


def _run(sc, secs: float) -> None:  # type: ignore[no-untyped-def]
    for _ in range(int(secs * 20)):
        sc.update(0.05)
        sc.overlay = None


def _spy(sc) -> dict[str, list[object]]:  # type: ignore[no-untyped-def]
    w, me = sc.world, sc.player
    seen: dict[str, list[object]] = {"shots": [], "done": []}
    emit = w.emit

    def spy(e):  # type: ignore[no-untyped-def]
        if isinstance(e, (TorpedoLaunched, PhaserFired)) and e.ship_id == me.id and not getattr(e, "defensive", False):
            seen["shots"].append(e)
        if isinstance(e, ObjectiveEnded) and e.outcome == "done":
            seen["done"].append(e.group)
        return emit(e)

    w.emit = spy
    return seen


# ------------------------------------------------------------------ the console, said to nobody in particular

@pytest.mark.parametrize("said", ["Cease fire!", "cease fire.", "ceasefire!", "cease-fire", "seize fire", "ceese fire",
                                  "hold your fire", "don't shoot", "dont fire", "weapons cold", "stop attacking",
                                  "stop the attack", "abort the attack", "break off", "call off the attack",
                                  "disengage", "leave them alone", "let her go", "spare them", "forget the shields",
                                  "stop disabling their shields", "never mind", "nevermind", "cancel that", "cancel"])
def test_every_way_of_saying_cease_fire_is_a_cease_fire(content, said: str) -> None:  # type: ignore[no-untyped-def]
    run, _, _ = _parsing(content)
    res = run(said)
    assert res.error is None and [type(c) for c in res.commands] == [CeaseFire], said


@pytest.mark.parametrize("said", ["stand down!", "Stand down.", "standdown", "stand-down", "knock it off",
                                  "that's enough", "enough!"])
def test_every_way_of_saying_stand_down_is_a_stand_down(content, said: str) -> None:  # type: ignore[no-untyped-def]
    run, _, _ = _parsing(content)
    assert [type(c) for c in run(said).commands] == [StandDown], said


def test_all_stop_is_the_engines_and_abort_is_still_the_self_destruct(content) -> None:  # type: ignore[no-untyped-def]
    run, _, _ = _parsing(content)
    cmd = run("all stop").commands[0]
    assert isinstance(cmd, SetHelm) and cmd.warp == 0.0
    assert not any(isinstance(c, CeaseFire) for c in run("abort").commands)


@pytest.mark.parametrize("said, kinds", [
    ("cease fire and take evasive action", [CeaseFire, Evasive]),
    ("cease fire, evasive", [CeaseFire, Evasive]),
    ("cease fire then evasive!", [CeaseFire, Evasive]),
    ("evasive and cease fire", [Evasive, CeaseFire]),
    ("stand down, I have nav", [StandDown, DelegateStation]),
])
def test_several_orders_in_one_line_are_all_carried_out(content, said: str, kinds: list[type]) -> None:  # type: ignore[no-untyped-def]
    run, _, _ = _parsing(content)
    res = run(said)
    assert res.error is None and [type(c) for c in res.commands] == kinds


def test_a_line_that_only_looks_like_two_orders_is_not_split(content) -> None:  # type: ignore[no-untyped-def]
    run, _, _ = _parsing(content)
    assert run("7, stand down").error is not None        # no course change smuggled in front of the stand down
    assert [type(c) for c in run("i have nav and weapons").commands] == [DelegateStation, DelegateStation]


@pytest.mark.parametrize("said, group", [
    ("target thier shields", "shields"), ("target their sheilds", "shields"), ("target her shields", "shields"),
    ("target its engines", "propulsion"), ("target the shields", "shields"), ("target both their shields", "shields"),
    ("aim at their shields", "shields"), ("hit their shields", "shields"), ("bring down their shields", "shields"),
    ("take their shields out", "shields"), ("I want their shields down", "shields"),
    ("target their phazers", "phasers"),
])
def test_plain_and_misspelt_disables(content, said: str, group: str) -> None:  # type: ignore[no-untyped-def]
    run, _, enemies = _parsing(content)
    res = run(said)
    assert res.error is None, res.error
    cmd = res.commands[0]
    assert isinstance(cmd, SetObjective) and (cmd.goal, cmd.group, cmd.targets) == ("disable", group, (enemies[0].id,))


def test_the_klingons_shields_and_the_other_ships_shields(content) -> None:  # type: ignore[no-untyped-def]
    run, _, enemies = _parsing(content, "pirate-hunt")
    cmd = run("target the orions' shields").commands[0]
    assert isinstance(cmd, SetObjective) and set(cmd.targets) == {e.id for e in enemies}
    cmd = run("target the other ship's shields").commands[0]
    assert isinstance(cmd, SetObjective) and cmd.targets == (enemies[1].id,)


def test_two_systems_in_one_order_are_two_objectives(content) -> None:  # type: ignore[no-untyped-def]
    run, _, _ = _parsing(content)
    for said in ("target their shields and engines", "disable their engines and phasers",
                 "take out their shields then their engines"):
        groups = [c.group for c in run(said).commands if isinstance(c, SetObjective)]
        assert len(groups) == 2 and len(set(groups)) == 2, said
    assert [c.group for c in run("disable their weapons and phasers").commands] == ["weapons"]


def test_aiming_words_that_are_not_a_disable(content) -> None:  # type: ignore[no-untyped-def]
    run, _, enemies = _parsing(content)
    cmd = run("target their life support").commands[0]
    assert isinstance(cmd, SelectTarget) and cmd.subsystem == "crew"
    cmd = run("fire phasers at their shields").commands[0]
    assert isinstance(cmd, FirePhasers) and cmd.subsystem == "shields" and cmd.target in (None, enemies[0].id)
    assert isinstance(run("target shields").commands[0], SelectTarget)      # the console's precision aim stays


@pytest.mark.parametrize("said", ["finish her off", "finish them", "finish off the wraith", "take them all out"])
def test_finishing_her_is_destroying_her(content, said: str) -> None:  # type: ignore[no-untyped-def]
    run, _, _ = _parsing(content)
    cmd = run(said).commands[0]
    assert isinstance(cmd, SetObjective) and cmd.goal == "destroy", said


@pytest.mark.parametrize("said, stations", [
    ("I have it", 4), ("I'll take it from here", 4), ("I'll take the helm", 1), ("give me the helm", 1),
    ("helm is mine", 1), ("I'll fly", 1), ("I have nav!", 1),
])
def test_more_ways_to_take_a_station_back(content, said: str, stations: int) -> None:  # type: ignore[no-untyped-def]
    run, _, _ = _parsing(content)
    cmds = run(said).commands
    assert len(cmds) == stations and all(isinstance(c, DelegateStation) and not c.on for c in cmds), said


# ------------------------------------------------------------------ said to the officers

@pytest.mark.parametrize("line", ["mr worf, target their shields", "lieutenant worf, target their shields",
                                  "worff, target their shields", "worf, can you target their shields?",
                                  "worf, please hit their shields", "worf, i want their shields down",
                                  "worf, take down their shields", "worf, go after their shields"])
def test_the_weapons_officer_understands_it_however_it_is_put(content, line: str) -> None:  # type: ignore[no-untyped-def]
    sc, enemy = _scene(content)
    sc.run_console(line)
    assert [(o.goal, o.group, o.officer) for o in sc.player.objectives] == [("disable", "shields", "worf")], line
    sc.close()


def test_a_question_about_disabling_fires_nothing(content) -> None:  # type: ignore[no-untyped-def]
    sc, _ = _scene(content)
    sc.run_console("worf, should we disable their shields?")
    assert not sc.player.objectives
    sc.close()


@pytest.mark.parametrize("line", ["wrof, cease fire", "sevn, stand down", "spok, stop", "weapons cold"])
def test_a_misspelt_name_still_stops_them(content, line: str) -> None:  # type: ignore[no-untyped-def]
    sc, _ = _scene(content, ["delegate all", "seven, disable their shields"])
    sc.run_console(line)
    assert sc.player.hold_fire and not sc.player.objectives, line
    sc.close()


def test_orders_to_two_officers_in_one_line_go_to_each(content) -> None:  # type: ignore[no-untyped-def]
    sc, _ = _scene(content)
    sc.run_console("worf target their shield, seven take the conn")
    me = sc.player
    assert me.conn == "seven"                            # not Worf, who was only told to target the shields
    assert [(o.group, o.officer) for o in me.objectives] == [("shields", "worf")]
    sc.close()
    sc, _ = _scene(content)
    sc.run_console("worf, target their shields and spock, take the helm")
    assert "helm" in sc.player.delegated and [o.officer for o in sc.player.objectives] == ["worf"]
    sc.close()


def test_one_officer_two_orders(content) -> None:  # type: ignore[no-untyped-def]
    sc, _ = _scene(content, ["seven, disable their shields"])
    sc.run_console("worf, cease fire and target their engines")
    me = sc.player
    assert [(o.group, o.officer) for o in me.objectives] == [("propulsion", "worf")] and not me.hold_fire
    sc.close()


# ------------------------------------------------------------------ in the middle of an attack

@pytest.mark.parametrize("stop", ["cease fire", "Cease fire!", "stand down", "seven, stand down", "worf, cease fire"])
def test_a_new_order_after_a_cease_fire_gets_the_guns_firing_again(content, stop: str) -> None:  # type: ignore[no-untyped-def]
    sc, _ = _scene(content, ["seven, disable their shields"])
    _run(sc, 3.0)
    sc.run_console(stop)
    seen = _spy(sc)
    _run(sc, 5.0)
    assert seen["shots"] == [] and sc.player.hold_fire
    sc.run_console("seven, disable their shields")
    _run(sc, 30.0)
    assert seen["shots"], f"after '{stop}' a new order never fired a shot"
    sc.close()


def test_disabling_two_systems_finishes_both_and_spares_her(content) -> None:  # type: ignore[no-untyped-def]
    sc, enemy = _scene(content, ["delegate helm"], seed=2)
    seen = _spy(sc)
    sc.run_console("target their shields and engines")
    for _ in range(180 * 20):
        sc.update(0.05)
        sc.overlay = None
        if len(seen["done"]) == 2:
            break
    assert sorted(seen["done"]) == ["propulsion", "shields"]   # the shields done doesn't stop work on the engines
    assert enemy.exists and enemy.structure > 0 and enemy.id in sc.player.spared
    sc.close()


# ------------------------------------------------------------------ with a language model

class _Gate:
    """A model that answers only when told to."""
    name = "fake"

    def __init__(self, reply: str) -> None:
        self.reply, self.go = reply, threading.Event()

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        self.go.wait(5)
        return self.reply


def _flush(sc) -> None:  # type: ignore[no-untyped-def]
    end = time.time() + 1.0
    while time.time() < end:
        sc.update(0.0)
        time.sleep(0.01)


@pytest.mark.parametrize("stop", ["cease fire", "stand down", "worf, stand down", "seven, cease fire"])
def test_an_answer_that_arrives_after_a_stop_sets_nobody_to_work(content, stop: str) -> None:  # type: ignore[no-untyped-def]
    sc, _ = _scene(content, ["delegate tactical"])
    gate = _Gate('{"say": "Engaging.", "commands": ["disable shields", "destroy them"]}')
    sc.bridge.llm = LLMService(gate)
    sc.run_console("worf, go get them, make them regret it")
    assert sc.bridge.llm.busy("worf")
    sc.run_console(stop)
    gate.go.set()
    _flush(sc)
    assert not sc.player.objectives and sc.player.hold_fire
    assert not any("Engaging." in ln.text for ln in sc.log if ln.text.startswith("Worf"))
    sc.close()


@pytest.mark.parametrize("stop", ["Cease fire!", "hold your fire", "stand down!"])
def test_a_punctuated_cease_fire_never_waits_on_the_model(content, stop: str) -> None:  # type: ignore[no-untyped-def]
    sc, _ = _scene(content)
    gate = _Gate('{"commands": ["fire all phasers"], "say": ""}')
    sc.translator = Translator(LLMService(gate, workers=1), "fallback")
    sc.run_console("let them have it with everything we've got")
    assert sc.translator.busy()
    sc.run_console(stop)
    assert sc.player.hold_fire and not sc.translator.busy()     # at once, and the order in flight is dropped
    gate.go.set()
    _flush(sc)
    assert sc.player.hold_fire
    sc.close()
