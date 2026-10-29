"""Officer delegation: bridge stations the captain hands to named officers.

The player's ship has four stations. Each is either run by the captain
(the default) or delegated to its officer with `delegate <station>`
(a `DelegateStation` command, so delegation is recorded and replays).

`Crew` is an ordinary controller: every officer whose station is delegated
runs an `OfficerBrain` (the AI captain's decision layers, with the officer's
personality) and only that station's commands get through. They are issued
with OFFICER authority, so anything the captain orders holds its channel
against the officer for a while, then the officer carries on.

Officers never retreat, surrender or self-destruct on their own, and they
never change the captain's chosen target: they pick one only when the
captain has none.

`conn <officer>` (or "Seven, take the bridge") gives one officer the whole
bridge [E]: a single brain with that officer's personality runs every
delegated station, and Spock or Seven will also hunt cloaked ships with
their tachyon detector. The captain's orders still win, as above.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

from ..ai.captain import AICaptain
from ..ai.personality import Personality
from ..content.schema import ContentDB
from ..core.rng import Rng
from ..sim.commands import (
    Authority, Command, ConfigureAutoload, ControlProbe, FirePhasers, FireTorpedoes, LaunchProbe, LoadTubes,
    LockWeapons, Pursue, ReinforceShield, Scan, SelectTarget, SetBanks, SetCloak, SetFireMode, SetHelm,
    SetPhaserSpread, SetPointDefense, SetRepairPriority, SetShields, SetTubes, StartProject, TurnMounts,
    FireSpecialRound,
)
from ..sim.observation import Observation
from ..sim.ship import Kind, Ship
from .characters import STATIONS, OfficerProfile

STATION_COMMANDS: dict[str, tuple[type[Command], ...]] = {
    "helm": (SetHelm, Pursue),
    "tactical": (SelectTarget, LockWeapons, TurnMounts, FirePhasers, SetPhaserSpread, SetBanks, FireTorpedoes,
                 ConfigureAutoload, LoadTubes, SetTubes, LaunchProbe, ControlProbe, SetFireMode, SetPointDefense,
                 FireSpecialRound),
    "engineering": (SetShields, ReinforceShield, SetRepairPriority, SetCloak),
    "science": (Scan, StartProject),
}

STATION_NAMES = {"helm": "Helm", "tactical": "Tactical", "engineering": "Engineering", "science": "Science"}


def station_of(cmd: Command) -> str | None:
    """The bridge station a command belongs to; None for the captain's own decisions (destruct, beam, orders)."""
    for station, kinds in STATION_COMMANDS.items():
        if isinstance(cmd, kinds):
            return station
    return None


@dataclass
class OfficerBrain(AICaptain):
    """The AI captain's judgement, working one station on the captain's behalf."""

    station: str = "helm"              # or "bridge": every station, for the officer with the conn
    title: str = ""
    officer_id: str = ""
    last_scan: dict[int, int] = field(default_factory=dict)
    last_repair_check: int = -999

    def _cmd(self, cls: type[Command], ship: Ship, **kw: object) -> Command:
        return cls(ship_id=ship.id, issuer=Authority.OFFICER, source=self.title or self.station, **kw)  # type: ignore[arg-type]

    def _strategy(self, obs: Observation, ship: Ship) -> list[Command]:
        """Pick a target only when the captain has none; never retreat, surrender or self-destruct."""
        out: list[Command] = []
        self.retreating = False
        captains = obs.contact(ship.target) if ship.target is not None else None
        if captains is not None:
            best = captains
        else:
            best, best_score = None, 0.0
            for c in obs.hostile_contacts():
                s = self._score(obs, ship, c)
                if s > best_score:
                    best, best_score = c, s
            if best is not None and self.station in ("tactical", "bridge"):
                out.append(self._cmd(SelectTarget, ship, target=best.id, subsystem=self._subsystem_choice(obs, ship, best)))
        self.target = best.id if best is not None else None
        if (self.station in ("tactical", "bridge") and best is not None and best.cls is not None and ship.tubes
                and self.autoload_set_for != best.id):
            spec = obs.content.torpedoes.get(ship.tubes[0].load_ordnance or ship.cls.torpedo)
            if spec is not None:
                prox = max(obs.rules.prox_floor, min(best.cls.max_warp * 50.0, spec.max_prox))
                out.append(self._cmd(ConfigureAutoload, ship, weapon="tube", prox=prox))
                self.autoload_set_for = best.id
        return out

    def _tactics(self, obs: Observation, ship: Ship) -> list[Command]:
        out = super()._tactics(obs, ship)
        if self.station in ("science", "bridge"):
            out.extend(self._science(obs, ship))
        if self.station in ("engineering", "bridge"):
            out.extend(self._engineering(obs, ship))
        if self.station == "bridge":
            out.extend(self._collaborate(obs, ship))
        return out

    def _collaborate(self, obs: Observation, ship: Ship) -> list[Command]:
        """In command, an officer uses the projects they know: Spock and Seven hunt cloaked ships with a detector."""
        from ..sim.projects import PROJECTS, project_loaded
        from .collaborations import COLLABORATIONS

        cloaked = [c for c in obs.hostile_contacts() if c.cloaked_hint]
        if not cloaked:
            return []
        c = min(cloaked, key=lambda c: c.distance_to(ship.x, ship.y))
        for collab in COLLABORATIONS:
            proj = PROJECTS.get(collab.project)
            spec = obs.content.torpedoes.get(proj.ordnance) if proj is not None and proj.ordnance else None
            if self.officer_id not in collab.officers or spec is None or spec.reveal_radius <= 0:
                continue
            if project_loaded(ship, proj) is not None:
                reach = spec.velocity * obs.rules.units_per_warp * (spec.arm_time + spec.max_time_fuse)
                if c.distance_to(ship.x, ship.y) > reach * 0.9:
                    return []
                # the contact's position is already dead-reckoned along its last heading where the computer can
                return [self._cmd(FireSpecialRound, ship, ordnance=proj.ordnance, x=c.x, y=c.y)]
            if proj.id not in ship.projects:
                return [self._cmd(StartProject, ship, project=proj.id)]
        return []

    def _science(self, obs: Observation, ship: Ship) -> list[Command]:
        """Keep a fresh scan of the target, then work through the other contacts, nearest first."""
        tpc = obs.rules.ticks_per_cycle
        if any(obs.tick - t < 3 * tpc for t in self.last_scan.values()):
            return []  # one scan at a time
        reach = ship.sensor_range() * obs.rules.scan_range_fraction
        candidates = []
        for c in obs.hostile_contacts():
            if not c.visible:
                continue
            d = c.distance_to(ship.x, ship.y)
            if d > reach:
                continue
            age = obs.tick - c.scan.tick if c.scan is not None else 10 ** 9
            stale = 20 * tpc if c.id == self.target else 60 * tpc
            if age > stale:
                candidates.append((c.id != self.target, d, c.id))
        if not candidates:
            return []
        _, _, cid = min(candidates)
        self.last_scan[cid] = obs.tick
        return [self._cmd(Scan, ship, target=cid)]

    def _engineering(self, obs: Observation, ship: Ship) -> list[Command]:
        """Point the repair crews at whatever matters most right now."""
        tpc = obs.rules.ticks_per_cycle
        if obs.tick - self.last_repair_check < 2 * tpc:
            return []
        self.last_repair_check = obs.tick
        want = repair_priority(ship, obs)
        if want != ship.repair_priority:
            return [self._cmd(SetRepairPriority, ship, kind=want)]
        return []


def repair_priority(ship: Ship, obs: Observation) -> Kind | None:
    """Engines if we can't move, then the shield facing the target, weapons, power; else spread the work."""
    def hurt(subs: Iterable[object]) -> bool:
        return any(getattr(s, "damage", 0) > 0 and not getattr(s, "destroyed", False) for s in subs)

    if not ship.cls.is_base and not ship.can_move() and hurt(ship.drives):
        return Kind.DRIVE
    c = obs.contact(ship.target) if ship.target is not None else None
    if c is not None and ship.shields:
        from ..core.angles import bearing, norm360

        rel = norm360(bearing(c.x - ship.x, c.y - ship.y) - ship.course)
        sh = ship.shield_for_bearing(rel)
        if sh is not None and sh.damage > 20 and not sh.destroyed:
            return Kind.SHIELD
    if hurt(ship.banks) or hurt(ship.tubes):
        banks = sum(b.damage for b in ship.banks if not b.destroyed)
        tubes = sum(t.damage for t in ship.tubes if not t.destroyed)
        return Kind.PHASER if banks >= tubes else Kind.TUBE
    if hurt(ship.reactors) or hurt(ship.batteries):
        return Kind.REACTOR
    return None


@dataclass
class Crew:
    """The player's bridge officers, run as one controller."""

    ship_id: int
    side: int
    content: ContentDB
    officers: dict[str, OfficerProfile]     # station -> officer
    rng: Rng
    period: int = 1
    phase: int = 0
    brains: dict[str, OfficerBrain] = field(default_factory=dict)

    def officer(self, station: str) -> OfficerProfile | None:
        return self.officers.get(station)

    def find(self, name: str) -> OfficerProfile | None:
        """An officer by id, name, alias or station, or a unique prefix of one."""
        q = name.lower().strip(" ,:")
        if not q:
            return None
        everyone = list(dict.fromkeys(self.officers.values()))
        for o in everyone:
            if q in (o.id, o.name.lower(), o.station, *o.aliases):
                return o
        hits = [o for o in everyone if any(a.startswith(q) for a in (o.id, o.name.lower(), *o.aliases))]
        return hits[0] if len(hits) == 1 else None

    def move_to(self, ship_id: int) -> None:
        """The captain changed ships (`beam <ally>`): the officers come along and start fresh."""
        self.ship_id = ship_id
        self.brains.clear()

    def _brain(self, station: str, ship: Ship, prof: OfficerProfile | None = None) -> OfficerBrain:
        prof = prof or self.officers[station]
        key = f"bridge:{prof.id}" if station == "bridge" else station
        b = self.brains.get(key)
        if b is None:
            faction = self.content.factions[ship.faction]
            prng = self.rng.derive(f"{key}:{ship.id}")
            pers = Personality.roll(faction, prng, prof.personality)
            b = OfficerBrain(ship.id, ship.side, pers, prng, station=station, title=prof.title, officer_id=prof.id)
            self.brains[key] = b
        return b

    def think(self, obs: Observation) -> list[Command]:
        ship = obs.own(self.ship_id)
        if ship is None or not ship.alive or ship.crew <= 0 or not ship.delegated:
            return []
        out: list[Command] = []
        commander = self.find(ship.conn) if ship.conn else None
        if commander is not None:
            # one mind runs the ship; stations the captain took back stay the captain's
            for cmd in self._brain("bridge", ship, commander).think(obs):
                if station_of(cmd) in ship.delegated:
                    out.append(cmd)
            return out
        for station in STATIONS:
            if station not in ship.delegated or station not in self.officers:
                continue
            for cmd in self._brain(station, ship).think(obs):
                if station_of(cmd) == station:
                    out.append(cmd)
        return out


def default_crew(officers: dict[str, OfficerProfile]) -> dict[str, OfficerProfile]:
    """Station -> officer: the first officer listed for each station."""
    out: dict[str, OfficerProfile] = {}
    for o in officers.values():
        out.setdefault(o.station, o)
    return out


__all__ = [
    "Crew", "OfficerBrain", "STATION_COMMANDS", "STATION_NAMES", "default_crew", "repair_priority", "station_of",
]
