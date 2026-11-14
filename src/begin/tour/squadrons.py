"""Starting squadrons [E]: named escort groups a captain earns, each with one perk for the tour.

A starting squadron is a shortcut and a reward. Picking one on the Squadron page fills the escorts with its
ships (they cost fleet points as usual) and brings its perk for the whole tour. Squadrons are earned two ways,
both kept in the captain's career (settings.json, "career"; see crew/career.py):

- an officer's trust: when Worf, La Forge or Spock come to trust the captain (Trusted), they put their name to
  a group of ships that know how they work;
- tours won: Starfleet gives a captain with a won tour a detachment of its own.

Squadrons are escorts and options only. The flagship is the tour's (the Enterprise is a Dreadnought), and no
perk touches her.

The perks:

- **veteran**: the escorts' crews are seasoned. Their morale starts higher and settles back to that, not their
  navy's usual, between stops.
- **tender**: a supply ship sails with the squadron. Every ship's magazine gets an extra quarter of a reload
  between stops.
- **liaison**: an officer with Starfleet's ear. One more call for reinforcements on this tour.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..content.schema import ContentDB
from ..crew.career import LEVELS, Career, level_index
from .state import ShipRecord, TourState, fleet_cost

VETERAN_MORALE = 12.0          # points of morale above her navy's usual
TENDER_RESUPPLY = 0.25         # extra share of a full magazine between stops
PERKS: dict[str, str] = {
    "veteran": "Seasoned crews, steadier morale",
    "tender": "A supply ship: more torpedoes each stop",
    "liaison": "One more call to Starfleet",
}
OFFICER_NAMES = {"worf": "Worf", "geordi": "La Forge", "spock": "Spock", "seven": "Seven"}


@dataclass(frozen=True)
class Squadron:
    key: str
    name: str
    escorts: tuple[str, ...]
    perks: tuple[str, ...] = ()
    blurb: str = ""
    officer: str = ""              # whose trust earns it ("" for none)
    level: str = ""                # the trust level it takes
    tours: int = 0                 # tours won it takes

    def unlocked(self, career: Career) -> bool:
        if self.officer and level_index(career.points(self.officer)) < _level_at(self.level):
            return False
        return tours_won(career) >= self.tours

    def requirement(self) -> str:
        """What earns it, in a few words."""
        parts = []
        if self.officer:
            parts.append(f"{OFFICER_NAMES.get(self.officer, self.officer.title())}'s trust ({self.level})")
        if self.tours:
            parts.append(f"{self.tours} tour{'s' if self.tours != 1 else ''} won")
        return " and ".join(parts) if parts else "Always available"

    def cost(self, content: ContentDB) -> int:
        return sum(fleet_cost(c, content) for c in self.escorts)

    def describe(self, content: ContentDB) -> str:
        """The ships, counted: '2 destroyers', 'a heavy cruiser and an interceptor'."""
        counts: dict[str, int] = {}
        for c in self.escorts:
            counts[c] = counts.get(c, 0) + 1
        bits = []
        for c, n in counts.items():
            name = content.classes[c].name.lower()
            bits.append(f"{n} {name}s" if n > 1 else f"{'an' if name[0] in 'aeiou' else 'a'} {name}")
        return " and ".join(bits)


SQUADRONS: tuple[Squadron, ...] = (
    Squadron("line", "Destroyer screen", ("federation.de", "federation.in"),
             blurb="A destroyer and an interceptor: Starfleet's usual escort for a starship on patrol."),
    Squadron("worf", "Worf's strike group", ("federation.de", "federation.de"), ("veteran",),
             "Two destroyers whose crews have drilled with Worf. They do not break.", "worf", "Trusted"),
    Squadron("geordi", "La Forge's tender group", ("federation.de", "federation.in"), ("tender",),
             "A destroyer and an interceptor, and the supply ship La Forge trusts to keep up.", "geordi", "Trusted"),
    Squadron("spock", "Spock's survey wing", ("federation.in", "federation.in"), ("liaison",),
             "Two fast interceptors, and a liaison officer Starfleet Command listens to.", "spock", "Trusted"),
    Squadron("detachment", "Starfleet detachment", ("federation.hc",), ("veteran", "liaison"),
             "A heavy cruiser with a veteran crew, given to a captain who has brought a tour home.", tours=1),
)
BY_KEY = {s.key: s for s in SQUADRONS}


def _level_at(name: str) -> int:
    return next((i for i, (n, _) in enumerate(LEVELS) if n == name), 0)


def tours_won(career: Career) -> int:
    won = career.store.get("tours_won")
    return len(won) if isinstance(won, list) else 0


def record_win(career: Career, tour_id: str, seed: int) -> bool:
    """A tour brought home, counted once. Returns True when it is new."""
    won = career.store.get("tours_won")
    won = list(won) if isinstance(won, list) else []
    key = f"{tour_id}#{seed}"
    if key in won:
        return False
    won.append(key)
    career.store["tours_won"] = won
    return True


def offered(content: ContentDB, faction: str) -> list[Squadron]:
    """The squadrons a tour of this faction can field (their ships must be its own)."""
    return [s for s in SQUADRONS if all(c in content.classes and content.classes[c].faction == faction for c in s.escorts)]


def newly_unlocked(before: Career, after: Career) -> list[Squadron]:
    return [s for s in SQUADRONS if s.unlocked(after) and not s.unlocked(before)]


def apply(squadron: Squadron | None, state: TourState, content: ContentDB) -> None:
    """At the start of a tour: the squadron's perks take effect."""
    if squadron is None:
        return
    state.perks = list(squadron.perks)
    state.squadron_key = squadron.key
    if "liaison" in squadron.perks:
        state.calls_left += 1
    settle(state, content)


def settle(state: TourState, content: ContentDB, recs: list[ShipRecord] | None = None) -> None:
    """Veteran crews' morale never sits below their seasoned level (at the start, and after each transit)."""
    if "veteran" not in state.perks:
        return
    for r in recs if recs is not None else state.squadron:
        if r.role == "escort" and not r.lost:
            seasoned = min(100.0, content.factions[content.classes[r.class_id].faction].morale_start + VETERAN_MORALE)
            r.morale = max(r.morale if r.morale is not None else 0.0, seasoned)


def resupply_bonus(state: TourState) -> float:
    return TENDER_RESUPPLY if "tender" in state.perks else 0.0


__all__ = ["BY_KEY", "PERKS", "SQUADRONS", "Squadron", "apply", "newly_unlocked", "offered", "record_win", "settle",
           "resupply_bonus", "tours_won"]
