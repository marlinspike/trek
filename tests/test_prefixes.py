"""Abbreviated orders: a verb prefix several commands share is settled by the rest of the line."""

from __future__ import annotations

import pytest

from begin.console.parser import ParseContext, parse
from begin.console.plain import split_orders
from begin.sim.commands import AllyOrder, CeaseFire, DeflectorPulse, LockWeapons, Pursue, SelectTarget, SetObjective

from .conftest import make_world


@pytest.fixture()
def setup(content):  # type: ignore[no-untyped-def]
    w = make_world(content)
    me = w.add_ship("federation.hc", 0, 0, 0, name="Enterprise")
    ally = w.add_ship("federation.hc", 0, 800, 0, name="Agena")
    foe = w.add_ship("klingon.bc", 1, 0, 3000, name="Talon")
    w.step()
    return w, me, ally, foe


def p(w, me, text):  # type: ignore[no-untyped-def]
    return parse(text, ParseContext(me.id, w.observe(0)))


@pytest.mark.parametrize("text", ["pu tal", "pu talon", "pur tal", "pu the tal", "pu #3"])
def test_pu_tal_pursues_the_talon(setup, text) -> None:  # type: ignore[no-untyped-def]
    w, me, _, foe = setup
    r = p(w, me, text.replace("#3", f"#{foe.id}"))
    assert r.error is None, r.error
    (c,) = r.commands
    assert isinstance(c, Pursue) and c.target == foe.id and not c.elude


def test_pu_tal_with_warp(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, _, foe = setup
    (c,) = p(w, me, "pu tal warp 5").commands
    assert isinstance(c, Pursue) and c.target == foe.id and c.warp == 5


def test_pu_alone_is_the_pulse(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, _, _ = setup
    (c,) = p(w, me, "pu").commands          # pursue needs a ship: only the pulse makes sense of it
    assert isinstance(c, DeflectorPulse)


@pytest.mark.parametrize(("text", "kind"), [("ta tal", SelectTarget), ("lo tal", LockWeapons), ("de tal", SetObjective)])
def test_other_shared_prefixes_follow_the_ship(setup, text, kind) -> None:  # type: ignore[no-untyped-def]
    w, me, _, foe = setup
    r = p(w, me, text)
    assert r.error is None, r.error
    (c,) = r.commands
    assert isinstance(c, kind)
    assert foe.id in ((c.target,) if hasattr(c, "target") else c.targets)  # type: ignore[attr-defined]
    if isinstance(c, SetObjective):
        assert c.goal == "destroy"       # not a probe detonated on the code 'tal'


@pytest.mark.parametrize("text", ["ta", "re", "de"])
def test_still_ambiguous_says_so(setup, text) -> None:  # type: ignore[no-untyped-def]
    w, me, _, _ = setup
    r = p(w, me, text)
    assert r.error is not None and "ambiguous" in r.error and not r.commands


def test_exact_and_unique_spellings_unchanged(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, _, foe = setup
    (c,) = p(w, me, "pulse").commands
    assert isinstance(c, DeflectorPulse)
    (c,) = p(w, me, "pursue talon").commands
    assert isinstance(c, Pursue) and c.target == foe.id


def test_tell_order_prefix_follows_the_ship(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, ally, foe = setup
    r = p(w, me, "tell agena re tal")          # report and release take no ship; recover does
    assert r.error is None, r.error
    (c,) = r.commands
    assert isinstance(c, AllyOrder) and c.ally == ally.id and c.order == "recover" and c.target == foe.id
    r = p(w, me, "tell agena re")
    assert r.error is not None and "ambiguous" in r.error


def test_shortened_order_starts_a_new_piece(setup) -> None:  # type: ignore[no-untyped-def]
    w, me, _, foe = setup
    assert split_orders("cease fire and pu tal") == ["cease fire", "pu tal"]
    r = p(w, me, "cease fire and pu tal")
    assert r.error is None, r.error
    assert [type(c) for c in r.commands] == [CeaseFire, Pursue] and r.commands[1].target == foe.id  # type: ignore[attr-defined]
