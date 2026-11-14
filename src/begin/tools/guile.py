"""A scripted captain who fights a Borg cube the way the Captain's Manual teaches (assets/help/borg.md): guile
first, then power. `begin --tour-test` flies each Borg tour a second time with it (the "+guile" row), because the
officers alone fight with power, which a cube is built to beat.

The captain gives the orders a player would type, through a battle session, and reads only what the player's
side can see:

1. Bring Seven's advancements online (when the tour has given her any), tune the shields against boarders, put Seven on the harmonics survey, and hold the range at torpedo reach,
   outside her beams and her tractor, at a cube's own best warp.
2. When the survey finds her vinculum relay and no hostile round is near the ship, send the away team to put it
   out. Once the team is aboard, keep torpedoes landing on her so the hive watches the ship, not the shuttle
   (a volley fired while the shuttle is crossing can hit it).
3. While she sleeps, stand clear of the blast and put torpedoes into her warp drives: her core goes.

Everything else (ships that are not hives, and the hive ships the officers can fight by power: probes and
spheres, which are as fast as the Enterprise) is left to the officer with the conn.
"""

from __future__ import annotations

import math
from dataclasses import dataclass

from ..battle import Battle
from ..session.battle import BattleSession
from ..sim.ship import Ship

HOLD_AT = 5600.0         # torpedo reach: outside a cube's beams (3,200) and her tractor, and her core's blast
VOLLEY_EVERY = 4.0       # cycles between torpedo volleys
CROSS_EVERY = 10.0       # cycles between away-team attempts
SAFE_LAUNCH = 4000.0     # no shuttle goes out with a hostile round this close: one casualty and she is adrift
HOLD_WARP = 7            # a cube's best: she never closes, and the drives last the fight a cube takes
STEP = 0.5               # cycles a turn of the script
OUTWEIGHS = 2.0          # a hive ship this many times our flagship's mass is the guile's quarry


@dataclass
class GuileCaptain:
    """Plays one battle against the Borg through a session, as a player at the console would."""

    session: BattleSession
    officer: str = "spock"
    target: int | None = None
    aim: str = ""
    volley: float = -1e9
    crossed: float = -1e9
    conn: bool = False

    @staticmethod
    def wanted(battle: Battle) -> bool:
        """Is there a hive ship worth the guile here?"""
        return _quarry(battle) is not None

    def begin(self) -> None:
        """Seven's advancements first, as the officers advise, then the survey and the shields."""
        from ..crew.officers import unfitted

        me = self.session.battle.world.ships.get(self.session.battle.player_ship_id or -1)
        if me is not None:
            self.order(*(f"design {a}" for a in unfitted(self.session.obs, me)))
        self.order("tune shields", "duty harmonics")

    def order(self, *lines: str) -> None:
        for line in lines:
            self.session.run_console(line)

    def turn(self) -> None:
        """One look at the board, and the orders it calls for."""
        battle = self.session.battle
        quarry = _quarry(battle)
        if quarry is None:
            if not self.conn:                       # the big one is gone: the officer finishes the rest
                self.order(f"{self.officer}, take the conn")
                self.conn = True
            return
        obs = self.session.obs
        me = battle.world.ships.get(battle.player_ship_id) if battle.player_ship_id is not None else None
        if me is None or not me.alive:
            return
        if quarry.id != self.target:
            self.target, self.aim = quarry.id, ""
            self.order(f"elude #{quarry.id} warp {HOLD_WARP} at {HOLD_AT:.0f}")
        now = battle.world.time
        asleep = obs.dormant(quarry.id) > 0
        found = obs.weak_point(quarry.id) is not None
        away = obs.away_ops()
        self._aim(quarry, "propulsion" if asleep else "relay" if found else "")
        reach = math.hypot(me.x - quarry.x, me.y - quarry.y)
        clear = reach > HOLD_AT - 500                   # outside the blast when her core goes
        incoming = any(math.hypot(o.x - me.x, o.y - me.y) < SAFE_LAUNCH for o in obs.threats())
        if (found and not asleep and not away and not incoming and reach < HOLD_AT + 1500
                and now - self.crossed >= CROSS_EVERY):
            self.order(f"away #{quarry.id} relay")
            self.crossed = now
        aboard = any(op.phase == "aboard" for op in away)  # never a volley down the shuttle's own path
        if ((asleep and clear) or (aboard and not asleep)) and now - self.volley >= VOLLEY_EVERY:
            self.order("fire all torpedoes")
            self.volley = now

    def _aim(self, quarry: Ship, system: str) -> None:
        if system and system != self.aim:
            self.order(f"target #{quarry.id} {system}")
            self.aim = system


def _quarry(battle: Battle) -> Ship | None:
    """The heaviest hive ship still fighting that far outweighs our flagship: a cube, the ship power alone loses
    to. Probes and spheres are as fast as we are, so holding the range is no defence against them: they are left
    to the officer with the conn."""
    from ..sim import collective

    w = battle.world
    me = w.ships.get(battle.player_ship_id) if battle.player_ship_id is not None else None
    least = OUTWEIGHS * me.cls.mass if me is not None else 0.0
    hives = [s for s in w.ships.values()
             if s.alive and s.side != w.player_side and collective.is_hive(w, s) and s.cls.mass >= least]
    return max(hives, key=lambda s: s.cls.mass, default=None)


def fight(battle: Battle, officer: str, limit_cycles: float) -> None:
    """Fight the battle to its end (or the time limit) with the guile captain in command."""
    session = BattleSession(battle, hidden={}, llm={}, career={}, chatter=False)
    session.paused = False
    captain = GuileCaptain(session, officer)
    captain.begin()
    w = battle.world
    try:
        while w.time < limit_cycles and not w.outcome.over:
            session.update(STEP, 1.0)
            captain.turn()
    finally:
        session.close()


__all__ = ["GuileCaptain", "fight"]
