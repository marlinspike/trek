"""Weapons coloured by race, and a torpedo shot down that looks different from one that hit."""

from __future__ import annotations

import pytest

from begin.ai.computer import ShipComputer
from begin.content.loader import ContentError, _hex
from begin.sim.commands import ConfigureAutoload, FireTorpedoes, SelectTarget
from begin.sim.events import Detonation, OrdnanceDestroyed, PhaserFired
from begin.sim.world import World
from begin.ui.effects import FIZZLE, UNKNOWN_WEAPON, Effects
from begin.ui.markdown import inline


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    def lum(c: tuple[int, int, int]) -> float:
        def ch(v: float) -> float:
            v /= 255
            return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
        r, g, bl = (ch(x) for x in c)
        return 0.2126 * r + 0.7152 * g + 0.0722 * bl
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_every_race_has_its_own_readable_colours(content) -> None:  # type: ignore[no-untyped-def]
    fs = list(content.factions.values())
    assert len({f.phaser_color for f in fs}) == len(fs) and len({f.torpedo_color for f in fs}) == len(fs)
    for f in fs:
        for c in (f.phaser_color, f.torpedo_color):
            assert _contrast(c, (5, 9, 18)) >= 4.5, f.id     # against the map background
        assert f.phaser_style in ("beam", "pulse")
    assert content.factions["klingon"].phaser_style == "pulse"
    assert _hex("#FF8000", "x") == (255, 128, 0)
    with pytest.raises(ContentError):
        _hex("orange", "x")


def _salvo_at_a_defended_ship(content):  # type: ignore[no-untyped-def]
    w = World(content, seed=4)
    me = w.add_ship("federation.dn", 0, 0, 0)
    foe = w.add_ship("klingon.dr", 1, 0, 6000, course=180)
    w.add_controller(ShipComputer(me.id, 0, w.rng.derive("pd")))
    w.execute(ConfigureAutoload(ship_id=foe.id, weapon="tube", prox=300, reload=True))
    w.execute(SelectTarget(ship_id=foe.id, target=me.id))
    events = []
    for _ in range(6):
        w.run(4)
        w.execute(FireTorpedoes(ship_id=foe.id, target=me.id))
        for _ in range(40):
            w.step()
            events.extend(w.take_events())
    return w, me, foe, events


def test_detonations_say_whose_they_were_and_why(content) -> None:  # type: ignore[no-untyped-def]
    w, me, foe, events = _salvo_at_a_defended_ship(content)
    booms = [e for e in events if isinstance(e, Detonation) and e.source == "torpedo"]
    assert booms and all(e.owner == foe.id for e in booms)
    assert {e.cause for e in booms} <= {"proximity", "fuse", "intercepted"}
    assert any(isinstance(e, OrdnanceDestroyed) for e in events)     # point defense got some
    obs = w.observe(me.side)
    assert all(o.faction == "klingon" for o in obs.threats())


def test_effects_draw_each_race_in_its_colours(content) -> None:  # type: ignore[no-untyped-def]
    kl, fed = content.factions["klingon"], content.factions["federation"]
    who = {1: kl, 2: fed}
    fx = Effects()
    fx.ingest([PhaserFired(0, 1, 0, (0, 0), 0.0, 10.0, 2000.0, [], (0, 2000)),
               PhaserFired(0, 2, 0, (0, 0), 0.0, 10.0, 2000.0, [], (0, 2000)),
               PhaserFired(0, 3, 0, (0, 0), 0.0, 10.0, 2000.0, [], (0, 2000))],
              0, {1, 2, 3}, set(), lambda sid: who.get(sid))
    assert [(b.color, b.style) for b in fx.beams] == [
        (kl.phaser_color, "pulse"), (fed.phaser_color, "beam"), (UNKNOWN_WEAPON, "beam")]
    fx = Effects()
    fx.ingest([Detonation(0, 0, 0, 500.0, "torpedo", 10.0, 1, "proximity")], 0, set(), set(), lambda sid: who.get(sid))
    hit = fx.rings[0]
    assert hit.core and hit.color != FIZZLE and len(fx.sparks) >= 10 and not fx.pops
    fx = Effects()
    fx.ingest([OrdnanceDestroyed(0, 0, 0, "torpedo", 2), Detonation(0, 0, 0, 500.0, "torpedo", 10.0, 1, "intercepted")],
              0, set(), set(), lambda sid: who.get(sid))
    assert fx.pops and not any(r.core for r in fx.rings)
    assert all(s.color == FIZZLE for s in fx.sparks)


def test_manual_colour_spans() -> None:
    (span,) = inline("{#62E85A green bolts}")
    assert span.text == "green bolts" and span.color == (0x62, 0xE8, 0x5A)
