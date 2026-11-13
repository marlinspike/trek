"""The Borg captain [E]: the hive's will aboard one of its ships.

The Collective does not bargain, retreat or strike its colours, and it does not fight the way a captain does.
It chooses whoever has hurt it most (`Mind.threat`), ignores small craft until it has noticed them, closes
steadily, holds its prey in a tractor beam and beams drones across to take the ship rather than destroy it.
A dormant ship (its vinculum relay cut) does nothing at all until it wakes.

Everything else (firing arcs, point defense, helm) is the ordinary captain's, so a cube moves and shoots by the
same rules as any other ship; only what it wants is different.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from ..sim.commands import (
    Command, FireAtPoint, FirePhasers, FireSpecialRound, FireTorpedoes, SelfDestruct, Surrender, Tractor, Transport,
)
from ..sim.observation import ContactView, Observation
from ..sim.ship import Ship
from .captain import AICaptain

THREAT_WEIGHT = 1.0 / 150.0     # each 150 points of damage a ship has done the hive doubles its claim on our attention
CRAFT_IGNORED = 0.0             # an unnoticed small craft is beneath notice
BEAM_MIN_PARTY = 4              # drones in the smallest party worth sending
TRACTOR_REACH = 0.9             # × tractor range: inside it, hold the prey
RIPE_HULL = 0.35                # prey this hurt is to be taken, not destroyed: hold fire and send drones
PROVOKED_CYCLES = 3.0           # ... unless she has hurt us this recently
FIRE = (FirePhasers, FireTorpedoes, FireAtPoint, FireSpecialRound)


@dataclass
class BorgCaptain(AICaptain):
    """A hive ship's captain: relentless, threat-driven, and out to assimilate."""

    last_beam: int = -10 ** 9

    def think(self, obs: Observation) -> Iterable[Command]:
        ship = obs.own(self.ship_id)
        if ship is None or not ship.alive or ship.crew <= 0 or ship.dormant > 0:
            return []
        self.retreating = self.withdrawing = False    # the hive never breaks
        out = [c for c in super().think(obs) if not isinstance(c, (Surrender, SelfDestruct))]
        if self._ripe(obs):
            out = [c for c in out if not isinstance(c, FIRE)]
        out.extend(self._assimilate(obs, ship))
        return out

    def _ripe(self, obs: Observation) -> bool:
        """Is the prey beaten enough to take whole? The hive holds its fire and boards, unless she bites."""
        c = obs.contact(self.target) if self.target is not None else None
        if c is None or c.cls is None or c.cls.is_base:
            return False
        hull = c.assessed.hull if c.assessed is not None and c.assessed.hull is not None else (
            c.scan.structure_frac if c.scan is not None else 1.0)
        if hull >= RIPE_HULL:
            return False
        m = obs.hive()
        bit = m.last_hurt.get(c.side if c.side is not None else -1, -10 ** 9) if m is not None else -10 ** 9
        return obs.tick - bit > PROVOKED_CYCLES * obs.rules.ticks_per_cycle

    # ------------------------------------------------------------ what it wants

    def _score(self, obs: Observation, ship: Ship, c: ContactView, probed: set[int | None],
               focused: set[int | None]) -> float:
        if c.cls is not None and c.cls.craft and c.id not in obs.noticed():
            return CRAFT_IGNORED
        base = super()._score(obs, ship, c, probed, focused)
        m = obs.hive()
        hurt = m.threat.get(c.id, 0.0) if m is not None else 0.0
        return base * (1.0 + hurt * THREAT_WEIGHT)

    def _subsystem_choice(self, obs: Observation, ship: Ship, c: ContactView | None) -> str | None:
        """The hive cuts the weapons that are teaching it, so the ship can be taken whole."""
        return "weapons" if c is not None else None

    def _assimilate(self, obs: Observation, ship: Ship) -> list[Command]:
        out: list[Command] = []
        rules = obs.content.factions[ship.faction].collective
        c = obs.contact(self.target) if self.target is not None else None
        if rules is None or c is None or not c.visible or c.cls is None:
            return out
        d = c.distance_to(ship.x, ship.y)
        if (ship.cls.has_tractor and ship.tractor is not None and ship.tractor.intact
                and ship.tractor_target != c.id and d < obs.rules.tractor_range * TRACTOR_REACH and not c.cls.is_base):
            out.append(self._cmd(Tractor, ship, target=c.id))
        tpc = obs.rules.ticks_per_cycle
        every = rules.beam_every * (0.5 if self._ripe(obs) else 1.0)
        if (d < obs.rules.beam_range and obs.tick - self.last_beam >= every * tpc
                and any(not t.destroyed for t in ship.transporters)):
            party = min(rules.party, ship.crew - 6)
            if party >= BEAM_MIN_PARTY:
                self.last_beam = obs.tick
                out.append(self._cmd(Transport, ship, target=c.id, count=party))
        return out


__all__ = ["BorgCaptain"]
