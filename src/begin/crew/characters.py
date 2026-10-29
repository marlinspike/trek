"""Bridge officers as characters: who they are, how they talk, and how they feel about the captain.

Profiles come from `content/data/officers.toml` (hand editable). Each officer
has a station, AI personality overrides, offline lines for in-battle chatter,
and a persona brief used when an LLM provider is configured.

A `Relationship` tracks rapport with the captain across battles. It moves a
little with every exchange (praise, rudeness, advice taken) and is saved in
the user settings, so later systems (negotiations, morale) can read it.

It never appears in menus, help pages or normal play, and it is kept
non-explicit at every level.
"""

from __future__ import annotations

import os
import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from ..content.loader import DATA_DIR, _read

STATIONS = ("helm", "tactical", "engineering", "science")


@dataclass(frozen=True, eq=False)  # compared and hashed by identity: one profile per officer
class OfficerProfile:
    id: str
    name: str
    rank: str
    station: str
    advises: tuple[str, ...]
    aliases: tuple[str, ...]
    personality: dict[str, float]
    persona: str
    lines: dict[str, tuple[str, ...]]

    @property
    def title(self) -> str:
        return f"{self.rank} {self.name}" if self.rank else self.name

    def line(self, event: str, rng: random.Random, **fill: object) -> str | None:
        options = self.lines.get(event)
        if not options:
            return None
        text = rng.choice(options)
        for k, v in fill.items():
            text = text.replace("{" + k + "}", str(v))
        return text


def load_officers(data_dir: Path = DATA_DIR) -> dict[str, OfficerProfile]:
    raw: list[dict[str, Any]] = _read("officers.toml", data_dir).get("officer", [])
    out: dict[str, OfficerProfile] = {}
    for o in raw:
        station = o["station"]
        if station not in STATIONS:
            raise ValueError(f"Officer {o['id']}: unknown station '{station}'.")
        out[o["id"]] = OfficerProfile(
            id=o["id"], name=o["name"], rank=o.get("rank", ""), station=station,
            advises=tuple(o.get("advises", [station])),
            aliases=tuple(a.lower() for a in o.get("aliases", [o["id"]])),
            personality={k: float(v) for k, v in o.get("personality", {}).items()},
            persona=" ".join(o.get("persona", "").split()),
            lines={k: tuple(v) for k, v in o.get("lines", {}).items()},
        )
    return out


@dataclass
class Relationship:
    """Rapport between the captain and one officer, from -1 (resentful) to +1 (devoted)."""

    rapport: float = 0.0
    exchanges: int = 0
    advice_taken: int = 0

    def nudge(self, amount: float) -> None:
        self.rapport = max(-1.0, min(1.0, self.rapport + amount))

    def negotiation_modifier(self) -> float:
        """How much this officer's goodwill helps in talks the captain leads (−0.15 to +0.15)."""
        return 0.15 * self.rapport

    @property
    def mood(self) -> str:
        r = self.rapport
        return ("devoted" if r > 0.6 else "warm" if r > 0.25 else "professional" if r > -0.25
                else "cool" if r > -0.6 else "resentful")


@dataclass
class Relationships:
    by_officer: dict[str, Relationship] = field(default_factory=dict)

    def get(self, officer_id: str) -> Relationship:
        return self.by_officer.setdefault(officer_id, Relationship())

    @staticmethod
    def from_settings(hidden: dict[str, object]) -> Relationships:
        raw = hidden.get("rapport", {})
        out = Relationships()
        if isinstance(raw, dict):
            for k, v in raw.items():
                if isinstance(v, dict):
                    out.by_officer[str(k)] = Relationship(float(v.get("rapport", 0.0)), int(v.get("exchanges", 0)),
                                                          int(v.get("advice_taken", 0)))
        return out

    def to_settings(self, hidden: dict[str, object]) -> None:
        hidden["rapport"] = {k: {"rapport": round(r.rapport, 4), "exchanges": r.exchanges, "advice_taken": r.advice_taken}
                             for k, r in self.by_officer.items()}

__all__ = [ "OfficerProfile", "Relationship", "Relationships", "STATIONS", "load_officers",
]
