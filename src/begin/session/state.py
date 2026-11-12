"""The battle session's state, declared in one place for the parts that share it (`BattleSession.__init__` sets it)."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from ..battle import Battle
    from ..console.orders import OrderBook, OrderRun
    from ..console.translator import Translator
    from ..crew.career import Career
    from ..crew.conversation import Bridge
    from ..crew.hails import Comms
    from ..crew.proposals import Proposal, Proposer
    from ..sim.events import Event
    from ..sim.observation import Observation
    from ..sim.scoring import Assessment
    from ..sim.world import World
    from .command import Recording
    from .common import TourLink
    from .hit_report import HitReport
    from .prefs import BridgePrefs


class SessionState:
    battle: Battle
    world: World
    player_id: int | None
    side: int
    tour: TourLink | None
    paused: bool
    speed: float
    acc: float
    obs: Observation
    hits: HitReport
    assessment: Assessment
    hidden: dict[str, object]
    bridge: Bridge | None
    translator: Translator | None
    llm_settings: dict[str, object]
    comms: Comms
    orders: OrderBook
    order_run: OrderRun | None
    deeds: list[Event]
    prefs: BridgePrefs
    proposer: Proposer
    proposal: Proposal | None
    _propose_t: float
    captain_typing: bool
    busy_elsewhere: bool
    career: Career
    alerts: dict[str, tuple[str, list[str]]]
    condition: str | None
    recording: Recording | None
    ran: list[str]
    style: str | None
    style_broken: str | None
    ribbon_won: str | None
    _career_done: bool
    ever_delegated: set[str]
    trust_news: list[str]
    phrasebook: dict[str, list[str]]
    chart_auto: bool
    chart_sort: str
    chart_hidden: set[int]
    chart_all: bool
    chart_origin: int | None


__all__ = ["SessionState"]
