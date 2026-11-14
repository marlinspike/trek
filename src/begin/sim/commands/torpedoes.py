"""Torpedoes: tubes, spreads, mines, projects and the engine boost."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import TYPE_CHECKING, ClassVar

from ..ship import Ship, Tube
from .base import Authority, Command, Rejected, _arc_advice, _indices, _require_target, _tube_list

if TYPE_CHECKING:
    from ..world import World


@dataclass(kw_only=True)
class FireTorpedoes(Command):
    tubes: tuple[int, ...] | None = None
    target: int | None = None
    subsystem: str | None = None
    count: int | None = None
    fan: float = 0.0
    name: ClassVar[str] = "fire torpedoes"

    def channels(self) -> tuple[str, ...]:
        return ("torpedoes",)

    def _plan(self, world: World, ship: Ship) -> list[tuple[int, int | None]]:
        """(tube index, target id) for each tube that will fire (command target, else the tube's lock)."""
        return self._survey(world, ship)[0]

    def _survey(self, world: World, ship: Ship) -> tuple[list[tuple[int, int | None]], list[int], list[int]]:
        """The tubes that will fire, the loaded tubes that can't bear, and the selected tubes not loaded."""
        from ..systems.ordnance import tube_solution

        if not ship.tubes:
            raise Rejected(f"The {ship.cls.name} has no torpedo tubes.")
        idx = _indices(ship.tubes, self.tubes)
        loaded = [i for i in idx if ship.tubes[i].loaded is not None and ship.tubes[i].intact]
        unloaded = [i for i in idx if i not in loaded]
        if not loaded:
            if any(not ship.tubes[i].intact for i in idx) and all(not ship.tubes[i].intact for i in idx):
                raise Rejected("All selected tubes are damaged.")
            if ship.torps_remaining <= 0 and not any(ship.tubes[i].loaded for i in idx):
                raise Rejected("Torpedo magazine is empty.")
            raise Rejected(f"{_tube_list(idx).capitalize()} {'is' if len(idx) == 1 else 'are'} not loaded."
                           if self.tubes is not None else "No torpedoes are loaded.")
        ok: list[tuple[int, int | None]] = []
        blind: list[int] = []
        aim_at: int | None = None
        for i in loaded:
            tgt = self.target if self.target is not None else ship.tubes[i].lock
            if tgt is not None and world.apparent_position(ship.side, tgt) is None:
                tgt = None
            if tube_solution(world, ship, ship.tubes[i], tgt) is not None:
                ok.append((i, tgt))
            else:
                blind.append(i)
                aim_at = tgt if aim_at is None else aim_at
        if not ok:
            raise Rejected(f"{_tube_list(blind).capitalize()} can't bear: {_arc_advice(world, ship, blind, aim_at)}")
        if self.count is not None:
            ok = ok[: max(0, self.count)]
        return ok, blind, unloaded

    def validate(self, world: World, ship: Ship) -> None:
        if self.target is not None:
            _require_target(world, ship, self.target)
        self._plan(world, ship)

    def apply(self, world: World, ship: Ship) -> None:
        from ..systems.ordnance import launch_torpedoes

        plan, blind, unloaded = self._survey(world, ship)
        if self.issuer >= Authority.CAPTAIN and (blind or (unloaded and self.tubes is not None)):
            from ..events import Message, Tone

            bits = [f"Firing {_tube_list([i for i, _ in plan])}."]
            if blind:
                aim_at = next((t for t in (self.target, *(ship.tubes[i].lock for i in blind)) if t is not None), None)
                bits.append(f"{_tube_list(blind).capitalize()} can't bear: {_arc_advice(world, ship, blind, aim_at)}")
            if unloaded and self.tubes is not None:
                bits.append(f"{_tube_list(unloaded).capitalize()} {'is' if len(unloaded) == 1 else 'are'} not loaded.")
            world.emit(Message(world.tick, " ".join(bits), Tone.CAUTION, speaker=self.source, ship_id=ship.id,
                               visible_to=frozenset({ship.side})))
        groups: dict[int | None, list[int]] = {}
        for i, tgt in plan:
            groups.setdefault(tgt, []).append(i)
        for tgt, idx in groups.items():
            sub = self.subsystem
            if sub is None and tgt is not None and tgt == ship.target:
                sub = ship.target_subsystem
            launch_torpedoes(world, ship, [ship.tubes[i] for i in idx], tgt, sub, self.fan)


@dataclass(kw_only=True)
class StartProject(Command):
    """Set the officers to design something over a few cycles (sim/projects.py) [E]."""

    project: str
    name: ClassVar[str] = "design"

    def channels(self) -> tuple[str, ...]:
        return ("project",)

    def validate(self, world: World, ship: Ship) -> None:
        from ..projects import PROJECTS, project_loaded

        proj = PROJECTS.get(self.project)
        if proj is None:
            raise Rejected(f"Nothing called '{self.project}' to design. Known: {', '.join(PROJECTS)}.")
        if self.project in ship.projects:
            raise Rejected(f"The {proj.title} is already being designed ({ship.projects[self.project]:.0f} cycles left).")
        if proj.needs_tubes and not any(t.intact for t in ship.tubes):
            raise Rejected(f"The {proj.title} needs a working torpedo tube.")
        if proj.is_ready is not None and proj.is_ready(ship):
            raise Rejected(f"The {proj.title} is already set up. {proj.hint}".strip())
        if proj.can_start is not None:
            why = proj.can_start(world, ship)
            if why is not None:
                raise Rejected(why)
        loaded_in = project_loaded(ship, proj) if proj.ordnance else None
        if loaded_in is not None:
            raise Rejected(f"The {proj.title} {'are' if proj.rounds > 1 else 'is'} already loaded: tube {loaded_in + 1}.")

    def apply(self, world: World, ship: Ship) -> None:
        from ..projects import PROJECTS

        ship.projects[self.project] = PROJECTS[self.project].cycles

    def describe(self) -> str:
        return f"design {self.project}"


@dataclass(kw_only=True)
class EngineBoost(Command):
    """The chief engineer puts a team on the drives ("give me all she's got") [E].

    For `boost_cycles` the drives heat up 1/`boost_endurance` as fast, so they run hot that much longer before
    they overheat. The price is the team itself: every other repair (systems and hull) runs at
    `boost_repair_share` × its speed until it is done. `on=False` sends the team back to the repairs early.
    """

    on: bool = True
    name: ClassVar[str] = "boost"

    def channels(self) -> tuple[str, ...]:
        return ("engineering.boost",)

    def validate(self, world: World, ship: Ship) -> None:
        from ..systems.power import boost_possible

        if not self.on:
            if ship.engine_boost <= 0.0:
                raise Rejected("The engine team is already on repairs.")
            return
        if ship.engine_boost > 0.0:
            raise Rejected(f"The team's already on the engines, Captain: {ship.engine_boost:.0f} cycles left.")
        why = boost_possible(ship)
        if why is not None:
            raise Rejected(why)

    def apply(self, world: World, ship: Ship) -> None:
        ship.engine_boost = world.rules.boost_cycles if self.on else 0.0

    def describe(self) -> str:
        return "engine boost" if self.on else "engine boost off"


@dataclass(kw_only=True)
class FireSpecialRound(Command):
    """Fire a designed round (e.g. the tachyon detector) at a point, fused to burst there [E]."""

    ordnance: str
    x: float
    y: float
    name: ClassVar[str] = "fire special round"

    def channels(self) -> tuple[str, ...]:
        return ("torpedoes",)

    def _tube(self, ship: Ship) -> Tube:
        tube = next((t for t in ship.tubes if t.loaded is not None and t.loaded.ordnance == self.ordnance), None)
        if tube is None:
            raise Rejected(f"No {self.ordnance} round is loaded. Ask Spock and Seven to design one ('design {self.ordnance}').")
        return tube

    def validate(self, world: World, ship: Ship) -> None:
        self._tube(ship)
        spec = world.content.torpedoes[self.ordnance]
        reach = spec.velocity * world.rules.units_per_warp * (spec.arm_time + spec.max_time_fuse)
        d = math.hypot(self.x - ship.x, self.y - ship.y)
        if d > reach:
            raise Rejected(f"That point is {d:,.0f} away; the round reaches {reach:,.0f}.")

    def apply(self, world: World, ship: Ship) -> None:
        from ..systems.ordnance import launch_at_point

        launch_at_point(world, ship, self._tube(ship), self.x, self.y)

    def describe(self) -> str:
        return f"fire {self.ordnance} at ({self.x:,.0f}, {self.y:,.0f})"


@dataclass(kw_only=True)
class ConfigureAutoload(Command):
    """Set autoload behaviour for tubes or launchers.

    Changes affect subsequent loads; torpedoes already in tubes stay loaded
    unless `reload` is set.
    """

    weapon: str  # "tube" | "launcher"
    mounts: tuple[int, ...] | None = None
    enabled: bool | None = None
    ordnance: str | None = None
    prox: float | None = None
    time: float | None = None
    reload: bool = False
    name: ClassVar[str] = "autoload"
    needs_crew: ClassVar[bool] = False

    def validate(self, world: World, ship: Ship) -> None:
        if self.weapon == "tube":
            if not ship.tubes:
                raise Rejected(f"The {ship.cls.name} has no torpedo tubes.")
            allowed = world.content.compatible_torpedoes(ship.cls)
            spec = None
            if self.ordnance is not None:
                spec = next((t for t in allowed if t.id == self.ordnance), None)
                if spec is None:
                    names = ", ".join(t.id.upper() for t in allowed)
                    raise Rejected(f"Tubes cannot load {self.ordnance.upper()} (compatible: {names}).")
            spec = spec or world.content.torpedoes[ship.tubes[0].load_ordnance or ship.cls.torpedo]
            if self.prox is not None and not (world.rules.prox_floor <= self.prox <= spec.max_prox):
                raise Rejected(f"Proximity for {spec.id.upper()} must be {world.rules.prox_floor:.0f}–{spec.max_prox:.0f}.")
        elif self.weapon == "launcher":
            if not ship.launchers:
                raise Rejected(f"The {ship.cls.name} has no probe launchers.")
            allowed_p = world.content.compatible_probes(ship.cls)
            pspec = None
            if self.ordnance is not None:
                pspec = next((p for p in allowed_p if p.id == self.ordnance), None)
                if pspec is None:
                    names = ", ".join(p.id.upper() for p in allowed_p)
                    raise Rejected(f"Launchers cannot load {self.ordnance.upper()} (compatible: {names}).")
            pspec = pspec or world.content.probes[ship.launchers[0].load_ordnance or ship.cls.probe]
            if self.prox is not None and not (world.rules.probe_prox_floor <= self.prox <= pspec.max_prox):
                raise Rejected(f"Probe proximity must be {world.rules.probe_prox_floor:.0f}–{pspec.max_prox:.0f}.")
            if self.time is not None and not (world.rules.probe_time_floor <= self.time <= pspec.max_time_fuse):
                raise Rejected(f"Probe time fuse must be {world.rules.probe_time_floor:.0f}–{pspec.max_time_fuse:.0f}.")
        else:
            raise Rejected(f"Unknown weapon type '{self.weapon}'.")

    def apply(self, world: World, ship: Ship) -> None:
        if self.weapon == "tube":
            for i in _indices(ship.tubes, self.mounts):
                t = ship.tubes[i]
                if self.enabled is not None:
                    t.autoload = self.enabled
                if self.ordnance is not None:
                    t.load_ordnance = self.ordnance
                if self.prox is not None:
                    t.load_prox = self.prox
                if self.reload and t.loaded is not None:
                    ship.torps_remaining += 1
                    t.loaded = None
                    t.charge = 0.0
        else:
            for i in _indices(ship.launchers, self.mounts):
                lch = ship.launchers[i]
                if self.enabled is not None:
                    lch.autoload = self.enabled
                if self.ordnance is not None:
                    lch.load_ordnance = self.ordnance
                if self.prox is not None:
                    lch.load_prox = self.prox
                if self.time is not None:
                    lch.load_time = self.time
                if self.reload and lch.loaded is not None:
                    ship.probes_remaining += 1
                    lch.loaded = None
                    lch.prep = 0.0

    def describe(self) -> str:
        bits = [f"autoload {self.weapon}s"]
        if self.ordnance:
            bits.append(self.ordnance.upper())
        if self.prox is not None:
            bits.append(f"prox {self.prox:.0f}")
        if self.time is not None:
            bits.append(f"time {self.time:.0f}")
        if self.enabled is not None:
            bits.append("on" if self.enabled else "off")
        return " ".join(bits)


@dataclass(kw_only=True)
class LoadTubes(Command):
    """Manually start loading (used when autoload is off) or unload tubes; `weapon="launcher"` for probe launchers."""

    tubes: tuple[int, ...] | None = None
    unload: bool = False
    weapon: str = "tube"
    name: ClassVar[str] = "load tubes"

    def apply(self, world: World, ship: Ship) -> None:
        if self.weapon == "launcher":
            for i in _indices(ship.launchers, self.tubes):
                lch = ship.launchers[i]
                if self.unload:
                    if lch.loaded is not None:
                        ship.probes_remaining += 1
                    lch.loaded = None
                    lch.prep = 0.0
                    lch.autoload = False  # launchers stay empty until loaded again (manual p. 18)
                    lch.manual_load_pending = False
                else:
                    lch.autoload = True
                    lch.manual_load_pending = True
            return
        for i in _indices(ship.tubes, self.tubes):
            t = ship.tubes[i]
            if self.unload:
                if t.loaded is not None:
                    ship.torps_remaining += 1
                t.loaded = None
                t.charge = 0.0
                t.manual_load_pending = False
            else:
                t.manual_load_pending = True

    def describe(self) -> str:
        what = "launchers" if self.weapon == "launcher" else "tubes"
        return f"{'unload' if self.unload else 'load'} {what}"


@dataclass(kw_only=True)
class SetTubes(Command):
    """Enable or disable torpedo tube charging (manual p. 16)."""

    tubes: tuple[int, ...] | None = None
    enabled: bool = True
    name: ClassVar[str] = "tubes"
    needs_crew: ClassVar[bool] = False

    def validate(self, world: World, ship: Ship) -> None:
        if not ship.tubes:
            raise Rejected(f"The {ship.cls.name} has no torpedo tubes.")

    def apply(self, world: World, ship: Ship) -> None:
        for i in _indices(ship.tubes, self.tubes):
            ship.tubes[i].enabled = self.enabled

    def describe(self) -> str:
        return f"{'enable' if self.enabled else 'disable'} tubes"
