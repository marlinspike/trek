"""The game's own controls: pause, time, help, coach, counsel, orders, the HUD, sound, recording, voices and keys."""

from __future__ import annotations

import re

from ...sim.commands import CeaseFire, StandDown
from ..tokens import ParseError, Tokens
from ..vocab import is_num, match_word
from .base import BRIDGE_SWITCHES, ParserBase, ParseResult


class InterfaceVerbs(ParserBase):
    def _v_pause(self, tok: Tokens, res: ParseResult) -> None:
        res.actions.append(("pause", None))

    def _v_resume(self, tok: Tokens, res: ParseResult) -> None:
        res.actions.append(("resume", None))

    def _v_time(self, tok: Tokens, res: ParseResult) -> None:
        v = tok.number("time scale")
        if v not in (0.25, 0.5, 1.0, 2.0, 4.0):
            raise ParseError("Time scale must be 0.25, 0.5, 1, 2 or 4.")
        res.actions.append(("speed", v))

    def _v_help(self, tok: Tokens, res: ParseResult) -> None:
        """`help` / `man` opens the manual; `help <command>` opens that command's page."""
        query = " ".join(tok.rest())
        res.actions.append(("manual", query or None))

    def _v_coach(self, tok: Tokens, res: ParseResult) -> None:
        tok.rest()
        res.actions.append(("manual", "coach"))

    def _v_counsel(self, tok: Tokens, res: ParseResult) -> None:
        """`counsel [on|off|<goal>]`: the officers' plans from here, over the map (the O key); with a goal, each
        officer's way to it: `counsel destroy the gr'oth`, `counsel kill all the cubes`, `counsel disable all their
        engines`, `counsel capture the mugger`, `counsel survive`, `counsel mission` [E]."""
        words = " ".join(tok.raw.split()[1:]).strip()
        res.actions.append(("counsel", words or None))
        tok.rest()

    def _v_quit(self, tok: Tokens, res: ParseResult) -> None:
        res.actions.append(("quit", None))

    def _v_execute(self, tok: Tokens, res: ParseResult) -> None:
        """`execute [order] <name>`: run one of the captain's named orders (config/orders.toml)."""
        tok.take_word("order", "plan")
        name = " ".join(tok.rest()).strip()
        if not name:
            raise ParseError("Execute which order? Type 'orders' to list them.")
        res.actions.append(("execute", name))

    def _v_orders(self, tok: Tokens, res: ParseResult) -> None:
        tok.rest()
        res.actions.append(("orders", None))

    def _v_belay(self, tok: Tokens, res: ParseResult) -> None:
        """`belay [that|order]`: stop the named order that is running, and cease fire;
        `belay all|everything`: and the officers stand down too."""
        everything = any(w in ("all", "everything", "everyone", "everybody") for w in tok.rest())
        res.actions.append(("belay", None))
        res.commands.append(self._cmd(StandDown if everything else CeaseFire))   # and whatever the officers had going

    def _v_request(self, tok: Tokens, res: ParseResult) -> None:
        """`request reinforcements` [E]: on a tour of duty, ask Starfleet for a ship; she arrives after the stop's ETA."""
        tok.take_word("reinforcements", "reinforcement", "backup", "help", "support", "assistance", "starfleet")
        tok.rest()
        res.actions.append(("reinforcements", None))

    def _v_hud(self, tok: Tokens, res: ParseResult) -> None:
        """`hud detail|simple`: every number on the panels, or only what matters (hover a panel to see the rest)."""
        first = tok.toks[0] if tok.toks else ""
        w = tok.next()
        if w is None:
            res.actions.append(("hud", "detail" if first == "detail" else None))
        elif w in ("detail", "detailed", "full", "all", "on", "more"):
            res.actions.append(("hud", "detail"))
        elif w in ("simple", "less", "off", "minimal", "clean"):
            res.actions.append(("hud", "simple"))
        elif w in ("jolt", "shake"):
            v = tok.next()
            if v not in ("on", "off"):
                raise ParseError("hud jolt on or hud jolt off: whether the map jolts when your ship takes a heavy blow.")
            res.actions.append(("hud", f"jolt {v}"))
        elif w in BRIDGE_SWITCHES:
            key, choices = BRIDGE_SWITCHES[w]
            v = tok.next()
            if v is None:
                res.actions.append(("bridge", None))
                return
            v = {"slower": "slow", "rare": "rarely", "seldom": "rarely", "never": "off", "none": "off",
                 "normal": "full", "voice": "voiced", "quieter": "quiet"}.get(v, v)
            if v not in choices:
                raise ParseError(f"hud {w} {'|'.join(choices)}")
            res.actions.append(("bridge", (key, v)))
        else:
            raise ParseError("hud detail (every number on the panels), hud simple (hover a panel for the rest), "
                             "hud jolt on|off, or hud bridge full|quiet|classic.")

    def _v_sound(self, tok: Tokens, res: ParseResult) -> None:
        """`sound on|off|<0-100>`, `sound phaser b`, `sound hum on|off|<0-100>`: the battle's sound effects, which
        version, and the ship's engine hum (M mutes too)."""
        first = tok.toks[0] if tok.toks else ""
        w = tok.next()
        if first == "mute" and w is None:
            res.actions.append(("sound", "off"))
        elif w is None:
            res.actions.append(("sound", None))
        elif w in ("on", "off"):
            res.actions.append(("sound", w))
        elif is_num(w) and 0 <= float(w) <= 100:
            res.actions.append(("sound", float(w)))
        elif w in ("hum", "engine", "engines", "drone", "ambience", "ambient"):
            v = tok.next()
            if v == "off":
                res.actions.append(("sound", ("hum", 0.0)))
            elif v == "on" or v is None:
                res.actions.append(("sound", ("hum", None)))
            elif is_num(v) and 0 <= float(v) <= 100:
                res.actions.append(("sound", ("hum", float(v) / 100)))
            else:
                raise ParseError("sound hum on, sound hum off, or sound hum <0-100> for how loud the ship's hum is.")
        elif w in ("phaser", "phasers", "torpedo", "torpedoes", "launch"):
            which = "phaser" if w.startswith("phaser") else "torpedo"
            v = tok.next()
            if v is not None and v not in ("a", "b", "c", "d"):
                raise ParseError(f"sound {which} a, b, c or d: the versions of the {which} sound.")
            res.actions.append(("sound", (which, v)))
        else:
            raise ParseError("sound on, sound off, sound <0-100> for the volume, sound hum on|off, "
                             "or sound phaser|torpedo a|b|c|d.")

    def _v_record(self, tok: Tokens, res: ParseResult) -> None:
        """`record <name>`, `record stop|save`, `record off|discard`, `record last <n> as <name>` [E]."""
        w = tok.next()
        if w is None:
            res.actions.append(("record", ("start", "")))
        elif w in ("stop", "save", "end", "done", "finish"):
            tok.rest()
            res.actions.append(("record", ("stop", "")))
        elif w in ("off", "discard", "cancel", "abort", "scrap"):
            tok.rest()
            res.actions.append(("record", ("discard", "")))
        elif w == "last":
            n = tok.number("how many")
            tok.take_word("as", "called", "named")
            name = "-".join(tok.toks[tok.i:])
            tok.i = len(tok.toks)
            res.actions.append(("record", ("last", f"{int(n)} {name}")))
        else:
            name = "-".join([w] + tok.toks[tok.i:])
            tok.i = len(tok.toks)
            res.actions.append(("record", ("start", name)))

    def _v_style(self, tok: Tokens, res: ParseResult) -> None:
        """`style` lists the command styles and ribbons; `style <name>` promises one for this battle [E]."""
        words = "".join(tok.toks[tok.i:]).replace("-", "")
        tok.i = len(tok.toks)
        res.actions.append(("style", words or None))

    def _v_voice(self, tok: Tokens, res: ParseResult) -> None:
        """`voice`: the voice page (engine, push-to-talk, test, models) [E]. `voice off|on`."""
        rest = " ".join(tok.rest())
        res.actions.append(("voice", rest or None))

    def _v_translate(self, tok: Tokens, res: ParseResult) -> None:
        """`translate on|off|always`: plain-English console input through the language model [E]."""
        w = tok.next()
        if w is None:
            res.actions.append(("translate", None))
            return
        mode = match_word(w, {"fallback": ("on", "fallback", "auto"), "off": ("off", "never"), "always": ("always", "all")})
        if mode is None:
            raise ParseError("translate on, translate off or translate always.")
        res.actions.append(("translate", mode))

    def _v_text(self, tok: Tokens, res: ParseResult) -> None:
        res.info.append("This remake has no text mode: the tactical display is always on. "
                        "Status commands print Begin's text displays here in the console.")

    def _v_key(self, tok: Tokens, res: ParseResult) -> None:
        """Begin 2.0's `key <F#|^x> <string>`: bind a key to console commands (';' separates commands)."""
        name = tok.next()
        if name is None:
            res.actions.append(("key", None))
            return
        name = name.upper() if name.startswith("f") else name
        if not re.fullmatch(r"(F([2-8]|1[0-2])|\^[a-z])", name):
            raise ParseError("Keys are F2-F8, F10-F12 or ^a-^z (F1 is help, F9 the debug view).")
        raw = tok.raw.strip()
        parts = raw.split(None, 2)
        text = parts[2].strip() if len(parts) > 2 else ""
        tok.rest()
        res.actions.append(("key", (name, text)))
