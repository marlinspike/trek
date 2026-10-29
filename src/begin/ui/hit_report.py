"""One plain line per target summing up what your weapons just did to it.

Hits on a heavily shielded ship mostly drain a shield, which is easy to miss
on the map, so the log says so: "Hits on Wraith: 8, all absorbed by shield 1
(now 87%)." Hits are gathered for a cycle after the last one, then reported.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..sim.events import Event, HullHit, ShieldHit, SubsystemDamaged


@dataclass
class _Tally:
    last_tick: int
    hits: int = 0
    shields: dict[int, float] = field(default_factory=dict)   # sector -> strength afterwards
    collapsed: list[int] = field(default_factory=list)
    hull: float = 0.0
    systems: list[str] = field(default_factory=list)


@dataclass
class HitReport:
    attacker: int | None
    tallies: dict[int, _Tally] = field(default_factory=dict)

    def ingest(self, events: list[Event], tick: int) -> None:
        hit_now: set[int] = set()
        for ev in events:
            if isinstance(ev, ShieldHit) and ev.attacker == self.attacker and ev.attacker is not None:
                t = self.tallies.setdefault(ev.ship_id, _Tally(tick))
                t.hits += 1
                t.last_tick = tick
                t.shields[ev.sector] = ev.strength
                if ev.collapsed:
                    t.collapsed.append(ev.sector)
                hit_now.add(ev.ship_id)
            elif isinstance(ev, HullHit) and ev.attacker == self.attacker and ev.attacker is not None:
                t = self.tallies.setdefault(ev.ship_id, _Tally(tick))
                if ev.ship_id not in hit_now:
                    t.hits += 1   # straight to the hull (shield down or facing a gap)
                t.last_tick = tick
                t.hull += ev.amount
                hit_now.add(ev.ship_id)
            elif isinstance(ev, SubsystemDamaged) and ev.ship_id in hit_now:
                t = self.tallies[ev.ship_id]
                t.systems.append(ev.label + (" destroyed" if ev.destroyed else ""))

    def due(self, tick: int, ticks_per_cycle: int, names: dict[int, str]) -> list[str]:
        """Lines for targets that have had a quiet cycle since their last hit."""
        out: list[str] = []
        for sid, t in list(self.tallies.items()):
            if tick - t.last_tick < ticks_per_cycle:
                continue
            del self.tallies[sid]
            out.append(_line(names.get(sid, f"#{sid}"), t))
        return out


def _line(name: str, t: _Tally) -> str:
    bits: list[str] = []
    shields = ", ".join(f"shield {k + 1} now {v:.0f}%" for k, v in sorted(t.shields.items()))
    if t.hull <= 0 and shields:
        bits.append(f"all absorbed ({shields})")
    elif shields:
        bits.append(shields)
    for k in dict.fromkeys(t.collapsed):
        bits.append(f"shield {k + 1} collapsed")
    if t.hull > 0:
        bits.append(f"{t.hull:.0f} damage to the hull")
    if t.systems:
        bits.append(", ".join(dict.fromkeys(t.systems)) + " hit")
    return f"Hits on {name}: {t.hits}, " + "; ".join(bits) + "."


__all__ = ["HitReport"]
