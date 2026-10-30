"""What our hits show of an enemy's condition, and the warning before her crew is lost to a power failure."""

from __future__ import annotations

from begin.sim.events import Message, ShipStatusChanged
from begin.sim.ship import ShipStatus
from begin.sim.systems.damage import DamageKind, apply_damage
from begin.sim.world import World


def _pair(content):  # type: ignore[no-untyped-def]
    w = World(content, seed=4)
    fed = w.add_ship("federation.hc", 0, 0, 0)
    kl = w.add_ship("klingon.bc", 1, 0, 6000)
    w.run(1.0)          # both on each other's sensors
    return w, fed, kl


def test_our_hits_wear_her_shield_down_where_we_can_see_it(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, kl = _pair(content)
    seen = []
    for _ in range(12):
        apply_damage(w, kl, 30, kl.x, kl.y - 500, DamageKind.PHASER, fed.id)
        c = w.observe(0).contact(kl.id)
        assert c is not None and c.assessed is not None
        hit = [v for v in c.assessed.shields if v is not None]
        assert len(hit) == 1                 # only the facing we struck
        seen.append(hit[0])
    assert seen == sorted(seen, reverse=True) and seen[-1] < seen[0] - 10   # it visibly drops, hit by hit
    sh = kl.shield_for_bearing(180.0)
    assert sh is not None and abs(seen[-1] - sh.effective) < 1e-6


def test_hull_damage_shows_once_a_hit_gets_through(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, kl = _pair(content)
    for sh in kl.shields:
        sh.up = False
    apply_damage(w, kl, 60, kl.x, kl.y - 500, DamageKind.PHASER, fed.id)
    c = w.observe(0).contact(kl.id)
    assert c is not None and c.assessed is not None and c.assessed.hull is not None
    assert c.assessed.hull < 1.0
    assert 0.0 in c.assessed.shields         # that facing is down: the hit went straight through


def test_a_power_failure_is_announced_before_her_crew_is_lost(content) -> None:  # type: ignore[no-untyped-def]
    w, fed, kl = _pair(content)
    for r in kl.reactors:
        r.damage = 100
    for d in kl.drives:
        d.damage = 100
    for b in kl.batteries:
        b.charge = 0.0
    warned_at = lost_at = None
    for _ in range(int(10 * w.rules.ticks_per_cycle)):
        w.step()
        for ev in w.step_events:
            if isinstance(ev, Message) and ev.visible_to == frozenset({0}) and "lost power" in ev.text:
                warned_at = warned_at if warned_at is not None else w.time
            if isinstance(ev, ShipStatusChanged) and ev.ship_id == kl.id and ev.status == "derelict":
                lost_at = w.time
        if lost_at is not None:
            break
        c = w.observe(0).contact(kl.id)
        if warned_at is not None:
            assert c is not None and c.assessed is not None and c.assessed.power_out
    assert kl.status == ShipStatus.DERELICT
    assert warned_at is not None and lost_at is not None
    assert lost_at - warned_at >= w.rules.life_support_failure_cycles - 0.5


def test_a_shield_without_power_reads_as_down_not_full(content) -> None:  # type: ignore[no-untyped-def]
    from begin.sim.events import ShieldHit

    w, fed, kl = _pair(content)
    for r in kl.reactors:
        r.damage = 100
    for d in kl.drives:
        d.damage = 100
    for b in kl.batteries:
        b.charge = 0.0
    w.step()                                 # no power: her shields stop absorbing, though they look intact
    w.step_events = []
    apply_damage(w, kl, 30, kl.x, kl.y - 500, DamageKind.PHASER, fed.id)
    hits = [ev for ev in w.step_events if isinstance(ev, ShieldHit)]
    assert hits and hits[0].strength == 0.0 and hits[0].penetrated > 0
    c = w.observe(0).contact(kl.id)
    assert c is not None and c.assessed is not None and 0.0 in c.assessed.shields
