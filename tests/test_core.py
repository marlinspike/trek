"""Geometry, content integrity and rule-level mechanics."""

from __future__ import annotations

import math

import pytest

from begin.core.angles import bearing, in_arc, norm180, turn_delta
from begin.sim.factory import SHIELD_FACINGS
from begin.sim.systems.damage import DamageKind, apply_damage
from begin.sim.systems.ordnance import intercept_bearing
from begin.sim.systems.phasers import bank_bears, phaser_damage

from .conftest import make_world


def test_bearing_convention() -> None:
    assert bearing(0, 1) == pytest.approx(0.0)
    assert bearing(1, 0) == pytest.approx(90.0)
    assert bearing(0, -1) == pytest.approx(180.0)
    assert bearing(-1, 0) == pytest.approx(270.0)
    assert turn_delta(350, 10) == pytest.approx(20)
    assert norm180(270) == pytest.approx(-90)


def test_arc_membership() -> None:
    assert in_arc(10, 0, 160)
    assert in_arc(350, 0, 160)
    assert not in_arc(90, 0, 160)
    assert in_arc(180, 180, 10)


def test_content_mount_counts(content) -> None:  # type: ignore[no-untyped-def]
    assert len(content.classes) == 20
    for cls in content.classes.values():
        assert len(cls.hull.banks) == cls.banks, cls.id
        assert len(cls.hull.tubes) == cls.tubes, cls.id
        assert len(cls.hull.launchers) == cls.launchers, cls.id


def test_intercept_leads_crossing_target() -> None:
    speed = 3000.0
    b = intercept_bearing(0, 0, 0, 6000, 200, 0, speed)
    assert 0 < b < 10
    # follow the solution: torpedo and target meet
    t = None
    r = math.radians(b)
    for step in range(1, 400):
        tt = step * 0.01
        tx, ty = 200 * tt, 6000
        px, py = math.sin(r) * speed * tt, math.cos(r) * speed * tt
        if math.hypot(tx - px, ty - py) < 30:
            t = tt
            break
    assert t is not None


def test_directional_shields_take_hits_on_facing(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    s = w.add_ship("federation.hc", 0, 0, 0, course=0)
    for idx, facing in enumerate(SHIELD_FACINGS):
        r = math.radians(facing)
        before = [sh.strength for sh in s.shields]
        apply_damage(w, s, 30, math.sin(r) * 1000, math.cos(r) * 1000, DamageKind.BLAST)
        after = [sh.strength for sh in s.shields]
        changed = [i for i in range(6) if after[i] < before[i]]
        assert changed == [idx], (facing, changed)
    assert s.structure == s.structure_max  # all absorbed


def test_shield_collapse_lets_damage_through(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    s = w.add_ship("federation.hc", 0, 0, 0)
    s.shields[0].strength = 0.0
    s.shields[0].effective = 0.0
    apply_damage(w, s, 40, 0, 1000, DamageKind.BLAST)
    assert s.structure < s.structure_max


def test_shield_bore_never_penetrates(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    s = w.add_ship("federation.hc", 0, 0, 0)
    s.shields[0].strength = 0.0
    s.shields[0].effective = 0.0
    assert apply_damage(w, s, 40, 0, 1000, DamageKind.SHIELD_BORE) == 0.0
    assert s.structure == s.structure_max


def test_phaser_damage_falloff(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    near = phaser_damage(w, 10, 10, 0, 2000)
    mid = phaser_damage(w, 10, 10, 1000, 2000)
    assert near == pytest.approx(22.5)
    assert mid == pytest.approx(22.5 * math.sqrt(0.5))
    assert phaser_damage(w, 10, 10, 2000, 2000) == 0.0
    assert phaser_damage(w, 10, 45, 0, 2000) < near


def test_bank_arcs_restrict_fire(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    s = w.add_ship("federation.hc", 0, 0, 0, course=0)
    for bank in s.banks:
        c = bank.mount.arc_center
        assert bank_bears(s, bank, c)
        if bank.mount.arc_width < 360:
            assert not bank_bears(s, bank, c + 180)


def test_heat_destroys_overdriven_drive(content) -> None:  # type: ignore[no-untyped-def]
    from begin.sim.commands import SetHelm

    w = make_world(content)
    s = w.add_ship("federation.hc", 0, 0, 0)
    for d in s.drives:
        d.damage = 60  # damaged drives run hot at any real warp
    w.execute(SetHelm(ship_id=s.id, warp=s.cls.max_warp))
    w.run(120)
    assert any(d.destroyed for d in s.drives)


def test_class_inherits_from_base(tmp_path) -> None:  # type: ignore[no-untyped-def]
    import shutil

    from begin.content.loader import DATA_DIR, load_content

    data = tmp_path / "data"
    shutil.copytree(DATA_DIR, data)
    with open(data / "classes.toml", "a") as f:
        f.write('\n[[class]]\nid = "federation.dnx"\nbase = "federation.dn"\nname = "Refit"\nbanks = 6\nmax_warp = 9.2\n')
    db = load_content(data)
    x, dn = db.classes["federation.dnx"], db.classes["federation.dn"]
    assert x.max_warp == 9.2 and x.name == "Refit"
    assert (x.tubes, x.shield_strength, x.repair, x.ship_names) == (dn.tubes, dn.shield_strength, dn.repair, dn.ship_names)
    assert x.hull.banks == dn.hull.banks


def test_federation_dreadnought_reaches_warp_9_5(content) -> None:  # type: ignore[no-untyped-def]
    from begin.sim.commands import SetHelm
    from tests.conftest import make_world

    w = make_world(content)
    s = w.add_ship("federation.dn", 0, 0, 0)
    w.execute(SetHelm(ship_id=s.id, course=0, warp=9.5))
    top = 0.0
    for _ in range(25):  # flank speed is a sprint: the drives burn out soon after
        w.run(1)
        top = max(top, s.warp)
    assert top > 9.4
