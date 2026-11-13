"""Readbacks: what the bridge understood, said back in a sentence [E].

On a real bridge an order is repeated back before it is carried out, so a
misheard order is caught at once. Every order the captain gives through the
console, the wheel, a proposal or by voice is read back here: the exact
course, warp, mounts, target and system, in the words an officer would use
("Course 090, warp 6. Aye, Captain."). Nothing here is guessed: each phrase
is built from the command's own fields, so the readback is what will happen.

`readback(cmd, name_of)` returns the sentence; `name_of(ship_id)` names a
ship as the captain sees it. Commands without a phrase of their own fall back
to `Command.describe()`.
"""

from __future__ import annotations

from typing import Callable

from ..sim.objectives import STRIKE_GROUPS
from ..sim.commands import (
    AllyOrder, CeaseFire, Command, ConfigureAutoload, DelegateStation, DeflectorPulse, Dock, EngineBoost, EndObjective, Evasive,
    FireBait, FirePhasers, FireTorpedoes, LaunchProbe, LoadTubes, LockWeapons, ManageRepairs, OpenFire, Pursue,
    ReinforceShield, Scan, SelectTarget, SetBanks, SetCloak, SetHelm, SetObjective, SetPhaserSpread, SetPointDefense,
    SetRepairPriority, SetShields, StandDown, StartProject, TakeConn, Tractor, Transport, TurnMounts,
)

NameOf = Callable[[int], str]

STATION_TITLES = {"helm": "Helm", "tactical": "Tactical", "engineering": "Engineering", "science": "Science"}


def mounts(ids: tuple[int, ...] | None, noun: str, plural: str) -> str:
    """'all phasers', 'phaser 2', 'phasers 1, 2 and 4' (mounts are numbered from 1 for the captain)."""
    if ids is None:
        return f"all {plural}"
    nums = [str(i + 1) for i in sorted(ids)]
    if len(nums) == 1:
        return f"{noun} {nums[0]}"
    return f"{plural} {', '.join(nums[:-1])} and {nums[-1]}"


def _course(c: float) -> str:
    return f"{round(c) % 360:03d}"


def _warp(w: float) -> str:
    return f"{w:g}" if float(w).is_integer() else f"{w:.1f}"


def _at(target: int | None, name_of: NameOf, system: str | None = None) -> str:
    if target is None:
        return " at the target"
    aim = f", aiming for her {system}" if system and system != "hull" else ""
    return f" at the {name_of(target)}{aim}"


def readback(cmd: Command, name_of: NameOf) -> str:
    """One sentence that says exactly what this order will do."""
    if isinstance(cmd, SetHelm):
        if cmd.warp == 0.0 and cmd.course is None:
            return "All stop."
        bits = []
        if cmd.course is not None:
            bits.append(f"Course {_course(cmd.course)}")
        if cmd.warp is not None:
            bits.append(f"warp {_warp(cmd.warp)}")
        s = ", ".join(bits) or "Holding course"
        return s[0].upper() + s[1:] + "."
    if isinstance(cmd, Pursue):
        how = "Breaking away from" if cmd.elude else "Pursuing"
        warp = f" at warp {_warp(cmd.warp)}" if cmd.warp is not None else ""
        return f"{how} the {name_of(cmd.target)}{warp}."
    if isinstance(cmd, Evasive):
        return "Evasive manoeuvres; I'll dodge their torpedoes." if cmd.on else "Evasive manoeuvres ended."
    if isinstance(cmd, Dock):
        return f"Docking with the {name_of(cmd.host)}." if cmd.host is not None else "Undocking."
    if isinstance(cmd, FirePhasers):
        if cmd.at_bearing is not None:
            return f"Firing {mounts(cmd.banks, 'phaser', 'phasers')} on bearing {_course(cmd.at_bearing)}."
        spread = f", spread {cmd.spread:g}" if cmd.spread is not None else ""
        return f"Firing {mounts(cmd.banks, 'phaser', 'phasers')}{_at(cmd.target, name_of, cmd.subsystem)}{spread}."
    if isinstance(cmd, FireBait):
        return f"One torpedo as bait{_at(cmd.target, name_of)}, the rest to follow."
    if isinstance(cmd, FireTorpedoes):
        what = mounts(cmd.tubes, "tube", "tubes")
        if cmd.count is not None:
            what = f"{cmd.count} torpedo{'es' if cmd.count != 1 else ''}"
        fan = f", fanned {cmd.fan:g}°" if cmd.fan else ""
        return f"Firing {what}{_at(cmd.target, name_of, cmd.subsystem)}{fan}."
    if isinstance(cmd, LaunchProbe):
        where = f" on course {_course(cmd.course)}" if cmd.course is not None else _at(cmd.target, name_of)
        n = f"{cmd.count} probes" if cmd.count > 1 else "a probe"
        return f"Launching {n}{where}."
    if isinstance(cmd, SelectTarget):
        if cmd.target is None:
            return "Target cleared."
        aim = f", aiming for her {cmd.subsystem}" if cmd.subsystem and cmd.subsystem != "hull" else ""
        lock = "; weapons locked" if cmd.lock_weapons else ""
        return f"Targeting the {name_of(cmd.target)}{aim}{lock}."
    if isinstance(cmd, LockWeapons):
        parts = []
        if cmd.phasers:
            parts.append(mounts(cmd.banks, "phaser", "phasers"))
        if cmd.torpedoes:
            parts.append(mounts(cmd.tubes, "tube", "tubes"))
        what = " and ".join(parts) or "weapons"
        on = f"on the {name_of(cmd.target)}" if cmd.target is not None else "on the target"
        return f"{what[0].upper() + what[1:]} locked {on}."
    if isinstance(cmd, TurnMounts):
        return f"Turning mounts to mark {cmd.mark:g}."
    if isinstance(cmd, SetPhaserSpread):
        return f"Phaser spread {cmd.spread:g}."
    if isinstance(cmd, SetBanks):
        if cmd.role is not None:
            return f"{mounts(cmd.banks, 'Phaser', 'Phasers')} set to {cmd.role.value}."
        return f"{mounts(cmd.banks, 'Phaser', 'Phasers')} {'enabled' if cmd.enabled else 'disabled'}."
    if isinstance(cmd, LoadTubes):
        noun, plural = ("launcher", "launchers") if cmd.weapon == "launcher" else ("tube", "tubes")
        return f"{'Unloading' if cmd.unload else 'Loading'} {mounts(cmd.tubes, noun, plural)}."
    if isinstance(cmd, ConfigureAutoload):
        state = "off" if cmd.enabled is False else "on"
        kind = f" with {cmd.ordnance.upper()}" if cmd.ordnance else ""
        return f"Autoload {state} for the {cmd.weapon}s{kind}."
    if isinstance(cmd, SetPointDefense):
        return f"Point defense {cmd.doctrine.value}."
    if isinstance(cmd, SetShields):
        which = "all shields" if cmd.sectors is None else mounts(cmd.sectors, "shield", "shields")
        return f"{'Raising' if cmd.up else 'Lowering'} {which}."
    if isinstance(cmd, ReinforceShield):
        return "Shield reinforcement off." if cmd.sector is None else f"Reinforcing shield {cmd.sector + 1}."
    if isinstance(cmd, SetRepairPriority):
        kind = str(getattr(cmd.kind, "value", cmd.kind))
        return "Repair crews spread across the ship." if cmd.kind is None else f"Repair crews to the {kind} first."
    if isinstance(cmd, ManageRepairs):
        return "Repairs are mine, Captain." if cmd.officer else "Repair crews answer to you, Captain."
    if isinstance(cmd, SetCloak):
        return "Cloaking." if cmd.on else "Decloaking."
    if isinstance(cmd, Scan):
        return f"Scanning the {name_of(cmd.target)}."
    if isinstance(cmd, SetObjective):
        many = len(cmd.targets)
        ships = f"the {name_of(cmd.targets[0])}" if many == 1 else f"{many} ships"
        if cmd.goal == "disable":
            return f"Knocking out the {cmd.group} on {ships}, then sparing her." if many == 1 else \
                f"Knocking out the {cmd.group} on {ships}."
        if cmd.goal == "hunt":
            return f"Hunting for {ships}."
        if cmd.goal == "strike":
            what = "" if cmd.group == "hull" else f"'s {STRIKE_GROUPS.get(cmd.group, cmd.group)}"
            return f"Sweep and strike: the moment the seeker lands, a salvo into {ships}{what}."
        return f"Standing order: {cmd.goal} {ships}."
    if isinstance(cmd, EndObjective):
        return "Standing order ended."
    if isinstance(cmd, StartProject):
        return f"Starting work on the {cmd.project}."
    if isinstance(cmd, DeflectorPulse):
        return "Pulsing the deflector."
    if isinstance(cmd, EngineBoost):
        return ("A team to the engines. Other repairs slow while they work." if cmd.on else
                "Engine team back to repairs.")
    if isinstance(cmd, CeaseFire):
        return "Ceasing fire. Point defense stays on."
    if isinstance(cmd, OpenFire):
        return "Weapons free."
    if isinstance(cmd, StandDown):
        return "Standing down. Every station is yours."
    if isinstance(cmd, DelegateStation):
        title = STATION_TITLES.get(cmd.station, cmd.station.title())
        return f"{title} is mine, Captain." if cmd.on else f"{title} is yours, Captain."
    if isinstance(cmd, TakeConn):
        return "I have the bridge." if cmd.officer else "You have the bridge, Captain."
    if isinstance(cmd, Tractor):
        return f"Tractor beam on the {name_of(cmd.target)}." if cmd.target is not None else "Tractor beam released."
    if isinstance(cmd, Transport):
        return f"Beaming {cmd.count} to the {name_of(cmd.target)}."
    if isinstance(cmd, AllyOrder):
        on = f" on the {name_of(cmd.target)}" if cmd.target is not None else ""
        return f"Signalling the {name_of(cmd.ally)}: {cmd.order}{on}."
    d = cmd.describe()
    return d[0].upper() + d[1:] + "."


__all__ = ["STATION_TITLES", "mounts", "readback"]
