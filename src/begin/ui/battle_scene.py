"""The battle screen: fixed-step simulation, tactical map, HUD, console and overlays.

The simulation advances in fixed ticks (10 per cycle; one cycle is one
second at 1×) from an accumulator fed by wall-clock time × the chosen
speed. Rendering interpolates between the last two ticks. Pausing stops
the accumulator; orders can still be given while paused.
"""

from __future__ import annotations

import math
from functools import partial
from dataclasses import dataclass
from typing import Callable

import pygame

from ..battle import Battle
from ..console import reports
from ..console.parser import ParseContext, parse
from ..core.angles import bearing, norm360
from ..sim.allies import AllyStanding
from ..sim.commands import (
    AllyOrder, Command, FirePhasers, FireTorpedoes, LaunchProbe, Pursue, Scan, SelectTarget, SetBanks, SetHelm,
    SetPointDefense, SetShields,
)
from ..sim.events import CommandRejected, Event, Message, ScanCompleted, Tone
from ..sim.observation import Observation
from ..sim.scoring import Assessment
from ..sim.ship import BankRole, Kind, Ship
from . import theme
from .camera import Camera
from ..crew.conversation import Bridge, Utterance
from ..crew.officers import station_of
from ..help.coach import HelpContext
from .manual import ManualView
from .hud import (
    PD_CYCLE, SUB_GROUPS, ContactsPanel, CrewPanel, FleetPanel, OwnShipPanel, Panel, TabbedPanel, TargetPanel, WeaponsPanel,
    hull_diagram,
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


class BattleScene:
    def __init__(self, battle: Battle, size: tuple[int, int], on_exit: Callable[[], None],
                 keys: dict[str, str] | None = None, hidden: dict[str, object] | None = None,
                 llm: dict[str, object] | None = None, chatter: bool = True) -> None:
        self.battle = battle
        self.world = battle.world
        self.player_id = battle.player_ship_id
        self.side = battle.setup.player_side if battle.setup.player_side >= 0 else 0
        self.on_exit = on_exit
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
        self.chart_sort = "name"
        self.chart_hidden: set[int] = set()
        self.chart_all = False
        self.chart_origin: int | None = None
        self.keys: dict[str, str] = keys if keys is not None else {}
        self.manual = ManualView(self._help_context, self._try_command, self._close_manual)
        self.hidden: dict[str, object] = hidden if hidden is not None else {}
        self.bridge: Bridge | None = None
        llm_note: str | None = None
        if battle.crew is not None:
            service = None
            try:
                from ..llm.providers import config_from_settings, make_provider
                from ..llm.service import LLMService

                cfg = config_from_settings(llm or {})
                if cfg is not None:
                    service = LLMService(make_provider(cfg))
                    llm_note = f"Officers are talking through {cfg.provider} ({cfg.model})."
            except Exception as e:  # noqa: BLE001 - a bad LLM setup must never stop a battle
                llm_note = f"LLM not available ({e}); officers will answer offline."
            self.bridge = Bridge(battle.crew, self.hidden, service, seed=battle.setup.seed, chatter=chatter)
        self.layout(size)
        self._frame_all()
        self._log("Battle stations. The simulation is paused: press Space to begin.", theme.CAUTION)
        if battle.setup.description:
            self._log(battle.setup.description, theme.TEXT_DIM)
        if llm_note:
            self._log(llm_note, theme.TEXT_DIM)

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
        self._crew_react(events)
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
        self.ui.mouse = pygame.mouse.get_pos()
        if self.bridge is not None and self.bridge.llm is not None:
            self._speak(self.bridge.poll(self._help_context(), self._officer_run))
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

    def _run_one(self, text: str) -> None:
        self._log(f"> {text}", theme.FRIEND)
        if self.player_id is None:
            self._log("No ship under command.", theme.CAUTION)
            return
        if self.bridge is not None:
            hit = self.bridge.addressed(text)
            if hit is not None:
                self._ask(*hit)
                return
        res = parse(text, ParseContext(self.player_id, self.world.observe(self.side)))
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
            reason = self.issue(cmd)
            if reason is None:
                self._log(f"  {cmd.describe()}: acknowledged", theme.TEXT_DIM)
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

    # ------------------------------------------------------------ bridge officers

    def _ask(self, officer: object, words: str) -> None:
        if self.bridge is None:
            return
        from ..crew.characters import OfficerProfile

        assert isinstance(officer, OfficerProfile)
        self._speak(self.bridge.ask(officer, words, self._help_context(), self._officer_run))

    def _officer_run(self, line: str, officer: object) -> str | None:
        """Carry out a console line an officer was told (or decided) to run; only their own stations."""
        from ..crew.characters import OfficerProfile
        from ..sim.commands import DelegateStation

        assert isinstance(officer, OfficerProfile)
        if self.player_id is None:
            return "No ship under command."
        res = parse(line, ParseContext(self.player_id, self.world.observe(self.side)))
        if res.error:
            return res.error
        if res.actions and not res.commands:
            return "That is for the captain to do."
        allowed = set(officer.advises) | {officer.station}
        for cmd in res.commands:
            st = cmd.station if isinstance(cmd, DelegateStation) else station_of(cmd)
            if st is None or st not in allowed:
                return "That is not my station, Captain."
        for cmd in res.commands:
            cmd.source = officer.title
            reason = self.issue(cmd)
            if reason:
                return reason
            self._log(f"  {cmd.describe()}: done", theme.TEXT_DIM)
        if res.display:
            self._show(res.display, None)
        return None

    def _speak(self, lines: list[Utterance]) -> None:
        tone = {"crew": theme.CREW, "caution": theme.CAUTION, "dim": theme.TEXT_DIM}
        for u in lines:
            self._log(f"{u.speaker}: {u.text}", tone.get(u.tone, theme.CREW))
            for c in u.commands:
                self._log(f"    › {c}", theme.TEXT_DIM)

    def address(self, name: str) -> None:
        """Open the console ready to speak to an officer."""
        self.console = f"{name}, "
        self.console_focus = True

    def _crew_react(self, events: list[Event]) -> None:
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
        lines = ["BRIDGE CREW:", "Station      Officer                     Running   Rapport"]
        for st, o in b.crew.officers.items():
            on = ship is not None and st in ship.delegated
            mood = b.relationships.get(o.id).mood
            lines.append(f"{st.title():<12} {o.title:<27} {'officer' if on else 'captain':<9} {mood}")
        lines.append("delegate <station>|all · assume <station>|all · ask <officer> <words> · <officer>, <words>")
        self._show(lines, None)

    def close(self) -> None:
        """Leaving the battle: remember how the officers feel, stop any LLM requests."""
        if self.bridge is not None:
            self.bridge.save(self.hidden)
            self.bridge.close()

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
        tick_len = 1.0 / self.world.rules.ticks_per_cycle
        alpha = 1.0 if self.paused else max(0.0, min(1.0, self.acc / tick_len))
        obs = self.world.observe(self.side)
        p = self.player
        self.view.draw(surf, obs, self.prev, self.now, alpha, self.player_id,
                       p.target if p else None, p.target_subsystem if p else None, self.selected_ally)
        self.ui.add(self.map_rect, lambda: None)
        self._map_overlay_text(surf)
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

    def _map_overlay_text(self, surf: pygame.Surface) -> None:
        r = self.map_rect
        t = self.world.time
        state = "PAUSED" if self.paused else f"{self.speed:g}×"
        col = theme.CAUTION if self.paused else theme.GOOD
        theme.text(surf, f"Cycle {t:7.1f}", (r.x + 14, r.y + 10), theme.TEXT, 14, "mono")
        theme.text(surf, state, (r.x + 130, r.y + 10), col, 14, "mono", weight="medium")
        theme.text(surf, self.battle.setup.title, (r.right - 14, r.y + 10), theme.TEXT_DIM, 12, anchor="topright")
        theme.text(surf, f"range {self.display_range():,.0f}  ·  F1 controls", (r.right - 14, r.y + 28), theme.TEXT_FAINT,
                   11, anchor="topright")

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
        pygame.draw.rect(surf, theme.BORDER, r, 1, border_radius=4)
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
            theme.text(surf, "Command console: press Enter and type an order (e.g. 'al tor al mk7 400', 'fp all s 10', 'help')",
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
        hull_diagram(surf, p, pygame.Rect(r.x + 20, r.y + 40, 380, 480))
        x = r.x + 420
        y = r.y + 40
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
                if s.damage:
                    theme.text(surf, f"{s.damage}", (rr.centerx, rr.bottom + 1), col, 9, "mono", anchor="midtop")
                xx += 40
                if xx > r.right - 40:
                    xx = x + 120
                    y += 26
            y += 28
        theme.text(surf, "Damaged weapons must be fully repaired before they charge again.  'repair <system>' sets priority.",
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
        w = self.world
        res = self.assessment.sides(w)
        score = self.assessment.score(w, self.side)
        r = self._modal(surf, 760, 470, "Battle assessment", theme.CAUTION)
        verdict = self.assessment.verdict(score)
        theme.text(surf, w.outcome.reason or "The engagement is over.", (r.x + 24, r.y + 40), theme.TEXT, 16, weight="semibold")
        theme.text(surf, verdict, (r.x + 24, r.y + 66), theme.CAUTION, 14)
        theme.text(surf, f"Score {score:+.1f}   ·   {w.time:.0f} cycles", (r.right - 24, r.y + 42), theme.TEXT, 14, "mono",
                   anchor="topright")
        y = r.y + 104
        for side, sr in sorted(res.items()):
            name = w.side_names.get(side, f"Side {side}")
            col = theme.FRIEND if side == self.side else theme.HOSTILE
            theme.text(surf, name + (" (you)" if side == self.side else ""), (r.x + 24, y), col, 14, weight="medium")
            theme.text(surf, f"{sr.ships} ships · lost {sr.lost} · disabled {sr.disabled} · escaped {sr.escaped} · "
                             f"surrendered {sr.surrendered} · strength {sr.loss * -100:+.0f}%",
                       (r.x + 24, y + 20), theme.TEXT_DIM, 12)
            y += 46
        y += 6
        for s in list(w.ships.values())[:9]:
            st = s.stats
            col = theme.FRIEND if s.side == self.side else theme.HOSTILE
            theme.text(surf, f"{s.name} ({s.cls.abbrev})", (r.x + 24, y), col, 12)
            theme.text(surf, f"{s.status.value:<11} dealt {st.damage_dealt:6.0f}  taken {st.damage_taken:6.0f}  "
                             f"phaser hits {st.phaser_hits}/{st.phaser_shots}  torps {st.torpedo_hits}/{st.torpedoes_fired}  "
                             f"intercepts {st.ordnance_intercepted}", (r.x + 200, y), theme.TEXT_DIM, 11, "mono")
            y += 18
        self.ui.button(surf, pygame.Rect(r.right - 184, r.bottom - 46, 160, 30), "Return to menu", self.on_exit, size=13)
        self.ui.button(surf, pygame.Rect(r.right - 352, r.bottom - 46, 160, 30), "Review the field",
                       lambda: setattr(self, "overlay", None), size=13)


__all__ = ["BattleScene", "CONTROLS", "SPEEDS"]
