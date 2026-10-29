"""World loop, commands, authority, autoload, fog of war and determinism."""

from __future__ import annotations

import math

from begin.sim.commands import (
    Authority, ConfigureAutoload, FirePhasers, FireTorpedoes, Pursue, SelectTarget, SetHelm,
)
from begin.sim.events import CommandRejected, Detonation, SubsystemDamaged
from begin.sim.ship import ShipStatus

from .conftest import charge_all, make_world


def _duel(content, seed: int, cycles: float = 90.0):  # type: ignore[no-untyped-def]
    """A scripted duel driven purely by commands."""
    w = make_world(content, seed=seed)
    a = w.add_ship("federation.hc", 0, 0, 0)
    b = w.add_ship("klingon.bc", 1, 0, 7000, course=180)
    for i in range(int(cycles * 10)):
        if i % 10 == 0:
            for s, t in ((a, b), (b, a)):
                if s.alive and t.exists:
                    w.submit(SelectTarget(ship_id=s.id, target=t.id, issuer=Authority.AI_CAPTAIN))
                    w.submit(Pursue(ship_id=s.id, target=t.id, warp=4, issuer=Authority.AI_CAPTAIN))
                    w.submit(FirePhasers(ship_id=s.id, issuer=Authority.AI_CAPTAIN, spread=10))
                    w.submit(FireTorpedoes(ship_id=s.id, issuer=Authority.AI_CAPTAIN))
        w.step()
        if w.outcome.over:
            break
    return w, a, b


def _fingerprint(w) -> tuple:  # type: ignore[no-untyped-def]
    return tuple(
        (s.id, round(s.x, 6), round(s.y, 6), s.crew, round(s.structure, 6), s.status.value,
         tuple(sub.damage for sub in s.subsystems()), tuple(round(sh.strength, 6) for sh in s.shields))
        for s in w.ships.values()
    ) + (w.tick, len(w.torpedoes), len(w.probes))


def test_determinism_same_seed(content) -> None:  # type: ignore[no-untyped-def]
    w1, *_ = _duel(content, 42)
    w2, *_ = _duel(content, 42)
    assert _fingerprint(w1) == _fingerprint(w2)


def test_different_seeds_diverge(content) -> None:  # type: ignore[no-untyped-def]
    w1, *_ = _duel(content, 1)
    w2, *_ = _duel(content, 2)
    assert _fingerprint(w1) != _fingerprint(w2)


def test_duel_produces_real_combat(content) -> None:  # type: ignore[no-untyped-def]
    w, a, b = _duel(content, 5, cycles=240)
    assert a.stats.phaser_hits > 0 and b.stats.phaser_hits > 0
    assert a.stats.torpedo_hits + b.stats.torpedo_hits > 0
    assert a.structure < a.structure_max or b.structure < b.structure_max


def test_simulation_rate_independent_of_rendering(content) -> None:  # type: ignore[no-untyped-def]
    """Running N steps in one batch or across many frames is identical."""
    w1, *_ = _duel(content, 9, cycles=30)
    w2 = make_world(content, seed=9)
    a = w2.add_ship("federation.hc", 0, 0, 0)
    b = w2.add_ship("klingon.bc", 1, 0, 7000, course=180)
    # re-drive using the logged commands at their ticks
    by_tick: dict[int, list] = {}
    for lc in w1.command_log:
        by_tick.setdefault(lc.tick, []).append(lc.command)
    assert a.id == 1 and b.id == 2
    while w2.tick < w1.tick:
        for cmd in by_tick.get(w2.tick, []):
            w2.submit(cmd)
        w2.step()
    assert _fingerprint(w1) == _fingerprint(w2)


def test_helm_reaches_ordered_course_and_warp(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    s = w.add_ship("federation.hc", 0, 0, 0)
    w.execute(SetHelm(ship_id=s.id, course=90, warp=4))
    w.run(20)
    assert abs(s.course - 90) < 1e-6
    assert abs(s.warp - 4) < 1e-6
    assert s.x > 1000 and abs(s.y) < 3000


def test_captain_order_overrides_automation(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    s = w.add_ship("federation.hc", 0, 0, 0)
    assert w.execute(SetHelm(ship_id=s.id, course=45, warp=2)) is None
    reason = w.execute(SetHelm(ship_id=s.id, course=200, issuer=Authority.COMPUTER, source="computer"))
    assert reason is not None and "Captain" in reason
    assert s.desired_course == 45
    # officers regain control once the captain delegates
    w.release_holds(s.id, "helm")
    assert w.execute(SetHelm(ship_id=s.id, course=200, issuer=Authority.OFFICER, source="helm officer")) is None
    assert s.desired_course == 200


def test_captain_hold_expires(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    s = w.add_ship("federation.hc", 0, 0, 0)
    w.execute(SetHelm(ship_id=s.id, course=45))
    w.run(w.rules.captain_hold_cycles + 1)
    assert w.execute(SetHelm(ship_id=s.id, course=90, issuer=Authority.COMPUTER)) is None


def test_autoload_loads_but_never_fires(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    a = w.add_ship("federation.hc", 0, 0, 0)
    b = w.add_ship("klingon.bc", 1, 0, 4000, course=180)
    w.execute(SelectTarget(ship_id=a.id, target=b.id))
    charge_all(w, 10)
    assert all(t.loaded is not None for t in a.tubes)
    assert not w.torpedoes  # autoload never launches on its own
    assert a.torps_remaining == a.cls.torps_carried - len(a.tubes)


def test_autoload_configuration_applies_to_next_load(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    a = w.add_ship("federation.hc", 0, 0, 0)
    charge_all(w, 10)
    assert w.execute(ConfigureAutoload(ship_id=a.id, weapon="tube", ordnance="mk8", prox=300)) is None
    assert all(t.loaded is not None and t.loaded.ordnance == "mk7" for t in a.tubes)
    w.execute(FireTorpedoes(ship_id=a.id))
    charge_all(w, 10)
    assert all(t.loaded is not None and t.loaded.ordnance == "mk8" and t.loaded.prox == 300 for t in a.tubes
               if t.mount.arc_center == 0)


def test_autoload_rejects_incompatible_ordnance(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    a = w.add_ship("federation.hc", 0, 0, 0)
    reason = w.execute(ConfigureAutoload(ship_id=a.id, weapon="tube", ordnance="plasma"))
    assert reason is not None and "cannot load" in reason


def test_autoload_off_leaves_tubes_empty(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    a = w.add_ship("federation.hc", 0, 0, 0)
    w.execute(ConfigureAutoload(ship_id=a.id, weapon="tube", enabled=False))
    charge_all(w, 10)
    assert all(t.loaded is None for t in a.tubes)


def test_rejection_reasons_are_specific(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    a = w.add_ship("federation.hc", 0, 0, 0)
    b = w.add_ship("klingon.bc", 1, 0, 9000)
    w.execute(SelectTarget(ship_id=a.id, target=b.id))
    assert w.execute(FirePhasers(ship_id=a.id)) == "No phaser banks are charged."
    charge_all(w, 5)
    r = w.execute(FirePhasers(ship_id=a.id))
    assert r is not None and "out of phaser range" in r
    rej = [e for e in w.take_events() if isinstance(e, CommandRejected)]
    assert rej


def test_subsystem_targeting_disables_without_destroying(content) -> None:  # type: ignore[no-untyped-def]
    """Precision fire at a subsystem group hits it far more often than random fire would."""
    def run(selector):  # type: ignore[no-untyped-def]
        hits = 0
        for seed in range(12):
            w = make_world(content, seed=seed)
            a = w.add_ship("federation.hc", 0, 0, 0)
            b = w.add_ship("klingon.bc", 1, 0, 900, course=0)
            for sh in b.shields:
                sh.strength = 0.0
                sh.up = False
            w.execute(SelectTarget(ship_id=a.id, target=b.id, subsystem=selector))
            for _ in range(3):
                for bank in a.banks:
                    bank.charge = a.cls.banks_charge
                w.execute(FirePhasers(ship_id=a.id, spread=10))
                w.step()
            hits += sum(1 for e in w.take_events()
                        if isinstance(e, SubsystemDamaged) and e.ship_id == b.id and e.sid in ("sensors", "computer"))
        return hits
    assert run("sensors") > run(None) * 2


def test_fog_of_war_hides_distant_ships(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    a = w.add_ship("federation.hc", 0, 0, 0)
    far = w.add_ship("klingon.bc", 1, 0, a.cls.scanner_range * 3)
    w.step()
    obs = w.observe(0)
    assert far.id not in obs.contacts()
    assert obs.own(a.id) is a
    assert obs.own(far.id) is None
    # bring it close and it appears, with position but no hidden internals
    far.y = 5000
    w.step()
    c = w.observe(0).contact(far.id)
    assert c is not None and c.visible
    assert not hasattr(c, "crew") and c.scan is None


def test_cloak_hides_from_observation(content) -> None:  # type: ignore[no-untyped-def]
    from begin.sim.commands import SetCloak

    w = make_world(content)
    a = w.add_ship("federation.hc", 0, 0, 0)
    r = w.add_ship("romulan.bp", 1, 0, 6000)
    w.step()
    assert w.observe(0).contact(r.id).visible  # type: ignore[union-attr]
    assert w.execute(SetCloak(ship_id=r.id, on=True)) is None
    w.run(3)
    c = w.observe(0).contact(r.id)
    assert c is None or not c.visible


def test_battle_ends_with_winner(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    a = w.add_ship("federation.hc", 0, 0, 0)
    b = w.add_ship("orion.ra", 1, 0, 3000)
    w.destroy_ship(b, "test", a.id)
    w.step()
    assert w.outcome.over and w.outcome.winner == 0
    assert a.stats.kills == 1
    assert b.status == ShipStatus.DESTROYED


def test_destruction_breakup_blast_hits_neighbours(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    a = w.add_ship("federation.hc", 0, 0, 0)
    b = w.add_ship("klingon.bc", 1, 0, 300)
    w.take_events()
    w.destroy_ship(b, "test", a.id)
    evs = w.take_events()
    assert any(isinstance(e, Detonation) and e.source == "ship" for e in evs)
    assert a.stats.damage_taken > 0


def test_self_destruct_countdown(content) -> None:  # type: ignore[no-untyped-def]
    from begin.sim.commands import SelfDestruct

    w = make_world(content)
    a = w.add_ship("federation.hc", 0, 0, 0)
    w.add_ship("klingon.bc", 1, 0, 20000)
    assert w.execute(SelfDestruct(ship_id=a.id, cycles=8)) is None
    w.run(2)
    assert w.execute(SelfDestruct(ship_id=a.id)) is None  # 6 left: abort allowed
    assert a.self_destruct < 0
    w.execute(SelfDestruct(ship_id=a.id, cycles=5))
    assert w.execute(SelfDestruct(ship_id=a.id)) is not None  # too late
    w.run(6)
    assert a.status == ShipStatus.DESTROYED


def test_escape_far_from_enemies(content) -> None:  # type: ignore[no-untyped-def]
    w = make_world(content)
    a = w.add_ship("federation.hc", 0, 0, 0)
    w.add_ship("klingon.bc", 1, 0, -10000)
    a.y = w.rules.escape_distance + 20000
    w.run(w.rules.escape_cycles + 1)
    assert a.status == ShipStatus.ESCAPED
    assert w.outcome.over and w.outcome.winner == 1


def test_torpedo_proximity_hits_moving_target(content) -> None:  # type: ignore[no-untyped-def]
    hits = 0
    for seed in range(6):
        w = make_world(content, seed=seed)
        a = w.add_ship("federation.hc", 0, 0, 0)
        b = w.add_ship("klingon.bc", 1, 0, 6000, course=90)
        w.execute(SetHelm(ship_id=b.id, warp=3))
        charge_all(w, 6)
        w.execute(SelectTarget(ship_id=a.id, target=b.id))
        assert w.execute(FireTorpedoes(ship_id=a.id)) is None
        w.run(5)
        hits += a.stats.torpedo_hits
    assert hits >= 6  # straight-line targets get hit (manual: "DON'T MOVE IN A STRAIGHT LINE")


def test_phasers_destroy_torpedoes_in_cone(content) -> None:  # type: ignore[no-untyped-def]
    from begin.sim.rules import Rules

    w = make_world(content, rules=Rules(beam_kill_base=1.0))  # a sure kill, to test the geometry
    a = w.add_ship("federation.hc", 0, 0, 0)
    b = w.add_ship("klingon.bc", 1, 0, 9000, course=180)
    charge_all(w, 8)
    w.execute(SelectTarget(ship_id=b.id, target=a.id))
    assert w.execute(FireTorpedoes(ship_id=b.id)) is None
    assert w.torpedoes
    t = w.torpedoes[0]
    while math.hypot(t.x - a.x, t.y - a.y) > 1500:
        w.step()
    brg = math.degrees(math.atan2(t.x - a.x, t.y - a.y)) % 360
    assert w.execute(FirePhasers(ship_id=a.id, at_bearing=brg, spread=20, defensive=True, max_banks=1)) is None
    assert a.stats.ordnance_intercepted >= 1


def test_torpedo_fire_explains_tubes_that_cannot_bear(content) -> None:  # type: ignore[no-untyped-def]
    """With tube arcs on, the Dreadnought's tubes 1-6 face forward and 7-8 aft: a target astern gets only 7 and 8."""
    from begin.sim.commands import FireTorpedoes, SelectTarget
    from begin.sim.events import Message
    from begin.sim.rules import Rules

    from .conftest import charge_all, make_world

    w = make_world(content, rules=Rules(tube_arcs=True))
    dn = w.add_ship("federation.dn", 0, 0, 0, course=0)
    enemy = w.add_ship("klingon.bc", 1, 0, -2500)
    charge_all(w, 12)
    assert all(t.loaded is not None for t in dn.tubes)
    assert w.execute(SelectTarget(ship_id=dn.id, target=enemy.id)) is None
    reason = w.execute(FireTorpedoes(ship_id=dn.id, tubes=(0, 1)))
    assert reason is not None and reason.startswith("Tubes 1 and 2 can't bear")
    assert "astern" in reason and "75° either side of the bow" in reason
    w.take_events()
    assert w.execute(FireTorpedoes(ship_id=dn.id, target=enemy.id)) is None
    fired = [t for t in dn.tubes if t.loaded is None]
    assert [dn.tubes.index(t) for t in fired] == [6, 7]
    msgs = [e.text for e in w.take_events() if isinstance(e, Message)]
    assert any(m.startswith("Firing tubes 7 and 8. Tubes 1-6 can't bear") for m in msgs)


def test_tubes_fire_in_any_direction_by_default(content) -> None:  # type: ignore[no-untyped-def]
    """As in Begin: every loaded tube fires at a target astern."""
    from begin.sim.commands import FireTorpedoes

    from .conftest import charge_all, make_world

    w = make_world(content)
    dn = w.add_ship("federation.dn", 0, 0, 0, course=0)
    enemy = w.add_ship("klingon.bc", 1, 0, -2500)
    charge_all(w, 12)
    assert w.execute(FireTorpedoes(ship_id=dn.id, target=enemy.id)) is None
    assert all(t.loaded is None for t in dn.tubes)


def test_detected_ships_are_identified_at_once(content) -> None:  # type: ignore[no-untyped-def]
    """As in Begin, a ship on sensors shows its class and name, even at the edge of sensor range."""
    from .conftest import make_world

    w = make_world(content)
    me = w.add_ship("federation.dn", 0, 0, 0)
    far = w.add_ship("klingon.bc", 1, 0, me.sensor_range() * w.content.classes["klingon.bc"].scanner_reflect * 0.95)
    w.run(1)
    c = w.observe(0).contact(far.id)
    assert c is not None and c.visible and c.identified and c.cls is not None
