"""After the battle: which bridge officer did the most for the ship [E].

An officer's part is counted from what the ship's own records show: the
orders they gave that were carried out (the command log names who gave each),
the objectives they saw through, and the projects their station finished.
It says nothing about how well the captain did; that is the assessment's job.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass

from ..sim.events import Event, ObjectiveEnded, ProjectCompleted
from ..sim.world import LoggedCommand
from .characters import OfficerProfile

OBJECTIVE_WEIGHT = 6      # an objective seen through counts as this many orders
PROJECT_WEIGHT = 8

TRIBUTE = {
    "helm": "kept us out of the worst of it",
    "tactical": "kept the weapons on target",
    "engineering": "kept the ship together",
    "science": "found us the openings",
}


@dataclass(frozen=True)
class Standout:
    officer: OfficerProfile
    orders: int
    objectives: int
    projects: int

    @property
    def score(self) -> int:
        return self.orders + OBJECTIVE_WEIGHT * self.objectives + PROJECT_WEIGHT * self.projects

    def line(self) -> str:
        bits = [f"{self.orders} order{'s' if self.orders != 1 else ''} carried out"]
        if self.objectives:
            bits.append(f"{self.objectives} objective{'s' if self.objectives != 1 else ''} achieved")
        if self.projects:
            bits.append(f"{self.projects} project{'s' if self.projects != 1 else ''} finished")
        return f"{self.officer.title} {TRIBUTE.get(self.officer.station, 'did the ship proud')}: " + ", ".join(bits) + "."


def _sources(o: OfficerProfile) -> set[str]:
    out = {o.title, o.name, o.station}
    if o.station == "helm":
        out.add("Helm")       # the helm officer's dodges are logged under the station
    return out


def standout(officers: Iterable[OfficerProfile], ship_id: int, log: Iterable[LoggedCommand],
             events: Iterable[Event]) -> Standout | None:
    """The officer who did the most, or None if none of them did anything (the captain fought her alone)."""
    crew = list(officers)
    orders = {o.id: 0 for o in crew}
    objectives = {o.id: 0 for o in crew}
    projects = {o.id: 0 for o in crew}
    by_source = {src: o.id for o in crew for src in _sources(o)}
    for lc in log:
        if lc.accepted and lc.command.ship_id == ship_id:
            oid = by_source.get(lc.command.source)
            if oid is not None:
                orders[oid] += 1
    science = next((o.id for o in crew if o.station == "science"), None)
    for ev in events:
        if isinstance(ev, ObjectiveEnded) and ev.ship_id == ship_id and ev.outcome == "done" and ev.officer in objectives:
            objectives[ev.officer] += 1
        elif isinstance(ev, ProjectCompleted) and ev.ship_id == ship_id and science is not None:
            projects[science] += 1       # Seven leads the designs
    best = max(crew, key=lambda o: (orders[o.id] + OBJECTIVE_WEIGHT * objectives[o.id] + PROJECT_WEIGHT * projects[o.id]),
               default=None)
    if best is None:
        return None
    s = Standout(best, orders[best.id], objectives[best.id], projects[best.id])
    return s if s.score > 0 else None


__all__ = ["Standout", "standout"]
