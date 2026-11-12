"""How much of the bridge the captain wants: the Bridge setting and the switches it sets [E].

`hud bridge full|quiet|classic` picks a whole style at once; each part can then be switched on its own
(`hud wheel off`, `hud focus pause`, `hud proposals often`, `hud orders off`, `hud subtitles off`,
`hud readbacks log`). Saved with the other settings in config/settings.json under "bridge".

- full: officers speak in subtitles and read every order back; the command wheel; the game eases to a
  quarter speed while you type; officers now and then propose an order; the orders are drawn on the map.
- quiet: the same tools, but officers speak only in the log unless it is urgent, nothing slows down, and
  nobody proposes anything unless asked.
- classic: the console as it was: "acknowledged" lines, no subtitles, wheel, focus, proposals or map orders.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields

MODES = ("full", "quiet", "classic")
FOCUS = ("slow", "pause", "off")
PROPOSALS = ("often", "rarely", "off")
SUBTITLES = ("all", "urgent", "off")
READBACKS = ("voiced", "log", "off")

PRESETS: dict[str, dict[str, object]] = {
    "full": {"wheel": True, "focus": "slow", "proposals": "rarely", "map_orders": True, "subtitles": "all",
             "readbacks": "voiced", "preview": True},
    "quiet": {"wheel": True, "focus": "off", "proposals": "off", "map_orders": True, "subtitles": "urgent",
              "readbacks": "log", "preview": True},
    "classic": {"wheel": False, "focus": "off", "proposals": "off", "map_orders": False, "subtitles": "off",
                "readbacks": "off", "preview": False},
}


@dataclass
class BridgePrefs:
    mode: str = "full"
    wheel: bool = True              # right-click a ship (or E) opens the command wheel
    focus: str = "slow"             # while typing an order: slow to 0.25x, pause, or off
    proposals: str = "rarely"       # officers propose an order now and then (Y makes it so, N belays)
    map_orders: bool = True         # standing orders drawn on the map
    subtitles: str = "all"          # officers' words low on the map: all, urgent only, or off
    readbacks: str = "voiced"       # orders read back: by the officer (subtitle + log), in the log, or "acknowledged"
    preview: bool = True            # a ghost of what the order being typed will do

    @staticmethod
    def from_dict(d: dict[str, object] | None) -> BridgePrefs:
        p = BridgePrefs()
        if not d:
            return p
        mode = d.get("mode")
        if mode in MODES:
            p.apply_mode(str(mode))
        names = {f.name for f in fields(BridgePrefs)} - {"mode"}
        allowed = {"focus": FOCUS, "proposals": PROPOSALS, "subtitles": SUBTITLES, "readbacks": READBACKS}
        for k, v in d.items():
            if k not in names:
                continue
            if k in allowed and v not in allowed[k]:
                continue
            if k not in allowed and not isinstance(v, bool):
                continue
            setattr(p, k, v)
        return p

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    def apply_mode(self, mode: str) -> None:
        self.mode = mode
        for k, v in PRESETS[mode].items():
            setattr(self, k, v)

    @property
    def classic(self) -> bool:
        return self.mode == "classic" and self.readbacks == "off"

    def describe(self) -> str:
        on = lambda b: "on" if b else "off"  # noqa: E731
        return (f"Bridge {self.mode}: subtitles {self.subtitles}, readbacks {self.readbacks}, wheel {on(self.wheel)}, "
                f"focus {self.focus}, proposals {self.proposals}, map orders {on(self.map_orders)}, "
                f"preview {on(self.preview)}.")


__all__ = ["BridgePrefs", "FOCUS", "MODES", "PRESETS", "PROPOSALS", "READBACKS", "SUBTITLES"]
