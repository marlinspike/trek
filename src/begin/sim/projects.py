"""Crew projects: something the officers design or build over a few cycles [E].

A project is started with the `StartProject` command (console `design <project>`,
or by asking the officers who run it) and finishes on its own; `update_projects`
advances it each tick. Who works on a project and what they say about it lives
in `crew/collaborations.py`; this module only knows what a project takes and
what it produces, so the simulation stays the same with or without officers.

To add a project: add a `ProjectDef` to `PROJECTS` with what finishing it does.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from .events import Message, ProjectCompleted, Tone
from .ship import LoadedTorpedo, Ship, Tube

if TYPE_CHECKING:
    from .world import World


@dataclass(frozen=True)
class ProjectDef:
    id: str
    title: str
    cycles: float                                          # working time with a full crew
    finish: Callable[[World, Ship, ProjectDef], int | None]  # does the work; returns a tube index if it loaded one
    ordnance: str = ""                                     # the special round it produces, if any
    needs_tubes: bool = False
    hint: str = ""                                         # how to use the result, told when it is done
    use: str = ""                                          # console command that uses a lasting result
    is_ready: Callable[[Ship], bool] | None = None         # a lasting result is already in place
    can_start: Callable[[World, Ship], str | None] | None = None   # why it can't be started now (None: it can)
    rounds: int = 1                                        # special rounds it loads


def _free_tube(ship: Ship, ordnance: str) -> Tube | None:
    """The tube a special round goes into: an empty one first, else one holding an ordinary torpedo."""
    usable = [t for t in ship.tubes if t.intact and t.enabled]
    for t in usable:
        if t.loaded is None and t.charge <= 0.0:
            return t
    for t in usable:
        if t.loaded is None:
            return t
    for t in usable:
        if t.loaded is not None and t.loaded.ordnance != ordnance:
            return t
    return None


def load_special_round(world: World, ship: Ship, proj: ProjectDef) -> int | None:
    """Put one designed round in a tube. A torpedo already there goes back to the magazine.

    The tube's own autoload setting is untouched, so once the round is fired the
    tube goes back to loading ordinary torpedoes.
    """
    spec = world.content.torpedoes[proj.ordnance]
    tube = _free_tube(ship, proj.ordnance)
    if tube is None:
        return None
    if tube.loaded is not None:
        ship.torps_remaining += 1
    elif tube.charge > 0.0:
        tube.charge = 0.0
    tube.loaded = LoadedTorpedo(spec.id, spec.max_prox)
    tube.charge = 100.0
    return tube.index


def configure_deflector(world: World, ship: Ship, proj: ProjectDef) -> int | None:
    """Set the deflector dish up for tachyon pulses; it stays set up for the rest of the battle."""
    ship.deflector_ready = True
    return None


def load_rounds(world: World, ship: Ship, proj: ProjectDef) -> int | None:
    """Several designed rounds, one to a tube; returns the first tube loaded."""
    first: int | None = None
    for _ in range(proj.rounds):
        i = load_special_round(world, ship, proj)
        if i is None:
            break
        first = i if first is None else first
    return first


def _needs_harmonics(world: World, ship: Ship) -> str | None:
    ins = world.insight.get(ship.side)
    if ins is None or not any(ins.has_code(sid) for sid in ins.surveys):
        return ("We don't have any Borg ship's shield harmonics yet. Scan them until Seven has resolved one "
                "('seven, scan for their harmonics').")
    if not any(t.intact for t in ship.tubes):
        return "The harmonic torpedoes need a working tube."
    return None


def _needs_boarders_or_hive(world: World, ship: Ship) -> str | None:
    from . import collective

    if not any(collective.is_hive(world, s) for s in world.ships.values() if s.side != ship.side):
        return "There are no Borg here, Captain."
    return None


def _needs_drones_aboard(world: World, ship: Ship) -> str | None:
    if ship.boarders <= 0:
        return "There are no drones aboard to cut off."
    return None


def _inoculate(world: World, ship: Ship, proj: ProjectDef) -> int | None:
    ship.inoculated = True
    return None


def _encrypt(world: World, ship: Ship, proj: ProjectDef) -> int | None:
    ship.encrypted = True
    return None


def _sever(world: World, ship: Ship, proj: ProjectDef) -> int | None:
    ship.severed = ship.boarders > 0
    return None


PROJECTS: dict[str, ProjectDef] = {
    "deflector": ProjectDef("deflector", "deflector tachyon pulse", 12.0, configure_deflector,
                            hint="Sweep ahead of the ship with 'pulse'.", use="pulse",
                            is_ready=lambda ship: ship.deflector_ready),
    "tachyon": ProjectDef("tachyon", "tachyon detector torpedo", 20.0, load_special_round,
                          ordnance="tachyon", needs_tubes=True,
                          hint="Fire it with 'tachyon <bearing> <range>' or 'tachyon <ship>'."),
    # the Borg [E] (sim/collective.py)
    "harmonic": ProjectDef("harmonic", "harmonic torpedoes", 16.0, load_rounds, ordnance="harmonic", needs_tubes=True,
                           rounds=3, can_start=_needs_harmonics,
                           hint="They go with your next torpedo volley, straight through the shields of any Borg "
                                "ship whose harmonics we hold."),
    "inoculate": ProjectDef("inoculate", "counter-nanoprobe inoculation", 26.0, lambda w, s, p: _inoculate(w, s, p),
                            can_start=_needs_boarders_or_hive, is_ready=lambda ship: ship.inoculated,
                            hint="Crew the drones beat now die rather than turn."),
    "encrypt": ProjectDef("encrypt", "computer lockout", 14.0, lambda w, s, p: _encrypt(w, s, p),
                          can_start=_needs_boarders_or_hive, is_ready=lambda ship: ship.encrypted,
                          hint="The drones can't seize any more of the ship's systems."),
    "sever": ProjectDef("sever", "link to the hive cut", 6.0, lambda w, s, p: _sever(w, s, p),
                        can_start=_needs_drones_aboard, is_ready=lambda ship: ship.severed,
                        hint="The drones aboard fight alone now: slower, and they seize nothing."),
}


def project_loaded(ship: Ship, proj: ProjectDef) -> int | None:
    """Index of a tube already holding this project's round, if any."""
    return next((t.index for t in ship.tubes if t.loaded is not None and t.loaded.ordnance == proj.ordnance), None)


def update_projects(world: World, ship: Ship, dt: float) -> None:
    if not ship.projects or ship.crew <= 0 or not ship.alive:
        return
    rate = max(0.25, ship.crew / max(1, ship.cls.crew))  # fewer hands, slower work
    for pid in list(ship.projects):
        ship.projects[pid] -= dt * rate
        if ship.projects[pid] > 0:
            continue
        del ship.projects[pid]
        proj = PROJECTS[pid]
        tube = proj.finish(world, ship, proj)
        world.emit(ProjectCompleted(world.tick, ship.id, pid, tube))
        if proj.ordnance and tube is None:
            text = f"The {proj.title} is ready, but no tube can take it."
        elif tube is not None:
            text = f"The {proj.title} is loaded in tube {tube + 1}. {proj.hint}".strip()
        else:
            text = f"The {proj.title} is ready. {proj.hint}".strip()
        world.emit(Message(world.tick, text, Tone.GOOD, ship_id=ship.id, visible_to=frozenset({ship.side})))


__all__ = ["PROJECTS", "ProjectDef", "load_special_round", "project_loaded", "update_projects"]
