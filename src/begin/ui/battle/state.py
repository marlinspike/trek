"""The battle screen's state, declared in one place for the parts that share it (`BattleScene.__init__` sets it)."""

from __future__ import annotations

from typing import TYPE_CHECKING, Callable

import pygame

if TYPE_CHECKING:
    from ...battle import Battle
    from ...console.orders import OrderBook, OrderRun
    from ...console.translator import Translator
    from ...crew.conversation import Bridge
    from ...crew.hails import Comms
    from ...sim.events import Event
    from ...sim.observation import Observation
    from ...sim.scoring import Assessment
    from ...sim.world import World
    from .. import theme
    from ..audio import Audio
    from ..camera import Camera
    from ..hit_report import HitReport
    from ..hud import Panel, TabbedPanel
    from ..manual import ManualView
    from ..tactical import Snapshot, TacticalView
    from ..tween import Tweens
    from ..widgets import UI
    from .common import LogLine, TourLink


class SceneState:
    battle: Battle
    world: World
    player_id: int | None
    side: int
    on_exit: Callable[[], None]
    exit_label: str
    tour: TourLink | None
    ui: UI
    paused: bool
    speed: float
    acc: float
    omniscient: bool
    cam: Camera
    view: TacticalView
    obs: Observation
    prev: Snapshot | None
    now: Snapshot
    log: list[LogLine]
    console: str
    console_focus: bool
    history: list[str]
    hist_i: int
    toast: tuple[str, theme.Color, float] | None
    hits: HitReport
    overlay: str | None
    side_tabs: TabbedPanel
    panels: list[Panel]
    selected_ally: int | None
    assessment: Assessment
    drag: tuple[int, int] | None
    dragged: bool
    printout: list[str] | None
    printout_cmd: str | None
    printout_tick: int
    log_scroll: int
    chart_auto: bool
    hud_detail: bool
    tweens: Tweens
    chart_sort: str
    chart_hidden: set[int]
    chart_all: bool
    chart_origin: int | None
    keys: dict[str, str]
    manual: ManualView
    hidden: dict[str, object]
    bridge: Bridge | None
    translator: Translator | None
    llm_settings: dict[str, object]
    comms: Comms
    orders: OrderBook
    order_run: OrderRun | None
    audio: Audio
    _was_alert: bool
    deeds: list[Event]
    size: tuple[int, int]
    map_rect: pygame.Rect
    col_rect: pygame.Rect
    bottom_rect: pygame.Rect
    console_rect: pygame.Rect


__all__ = ["SceneState"]
