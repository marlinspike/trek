"""What the officers say about the Borg [E]: the science officer's survey, the hive adapting to our weapons, ships
going dark and waking, cores going critical, the shields' tuning, away teams, stand-ins taking a station, and the
Doctor's sickbay.

The simulation says what happened (`HiveEvent`, sim/collective.py and sim/away.py); this turns it into the right
officer's words, from their `lines` in officers.toml (the player's own lines win, config/officers.toml). These
reports carry what the captain needs to decide, so they are said even with the bridge chatter turned off; each
kind is rate limited so a long fight doesn't become a stream of them.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Iterable

from ..sim.events import Event, HiveEvent
from ..sim.observation import Observation
from ..sim.ship import Ship
from .characters import OfficerProfile
from .station_reports import contact_name
from .utterance import Utterance

if TYPE_CHECKING:
    from .conversation import Bridge

WEAPON_WORDS = {"phaser": "phasers", "torpedo": "torpedoes", "harmonic": "harmonic torpedoes", "probe": "probes"}
PROGRESS_EVERY = 0.25         # the survey's progress is said at each quarter
SAME_GAP = 10.0               # seconds before the same kind of hive report is said again
LEAK_GAP = 40.0               # seconds between warnings that we are venting plasma


@dataclass
class HiveTalk:
    """What has been said about the Borg this battle, so nothing is said twice when once will do."""

    said: dict[str, int] = field(default_factory=dict)             # report kind (and ship) -> tick
    survey_band: dict[int, int] = field(default_factory=dict)      # hive ship -> quarter of the survey last said
    tuning: str = ""                                               # "" | "started" | "done"
    covered: int = 0                                               # stand-ins already announced
    wounded: frozenset[str] = frozenset()                          # who was in sickbay last time we looked


def _fresh(talk: HiveTalk, key: str, obs: Observation, gap: float = SAME_GAP) -> bool:
    last = talk.said.get(key)
    if last is not None and obs.tick - last < gap * obs.rules.ticks_per_cycle:
        return False
    talk.said[key] = obs.tick
    return True


def _system(sid: str) -> str:
    stem = sid.rstrip("0123456789")
    return f"{stem} {sid[len(stem):]}" if stem != sid else sid


def _names(b: Bridge, ids: Iterable[str]) -> str:
    names = [o.name for i in ids if (o := b.find(i)) is not None]
    return names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1] if names else ""


def hive_remarks(b: Bridge, events: Iterable[Event], s: Ship, obs: Observation) -> list[Utterance]:
    """The officers' reports on the Borg this step: events first, then what has changed aboard."""
    out: list[Utterance] = []
    talk = b._hive

    def say(o: OfficerProfile | None, event: str, fallback: str = "", **fill: object) -> None:
        if o is None:
            return
        u = b._line(o, event, **fill) or (b._say(o, fallback.format(**fill)) if fallback else None)
        if u is None:
            return
        b._last_line[o.id] = b._last_any = obs.tick
        if not b._voice(o, u.text, obs):
            out.append(u)

    sci, tac, eng = b.crew.officer("science"), b.crew.officer("tactical"), b.crew.officer("engineering")
    doctor = b.find("doctor")
    for ev in events:
        if not isinstance(ev, HiveEvent):
            continue
        name = contact_name(obs, ev.ship_id)
        if ev.kind == "surveyed" and ev.target == s.id:
            found, _, by = ev.detail.partition("|")
            o = b.find(by) if by else sci
            if found == "weak":
                relay = obs.weak_point(ev.ship_id)
                say(o, "weak_found", "{target}'s vinculum relay runs through its {system}. Destroy it and the drones "
                    "sleep.", target=name, system=_system(relay) if relay else "auxiliary systems")
            elif found == "code":
                say(o, "harmonics_done", "I have {target}'s shield harmonics. Say 'design harmonic'.", target=name)
            else:
                band = int(float(found or 0.0) / PROGRESS_EVERY + 1e-6)
                was = talk.survey_band.get(ev.ship_id)
                talk.survey_band[ev.ship_id] = band
                if was is None:
                    say(o, "harmonics_start", "Beginning a harmonic survey of {target}.", target=name)
                elif band > was:
                    say(o, "harmonics_progress", "{target}'s shield harmonics: {n} percent.", target=name,
                        n=round(float(found) * 100))
        elif ev.kind == "adapted" and ev.target == s.id and _fresh(talk, f"adapted:{ev.detail}", obs):
            family = ev.detail.partition(":")[0]
            say(tac or sci, "adapted", "They have adapted to our {weapon}.", weapon=WEAPON_WORDS.get(family, family))
        elif ev.kind == "shift" and ev.target == s.id and _fresh(talk, "shift", obs, 20.0):
            say(b.find(ev.detail) if ev.detail else sci, "shift", "They have shifted their beams. Retuning.")
        elif ev.kind == "remodulated" and ev.ship_id == s.id and ev.detail and _fresh(talk, "remodulate", obs, 6.0):
            say(b.find(ev.detail), "remodulate", "Remodulating phasers.")
        elif ev.kind == "dormant" and (obs.contact(ev.ship_id) or obs.own(ev.ship_id)) is not None:
            say(sci, "dormant", "{target} has gone dark. Its drones are dormant for {n} cycles.", target=name,
                n=ev.detail or "a few")
        elif ev.kind == "waking" and obs.contact(ev.ship_id) is not None:
            say(sci, "waking", "{target} is awake again, Captain.", target=name)
        elif ev.kind == "critical" and obs.contact(ev.ship_id) is not None:
            say(eng or sci, "critical", "{target}'s core has gone critical! {n} cycles. Get us clear, Captain!",
                target=name, n=ev.detail or "a few")
        elif ev.kind == "shuttle" and ev.target is not None and (op := _op(obs, ev.target)) is not None:
            say(b.find(op.members[0]) if op.members else None, "away", "We are on our way, Captain.")
    _aboard(b, s, obs, say, talk, sci, eng, doctor)
    return out


def _op(obs: Observation, shuttle: int):  # type: ignore[no-untyped-def]
    return next((op for op in obs.away_ops() if op.shuttle == shuttle), None)


def _aboard(b: Bridge, s: Ship, obs: Observation, say, talk: HiveTalk, sci: OfficerProfile | None,  # type: ignore[no-untyped-def]
            eng: OfficerProfile | None, doctor: OfficerProfile | None) -> None:
    """What has changed on our own ship: the shields' tuning, plasma vented, stand-ins, sickbay."""
    tuner = b.find(s.duty_by) if s.duty_by else sci
    if s.duty == "shields" and talk.tuning == "":
        talk.tuning = "started"
        say(tuner, "tune_start", "Tuning our shield harmonics against their weapons.")
    elif s.duty == "shields" and talk.tuning == "started" and s.tuning >= 0.999:
        talk.tuning = "done"
        say(tuner, "tune_done", "Our shields are tuned against them, Captain.")
    elif s.duty != "shields" and talk.tuning == "started":
        talk.tuning = ""
    if obs.leaking(s.id) and _fresh(talk, "plasma", obs, LEAK_GAP):
        bad = next((i + 1 for i, d in enumerate(s.drives) if not d.destroyed and d.damage >= 25), 1)
        say(eng, "plasma", "We're venting plasma from warp drive {n}. Anyone can follow it, cloak or no cloak. "
            "Repair it, or drop below warp 1.", n=bad)
    covering = b.crew.covering
    for station, sub, regular in covering[talk.covered:]:
        if regular is not None and sub is not regular:
            say(sub, "cover", "I have {station}, Captain.", station=station)
    talk.covered = len(covering)
    wounded = frozenset(s.wounded)
    if wounded - talk.wounded:
        say(doctor, "wounded", "I have {who} in sickbay.", who=_names(b, sorted(wounded - talk.wounded)))
    elif talk.wounded - wounded:
        say(doctor, "mended", "{who} are back on duty.", who=_names(b, sorted(talk.wounded - wounded)))
    talk.wounded = wounded


__all__ = ["HiveTalk", "hive_remarks"]
