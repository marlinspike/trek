"""The battle screen: fixed-step simulation, tactical map, HUD, console and overlays.

The simulation advances in fixed ticks (10 per cycle; one cycle is one
second at 1×) from an accumulator fed by wall-clock time × the chosen
speed. Rendering interpolates between the last two ticks. Pausing stops
the accumulator; orders can still be given while paused.
"""

from __future__ import annotations

import math
import re
import time
from functools import partial
from dataclasses import dataclass
from typing import Callable, Protocol

import pygame

from ..battle import Battle
from ..console import reports
from .hit_report import HitReport
from ..console.parser import ParseContext, ParseResult, parse
from ..console.vocab import VERBS
from ..console.orders import OrderBook, OrderRun, aim
from ..console.translator import Translation, Translator
from ..core.angles import bearing, norm360
from ..sim.allies import AllyStanding
from ..sim.commands import (
    AddressCrew, AllyOrder, CeaseFire, Command, SetObjective, FirePhasers, FireTorpedoes, LaunchProbe, Pursue, Scan, SelectTarget, SetBanks, SetHelm,
    SetPointDefense, SetShields, StandDown, offensive_fire,
)
from ..sim.events import Event, Message, ObjectiveEnded, ProjectCompleted, ScanCompleted, Tone
from ..sim.observation import Observation
from ..sim.scoring import Assessment
from ..sim.ship import BankRole, Kind, Ship
from . import comms_view, officer_view, theme
from .audio import Audio
from .camera import Camera
from ..crew.conversation import Bridge, Utterance, whole_bridge_stand_down
from ..crew.hails import Comms, load_lines, prisoners_lines
from ..crew.officers import STATION_COMMANDS, Activity, station_of
from ..sim.systems.repair import in_battle, under_repair
from ..help.coach import HelpContext
from .manual import ManualView
from .tween import Tweens
from .hud import (
    PD_CYCLE, SUB_GROUPS, ContactsPanel, CrewPanel, FleetPanel, OwnShipPanel, Panel, TabbedPanel, TargetPanel, WeaponsPanel,
    diagram_legend, hull_diagram,
)
from .tactical import Snapshot, TacticalView
from .widgets import UI

SPEEDS = (0.25, 0.5, 1.0, 2.0, 4.0)
TONE_COLOR = {
    Tone.INFO: theme.TEXT, Tone.GOOD: theme.GOOD, Tone.CAUTION: theme.CAUTION, Tone.ALERT: theme.ALERT,
    Tone.CREW: theme.CREW,
}

CONTROLS = [
    ("Space", "Pause / resume"),
    ("[  ]", "Slower / faster (0.25× – 4×)"),
    ("W  S", "Warp up / down"),
    ("A  D", "Turn 15° port / starboard (Shift: 5°)"),
    ("Right-click map", "Steer toward that point"),
    ("Shift + right-click ship", "Pursue that ship"),
    ("Left-click ship", "Select target"),
    ("Tab", "Next target"),
    ("R", "Cycle subsystem aim (hull, propulsion, weapons…)"),
    ("F  T  P", "Fire phasers / torpedoes / launch probe"),
    ("X", "Scan target"),
    ("G", "Raise / lower shields"),
    ("V", "Cycle point-defense doctrine"),
    ("Q", "Show phaser arcs"),
    ("Wheel, + −", "Zoom"),
    ("Drag, arrows", "Pan the map"),
    ("C", "Centre and follow own ship"),
    ("Enter or /", "Open the command console (type 'help')"),
    ("F2-F8, F10-F12, Ctrl+key", "Run a 'key' macro you defined in the console"),
    ("Wheel over the log", "Scroll the console log"),
    ("I", "Damage assessment (inspect own ship)"),
    ("M", "Sound on / off"),
    ("F1 or H", "This reference"),
    ("Esc", "Close overlay / battle menu"),
]


@dataclass
class LogLine:
    tick: int
    text: str
    color: theme.Color
    mono: bool = False


FKEYS = {getattr(pygame, f"K_F{n}"): f"F{n}" for n in (2, 3, 4, 5, 6, 7, 8, 10, 11, 12)}


RED_ALERT_FLOOR, RED_ALERT_PULSE, RED_ALERT_PERIOD = 0.22, 0.38, 1.8   # border tint and its pulse (seconds)
ORDER_TRANSLATE_WAIT = 8.0     # seconds a named order waits for a step's translation before skipping it


class TourLink(Protocol):
    """What a battle on a tour of duty can ask of the tour (a `TourRun`)."""

    def reinforcement_arrival(self, battle: Battle, player_ship: Ship | None) -> tuple[object | None, str]: ...


# "hail the X", "open a channel to X", "open hailing frequencies", "get me the X", "put me through to X" [E]
_HAIL_ORDER = re.compile(r"^\s*(hail(ing)?( frequencies)?|open (a |hailing )?(channel|frequencies|comms?)( to| with)?|"
                         r"get me|put me through to|signal|raise them|raise the)\b\s*", re.I)


class BattleScene:
    def __init__(self, battle: Battle, size: tuple[int, int], on_exit: Callable[[], None],
                 keys: dict[str, str] | None = None, hidden: dict[str, object] | None = None,
                 llm: dict[str, object] | None = None, chatter: bool = True, volume: float = 0.6,
                 muted: bool = False, sounds: dict[str, str] | None = None) -> None:
        self.battle = battle
        self.world = battle.world
        self.player_id = battle.player_ship_id
        self.side = battle.setup.player_side if battle.setup.player_side >= 0 else 0
        self.on_exit = on_exit
        self.exit_label = "Return to menu"
        self.tour: TourLink | None = None     # on a tour of duty: Starfleet answers `request reinforcements`
        self.ui = UI()
        self.paused = True
        self.speed = 1.0
        self.acc = 0.0
        self.omniscient = False
        self.cam = Camera(pygame.Rect(0, 0, 100, 100), zoom=0.035, follow=self.player_id)
        self.view = TacticalView(self.cam)
        self.obs: Observation = self.world.observe(self.side)
        self.prev: Snapshot | None = None
        self.now = Snapshot.take(self.obs)
        self.log: list[LogLine] = []
        self.console = ""
        self.console_focus = False
        self.history: list[str] = []
        self.hist_i = 0
        self.toast: tuple[str, theme.Color, float] | None = None
        self.hits = HitReport(None)   # "Hits on Wraith: ..." lines in the log
        self.overlay: str | None = "help_brief"
        self.side_tabs = TabbedPanel([ContactsPanel(), FleetPanel(), CrewPanel()])
        self.panels: list[Panel] = [OwnShipPanel(), TargetPanel(), WeaponsPanel(), self.side_tabs]
        self.selected_ally: int | None = None
        self.assessment = Assessment.begin(self.world)
        self.drag: tuple[int, int] | None = None
        self.dragged = False
        # Begin's text displays: the latest one stays on the map, refreshed live, until dismissed
        self.printout: list[str] | None = None
        self.printout_cmd: str | None = None
        self.printout_tick = -1
        self.log_scroll = 0
        self.chart_auto = False
        self.hud_detail = False             # every number on the panels; otherwise hover a panel to see them
        self.tweens = Tweens()              # panel numbers easing to their new values
        self.chart_sort = "name"
        self.chart_hidden: set[int] = set()
        self.chart_all = False
        self.chart_origin: int | None = None
        self.keys: dict[str, str] = keys if keys is not None else {}
        self.manual = ManualView(self._help_context, self._try_command, self._close_manual)
        self.hidden: dict[str, object] = hidden if hidden is not None else {}
        self.bridge: Bridge | None = None
        self.translator: Translator | None = None
        self.llm_settings: dict[str, object] = llm if llm is not None else {}
        llm_note: str | None = None
        provider = None
        try:
            from ..llm.providers import config_from_settings, make_provider

            cfg = config_from_settings(self.llm_settings)
            if cfg is not None:
                provider = make_provider(cfg)
                think = "" if cfg.think is None else f", thinking {'on' if cfg.think is True else 'off' if cfg.think is False else cfg.think}"
                who = "Officers are talking" if battle.crew is not None else "The console understands plain English"
                llm_note = f"{who} through {cfg.provider} ({cfg.model}{think})."
        except Exception as e:  # noqa: BLE001 - a bad LLM setup must never stop a battle
            llm_note = f"LLM not available ({e}); officers will answer offline."
        if provider is not None:
            from ..llm.service import LLMService

            # its own worker, so console translations never queue behind an officer's answer
            self.translator = Translator(LLMService(provider, workers=1), self.llm_settings.get("console"))
            if self.translator.mode != "off":
                llm_note = (llm_note or "") + " You can type orders in plain English."
        if battle.crew is not None:
            service = None
            if provider is not None:
                from ..llm.service import LLMService

                service = LLMService(provider)
            self.bridge = Bridge(battle.crew, self.hidden, service, seed=battle.setup.seed, chatter=chatter)
        from ..paths import config_dir

        # [E] hailing enemy captains: its own model worker, so a hail never queues behind an officer
        hail_llm = None
        if provider is not None:
            from ..llm.service import LLMService

            hail_llm = LLMService(provider, workers=1)
        crew = battle.crew
        self.comms = Comms(self.world, self.side, hail_llm, seed=battle.setup.seed,
                           lines=load_lines(override=config_dir() / "hails.toml"),
                           officers=(lambda st: crew.officer(st)) if crew is not None else None)
        self.orders = OrderBook.load(config_dir())
        self.order_run: OrderRun | None = None
        self.audio = Audio(volume, muted, sounds, config_dir() / "sounds")
        for problem in self.audio.problems:
            self._log(f"Couldn't use your sound {problem}", theme.TEXT_DIM)
        self._was_alert = False
        self.deeds: list[Event] = []          # objectives and projects finished: the officers' record for the debrief
        if provider is not None and self.orders.orders:
            from ..llm.service import LLMService

            self.orders.llm = LLMService(provider, workers=1)
        self.layout(size)
        self._frame_all()
        self._log("Battle stations. The simulation is paused: press Space to begin.", theme.CAUTION)
        if battle.setup.description:
            self._log(battle.setup.description, theme.TEXT_DIM)
        if llm_note:
            self._log(llm_note, theme.TEXT_DIM)
        self._order_problems(self.orders.prepare(self._would_run, self._translation_brief(), self._target_id()))

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
        """Zoom so every ship we know about is on screen."""
        pts = list(self.now.ships.values())
        if not pts:
            return
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        span_x = max(xs) - min(xs) + 6000
        span_y = max(ys) - min(ys) + 6000
        r = self.map_rect
        self.cam.zoom = max(self.cam.min_zoom, min(0.08, r.width / span_x, r.height / span_y))

    def display_range(self) -> float:
        """World units from the map centre to its nearer edge (Begin's display 'range')."""
        r = self.map_rect
        return min(r.width, r.height) / 2.0 / self.cam.zoom

    def set_display_range(self, units: float) -> None:
        r = self.map_rect
        self.cam.zoom = max(self.cam.min_zoom, min(self.cam.max_zoom, min(r.width, r.height) / 2.0 / units))
        if self.player_id is not None:
            self.cam.follow = self.player_id

    # ------------------------------------------------------------ helpers used by panels

    @property
    def player(self) -> Ship | None:
        return self.obs.own(self.player_id) if self.player_id is not None else None

    def issue(self, cmd: Command) -> str | None:
        reason = self.world.execute(cmd)
        if reason:
            self.toast = (reason, theme.CAUTION, 3.0)
        self._drain_events()
        return reason

    def fire_phasers(self, banks: tuple[int, ...] | None) -> None:
        p = self.player
        if p is not None:
            self.issue(FirePhasers(ship_id=p.id, banks=banks))

    def fire_torpedoes(self, tubes: tuple[int, ...] | None) -> None:
        p = self.player
        if p is not None:
            self.issue(FireTorpedoes(ship_id=p.id, tubes=tubes))

    def launch_probe(self) -> None:
        p = self.player
        if p is None:
            return
        if p.target is None:
            self.toast = ("Select a target for the probe (or use the console: 'fire probes course 90').", theme.CAUTION, 3.0)
            return
        self.issue(LaunchProbe(ship_id=p.id, target=p.target))

    def toggle_reserve(self, i: int) -> None:
        p = self.player
        if p is None:
            return
        role = BankRole.FLEX if p.banks[i].role == BankRole.DEFENSE else BankRole.DEFENSE
        self.issue(SetBanks(ship_id=p.id, banks=(i,), role=role))

    def toggle_overlay(self, name: str) -> None:
        self.overlay = None if self.overlay == name else name

    def center_on(self, sid: int) -> None:
        pose = self.now.ships.get(sid)
        if pose:
            self.cam.follow = None
            self.cam.cx, self.cam.cy = pose[0], pose[1]

    def allies(self) -> list[Ship]:
        """Our other living ships, nearest first."""
        p = self.player
        out = [s for s in self.obs.own_ships() if p is None or s.id != p.id]
        if p is not None:
            out.sort(key=lambda s: math.hypot(s.x - p.x, s.y - p.y))
        return out

    def select_ally(self, sid: int) -> None:
        self.selected_ally = sid
        self.side_tabs.show(FleetPanel)

    def order_ally(self, ally: int, order: str, target: int | None = None, value: float | None = None) -> None:
        p = self.player
        if p is not None:
            self.issue(AllyOrder(ship_id=p.id, ally=ally, order=order, target=target, value=value))

    def nearest_base(self, ally: Ship) -> Ship | None:
        """The nearest of our ships with docking bays, other than the ally itself."""
        bases = [s for s in self.obs.own_ships() if s.id != ally.id and s.cls.mass_capacity > 0]
        return min(bases, key=lambda s: math.hypot(s.x - ally.x, s.y - ally.y), default=None)

    def ally_report(self, sid: int) -> None:
        ally = self.obs.own(sid)
        if ally is not None:
            self._show(reports.report_lines(self.obs, ally, self.obs.ally_order(sid) or AllyStanding()), None)

    def take_command(self, sid: int) -> None:
        self._transfer(sid)

    def _log(self, text: str, color: theme.Color = theme.TEXT, mono: bool = False) -> None:
        self.log.append(LogLine(self.world.tick, text, color, mono))
        self.log_scroll = 0
        if len(self.log) > 400:
            del self.log[:100]

    # ------------------------------------------------------------ simulation

    def _drain_events(self) -> None:
        events = self.world.take_events()
        self.obs = self.world.observe(self.side)
        self.view.ingest(events, self.obs)
        self.deeds.extend(ev for ev in events if isinstance(ev, (ObjectiveEnded, ProjectCompleted)))
        if self.audio.available:
            visible = {s.id for s in self.obs.own_ships()} | {c.id for c in self.obs.contacts().values() if c.visible}
            self.audio.events(events, time.monotonic(), self._heard_at, visible, self._beam_style, self._ship_at)
        self._crew_react(events)
        self.hits.attacker = self.player_id
        self.hits.ingest(events, self.world.tick)
        names = {c.id: c.label.split(" (")[0] for c in self.obs.contacts().values() if c.identified}
        for line in self.hits.due(self.world.tick, self.world.rules.ticks_per_cycle, names):
            self._log(line, theme.GOOD)
        for ev in events:
            if isinstance(ev, Message):
                if ev.visible_to is not None and self.side not in ev.visible_to:
                    continue
                if ev.text.startswith("Scanning ") and self.player is not None and "science" in self.player.delegated:
                    continue  # Seven reports what matters herself
                who = f"{ev.speaker}: " if ev.speaker and ev.speaker not in ev.text else ""
                self._log(who + ev.text, TONE_COLOR.get(ev.tone, theme.TEXT))
            elif (isinstance(ev, ScanCompleted) and ev.ship_id == self.player_id
                  and not (self.player is not None and "science" in self.player.delegated)):  # Seven's routine scans stay quiet
                c = self.obs.contact(ev.target_id)
                if c is not None and c.scan is not None:
                    self._show(reports.scan_lines(self.obs, c), None)

    def update(self, dt: float) -> None:
        self.tweens.update(dt)
        self.ui.mouse = pygame.mouse.get_pos()
        if self.bridge is not None and self.bridge.llm is not None:
            self._speak(self.bridge.poll(self._help_context(), self._officer_run))
            for cmd in self.bridge.take_addresses():
                self.issue(cmd)
        if self.comms.llm is not None:
            self._speak(self.comms.poll(self.player, self.issue))
        if self.translator is not None and self.translator.busy():
            for answer in self.translator.poll(self._would_run):
                self._translated(answer)
        if self.bridge is not None:
            # while the captain waits on an interpretation, officers' remarks don't queue at the model ahead of it
            self.bridge.hold_voices = self.translator is not None and self.translator.busy()
        if self.orders.busy():
            self._order_problems(self.orders.poll(self._would_run, self._target_id()))
        self._advance_order()
        if self.toast:
            msg, col, t = self.toast
            self.toast = (msg, col, t - dt) if t - dt > 0 else None
        self.view.update(dt)
        if self.chart_auto and self.printout is None:
            self._show(self._chart_lines(), None)
            self.printout_cmd = "\0chart"
        self._refresh_printout()
        if self.paused or self.world.outcome.over:
            self.acc = 0.0
            self.obs = self.world.observe(self.side)
            return
        tick_len = 1.0 / self.world.rules.ticks_per_cycle
        self.acc += dt * self.speed
        steps = 0
        while self.acc >= tick_len and steps < 12:
            self.prev = Snapshot.take(self.world.observe(self.side))
            self.world.step()
            self.acc -= tick_len
            steps += 1
            self._drain_events()
            self.now = Snapshot.take(self.obs)
            if self.world.outcome.over:
                self.overlay = "debrief"
                self._crew_outcome()
                break
        if steps >= 12:
            self.acc = 0.0

    # ------------------------------------------------------------ input

    def handle(self, ev: pygame.event.Event) -> None:
        if ev.type == pygame.VIDEORESIZE:
            self.layout((ev.w, ev.h))
            return
        if self.overlay == "manual":
            if ev.type == pygame.KEYDOWN:
                self.manual.key(ev)
                return
            if ev.type == pygame.TEXTINPUT:
                self.manual.text(ev.text)
                return
            if ev.type == pygame.MOUSEWHEEL:
                self.manual.wheel(ev.y, self.ui.mouse)
                return
        if ev.type == pygame.KEYDOWN:
            if self.console_focus:
                self._console_key(ev)
            else:
                self._key(ev)
        elif ev.type == pygame.TEXTINPUT and self.console_focus:
            self.console += ev.text
        elif ev.type == pygame.MOUSEBUTTONDOWN:
            self._mouse_down(ev)
        elif ev.type == pygame.MOUSEBUTTONUP and ev.button == 1:
            if self.drag is not None and not self.dragged:
                self._left_click(ev.pos)
            self.drag = None
        elif ev.type == pygame.MOUSEMOTION and self.drag is not None:
            dx, dy = ev.pos[0] - self.drag[0], ev.pos[1] - self.drag[1]
            if self.dragged or abs(dx) + abs(dy) > 4:
                self.dragged = True
                self.cam.pan_pixels(dx, dy)
                self.drag = ev.pos
        elif ev.type == pygame.MOUSEWHEEL:
            if self.bottom_rect.collidepoint(self.ui.mouse):
                self.log_scroll = max(0, min(len(self.log) - 1, self.log_scroll + ev.y * 3))
            elif self.map_rect.collidepoint(self.ui.mouse):
                self.cam.zoom_at(1.15 ** ev.y, *self.ui.mouse)

    def _mouse_down(self, ev: pygame.event.Event) -> None:
        if self.overlay in ("debrief", "menu", "manual"):
            h = self.ui.hit(ev.pos)
            if h and ev.button == 1:
                h.action()
            return
        h = self.ui.hit(ev.pos)
        if h is not None and not (self.map_rect.collidepoint(ev.pos) and self.overlay is None and h.rect == self.map_rect):
            if ev.button == 1:
                if self.overlay and self.overlay.startswith("help"):
                    self.overlay = None
                h.action()
                return
            if ev.button == 3 and h.right is not None:
                h.right()
                return
        if self.overlay and self.overlay.startswith("help"):
            self.overlay = None
        if self.console_rect.collidepoint(ev.pos):
            self.console_focus = True
            return
        self.console_focus = False
        if not self.map_rect.collidepoint(ev.pos):
            return
        if ev.button == 1:
            self.drag = ev.pos
            self.dragged = False
        elif ev.button == 2:
            self.drag = ev.pos
            self.dragged = True
        elif ev.button == 3:
            self._right_click(ev.pos)

    def _left_click(self, pos: tuple[int, int]) -> None:
        p = self.player
        sid = self.view.pick(self.obs, self.now, *pos)
        if p is None:
            return
        if sid is not None and sid in self.obs.contacts():
            self.issue(SelectTarget(ship_id=p.id, target=sid, subsystem=p.target_subsystem))
        elif sid is not None and sid != p.id and self.obs.own(sid) is not None:
            self.select_ally(sid)

    def _right_click(self, pos: tuple[int, int]) -> None:
        p = self.player
        if p is None:
            return
        mods = pygame.key.get_mods()
        sid = self.view.pick(self.obs, self.now, *pos)
        if sid is not None and sid != p.id and mods & pygame.KMOD_SHIFT:
            self.issue(Pursue(ship_id=p.id, target=sid, warp=max(p.desired_warp, 1.0)))
            return
        wx, wy = self.cam.to_world(*pos)
        crs = bearing(wx - p.x, wy - p.y)
        warp = p.desired_warp if p.desired_warp > 0.5 else min(p.cls.cruise_warp, p.max_attainable_warp)
        self.issue(SetHelm(ship_id=p.id, course=round(crs), warp=warp))

    def _key(self, ev: pygame.event.Event) -> None:
        k = ev.key
        p = self.player
        shift = ev.mod & pygame.KMOD_SHIFT
        if k in FKEYS and self.run_key(FKEYS[k]):
            return
        if ev.mod & pygame.KMOD_CTRL and pygame.K_a <= k <= pygame.K_z and self.run_key("^" + chr(k)):
            return
        if k == pygame.K_ESCAPE:
            if self.overlay is None and self.printout is not None:
                self.printout = None
                self.chart_auto = False
            elif self.overlay in (None, "help_brief"):
                self.overlay = "menu"
            elif self.overlay == "debrief":
                self.on_exit()
            else:
                self.overlay = None
            return
        if self.overlay == "debrief":
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.on_exit()
            return
        if self.overlay and self.overlay.startswith("help") and k not in (pygame.K_F1, pygame.K_h):
            self.overlay = None
        if k == pygame.K_SPACE:
            self.paused = not self.paused
        elif k in (pygame.K_RIGHTBRACKET, pygame.K_PERIOD):
            self.speed = SPEEDS[min(len(SPEEDS) - 1, SPEEDS.index(self.speed) + 1)]
        elif k in (pygame.K_LEFTBRACKET, pygame.K_COMMA):
            self.speed = SPEEDS[max(0, SPEEDS.index(self.speed) - 1)]
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SLASH, pygame.K_BACKQUOTE):
            self.console_focus = True
            pygame.key.start_text_input()
        elif k == pygame.K_F1:
            self.open_manual("controls")
        elif k == pygame.K_h:
            self.open_manual()
        elif k == pygame.K_i:
            self.toggle_overlay("damage")
        elif k == pygame.K_q:
            self.view.show_arcs = not self.view.show_arcs
        elif k == pygame.K_c:
            self.cam.follow = self.player_id
        elif k in (pygame.K_EQUALS, pygame.K_PLUS, pygame.K_KP_PLUS):
            self.cam.zoom_at(1.25, *self.map_rect.center)
        elif k in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.cam.zoom_at(0.8, *self.map_rect.center)
        elif k in (pygame.K_LEFT, pygame.K_RIGHT, pygame.K_UP, pygame.K_DOWN):
            step = 80
            dx = {pygame.K_LEFT: step, pygame.K_RIGHT: -step}.get(k, 0)
            dy = {pygame.K_UP: step, pygame.K_DOWN: -step}.get(k, 0)
            self.cam.pan_pixels(dx, dy)
        elif k == pygame.K_m:
            muted = self.audio.toggle_mute()
            self.toast = ("Sound off (M)" if muted else "Sound on (M)", theme.TEXT_DIM, 1.5)
        elif k == pygame.K_F9:
            self.omniscient = not self.omniscient
        elif p is None:
            return
        elif k == pygame.K_w:
            self.issue(SetHelm(ship_id=p.id, warp=min(p.cls.max_warp, math.floor(p.desired_warp + 1))))
        elif k == pygame.K_s:
            self.issue(SetHelm(ship_id=p.id, warp=max(0.0, math.ceil(p.desired_warp - 1))))
        elif k == pygame.K_a:
            self.issue(SetHelm(ship_id=p.id, course=norm360(p.desired_course - (5 if shift else 15))))
        elif k == pygame.K_d:
            self.issue(SetHelm(ship_id=p.id, course=norm360(p.desired_course + (5 if shift else 15))))
        elif k == pygame.K_f:
            self.fire_phasers(None)
        elif k == pygame.K_t:
            self.fire_torpedoes(None)
        elif k == pygame.K_p:
            self.launch_probe()
        elif k == pygame.K_x:
            if p.target is not None:
                self.issue(Scan(ship_id=p.id, target=p.target))
        elif k == pygame.K_TAB:
            self._cycle_target(-1 if shift else 1)
        elif k == pygame.K_r:
            if p.target is not None:
                i = SUB_GROUPS.index(p.target_subsystem) if p.target_subsystem in SUB_GROUPS else 0
                self.issue(SelectTarget(ship_id=p.id, target=p.target, subsystem=SUB_GROUPS[(i + 1) % len(SUB_GROUPS)]))
        elif k == pygame.K_g:
            up = not any(s.up for s in p.shields)
            self.issue(SetShields(ship_id=p.id, up=up))
        elif k == pygame.K_v:
            nxt = PD_CYCLE[(PD_CYCLE.index(p.pd_doctrine) + 1) % len(PD_CYCLE)]
            self.issue(SetPointDefense(ship_id=p.id, doctrine=nxt))
            self.toast = (f"Point defense: {nxt.value}", theme.GOOD, 2.0)

    def _cycle_target(self, step: int) -> None:
        p = self.player
        if p is None:
            return
        cs = sorted(self.obs.contacts().values(), key=lambda c: c.distance_to(p.x, p.y))
        if not cs:
            self.toast = ("No contacts on sensors.", theme.CAUTION, 2.0)
            return
        ids = [c.id for c in cs]
        i = ids.index(p.target) if p.target in ids else -1
        nxt = ids[(i + step) % len(ids)]
        self.issue(SelectTarget(ship_id=p.id, target=nxt, subsystem=p.target_subsystem))

    def _console_key(self, ev: pygame.event.Event) -> None:
        k = ev.key
        if k == pygame.K_ESCAPE:
            self.console_focus = False
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            self._submit_console()
        elif k == pygame.K_BACKSPACE:
            self.console = self.console[:-1]
        elif k == pygame.K_UP and self.history:
            self.hist_i = max(0, self.hist_i - 1)
            self.console = self.history[self.hist_i]
        elif k == pygame.K_DOWN and self.history:
            self.hist_i = min(len(self.history), self.hist_i + 1)
            self.console = self.history[self.hist_i] if self.hist_i < len(self.history) else ""

    def _submit_console(self) -> None:
        text = self.console.strip()
        self.console = ""
        if not text:
            self.console_focus = False
            return
        self.history.append(text)
        self.hist_i = len(self.history)
        self.run_console(text)

    def run_console(self, text: str) -> None:
        """Run a console line; ';' separates several commands (as in key macros)."""
        if text.strip().lower().split(None, 1)[:1] == ["key"]:
            self._run_one(text.strip())  # the macro itself may hold several commands
            return
        for part in [t.strip() for t in text.split(";")]:
            if part:
                self._run_one(part)

    def _run_one(self, text: str, translate: bool = True, echo: str = "> ") -> None:
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
                and tr.wants(res.error is None, _exact_verb(text) or len(text.split()) >= 2)):
            tr.submit(text, self._translation_brief(), res.error)
            self._log("  … interpreting", theme.TEXT_DIM)
            return
        self._execute(text, res)

    def _execute_now(self, text: str, res: ParseResult | None = None) -> None:
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

    def _after_captain(self, cmd: Command) -> None:
        """Follow-through on the captain's own orders that hand work back from the officers."""
        from ..sim.commands import DelegateStation, EndObjective

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
        from ..sim.commands import Evasive

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

    def _execute(self, text: str, res: ParseResult) -> None:
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

    def _show(self, lines: list[str], live_cmd: str | None) -> None:
        for line in lines:
            self._log(line, theme.TEXT, mono=True)
        self.printout = list(lines)
        self.printout_cmd = live_cmd
        self.printout_tick = self.world.tick

    def _refresh_printout(self) -> None:
        if self.printout is None or self.world.tick - self.printout_tick < 5:
            return
        self.printout_tick = self.world.tick
        if self.printout_cmd == "\0chart":
            self.printout = self._chart_lines()
        elif self.printout_cmd and self.player_id is not None:
            res = parse(self.printout_cmd, ParseContext(self.player_id, self.world.observe(self.side)))
            if res.display and not res.error:
                self.printout = res.display

    def _chart_lines(self) -> list[str]:
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

    def _action(self, name: str, val: object) -> None:
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

    def _reinforcements(self) -> None:
        if self.tour is None:
            self._log("Starfleet sends reinforcements only on a tour of duty (main menu, Tour of duty).", theme.CAUTION)
            return
        if self.world.outcome.over:
            self._log("The battle is over.", theme.TEXT_DIM)
            return
        arrival, msg = self.tour.reinforcement_arrival(self.battle, self.player)
        self._log(msg, theme.GOOD if arrival is not None else theme.CAUTION)

    def _inbound(self) -> list[tuple[str, float]]:
        """Starfleet's ships on their way, with their ETAs, for the map."""
        out = []
        for a in self.world.arrivals:
            if a.tag == "starfleet" and not a.arrived and a.side == self.side:
                eta = a.eta(self.world)
                if eta is not None:
                    names = ", ".join(f"USS {n}" for n in a.names if n) or "Starfleet"
                    out.append((names, eta))
        return out

    # ------------------------------------------------------------ named orders

    def _target_id(self) -> int | None:
        p = self.player
        return p.target if p is not None else None

    def _order_problems(self, problems: list[str]) -> None:
        for p in problems:
            self._log(f"Named order {p}", theme.CAUTION)

    def _execute_order(self, name: str) -> None:
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

    def _belay(self) -> None:
        run = self.order_run
        if run is None or run.done:
            return          # nothing to belay but the cease fire that came with it
        left = len(run.order.steps) - run.index
        self._log(f"Order {run.order.name} belayed ({left} step{'s' if left != 1 else ''} not run).", theme.CAUTION)
        self.order_run = None

    def _advance_order(self) -> None:
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

    # ------------------------------------------------------------ plain English

    def _activity(self, obs: Observation) -> list[Activity]:
        crew = self.battle.crew
        if crew is None or self.player_id is None or crew.ship_id != self.player_id:
            return []
        return crew.activity(obs)

    def _officer_name(self, oid: str) -> str:
        o = self.bridge.find(oid) if self.bridge is not None else None
        return o.name if o is not None else oid

    def _translation_brief(self) -> str:
        """What the translating model may know: the situation, the officers, and the names the console accepts."""
        from ..crew.conversation import situation

        ctx = self._help_context()
        lines = [situation(ctx)]
        if self.bridge is not None:
            lines.append("Bridge officers (address them with ask <officer> <words>): " + ", ".join(
                f"{o.id} ({o.name}, {o.station})" for o in self.bridge.officers()) + ".")
        allies = [a.name for a in self.allies()]
        if allies:
            lines.append("Our other ships: " + ", ".join(allies) + ".")
        return "\n".join(lines)

    def _would_run(self, line: str) -> str | None:
        """Why a translated line would be rejected, or None: checked before anything runs."""
        if self.player_id is None:
            return "No ship under command."
        if self.bridge is not None and self.bridge.addressed(line) is not None:
            return None
        return parse(line, ParseContext(self.player_id, self.world.observe(self.side))).error

    def _translated(self, t: Translation) -> None:
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

    def _translate_mode(self, mode: object) -> None:
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

    # ------------------------------------------------------------ bridge officers

    def hail(self, target: int | None, words: str) -> None:
        """Open a channel to an enemy captain (or every one on sensors) and say `words` [E]."""
        p = self.player
        if p is None or not p.alive:
            self._log("No ship under command.", theme.CAUTION)
            return
        self._speak(self.comms.hail(p, target, words, self.issue))

    def open_channel(self, sid: int) -> None:
        """The Hail button: open a channel (they answer), then the console waits for the captain's words."""
        self.hail(sid, "")
        name = self.obs.contact(sid)
        label = name.label.split(" (")[0] if name is not None and name.identified else f"#{sid}"
        self.console = f"hail {label} "
        self.console_focus = True
        pygame.key.start_text_input()

    def _comms_button(self, line: str) -> None:
        if line.startswith("\0type:"):
            self.console = line[len("\0type:"):]
            self.console_focus = True
            pygame.key.start_text_input()
            return
        self.run_console(line)

    def _ask(self, officer: object, words: str) -> None:
        if self.bridge is None:
            return
        from ..crew.characters import OfficerProfile

        assert isinstance(officer, OfficerProfile)
        if _HAIL_ORDER.match(words):
            # "worf, hail the Gr'oth" / "seven, open a channel to them": the officer opens it, the captain speaks
            res = parse(_HAIL_ORDER.sub("hail ", words, count=1), ParseContext(self.player_id, self.world.observe(self.side)))
            if res.error:
                self._speak([Utterance(officer.id, officer.title, res.error, "caution")])
                return
            self._speak([Utterance(officer.id, officer.title, "Channel open, Captain.")])
            for name, val in res.actions:
                if name == "hail":
                    self.hail(val[0], str(val[1]))  # type: ignore[index]
            return
        self._speak(self.bridge.ask(officer, words, self._help_context(), self._officer_run))

    def _conn(self, who: str | None) -> str | None:
        """Hand the bridge to an officer, or take it back. Returns why not, or None."""
        from ..sim.commands import TakeConn

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

    def _conn_command(self, who: object) -> None:
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

    def _officer_run(self, line: str, officer: object) -> str | None:
        """Carry out a console line an officer was told (or decided) to run; only their own stations."""
        from ..crew.characters import OfficerProfile
        from ..sim.commands import DelegateStation, EndObjective, ManageRepairs, SetObjective

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
        from ..sim.commands import SetObjective

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

    def _speak(self, lines: list[Utterance]) -> None:
        tone = {"crew": theme.CREW, "caution": theme.CAUTION, "dim": theme.TEXT_DIM, "enemy": theme.HAIL}
        for u in lines:
            self._log(f"{u.speaker}: {u.text}", tone.get(u.tone, theme.CREW))
            for c in u.commands:
                self._log(f"    › {c}", theme.TEXT_DIM)

    def address_crew(self) -> None:
        """Open the console ready for a speech to the crew."""
        self.console = "address crew "
        self.console_focus = True

    def address(self, name: str) -> None:
        """Open the console ready to speak to an officer."""
        self.console = f"{name}, "
        self.console_focus = True

    def _crew_react(self, events: list[Event]) -> None:
        self._speak(self.comms.react(events, self.player))
        if self.bridge is not None and self.player_id is not None:
            self._speak(self.bridge.react(events, self._help_context()))

    def _crew_outcome(self) -> None:
        if self.bridge is None:
            return
        o = self.world.outcome
        won = None if o.winner is None else (o.winner == self.side)
        self._speak(self.bridge.outcome(won))
        self.bridge.save(self.hidden)

    def _crew_command(self, val: object) -> None:
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

    def close(self) -> None:
        """Leaving the battle: remember how the officers feel, stop any LLM requests."""
        if self.bridge is not None:
            self.bridge.save(self.hidden)
            self.bridge.close()
        if self.translator is not None:
            self.translator.close()
        self.comms.close()
        self.orders.close()

    def _chart(self, opts: dict[str, object]) -> None:
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

    def _transfer(self, sid: int) -> None:
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

    def _key_binding(self, val: tuple[str, str] | None) -> None:
        if val is None:
            if not self.keys:
                self._log("No keys defined. e.g. 'key F5 fire all phasers 10'.", theme.TEXT_DIM)
            for k, v in sorted(self.keys.items()):
                self._log(f"{k:<4} {v}", theme.TEXT, mono=True)
            return
        name, text = val
        if text:
            self.keys[name] = text
            self._log(f"{name} = {text}", theme.TEXT_DIM)
        else:
            self.keys.pop(name, None)
            self._log(f"{name} cleared.", theme.TEXT_DIM)

    # ------------------------------------------------------------ manual

    def _help_context(self) -> HelpContext:
        return HelpContext(self.world.content, self.world.observe(self.side), self.player)

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

    def run_key(self, name: str) -> bool:
        text = self.keys.get(name)
        if not text:
            return False
        self.run_console(text)
        return True

    def _status_report(self) -> None:
        p = self.player
        if p is None:
            return
        self._log(f"{p.name}: warp {p.warp:.1f}, course {p.course:.0f}, crew {p.crew}, hull "
                  f"{max(0.0, p.structure) / p.structure_max * 100:.0f}%, torps {p.torps_remaining}, probes {p.probes_remaining}",
                  theme.TEXT)

    # ------------------------------------------------------------ drawing

    def draw(self, surf: pygame.Surface) -> None:
        self.ui.begin_frame()
        surf.fill((5, 9, 18))
        alert = self._red_alert()
        theme.set_alert(alert)
        if alert > 0 and not self._was_alert:
            self.audio.play("alert", time.monotonic(), 0.0, 0.8)
        self._was_alert = alert > 0
        tick_len = 1.0 / self.world.rules.ticks_per_cycle
        alpha = 1.0 if self.paused else max(0.0, min(1.0, self.acc / tick_len))
        obs = self.world.observe(self.side)
        p = self.player
        self.view.draw(surf, obs, self.prev, self.now, alpha, self.player_id,
                       p.target if p else None, p.target_subsystem if p else None, self.selected_ally)
        self.ui.add(self.map_rect, lambda: None)
        acts = self._activity(obs)
        officer_view.draw_intent(surf, self.cam, obs, p, acts, self._officer_name)
        comms_view.draw_map(surf, self.cam, self.world, self.side, self.player_id, self.comms, time.monotonic(),
                            self.map_rect)
        self._map_overlay_text(surf)
        officer_view.draw_panel(surf, (self.map_rect.x + 14, self.map_rect.y + 36), acts, self._officer_name,
                                self.world.tick, self.world.rules.ticks_per_cycle)
        self._draw_printout(surf)
        self._bottom(surf)
        self._column(surf)
        if self.overlay:
            self._draw_overlay(surf)
        if self.toast:
            msg, col, t = self.toast
            w = theme.text_width(msg, 13) + 24
            r = pygame.Rect(0, 0, w, 30)
            r.midbottom = (self.map_rect.centerx, self.map_rect.bottom - 14)
            pygame.draw.rect(surf, theme.BG_PANEL_HI, r, border_radius=4)
            pygame.draw.rect(surf, col, r, 1, border_radius=4)
            theme.text(surf, msg, r.center, col, 13, anchor="center")
        self.ui.draw_tooltip(surf)
        theme.set_alert(0.0)
        for name, x, y in self.view.take_sounds():
            heard = self._heard_at(x, y)
            if heard is not None:
                self.audio.play(name, time.monotonic(), *heard)

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

    def _red_alert(self) -> float:
        """How red the panel borders are right now: a slow pulse while the ship is in a fight, else 0."""
        p = self.player
        if p is None or not p.alive or self.world.outcome.over or not in_battle(self.world, p):
            return 0.0
        return RED_ALERT_FLOOR + RED_ALERT_PULSE * (0.5 + 0.5 * math.sin(time.monotonic() * math.tau / RED_ALERT_PERIOD))

    def _map_overlay_text(self, surf: pygame.Surface) -> None:
        r = self.map_rect
        t = self.world.time
        state = "PAUSED" if self.paused else f"{self.speed:g}×"
        col = theme.CAUTION if self.paused else theme.GOOD
        theme.text(surf, f"Cycle {t:7.1f}", (r.x + 14, r.y + 10), theme.TEXT, 14, "mono")
        theme.text(surf, state, (r.x + 130, r.y + 10), col, 14, "mono", weight="medium")
        if theme.border() != theme.BORDER:
            theme.text(surf, "RED ALERT", (r.x + 180, r.y + 12), theme.mix(theme.TEXT_DIM, theme.ALERT, 0.8), 11,
                       weight="semibold")
        if self.paused and not self.world.outcome.over:
            # hard to miss: nothing moves, charges or reloads while paused
            msg = "PAUSED  ·  press Space to run"
            b = pygame.Rect(0, 0, theme.text_width(msg, 14, weight="semibold") + 32, 30)
            b.midtop = (r.centerx, r.y + 10)
            pygame.draw.rect(surf, theme.BG_PANEL_HI, b, border_radius=4)
            pygame.draw.rect(surf, theme.CAUTION, b, 1, border_radius=4)
            theme.text(surf, msg, b.center, theme.CAUTION, 14, weight="semibold", anchor="center")
        self._draw_conn_banner(surf, r.y + (46 if self.paused and not self.world.outcome.over else 10))
        theme.text(surf, self.battle.setup.title, (r.right - 14, r.y + 10), theme.TEXT_DIM, 12, anchor="topright")
        theme.text(surf, f"range {self.display_range():,.0f}  ·  F1 controls", (r.right - 14, r.y + 28), theme.TEXT_FAINT,
                   11, anchor="topright")
        y = r.y + 48
        for names, eta in self._inbound():
            # reinforcements on the way: a countdown that pulses as they get close
            close = eta < 15
            pulse = 0.5 + 0.5 * math.sin(time.monotonic() * math.tau / 0.9) if close else 1.0
            col = theme.mix(theme.TEXT_DIM, theme.GOOD, 0.4 + 0.6 * pulse)
            theme.text(surf, f"{names}  ·  ETA {eta:4.0f} cycles", (r.right - 14, y), col, 13, "mono", anchor="topright")
            y += 20
        comms_view.draw_card(surf, (r.right - 14, y + 4), self.world, self.side, self.player_id, self.comms, self.ui,
                             time.monotonic(), self._comms_button)

    def _draw_conn_banner(self, surf: pygame.Surface, top: int) -> None:
        """Who has the conn, when it isn't the captain; click it to take the bridge back."""
        ship, b = self.player, self.bridge
        o = b.find(ship.conn) if ship is not None and ship.conn and b is not None else None
        if o is None:
            if ship is not None and ship.evasive:
                self._draw_evasive_banner(surf, top)
            return
        msg = f"{o.name.upper()} HAS THE CONN  ·  say \"I have the bridge\" to take it back"
        box = pygame.Rect(0, 0, theme.text_width(msg, 13, weight="semibold") + 32, 28)
        box.midtop = (self.map_rect.centerx, top)
        pygame.draw.rect(surf, theme.BG_PANEL_HI, box, border_radius=4)
        pygame.draw.rect(surf, theme.CREW, box, 2, border_radius=4)
        theme.text(surf, msg, box.center, theme.CREW, 13, weight="semibold", anchor="center")
        self.ui.add(box, lambda: self.run_console("I have the bridge"), "Take the bridge back")

    def _draw_evasive_banner(self, surf: pygame.Surface, top: int) -> None:
        """Evasive manoeuvres are on: amber while the helm is dodging; click to end them."""
        dodging = any(a.role == "evasive" and a.kind == "evade" for a in self._activity(self.obs))
        msg = "EVASIVE MANOEUVRES  ·  " + ("dodging torpedoes" if dodging else "watching for torpedoes") + \
              "  ·  any helm order ends them"
        col = theme.CAUTION if dodging else theme.FRIEND
        box = pygame.Rect(0, 0, theme.text_width(msg, 13, weight="semibold") + 32, 28)
        box.midtop = (self.map_rect.centerx, top)
        pygame.draw.rect(surf, theme.BG_PANEL_HI, box, border_radius=4)
        pygame.draw.rect(surf, col, box, 2, border_radius=4)
        theme.text(surf, msg, box.center, col, 13, weight="semibold", anchor="center")
        self.ui.add(box, lambda: self.run_console("evasive off"), "End evasive manoeuvres (or give any helm order)")

    def _draw_printout(self, surf: pygame.Surface) -> None:
        """The latest Begin text display, in the map's lower-left corner."""
        if not self.printout:
            return
        lines = self.printout[:30]
        size = 12
        lh = 15
        w = min(self.map_rect.width - 24, max(theme.text_width(t, size, "mono") for t in lines) + 24)
        h = lh * len(lines) + 30
        r = pygame.Rect(self.map_rect.x + 12, self.map_rect.bottom - h - 12, w, h)
        panel = pygame.Surface(r.size, pygame.SRCALPHA)
        panel.fill((*theme.BG_PANEL, 228))
        surf.blit(panel, r)
        pygame.draw.rect(surf, theme.BORDER_HI, r, 1, border_radius=4)
        y = r.y + 8
        for t in lines:
            theme.text(surf, t, (r.x + 12, y), theme.TEXT, size, "mono")
            y += lh
        theme.text(surf, "Esc closes" + (" · live" if self.printout_cmd else ""), (r.right - 10, r.bottom - 17),
                   theme.TEXT_FAINT, 10, anchor="topright")

    def _bottom(self, surf: pygame.Surface) -> None:
        r = self.bottom_rect
        pygame.draw.rect(surf, theme.BG_PANEL, r, border_radius=4)
        pygame.draw.rect(surf, theme.border(), r, 1, border_radius=4)
        # time controls
        x = r.x + 10
        y = r.y + 8
        self.ui.button(surf, pygame.Rect(x, y, 70, 24), "▶ Run" if self.paused else "❚❚ Pause",
                       lambda: setattr(self, "paused", not self.paused), "Space", active=not self.paused, accent=theme.GOOD)
        x += 78
        for s in SPEEDS:
            label = f"{s:g}×"
            self.ui.button(surf, pygame.Rect(x, y, 46, 24), label, partial(setattr, self, "speed", s),
                           "Simulation speed ([ and ])", active=self.speed == s)
            x += 50
        theme.text(surf, "Orders also work while paused.", (x + 8, y + 5), theme.TEXT_FAINT, 11)
        # log
        lines_area = pygame.Rect(r.x + 10, r.y + 40, r.width - 20, r.height - 76)
        n = lines_area.height // 16
        end = len(self.log) - self.log_scroll
        for i, line in enumerate(self.log[max(0, end - n):end]):
            theme.text(surf, line.text[:160], (lines_area.x, lines_area.y + i * 16), line.color, 12,
                       "mono" if line.mono else "ui")
        if self.log_scroll:
            theme.text(surf, f"↑ {self.log_scroll} older · wheel to scroll", (lines_area.right, lines_area.y),
                       theme.TEXT_FAINT, 11, anchor="topright")
        # console
        self.console_rect = pygame.Rect(r.x + 8, r.bottom - 32, r.width - 16, 26)
        pygame.draw.rect(surf, theme.BG_INPUT, self.console_rect, border_radius=3)
        pygame.draw.rect(surf, theme.FRIEND if self.console_focus else theme.BORDER, self.console_rect, 1, border_radius=3)
        prompt = "› " + self.console
        if self.console_focus and (pygame.time.get_ticks() // 500) % 2 == 0:
            prompt += "▏"
        if not self.console and not self.console_focus:
            theme.text(surf, "Command console: press Enter and type an order (e.g. 'al tor al mk7 250', 'fp all s 10', 'help')",
                       (self.console_rect.x + 10, self.console_rect.y + 5), theme.TEXT_FAINT, 12)
        else:
            theme.text(surf, prompt, (self.console_rect.x + 10, self.console_rect.y + 4), theme.TEXT, 13, "mono")

    def _column(self, surf: pygame.Surface) -> None:
        r = self.col_rect
        fixed = sum(p.min_height for p in self.panels if p.weight == 0)
        gap = 8
        free = r.height - fixed - gap * (len(self.panels) - 1)
        wsum = sum(p.weight for p in self.panels) or 1.0
        y = r.y
        for p in self.panels:
            h = p.min_height if p.weight == 0 else max(p.min_height, int(free * p.weight / wsum))
            p.draw(surf, pygame.Rect(r.x, y, r.width, h), self)
            y += h + gap

    # ------------------------------------------------------------ overlays

    def _modal(self, surf: pygame.Surface, w: int, h: int, title: str, accent: theme.Color = theme.FRIEND) -> pygame.Rect:
        shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        shade.fill((2, 5, 12, 170))
        surf.blit(shade, (0, 0))
        r = pygame.Rect(0, 0, w, h)
        r.center = (surf.get_width() // 2, surf.get_height() // 2)
        theme.panel(surf, r, title, accent)
        return r

    def _draw_overlay(self, surf: pygame.Surface) -> None:
        o = self.overlay
        if o == "help_brief":
            r = pygame.Rect(0, 0, 520, 132)
            r.center = self.map_rect.center
            pygame.draw.rect(surf, theme.BG_PANEL, r, border_radius=6)
            pygame.draw.rect(surf, theme.BORDER_HI, r, 1, border_radius=6)
            theme.text(surf, "Space to begin.  Left-click a contact to target it,", (r.centerx, r.y + 22), theme.TEXT, 15, anchor="center")
            theme.text(surf, "right-click the map to steer, F / T / P to fire.", (r.centerx, r.y + 46), theme.TEXT, 15, anchor="center")
            theme.text(surf, "Enter opens the console. H opens the manual, F1 the controls.", (r.centerx, r.y + 78),
                       theme.TEXT_DIM, 13, anchor="center")
            theme.text(surf, "(any key or click to dismiss)", (r.centerx, r.y + 104), theme.TEXT_FAINT, 11, anchor="center")
        elif o == "help":
            r = self._modal(surf, 640, 40 + 22 * len(CONTROLS) + 20, "Controls")
            y = r.y + 34
            for k, v in CONTROLS:
                theme.text(surf, k, (r.x + 24, y), theme.FRIEND, 13, "mono")
                theme.text(surf, v, (r.x + 250, y), theme.TEXT, 13)
                y += 22
        elif o == "menu":
            r = self._modal(surf, 360, 190, "Battle")
            self.ui.button(surf, pygame.Rect(r.x + 30, r.y + 44, r.width - 60, 34), "Resume",
                           lambda: setattr(self, "overlay", None), size=14)
            self.ui.button(surf, pygame.Rect(r.x + 30, r.y + 88, r.width - 60, 34), "Manual",
                           lambda: self.open_manual(), size=14)
            self.ui.button(surf, pygame.Rect(r.x + 30, r.y + 132, r.width - 60, 34), "Leave battle",
                           self.on_exit, size=14, accent=theme.ALERT)
        elif o == "manual":
            w, h = surf.get_size()
            self.manual.draw(surf, pygame.Rect(24, 24, w - 48, h - 48), self.ui)
        elif o == "damage":
            self._damage_view(surf)
        elif o == "scan":
            self._scan_view(surf)
        elif o == "debrief":
            self._debrief(surf)

    def _damage_view(self, surf: pygame.Surface) -> None:
        p = self.player
        if p is None:
            self.overlay = None
            return
        r = self._modal(surf, 860, 560, f"Damage assessment — {p.name}")
        fixing, hull_fixing = under_repair(self.world, p)
        hull_diagram(surf, p, pygame.Rect(r.x + 20, r.y + 40, 380, 400), repairing=fixing, ui=self.ui)
        diagram_legend(surf, r.x + 20, r.y + 446)
        x = r.x + 420
        y = r.y + 40
        hf = max(0.0, p.structure) / p.structure_max
        hull_note = "  under repair" if hull_fixing else ""
        theme.text(surf, f"Hull {hf * 100:.0f}%{hull_note}", (x, y), theme.REPAIR if hull_fixing else theme.TEXT_DIM, 12)
        if hull_fixing and p.docked_to is None and hf < self.world.rules.hull_field_limit:
            theme.text(surf, f"(crews patch it to {self.world.rules.hull_field_limit * 100:.0f}%; a base does the rest)",
                       (x + 170, y), theme.TEXT_FAINT, 11)
        y += 24
        groups: dict[Kind, list] = {}
        for s in p.subsystems():
            groups.setdefault(s.kind, []).append(s)
        for kind, subs in groups.items():
            theme.text(surf, subs[0].label.split(" ")[0] if len(subs) > 1 else subs[0].label, (x, y), theme.TEXT_DIM, 12)
            xx = x + 120
            for s in subs:
                col = theme.health_color(s.health, s.destroyed)
                rr = pygame.Rect(xx, y + 2, 34, 12)
                theme.bar(surf, rr, s.health, col)
                if s.sid in fixing:
                    prio = s.kind == p.repair_priority
                    pygame.draw.rect(surf, theme.REPAIR, rr.inflate(4, 4), 2 if prio else 1, border_radius=2)
                if s.damage:
                    theme.text(surf, f"{s.damage}", (rr.centerx, rr.bottom + 1), col, 9, "mono", anchor="midtop")
                xx += 40
                if xx > r.right - 40:
                    xx = x + 120
                    y += 26
            y += 28
        theme.text(surf, "Outlined: under repair (bold: the priority).  Damaged weapons must be fully repaired before they "
                         "charge again.  'repair <system>' sets priority.",
                   (r.x + 20, r.bottom - 26), theme.TEXT_FAINT, 11)

    def _scan_view(self, surf: pygame.Surface) -> None:
        p = self.player
        c = self.obs.contact(p.target) if p and p.target is not None else None
        if c is None or c.scan is None:
            self.overlay = None
            return
        sc = c.scan
        r = self._modal(surf, 720, 420, f"Scan — {c.label}", theme.HOSTILE)
        y = r.y + 40
        theme.text(surf, f"Confidence {sc.confidence * 100:.0f}% · {((self.obs.tick - sc.tick) * self.obs.rules.dt):.0f} cycles old",
                   (r.x + 20, y), theme.TEXT_DIM, 12)
        y += 24
        for i, v in enumerate(sc.shields):
            theme.text(surf, f"Shield {i + 1}", (r.x + 20, y), theme.TEXT_DIM, 12)
            theme.bar(surf, pygame.Rect(r.x + 110, y + 3, 200, 10), max(0, v) / 100, theme.SHIELD if v > 0 else theme.ALERT)
            theme.text(surf, "down" if v < 0 else f"{v:.0f}%", (r.x + 320, y), theme.TEXT, 12, "mono")
            y += 20
        y += 8
        theme.text(surf, f"Crew ~{sc.crew} · hull {sc.structure_frac * 100:.0f}% · charged banks {sc.charged_banks} · "
                         f"loaded tubes {sc.loaded_tubes} · probes {sc.probes_loaded}", (r.x + 20, y), theme.TEXT, 13)
        y += 28
        bad = sorted(((d, sid) for sid, d in sc.subsystems.items() if d > 0), reverse=True)[:12]
        theme.text(surf, "Damaged systems (estimated):" if bad else "No damage resolved.", (r.x + 20, y), theme.TEXT_DIM, 12)
        y += 20
        for i, (d, sid) in enumerate(bad):
            theme.text(surf, f"{sid}: {d}%", (r.x + 20 + (i % 3) * 220, y + (i // 3) * 18),
                       theme.health_color(1 - d / 100, d >= 100), 12, "mono")

    def _debrief(self, surf: pygame.Surface) -> None:
        """The end of the battle: how it went, your ship's record, the officer who stood out, every ship's tally."""
        w = self.world
        res = self.assessment.sides(w)
        score = self.assessment.score(w, self.side)
        rows = list(w.ships.values())[:9]
        r = self._modal(surf, 800, 330 + 46 * len(res) + 18 * len(rows), "Battle assessment", theme.CAUTION)
        verdict = self.assessment.verdict(score)
        theme.text(surf, w.outcome.reason or "The engagement is over.", (r.x + 24, r.y + 36), theme.TEXT, 20, "display", weight="semibold")
        theme.text(surf, verdict, (r.x + 24, r.y + 68), theme.CAUTION, 14)
        theme.text(surf, f"Score {score:+.1f}   ·   {w.time:.0f} cycles", (r.right - 24, r.y + 44), theme.TEXT, 14, "mono",
                   anchor="topright")
        y = r.y + 100
        me = w.ships.get(self.player_id) if self.player_id is not None else None
        if me is not None:
            st = me.stats
            card = pygame.Rect(r.x + 16, y, r.width - 32, 72)
            pygame.draw.rect(surf, theme.BG_PANEL_HI, card, border_radius=4)
            theme.text(surf, f"{me.name} · {me.status.value}", (card.x + 12, card.y + 8), theme.FRIEND, 14, weight="medium")
            hull = max(0.0, me.structure / me.structure_max)
            stats = [("hull", f"{hull:.0%}", theme.health_color(hull)),
                     ("crew", f"{me.crew}/{me.cls.crew}", theme.TEXT),
                     ("morale", f"{reports.morale_words(me.morale)} {me.morale:.0f}", theme.health_color(me.morale / 100)),
                     ("phasers", _ratio(st.phaser_hits, st.phaser_shots), theme.TEXT),
                     ("torpedoes", _ratio(st.torpedo_hits, st.torpedoes_fired), theme.TEXT),
                     ("dealt", f"{st.damage_dealt:,.0f}", theme.GOOD),
                     ("taken", f"{st.damage_taken:,.0f}", theme.CAUTION),
                     ("kills", str(st.kills), theme.TEXT)]
            col_w = (card.width - 24) / len(stats)
            for k, (label, val, colr) in enumerate(stats):
                x = card.x + 12 + k * col_w
                theme.text(surf, label, (x, card.y + 32), theme.TEXT_FAINT, 10)
                theme.text(surf, val, (x, card.y + 46), colr, 13, "mono")
            y = card.bottom + 14
        crew = self.battle.crew
        best = None
        if crew is not None and self.player_id is not None:
            from ..crew.review import standout

            best = standout(crew.officers.values(), self.player_id, w.command_log, self.deeds)
        if best is not None:
            theme.text(surf, "STANDOUT OFFICER", (r.x + 24, y - 2), theme.TEXT_DIM, 11, "display", weight="medium")
            theme.text(surf, best.line(), (r.x + 24, y + 15), theme.CREW, 13)
        elif crew is not None:
            theme.text(surf, "You fought the ship yourself: your officers gave no orders of their own.", (r.x + 24, y + 8),
                       theme.TEXT_DIM, 12)
        y += 44
        for side, sr in sorted(res.items()):
            name = w.side_names.get(side, f"Side {side}")
            col = theme.FRIEND if side == self.side else theme.HOSTILE
            theme.text(surf, name + (" (you)" if side == self.side else ""), (r.x + 24, y), col, 14, weight="medium")
            theme.text(surf, f"{sr.ships} ships · lost {sr.lost} · disabled {sr.disabled} · escaped {sr.escaped} · "
                             f"surrendered {sr.surrendered} · strength {sr.loss * -100:+.0f}%",
                       (r.x + 24, y + 20), theme.TEXT_DIM, 12)
            y += 46
        y += 6
        for s in rows:
            st = s.stats
            col = theme.FRIEND if s.side == self.side else theme.HOSTILE
            theme.text(surf, f"{s.name} ({s.cls.abbrev})", (r.x + 24, y), col, 12)
            theme.text(surf, f"{s.status.value:<11} dealt {st.damage_dealt:6.0f}  taken {st.damage_taken:6.0f}  "
                             f"phaser hits {st.phaser_hits}/{st.phaser_shots}  torps {st.torpedo_hits}/{st.torpedoes_fired}  "
                             f"intercepts {st.ordnance_intercepted}", (r.x + 200, y), theme.TEXT_DIM, 11, "mono")
            y += 18
        self.ui.button(surf, pygame.Rect(r.right - 224, r.bottom - 46, 200, 30), self.exit_label, self.on_exit, size=13)
        self.ui.button(surf, pygame.Rect(r.right - 392, r.bottom - 46, 160, 30), "Review the field",
                       lambda: setattr(self, "overlay", None), size=13)


def _ratio(hits: int, shots: int) -> str:
    return f"{hits}/{shots}"


def _exact_verb(text: str) -> bool:
    """The line starts with a console verb spelled in full (not a number, prefix or ordinary word)."""
    first = text.strip().lower().split(None, 1)[:1]
    return bool(first) and any(first[0] in spellings for spellings in VERBS.values())


__all__ = ["BattleScene", "CONTROLS", "SPEEDS"]
