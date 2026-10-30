"""Evasive manoeuvres: a Federation helm order to dodge incoming torpedoes on its own."""

from __future__ import annotations

from begin.console.parser import ParseContext, parse
from begin.core.rng import Rng
from begin.crew.characters import load_officers
from begin.crew.officers import Crew, default_crew
from begin.sim.commands import Authority, ConfigureAutoload, Evasive, FireTorpedoes, Pursue, SetHelm
from begin.sim.world import World


def _salvo(content, evasive: bool):  # type: ignore[no-untyped-def]
    w = World(content, seed=3)
    me = w.add_ship("federation.dn", 0, 0, 0)
    foe = w.add_ship("klingon.dr", 1, 8000, 6000, course=270)
    crew = Crew(me.id, 0, content, default_crew(load_officers()), Rng(1))
    w.add_controller(crew)
    w.execute(SetHelm(ship_id=me.id, course=0, warp=4, issuer=Authority.CAPTAIN))
    w.execute(ConfigureAutoload(ship_id=foe.id, weapon="tube", prox=400, reload=True))
    if evasive:
        assert w.execute(Evasive(ship_id=me.id, issuer=Authority.CAPTAIN)) is None
    w.run(4)
    assert w.execute(FireTorpedoes(ship_id=foe.id, target=me.id, count=4)) is None
    w.run(5)
    return w, me, foe, crew


def _hurt(me) -> float:  # type: ignore[no-untyped-def]
    return me.structure_max - me.structure + sum(100.0 - s.strength for s in me.shields)


def test_the_order_parses_and_is_federation_only(content) -> None:  # type: ignore[no-untyped-def]
    w = World(content, seed=1)
    me = w.add_ship("federation.dn", 0, 0, 0)
    kl = w.add_ship("klingon.dr", 1, 0, 9000)
    for text, on in (("evasive", True), ("evasive manoeuvres", True), ("evade", True), ("evade torpedoes", True),
                     ("evasive off", False)):
        (c,) = parse(text, ParseContext(me.id, w.observe(0))).commands
        assert isinstance(c, Evasive) and c.on is on, text
    assert isinstance(parse("evade " + kl.name.lower(), ParseContext(me.id, w.observe(0))).commands[0], Pursue)
    err = w.execute(Evasive(ship_id=kl.id))
    assert err is not None and "Starfleet" in err


def test_the_helm_dodges_and_then_comes_back_to_the_captains_course(content) -> None:  # type: ignore[no-untyped-def]
    _, held, _, _ = _salvo(content, evasive=False)
    assert _hurt(held) > 10
    w, me, _, crew = _salvo(content, evasive=True)
    assert _hurt(me) < 1 and me.evasive
    acts = [a for a in crew.activity(w.observe(0)) if a.role == "evasive"]
    assert acts and acts[0].plan is not None
    w.run(8)
    assert me.desired_course == 0 and me.desired_warp == 4       # clear of them: back on the captain's heading
    w.execute(SetHelm(ship_id=me.id, course=90, issuer=Authority.CAPTAIN))
    assert not me.evasive                                         # any helm order ends it


def test_after_a_dodge_a_pursuit_carries_on(content) -> None:  # type: ignore[no-untyped-def]
    from begin.sim.ship import HelmMode

    w = World(content, seed=3)
    me = w.add_ship("federation.dn", 0, 0, 0)
    foe = w.add_ship("klingon.dr", 1, 8000, 6000, course=270)
    lead = w.add_ship("federation.dn", 0, 0, 30000)          # following a friend due north, into the salvo
    w.add_controller(Crew(me.id, 0, content, default_crew(load_officers()), Rng(1)))
    assert w.execute(Pursue(ship_id=me.id, target=lead.id, warp=4, issuer=Authority.CAPTAIN)) is None
    w.execute(Evasive(ship_id=me.id, issuer=Authority.CAPTAIN))
    w.execute(ConfigureAutoload(ship_id=foe.id, weapon="tube", prox=400, reload=True))
    w.run(4)
    w.execute(FireTorpedoes(ship_id=foe.id, target=me.id, count=4))
    modes = set()
    for _ in range(20):
        w.run(0.5)
        modes.add(me.helm_mode)
    assert HelmMode.COURSE in modes                  # it broke off to dodge
    assert me.evasive and me.helm_mode == HelmMode.PURSUE and me.helm_target == lead.id
