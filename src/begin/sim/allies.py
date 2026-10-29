"""Standing orders for ally ships (Begin's `tell <ally> ...`, manual pp. 22-25 and the v2.0 additions).

An ally carries several independent orders at once, as in Begin:

* one *movement* order (escort, hold course, run, withdraw, approach,
  defend, dock, tractor, tow, board, stop); a new one replaces the old;
* an ordered *target* (target / attack), cleared by disengage;
* *hold fire* / *open fire*;
* a *weapon* preference (torpedo / phaser / probe), each overriding the others;
* a *group* number for `tell <group> ...`.

The world owns this state; AI captains read it through their Observation.
"""

from __future__ import annotations

from dataclasses import dataclass

# canonical order -> accepted spellings (any unique prefix also works in the console)
ORDER_WORDS: dict[str, tuple[str, ...]] = {
    "target": ("target",),
    "attack": ("attack", "kill", "engage"),
    "hold": ("hold", "holdfire", "cease"),
    "open": ("open", "openfire"),
    "disengage": ("disengage",),
    "escort": ("escort", "follow"),
    "course": ("course", "heading"),
    "run": ("run", "retreat", "flee"),
    "withdraw": ("withdraw", "reserve"),
    "cancel": ("cancel",),
    "torpedo": ("torpedo", "torpedoes", "torp", "torps"),
    "phaser": ("phaser", "phasers"),
    "probe": ("probe", "probes"),
    "report": ("report", "status"),
    "board": ("board",),
    "tow": ("tow",),
    "tractor": ("tractor",),
    "release": ("release",),
    "approach": ("approach",),
    "dock": ("dock",),
    "undock": ("undock",),
    "join": ("join",),
    "leave": ("leave",),
    "stop": ("stop", "halt"),
    "defend": ("defend", "protect", "guard"),
    "recover": ("recover",),
    "eject": ("eject",),
}

MOVEMENT_ORDERS = frozenset(
    {"escort", "course", "run", "withdraw", "approach", "defend", "dock", "tractor", "tow", "board", "stop"}
)
WEAPON_ORDERS = frozenset({"torpedo", "phaser", "probe"})
# orders that name a ship, and whether that ship must be hostile (True), friendly (False) or either (None)
SHIP_ORDERS: dict[str, bool | None] = {
    "target": True, "attack": True, "torpedo": True, "phaser": True, "probe": True, "board": True,
    "escort": False, "defend": False, "dock": False, "recover": False, "eject": False,
    "tow": None, "tractor": None, "approach": None,
}

DEFAULT_ESCORT_RANGE = 3000.0
DEFAULT_APPROACH_RANGE = 2000.0
DEFEND_RANGE = 2000.0


@dataclass
class AllyStanding:
    movement: str | None = None
    move_target: int | None = None
    move_value: float | None = None
    destination: int | None = None    # tow destination
    party: int = 0                    # boarding party size
    target: int | None = None         # ordered target, shown in parentheses by `status fleet`
    hold_fire: bool = False
    weapon: str | None = None
    group: int | None = None
    recover: int | None = None        # a base's order to bring a ship aboard
    issued: int = 0                   # tick of the last order, so captains notice new ones

    def mission(self, name_of: dict[int, str]) -> str:
        """Begin's MISSION column."""
        bits: list[str] = []
        m = self.movement
        if m is not None:
            who = name_of.get(self.move_target, "") if self.move_target is not None else ""
            if m == "course":
                bits.append(f"Course {self.move_value:.0f}" if self.move_value is not None else "Course")
            elif m in ("escort", "approach") and self.move_value is not None:
                bits.append(f"{m.title()} {who} at {self.move_value:,.0f}")
            elif m == "tow" and self.destination is not None:
                bits.append(f"Tow {who} to {name_of.get(self.destination, '?')}")
            elif m == "board":
                bits.append(f"Board {who} ({self.party})")
            else:
                bits.append(f"{m.title()} {who}".strip())
        if self.weapon:
            bits.append(self.weapon.title())
        if self.hold_fire:
            bits.append("Hold fire")
        if self.recover is not None:
            bits.append(f"Recover {name_of.get(self.recover, '?')}")
        return ", ".join(bits) if bits else ".."

    def summary(self, name_of: dict[int, str]) -> str:
        """The mission plus the ordered target, for the map and the Fleet tab; empty when the ally is on its own."""
        m = self.mission(name_of)
        bits = [] if m == ".." else [m]
        if self.target is not None:
            bits.append(f"{'attack' if self.movement is None else 'target'} {name_of.get(self.target, '?')}")
        return ", ".join(bits)


__all__ = [
    "AllyStanding", "DEFAULT_APPROACH_RANGE", "DEFAULT_ESCORT_RANGE", "DEFEND_RANGE", "MOVEMENT_ORDERS",
    "ORDER_WORDS", "SHIP_ORDERS", "WEAPON_ORDERS",
]
