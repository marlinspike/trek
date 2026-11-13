"""The battle screen's state, declared in one place for the parts that share it (`BattleScene.__init__` sets it).

The game itself lives in a `BattleSession` (`session/battle.py`). What the screen shows of it is read through
`Forward` attributes, which read from (and set on) the session, so the screen holds no game state of its own.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, Callable, Generic, TypeVar, overload

import pygame

T = TypeVar("T")


class Forward(Generic[T]):
    """An attribute of the session, shown by the screen: `scene.paused` is `scene.session.paused`."""

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    @overload
    def __get__(self, obj: None, owner: type | None = None) -> Forward[T]: ...
    @overload
    def __get__(self, obj: object, owner: type | None = None) -> T: ...

    def __get__(self, obj: Any, owner: type | None = None) -> Any:
        if obj is None:
            return self
        return getattr(obj.session, self.name)

    def __set__(self, obj: Any, value: T) -> None:
        setattr(obj.session, self.name, value)


if TYPE_CHECKING:
    from ...console.complete import Completer
    from ...crew.proposals import Proposal
    from ...session.interface import Session
    from ...session.command import Recording
    from ..microphone import Recorder
    from ...voice.settings import VoiceSettings
    from ...console.parser import ParseResult
    from ...crew.hails import Comms
    from ...sim.observation import Observation
    from .. import theme
    from ..audio import Audio
    from ...session.prefs import BridgePrefs
    from ..subtitles import Subtitles
    from ..camera import Camera
    from ..hud import Panel, TabbedPanel
    from ..manual import ManualView
    from ..tactical import Snapshot, TacticalView
    from ..tween import Tweens
    from ..widgets import UI
    from .common import LogLine


class SceneState:
    session: Session              # the game: the screen reaches it only through this contract
    # the game, as the screen shows it (see `Forward`)
    player_id: Forward[int | None] = Forward()
    paused: Forward[bool] = Forward()
    speed: Forward[float] = Forward()
    acc: Forward[float] = Forward()
    obs: Forward[Observation] = Forward()
    comms: Forward[Comms] = Forward()
    prefs: Forward[BridgePrefs] = Forward()
    proposal: Forward[Proposal | None] = Forward()
    condition: Forward[str | None] = Forward()
    recording: Forward[Recording | None] = Forward()
    style: Forward[str | None] = Forward()
    style_broken: Forward[str | None] = Forward()
    chart_auto: Forward[bool] = Forward()
    # the screen's own state
    on_exit: Callable[[], None]
    exit_label: str
    ui: UI
    omniscient: bool
    cam: Camera
    view: TacticalView
    prev: Snapshot | None
    now: Snapshot
    log: list[LogLine]
    console: str
    console_focus: bool
    history: list[str]
    hist_i: int
    toast: tuple[str, theme.Color, float] | None
    overlay: str | None
    side_tabs: TabbedPanel
    panels: list[Panel]
    selected_ally: int | None
    drag: tuple[int, int] | None
    dragged: bool
    printout: list[str] | None
    printout_cmd: str | None
    printout_tick: int
    log_scroll: int
    hud_detail: bool
    tweens: Tweens
    keys: dict[str, str]
    manual: ManualView
    audio: Audio
    _was_alert: bool
    _alert_since: float
    fired_at: dict[int, float]
    _channels: dict[int, str]
    bridge_store: dict[str, object]
    subs: Subtitles
    _toast_seen: object
    focus_k: float
    focus_idle: float
    wheel: object | None
    counsel_open: bool
    counsel_ran: dict[str, float]
    counsel_box: pygame.Rect | None
    _wheel_t: float
    completer: Completer
    _preview_key: object
    _preview: ParseResult | None
    voice_store: dict[str, object]
    vset: VoiceSettings
    recorder: Recorder | None
    voice_state: str
    voice_note: str
    wheels: dict
    size: tuple[int, int]
    map_rect: pygame.Rect
    col_rect: pygame.Rect
    bottom_rect: pygame.Rect
    console_rect: pygame.Rect


__all__ = ["Forward", "SceneState"]
