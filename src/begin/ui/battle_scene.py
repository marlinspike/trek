"""The battle screen: the tactical map, HUD, console and overlays, presenting a `BattleSession`.

The game is the session's (`session/battle.py`): the clock, the orders, the officers, hails, the outcome. This
screen draws what our side knows, turns keys, clicks and spoken words into orders for the session, and turns
what the session says (`session/news.py`) into log lines, subtitles, sounds and printouts. Rendering
interpolates between the session's last two ticks.

This module holds the screen's state and frame loop. Its other parts live in `ui/battle/` and are mixed in:
input (keys and mouse), comms (the hail and officer shortcuts), bridge (focus, pointing, the wheel, proposals),
voice (push-to-talk) and render (drawing). `ui/battle/state.py` declares the state they share.
"""

from __future__ import annotations

import math
import time
from typing import TYPE_CHECKING, Callable

import pygame

from ..battle import Battle
from ..console.complete import Completer
from ..help.coach import HelpContext
from ..paths import config_dir
from ..session.battle import BattleSession
from ..session.common import CHART
from ..session.interface import Campaign, Channels, Clock, Crew, Display, Orders, Session
from ..session.news import Commanding, Cue, Line, News, Notice, Printout, Prompt, Request, Show, Ticked, Voice
from ..session.prefs import BridgePrefs
from ..sim.commands import Command
from ..sim.events import PhaserFired
from ..sim.ship import Ship
from . import theme
from .audio import HUM_LEVEL as HUM_DEFAULT, Audio
from .battle.bridge import BridgeMixin
from .battle.common import CONTROLS, SPEEDS, TONE_COLOR, LogLine
from .battle.comms import CommsMixin
from .battle.input import InputMixin
from .battle.render import RenderMixin
from .battle.voice import VoiceMixin
from .camera import Camera
from .hud import ContactsPanel, CrewPanel, FleetPanel, OwnShipPanel, Panel, TabbedPanel, TargetPanel, WeaponsPanel
from .manual import ManualView
from .orders_panel import OrdersPanel
from .subtitles import Subtitles
from .tactical import Snapshot, TacticalView
from .tween import Tweens
from .wheel import load_wheels
from .widgets import UI

FRAME_MARGIN = 3000.0       # world units round the farthest ship when the map frames the battle at the start
FRAME_FARTHEST = 32000.0    # world units: the start never zooms out further than this from the centre to the edge

if TYPE_CHECKING:
    from ..crew.counsel import Plan


class BattleScene(InputMixin, CommsMixin, BridgeMixin, VoiceMixin, RenderMixin):
    def __init__(self, battle: Battle | Session, size: tuple[int, int], on_exit: Callable[[], None],
                 keys: dict[str, str] | None = None, hidden: dict[str, object] | None = None,
                 llm: dict[str, object] | None = None, chatter: bool = True, volume: float = 0.6,
                 muted: bool = False, sounds: dict[str, str] | None = None, hum: float = 0.35,
                 jolt: bool = True, bridge: dict[str, object] | None = None,
                 career: dict[str, object] | None = None, voice: dict[str, object] | None = None) -> None:
        # the Bridge setting (full, quiet, classic and its parts), kept in settings.json's "bridge"
        self.bridge_store: dict[str, object] = bridge if bridge is not None else {}
        self.session: Session
        if isinstance(battle, Battle):
            self.session = BattleSession(battle, hidden=hidden, llm=llm, chatter=chatter,
                                         prefs=BridgePrefs.from_dict(self.bridge_store), career=career)
        else:
            self.session = battle
        self.clock: Clock = self.session
        self.orders: Orders = self.session
        self.crew: Crew = self.session
        self.channels: Channels = self.session
        self.readout: Display = self.session
        self.campaign: Campaign = self.session
        self.on_exit: Callable[[], None] = on_exit
        self.exit_label: str = "Return to menu"
        self.ui: UI = UI()
        self.omniscient: bool = False
        self.cam: Camera = Camera(pygame.Rect(0, 0, 100, 100), zoom=0.035, follow=self.player_id)
        self.view: TacticalView = TacticalView(self.cam)
        self.prev: Snapshot | None = None
        self.now: Snapshot = Snapshot.take(self.obs)
        self.log: list[LogLine] = []
        self.console: str = ""
        self.console_focus: bool = False
        self.history: list[str] = []
        self.hist_i: int = 0
        self.toast: tuple[str, theme.Color, float] | None = None
        self.overlay: str | None = "help_brief"
        self.side_tabs: TabbedPanel = TabbedPanel([ContactsPanel(), FleetPanel(), CrewPanel(), OrdersPanel()])
        self.panels: list[Panel] = [OwnShipPanel(), TargetPanel(), WeaponsPanel(), self.side_tabs]
        self.selected_ally: int | None = None
        self.drag: tuple[int, int] | None = None
        self.dragged: bool = False
        # Begin's text displays: the latest one stays on the map, refreshed live, until dismissed
        self.printout: list[str] | None = None
        self.printout_cmd: str | None = None
        self.printout_tick: int = -1
        self.log_scroll: int = 0
        self.hud_detail: bool = False             # every number on the panels; otherwise hover a panel to see them
        self.tweens: Tweens = Tweens()              # panel numbers easing to their new values
        self.keys: dict[str, str] = keys if keys is not None else {}
        self.subs: Subtitles = Subtitles()
        self._toast_seen: object = None
        self.focus_k: float = 0.0           # tactical focus, eased 0..1
        self.focus_idle: float = 0.0        # seconds since the captain's last keystroke in the console
        self.wheel: object | None = None    # the open command wheel, if any
        self.counsel_open: bool = False     # [E] the officers' plans over the map (O, `counsel`)
        self.counsel_ran: dict[str, float] = {}   # steps run from the panel: line -> when, for a moment's tick
        self.counsel_box: pygame.Rect | None = None   # where the panel was last drawn: other cards keep clear of it
        self._wheel_t: float = 0.0
        self.completer: Completer = Completer()
        self._preview_key: object = None
        self._preview = None
        self._voice_setup(voice)
        self.wheels = load_wheels(config_dir() / "wheel.toml")
        self.manual: ManualView = ManualView(self._help_context, self._try_command, self._close_manual)
        self.audio: Audio = Audio(volume, muted, sounds, config_dir() / "sounds", hum=hum)
        self.view.jolt = jolt
        self._channels: dict[int, str] = {}     # how each hail channel stood last frame, to hear it open and close
        self._was_alert: bool = False
        self._alert_since: float = 0.0
        self.fired_at: dict[int, float] = {}   # our phaser banks: when each last fired
        self.layout(size)
        self._frame_all()
        self.clock.subscribe(self._hear_session)
        for problem in self.audio.problems:
            self._log(f"Couldn't use your sound {problem}", theme.TEXT_DIM)

    # ------------------------------------------------------------ layout

    def layout(self, size: tuple[int, int]) -> None:
        w, h = size
        self.size = size
        col = max(420, int(w * 0.29))
        bottom = 168
        self.map_rect = pygame.Rect(8, 8, w - col - 24, h - bottom - 16)
        self.cam.rect = self.map_rect
        self.col_rect = pygame.Rect(w - col - 8, 8, col, h - 16)
        self.bottom_rect = pygame.Rect(8, h - bottom, w - col - 24, bottom - 8)

    def _frame_all(self) -> None:
        """At the start the map shows our ship and at least the nearest enemy: it opens at its usual scale and only
        steps back as far as that enemy needs (never so far that the ships shrink to specks; the contacts list has
        anyone beyond)."""
        here = self.now.ships.get(self.cam.follow) if self.cam.follow is not None else None
        if here is None:
            return
        foes = [self.now.ships[c.id] for c in self.obs.contacts().values()
                if c.id in self.now.ships and not (c.side is not None and c.side == self.obs.side)]
        if not foes:
            return
        near = min(foes, key=lambda p: math.hypot(p[0] - here[0], p[1] - here[1]))
        half_x = abs(near[0] - here[0]) + FRAME_MARGIN
        half_y = abs(near[1] - here[1]) + FRAME_MARGIN
        r = self.map_rect
        need = min((r.width / 2 - 60) / half_x, (r.height / 2 - 60) / half_y)    # clear of the banners at the top
        floor = min(r.width, r.height) / 2 / FRAME_FARTHEST
        self.cam.zoom = max(self.cam.min_zoom, floor, min(self.cam.zoom, need))

    def display_range(self) -> float:
        """World units from the map centre to its nearer edge (Begin's display 'range')."""
        r = self.map_rect
        return min(r.width, r.height) / 2.0 / self.cam.zoom

    def set_display_range(self, units: float) -> None:
        r = self.map_rect
        self.cam.zoom = max(self.cam.min_zoom, min(self.cam.max_zoom, min(r.width, r.height) / 2.0 / units))
        if self.player_id is not None:
            self.cam.follow = self.player_id

    # ------------------------------------------------------------ the game, for the panels and keys

    @property
    def player(self) -> Ship | None:
        return self.clock.player

    def issue(self, cmd: Command) -> str | None:
        return self.orders.submit(cmd)

    def run_console(self, text: str) -> None:
        self.orders.say(text)

    def fire_phasers(self, banks: tuple[int, ...] | None) -> None:
        self.orders.fire_phasers(banks)

    def fire_torpedoes(self, tubes: tuple[int, ...] | None) -> None:
        self.orders.fire_torpedoes(tubes)

    def launch_probe(self) -> None:
        self.orders.launch_probe()

    def toggle_reserve(self, i: int) -> None:
        self.orders.toggle_reserve(i)

    def order_ally(self, ally: int, order: str, target: int | None = None, value: float | None = None) -> None:
        self.orders.order_ally(ally, order, target, value)

    def ally_report(self, sid: int) -> None:
        self.channels.ally_report(sid)

    def take_command(self, sid: int) -> None:
        self.orders.take_command(sid)

    def allies(self) -> list[Ship]:
        return self.readout.allies()

    def nearest_base(self, ally: Ship) -> Ship | None:
        return self.readout.nearest_base(ally)

    def accept_proposal(self) -> bool:
        return self.orders.accept_proposal()

    def belay_proposal(self) -> bool:
        return self.orders.belay_proposal()

    def style_check(self, cmd: Command | None = None, why: str | None = None) -> None:
        self.orders.style_check(cmd, why)

    def ship_name(self, sid: int) -> str:
        return self.readout.ship_name(sid)

    def _help_context(self) -> HelpContext:
        return self.readout.help_context()

    def toggle_counsel(self, on: bool | None = None) -> None:
        """Open or close the officers' counsel over the map."""
        self.counsel_open = (not self.counsel_open) if on is None else on
        self.focus_idle = 0.0
        if self.counsel_open:
            if self.overlay == "help_brief":
                self.overlay = None
            self.crew.counsel(force=True)

    def follow_plan(self, i: int) -> bool:
        """Keys 1 to 4 while the counsel is open: go all in on that officer's plan."""
        plans = self.crew.counsel()
        if not self.counsel_open or not 0 <= i < len(plans):
            return False
        self._follow(plans[i], None)
        return True

    def _follow(self, plan: Plan, line: str | None) -> None:
        lines = [line] if line is not None else plan.lines
        now = time.monotonic()
        for ln in lines:
            self.counsel_ran[ln] = now
        self.crew.follow(plan, lines if line is not None else None)
        if line is None:
            self.counsel_open = False      # all in: the orders are given, the battle runs on at your speed

    def toggle_overlay(self, name: str) -> None:
        self.overlay = None if self.overlay == name else name

    def center_on(self, sid: int) -> None:
        pose = self.now.ships.get(sid)
        if pose:
            self.cam.follow = None
            self.cam.cx, self.cam.cy = pose[0], pose[1]

    def select_ally(self, sid: int) -> None:
        self.selected_ally = sid
        self.side_tabs.show(FleetPanel)

    def _log(self, text: str, color: theme.Color = theme.TEXT, mono: bool = False, channel: str = "computer") -> None:
        """A line of the screen's own (sound settings, voice problems): the game's come through `_hear_session`."""
        self.log.append(LogLine(self.obs.tick, text, color, mono, channel))
        self.log_scroll = 0
        if len(self.log) > 400:
            del self.log[:100]

    def _show(self, lines: list[str], live: str | None = None) -> None:
        """Put a display of the screen's own on the map (and in the log)."""
        self._hear_session(Printout(tuple(lines), live))
        for line in lines:
            self._log(line, theme.TEXT, mono=True)

    def _voice(self, speaker: str, text: str, color: theme.Color, station: str | None = None,
               officer: str | None = None, urgent: bool = False) -> None:
        """Say a line in a subtitle, as far as the captain's Bridge setting wants them."""
        mode = self.prefs.subtitles
        if mode == "off" or (mode == "urgent" and not urgent):
            return
        self.subs.say(speaker, text, color, station, officer, urgent)

    # ------------------------------------------------------------ what the session says

    def _hear_session(self, item: News) -> None:
        if isinstance(item, Line):
            self.log.append(LogLine(item.tick, item.text, TONE_COLOR.get(item.tone, theme.TEXT), item.mono, item.channel))
            self.log_scroll = 0
            if len(self.log) > 400:
                del self.log[:100]
        elif isinstance(item, Ticked):
            self._ticked(item)
        elif isinstance(item, Voice):
            self._voice(item.speaker, item.text, TONE_COLOR.get(item.tone, theme.CREW), item.station, item.officer,
                        item.urgent)
        elif isinstance(item, Notice):
            self.toast = (item.text, TONE_COLOR.get(item.tone, theme.CAUTION), item.seconds)
        elif isinstance(item, Cue):
            self.audio.play(item.name, time.monotonic(), 0.0, item.level)
        elif isinstance(item, Printout):
            if not item.lines:
                if self.printout_cmd == item.live:
                    self.printout = None
                return
            self.printout = list(item.lines)
            self.printout_cmd = item.live
            self.printout_tick = self.obs.tick
        elif isinstance(item, Prompt):
            if item.text is not None:
                self.console = item.text
            self.console_focus = True
            pygame.key.start_text_input()
        elif isinstance(item, Show):
            self.overlay = item.overlay
        elif isinstance(item, Commanding):
            self.cam.follow = item.ship_id
        elif isinstance(item, Request):
            self._request(item.name, item.value)

    def _ticked(self, t: Ticked) -> None:
        obs = self.obs
        events = list(t.events)
        self.view.ingest(events, obs)
        if self.audio.available:
            visible = {s.id for s in obs.own_ships()} | {c.id for c in obs.contacts().values() if c.visible}
            self.audio.events(events, time.monotonic(), self._heard_at, visible, self._beam_style, self._ship_at,
                              self.view.effects.landing)
        for ev in events:
            if isinstance(ev, PhaserFired) and ev.ship_id == self.player_id:
                self.fired_at[ev.bank] = time.monotonic()      # its button glows while the beam is out
        if t.stepped:
            self.prev = self.now
            self.now = Snapshot.take(obs)

    def _request(self, name: str, val: object) -> None:
        """Console orders that are the screen's to carry out."""
        if name == "range":
            if val is None:
                self._log(f"Display range {self.display_range():,.0f} units.", theme.TEXT_DIM)
            else:
                r = (self.display_range() / 2 if val == "in" else self.display_range() * 2) if isinstance(val, str) \
                    else float(val)  # type: ignore[arg-type]
                r = max(200.0, min(500000.0, r))
                self.set_display_range(r)
                self._log(f"Display range set to {r:,.0f} units.", theme.TEXT_DIM)
        elif name == "counsel":
            self.toggle_counsel(None if val is None else val == "on")
        elif name == "key":
            self._key_binding(val)  # type: ignore[arg-type]
        elif name == "manual":
            self.open_manual(val)  # type: ignore[arg-type]
        elif name == "sound":
            self._sound(val)
        elif name == "bridge":
            self.bridge_setting(val)
        elif name == "voice":
            self.voice_command(val)
        elif name == "hud" and isinstance(val, str) and val.startswith("jolt"):
            self.view.jolt = val.endswith("on")
            self._log("The map jolts when your ship takes a heavy blow." if self.view.jolt else
                      "The map stays still when your ship is hit. 'hud jolt on' brings the jolt back.", theme.TEXT_DIM)
        elif name == "hud":
            if val is not None:
                self.hud_detail = val == "detail"
            self._log("Panels show every number." if self.hud_detail else
                      "Panels show what matters; hover one for its numbers. 'hud detail' shows them all.", theme.TEXT_DIM)

    # ------------------------------------------------------------ time

    def update(self, dt: float) -> None:
        self.tweens.update(dt)
        self.ui.mouse = pygame.mouse.get_pos()
        s = self.session
        s.captain_typing = self.console_focus
        s.busy_elsewhere = self.overlay is not None
        if self.toast:
            msg, col, t = self.toast
            if self.toast is not self._toast_seen and not self.prefs.classic and self.prefs.subtitles != "off":
                self.subs.say("", msg, col, urgent=col in (theme.CAUTION, theme.ALERT))   # the computer's voice
            self.toast = (msg, col, t - dt) if t - dt > 0 else None
            self._toast_seen = self.toast
        self.subs.update(dt)
        self._focus_update(dt)
        self._voice_poll()
        self.view.update(dt)
        if self.printout is None:
            chart = s.live_chart()
            if chart is not None:
                self.printout, self.printout_cmd, self.printout_tick = chart, CHART, self.obs.tick
        self._refresh_printout()
        s.update(dt, self.effective_speed())

    def _refresh_printout(self) -> None:
        if self.printout is None or self.obs.tick - self.printout_tick < 5:
            return
        self.printout_tick = self.obs.tick
        if self.printout_cmd:
            lines = self.readout.display(self.printout_cmd)
            if lines is not None:
                self.printout = lines

    def open_manual(self, query: str | None = None) -> None:
        msg = self.manual.open(query)
        if msg:
            self._log(msg, theme.TEXT_DIM)
        self.overlay = "manual"
        self.console_focus = False
        pygame.key.start_text_input()

    def _close_manual(self) -> None:
        if self.overlay == "manual":
            self.overlay = None

    def _try_command(self, text: str) -> None:
        self._close_manual()
        self.console = text
        self.console_focus = True
        pygame.key.start_text_input()

    def close(self) -> None:
        """Leaving the battle: the session remembers how the officers feel and stops its LLM requests."""
        self.clock.close()
        self.audio.stop()

    # ------------------------------------------------------------ sound

    def _heard_at(self, x: float, y: float) -> tuple[float, float] | None:
        """(pan, level) for something at a map point: full in view, fading off its edges, silent far away."""
        sx, sy = self.cam.to_screen(x, y)
        r = self.map_rect
        dx = (sx - r.centerx) / max(1, r.width / 2)
        dy = (sy - r.centery) / max(1, r.height / 2)
        out = max(abs(dx), abs(dy))
        if out > 2.0:
            return None
        level = 0.8 if out <= 1.0 else 0.8 * (2.0 - out)
        return max(-0.8, min(0.8, dx * 0.7)), level

    def _ship_at(self, sid: int) -> tuple[float, float] | None:
        s = self.obs.own(sid)
        if s is not None:
            return s.x, s.y
        c = self.obs.contact(sid)
        return (c.x, c.y) if c is not None else None

    def _beam_style(self, sid: int) -> str:
        from .tactical import faction_seen

        f = faction_seen(self.obs, sid)
        return f.phaser_style if f is not None else "beam"

    def _sound(self, val: object) -> None:
        a = self.audio
        if isinstance(val, tuple) and val[0] == "hum":
            level = val[1]
            a.hum = HUM_DEFAULT if level is None else max(0.0, min(1.0, float(level)))   # type: ignore[arg-type]
            self._log(f"Ship's hum: {a.hum * 100:.0f}% of the volume. 'sound hum off' silences it." if a.hum > 0 else
                      "Ship's hum off. 'sound hum on' brings it back.", theme.TEXT_DIM)
            return
        if isinstance(val, tuple):
            which, variant = val
            name = "launch" if which == "torpedo" else which
            if variant is not None:
                a.choose(name, variant)
            a.muted = False
            a._last.pop(name, None)
            a.play(name, time.monotonic())          # a sample, so the captain hears what they picked
            pick = a.choice.get(name, "d")
            self._log(f"{which.capitalize()} sound: your own {a.own[name].name}." if name in a.own else
                      f"{which.capitalize()} sound: version {pick} of a, b, c, d. 'sound {which} b' tries another; "
                      "it's kept for next time.", theme.TEXT_DIM)
            return
        if val is None:
            pass
        elif val == "on":
            a.muted = False
        elif val == "off":
            a.muted = True
        else:
            a.volume = max(0.0, min(1.0, float(val) / 100))   # type: ignore[arg-type]
            a.muted = False
        state = "no audio device" if not a.available else "muted" if a.muted else f"volume {a.volume * 100:.0f}"
        self._log(f"Sound: {state}. M mutes; 'sound <0-100>' sets the volume.", theme.TEXT_DIM)

__all__ = ["BattleScene", "CONTROLS", "SPEEDS"]
