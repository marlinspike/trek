"""Running typed orders: parsing, the captain's own commands, printouts, the chart and the manual.

Part of `BattleScene` (see `ui/battle_scene.py`), which mixes these methods in; they share its state."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ...console import reports
from ...console.parser import ParseContext, ParseResult, parse
from ...crew.intents import whole_bridge_stand_down
from ...crew.hails import prisoners_lines
from ...sim.commands import AddressCrew, CeaseFire, Command, DelegateStation, EndObjective, Evasive, SetHelm, SetObjective, StandDown
from .. import theme
from .common import exact_verb
from .state import SceneState

if TYPE_CHECKING:
    from ..battle_scene import BattleScene


class ConsoleMixin(SceneState):
    def run_console(self: BattleScene, text: str) -> None:
        """Run a console line; ';' separates several commands (as in key macros)."""
        if text.strip().lower().split(None, 1)[:1] == ["key"]:
            self._run_one(text.strip())  # the macro itself may hold several commands
            return
        for part in [t.strip() for t in text.split(";")]:
            if part:
                self._run_one(part)

    def _run_one(self: BattleScene, text: str, translate: bool = True, echo: str = "> ") -> None:
        self._log(f"{echo}{text}", theme.FRIEND)
        if self.player_id is None:
            self._log("No ship under command.", theme.CAUTION)
            return
        if translate and echo == "> " and self.orders.find(text) is not None:
            self._execute_order(text)       # a named order, called by name alone
            return
        if whole_bridge_stand_down(text):
            self._execute_now("stand down")     # "everyone stop", "all hands stand down": the whole bridge, at once
            return
        if self.bridge is not None:
            pieces = self.bridge.split_addressed(text)
            if len(pieces) > 1:                 # "worf, target their shields and spock, take the helm"
                for piece in pieces:
                    self._run_one(piece, translate, "  > ")
                return
            hit = self.bridge.addressed(text)
            if hit is not None:
                self._ask(*hit)
                return
            holder = self.bridge.find(self.player.conn) if self.player is not None and self.player.conn else None
            if holder is not None and self.bridge.handover(text) == "release":
                self._ask(holder, text)   # "I have the bridge", said to whoever has it
                return
        res = parse(text, ParseContext(self.player_id, self.world.observe(self.side)))
        tr = self.translator
        if any(isinstance(c, (CeaseFire, StandDown)) for c in res.commands):
            self._execute_now(text, res)
            return
        if (translate and tr is not None and not any(n == "translate" for n, _ in res.actions)
                and tr.wants(res.error is None, exact_verb(text) or len(text.split()) >= 2)):
            tr.submit(text, self._translation_brief(), res.error)
            self._log("  … interpreting", theme.TEXT_DIM)
            return
        self._execute(text, res)

    def _execute_now(self: BattleScene, text: str, res: ParseResult | None = None) -> None:
        """A cease fire or a stand down: at once, never waiting on a language model, and nothing still being
        interpreted may open fire (or take a station) after it."""
        if res is None:
            assert self.player_id is not None
            res = parse(text, ParseContext(self.player_id, self.world.observe(self.side)))
        tr = self.translator
        if tr is not None and tr.busy():
            tr.drop_pending()
            self._log("  (interpretation dropped)", theme.TEXT_DIM)
        if self.bridge is not None:
            self.bridge.drop_orders()       # nor may an officer's answer still on its way from the model
        self._execute(text, res)

    def _after_captain(self: BattleScene, cmd: Command) -> None:
        """Follow-through on the captain's own orders that hand work back from the officers."""
        ship, b = self.player, self.bridge
        if ship is None:
            return
        if isinstance(cmd, StandDown):
            self._belay()               # a named order running stops too
            self._log("  Every station and the bridge are yours, Captain.", theme.TEXT_DIM)
            return
        if isinstance(cmd, DelegateStation) and not cmd.on and b is not None:
            # taking a station back stands down the officer it was delegated to, and only them: what they were working
            # on ends ("I have weapons" stops Worf's disable), while the rest of the bridge keeps at its own work
            o = b.crew.officers.get(cmd.station)
            owners = {o.id} | ({""} if cmd.station == "science" else set()) if o is not None else set()
            for who in sorted({ob.officer for ob in ship.objectives} & owners):
                self.issue(EndObjective(ship_id=ship.id, officer=who, reason="station taken back"))
            return
        if b is None:
            return
        if isinstance(cmd, Evasive) and cmd.on and "helm" in ship.delegated and "helm" in b.crew.officers:
            o = b.find(ship.conn) if ship.conn else b.crew.officers["helm"]
            if o is not None:
                self._log(f"  {o.name} is flying the ship and dodges torpedoes as part of it. "
                          f"Say 'I have nav' to fly evasive manoeuvres yourself.", theme.TEXT_DIM)
            return
        all_stop = isinstance(cmd, SetHelm) and cmd.warp == 0.0 and cmd.course is None
        if not (isinstance(cmd, CeaseFire) or all_stop):
            return
        # the captain said stop, but someone is still at work: say who, and how to stop them
        busy: list[str] = []
        holder = b.find(ship.conn) if ship.conn else None
        if holder is not None:
            busy.append(f"{holder.name} has the bridge")
        elif "helm" in ship.delegated and "helm" in b.crew.officers:
            busy.append(f"{b.crew.officers['helm'].name} has the helm")
        if all_stop:
            for ob in ship.objectives:
                o = b.find(ob.officer) if ob.officer else b.crew.officers.get("science")
                if o is not None:
                    busy.append(f"{o.name} is still working to {ob.describe()}")
                    break
        if busy:
            self._log(f"  {'; '.join(busy)}. 'stand down' takes every station back and stops them; "
                      f"'<officer>, stand down' just that one.", theme.CAUTION)

    def _execute(self: BattleScene, text: str, res: ParseResult) -> None:
        if res.error:
            self._log(res.error, theme.CAUTION)
            self.toast = (res.error, theme.CAUTION, 3.0)
            return
        for line in res.info:
            self._log(line, theme.TEXT_DIM)
        if res.display:
            # a pure display (no orders) stays on the map and refreshes live
            self._show(res.display, text if not res.commands and not res.actions else None)
        for name, val in res.actions:
            self._action(name, val)
        for cmd in res.commands:
            if isinstance(cmd, AddressCrew) and self.bridge is not None and self.player is not None:
                err = cmd.validate_now(self.world, self.player)
                if err:
                    self._log(f"Unable to comply: {err}", theme.CAUTION)
                    continue
                if self.bridge.judge_address(cmd, self._help_context()):
                    self._log("  … the crew listens", theme.TEXT_DIM)
                    continue      # the model judges how it lands; the morale follows when it answers
            if isinstance(cmd, SetObjective) and not cmd.officer and self.bridge is not None:
                # "disable their shields" said to nobody in particular: the weapons officer focuses fire on them
                o = self.bridge.crew.officers.get("tactical")
                if o is not None and cmd.goal != "capture":
                    cmd.officer = o.id
            reason = self.issue(cmd)
            if reason is None:
                self._log(f"  {cmd.describe()}: acknowledged", theme.TEXT_DIM)
                self._after_captain(cmd)
                if isinstance(cmd, AddressCrew) and self.bridge is not None:
                    self._speak(self.bridge.address_reaction(cmd))
        if res.commands and self.bridge is not None:
            self.bridge.captain_ran(text, self.world.tick, self.world.rules.ticks_per_cycle)

    def _show(self: BattleScene, lines: list[str], live_cmd: str | None) -> None:
        for line in lines:
            self._log(line, theme.TEXT, mono=True)
        self.printout = list(lines)
        self.printout_cmd = live_cmd
        self.printout_tick = self.world.tick

    def _refresh_printout(self: BattleScene) -> None:
        if self.printout is None or self.world.tick - self.printout_tick < 5:
            return
        self.printout_tick = self.world.tick
        if self.printout_cmd == "\0chart":
            self.printout = self._chart_lines()
        elif self.printout_cmd and self.player_id is not None:
            res = parse(self.printout_cmd, ParseContext(self.player_id, self.world.observe(self.side)))
            if res.display and not res.error:
                self.printout = res.display

    def _chart_lines(self: BattleScene) -> list[str]:
        obs = self.world.observe(self.side)
        origin = None
        if self.chart_origin is not None:
            origin = obs.own(self.chart_origin) or obs.contact(self.chart_origin)
        if origin is None:
            origin = self.player
        if origin is None:
            return ["No ship to chart from."]
        return reports.chart_lines(obs, origin, self.player_id or -1, self.chart_sort,
                                   frozenset(self.chart_hidden), self.chart_all)

    def _action(self: BattleScene, name: str, val: object) -> None:
        if name == "pause":
            self.paused = True
        elif name == "resume":
            self.paused = False
        elif name == "speed":
            self.speed = float(val)  # type: ignore[arg-type]
        elif name == "range":
            if val is None:
                self._log(f"Display range {self.display_range():,.0f} units.", theme.TEXT_DIM)
            else:
                r = float(val)  # type: ignore[arg-type]
                self.set_display_range(r)
                self._log(f"Display range set to {r:,.0f} units.", theme.TEXT_DIM)
        elif name == "chart":
            self._chart(val)  # type: ignore[arg-type]
        elif name == "quit":
            self.world.end_simulation()
            self._drain_events()
            self.overlay = "debrief"
            self._crew_outcome()
        elif name == "transfer":
            self._transfer(int(val))  # type: ignore[call-overload]
        elif name == "key":
            self._key_binding(val)  # type: ignore[arg-type]
        elif name == "manual":
            self.open_manual(val)  # type: ignore[arg-type]
        elif name == "ask":
            assert isinstance(val, tuple)
            who, words = str(val[0]), str(val[1])
            o = self.bridge.find(who) if self.bridge is not None else None
            if o is None:
                self._log(f"No officer called '{who}'. Type 'crew' to see who is on the bridge.", theme.CAUTION)
            else:
                self._ask(o, words)
        elif name == "crew":
            self._crew_command(val)
        elif name == "conn":
            self._conn_command(val)
        elif name == "translate":
            self._translate_mode(val)
        elif name == "execute":
            self._execute_order(str(val))
        elif name == "orders":
            self._show(self.orders.listing(), None)
        elif name == "belay":
            self._belay()
        elif name == "sound":
            self._sound(val)
        elif name == "reinforcements":
            self._reinforcements()
        elif name == "hail":
            assert isinstance(val, tuple)
            self.hail(val[0], str(val[1]))
        elif name == "prisoners":
            for line in prisoners_lines(self.world, self.side):
                self._log(line, theme.TEXT)
        elif name == "hud":
            if val is not None:
                self.hud_detail = val == "detail"
            self._log("Panels show every number." if self.hud_detail else
                      "Panels show what matters; hover one for its numbers. 'hud detail' shows them all.", theme.TEXT_DIM)

    def _chart(self: BattleScene, opts: dict[str, object]) -> None:
        show = True
        if "auto" in opts:
            self.chart_auto = bool(opts["auto"])
            if not self.chart_auto:
                if self.printout_cmd == "\0chart":
                    self.printout = None
                self._log("Chart display off.", theme.TEXT_DIM)
                return
        if "sort" in opts:
            self.chart_sort = str(opts["sort"])
        if "all" in opts:
            self.chart_all = True
            self.chart_hidden.clear()
        if "include" in opts:
            self.chart_hidden.discard(int(opts["include"]))  # type: ignore[call-overload]
        if "exclude" in opts:
            self.chart_hidden.add(int(opts["exclude"]))  # type: ignore[call-overload]
            self.chart_all = False
        if "origin" in opts:
            self.chart_origin = int(opts["origin"])  # type: ignore[call-overload]
        elif "show" in opts:
            self.chart_origin = None
        if show:
            self._show(self._chart_lines(), None)
            self.printout_cmd = "\0chart"

    def _transfer(self: BattleScene, sid: int) -> None:
        reason = self.battle.transfer_command(sid)
        if reason is not None:
            self._log(reason, theme.CAUTION)
            self.toast = (reason, theme.CAUTION, 3.0)
            return
        self.player_id = sid
        self.cam.follow = sid
        self.obs = self.world.observe(self.side)
        p = self.player
        self._log(f"You beam aboard the {p.name if p else 'ship'} and take command.", theme.GOOD)

    def open_manual(self: BattleScene, query: str | None = None) -> None:
        msg = self.manual.open(query)
        if msg:
            self._log(msg, theme.TEXT_DIM)
        self.overlay = "manual"
        self.console_focus = False
        pygame.key.start_text_input()

    def _close_manual(self: BattleScene) -> None:
        if self.overlay == "manual":
            self.overlay = None

    def _try_command(self: BattleScene, text: str) -> None:
        self._close_manual()
        self.console = text
        self.console_focus = True
        pygame.key.start_text_input()

    def _status_report(self: BattleScene) -> None:
        p = self.player
        if p is None:
            return
        self._log(f"{p.name}: warp {p.warp:.1f}, course {p.course:.0f}, crew {p.crew}, hull "
                  f"{max(0.0, p.structure) / p.structure_max * 100:.0f}%, torps {p.torps_remaining}, probes {p.probes_remaining}",
                  theme.TEXT)


__all__ = ["ConsoleMixin"]
