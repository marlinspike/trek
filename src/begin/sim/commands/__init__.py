"""Typed commands: the only way anything changes a ship's intent.

Players, AI captains, ship computers and delegated officers all submit the
same command types. Each command validates against the current world and
either applies or is rejected with a human-readable reason.

Authority and control channels: a command declares the channels it drives
(e.g. "helm"). When the CAPTAIN issues one, lower authorities (computer,
officer) are locked out of that channel for a hold period, so automation
never fights an explicit order. Delegating a station clears its holds.

The commands live in one module per station: helm, targeting, phasers, torpedoes, probes, shields,
crew, fire control, operations, ally orders and the Borg. Every name is re-exported here, so
`from begin.sim.commands import X` is unchanged."""

from __future__ import annotations

from .ally_orders import AllyOrder, in_mount_arc
from .base import Authority, Command, Rejected
from .borg import COUNTERMEASURES, DUTIES, AwayTeam, Countermeasure, Remodulate, SetDuty, ShuttleOrder
from .crew import STATION_CHANNELS, AddressCrew, DelegateStation, ManageRepairs, SelfDestruct, SetRepairPriority, Surrender, TakeConn
from .fire_control import (
    CeaseFire, DeflectorPulse, EndObjective, FireAtPoint, FireBait, OpenFire, SetObjective, StandDown, fire_target,
    offensive_fire,
)
from .helm import Evasive, Pursue, SetHelm, end_objectives
from .operations import SWEEP_CYCLES, Dock, FireSeeker, Hail, Scan, SetCloak, Sweep, Tractor, Transport
from .phasers import FirePhasers, SetBanks, SetPhaserSpread
from .probes import ControlProbe, LaunchProbe, SetFireMode, SetPointDefense
from .shields import ReinforceShield, SetShields
from .targeting import LockWeapons, SelectTarget, SplitFire, TurnMounts, split_locks
from .torpedoes import ConfigureAutoload, EngineBoost, FireSpecialRound, FireTorpedoes, LoadTubes, SetTubes, StartProject

__all__ = [
    "AddressCrew",
    "AllyOrder",
    "Authority",
    "AwayTeam",
    "COUNTERMEASURES",
    "CeaseFire",
    "Command",
    "ConfigureAutoload",
    "ControlProbe",
    "Countermeasure",
    "DUTIES",
    "DeflectorPulse",
    "DelegateStation",
    "Dock",
    "EndObjective",
    "EngineBoost",
    "Evasive",
    "FireAtPoint",
    "FireBait",
    "FirePhasers",
    "FireSeeker",
    "FireSpecialRound",
    "FireTorpedoes",
    "Hail",
    "LaunchProbe",
    "LoadTubes",
    "LockWeapons",
    "SplitFire",
    "ManageRepairs",
    "OpenFire",
    "Pursue",
    "ReinforceShield",
    "Rejected",
    "Remodulate",
    "STATION_CHANNELS",
    "SWEEP_CYCLES",
    "Scan",
    "SelectTarget",
    "SelfDestruct",
    "SetBanks",
    "SetCloak",
    "SetDuty",
    "SetFireMode",
    "SetHelm",
    "SetObjective",
    "SetPhaserSpread",
    "SetPointDefense",
    "SetRepairPriority",
    "SetShields",
    "SetTubes",
    "ShuttleOrder",
    "StandDown",
    "StartProject",
    "Surrender",
    "Sweep",
    "TakeConn",
    "Tractor",
    "Transport",
    "TurnMounts",
    "end_objectives",
    "fire_target",
    "in_mount_arc",
    "offensive_fire",
    "split_locks",
]
