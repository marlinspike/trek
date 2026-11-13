"""Named orders from config/orders.toml, and the translator that turns plain words into console commands.

Part of `BattleSession` (see `session/battle.py`), which mixes these methods in; they share its state."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ..console.orders import OrderRun, aim
from ..console.parser import ParseContext, parse
from ..console.translator import Translation
from ..crew.station_reports import situation
from .common import ORDER_TRANSLATE_WAIT
from .news import Prompt
from .state import SessionState

if TYPE_CHECKING:
    from .battle import BattleSession


class OrdersMixin(SessionState):
    def _order_problems(self: BattleSession, problems: list[str]) -> None:
        for p in problems:
            self._log(f"Named order {p}", "caution")

    def _execute_order(self: BattleSession, name: str) -> None:
        order = self.orders.find(name)
        if order is None:
            known = ", ".join(self.orders.orders) or "none yet"
            self._log(f"No named order '{name}' (yours: {known}). See 'help orders'.", "caution")
            return
        if self.order_run is not None and not self.order_run.done:
            self._log(f"Order {self.order_run.order.name} belayed.", "dim")
        self._log(f"Executing order {order.name}" + (f": {order.note}" if order.note else "."), "friend")
        self.order_run = OrderRun(order)
        self._advance_order()

    def _belay(self: BattleSession) -> None:
        run = self.order_run
        if run is None or run.done:
            return          # nothing to belay but the cease fire that came with it
        left = len(run.order.steps) - run.index
        self._log(f"Order {run.order.name} belayed ({left} step{'s' if left != 1 else ''} not run).", "caution")
        self.order_run = None

    def _advance_order(self: BattleSession) -> None:
        """Run the running order's steps until one says wait (or waits on its translation)."""
        run = self.order_run
        while run is not None and not run.done and self.order_run is run:
            if self.world.tick < run.resume_tick:
                return
            step = run.order.steps[run.index]
            if step.is_wait:
                run.resume_tick = self.world.tick + round(step.wait * self.world.rules.ticks_per_cycle)
                run.index += 1
                continue
            line = self.orders.lines.get(step.text)
            if line is not None and line.pending:
                if run.held_since is None:
                    run.held_since = time.monotonic()
                if time.monotonic() - run.held_since < ORDER_TRANSLATE_WAIT:
                    return      # still being translated: the order waits for it
                self._log(f"» {step.text}   (skipped: no translation yet)", "caution")
            elif line is not None and line.error and not line.commands:
                self._log(f"» {step.text}   (skipped: {line.error})", "caution")
            else:
                target = self._target_id()
                for c in (line.commands if line is not None and line.commands else [step.text]):
                    self._run_one(aim(c, target), translate=False, echo="» ")
            run.held_since = None
            run.index += 1
        if run is not None and run.done and self.order_run is run:
            self.order_run = None
            self._log(f"Order {run.order.name} complete.", "dim")

    def _translation_brief(self: BattleSession) -> str:
        """What the translating model may know: the situation, the officers, and the names the console accepts."""
        ctx = self._help_context()
        lines = [situation(ctx)]
        if self.bridge is not None:
            lines.append("Bridge officers (address them with ask <officer> <words>): " + ", ".join(
                f"{o.id} ({o.name}, {o.station})" for o in self.bridge.officers()) + ".")
        allies = [a.name for a in self.allies()]
        if allies:
            lines.append("Our other ships: " + ", ".join(allies) + ".")
        return "\n".join(lines)

    def _would_run(self: BattleSession, line: str) -> str | None:
        """Why a translated line would be rejected, or None: checked before anything runs."""
        if self.player_id is None:
            return "No ship under command."
        if self.bridge is not None and self.bridge.addressed(line) is not None:
            return None
        return parse(line, ParseContext(self.player_id, self.world.observe(self.side))).error

    def dry_run(self: BattleSession, line: str) -> str | None:
        """Why a console line would be refused right now, or None: parsed, and every order in it checked by the
        simulation's own rules without being given (the counsel offers only lines that pass) [E]."""
        from ..sim.commands import Rejected

        why = self._would_run(line)
        if why is not None:
            return why
        ship = self.player
        if ship is None or (self.bridge is not None and self.bridge.addressed(line) is not None):
            return None
        res = parse(line, ParseContext(ship.id, self.world.observe(self.side)))
        for cmd in res.commands:
            held = self.world._held(cmd)
            if held is not None:
                return held
            try:
                cmd.validate(self.world, ship)
            except Rejected as r:
                return str(r)
        return None

    def _translated(self: BattleSession, t: Translation) -> None:
        if t.say:
            self._log(f"Computer: {t.say}", "text")
        if t.error:
            self._log(f"'{t.text}' not interpreted: {t.error}. Type 'help' for the commands.", "caution")
            self._notice(f"Couldn't work out '{t.text}'", "caution", 3.0)
            return
        if t.clarify:
            self._log(f"Computer: {t.clarify}", "caution")
            self._notice(t.clarify, "caution", 5.0)
            self._emit(Prompt(None))
        for c in t.held:
            self._log(f"≈ {c}   (not run: type it yourself if you mean it)", "caution")
        for c in t.commands:
            self._run_one(c, translate=False, echo="≈ ")
        if t.commands and not t.held and not t.clarify:
            self.remember_phrase(t.text, t.commands)     # the same words work at once next time

    def _translate_mode(self: BattleSession, mode: object) -> None:
        tr = self.translator
        if tr is None:
            self._log("No language model is set up, so commands must be typed exactly. See 'help llm'.", "caution")
            return
        if mode is not None:
            tr.mode = str(mode)
            tr.awaiting = False
            self.llm_settings["console"] = tr.mode    # saved with the settings when the battle ends
        self._log({"off": "Plain English is off: commands must be typed exactly.",
                   "fallback": "Plain English is on: anything the console doesn't recognise goes to the model.",
                   "always": "Plain English for everything: every line goes to the model first."}[tr.mode],
                  "dim")


__all__ = ["OrdersMixin"]
