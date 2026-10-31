"""Named orders from config/orders.toml, and the translator that turns plain words into console commands.

Part of `BattleScene` (see `ui/battle_scene.py`), which mixes these methods in; they share its state."""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

from ...console.orders import OrderRun, aim
from ...console.parser import ParseContext, parse
from ...console.translator import Translation
from ...crew.conversation import situation
from .. import theme
from .common import ORDER_TRANSLATE_WAIT
from .state import SceneState

if TYPE_CHECKING:
    from ..battle_scene import BattleScene


class OrdersMixin(SceneState):
    def _order_problems(self: BattleScene, problems: list[str]) -> None:
        for p in problems:
            self._log(f"Named order {p}", theme.CAUTION)

    def _execute_order(self: BattleScene, name: str) -> None:
        order = self.orders.find(name)
        if order is None:
            known = ", ".join(self.orders.orders) or "none yet"
            self._log(f"No named order '{name}' (yours: {known}). See 'help orders'.", theme.CAUTION)
            return
        if self.order_run is not None and not self.order_run.done:
            self._log(f"Order {self.order_run.order.name} belayed.", theme.TEXT_DIM)
        self._log(f"Executing order {order.name}" + (f": {order.note}" if order.note else "."), theme.FRIEND)
        self.order_run = OrderRun(order)
        self._advance_order()

    def _belay(self: BattleScene) -> None:
        run = self.order_run
        if run is None or run.done:
            return          # nothing to belay but the cease fire that came with it
        left = len(run.order.steps) - run.index
        self._log(f"Order {run.order.name} belayed ({left} step{'s' if left != 1 else ''} not run).", theme.CAUTION)
        self.order_run = None

    def _advance_order(self: BattleScene) -> None:
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
                self._log(f"» {step.text}   (skipped: no translation yet)", theme.CAUTION)
            elif line is not None and line.error and not line.commands:
                self._log(f"» {step.text}   (skipped: {line.error})", theme.CAUTION)
            else:
                target = self._target_id()
                for c in (line.commands if line is not None and line.commands else [step.text]):
                    self._run_one(aim(c, target), translate=False, echo="» ")
            run.held_since = None
            run.index += 1
        if run is not None and run.done and self.order_run is run:
            self.order_run = None
            self._log(f"Order {run.order.name} complete.", theme.TEXT_DIM)

    def _translation_brief(self: BattleScene) -> str:
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

    def _would_run(self: BattleScene, line: str) -> str | None:
        """Why a translated line would be rejected, or None: checked before anything runs."""
        if self.player_id is None:
            return "No ship under command."
        if self.bridge is not None and self.bridge.addressed(line) is not None:
            return None
        return parse(line, ParseContext(self.player_id, self.world.observe(self.side))).error

    def _translated(self: BattleScene, t: Translation) -> None:
        if t.say:
            self._log(f"Computer: {t.say}", theme.TEXT)
        if t.error:
            self._log(f"'{t.text}' not interpreted: {t.error}. Type 'help' for the commands.", theme.CAUTION)
            self.toast = (f"Couldn't work out '{t.text}'", theme.CAUTION, 3.0)
            return
        if t.clarify:
            self._log(f"Computer: {t.clarify}", theme.CAUTION)
            self.toast = (t.clarify, theme.CAUTION, 5.0)
            self.console_focus = True
        for c in t.held:
            self._log(f"≈ {c}   (not run: type it yourself if you mean it)", theme.CAUTION)
        for c in t.commands:
            self._run_one(c, translate=False, echo="≈ ")

    def _translate_mode(self: BattleScene, mode: object) -> None:
        tr = self.translator
        if tr is None:
            self._log("No language model is set up, so commands must be typed exactly. See 'help llm'.", theme.CAUTION)
            return
        if mode is not None:
            tr.mode = str(mode)
            tr.awaiting = False
            self.llm_settings["console"] = tr.mode    # saved with the settings when the battle ends
        self._log({"off": "Plain English is off: commands must be typed exactly.",
                   "fallback": "Plain English is on: anything the console doesn't recognise goes to the model.",
                   "always": "Plain English for everything: every line goes to the model first."}[tr.mode],
                  theme.TEXT_DIM)


__all__ = ["OrdersMixin"]
