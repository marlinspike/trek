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


PROJECTS: dict[str, ProjectDef] = {
    "deflector": ProjectDef("deflector", "deflector tachyon pulse", 12.0, configure_deflector,
                            hint="Sweep ahead of the ship with 'pulse'.", use="pulse",
                            is_ready=lambda ship: ship.deflector_ready),
    "tachyon": ProjectDef("tachyon", "tachyon detector torpedo", 20.0, load_special_round,
                          ordnance="tachyon", needs_tubes=True,
                          hint="Fire it with 'tachyon <bearing> <range>' or 'tachyon <ship>'."),
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
