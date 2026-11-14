"""The bridge's voices and the officers' proposals [E].

Part of `BattleSession` (see `session/battle.py`), which mixes these methods in; they share its state.

- Readbacks: every order the captain gives (typed, from the wheel, a proposal or by voice: they all come
  through the console) is read back by the officer at that station, in a sentence built from the order itself.
- Proposals: now and then an officer offers an order; the captain makes it so (Y) or belays it (N). A Veteran
  officer acts alone when an urgent proposal lapses.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from ..console.readback import STATION_TITLES, readback
from ..crew.officers import station_of
from ..crew.proposals import Proposal
from ..sim.commands import Command
from .news import Voice
from .state import SessionState

if TYPE_CHECKING:
    from .battle import BattleSession

VETERAN_LINES = ("evasive", "raise shields all")    # what a Veteran does unasked when an urgent proposal lapses


class VoicesMixin(SessionState):
    # ------------------------------------------------------------ names

    def ship_name(self: BattleSession, sid: int) -> str:
        """A ship as the captain knows her: her name if identified, else her contact number."""
        return self.obs.name_of(sid)

    def _station_officer(self: BattleSession, station: str | None) -> tuple[str, str | None]:
        """(name, officer id) of whoever answers for a station: its officer, or the station itself."""
        if station is None:
            return "", None
        b = self.bridge
        o = b.crew.officers.get(station) if b is not None else None
        if o is not None:
            return o.name, o.id
        return STATION_TITLES.get(station, station.title()), None

    # ------------------------------------------------------------ voices

    def _voice(self: BattleSession, speaker: str, text: str, tone: str, station: str | None = None,
               officer: str | None = None, urgent: bool = False, kind: str = "report",
               faction: str | None = None) -> None:
        """Someone says a line aloud; the presentation decides how much of it to show and to speak."""
        self._emit(Voice(speaker, text, tone, station, officer, urgent, kind, faction))

    def _readback(self: BattleSession, cmd: Command) -> None:
        """The officer at the order's station says back exactly what they will do."""
        mode = self.prefs.readbacks
        if mode == "off":
            self._log(f"  {cmd.describe()}: acknowledged", "dim")
            return
        station = station_of(cmd)
        name, oid = self._station_officer(station)
        line = readback(cmd, self.ship_name)
        self._log(f"  {name + ': ' if name else ''}{line}", "readback", channel="bridge")
        if mode == "voiced":
            self._voice(name, line, "crew" if name else "dim", station, oid, kind="readback")

    # ------------------------------------------------------------ officers' proposals

    def _proposals_tick(self: BattleSession, dt: float) -> None:
        p = self.proposal
        if isinstance(p, Proposal):
            if not self.paused:
                p.age += dt
            if p.age >= p.life:
                self.proposal = None            # it lapses quietly: the captain was busy
                if p.urgent and self.career.acts_alone(p.officer) and p.line in VETERAN_LINES:
                    # a Veteran officer doesn't wait to be told twice when the ship is in danger
                    self._log(f"{p.name}: Making it so, Captain.", "crew", channel="bridge")
                    self._voice(p.name, "Making it so, Captain.", "crew", p.station, p.officer, urgent=True)
                    self.run_console(p.line)
            return
        crew, ship = self.battle.crew, self.player
        if self.bridge is not None:          # one voice for incoming torpedoes: the proposal, not advice as well
            self.bridge.proposals_on = self.prefs.proposals != "off" and self.style != "green"
        if (crew is None or ship is None or not ship.alive or self.paused or self.world.outcome.over
                or crew.ship_id != ship.id or self.prefs.proposals == "off" or self.busy_elsewhere):
            return
        self._propose_t -= dt
        if self._propose_t > 0:
            return
        self._propose_t = 0.5
        if self.style == "green":
            return                              # a green crew only follows orders
        new = self.proposer.next(self.obs, ship, crew.officers, self.world.time, self.prefs.proposals,
                                 self.captain_typing, self.career.offers_while_typing)
        if new is not None:
            new.bonus = self.career.proposal_bonus(new.officer)
            self.proposal = new
            keys = "Ctrl+Y makes it so" if self.captain_typing else "Y makes it so, N belays"
            self._log(f"{new.name}: {new.text}  ({keys})", "crew", channel="bridge")
            self._cue("lock", 0.3)

    def accept_proposal(self: BattleSession) -> bool:
        p = self.proposal
        if not isinstance(p, Proposal):
            return False
        self.proposal = None
        self.career.proposal(p.officer, accepted=True)
        self.run_console(p.line)
        return True

    def belay_proposal(self: BattleSession) -> bool:
        p = self.proposal
        if not isinstance(p, Proposal):
            return False
        self.proposal = None
        self.proposer.belay(p, self.world.time)
        self.career.proposal(p.officer, accepted=False)
        self._log(f"  {p.name}: Aye, Captain.", "dim", channel="bridge")
        return True


__all__ = ["VETERAN_LINES", "VoicesMixin"]
