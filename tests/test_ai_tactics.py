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
