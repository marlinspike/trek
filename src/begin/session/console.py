"""Running typed orders: parsing, the captain's own commands, printouts and the chart.

Part of `BattleSession` (see `session/battle.py`), which mixes these methods in; they share its state."""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..console import reports
from ..console.parser import ParseContext, ParseResult, parse
from ..crew.intents import whole_bridge_stand_down
from ..crew.hails import prisoners_lines
from ..sim.commands import (
    AddressCrew, CeaseFire, Command, DelegateStation, EndObjective, Evasive, SetHelm, SetObjective, StandDown, TakeConn,
)
from .common import CHART, exact_verb
from .news import Commanding, Printout, Request, Show
from .state import SessionState

if TYPE_CHECKING:
    from .battle import BattleSession


# [E] a captain's answer to an officer's proposal, typed or spoken, as Y and N on the subtitle
AYE = frozenset(("make it so", "make it so number one", "make it so, number one", "do it", "yes", "aye", "y",
                 "very well", "proceed", "affirmative", "go ahead", "agreed", "carry on"))
BELAY = frozenset(("no", "n", "negative", "not now", "no thanks"))     # 'belay (that)' still stops the guns


class ConsoleMixin(SessionState):
    def run_console(self: BattleSession, text: str) -> None:
        """Run a console line; ';' separates several commands (as in key macros)."""
        if text.strip().lower().split(None, 1)[:1] == ["key"]:
            self._run_one(text.strip())  # the macro itself may hold several commands
            return
        for part in [t.strip() for t in text.split(";")]:
            if part:
                self._run_one(part)

    def _run_one(self: BattleSession, text: str, translate: bool = True, echo: str = "> ") -> None:
        self._log(f"{echo}{text}", "friend", channel="bridge")
        if self.player_id is None:
            self._log("No ship under command.", "caution")
            return
        said = text.strip().lower().rstrip(".!")
        if echo == "> " and said in AYE and self.accept_proposal():
            return          # [E] 'make it so': the officer's proposal on the screen, as Y would
        if echo == "> " and said in BELAY and self.belay_proposal():
            return
        if echo == "> " and said in AYE and self.translator is None:
            self._log("Nothing waiting on your word, Captain.", "dim")
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
                self.note_ran(text)
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
        known = self.recalled(text) if res.error is not None and translate else None
        if known:          # plain words the model worked out before: no need to ask again
            self._log("  (remembered)", "dim")
            for c in known:
                self._run_one(c, translate=False, echo="≈ ")
            return
        if (translate and tr is not None and not any(n == "translate" for n, _ in res.actions)
                and tr.wants(res.error is None, exact_verb(text) or len(text.split()) >= 2)):
            tr.submit(text, self._translation_brief(), res.error)
            self._log("  … interpreting", "dim")
            return
        self._execute(text, res)

    def _execute_now(self: BattleSession, text: str, res: ParseResult | None = None) -> None:
        """A cease fire or a stand down: at once, never waiting on a language model, and nothing still being
        interpreted may open fire (or take a station) after it."""
        if res is None:
            assert self.player_id is not None
            res = parse(text, ParseContext(self.player_id, self.world.observe(self.side)))
        tr = self.translator
        if tr is not None and tr.busy():
            tr.drop_pending()
            self._log("  (interpretation dropped)", "dim")
        if self.bridge is not None:
            self.bridge.drop_orders()       # nor may an officer's answer still on its way from the model
        self._execute(text, res)

    def _after_captain(self: BattleSession, cmd: Command) -> None:
        """Follow-through on the captain's own orders that hand work back from the officers."""
        ship, b = self.player, self.bridge
        if ship is None:
            return
        if isinstance(cmd, StandDown):
            self._belay()               # a named order running stops too
            self._log("  Every station and the bridge are yours, Captain.", "dim")
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
                          f"Say 'I have nav' to fly evasive manoeuvres yourself.", "dim")
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
                      f"'<officer>, stand down' just that one.", "caution")

    def _execute(self: BattleSession, text: str, res: ParseResult) -> None:
        if res.error:
            self._log(res.error, "caution")
            self._notice(res.error, "caution", 3.0)
            self._cue("deny", 0.7)
            return
        for line in res.info:
            self._log(line, "dim")
        if res.display:
            # a pure display (no orders) stays on the map and refreshes live
            self._show(res.display, text if not res.commands and not res.actions else None)
        for name, val in res.actions:
            self._action(name, val)
        for cmd in res.commands:
            if isinstance(cmd, AddressCrew) and self.bridge is not None and self.player is not None:
                err = cmd.validate_now(self.world, self.player)
                if err:
                    self._log(f"Unable to comply: {err}", "caution")
                    continue
                if self.bridge.judge_address(cmd, self._help_context()):
                    self._log("  … the crew listens", "dim")
                    continue      # the model judges how it lands; the morale follows when it answers
            if isinstance(cmd, SetObjective) and not cmd.officer and self.bridge is not None:
                # "disable their shields" said to nobody in particular: the weapons officer focuses fire on them
                o = self.bridge.crew.officers.get("science" if cmd.goal in ("hunt", "strike") else "tactical")
                if o is not None and cmd.goal != "capture":     # finding a lost ship is the science officer's job
                    cmd.officer = o.id
            reason = self.issue(cmd)
            if reason is None:
                self._cue("confirm", 0.6)     # one chirp however many orders it held
                self._readback(cmd)
                self.style_check(cmd)
                if isinstance(cmd, DelegateStation) and cmd.on:
                    self.ever_delegated.add(cmd.station)
                elif isinstance(cmd, TakeConn) and cmd.officer:
                    self.ever_delegated.update(("helm", "tactical", "engineering", "science"))
                self._after_captain(cmd)
                if isinstance(cmd, AddressCrew) and self.bridge is not None:
                    self._speak(self.bridge.address_reaction(cmd))
        if res.commands:
            self.note_ran(text)
        if res.commands and self.bridge is not None:
            self.bridge.captain_ran(text, self.world.tick, self.world.rules.ticks_per_cycle)

    def _show(self: BattleSession, lines: list[str], live_cmd: str | None) -> None:
        for line in lines:
            self._log(line, "text", mono=True)
        self._emit(Printout(tuple(lines), live_cmd))

    def preview(self: BattleSession, text: str) -> ParseResult | None:
        """What a line would do if run now, without running it (the console's preview), or None."""
        if self.player_id is None:
            return None
        return parse(text, ParseContext(self.player_id, self.world.observe(self.side)))

    def understood(self: BattleSession, line: str) -> str | None:
        """Why a heard line would not run as it stands (a voice order is never guessed at), or None if it will:
        a console order, a named order, a phrase learned before, words to an officer, or anything at all when a
        language model is there to interpret it."""
        if self.player_id is None or self.translator is not None:
            return None
        if self.bridge is not None and self.bridge.addressed(line) is not None:
            return None
        if self.orders.find(line) is not None or self.recalled(line):
            return None
        return parse(line, ParseContext(self.player_id, self.world.observe(self.side))).error

    def display(self: BattleSession, live: str) -> list[str] | None:
        """A live printout as it stands now (`Printout.live`): the chart, or a display order run again."""
        if live == CHART:
            return self._chart_lines()
        if self.player_id is None:
            return None
        res = parse(live, ParseContext(self.player_id, self.world.observe(self.side)))
        return res.display if res.display and not res.error else None

    def _chart_lines(self: BattleSession) -> list[str]:
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

    def _action(self: BattleSession, name: str, val: object) -> None:
        if name == "pause":
            self.paused = True
        elif name == "resume":
            self.paused = False
        elif name == "speed":
            self.speed = float(val)  # type: ignore[arg-type]
        elif name == "chart":
            self._chart(val)  # type: ignore[arg-type]
        elif name == "quit":
            self.world.end_simulation()
            self._drain_events()
            self._emit(Show("debrief"))
            self._crew_outcome()
        elif name == "transfer":
            self._transfer(int(val))  # type: ignore[call-overload]
        elif name == "ask":
            assert isinstance(val, tuple)
            who, words = str(val[0]), str(val[1])
            o = self.bridge.find(who) if self.bridge is not None else None
            if o is None:
                self._log(f"No officer called '{who}'. Type 'crew' to see who is on the bridge.", "caution")
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
        elif name == "reinforcements":
            self._reinforcements()
        elif name == "hail":
            assert isinstance(val, tuple)
            self.hail(val[0], str(val[1]))
        elif name == "prisoners":
            for line in prisoners_lines(self.world, self.side):
                self._log(line, "text")
        elif name == "alert":
            self.alert(val)  # type: ignore[arg-type]
        elif name == "record":
            self.record(val)  # type: ignore[arg-type]
        elif name == "style":
            self.choose_style(val)  # type: ignore[arg-type]
        elif name == "counsel":
            self.counsel_order(val)  # type: ignore[arg-type]
        else:
            # display range, the manual, sound, the HUD and Bridge settings, key macros, voice orders: the
            # presentation's business, not the game's
            self._emit(Request(name, val))

    def _chart(self: BattleSession, opts: dict[str, object]) -> None:
        show = True
        if "auto" in opts:
            self.chart_auto = bool(opts["auto"])
            if not self.chart_auto:
                self._emit(Printout((), CHART))     # an empty live chart: take it off the map
                self._log("Chart display off.", "dim")
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
            self._show(self._chart_lines(), CHART)

    def _transfer(self: BattleSession, sid: int) -> None:
        reason = self.battle.transfer_command(sid)
        if reason is not None:
            self._log(reason, "caution")
            self._notice(reason, "caution", 3.0)
            return
        self.player_id = sid
        self.obs = self.world.observe(self.side)
        self._emit(Commanding(sid))
        p = self.player
        self._log(f"You beam aboard the {p.name if p else 'ship'} and take command.", "good")

    def _status_report(self: BattleSession) -> None:
        p = self.player
        if p is None:
            return
        self._log(f"{p.name}: warp {p.warp:.1f}, course {p.course:.0f}, crew {p.crew}, hull "
                  f"{max(0.0, p.structure) / p.structure_max * 100:.0f}%, torps {p.torps_remaining}, probes {p.probes_remaining}",
                  "text")


__all__ = ["ConsoleMixin"]
