"""Named tactical orders: written in config/orders.toml, run by name, with waits, targets and belay."""

from __future__ import annotations

import json
import os
import time
from pathlib import Path

import pygame
import pytest

from begin.battle import build_battle
from begin.console.orders import OrderBook, aim, read_orders
from begin.console.parser import ParseContext, parse
from begin.llm.service import LLMService
from begin.presets import load_presets

EXAMPLE = Path(__file__).resolve().parents[1] / "config" / "orders.example.toml"

BETA = """
[beta-1]
note = "Fan and hand over"
steps = [
    "helm 180 speed 5",
    "fire all torpedoes spread 10",
    "wait 2",
    "spock, you have the conn",
    "seven, disable their shields",
]
"""


def test_reading_orders(tmp_path: Path) -> None:
    (tmp_path / "orders.toml").write_text("""
quick = ["raise all", "wait 1", "fire all phasers"]
"Bad Name" = ["stop"]
""" + BETA + """
[loop]
steps = ["execute order beta-1", "stop"]
""")
    orders, problems = read_orders(tmp_path / "orders.toml")
    assert set(orders) == {"beta-1", "quick", "loop"}
    beta = orders["beta-1"]
    assert beta.note == "Fan and hand over" and len(beta.steps) == 5
    assert beta.steps[2].is_wait and beta.steps[2].wait == 2
    assert [s.text for s in orders["loop"].steps] == ["stop"]
    assert any("Bad Name" in p for p in problems) and any("cannot run another order" in p for p in problems)
    ex, ex_problems = read_orders(EXAMPLE)
    assert "beta-1" in ex and not ex_problems
    assert aim("cripple their shields", 7) == "cripple #7 shields"
    assert aim("pursue the target warp 6", 7) == "pursue #7 warp 6"
    assert aim("seven, disable their shields", 7) == "seven, disable their shields"   # officers read it as said
    assert aim("lock all banks on #T", 7) == "lock all banks on #7"


def test_console_verbs(content) -> None:  # type: ignore[no-untyped-def]
    b = build_battle(content, next(p for p in load_presets() if p.id == "dreadnought-duel").setup())
    ctx = ParseContext(b.player_ship_id, b.world.observe(0))
    assert parse("execute order beta-1", ctx).actions == [("execute", "beta-1")]
    assert parse("exec beta-1", ctx).actions == [("execute", "beta-1")]
    assert parse("orders", ctx).actions == [("orders", None)]
    assert parse("belay that", ctx).actions == [("belay", None)]
    assert parse("execute", ctx).error is not None


@pytest.fixture()
def scene(content):  # type: ignore[no-untyped-def]
    (Path(os.environ["BEGIN_HOME"]) / "orders.toml").write_text(BETA + """
[close]
steps = ["come about and run"]
""")
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


def _said(sc) -> list[str]:  # type: ignore[no-untyped-def]
    return [ln.text for ln in sc.log]


def test_an_order_runs_its_steps_in_turn_and_waits(scene) -> None:  # type: ignore[no-untyped-def]
    sc, surf = scene
    me = sc.player
    assert any("close: 'come about and run'" in t for t in _said(sc))   # no model: flagged at the start
    wraith = next(iter(sc.obs.contacts()))
    sc.run_console(f"target #{wraith}")
    sc.world.run(6)                                     # tubes loaded
    sc.run_console("beta-1")
    assert me.desired_course == pytest.approx(180) and me.stats.torpedoes_fired > 0
    assert me.conn == ""                                # waiting: Spock doesn't have the bridge yet
    assert sc.order_run is not None
    sc.paused = False
    sc.overlay = None
    end = sc.world.tick + 3 * sc.world.rules.ticks_per_cycle
    while sc.world.tick < end:
        sc.update(0.05)
    assert me.conn == "spock"
    assert any(o for o in me.objectives), me.objectives  # Seven is after their shields
    assert sc.order_run is None and any("Order beta-1 complete" in t for t in _said(sc))
    sc.run_console("orders")
    assert sc.printout is not None and any("beta-1" in ln for ln in sc.printout)
    sc.draw(surf)


def test_belay_stops_an_order(scene) -> None:  # type: ignore[no-untyped-def]
    sc, _ = scene
    sc.run_console("execute order beta-1")
    assert sc.order_run is not None
    sc.run_console("belay")
    assert sc.order_run is None and any("belayed (2 steps not run)" in t for t in _said(sc))
    sc.paused = False
    sc.overlay = None
    for _ in range(80):
        sc.update(0.05)
    assert sc.player.conn == ""
    sc.run_console("execute gamma-9")
    assert "No named order 'gamma-9'" in _said(sc)[-1]


class _Translate:
    name = "orders"

    def complete(self, system: str, messages: list[dict[str, str]]) -> str:
        assert "#T" in system and messages[-1]["content"] == "come about and run"
        return '{"commands": ["elude #T warp 8"], "say": "", "clarify": ""}'


def test_plain_english_steps_are_translated_once_and_remembered(scene) -> None:  # type: ignore[no-untyped-def]
    sc, _ = scene
    wraith = next(iter(sc.obs.contacts()))
    sc.run_console(f"target #{wraith}")
    book = OrderBook.load(Path(os.environ["BEGIN_HOME"]))
    book.llm = LLMService(_Translate(), workers=1)
    sc.orders.close()
    sc.orders = book
    assert book.prepare(sc._would_run, "", wraith) == []
    end = time.time() + 5
    while book.busy() and time.time() < end:
        sc.update(0.0)
        time.sleep(0.01)
    assert book.lines["come about and run"].commands == ["elude #T warp 8"]
    cache = json.loads((Path(os.environ["BEGIN_HOME"]) / "orders.cache.json").read_text())
    assert cache == {"come about and run": ["elude #T warp 8"]}
    sc.run_console("close")
    assert f"» elude #{wraith} warp 8" in _said(sc)
    again = OrderBook.load(Path(os.environ["BEGIN_HOME"]))          # the next battle needs no model for it
    assert again.prepare(sc._would_run, "", wraith) == [] and again.lines["come about and run"].commands
