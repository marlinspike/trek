"""Officers commenting on the battle as it happens: callouts, damage and repair reports, morale, objectives."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Iterable

from ..console.reports import morale_words
from ..core.angles import bearing
from ..help.coach import HelpContext
from ..sim.events import (
    ContactChanged, Event, HullHit, MoraleShift, ObjectiveEnded, PhaserFired, ProjectCompleted, ScanCompleted, ShipStatusChanged,
    SubsystemRepaired, TorpedoLaunched,
)
from ..sim.objectives import DISABLE_GROUPS
from ..sim.observation import Observation
from ..sim.ship import HULL, KIND_LABEL, Kind, Ship
from . import collaborations
from .characters import OfficerProfile
from .station_reports import contact_name
from .utterance import Utterance

if TYPE_CHECKING:
    from .conversation import Bridge


# steps worth saying aloud as they start, how long each must last first (seconds), and the gap between callouts
CALLOUT_KINDS = ("evade", "close", "open", "fight", "bait", "salvo", "between", "phasers", "hunt")
CALLOUT_SETTLE = {"evade": 0.0, "bait": 0.0, "salvo": 0.0, "between": 0.0, "close": 2.0, "open": 2.0, "fight": 2.0}
CALLOUT_GAP = 4.0
CALLOUT_REPEAT = {"bait": 20.0, "salvo": 20.0, "between": 20.0, "phasers": 30.0, "close": 10.0, "open": 10.0,
                  "fight": 15.0, "hunt": 20.0, "evade": 5.0}   # seconds before the same kind of step is said again
MORALE_GAP = 20.0           # seconds between remarks on the crew's spirits
REPAIR_REPORT_DAMAGE = 25   # % damage before a system is worth reporting
REPAIR_GAP = 12.0           # seconds between repair reports

MORALE_CAUSES = {
    ("damage", False): " after that damage", ("loss", False): " after losing a ship", ("shield", False): "",
    ("hits", True): " with every hit we land", ("kill", True): " after that kill", ("repairs", True): " as repairs come in",
    ("address", True): " after your words",
}


class Chatter:
    """The officers' running commentary on the battle, mixed into `Bridge`."""

    def react(self: Bridge, events: Iterable[Event], ctx: HelpContext) -> list[Utterance]:
        """Officers comment on what just happened (rate limited)."""
        s, obs = ctx.ship, ctx.obs
        if s is None or obs is None:
            return []
        for c in obs.contacts().values():
            if c.identified:
                self._names[c.id] = contact_name(obs, c.id)
        out = self._objective_reports(events, s, obs)   # asked-for work is always reported
        out.extend(self._callouts(s, obs))
        out.extend(self._repair_reports(s, obs))
        out.extend(self._morale_remarks(events, s, obs))
        if not self.chatter:
            return out
        commander = self.find(s.conn) if s.conn else None
        if commander is not None and s.target is not None and s.target != self._conn_target:
            self._maybe(out, obs, "", "bridge_target", 1.0, gap=4.0, officer=commander, target=contact_name(obs, s.target))
        self._conn_target = s.target if commander is not None else None
        for ev in events:
            self._event_remark(ev, s, obs, commander, out)
        self._warnings(s, obs, out)
        return out

    def _event_remark(self: Bridge, ev: Event, s: Ship, obs: Observation, commander: OfficerProfile | None,
                      out: list[Utterance]) -> None:
        """An officer's remark on one event, if it is worth one."""
        if isinstance(ev, ProjectCompleted) and ev.ship_id == s.id:
            collab = collaborations.for_project(ev.project)
            if collab is not None and (ev.tube is not None or "{tube}" not in str(collab.done)):
                out.extend(self._chorus(collab.done, tube=(ev.tube or 0) + 1))
                self._last_any = obs.tick
        elif isinstance(ev, (TorpedoLaunched, PhaserFired)) and ev.ship_id == s.id and s.objectives:
            pass       # the officer working the objective says what she is firing and why
        elif isinstance(ev, TorpedoLaunched) and ev.ship_id == s.id and commander is not None:
            self._maybe(out, obs, "", "bridge_torpedoes", 0.5, officer=commander)
        elif isinstance(ev, TorpedoLaunched) and ev.ship_id == s.id and "tactical" in s.delegated:
            self._maybe(out, obs, "tactical", "torpedoes", 0.6)
        elif isinstance(ev, PhaserFired) and ev.ship_id == s.id and "tactical" in s.delegated:
            self._maybe(out, obs, "tactical", "phasers", 0.15)
        elif isinstance(ev, ShipStatusChanged) and ev.status == "destroyed":
            c = obs.contact(ev.ship_id)
            if c is not None and not (c.side is not None and c.side == s.side):
                self._maybe(out, obs, "tactical", "enemy_destroyed", 0.9, target=contact_name(obs, ev.ship_id))
        elif isinstance(ev, HullHit) and ev.ship_id == s.id and s.structure > 0:
            band = int(4 * max(0.0, s.structure) / max(1.0, s.structure_max))
            if band < self._hull_band:
                self._hull_band = band
                self._maybe(out, obs, "engineering", "hull", 1.0,
                            n=round(100 * max(0.0, s.structure) / max(1.0, s.structure_max)))
        elif isinstance(ev, ContactChanged) and ev.side == s.side and ev.acquired:
            c = obs.contact(ev.ship_id)
            if c is not None and c.visible:
                self._maybe(out, obs, "science", "contact", 0.5, target=contact_name(obs, ev.ship_id))
        elif isinstance(ev, ContactChanged) and ev.side == s.side and not ev.acquired:
            # the science officer gives the last fix, so the captain knows where to look
            c = obs.contact(ev.ship_id)
            if c is not None and not c.visible and not c.cloaked_hint:
                self._maybe(out, obs, "science", "lost", 1.0, gap=4.0, target=contact_name(obs, ev.ship_id),
                            bearing=f"{bearing(c.x - s.x, c.y - s.y):.0f}",
                            range=f"{math.hypot(c.x - s.x, c.y - s.y):,.0f}",
                            heading=f"{c.course:.0f}", warp=f"{c.warp:.1f}")
        elif isinstance(ev, ScanCompleted) and ev.ship_id == s.id:
            self._maybe(out, obs, "science", "scan", 0.7, target=contact_name(obs, ev.target_id))
        elif isinstance(ev, SubsystemRepaired) and ev.ship_id == s.id:
            self._maybe(out, obs, "engineering", "repaired", 0.3, n=ev.label)

    def _warnings(self: Bridge, s: Ship, obs: Observation, out: list[Utterance]) -> None:
        """Incoming fire (when the captain is flying) and hot engines."""
        threats = len([o for o in obs.threats() if math.hypot(o.x - s.x, o.y - s.y) < 8000])
        if threats > self._threats and "helm" not in s.delegated and not s.evasive:
            self._maybe(out, obs, "helm", "incoming", 0.5)   # advice: with an officer at the helm, they just dodge
        self._threats = threats
        temp = max((d.temp for d in s.drives if not d.destroyed), default=0.0)
        if temp > obs.rules.temp_limit * 0.85:
            self._maybe(out, obs, "engineering", "hot", 1.0, gap=20.0)

    def _callouts(self: Bridge, s: Ship, obs: Observation) -> list[Utterance]:
        """Officers flying the ship or working an objective say what they're doing as they start each step
        [E], so the captain can follow it: "Evading two torpedoes, coming to 270 warp 6." Rate limited."""
        out: list[Utterance] = []
        tpc = obs.rules.ticks_per_cycle
        for a in self.crew.activity(obs):
            if a.kind == self._step_said.get(a.officer_id) or a.kind not in CALLOUT_KINDS:
                if a.kind not in CALLOUT_KINDS:
                    self._step_said[a.officer_id] = a.kind
                continue
            if obs.tick - a.since < CALLOUT_SETTLE.get(a.kind, 1.0) * tpc:
                continue   # wait until the step has stuck, so a helm that changes its mind doesn't chatter
            if obs.tick - self._callout_at.get(a.officer_id, -10 ** 9) < CALLOUT_GAP * tpc:
                continue
            if obs.tick - self._kind_said.get((a.officer_id, a.kind), -10 ** 9) < CALLOUT_REPEAT.get(a.kind, 0.0) * tpc:
                self._step_said[a.officer_id] = a.kind   # the same move again: once is enough for a while
                continue
            o = self.find(a.officer_id)
            if o is None:
                continue
            self._step_said[a.officer_id] = a.kind
            self._callout_at[a.officer_id] = self._kind_said[(a.officer_id, a.kind)] = obs.tick
            out.append(self._say(o, a.doing.rstrip(".") + "."))
        out.extend(self._knockouts(s, obs))
        return out

    def _morale_remarks(self: Bridge, events: Iterable[Event], s: Ship, obs: Observation) -> list[Utterance]:
        """The first officer says when the crew's spirits shift sharply (a band of 20 points)."""
        shifts = [ev for ev in events if isinstance(ev, MoraleShift) and ev.ship_id == s.id and ev.cause != "rest"]
        if not shifts or obs.tick - self._morale_said < MORALE_GAP * obs.rules.ticks_per_cycle:
            return []
        o = self.find("spock") or self.crew.officer("science")
        if o is None:
            return []
        ev = shifts[-1]
        self._morale_said = obs.tick
        word = morale_words(ev.morale)
        why = MORALE_CAUSES.get((ev.cause, ev.rising), "")
        if ev.rising:
            text = f"Morale is rising, Captain{why}: the crew is {word} ({ev.morale:.0f})."
        else:
            text = f"Captain, the crew is {word}{why} (morale {ev.morale:.0f})."
            if ev.morale < 40 and obs.tick - s.last_address >= obs.rules.morale_address_cycles * obs.rules.ticks_per_cycle:
                text += " A word from you might steady them."
        u = self._say(o, text, "crew" if ev.rising else "caution")
        if not ev.rising:
            u.commands = ["address crew "]
        return [u]

    def _repair_reports(self: Bridge, s: Ship, obs: Observation) -> list[Utterance]:
        """Spock (or the engineer) says when systems or the hull need repairs and offers to direct the crews;
        once directing them, says where he sends them. Spoken even with chatter off, like callouts."""
        tpc = obs.rules.ticks_per_cycle
        manager = self.crew.repair_officer(s)
        if manager is not None:
            prio = s.repair_priority
            if prio != self._repair_prio and obs.tick - self._repair_said >= REPAIR_GAP * tpc / 2:
                self._repair_prio = prio
                self._repair_said = obs.tick
                where = ("the hull" if prio == HULL else f"the {KIND_LABEL[prio].lower()}s" if isinstance(prio, Kind)
                         else "every damaged system")
                return [self._say(manager, f"Repair crews to {where}.")]
            return []
        self._repair_prio = s.repair_priority
        reporter = self.find("spock") or self.crew.officer("engineering")
        if reporter is None or not s.alive:
            return []
        damaged = {sub.sid: sub for sub in s.subsystems() if sub.damage >= REPAIR_REPORT_DAMAGE}
        new = [damaged[sid] for sid in damaged if sid not in self._repair_seen]
        self._repair_seen &= set(damaged)
        hull = max(0.0, s.structure) / max(1.0, s.structure_max)
        band = int(hull * 4)
        worse_hull = band < self._repair_band
        if not new and not worse_hull:
            self._repair_band = band     # repaired back up: a later drop is news again
            return []
        if obs.tick - self._repair_said < REPAIR_GAP * tpc:
            return []
        self._repair_said = obs.tick
        self._repair_seen |= {sub.sid for sub in new}
        self._repair_band = band
        parts = []
        if new:
            worst = sorted(new, key=lambda sub: -sub.damage)
            names = ", ".join(f"{sub.label.lower()} {'destroyed' if sub.destroyed else f'{sub.damage}%'}"
                              for sub in worst[:3])
            more = f" and {len(worst) - 3} more" if len(worst) > 3 else ""
            parts.append(f"{names}{more} need repairs")
        if worse_hull or hull < 0.75:
            parts.append(f"hull at {hull * 100:.0f}%")
        text = "Captain, " + "; ".join(parts) + ". Shall I direct the repair crews?"
        u = self._say(reporter, text)
        u.commands = [f"repair auto {reporter.id}"]
        return [u]

    def _knockouts(self: Bridge, s: Ship, obs: Observation) -> list[Utterance]:
        """'Wraith: 3 of 6 shields out.' as each scan shows another of the asked-for systems down."""
        from .objectives import group_state, label

        out: list[Utterance] = []
        for o in s.objectives:
            if o.goal != "disable":
                continue
            officer = (self.find(o.officer) if o.officer else None) or self.crew.officer("science")
            if officer is None:
                continue
            for t in o.targets:
                st = group_state(obs.contact(t), o.group)
                if st is None or st[0] == 0:
                    continue
                key = (o.group, t)
                if st[1] > self._knocked.get(key, 0) and st[1] < st[0] and key not in self._disabled_seen:
                    what = DISABLE_GROUPS.get(o.group, o.group)
                    out.append(self._say(officer, f"{label(obs, t, self.crew.names)}: {st[1]} of {st[0]} {what} out."))
                self._knocked[key] = st[1]
        return out

    def _objective_reports(self: Bridge, events: Iterable[Event], s: Ship, obs: Observation) -> list[Utterance]:
        out = self._objective_progress(s, obs)
        for ev in events:
            if not (isinstance(ev, ObjectiveEnded) and ev.ship_id == s.id and ev.outcome != "cancelled"):
                continue
            o = (self.find(ev.officer) if ev.officer else None) or self.crew.officer("science")
            if o is None:
                continue
            systems = DISABLE_GROUPS.get(ev.group, ev.group)
            names = ", ".join(self._names.get(t, f"#{t}") for t in ev.targets)
            if ev.outcome == "done" and ev.goal == "capture":
                out.append(self._line(o, "objective_captured", targets=names)
                           or self._say(o, f"{names} is ours, Captain. The boarding parties hold her."))
            elif ev.outcome == "done" and ev.goal == "destroy":
                out.append(self._line(o, "objective_destroyed", targets=names)
                           or self._say(o, f"{names}: destroyed, Captain."))
            elif ev.outcome == "done":
                out.append(self._line(o, "objective_done", targets=names, systems=systems)
                           or self._say(o, f"Done, Captain: {names} have lost their {systems}."))
                if ev.goal == "disable":
                    out.append(self._say(o, "Holding fire on her now. Fire on her yourself, or say 'target her hull' "
                                            "or 'destroy her', to finish her.", "dim"))
            else:
                out.append(self._line(o, "objective_failed", reason=ev.reason)
                           or self._say(o, f"I can't finish that: {ev.reason}.", "caution"))
            pl = self.crew.planners.get(o.id)
            if pl is not None and pl.tally_for[:2] == (ev.goal, ev.group):
                from .objectives import summary

                out.append(self._say(o, "That took " + summary(pl, obs.tick, obs.rules.ticks_per_cycle), "dim"))
            self._last_any = obs.tick
        return out

    def _objective_progress(self: Bridge, s: Ship, obs: Observation) -> list[Utterance]:
        """Report each enemy ship as its asked-for systems go down (judged, like the officer does, by scans)."""
        from .objectives import disabled

        out: list[Utterance] = []
        for o in s.objectives:
            if o.goal != "disable":
                continue   # a ship taken out is reported as it goes
            officer = (self.find(o.officer) if o.officer else None) or self.crew.officer("science")
            if officer is None:
                continue
            gone = obs.gone()
            for t in o.targets:
                key = (o.group, t)
                if key in self._disabled_seen or not disabled(obs.contact(t), o.group):
                    continue
                self._disabled_seen.add(key)
                left = [x for x in o.targets if x not in gone and not disabled(obs.contact(x), o.group)]
                if not left:
                    continue   # the closing report says it
                more = f"{len(left)} to go."
                systems = DISABLE_GROUPS.get(o.group, o.group)
                out.append(self._line(officer, "objective_progress", target=contact_name(obs, t), systems=systems, left=more)
                           or self._say(officer, f"{contact_name(obs, t)}'s {systems} are down. {more}"))
        return out

    def outcome(self: Bridge, won: bool | None) -> list[Utterance]:
        o = self.crew.officer("helm") or next(iter(self.crew.officers.values()), None)
        if o is None or won is None:
            return []
        u = self._line(o, "victory" if won else "defeat")
        return [u] if u else []

    def _maybe(self: Bridge, out: list[Utterance], obs: Observation, station: str, event: str, p: float,
               gap: float = 8.0, officer: OfficerProfile | None = None, **fill: object) -> None:
        o = officer or self.crew.officer(station)
        if o is None or event not in o.lines:
            return
        tpc = obs.rules.ticks_per_cycle
        if obs.tick - self._last_line.get(o.id, -10 ** 9) < gap * tpc or obs.tick - self._last_any < 3 * tpc:
            return
        if self.rng.random() > p:
            return
        u = self._line(o, event, **fill)
        if u is not None:
            self._last_line[o.id] = self._last_any = obs.tick
            if not self._voice(o, u.text, obs):
                out.append(u)


__all__ = ["Chatter"]
