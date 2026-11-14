"""Officers' proposals: "Torpedoes inbound, Captain. Evasive manoeuvres?" [E]

Now and then the officer at a station the captain is running sees something
worth doing and proposes it, as one console line. Y makes it so (the line runs
as if typed, and the officer reads it back); N belays it; it lapses after a few
seconds if the captain is busy. Proposals are rare by design:

- only for stations the captain runs (a delegated station acts for itself);
- one at a time, at most one per officer a minute (`hud proposals often`
  halves that), never the same line again soon after it was belayed;
- only from what the officer can see: the contact on sensors, our own
  shields and tubes, torpedoes on the plot. Nothing is proposed that the
  console would refuse.

`propose(...)` looks at the situation and returns the most pressing proposal,
or None. It never changes anything.
"""

from __future__ import annotations

import math
from collections.abc import Callable
from dataclasses import dataclass, field

from ..core.angles import bearing
from ..sim.observation import Observation
from ..sim.ship import Ship
from ..sim.ship import bank_bears, bank_ready
from .characters import OfficerProfile
from .helm import incoming
from .split_fire import worth_splitting

LIFE = 8.0                  # seconds a proposal waits for Y or N
URGENT_LIFE = 6.0
COOLDOWN = {"often": 30.0, "rarely": 60.0}     # cycles between one officer's proposals
GAP = {"often": 10.0, "rarely": 20.0}          # cycles between any two proposals
BELAY_MEMORY = 120.0        # cycles a belayed line is not proposed again
SHIELD_CLOSE = 15000.0      # an enemy this close with our shields down is worth a word
TORPEDO_REACH = 9000.0      # proposing torpedoes only inside this
SCAN_REACH = 20000.0
HOT_SHARE = 0.7             # drives this close to their limit (and still heating) are worth a team [E]


@dataclass
class Proposal:
    officer: str            # officer id
    name: str               # "Worf"
    station: str
    text: str               # what they say
    line: str               # the console line Y runs
    urgent: bool = False
    age: float = 0.0        # seconds shown
    bonus: float = 0.0      # extra seconds it waits (a Steady officer's, see crew/career.py)

    @property
    def life(self) -> float:
        return (URGENT_LIFE if self.urgent else LIFE) + self.bonus


def _name(obs: Observation, sid: int) -> str:
    c = obs.contact(sid)
    if c is not None and c.identified:
        return c.label.split(" (")[0]
    return f"#{sid}"


def candidates(obs: Observation, ship: Ship, officers: dict[str, OfficerProfile]) -> list[Proposal]:
    """Everything worth proposing right now, most pressing first."""
    out: list[Proposal] = []
    free = set(officers) - set(ship.delegated) if not ship.conn else set()

    def say(station: str, text: str, line: str, urgent: bool = False) -> None:
        o = officers.get(station)
        if o is not None and station in free:
            out.append(Proposal(o.id, o.name, station, text, line, urgent))

    hostile = [c for c in obs.hostile_contacts() if c.visible and c.id not in obs.gone()]
    nearest = min(hostile, key=lambda c: c.distance_to(ship.x, ship.y), default=None)
    d_near = nearest.distance_to(ship.x, ship.y) if nearest is not None else math.inf
    # helm: torpedoes on the way in
    threats = incoming(obs, ship)
    if threats and not ship.evasive:
        n = len(threats)
        say("helm", f"{'Torpedo' if n == 1 else f'{n} torpedoes'} inbound, Captain. Evasive manoeuvres?", "evasive", True)
    # engineering: shields down with an enemy close
    if ship.shields and not any(s.up for s in ship.shields) and d_near < SHIELD_CLOSE:
        say("engineering", "Our shields are down with the enemy this close. Raise them?", "raise shields all", True)
    # engineering: the shield facing the enemy is failing while another is strong
    elif nearest is not None and ship.shields and d_near < SHIELD_CLOSE and all(s.reinforced is False for s in ship.shields):
        rel = (bearing(nearest.x - ship.x, nearest.y - ship.y) - ship.course) % 360
        k = min(range(len(ship.shields)), key=lambda i: abs(((rel - ship.shields[i].facing) + 180) % 360 - 180))
        sh = ship.shields[k]
        if sh.up and sh.strength < 30 and max(s.strength for s in ship.shields) > 70:
            say("engineering", f"Shield {k + 1} is at {sh.strength:.0f}% and facing them. Reinforce it?", f"reinforce {k + 1}")
    # engineering: the drives are heating towards their limit; a team on them buys time [E]
    live = [d for d in ship.drives if not d.destroyed]
    if live and ship.engine_boost <= 0.0 and ship.crew > 0:
        hot = max(live, key=lambda d: d.temp)
        if hot.temp > obs.rules.temp_limit * HOT_SHARE and hot.temp_rate > 0.0:
            say("engineering", "The drives are running hot, Captain. Want me to put a team on them? "
                               "Other repairs will slow.", "boost")
    tgt = obs.contact(ship.target) if ship.target is not None else None
    if tgt is not None and (not tgt.visible or tgt.id in obs.gone()):
        tgt = None
    if not ship.hold_fire:
        # tactical: no target while an enemy is in sight
        if tgt is None and nearest is not None:
            say("tactical", f"The {_name(obs, nearest.id)} is the closest, Captain. Target her?", f"target {_name(obs, nearest.id)}")
        elif tgt is not None and not any(o.goal == "engage" for o in ship.objectives) and \
                (pair := worth_splitting(obs, ship)) is not None:
            a, b = (_name(obs, i) for i in pair)
            say("tactical", f"The {a} and the {b} are both in reach, Captain. Divide our fire between them?",
                f"engage {a} and {b}")
        elif tgt is not None:
            d = tgt.distance_to(ship.x, ship.y)
            brg = bearing(tgt.x - ship.x, tgt.y - ship.y)
            ready = [b for b in ship.banks if b.enabled and bank_bears(ship, b, brg) and bank_ready(ship, b)]
            loaded = [t for t in ship.tubes if t.enabled and t.loaded is not None]
            name = _name(obs, tgt.id)
            if d <= ship.cls.banks_range and len(ready) >= max(2, len(ship.banks) // 2):
                say("tactical", f"{len(ready)} phasers bear on the {name} and she's in range. Fire?",
                    f"fire all phasers at {name}")
            elif d <= TORPEDO_REACH and len(loaded) >= max(2, len(ship.tubes) // 2):
                say("tactical", f"{len(loaded)} tubes loaded and the {name} is {d:,.0f} out. Torpedoes?",
                    f"fire all torpedoes at {name}")
    # science: an enemy close by that we haven't scanned
    for c in sorted(hostile, key=lambda c: c.distance_to(ship.x, ship.y)):
        if c.scan is None and c.distance_to(ship.x, ship.y) < SCAN_REACH and c.identified:
            say("science", f"We know nothing of the {_name(obs, c.id)}'s condition. Scan her?", f"scan {_name(obs, c.id)}")
            break
    out.sort(key=lambda p: not p.urgent)
    return out


@dataclass
class Proposer:
    """Paces proposals: one at a time, an officer at most once a minute, belayed lines kept quiet."""

    last_by: dict[str, float] = field(default_factory=dict)
    last_any: float = -1e9
    belayed: dict[str, float] = field(default_factory=dict)

    def next(self, obs: Observation, ship: Ship, officers: dict[str, OfficerProfile], now: float, mode: str,
             typing: bool, typing_ok: Callable[[str], bool] | None = None) -> Proposal | None:
        """The proposal to show now, if any (`now` in battle cycles). While the captain types, only an urgent one,
        or one from an officer `typing_ok` allows (a Trusted officer)."""
        if mode not in COOLDOWN:
            return None
        for p in candidates(obs, ship, officers):
            if typing and not p.urgent and not (typing_ok is not None and typing_ok(p.officer)):
                continue
            if now - self.belayed.get(_belay_key(p.line), -1e9) < BELAY_MEMORY:
                continue
            if now - self.last_by.get(p.officer, -1e9) < COOLDOWN[mode]:
                continue
            if not p.urgent and now - self.last_any < GAP[mode]:
                continue
            self.last_by[p.officer] = now
            self.last_any = now
            return p
        return None

    def belay(self, p: Proposal, now: float) -> None:
        self.belayed[_belay_key(p.line)] = now


def _belay_key(line: str) -> str:
    """What a belay silences: the line, or every split of fire however the pair of ships changes."""
    return "engage" if line.startswith("engage ") else line


__all__ = ["Proposal", "Proposer", "candidates"]
