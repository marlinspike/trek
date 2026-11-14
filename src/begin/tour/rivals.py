"""Returning enemy captains [E]: the ones who got away come back, and remember you.

When a tour stop ends with the enemy's commander (the captain of their heaviest ship) still free, because their
ship escaped or held the field, that captain becomes a **rival**. Rivals are kept in the captain's career
(settings.json, "career", "rivals"), so they follow you from tour to tour.

A rival returns at a later stop against their own navy: they take command of the heaviest enemy ship there,
better than before (each meeting sharpens them), and they hail you as someone they know. How much your bridge
can tell you about them rides on the officers' trust (crew/career.py):

    Green     sensors name the ship and its captain, and say we have met
    Steady    the officer who knows that navy recognises them and says where you met
    Trusted   ...and tells you how they got away last time, so you can stop it happening again

A rival destroyed or taken is done: they never return, and the Ready Room says so after the battle.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import TYPE_CHECKING, Any

from ..crew.career import Career, level_index
from ..sim.ship import ShipStatus

if TYPE_CHECKING:
    from ..battle import Battle
    from ..content.schema import ContentDB
    from .model import Stop

MAX_RIVALS = 8
COMPETENCE = 0.72              # a rival's competence the first time they return ...
SHARPER = 0.05                 # ... and how much each meeting adds
TOP = 0.95
WHO_KNOWS = {"klingon": "worf", "romulan": "spock", "orion": "worf"}     # who recognises a navy's captains
OFFICER_NAMES = {"worf": "Worf", "spock": "Spock", "seven": "Seven of Nine", "geordi": "La Forge"}
GREETINGS = {
    "klingon": "Enterprise! I remember {place}. This time there is no running for either of us.",
    "romulan": "Enterprise. We meet again. I have studied {place}; I suggest you have done the same.",
    "orion": "Well, if it isn't the Enterprise. {place} cost me. Today you pay it back.",
}
GREETING = "Enterprise. We have met before, at {place}. I have not forgotten."
HABITS = {"escaped": "broke off and ran when the fight turned", "held": "held the field when we withdrew"}


@dataclass
class Rival:
    name: str
    faction: str
    ship_class: str
    ship_name: str
    met: int = 1                  # battles against us
    place: str = ""               # where we last met
    tour: str = ""                # on which tour
    habit: str = "escaped"        # how they last got away: escaped | held
    fate: str = "at large"        # at large | destroyed | captured

    @property
    def at_large(self) -> bool:
        return self.fate == "at large"

    def competence(self) -> float:
        return min(TOP, COMPETENCE + SHARPER * self.met)


class RivalBook:
    """The rivals kept in a career's store, and what a tour does with them."""

    def __init__(self, career: Career) -> None:
        self.career = career
        raw = career.store.get("rivals")
        self.rivals: list[Rival] = []
        for d in raw if isinstance(raw, list) else []:
            try:
                self.rivals.append(Rival(**d))
            except TypeError:
                continue

    def save(self) -> None:
        self.career.store["rivals"] = [asdict(r) for r in self.rivals[-MAX_RIVALS:]]

    def find(self, name: str, faction: str) -> Rival | None:
        return next((r for r in self.rivals if r.name == name and r.faction == faction), None)

    # ------------------------------------------------------------ before a stop

    def for_stop(self, stop: Stop, content: ContentDB, flags: set[str]) -> Rival | None:
        """The rival who comes back at this stop: one at large from the navy we face, the most met first."""
        factions = {content.classes[c].faction for c in stop.enemy_ships(flags)}
        if len(factions) != 1:
            return None
        faction = next(iter(factions))
        free = [r for r in self.rivals if r.at_large and r.faction == faction]
        return max(free, key=lambda r: (r.met, -self.rivals.index(r))) if free else None

    def greeting(self, rival: Rival) -> str:
        return GREETINGS.get(rival.faction, GREETING).format(place=rival.place or "our last meeting")

    def recognition(self, rival: Rival) -> tuple[str, str]:
        """(speaker, words): what the bridge can tell the captain about a returning rival, by trust."""
        officer = WHO_KNOWS.get(rival.faction, "spock")
        trust = level_index(self.career.points(officer))
        times = "once" if rival.met == 1 else "twice" if rival.met == 2 else f"{rival.met} times"
        if trust == 0:
            return "Computer", f"The enemy flagship is under {rival.name}, a captain we have fought before."
        words = f"Captain, that is {rival.name}. We fought them {times}, last at {rival.place or 'our last meeting'}."
        if trust >= 2:
            words += f" Last time they {HABITS.get(rival.habit, rival.habit)}. Expect it again, and be ready for it."
        return OFFICER_NAMES.get(officer, officer.title()), words

    # ------------------------------------------------------------ after a stop

    def after_battle(self, battle: Battle, place: str, tour: str, rival: Rival | None) -> str:
        """Who is a rival now, who returns again, and who is done. Returns a line for the Ready Room, or ""."""
        w = battle.world
        side = w.player_side
        enemies = [s for s in w.ships.values() if s.side != side and s.side >= 0 and not s.cls.is_base and s.captain]
        if not enemies:
            return ""
        news = ""
        if rival is not None:
            ship = next((s for s in enemies if s.captain == rival.name), None)
            if ship is not None:
                rival.met += 1
                rival.place, rival.tour = place, tour
                news = self._settle(rival, ship.status, w.outcome.winner == side)
        else:
            boss = max(enemies, key=lambda s: s.cls.mass)
            free = _free(boss.status, w.outcome.winner == side)
            if free:
                known = self.find(boss.captain, boss.cls.faction)
                if known is None:
                    self.rivals.append(Rival(boss.captain, boss.cls.faction, boss.cls.id, boss.name, place=place,
                                             tour=tour, habit=free))
                    news = f"{boss.captain} of the {boss.name} got away. We have not seen the last of them."
                else:
                    known.met += 1
                    known.place, known.tour, known.habit = place, tour, free
        self.save()
        return news

    def _settle(self, rival: Rival, status: ShipStatus, won: bool) -> str:
        if status in (ShipStatus.DESTROYED, ShipStatus.DERELICT):
            rival.fate = "destroyed"
            return f"{rival.name} will not trouble us again: the {rival.ship_name} is destroyed."
        if status in (ShipStatus.CAPTURED, ShipStatus.SURRENDERED):
            rival.fate = "captured"
            return f"{rival.name} is our prisoner at last."
        free = _free(status, won)
        rival.habit = free or rival.habit
        return f"{rival.name} got away again." if free else ""


def _free(status: ShipStatus, we_won: bool) -> str:
    """How an enemy captain left the field free: 'escaped', 'held' (we withdrew), or '' (not free)."""
    if status == ShipStatus.ESCAPED:
        return "escaped"
    if status == ShipStatus.ACTIVE and not we_won:
        return "held"
    return ""


def personality(rival: Rival) -> dict[str, float]:
    """The leanings a returning rival fights with: sharper with every meeting."""
    c = rival.competence()
    return {"competence": c, "crew_competence": c, "discipline": min(TOP, c + 0.05)}


def as_dict(rival: Rival) -> dict[str, Any]:
    return asdict(rival)


__all__ = ["GREETINGS", "MAX_RIVALS", "Rival", "RivalBook", "WHO_KNOWS", "personality"]
