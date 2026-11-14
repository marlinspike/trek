"""The game is separate from its screen, and orders can travel (session/interface.py has the rules).

These guard the layering so the AI, game modes, a network link or a new presenter can change without
touching the UI: they fail the build the moment the boundary is crossed.
"""

from __future__ import annotations

import ast
import dataclasses
import hashlib
import json
import typing
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Union

import pytest

from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle
from begin.content import default_content
from begin.session import wire
from begin.session.battle import BattleSession
from begin.session.news import Line, Ticked
from begin.sim.commands import Command, FirePhasers, FireTorpedoes, SelectTarget, SetHelm

SRC = Path(__file__).resolve().parents[1] / "src" / "begin"

# what the UI may never import at run time: the world and its machinery, the minds in it, the models, and the
# session's own parts (the UI reaches a session only through session.interface.Session)
UI_FORBIDDEN = (
    "begin.sim.world", "begin.sim.systems", "begin.sim.factory", "begin.ai", "begin.llm",
    "begin.console.translator", "begin.console.orders", "begin.crew.conversation", "begin.crew.chatter",
    "begin.session.console", "begin.session.orders", "begin.session.comms", "begin.session.command",
    "begin.session.voices", "begin.session.state",
)
# the composition root builds sessions and battles; it is the one UI module allowed to know how
COMPOSITION_ROOT = {"begin.ui.app", "begin.ui.battle_scene"}


def _module(path: Path) -> str:
    rel = path.relative_to(SRC.parent).with_suffix("")
    parts = list(rel.parts)
    if parts[-1] == "__init__":
        parts.pop()
    return ".".join(parts)


def _runtime_imports(path: Path) -> list[str]:
    """Modules a file imports when it runs (imports under `if TYPE_CHECKING:` are for the type checker only)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    mod = _module(path)
    package = mod if path.name == "__init__.py" else mod.rsplit(".", 1)[0]
    skip: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.If) and "TYPE_CHECKING" in ast.unparse(node.test):
            for sub in node.body:
                for n in ast.walk(sub):
                    skip.add(id(n))
    out: list[str] = []
    for node in ast.walk(tree):
        if id(node) in skip:
            continue
        if isinstance(node, ast.Import):
            out += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                base = package.split(".")
                base = base[: len(base) - (node.level - 1)]
                name = ".".join(base + ([node.module] if node.module else []))
            else:
                name = node.module or ""
            out.append(name)
            out += [f"{name}.{a.name}" for a in node.names]
    return out


def _files(sub: str) -> list[Path]:
    return sorted((SRC / sub).rglob("*.py")) if sub else sorted(SRC.glob("*.py"))


def test_nothing_outside_the_ui_needs_pygame_or_the_ui() -> None:
    bad = []
    for path in sorted(SRC.rglob("*.py")):
        mod = _module(path)
        if mod.startswith("begin.ui") or mod == "begin.__main__":
            continue
        for name in _runtime_imports(path):
            if name == "pygame" or name.startswith("pygame.") or name.startswith("begin.ui"):
                bad.append(f"{mod} imports {name}")
    assert not bad, "the game must run without a screen:\n" + "\n".join(bad)


def test_the_ui_reaches_the_game_only_through_a_session() -> None:
    bad = []
    for path in _files("ui"):
        mod = _module(path)
        for name in _runtime_imports(path):
            if any(name == f or name.startswith(f + ".") for f in UI_FORBIDDEN):
                bad.append(f"{mod} imports {name}")
            if name.startswith("begin.session.battle") and mod not in COMPOSITION_ROOT:
                bad.append(f"{mod} imports {name} (only the composition root builds sessions)")
    assert not bad, "the UI must talk to a Session and read an Observation:\n" + "\n".join(bad)


def test_the_ui_never_touches_the_world() -> None:
    """No `.world` anywhere in the UI: what it shows comes from an Observation, what it changes goes by order."""
    bad = []
    for path in _files("ui"):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Attribute) and node.attr == "world":
                bad.append(f"{_module(path)}:{node.lineno}")
    assert not bad, "the UI reads the world directly at:\n" + "\n".join(bad)


def test_the_session_says_tones_never_colours() -> None:
    for path in _files("session"):
        names = _runtime_imports(path)
        assert not any(n.startswith("begin.ui") for n in names), _module(path)
        assert "theme." not in path.read_text(encoding="utf-8"), f"{_module(path)} speaks in colours"


# ------------------------------------------------------------------ orders on the wire

def _sample(hint: Any, name: str) -> Any:
    origin = typing.get_origin(hint)
    if origin in (Union, getattr(__import__("types"), "UnionType")):
        arms = [a for a in typing.get_args(hint) if a is not type(None)]
        return _sample(arms[0], name)
    if origin is Literal:
        return typing.get_args(hint)[0]
    if origin is tuple:
        inner = typing.get_args(hint)[0] if typing.get_args(hint) else int
        return (0, 2) if inner is int else (_sample(inner, name), _sample(inner, name + "2"))
    if isinstance(hint, type) and issubclass(hint, Enum):
        return list(hint)[-1]
    if hint is bool:
        return True
    if hint is int:
        return 3
    if hint is float:
        return 12.5
    if hint is str:
        return f"{name}-text"
    return None


@pytest.mark.parametrize("name", sorted(wire.command_types()))
def test_every_order_survives_the_wire(name: str) -> None:
    cls = wire.command_types()[name]
    hints = typing.get_type_hints(cls)
    kwargs = {f.name: _sample(hints[f.name], f.name) for f in dataclasses.fields(cls)
              if f.init and hints[f.name] is not object}
    cmd = cls(**kwargs)
    back = wire.loads(json.dumps(json.loads(wire.dumps(cmd))))
    assert type(back) is cls
    assert wire.encode(back) == wire.encode(cmd)


def test_bad_orders_are_refused_not_guessed() -> None:
    with pytest.raises(wire.WireError):
        wire.decode({"type": "Hyperspace", "ship_id": 1})
    with pytest.raises(wire.WireError):
        wire.decode({"type": "SetHelm", "ship_id": "one"})
    with pytest.raises(wire.WireError):
        wire.decode({"type": "SetHelm", "ship_id": 1, "hyperdrive": True})


# ------------------------------------------------------------------ lockstep: the same orders, the same battle

def _setup() -> BattleSetup:
    return BattleSetup([FleetSpec(0, [ShipSpec("federation.hc"), ShipSpec("federation.de")], player=True,
                                  center=(0.0, -9000.0)),
                        FleetSpec(1, [ShipSpec("klingon.bc"), ShipSpec("klingon.fr")], center=(0.0, 9000.0))], seed=11)


def _play(orders: dict[int, list[Command]]) -> str:
    world = build_battle(default_content(), _setup()).world
    for _ in range(600):
        for cmd in orders.get(world.tick, []):
            world.execute(cmd)
        world.step()
        if world.outcome.over:
            break
    h = hashlib.sha1()
    for s in sorted(world.ships.values(), key=lambda s: s.id):
        h.update(repr((s.id, round(s.x, 6), round(s.y, 6), s.course, s.warp, s.structure, s.status)).encode())
    return h.hexdigest()


def test_a_battle_replays_exactly_from_orders_sent_as_json() -> None:
    battle = build_battle(default_content(), _setup())
    me = battle.player_ship_id
    assert me is not None
    enemy = next(s.id for s in battle.world.ships.values() if s.side == 1)
    orders: dict[int, list[Command]] = {
        5: [SetHelm(ship_id=me, course=10.0, warp=6.0), SelectTarget(ship_id=me, target=enemy)],
        120: [FireTorpedoes(ship_id=me, tubes=None)],
        180: [FirePhasers(ship_id=me, banks=None), SetHelm(ship_id=me, course=350.0, warp=4.0)],
    }
    sent = {t: [wire.loads(wire.dumps(c)) for c in cs] for t, cs in orders.items()}
    assert _play(orders) == _play(sent)


# ------------------------------------------------------------------ a battle with no screen at all

def test_a_session_plays_without_a_screen() -> None:
    session = BattleSession(build_battle(default_content(), _setup()), hidden={}, llm={}, career={})
    heard: list[object] = []
    session.subscribe(heard.append)
    assert any(isinstance(n, Line) and "Battle stations" in n.text for n in heard)   # what it said before
    session.say("helm 10 warp 6")
    assert session.player is not None and session.player.desired_warp == 6.0
    session.paused = False
    ticks = sum(session.update(0.1) for _ in range(50))
    assert ticks >= 40
    assert sum(1 for n in heard if isinstance(n, Ticked) and n.stepped) == ticks
    assert all(not hasattr(n, "color") for n in heard)
    session.close()
