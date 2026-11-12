"""Bridge officers as characters: who they are, how they talk, and how they feel about the captain.

Profiles come from `content/data/officers.toml` (hand editable). Each officer
has a station, AI personality overrides, offline lines for in-battle chatter,
and a persona brief used when an LLM provider is configured.

A `Relationship` tracks rapport with the captain across battles. It moves a
little with every exchange (praise, rudeness, advice taken) and is saved in
the user settings, so later systems (negotiations, morale) can read it.

Each officer also has a few free-text **traits** ("dry wit", "coolly
confident"). With a language model they colour how the officer talks, never
how well they do the job. The shipped traits are in officers.toml; the
player's own, in `config/officers.toml`, replace them officer by officer:

    [seven]
    traits = ["highly effective", "coolly confident", "ex-Borg precision"]
    response_style = "factual, crisp, coolly confident"

A **response style** says how the officer answers when a model writes their
words: length, tone, register. The game passes the player's traits and
response styles to their model as written.

The player's file can reshape an officer completely, any part of them [E]: a
new `name` and `rank`, extra `aliases`, a whole new `persona`, or a
`background`, `interests` and `quirks` added to the shipped one, and their
own offline `lines` for any event (these work without a language model):

    [worf]
    interests = ["cooking for the crew", "Klingon opera"]
    quirks = ["judges every battle as if it were a meal"]
    [worf.lines]
    idle = ["The galley has gagh tonight. It is... adequate. I will improve it."]

`idle` lines are said in quiet moments, when no enemy is in sight.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import tomllib

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
    traits: tuple[str, ...] = ()
    response_style: str = ""       # how they answer, for the language model ("terse, clipped reports")
    rapport_floor: float = -1.0    # the lowest their rapport can fall (-1: no floor); set in config/officers.toml
    background: str = ""           # who they are beyond the station, for the language model [E]
    interests: tuple[str, ...] = ()   # what they care about off duty; shows in quiet moments [E]
    quirks: tuple[str, ...] = ()      # habits of speech or manner [E]

    def brief(self) -> str:
        """Who they are, for a language model: the persona and whatever the player added to it."""
        out = self.persona
        if self.background:
            out += " Your background: " + self.background + ("" if self.background[-1] in ".!?" else ".")
        if self.interests:
            out += (f" Off duty you care about: {', '.join(self.interests)}. It shows in how you talk, most of all "
                    "in quiet moments.")
        if self.quirks:
            out += f" Your quirks: {'; '.join(self.quirks)}."
        return out

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


def read_traits(path: Path) -> dict[str, tuple[str, ...]]:
    """The player's own officer traits (`[<officer id>] traits = [...]`); empty when there is no file."""
    try:
        raw = tomllib.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    out: dict[str, tuple[str, ...]] = {}
    for oid, v in raw.items():
        traits = v.get("traits") if isinstance(v, dict) else None
        if isinstance(traits, list):
            out[str(oid).lower()] = tuple(str(t).strip() for t in traits if str(t).strip())
        elif isinstance(traits, str):
            out[str(oid).lower()] = tuple(t.strip() for t in traits.split(",") if t.strip())
    return out


def read_response_styles(path: Path) -> dict[str, str]:
    """The player's own response styles (`[<officer id>] response_style = "..."`); empty when there is no file."""
    try:
        raw = tomllib.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {str(oid).lower(): " ".join(str(v["response_style"]).split())
            for oid, v in raw.items() if isinstance(v, dict) and isinstance(v.get("response_style"), str)}


def read_rapport_floors(path: Path) -> dict[str, float]:
    """The player's own rapport floors (`[<officer id>] rapport_floor = 0.5`, -1 to 1); empty when there is none."""
    try:
        raw = tomllib.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    return {str(oid).lower(): max(-1.0, min(1.0, float(v["rapport_floor"])))
            for oid, v in raw.items() if isinstance(v, dict) and isinstance(v.get("rapport_floor"), (int, float))}


def _words(v: object) -> tuple[str, ...]:
    """A list of short phrases, or one comma-separated string of them."""
    if isinstance(v, list):
        return tuple(str(t).strip() for t in v if str(t).strip())
    if isinstance(v, str):
        return tuple(t.strip() for t in v.split(",") if t.strip())
    return ()


def _text(v: object) -> str:
    return " ".join(str(v).split()) if isinstance(v, str) else ""


def read_characters(path: Path) -> dict[str, dict[str, Any]]:
    """Everything the player's file says about each officer (`[<officer id>] ...`), checked and tidied;
    empty when there is no file. Unknown keys and values of the wrong kind are ignored, never fatal."""
    try:
        raw = tomllib.loads(path.read_text())
    except (OSError, ValueError):
        return {}
    out: dict[str, dict[str, Any]] = {}
    for oid, v in raw.items():
        if not isinstance(v, dict):
            continue
        c: dict[str, Any] = {}
        for key in ("name", "rank", "persona", "background", "response_style"):
            if isinstance(v.get(key), str) and (key == "rank" or _text(v[key])):
                c[key] = _text(v[key])
        for key in ("traits", "interests", "quirks", "aliases"):
            if key in v and isinstance(v[key], (list, str)):
                c[key] = _words(v[key])
        if isinstance(v.get("rapport_floor"), (int, float)):
            c["rapport_floor"] = max(-1.0, min(1.0, float(v["rapport_floor"])))
        if isinstance(v.get("lines"), dict):
            c["lines"] = {str(ev): tuple(str(x) for x in (ls if isinstance(ls, list) else [ls]) if str(x).strip())
                          for ev, ls in v["lines"].items() if isinstance(ls, (list, str))}
        out[str(oid).lower()] = c
    return out


def load_officers(data_dir: Path = DATA_DIR, traits_file: Path | None = None) -> dict[str, OfficerProfile]:
    """The bridge officers; `traits_file` (config/officers.toml) reshapes them officer by officer: anything it
    gives (name, rank, persona, background, traits, interests, quirks, response style, lines) wins."""
    raw: list[dict[str, Any]] = _read("officers.toml", data_dir).get("officer", [])
    mine = read_characters(traits_file) if traits_file is not None else {}
    out: dict[str, OfficerProfile] = {}
    for o in raw:
        station = o["station"]
        if station not in STATIONS:
            raise ValueError(f"Officer {o['id']}: unknown station '{station}'.")
        m = mine.get(o["id"], {})
        name = m.get("name") or o["name"]
        aliases = [a.lower() for a in o.get("aliases", [o["id"]])] + [a.lower() for a in m.get("aliases", ())]
        if name != o["name"]:                      # a renamed officer answers to her new name too
            aliases += [name.lower(), name.split()[0].lower()]
        lines = {k: tuple(v) for k, v in o.get("lines", {}).items()}
        lines.update({k: v for k, v in m.get("lines", {}).items() if v})
        out[o["id"]] = OfficerProfile(
            id=o["id"], name=name, rank=m.get("rank", o.get("rank", "")), station=station,
            advises=tuple(o.get("advises", [station])),
            aliases=tuple(dict.fromkeys(aliases)),
            personality={k: float(v) for k, v in o.get("personality", {}).items()},
            persona=m.get("persona") or " ".join(o.get("persona", "").split()),
            lines=lines,
            traits=m.get("traits", tuple(str(t) for t in o.get("traits", []))),
            response_style=m.get("response_style", " ".join(str(o.get("response_style", "")).split())),
            rapport_floor=m.get("rapport_floor", float(o.get("rapport_floor", -1.0))),
            background=m.get("background", _text(o.get("background", ""))),
            interests=m.get("interests", _words(o.get("interests", []))),
            quirks=m.get("quirks", _words(o.get("quirks", []))),
        )
    return out


@dataclass
class Relationship:
    """Rapport between the captain and one officer, from -1 (resentful) to +1 (devoted)."""

    rapport: float = 0.0
    exchanges: int = 0
    advice_taken: int = 0
    floor: float = -1.0           # the lowest this officer's rapport can go (an officer's `rapport_floor`)

    def nudge(self, amount: float) -> None:
        self.rapport = max(self.floor, min(1.0, self.rapport + amount))

    def hold_at_least(self, floor: float) -> None:
        self.floor = max(-1.0, min(1.0, floor))
        self.rapport = max(self.rapport, self.floor)

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


__all__ = [
    "OfficerProfile", "Relationship", "Relationships", "STATIONS", "load_officers", "read_characters", "read_response_styles",
    "read_traits",
]
