"""Who is in command: the separately modelled dimensions of an AI ship.

Begin rolled one personality per captain from the nation's dogma
(`clamp01(value ± uniform(deviation))`) [R]. We keep that and add the
dimensions the remake models separately [E]:

* computer sophistication lives on the ship (faction hardware), not here;
* captain competence: reading the situation, timing, using the right tool;
* crew competence: how quickly orders are carried out (decision latency);
* aggression and risk, courage (bravery) and discipline;
* creativity: willingness to try unusual moves (probes, subsystem shots);
* loyalty: how readily an ally follows the flagship's orders;
* doctrine: the faction playbook (weapon bias, focus fire, surrender);
* fanaticism: last-stand behaviour.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..content.schema import Doctrine, Faction
from ..core.rng import Rng


def _clamp01(x: float) -> float:
    return max(0.0, min(1.0, x))


@dataclass(frozen=True)
class Personality:
    aggression: float
    bravery: float
    loyalty: float
    fanaticism: float
    boarding: float
    competence: float
    crew_competence: float
    discipline: float
    creativity: float
    doctrine: Doctrine

    @property
    def reaction_ticks(self) -> int:
        """Ticks between tactical decisions: better crews act on orders faster."""
        return int(round(4 + (1.0 - self.crew_competence) * 8))

    @staticmethod
    def roll(faction: Faction, rng: Rng, overrides: dict[str, float] | None = None) -> Personality:
        d = faction.dogma
        dev = d.deviation
        cm = faction.captains

        def vary(v: float, spread: float) -> float:
            return _clamp01(v + rng.uniform(-spread, spread))

        p = dict(
            aggression=vary(d.aggression, dev),
            bravery=vary(d.bravery, dev),
            loyalty=max(0.0, d.loyalty + rng.uniform(-dev, dev)),
            fanaticism=vary(d.fanaticism, dev),
            boarding=d.boarding,
            competence=_clamp01(rng.gauss(cm.competence, cm.competence_dev)),
            crew_competence=_clamp01(rng.gauss(cm.competence, cm.competence_dev)),
            discipline=vary(cm.discipline, cm.deviation),
            creativity=vary(cm.creativity, cm.deviation),
        )
        if overrides:
            p.update({k: v for k, v in overrides.items() if k in p})
        return Personality(doctrine=faction.doctrine, **p)  # type: ignore[arg-type]


__all__ = ["Personality"]
