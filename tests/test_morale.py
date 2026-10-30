"""Crew morale: what lowers and raises it, what it does, and the captain's address."""

from __future__ import annotations

import time

import pygame
import pytest

from begin.battle import build_battle
from begin.console.parser import ParseContext, parse
from begin.llm.service import LLMService
from begin.presets import load_presets
from begin.sim.commands import AddressCrew, Authority
from begin.sim.systems.damage import DamageKind, apply_damage
from begin.sim.world import World


def _pair(content):  # type: ignore[no-untyped-def]
    w = World(content, seed=4)
    fed = w.add_ship("federation.hc", 0, 0, 0)
    kl = w.add_ship("klingon.bc", 1, 0, 6000)
    return w, fed, kl


def _hit(w, ship, attacker, amount: float) -> None:  # type: ignore[no-untyped-def]
    for sh in ship.shields:
        sh.up = False
    apply_damage(w, ship, amount, ship.x, ship.y + 500, DamageKind.PHASER, attacker.id)
    w.step()


def test_damage_shakes_a_crew_by_race_and_hits_lift_the_attackers(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, kl = _pair(content)
    assert fed.morale == 80 and kl.morale == 85 and fed.morale_base == 80
    f0, k0 = fed.morale, kl.morale
    _hit(w, fed, kl, 60)
    fed_drop = f0 - fed.morale
    assert fed_drop > 3 and kl.morale > k0                       # the Klingons cheer their hits
    w2, fed2, kl2 = _pair(content)
    _hit(w2, kl2, fed2, 60 * kl2.structure_max / fed2.structure_max)
    assert 0 < 85 - kl2.morale < fed_drop                         # the same share of hull shakes a Klingon less


def test_a_kill_lifts_the_side_and_spirits_settle_back_out_of_the_fight(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, kl = _pair(content)
    w.add_ship("klingon.bc", 1, 0, 60000)   # far off: the battle goes on, out of range
    before = fed.morale
    w.destroy_ship(kl, "test", fed.id)
    w.step()
    assert fed.morale >= before + 11                              # 6 for the side, 6 more for the ship that did it
    fed.morale = 40.0
    w.run(30)
    assert fed.morale > 40 and fed.morale <= fed.morale_base


def test_morale_speeds_or_slows_the_crew_a_little(content) -> None:  # type: ignore[no-untyped-def]
    loads = []
    for m in (100.0, 0.0):
        w = World(content, seed=4)
        s = w.add_ship("federation.hc", 0, 0, 0)
        s.morale = m
        w.run(1.5)
        loads.append(sum(t.charge for t in s.tubes))
    assert loads[0] > loads[1] * 1.2


def test_the_captains_address(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, _ = _pair(content)
    (c,) = parse("address crew Steady, people. We bring her home.", ParseContext(fed.id, w.observe(0))).commands
    assert isinstance(c, AddressCrew) and c.text == "Steady, people. We bring her home."
    (c2,) = parse("rally the crew: hold together", ParseContext(fed.id, w.observe(0))).commands
    assert c2.text == "hold together"     # type: ignore[attr-defined]
    fed.morale = 50.0
    c.issuer = Authority.CAPTAIN
    assert w.execute(c) is None and fed.morale == pytest.approx(58.0)
    again = w.execute(AddressCrew(ship_id=fed.id, text="again", issuer=Authority.CAPTAIN))
    assert again is not None and "ring hollow" in again and fed.morale == pytest.approx(58.0)
    w.run(61)
    assert w.execute(AddressCrew(ship_id=fed.id, text="once more", rousing=1.5)) is None


class _Judge:
    name = "judge"

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        assert "rousing" in system and messages[-1]["content"].startswith("We have")
        return '{"score": 1.5, "reaction": "Remarkable, Captain. They would follow you anywhere."}'


@pytest.fixture()
def scene(content):  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme
    from begin.ui.battle_scene import BattleScene

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    surf = pygame.display.set_mode((1400, 860))
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    sc = BattleScene(b, surf.get_size(), lambda: None, hidden={}, llm={})
    yield sc, surf
    sc.close()


def test_spock_remarks_on_spirits_and_the_model_judges_a_speech(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    me = sc.player
    sc.paused = False
    sc.overlay = None
    from begin.sim.systems.morale import adjust

    adjust(sc.world, me, -45, "damage")
    for _ in range(4):
        sc.update(0.05)
    said = [ln.text for ln in sc.log]
    assert any(t.startswith("Spock: Captain, the crew is shaken") and "A word from you" in t for t in said), said[-5:]
    sc.draw(surf)

    sc.bridge.llm = LLMService(_Judge(), workers=1)
    m0 = me.morale
    sc.run_console("address crew We have beaten worse than this. Stations, and steady.")
    end = time.time() + 5
    while me.morale <= m0 and time.time() < end:
        sc.update(0.0)
        time.sleep(0.01)
    assert me.morale == pytest.approx(m0 + 12.0, abs=1.0)
    assert any(ln.text == "Spock: Remarkable, Captain. They would follow you anywhere." for ln in sc.log)
