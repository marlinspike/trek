"""The bridge officers and hailing frequencies: asking, ordering, handing over the conn, the crew's reactions.

Part of `BattleScene` (see `ui/battle_scene.py`), which mixes these methods in; they share its state."""

from __future__ import annotations

from typing import TYPE_CHECKING

import pygame

from ...console.parser import ParseContext, parse
from ...crew.characters import OfficerProfile
from ...crew.conversation import Utterance
from ...crew.officers import STATION_COMMANDS, Activity, station_of
from ...sim.commands import CeaseFire, DelegateStation, EndObjective, ManageRepairs, SetObjective, TakeConn, offensive_fire
from ...sim.events import Event
from ...sim.observation import Observation
from .. import theme
from .common import HAIL_ORDER
from .state import SceneState

if TYPE_CHECKING:
    from ..battle_scene import BattleScene


class CommsMixin(SceneState):
    def _activity(self: BattleScene, obs: Observation) -> list[Activity]:
        crew = self.battle.crew
        if crew is None or self.player_id is None or crew.ship_id != self.player_id:
            return []
        return crew.activity(obs)

    def _officer_name(self: BattleScene, oid: str) -> str:
        o = self.bridge.find(oid) if self.bridge is not None else None
        return o.name if o is not None else oid

    def hail(self: BattleScene, target: int | None, words: str) -> None:
        """Open a channel to an enemy captain (or every one on sensors) and say `words` [E]."""
        p = self.player
        if p is None or not p.alive:
            self._log("No ship under command.", theme.CAUTION)
            return
        self._speak(self.comms.hail(p, target, words, self.issue))

    def open_channel(self: BattleScene, sid: int) -> None:
        """The Hail button: open a channel (they answer), then the console waits for the captain's words."""
        self.hail(sid, "")
        name = self.obs.contact(sid)
        label = name.label.split(" (")[0] if name is not None and name.identified else f"#{sid}"
        self.console = f"hail {label} "
        self.console_focus = True
        pygame.key.start_text_input()

    def _comms_button(self: BattleScene, line: str) -> None:
        if line.startswith("\0type:"):
            self.console = line[len("\0type:"):]
            self.console_focus = True
            pygame.key.start_text_input()
            return
        self.run_console(line)

    def _ask(self: BattleScene, officer: object, words: str) -> None:
        if self.bridge is None:
            return
        assert isinstance(officer, OfficerProfile)
        if HAIL_ORDER.match(words):
            # "worf, hail the Gr'oth" / "seven, open a channel to them": the officer opens it, the captain speaks
            res = parse(HAIL_ORDER.sub("hail ", words, count=1), ParseContext(self.player_id, self.world.observe(self.side)))
            if res.error:
                self._speak([Utterance(officer.id, officer.title, res.error, "caution")])
                return
            self._speak([Utterance(officer.id, officer.title, "Channel open, Captain.")])
            for name, val in res.actions:
                if name == "hail":
                    self.hail(val[0], str(val[1]))  # type: ignore[index]
            return
        self._speak(self.bridge.ask(officer, words, self._help_context(), self._officer_run))

    def _conn(self: BattleScene, who: str | None) -> str | None:
        """Hand the bridge to an officer, or take it back. Returns why not, or None."""
        ship, b = self.player, self.bridge
        if ship is None or b is None:
            return "No bridge crew aboard."
        if who is None:
            if not ship.conn:
                return "You already have the bridge, Captain."
            return self.issue(TakeConn(ship_id=ship.id, officer=""))
        o = b.find(who)
        if o is None:
            return f"No officer called '{who}'. Type 'crew' to see who is on the bridge."
        if ship.conn == o.id:
            return f"{o.name} already has the bridge."
        return self.issue(TakeConn(ship_id=ship.id, officer=o.id))

    def _conn_command(self: BattleScene, who: object) -> None:
        """`conn <officer>` / `conn captain` typed at the console: the officer answers as if told aloud."""
        ship, b = self.player, self.bridge
        before = ship.conn if ship is not None else ""
        err = self._conn(None if who is None else str(who))
        if err:
            self._log(err, theme.CAUTION)
            return
        if b is not None and ship is not None:
            o = b.find(ship.conn or before)
            if o is not None:
                self._speak(b.handover_lines(o, bool(ship.conn)))

    def _officer_run(self: BattleScene, line: str, officer: object) -> str | None:
        """Carry out a console line an officer was told (or decided) to run; only their own stations."""
        assert isinstance(officer, OfficerProfile)
        if self.player_id is None:
            return "No ship under command."
        res = parse(line, ParseContext(self.player_id, self.world.observe(self.side)))
        if res.error:
            return res.error
        if res.actions and not res.commands:
            conn = [v for n, v in res.actions if n == "conn"]
            if conn:   # the captain told this officer to take (or hand back) the bridge
                return self._conn(None if conn[0] is None else str(conn[0]))
            return "That is for the captain to do."
        allowed = set(officer.advises) | {officer.station}
        if self.player is not None and self.player.conn == officer.id:
            allowed |= set(STATION_COMMANDS)   # in command of the bridge
        for cmd in res.commands:
            if isinstance(cmd, (ManageRepairs, CeaseFire, SetObjective, EndObjective)) or (
                    isinstance(cmd, DelegateStation) and not cmd.on):
                continue       # any officer can direct repairs, cease fire, hand a station back or take an objective
            st = cmd.station if isinstance(cmd, DelegateStation) else station_of(cmd)
            if st is None or st not in allowed:
                return "That is not my station, Captain."
        if self.player is not None and self.player.hold_fire and any(offensive_fire(c) for c in res.commands):
            return "We are holding fire on your order, Captain. Say 'open fire' to release it."
        for cmd in res.commands:
            cmd.source = officer.title
            if isinstance(cmd, SetObjective):
                cmd.officer = officer.id   # the officer who was asked does the work
            reason = self.issue(cmd)
            if reason:
                return reason
            self._log(f"  {cmd.describe()}: done", theme.TEXT_DIM)
            if isinstance(cmd, DelegateStation) and not cmd.on:
                self._after_captain(cmd)     # "seven, I have weapons": Worf, who had them, stands down
        if res.display:
            self._show(res.display, None)
        return None

    def _speak(self: BattleScene, lines: list[Utterance]) -> None:
        tone = {"crew": theme.CREW, "caution": theme.CAUTION, "dim": theme.TEXT_DIM, "enemy": theme.HAIL}
        for u in lines:
            self._log(f"{u.speaker}: {u.text}", tone.get(u.tone, theme.CREW))
            for c in u.commands:
                self._log(f"    › {c}", theme.TEXT_DIM)

    def address_crew(self: BattleScene) -> None:
        """Open the console ready for a speech to the crew."""
        self.console = "address crew "
        self.console_focus = True

    def address(self: BattleScene, name: str) -> None:
        """Open the console ready to speak to an officer."""
        self.console = f"{name}, "
        self.console_focus = True

    def _crew_react(self: BattleScene, events: list[Event]) -> None:
        self._speak(self.comms.react(events, self.player))
        if self.bridge is not None and self.player_id is not None:
            self._speak(self.bridge.react(events, self._help_context()))

    def _crew_outcome(self: BattleScene) -> None:
        if self.bridge is None:
            return
        o = self.world.outcome
        won = None if o.winner is None else (o.winner == self.side)
        self._speak(self.bridge.outcome(won))
        self.bridge.save(self.hidden)

    def _crew_command(self: BattleScene, val: object) -> None:
        b = self.bridge
        if b is None:
            self._log("No bridge crew aboard.", theme.CAUTION)
            return
        if isinstance(val, tuple) and val and val[0] == "chatter":
            b.chatter = bool(val[1])
            self._log(f"Officer chatter {'on' if b.chatter else 'off'}.", theme.TEXT_DIM)
            return
        ship = self.player
        holder = b.find(ship.conn) if ship is not None and ship.conn else None
        lines = ["BRIDGE CREW:", f"Command: {holder.title + ' has the bridge' if holder else 'the captain has the bridge'}",
                 "Station      Officer                     Running   Rapport"]
        for st, o in b.crew.officers.items():
            on = ship is not None and st in ship.delegated
            mood = b.relationships.get(o.id).mood
            lines.append(f"{st.title():<12} {o.title:<27} {'officer' if on else 'captain':<9} {mood}")
        lines.append("delegate <station>|all · assume <station>|all · conn <officer>|captain · <officer>, <words>")
        self._show(lines, None)


__all__ = ["CommsMixin"]
