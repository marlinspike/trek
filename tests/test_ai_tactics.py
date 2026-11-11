"""AI captains fight to their ship's strengths: they weigh their loadout against the target's."""

from __future__ import annotations

from begin.ai.captain import AICaptain
from begin.ai.personality import Personality
from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle
from begin.core.rng import Rng


def _duel(content, mine: str, theirs: str, gap: float = 6000.0):  # type: ignore[no-untyped-def]
    b = build_battle(content, BattleSetup([
        FleetSpec(side=0, player=True, center=(0.0, 0.0), ships=[ShipSpec(mine)]),
        FleetSpec(side=1, center=(0.0, gap), ships=[ShipSpec(theirs)]),
    ], seed=7))
    w = b.world
    me = w.ships[b.player_ship_id]
    enemy = next(s for s in w.ships.values() if s.id != me.id)
    enemy.x, enemy.y = me.x, me.y + gap
    w.run(0.2)                                        # sensors pick each other up
    cap = AICaptain(me.id, 0, Personality.roll(content.factions[me.faction], Rng(1)), Rng(1))
    obs = w.observe(0)
    return cap, obs, w.ships[me.id], obs.contact(enemy.id)


def test_a_torpedo_ship_stands_off_and_a_phaser_ship_closes(content) -> None:  # type: ignore[no-untyped-def]
    cap, obs, me, c = _duel(content, "federation.hc", "klingon.bc")
    close, stand = cap._odds(obs, me, c)
    assert stand > close                              # six Mark 7 tubes beat Klingon banks at range
    cap, obs, me, c = _duel(content, "orion.ra", "klingon.fr")
    close, stand = cap._odds(obs, me, c)
    assert close > stand                              # a raider has no tubes: its banks are all it has


def test_the_standoff_stays_outside_the_targets_banks(content) -> None:  # type: ignore[no-untyped-def]
    """A heavy cruiser that finds a battlecruiser inside its banks' reach opens the range, not the throttle."""
    cap, obs, me, c = _duel(content, "federation.hc", "klingon.bc", gap=2000.0)
    cmd = cap._maneuver(obs, me, c)
    assert cmd is not None
    from begin.core.angles import ang_dist, bearing

    toward = bearing(c.x - me.x, c.y - me.y)
    assert ang_dist(cmd.course, toward) > 90.0       # type: ignore[attr-defined]
    cap.smart = False                                 # Begin's own rule fights it out at this range
    cap.last_helm = None
    old = cap._maneuver(obs, me, c)
    assert old is not None and ang_dist(old.course, toward) < 90.0   # type: ignore[attr-defined]


def test_a_failing_shield_is_turned_away(content) -> None:  # type: ignore[no-untyped-def]
    cap, obs, me, c = _duel(content, "federation.hc", "klingon.bc", gap=2000.0)
    from begin.core.angles import bearing, norm360

    brg = bearing(c.x - me.x, c.y - me.y)
    facing = me.shield_for_bearing(norm360(brg - me.course))
    assert facing is not None
    facing.effective = 5.0
    cmd = cap._maneuver(obs, me, c)
    assert cmd is not None and "turning shield" in cap.trace.recent(1)[0][1]
    after = me.shield_for_bearing(norm360(brg - cmd.course))   # type: ignore[attr-defined]
    assert after is not None and after is not facing and after.effective > 50.0


# ------------------------------------------------------------------ Begin's reflexes, and dodging [R + E]

def test_a_self_destruct_countdown_sends_a_captain_running(content) -> None:  # type: ignore[no-untyped-def]
    """[R] Begin's flee reflex: inside the blast of a ship counting down, run directly away."""
    cap, obs, me, c = _duel(content, "klingon.bc", "federation.hc", gap=1500.0)
    from begin.core.angles import ang_dist, bearing

    w = obs._w
    w.ships[c.id].self_destruct = 4.0
    obs = w.observe(me.side)
    cmd = cap._flee_blast(obs, me)
    assert cmd is not None
    away = bearing(me.x - c.x, me.y - c.y)
    assert ang_dist(cmd.course, away) < 3.0 and cmd.warp >= me.max_attainable_warp - 0.01   # type: ignore[attr-defined]
    w.ships[c.id].self_destruct = -1.0
    cap.last_helm = None
    assert cap._flee_blast(w.observe(me.side), me) is None


def test_snap_phasers_hit_a_ship_charging_us_that_is_not_the_target(content) -> None:  # type: ignore[no-untyped-def]
    cap, obs, me, c = _duel(content, "klingon.bc", "federation.hc", gap=1500.0)
    from begin.core.angles import bearing
    from begin.sim.commands import FirePhasers

    w = obs._w
    rammer = w.ships[c.id]
    rammer.course = rammer.desired_course = bearing(me.x - rammer.x, me.y - rammer.y)
    rammer.warp = rammer.desired_warp = 6.0
    w.run(0.2)
    for bank in me.banks:
        bank.charge = me.cls.banks_charge
    obs = w.observe(me.side)
    shots = cap._snap_phasers(obs, me, None)                             # nobody targeted: it still snaps
    assert len(shots) == 1 and isinstance(shots[0], FirePhasers) and shots[0].target == rammer.id
    assert cap._snap_phasers(obs, me, obs.contact(rammer.id)) == []      # the target gets the normal fire discipline
    rammer.course = rammer.desired_course = rammer.course + 90.0        # turning away: no longer boring in
    w.run(0.1)
    assert cap._snap_phasers(w.observe(me.side), me, None) == []


def test_weave_legs_are_held_for_two_cycles(content) -> None:  # type: ignore[no-untyped-def]
    """[R] Begin's steering cadence: the weave swings to the other side every two cycles, not every helm order."""
    cap, obs, me, c = _duel(content, "klingon.bc", "federation.hc", gap=8000.0)
    first = cap._weave(obs, me, 0.0, 8000.0)
    side = cap.weave_side
    cap._weave(obs, me, 10.0, 8000.0)
    assert cap.weave_side == side                                        # same leg: the base moved, the side didn't
    obs.tick += 2 * obs.rules.ticks_per_cycle
    cap._weave(obs, me, 10.0, 8000.0)
    assert cap.weave_side == -side and first is not None


def test_enemy_captains_dodge_a_torpedo_they_would_fly_into(content) -> None:  # type: ignore[no-untyped-def]
    """[E] Enemy captains use the officers' predictor to get out of a torpedo's path."""
    from begin.ai.captain import AICaptain
    from begin.battle import BattleSetup, FleetSpec, ShipSpec, build_battle

    dodged = 0
    for seed in range(1, 5):
        b = build_battle(content, BattleSetup([FleetSpec(0, [ShipSpec("federation.hc")]),
                                               FleetSpec(1, [ShipSpec("klingon.bc")])], seed=seed))
        b.world.run(60.0)
        dodged += sum(c.dodges for c in b.world.controllers if isinstance(c, AICaptain))
    assert dodged > 0


def test_countdowns_are_seen_only_in_the_last_five_cycles(content) -> None:  # type: ignore[no-untyped-def]
    cap, obs, me, c = _duel(content, "klingon.bc", "federation.hc", gap=3000.0)
    w = obs._w
    w.ships[c.id].self_destruct = 8.0
    assert w.observe(me.side).countdowns() == []
    w.ships[c.id].self_destruct = 3.0
    (sid, _x, _y, left, radius), = w.observe(me.side).countdowns()
    assert sid == c.id and left == 3.0 and radius > 0
