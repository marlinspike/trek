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

from collections.abc import Mapping, Sequence
from typing import Any, Callable

from ..sim.objectives import STRIKE_GROUPS
from ..sim.commands import (
    AllyOrder, CeaseFire, Command, ConfigureAutoload, DelegateStation, DeflectorPulse, Dock, EngineBoost, EndObjective, Evasive,
    FireBait, FirePhasers, FireTorpedoes, LaunchProbe, LoadTubes, LockWeapons, ManageRepairs, OpenFire, Pursue,
    ReinforceShield, Scan, SelectTarget, SetBanks, SetCloak, SetHelm, SetObjective, SetPhaserSpread, SetPointDefense,
    SetRepairPriority, SetShields, SplitFire, StandDown, StartProject, TakeConn, Tractor, Transport, TurnMounts,
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


# One phrase per kind of order. Each takes the command and `name_of`; they are tried in this order with
# isinstance, so a subclass listed before its base (FireBait before FireTorpedoes) keeps its own phrase.


def _set_helm(cmd: SetHelm, name_of: NameOf) -> str:
    if cmd.warp == 0.0 and cmd.course is None:
        return "All stop."
    bits = []
    if cmd.course is not None:
        bits.append(f"Course {_course(cmd.course)}")
    if cmd.warp is not None:
        bits.append(f"warp {_warp(cmd.warp)}")
    s = ", ".join(bits) or "Holding course"
    return s[0].upper() + s[1:] + "."


def _pursue(cmd: Pursue, name_of: NameOf) -> str:
    how = "Breaking away from" if cmd.elude else "Pursuing"
    warp = f" at warp {_warp(cmd.warp)}" if cmd.warp is not None else ""
    return f"{how} the {name_of(cmd.target)}{warp}."


def _evasive(cmd: Evasive, name_of: NameOf) -> str:
    return "Evasive manoeuvres; I'll dodge their torpedoes." if cmd.on else "Evasive manoeuvres ended."


def _dock(cmd: Dock, name_of: NameOf) -> str:
    return f"Docking with the {name_of(cmd.host)}." if cmd.host is not None else "Undocking."


def _fire_phasers(cmd: FirePhasers, name_of: NameOf) -> str:
    if cmd.at_bearing is not None:
        return f"Firing {mounts(cmd.banks, 'phaser', 'phasers')} on bearing {_course(cmd.at_bearing)}."
    spread = f", spread {cmd.spread:g}" if cmd.spread is not None else ""
    return f"Firing {mounts(cmd.banks, 'phaser', 'phasers')}{_at(cmd.target, name_of, cmd.subsystem)}{spread}."


def _fire_bait(cmd: FireBait, name_of: NameOf) -> str:
    return f"One torpedo as bait{_at(cmd.target, name_of)}, the rest to follow."


def _fire_torpedoes(cmd: FireTorpedoes, name_of: NameOf) -> str:
    what = mounts(cmd.tubes, "tube", "tubes")
    if cmd.count is not None:
        what = f"{cmd.count} torpedo{'es' if cmd.count != 1 else ''}"
    fan = f", fanned {cmd.fan:g}°" if cmd.fan else ""
    return f"Firing {what}{_at(cmd.target, name_of, cmd.subsystem)}{fan}."


def _launch_probe(cmd: LaunchProbe, name_of: NameOf) -> str:
    where = f" on course {_course(cmd.course)}" if cmd.course is not None else _at(cmd.target, name_of)
    n = f"{cmd.count} probes" if cmd.count > 1 else "a probe"
    return f"Launching {n}{where}."


def _select_target(cmd: SelectTarget, name_of: NameOf) -> str:
    if cmd.target is None:
        return "Target cleared."
    aim = f", aiming for her {cmd.subsystem}" if cmd.subsystem and cmd.subsystem != "hull" else ""
    lock = "; weapons locked" if cmd.lock_weapons else ""
    return f"Targeting the {name_of(cmd.target)}{aim}{lock}."


def _lock_weapons(cmd: LockWeapons, name_of: NameOf) -> str:
    parts = []
    if cmd.phasers:
        parts.append(mounts(cmd.banks, "phaser", "phasers"))
    if cmd.torpedoes:
        parts.append(mounts(cmd.tubes, "tube", "tubes"))
    what = " and ".join(parts) or "weapons"
    on = f"on the {name_of(cmd.target)}" if cmd.target is not None else "on the target"
    return f"{what[0].upper() + what[1:]} locked {on}."


def _set_banks(cmd: SetBanks, name_of: NameOf) -> str:
    if cmd.role is not None:
        return f"{mounts(cmd.banks, 'Phaser', 'Phasers')} set to {cmd.role.value}."
    return f"{mounts(cmd.banks, 'Phaser', 'Phasers')} {'enabled' if cmd.enabled else 'disabled'}."


def _load_tubes(cmd: LoadTubes, name_of: NameOf) -> str:
    noun, plural = ("launcher", "launchers") if cmd.weapon == "launcher" else ("tube", "tubes")
    return f"{'Unloading' if cmd.unload else 'Loading'} {mounts(cmd.tubes, noun, plural)}."


def _autoload(cmd: ConfigureAutoload, name_of: NameOf) -> str:
    state = "off" if cmd.enabled is False else "on"
    kind = f" with {cmd.ordnance.upper()}" if cmd.ordnance else ""
    return f"Autoload {state} for the {cmd.weapon}s{kind}."


def _set_shields(cmd: SetShields, name_of: NameOf) -> str:
    which = "all shields" if cmd.sectors is None else mounts(cmd.sectors, "shield", "shields")
    return f"{'Raising' if cmd.up else 'Lowering'} {which}."


def _repair_priority(cmd: SetRepairPriority, name_of: NameOf) -> str:
    kind = str(getattr(cmd.kind, "value", cmd.kind))
    return "Repair crews spread across the ship." if cmd.kind is None else f"Repair crews to the {kind} first."


def runs(idx: Sequence[int]) -> str:
    """'1-4', '1, 2 and 5', '3' from zero-based indices."""
    nums = sorted(i + 1 for i in idx)
    if not nums:
        return ""
    parts: list[str] = []
    start = prev = nums[0]
    for n in [*nums[1:], None]:
        if n is not None and n == prev + 1:
            prev = n
            continue
        parts.extend([str(start)] if start == prev else [str(start), str(prev)] if prev == start + 1 else [f"{start}-{prev}"])
        if n is not None:
            start = prev = n
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def split_words(banks: Mapping[int, Sequence[int]], tubes: Mapping[int, Sequence[int]],
                name_of: Callable[[int], str]) -> str:
    """Words for where the weapons are: "Tubes 1-4 on the Talon, 5-8 on the Wraith; phasers on the Talon."
    A weapon all on one ship is named without numbers."""
    def part(plural: str, given: Mapping[int, Sequence[int]]) -> str:
        groups = {t: g for t, g in given.items() if g}
        if not groups:
            return ""
        if len(groups) == 1:
            ((t, _),) = groups.items()
            return f"{plural} on the {name_of(t)}"
        bits = [f"{runs(g)} on the {name_of(t)}" for t, g in sorted(groups.items(), key=lambda kv: min(kv[1]))]
        return f"{plural} {', '.join(bits)}" if len(bits) > 2 else f"{plural} {bits[0]}, {bits[1]}"
    t = part("tubes", tubes)
    b = part("phasers", banks)
    text = "; ".join(x for x in (t, b) if x)
    return (text[0].upper() + text[1:] + ".") if text else ""


def _split_fire(cmd: SplitFire, name_of: NameOf) -> str:
    return "Splitting fire. " + split_words(dict(cmd.banks), dict(cmd.tubes), name_of)


def _set_objective(cmd: SetObjective, name_of: NameOf) -> str:
    many = len(cmd.targets)
    ships = f"the {name_of(cmd.targets[0])}" if many == 1 else f"{many} ships"
    if cmd.goal == "disable":
        return f"Knocking out the {cmd.group} on {ships}, then sparing her." if many == 1 else \
            f"Knocking out the {cmd.group} on {ships}."
    if cmd.goal == "hunt":
        return f"Hunting for {ships}."
    if cmd.goal == "engage":
        named = [f"the {name_of(t)}" for t in cmd.targets]
        both = " and ".join(named) if len(named) < 3 else ", ".join(named[:-1]) + " and " + named[-1]
        return f"Engaging {both}. I'll divide our fire between them."
    if cmd.goal == "strike":
        what = "" if cmd.group == "hull" else f"'s {STRIKE_GROUPS.get(cmd.group, cmd.group)}"
        return f"Sweep and strike: the moment the seeker lands, a salvo into {ships}{what}."
    return f"Standing order: {cmd.goal} {ships}."


def _delegate(cmd: DelegateStation, name_of: NameOf) -> str:
    title = STATION_TITLES.get(cmd.station, cmd.station.title())
    return f"{title} is mine, Captain." if cmd.on else f"{title} is yours, Captain."


def _ally_order(cmd: AllyOrder, name_of: NameOf) -> str:
    on = f" on the {name_of(cmd.target)}" if cmd.target is not None else ""
    return f"Signalling the {name_of(cmd.ally)}: {cmd.order}{on}."


_PHRASES: tuple[tuple[type[Command], Callable[[Any, NameOf], str]], ...] = (
    (SetHelm, _set_helm),
    (Pursue, _pursue),
    (Evasive, _evasive),
    (Dock, _dock),
    (FirePhasers, _fire_phasers),
    (FireBait, _fire_bait),
    (FireTorpedoes, _fire_torpedoes),
    (LaunchProbe, _launch_probe),
    (SelectTarget, _select_target),
    (LockWeapons, _lock_weapons),
    (SplitFire, _split_fire),
    (TurnMounts, lambda cmd, name_of: f"Turning mounts to mark {cmd.mark:g}."),
    (SetPhaserSpread, lambda cmd, name_of: f"Phaser spread {cmd.spread:g}."),
    (SetBanks, _set_banks),
    (LoadTubes, _load_tubes),
    (ConfigureAutoload, _autoload),
    (SetPointDefense, lambda cmd, name_of: f"Point defense {cmd.doctrine.value}."),
    (SetShields, _set_shields),
    (ReinforceShield, lambda cmd, name_of: "Shield reinforcement off." if cmd.sector is None
        else f"Reinforcing shield {cmd.sector + 1}."),
    (SetRepairPriority, _repair_priority),
    (ManageRepairs, lambda cmd, name_of: "Repairs are mine, Captain." if cmd.officer
        else "Repair crews answer to you, Captain."),
    (SetCloak, lambda cmd, name_of: "Cloaking." if cmd.on else "Decloaking."),
    (Scan, lambda cmd, name_of: f"Scanning the {name_of(cmd.target)}."),
    (SetObjective, _set_objective),
    (EndObjective, lambda cmd, name_of: "Standing order ended."),
    (StartProject, lambda cmd, name_of: f"Starting work on the {cmd.project}."),
    (DeflectorPulse, lambda cmd, name_of: "Pulsing the deflector."),
    (EngineBoost, lambda cmd, name_of: "A team to the engines. Other repairs slow while they work." if cmd.on
        else "Engine team back to repairs."),
    (CeaseFire, lambda cmd, name_of: "Ceasing fire. Point defense stays on."),
    (OpenFire, lambda cmd, name_of: "Weapons free."),
    (StandDown, lambda cmd, name_of: "Standing down. Every station is yours."),
    (DelegateStation, _delegate),
    (TakeConn, lambda cmd, name_of: "I have the bridge." if cmd.officer else "You have the bridge, Captain."),
    (Tractor, lambda cmd, name_of: f"Tractor beam on the {name_of(cmd.target)}." if cmd.target is not None
        else "Tractor beam released."),
    (Transport, lambda cmd, name_of: f"Beaming {cmd.count} to the {name_of(cmd.target)}."),
    (AllyOrder, _ally_order),
)


def readback(cmd: Command, name_of: NameOf) -> str:
    """One sentence that says exactly what this order will do."""
    for kind, phrase in _PHRASES:
        if isinstance(cmd, kind):
            return phrase(cmd, name_of)
    d = cmd.describe()
    return d[0].upper() + d[1:] + "."


__all__ = ["STATION_TITLES", "mounts", "readback", "runs", "split_words"]
