"""The captain's command: alert conditions, recording named orders, command styles, trust and learned phrasing [E].

Part of `BattleScene` (see `ui/battle_scene.py`), which mixes these methods in; they share its state.

- `alert red|yellow|green` runs that condition's lines (content/data/alerts.toml, or config/alerts.toml) and shows
  the condition on the map.
- `record <name>` ... `record stop` keeps the lines the captain runs and saves them as a named order in
  config/orders.toml, tidied: displays and repeats dropped, pauses of two cycles or more kept as `wait N`.
  `record last <n> as <name>` saves the last few lines already run. With no name, the order gets a
  Starfleet-style one (alpha-1, bravo-2...).
- `style <name>` promises a command style before the battle starts; win keeping it for its ribbon.
- Trust (`crew/career.py`) grows with the battles officers fight beside the captain; a rise is announced.
- Learned phrasing: a plain-English line the language model turned into console commands is remembered in
  config/phrasebook.json, so the same words work at once next time, with or without the model.
"""

from __future__ import annotations

import json
import re
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING

from ...console.orders import OrderBook
from ...crew.career import STYLE_WORDS, STYLES
from ...crew.review import standout
from ...paths import config_dir
from ...sim.commands import Command, DelegateStation, SetHelm, TakeConn
from .. import theme
from .state import SceneState

if TYPE_CHECKING:
    from ..battle_scene import BattleScene

ALERTS_FILE = Path(__file__).resolve().parents[2] / "content" / "data" / "alerts.toml"
ALERT_COLOR = {"red": theme.ALERT, "yellow": theme.CAUTION, "green": theme.GOOD}
NOT_RECORDED = re.compile(r"^\s*(record|rec|status|st|damage|dmg|chart|report|help|\?|orders|plans|crew|style|"
                          r"voice|hud|sound|range|zoom|banks|tubes|launchers|shields|fleet|prisoners|key|pause|"
                          r"resume|time|translate|quit|exit)\b", re.I)
NAMES = ("alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "gamma", "kappa", "sigma", "omega")
SILENT_WARP = 5.0


def load_alerts(override: Path | None = None) -> dict[str, tuple[str, list[str]]]:
    out: dict[str, tuple[str, list[str]]] = {}
    for path in (ALERTS_FILE, override):
        if path is None or not path.exists():
            continue
        try:
            data = tomllib.loads(path.read_text(encoding="utf-8"))
        except (OSError, tomllib.TOMLDecodeError):
            continue
        for k in ("red", "yellow", "green"):
            body = data.get(k)
            if isinstance(body, dict) and isinstance(body.get("steps"), list):
                out[k] = (str(body.get("note", "")), [str(x) for x in body["steps"] if str(x).strip()])
    return out


@dataclass
class Recording:
    name: str
    steps: list[tuple[float, str]] = field(default_factory=list)    # (battle time, console line)


def tidy(steps: list[tuple[float, str]]) -> list[str]:
    """The lines worth keeping as an order: no displays or repeats, and the pauses that mattered."""
    out: list[str] = []
    last_t: float | None = None
    for t, line in steps:
        if NOT_RECORDED.match(line):
            continue
        if out and out[-1] == line:
            continue
        if last_t is not None and t - last_t >= 2.0:
            out.append(f"wait {round(t - last_t)}")
        out.append(line)
        last_t = t
    return out


def order_name(raw: str, taken: set[str]) -> str:
    name = re.sub(r"[^a-z0-9_\-]+", "-", raw.strip().lower()).strip("-")
    if name and name[0].isalnum():
        return name
    for n in range(1, 10):
        for g in NAMES:
            cand = f"{g}-{n}"
            if cand not in taken:
                return cand
    return "order"


def toml_order(name: str, steps: list[str], note: str = "") -> str:
    body = ",\n".join(f"    {json.dumps(s)}" for s in steps)
    head = f"\n[{name}]\n" + (f"note = {json.dumps(note)}\n" if note else "")
    return head + f"steps = [\n{body},\n]\n"


class CommandMixin(SceneState):
    # ------------------------------------------------------------ alert conditions

    def alert(self: BattleScene, which: str | None) -> None:
        if which is None:
            here = self.condition or "none set"
            self._log(f"Condition: {here}. " + " · ".join(f"alert {k}: {v[0]}" for k, v in self.alerts.items()),
                      theme.TEXT_DIM)
            return
        bundle = self.alerts.get(which)
        if bundle is None:
            self._log(f"No alert {which} in alerts.toml.", theme.CAUTION)
            return
        self.condition = which
        note, steps = bundle
        self._log(f"Condition {which}" + (f": {note}" if note else "."), ALERT_COLOR[which], channel="bridge")
        name, oid = self._station_officer("tactical")
        self._voice(name or "", f"Condition {which}, Captain.", ALERT_COLOR[which], "tactical" if name else None, oid,
                    urgent=which == "red")
        for line in steps:
            self._run_one(line, translate=False, echo="  » ")
        if which == "red":
            import time as _t

            self.audio.play("alert", _t.monotonic(), 0.0, 0.5)

    # ------------------------------------------------------------ recording named orders

    def record(self: BattleScene, val: tuple[str, str]) -> None:
        what, arg = val
        if what == "start":
            name = order_name(arg, set(self.orders.orders)) if arg else order_name("", set(self.orders.orders))
            self.recording = Recording(name)
            self._log(f"Recording order {name}: every order you give from now is kept. 'record stop' saves it, "
                      "'record off' throws it away.", theme.FRIEND)
        elif what == "discard":
            if self.recording is None:
                self._log("Not recording.", theme.TEXT_DIM)
                return
            self._log(f"Recording of {self.recording.name} thrown away.", theme.TEXT_DIM)
            self.recording = None
        elif what == "stop":
            rec = self.recording
            if rec is None:
                self._log("Not recording. 'record <name>' starts.", theme.TEXT_DIM)
                return
            self.recording = None
            self._save_order(rec.name, tidy(rec.steps))
        elif what == "last":
            n_s, _, name = arg.partition(" ")
            n = max(1, min(20, int(n_s)))
            ran = [line for line in self.ran[-n:]]
            self._save_order(order_name(name, set(self.orders.orders)), tidy([(0.0, x) for x in ran]))

    def note_ran(self: BattleScene, line: str) -> None:
        """A line the captain gave that ran: kept for `record last`, and for the recording, if one is on."""
        if NOT_RECORDED.match(line):
            return
        self.ran.append(line)
        del self.ran[:-30]
        if self.recording is not None:
            self.recording.steps.append((self.world.time, line))

    def _save_order(self: BattleScene, name: str, steps: list[str]) -> None:
        if not steps:
            self._log(f"Nothing to save in {name}: no orders were given.", theme.CAUTION)
            return
        folder = config_dir()
        path = folder / "orders.toml"
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if not path.exists():
                example = folder / "orders.example.toml"
                start = example.read_text(encoding="utf-8") if example.exists() else "# Your named tactical orders.\n"
                path.write_text(start, encoding="utf-8")
            text = path.read_text(encoding="utf-8")
            if re.search(rf"^\[{re.escape(name)}\]", text, re.M):
                self._log(f"There is already an order called {name}. Pick another name.", theme.CAUTION)
                return
            path.write_text(text.rstrip() + "\n" + toml_order(name, steps, f"Recorded in {self.battle.setup.title}"),
                            encoding="utf-8")
        except OSError as e:
            self._log(f"Couldn't save the order: {e}", theme.CAUTION)
            return
        llm = self.orders.llm
        self.orders = OrderBook.load(folder)
        self.orders.llm = llm
        self._order_problems(self.orders.prepare(self._would_run, self._translation_brief(), self._target_id()))
        self._log(f"Order {name} saved ({len(steps)} steps): " + " · ".join(steps), theme.GOOD)
        self._log(f"Say '{name}' to run it. It's in the Orders tab, and in config/orders.toml to edit.", theme.TEXT_DIM)

    # ------------------------------------------------------------ command styles

    def choose_style(self: BattleScene, words: str | None) -> None:
        if words is None:
            lines = ["COMMAND STYLES: promise one before the battle starts; win keeping it for its ribbon."]
            for s in STYLES.values():
                n = self.career.ribbons.get(s.key, 0)
                mark = "◆" if self.style == s.key else " "
                lines.append(f"{mark} style {s.key:<7} {s.name:<15} {s.promise}" + (f"   ribbons: {n}" if n else ""))
            self._show(lines, None)
            return
        key = STYLE_WORDS.get(words)
        if key is None:
            self._log(f"No style '{words}'. Type 'style' for the list.", theme.CAUTION)
            return
        if self.world.time > 1.0 and self.style != key:
            self._log("A style is promised before the battle starts.", theme.CAUTION)
            return
        if key == "green" and self.player is not None and (self.player.delegated or self.player.conn):
            self._log("A green crew can't already hold a station. 'stand down' first.", theme.CAUTION)
            return
        self.style = key
        self.style_broken = None
        s = STYLES[key]
        self._log(f"{s.name}: {s.promise}", theme.CAUTION, channel="bridge")

    def style_check(self: BattleScene, cmd: Command | None = None, why: str | None = None) -> None:
        """Called as orders go out: does this one break the promise?"""
        if self.style is None or self.style_broken is not None:
            return
        reason = why
        if cmd is not None:
            if self.style in ("chair", "green") and (
                    (isinstance(cmd, DelegateStation) and cmd.on) or (isinstance(cmd, TakeConn) and cmd.officer)):
                reason = "a station was handed over"
            elif self.style == "silent" and isinstance(cmd, SetHelm) and cmd.warp is not None and cmd.warp > SILENT_WARP:
                reason = f"warp {cmd.warp:g}"
        if reason is not None:
            self.style_broken = reason
            self._log(f"{STYLES[self.style].name} broken: {reason}.", theme.TEXT_DIM)

    def _style_tick(self: BattleScene) -> None:
        p = self.player
        if self.style is None or self.style_broken is not None or p is None:
            return
        if self.style == "silent" and p.warp > SILENT_WARP + 0.05:
            self.style_check(why=f"warp {p.warp:.1f}")
        if self.style in ("chair", "green") and (p.delegated or p.conn):
            self.style_check(why="a station was handed over")

    # ------------------------------------------------------------ the end of the battle

    def career_outcome(self: BattleScene) -> None:
        """Trust and ribbons when the battle ends (once)."""
        if self._career_done:
            return
        self._career_done = True
        w = self.world
        won = w.outcome.winner is not None and w.outcome.winner == self.side
        crew = self.battle.crew
        if won and crew is not None and self.player_id is not None:
            delegated = [o.id for st, o in crew.officers.items() if st in self.ever_delegated]
            best = standout(crew.officers.values(), self.player_id, w.command_log, self.deeds)
            self.career.battle_won([o.id for o in crew.officers.values()], delegated,
                                   getattr(getattr(best, "officer", None), "id", None))
        if self.style is not None:
            s = STYLES[self.style]
            me = w.ships.get(self.player_id) if self.player_id is not None else None
            if self.style == "iron" and me is not None and me.structure / me.structure_max <= 0.75:
                self.style_broken = self.style_broken or f"hull {max(0.0, me.structure / me.structure_max):.0%}"
            if won and self.style_broken is None:
                self.career.ribbon(self.style)
                self.ribbon_won = s.ribbon
                self._log(f"{s.ribbon} earned: {s.name}. You have {self.career.ribbons[self.style]}.", theme.GOOD)
            elif self.style_broken is not None:
                self._log(f"{s.name} not kept ({self.style_broken}).", theme.TEXT_DIM)
        self._announce_trust()

    def _announce_trust(self: BattleScene) -> None:
        b = self.bridge
        for oid, lvl in self.career.take_risen():
            o = b.find(oid) if b is not None else None
            name = o.name if o is not None else oid
            self._log(f"{name} now trusts you as a {lvl} officer.", theme.GOOD, channel="bridge")
            self.trust_news.append(f"{name}: {lvl}")

    # ------------------------------------------------------------ learned phrasing

    def remember_phrase(self: BattleScene, words: str, commands: list[str]) -> None:
        key = " ".join(words.lower().split())
        if not key or not commands or key in self.phrasebook:
            return
        self.phrasebook[key] = list(commands)
        try:
            path = config_dir() / "phrasebook.json"
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(self.phrasebook, indent=1, sort_keys=True), encoding="utf-8")
        except OSError:
            pass

    def recalled(self: BattleScene, words: str) -> list[str] | None:
        return self.phrasebook.get(" ".join(words.lower().split()))


def load_phrasebook() -> dict[str, list[str]]:
    try:
        raw = json.loads((config_dir() / "phrasebook.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    if not isinstance(raw, dict):
        return {}
    return {str(k): [str(c) for c in v] for k, v in raw.items() if isinstance(v, list)}


__all__ = ["CommandMixin", "Recording", "load_alerts", "load_phrasebook", "order_name", "tidy", "toml_order"]
