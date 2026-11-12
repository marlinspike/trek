"""The captain's career: how far each officer trusts the captain, and ribbons for command styles [E].

Trust is earned in battle and kept between battles and tours (settings.json,
"career"). It is not the hidden rapport, which colours how an officer speaks;
trust is shown, and it changes what an officer will do:

    Green    0   new to this captain
    Steady  10   their proposals wait a little longer for an answer
    Trusted 30   ...and they may propose while the captain is typing (as a chip, Ctrl+Y)
    Veteran 70   ...and an urgent proposal left unanswered they carry out themselves

Points: a proposal the captain makes so +2; a battle won with the officer at
their post +2, or +3 if their station was handed to them; standing out in the
debrief +4. A belayed proposal costs nothing: the captain decides.

Command styles are a promise made before the battle starts (`style <name>`):
win the battle keeping it and the ribbon is the captain's. They change nothing
in the battle itself except what the captain chooses to do.
"""

from __future__ import annotations

from dataclasses import dataclass

LEVELS = (("Green", 0), ("Steady", 10), ("Trusted", 30), ("Veteran", 70))


@dataclass(frozen=True)
class Style:
    key: str
    name: str
    promise: str
    ribbon: str


STYLES: dict[str, Style] = {s.key: s for s in (
    Style("chair", "From the chair", "Win without handing a station or the conn to an officer.", "Chair ribbon"),
    Style("book", "By the book", "Win giving every order by its words: the console, the wheel, a proposal or "
                                 "your voice. No fire, helm or warp keys and no steering clicks.", "Book ribbon"),
    Style("silent", "Silent running", "Win without hailing anyone and never above warp 5.", "Silent ribbon"),
    Style("green", "Green crew", "Win with a crew that only follows orders: no proposals, no station or conn "
                                 "handed over.", "Green ribbon"),
    Style("iron", "Iron captain", "Win with the hull above 75%.", "Iron ribbon"),
)}
STYLE_WORDS = {"chair": "chair", "fromthechair": "chair", "book": "book", "bythebook": "book", "silent": "silent",
               "silentrunning": "silent", "green": "green", "greencrew": "green", "iron": "iron", "ironcaptain": "iron"}


def level(points: float) -> str:
    name = LEVELS[0][0]
    for n, at in LEVELS:
        if points >= at:
            name = n
    return name


def level_index(points: float) -> int:
    return [n for n, _ in LEVELS].index(level(points))


class Career:
    """A view on settings.json's "career": {"trust": {officer: points}, "ribbons": {style: count}}."""

    def __init__(self, store: dict[str, object] | None = None) -> None:
        self.store: dict[str, object] = store if store is not None else {}
        trust = self.store.get("trust")
        ribbons = self.store.get("ribbons")
        self.trust: dict[str, float] = {str(k): float(v) for k, v in trust.items()} if isinstance(trust, dict) else {}
        self.ribbons: dict[str, int] = {str(k): int(v) for k, v in ribbons.items()} if isinstance(ribbons, dict) else {}
        self.risen: list[tuple[str, str]] = []     # (officer, new level) since last asked

    def save(self) -> None:
        self.store["trust"] = {k: round(v, 1) for k, v in sorted(self.trust.items())}
        self.store["ribbons"] = dict(sorted(self.ribbons.items()))

    def points(self, officer: str) -> float:
        return self.trust.get(officer, 0.0)

    def level(self, officer: str) -> str:
        return level(self.points(officer))

    def add(self, officer: str, pts: float) -> None:
        before = level_index(self.points(officer))
        self.trust[officer] = self.points(officer) + pts
        after = level_index(self.trust[officer])
        if after > before:
            self.risen.append((officer, LEVELS[after][0]))
        self.save()

    def proposal(self, officer: str, accepted: bool) -> None:
        if accepted:
            self.add(officer, 2)

    def battle_won(self, at_post: list[str], delegated: list[str], standout: str | None) -> None:
        for o in at_post:
            self.add(o, 3 if o in delegated else 2)
        if standout:
            self.add(standout, 4)

    def ribbon(self, style: str) -> None:
        self.ribbons[style] = self.ribbons.get(style, 0) + 1
        self.save()

    def take_risen(self) -> list[tuple[str, str]]:
        out, self.risen = self.risen, []
        return out

    # perks ------------------------------------------------------------
    def proposal_bonus(self, officer: str) -> float:
        """Extra seconds a Steady (or better) officer's proposal waits."""
        return 4.0 if level_index(self.points(officer)) >= 1 else 0.0

    def offers_while_typing(self, officer: str) -> bool:
        return level_index(self.points(officer)) >= 2

    def acts_alone(self, officer: str) -> bool:
        return level_index(self.points(officer)) >= 3


__all__ = ["Career", "LEVELS", "STYLES", "STYLE_WORDS", "Style", "level"]
