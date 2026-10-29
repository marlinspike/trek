"""Headless AI battles: repeatable, bounded, and the AI only ever sees observations."""

from __future__ import annotations

import pytest

from begin.ai.captain import AICaptain
from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle, quick_battle
from begin.presets import load_presets
from begin.sim.observation import Observation
from begin.sim.scoring import Assessment


def _fp(world):  # type: ignore[no-untyped-def]
    return tuple((s.id, round(s.x, 4), round(s.y, 4), s.crew, round(s.structure, 4), s.status.value)
                 for s in world.ships.values()) + (world.tick,)


def test_ai_battles_are_repeatable(content) -> None:  # type: ignore[no-untyped-def]
    def run():  # type: ignore[no-untyped-def]
        b = build_battle(content, quick_battle(content, 77, size=2))
        b.world.run(120)
        return _fp(b.world)
    assert run() == run()


def test_ai_duel_reaches_a_result(content) -> None:  # type: ignore[no-untyped-def]
    setup = BattleSetup([FleetSpec(0, [ShipSpec("federation.hc")]), FleetSpec(1, [ShipSpec("klingon.bc")])], seed=1)
    b = build_battle(content, setup)
    b.world.run(900)
    w = b.world
    assert any(s.stats.damage_dealt > 0 for s in w.ships.values())
    assert w.outcome.over or any(not s.alive or cap.retreating for s, cap in
                                 ((w.ships[i], c) for i, c in b.captains.items()))


def test_ai_receives_only_observations(content, monkeypatch) -> None:  # type: ignore[no-untyped-def]
    seen: list[type] = []
    orig = AICaptain.think

    def spy(self, obs):  # type: ignore[no-untyped-def]
        seen.append(type(obs))
        return orig(self, obs)

    monkeypatch.setattr(AICaptain, "think", spy)
    b = build_battle(content, quick_battle(content, 5))
    b.world.run(5)
    assert seen and all(t is Observation for t in seen)


def test_presets_build_and_run(content) -> None:  # type: ignore[no-untyped-def]
    for p in load_presets():
        b = build_battle(content, p.setup())
        b.world.run(10)
        assert b.world.tick == 100


def test_ship_limit(content) -> None:  # type: ignore[no-untyped-def]
    too_many = BattleSetup([FleetSpec(0, [ShipSpec("orion.as")] * 31), FleetSpec(1, [ShipSpec("orion.as")] * 30)])
    with pytest.raises(ValueError):
        build_battle(content, too_many)


def test_assessment_scores_a_win(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, BattleSetup([FleetSpec(0, [ShipSpec("federation.hc")], player=True),
                                           FleetSpec(1, [ShipSpec("klingon.bc")])]))
    w = b.world
    a = Assessment.begin(w)
    enemy = next(s for s in w.ships.values() if s.side == 1)
    w.destroy_ship(enemy, "test", b.player_ship_id)
    w.step()
    assert a.score(w, 0) > 5
    assert "victory" in a.verdict(a.score(w, 0))
