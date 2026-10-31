"""The battle screen: fixed-step simulation, tactical map, HUD, console and overlays.

The simulation advances in fixed ticks (10 per cycle; one cycle is one
second at 1×) from an accumulator fed by wall-clock time × the chosen
speed. Rendering interpolates between the last two ticks. Pausing stops
the accumulator; orders can still be given while paused.

This module holds the scene's state and frame loop. Its other parts live in `ui/battle/` and are mixed in:
input (keys and mouse), console (typed orders), orders (named orders and the translator), comms (officers
and hails) and render (drawing). `ui/battle/state.py` declares the state they share.
"""

from __future__ import annotations

import math
import time
from typing import Callable

import pygame

from ..battle import Battle
from ..console import reports
from ..console.orders import OrderBook, OrderRun
from ..console.translator import Translator
from ..crew.conversation import Bridge
from ..crew.hails import Comms, load_lines
from ..help.coach import HelpContext
from ..sim.allies import AllyStanding
from ..sim.commands import AllyOrder, Command, FirePhasers, FireTorpedoes, LaunchProbe, SetBanks
from ..sim.events import Event, Message, ObjectiveEnded, ProjectCompleted, ScanCompleted
from ..sim.observation import Observation
from ..sim.scoring import Assessment
from ..sim.ship import BankRole, Ship
from ..sim.world import World
from . import theme
from .audio import Audio
from .battle.common import CONTROLS, SPEEDS, TONE_COLOR, LogLine, TourLink
from .battle.comms import CommsMixin
from .battle.console import ConsoleMixin
from .battle.input import InputMixin
from .battle.orders import OrdersMixin
from .battle.render import RenderMixin
from .camera import Camera
from .hit_report import HitReport
from .hud import ContactsPanel, CrewPanel, FleetPanel, OwnShipPanel, Panel, TabbedPanel, TargetPanel, WeaponsPanel
from .manual import ManualView
from .tactical import Snapshot, TacticalView
from .tween import Tweens
from .widgets import UI


class BattleScene(InputMixin, ConsoleMixin, OrdersMixin, CommsMixin, RenderMixin):
    def __init__(self, battle: Battle, size: tuple[int, int], on_exit: Callable[[], None],
                 keys: dict[str, str] | None = None, hidden: dict[str, object] | None = None,
                 llm: dict[str, object] | None = None, chatter: bool = True, volume: float = 0.6,
                 muted: bool = False, sounds: dict[str, str] | None = None) -> None:
        self.battle: Battle = battle
        self.world: World = battle.world
        self.player_id: int | None = battle.player_ship_id
        self.side: int = battle.setup.player_side if battle.setup.player_side >= 0 else 0
        self.on_exit: Callable[[], None] = on_exit
        self.exit_label: str = "Return to menu"
        self.tour: TourLink | None = None     # on a tour of duty: Starfleet answers `request reinforcements`
        self.ui: UI = UI()
        self.paused: bool = True
        self.speed: float = 1.0
        self.acc: float = 0.0
        self.omniscient: bool = False
        self.cam: Camera = Camera(pygame.Rect(0, 0, 100, 100), zoom=0.035, follow=self.player_id)
        self.view: TacticalView = TacticalView(self.cam)
        self.obs: Observation = self.world.observe(self.side)
        self.prev: Snapshot | None = None
        self.now: Snapshot = Snapshot.take(self.obs)
        self.log: list[LogLine] = []
        self.console: str = ""
        self.console_focus: bool = False
        self.history: list[str] = []
        self.hist_i: int = 0
        self.toast: tuple[str, theme.Color, float] | None = None
        self.hits: HitReport = HitReport(None)   # "Hits on Wraith: ..." lines in the log
        self.overlay: str | None = "help_brief"
        self.side_tabs: TabbedPanel = TabbedPanel([ContactsPanel(), FleetPanel(), CrewPanel()])
        self.panels: list[Panel] = [OwnShipPanel(), TargetPanel(), WeaponsPanel(), self.side_tabs]
        self.selected_ally: int | None = None
        self.assessment: Assessment = Assessment.begin(self.world)
        self.drag: tuple[int, int] | None = None
        self.dragged: bool = False
        # Begin's text displays: the latest one stays on the map, refreshed live, until dismissed
        self.printout: list[str] | None = None
        self.printout_cmd: str | None = None
        self.printout_tick: int = -1
        self.log_scroll: int = 0
        self.chart_auto: bool = False
        self.hud_detail: bool = False             # every number on the panels; otherwise hover a panel to see them
        self.tweens: Tweens = Tweens()              # panel numbers easing to their new values
        self.chart_sort: str = "name"
        self.chart_hidden: set[int] = set()
        self.chart_all: bool = False
        self.chart_origin: int | None = None
        self.keys: dict[str, str] = keys if keys is not None else {}
        self.manual: ManualView = ManualView(self._help_context, self._try_command, self._close_manual)
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
        self.comms: Comms = Comms(self.world, self.side, hail_llm, seed=battle.setup.seed,
                           lines=load_lines(override=config_dir() / "hails.toml"),
                           officers=(lambda st: crew.officer(st)) if crew is not None else None)
        self.orders: OrderBook = OrderBook.load(config_dir())
        self.order_run: OrderRun | None = None
        self.audio: Audio = Audio(volume, muted, sounds, config_dir() / "sounds")
        for problem in self.audio.problems:
            self._log(f"Couldn't use your sound {problem}", theme.TEXT_DIM)
        self._was_alert: bool = False
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

    # ------------------------------------------------------------ plain English

    # ------------------------------------------------------------ bridge officers

    def close(self) -> None:
        """Leaving the battle: remember how the officers feel, stop any LLM requests."""
        if self.bridge is not None:
            self.bridge.save(self.hidden)
            self.bridge.close()
        if self.translator is not None:
            self.translator.close()
        self.comms.close()
        self.orders.close()

    # ------------------------------------------------------------ manual

    def _help_context(self) -> HelpContext:
        return HelpContext(self.world.content, self.world.observe(self.side), self.player)

    # ------------------------------------------------------------ drawing

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

    # ------------------------------------------------------------ overlays


__all__ = ["BattleScene", "CONTROLS", "SPEEDS"]
