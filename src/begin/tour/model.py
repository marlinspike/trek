"""A tour of duty as written in TOML: the patrol, its stops, briefings, choices and waves [E].

Shipped tours live in `content/data/tours.toml`; your own go in `config/tours/*.toml`
in the same format (a tour with the same id as a shipped one replaces it):

    [[tour]]
    id = "border-patrol"
    title = "Border Patrol"
    flagship = "federation.dn"          # optional: the faction's default, a Dreadnought for the Federation
    budget = 300                       # fleet points for escorts (a class costs its mass)
    reinforcement_calls = 2
    reinforcements = ["federation.hc", "federation.de"]
    resupply = 0.5                     # share of a full magazine a supply ship brings between stops

    [[tour.stop]]
    id = "raiders"
    title = "Orion raiders"
    system = "Tau Ceti"
    chart = [0.2, 0.7]                 # where it sits on the patrol chart, 0..1 across and down
    transit = 150                      # cycles of travel to get here: field repairs happen on the way
    eta = 120                          # cycles for Starfleet's reinforcements to reach this stop
    officer = "seven"                  # who gives the briefing
    briefing = "Two Orion raiders..."
    enemies = ["orion.an", "orion.ra"]

    [[tour.stop.choice]]               # decided in the Ready Room before this stop
    label = "Refit at the starbase"
    consequence = "A full refit, but the Klingons have time to bring another battle cruiser."
    refit = true
    transit = 300
    flags = ["refit"]

    [[tour.stop.wave]]                 # later waves of attackers (the first is `enemies`)
    ships = ["klingon.bc"]
    after_clear = 60
    if_flag = "refit"                  # only if a choice set this flag (or `unless_flag`)

A stop can also set `win_flag` (a flag set when you win it), list friendly ships already
there (`friends`, e.g. the starbase), drop enemies when a flag is set
(`[tour.stop.drop] dreadnought-beaten = ["klingon.dr"]`) or add them
(`[tour.stop.add] refit = ["klingon.bc"]`).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from ..battle import PLAYER_FLAGSHIP_CLASSES

try:
    import tomllib
except ModuleNotFoundError:  # Python 3.10
    import tomli as tomllib  # type: ignore[no-redef]

TOURS_FILE = Path(__file__).resolve().parent.parent / "content" / "data" / "tours.toml"


@dataclass(frozen=True)
class Choice:
    label: str
    consequence: str
    refit: bool = False                 # put in at the starbase: hull, systems, crew and magazines made good
    transit: float | None = None        # cycles of travel instead of the stop's own (a detour)
    flags: tuple[str, ...] = ()


@dataclass(frozen=True)
class WaveDef:
    ships: tuple[str, ...]
    after_clear: float | None = None
    at: float | None = None
    center: tuple[float, float] = (0.0, 16000.0)
    message: str = ""
    if_flag: str = ""
    unless_flag: str = ""


@dataclass(frozen=True)
class Stop:
    id: str
    title: str
    system: str
    chart: tuple[float, float]
    briefing: str
    enemies: tuple[str, ...]
    officer: str = "spock"
    transit: float = 150.0
    eta: float = 120.0
    friends: tuple[str, ...] = ()       # friendly ships already on the field (a starbase), not in your squadron
    enemy_center: tuple[float, float] = (0.0, 12000.0)
    player_center: tuple[float, float] = (0.0, -11000.0)
    friends_center: tuple[float, float] = (0.0, -4000.0)
    choices: tuple[Choice, ...] = ()
    waves: tuple[WaveDef, ...] = ()
    win_flag: str = ""
    add: dict[str, tuple[str, ...]] = field(default_factory=dict)    # flag -> extra enemies
    drop: dict[str, tuple[str, ...]] = field(default_factory=dict)   # flag -> enemies that don't come
    finale: bool = False                # losing the friends here (the starbase) loses the tour
    seed: int = 1

    def enemy_ships(self, flags: set[str]) -> list[str]:
        ships = list(self.enemies)
        for flag, extra in self.add.items():
            if flag in flags:
                ships.extend(extra)
        for flag, gone in self.drop.items():
            if flag in flags:
                for cid in gone:
                    if cid in ships:
                        ships.remove(cid)
        return ships

    def active_waves(self, flags: set[str]) -> list[WaveDef]:
        return [w for w in self.waves if (not w.if_flag or w.if_flag in flags) and
                (not w.unless_flag or w.unless_flag not in flags)]


@dataclass(frozen=True)
class TourDef:
    id: str
    title: str
    description: str
    flagship: str
    stops: tuple[Stop, ...]
    faction: str = "federation"
    budget: int = 300
    reinforcement_calls: int = 2
    reinforcements: tuple[str, ...] = ()
    starbase: str = "Starbase 12"
    sector: str = ""
    resupply: float = 0.5               # share of a full magazine a supply run restores between stops
    source: str = "shipped"             # or the file it came from


def _pair(v: Any, default: tuple[float, float]) -> tuple[float, float]:
    if isinstance(v, (list, tuple)) and len(v) == 2:
        return float(v[0]), float(v[1])
    return default


def _flags(v: Any) -> tuple[str, ...]:
    if isinstance(v, str):
        return (v,)
    return tuple(str(x) for x in v or ())


def _ships(v: Any) -> dict[str, tuple[str, ...]]:
    return {str(k): tuple(str(c) for c in cs) for k, cs in (v or {}).items()}


def parse_tour(t: dict[str, Any], source: str = "shipped") -> TourDef:
    stops = []
    for i, s in enumerate(t.get("stop", [])):
        choices = tuple(Choice(str(c["label"]), str(c.get("consequence", "")), bool(c.get("refit", False)),
                               float(c["transit"]) if "transit" in c else None, _flags(c.get("flags")))
                        for c in s.get("choice", []))
        waves = tuple(WaveDef(tuple(w["ships"]), float(w["after_clear"]) if "after_clear" in w else None,
                              float(w["at"]) if "at" in w else None, _pair(w.get("center"), (0.0, 16000.0)),
                              str(w.get("message", "")), str(w.get("if_flag", "")), str(w.get("unless_flag", "")))
                      for w in s.get("wave", []))
        stops.append(Stop(
            id=str(s["id"]), title=str(s["title"]), system=str(s.get("system", s["title"])),
            chart=_pair(s.get("chart"), (0.1 + 0.8 * i / max(1, len(t.get("stop", [])) - 1), 0.5)),
            briefing=str(s.get("briefing", "")).strip(), enemies=tuple(s.get("enemies", ())),
            officer=str(s.get("officer", "spock")), transit=float(s.get("transit", 150.0)), eta=float(s.get("eta", 120.0)),
            friends=tuple(s.get("friends", ())), enemy_center=_pair(s.get("enemy_center"), (0.0, 12000.0)),
            player_center=_pair(s.get("player_center"), (0.0, -11000.0)),
            friends_center=_pair(s.get("friends_center"), (0.0, -4000.0)),
            choices=choices, waves=waves, win_flag=str(s.get("win_flag", "")),
            add=_ships(s.get("add")), drop=_ships(s.get("drop")), finale=bool(s.get("finale", False)),
            seed=int(s.get("seed", 1000 + i)),
        ))
    return TourDef(
        id=str(t["id"]), title=str(t["title"]), description=str(t.get("description", "")).strip(),
        flagship=str(t.get("flagship") or PLAYER_FLAGSHIP_CLASSES.get(str(t.get("faction", "federation")), "")), stops=tuple(stops), faction=str(t.get("faction", "federation")),
        budget=int(t.get("budget", 300)), reinforcement_calls=int(t.get("reinforcement_calls", 2)),
        reinforcements=tuple(t.get("reinforcements", ())), starbase=str(t.get("starbase", "Starbase 12")),
        sector=str(t.get("sector", "")), resupply=float(t.get("resupply", 0.5)), source=source,
    )


def load_tours(user_dir: Path | None = None, path: Path = TOURS_FILE) -> tuple[list[TourDef], list[str]]:
    """Shipped tours, then the player's own from `<config>/tours/*.toml`. Returns the tours and any problems."""
    with open(path, "rb") as fh:
        tours = {t["id"]: parse_tour(t) for t in tomllib.load(fh).get("tour", [])}
    problems: list[str] = []
    if user_dir is not None and user_dir.is_dir():
        for f in sorted(user_dir.glob("*.toml")):
            try:
                for t in tomllib.loads(f.read_text()).get("tour", []):
                    tours[str(t["id"])] = parse_tour(t, source=f.name)
            except (OSError, ValueError, KeyError, TypeError) as e:
                problems.append(f"{f.name}: {e}")
    return list(tours.values()), problems


def check_tour(tour: TourDef, classes: set[str]) -> list[str]:
    """Problems with a tour's ship classes, so a typo in a hand-written tour is reported, not crashed on."""
    out = []
    names = [tour.flagship, *tour.reinforcements]
    for s in tour.stops:
        names += [*s.enemies, *s.friends, *(c for w in s.waves for c in w.ships),
                  *(c for v in s.add.values() for c in v)]
    for cid in names:
        if cid not in classes:
            out.append(f"{tour.title}: unknown ship class '{cid}'")
    if not tour.stops:
        out.append(f"{tour.title}: no stops")
    return out


__all__ = ["Choice", "Stop", "TourDef", "WaveDef", "check_tour", "load_tours", "parse_tour"]
