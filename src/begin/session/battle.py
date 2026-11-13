"""One battle, played: the game side of the battle screen, with no screen [E].

A `BattleSession` owns everything that makes a battle a game rather than a picture: the fixed-step clock,
the captain's orders (typed, clicked, spoken or proposed), the bridge officers and their language model, the
hails to enemy captains, plain-English translation, named orders, command styles and career, tour
reinforcements and the outcome. It never imports pygame. Whoever presents the battle (the battle screen, a
test, one day a network host) gives it time and orders and reads back what happened:

    session = BattleSession(build_battle(content, setup))
    session.subscribe(print)              # Line, Voice, Notice, Cue, Printout... (session/news.py)
    session.say("helm 90 warp 6")         # anything the console takes
    session.submit(FirePhasers(ship_id=session.player_id))
    session.update(1 / 60)                # time passes: officers think, the world steps
    session.observe()                     # what our side knows, to draw

The simulation advances in fixed ticks (10 per cycle; one cycle is one second at 1×) from an accumulator fed by
wall-clock time × the chosen speed; `acc` is what is left over, for a presenter that interpolates between ticks.
"""

from __future__ import annotations

import math
from pathlib import Path
from typing import TYPE_CHECKING, Callable

from ..battle import Battle
from ..console import reports
from ..console.orders import OrderBook, OrderRun, TacticalOrder
from ..console.translator import Translator
from ..crew.career import Career
from ..crew.characters import OfficerProfile
from ..crew.conversation import Bridge
from ..crew.review import standout
from ..crew.hails import Comms, load_lines
from ..crew.proposals import Proposal, Proposer
from ..help.coach import HelpContext
from ..paths import config_dir
from ..sim.allies import AllyStanding
from ..sim.commands import AllyOrder, Command, FirePhasers, FireTorpedoes, LaunchProbe, SetBanks
from ..sim.events import CommandRejected, Event, Message, ObjectiveEnded, ProjectCompleted, ScanCompleted
from ..sim.observation import Observation
from ..sim.scoring import Assessment
from ..sim.ship import BankRole, Ship
from ..sim.systems.sensors import ScanRecord
from ..sim.systems.repair import in_battle
from ..sim.world import World
from ..tour.run import TourRun
from .command import CommandMixin, Recording, load_alerts, load_phrasebook
from .comms import CommsMixin
from .common import CHART, EVENT_TONE, TourLink
from .console import ConsoleMixin
from .debrief import Debrief, SideTally
from .hit_report import HitReport
from .interface import Session
from .news import Commanding, Cue, Line, News, Notice, Show, Ticked
from .orders import OrdersMixin
from .prefs import BridgePrefs
from .voices import VoicesMixin

Listener = Callable[[News], None]
MAX_STEPS_PER_UPDATE = 12      # a stalled frame never makes the battle leap ahead


class BattleSession(ConsoleMixin, OrdersMixin, CommsMixin, CommandMixin, VoicesMixin):
    def __init__(self, battle: Battle, *, hidden: dict[str, object] | None = None,
                 llm: dict[str, object] | None = None, chatter: bool = True, prefs: BridgePrefs | None = None,
                 career: dict[str, object] | None = None, config: Path | None = None) -> None:
        folder = config if config is not None else config_dir()
        self._listeners: list[Listener] = []
        self._held: list[News] = []          # news from before anyone listened (the opening lines)
        self.battle = battle
        self.world: World = battle.world
        self.player_id = battle.player_ship_id
        self.side = battle.setup.player_side if battle.setup.player_side >= 0 else 0
        self.tour: TourLink | None = None     # on a tour of duty: Starfleet answers `request reinforcements`
        self.paused = True
        self.speed = 1.0
        self.acc = 0.0
        self.obs: Observation = self.world.observe(self.side)
        self.hits = HitReport(None)           # "Hits on Wraith: ..." lines in the log
        self._scans_seen: dict[int, ScanRecord] = {}   # the scan each contact last showed, for "what changed" [E]
        self.assessment = Assessment.begin(self.world)
        self.prefs = prefs if prefs is not None else BridgePrefs()
        self.captain_typing = False           # the presenter says so: proposals wait, or come as a chip
        self.busy_elsewhere = False           # the captain is reading a screen over the battle: no proposals
        self.chart_auto = False
        self.chart_sort = "name"
        self.chart_hidden: set[int] = set()
        self.chart_all = False
        self.chart_origin: int | None = None
        self.proposer = Proposer()
        self.proposal: Proposal | None = None
        self._propose_t = 0.0
        self.career = Career(career)
        self.alerts = load_alerts(folder / "alerts.toml")
        self.condition: str | None = None
        self.recording: Recording | None = None
        self.ran: list[str] = []
        self.style: str | None = None
        self.style_broken: str | None = None
        self.ribbon_won: str | None = None
        self._career_done = False
        self.ever_delegated: set[str] = set()
        self.trust_news: list[str] = []
        self.phrasebook = load_phrasebook()
        self.deeds: list[Event] = []          # objectives and projects finished: the officers' record for the debrief
        self.hidden = hidden if hidden is not None else {}
        self.bridge: Bridge | None = None
        self.translator: Translator | None = None
        self.llm_settings = llm if llm is not None else {}
        llm_note: str | None = None
        provider = None
        try:
            from ..llm.providers import config_from_settings, make_provider

            cfg = config_from_settings(self.llm_settings)
            if cfg is not None:
                from ..llm.routing import with_character

                routed = with_character(make_provider(cfg), self.llm_settings, self._faction_of)
                provider = routed.provider
                think = "" if cfg.think is None else f", thinking {'on' if cfg.think is True else 'off' if cfg.think is False else cfg.think}"
                who = "Officers are talking" if battle.crew is not None else "The console understands plain English"
                llm_note = f"{who} through {cfg.provider} ({cfg.model}{think})."
                if routed.note():
                    llm_note += " " + str(routed.note())
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
        # [E] hailing enemy captains: its own model worker, so a hail never queues behind an officer
        hail_llm = None
        if provider is not None:
            from ..llm.service import LLMService

            hail_llm = LLMService(provider, workers=1)
        crew = battle.crew
        self.comms = Comms(self.world, self.side, hail_llm, seed=battle.setup.seed,
                           lines=load_lines(override=folder / "hails.toml"),
                           officers=(lambda st: crew.officer(st)) if crew is not None else None)
        self.orders = OrderBook.load(folder)
        self.order_run: OrderRun | None = None
        if provider is not None and self.orders.orders:
            from ..llm.service import LLMService

            self.orders.llm = LLMService(provider, workers=1)
        self._log("Battle stations. The simulation is paused: press Space to begin.", "caution")
        if battle.setup.description:
            self._log(battle.setup.description, "dim")
        if llm_note:
            self._log(llm_note, "dim")
        self._order_problems(self.orders.prepare(self._would_run, self._translation_brief(), self._target_id()))

    # ------------------------------------------------------------ the outbox

    def subscribe(self, listener: Listener) -> None:
        """Hear everything the session says from now on (and what it said before anyone listened)."""
        self._listeners.append(listener)
        held, self._held = self._held, []
        for item in held:
            listener(item)

    def _emit(self, item: News) -> None:
        if not self._listeners:
            self._held.append(item)
            del self._held[:-400]
            return
        for fn in self._listeners:
            fn(item)

    def _log(self, text: str, tone: str = "text", mono: bool = False, channel: str = "computer") -> None:
        self._emit(Line(text, tone, channel, mono, self.world.tick))

    def _notice(self, text: str, tone: str = "caution", seconds: float = 3.0) -> None:
        self._emit(Notice(text, tone, seconds))

    def _cue(self, name: str, level: float = 0.6) -> None:
        self._emit(Cue(name, level))

    # ------------------------------------------------------------ what the presenter reads

    @property
    def player(self) -> Ship | None:
        return self.obs.own(self.player_id) if self.player_id is not None else None

    @property
    def tick_length(self) -> float:
        """Seconds of battle time in one tick, at 1×."""
        return 1.0 / self.world.rules.ticks_per_cycle

    @property
    def over(self) -> bool:
        return self.world.outcome.over

    @property
    def title(self) -> str:
        return self.battle.setup.title

    def officers(self) -> dict[str, OfficerProfile]:
        """The bridge officers by station (empty when the ship has none)."""
        return dict(self.bridge.crew.officers) if self.bridge is not None else {}

    def find_officer(self, who: str) -> OfficerProfile | None:
        """An officer by id, name or alias."""
        return self.bridge.find(who) if self.bridge is not None else None

    def in_command(self) -> OfficerProfile | None:
        """The officer who has the conn, if the captain handed it over."""
        p = self.player
        return self.find_officer(p.conn) if p is not None and p.conn else None

    def trust(self, officer: str) -> str:
        """How far an officer trusts the captain, in a word (crew/career.py)."""
        return self.career.level(officer)

    def named_orders(self) -> dict[str, TacticalOrder]:
        """The captain's named tactical orders (config/orders.toml)."""
        return dict(self.orders.orders)

    def running_order(self) -> str | None:
        """The named order running now, if any."""
        run = self.order_run
        return run.order.name if run is not None and not run.done else None

    def repair_officer(self, ship: Ship) -> OfficerProfile | None:
        """The officer directing the repair crews on one of our ships, if any."""
        crew = self.battle.crew
        return crew.repair_officer(ship) if crew is not None and crew.ship_id == ship.id else None

    def observe(self) -> Observation:
        """What our side knows now."""
        return self.obs

    def allies(self) -> list[Ship]:
        """Our other living ships, nearest first."""
        p = self.player
        out = [s for s in self.obs.own_ships() if p is None or s.id != p.id]
        if p is not None:
            out.sort(key=lambda s: math.hypot(s.x - p.x, s.y - p.y))
        return out

    def nearest_base(self, ally: Ship) -> Ship | None:
        """The nearest of our ships with docking bays, other than the ally itself."""
        bases = [s for s in self.obs.own_ships() if s.id != ally.id and s.cls.mass_capacity > 0]
        return min(bases, key=lambda s: math.hypot(s.x - ally.x, s.y - ally.y), default=None)

    def inbound(self) -> list[tuple[str, float]]:
        """Starfleet's ships on their way, with their ETAs, for the map."""
        out = []
        for a in self.world.arrivals:
            if a.tag == "starfleet" and not a.arrived and a.side == self.side:
                eta = a.eta(self.world)
                if eta is not None:
                    names = ", ".join(f"USS {n}" for n in a.names if n) or "Starfleet"
                    out.append((names, eta))
        return out

    def _help_context(self) -> HelpContext:
        return HelpContext(self.world.content, self.world.observe(self.side), self.player)

    help_context = _help_context

    def _faction_of(self, ship: str) -> str | None:
        """An enemy ship's faction, by the id a hail's request carries (for the character voice model)."""
        s = self.world.ships.get(int(ship))
        return s.faction if s is not None else None

    def _target_id(self) -> int | None:
        p = self.player
        return p.target if p is not None else None

    # ------------------------------------------------------------ orders

    def submit(self, cmd: Command) -> str | None:
        """Give an order now. Returns why it was refused, or None."""
        return self.issue(cmd)

    def say(self, text: str) -> None:
        """Anything the captain can type at the console (several orders split by ';')."""
        self.run_console(text)

    def issue(self, cmd: Command) -> str | None:
        reason = self.world.execute(cmd)
        if reason:
            self._notice(reason, "caution", 3.0)
        self._drain_events()
        return reason

    def fire_phasers(self, banks: tuple[int, ...] | None) -> None:
        p = self.player
        self.style_check(why="a fire key")
        if p is not None:
            self.issue(FirePhasers(ship_id=p.id, banks=banks))

    def fire_torpedoes(self, tubes: tuple[int, ...] | None) -> None:
        p = self.player
        self.style_check(why="a fire key")
        if p is not None:
            self.issue(FireTorpedoes(ship_id=p.id, tubes=tubes))

    def launch_probe(self) -> None:
        p = self.player
        if p is None:
            return
        self.style_check(why="a fire key")
        if p.target is None:
            self._notice("Select a target for the probe (or use the console: 'fire probes course 90').", "caution", 3.0)
            return
        self.issue(LaunchProbe(ship_id=p.id, target=p.target))

    def toggle_reserve(self, i: int) -> None:
        p = self.player
        if p is None:
            return
        role = BankRole.FLEX if p.banks[i].role == BankRole.DEFENSE else BankRole.DEFENSE
        self.issue(SetBanks(ship_id=p.id, banks=(i,), role=role))

    def order_ally(self, ally: int, order: str, target: int | None = None, value: float | None = None) -> None:
        p = self.player
        if p is not None:
            self.issue(AllyOrder(ship_id=p.id, ally=ally, order=order, target=target, value=value))

    def ally_report(self, sid: int) -> None:
        ally = self.obs.own(sid)
        if ally is not None:
            self._show(reports.report_lines(self.obs, ally, self.obs.ally_order(sid) or AllyStanding()), None)

    def take_command(self, sid: int) -> None:
        self._transfer(sid)

    def status_report(self) -> None:
        p = self.player
        if p is None:
            return
        self._log(f"{p.name}: warp {p.warp:.1f}, course {p.course:.0f}, crew {p.crew}, hull "
                  f"{max(0.0, p.structure) / p.structure_max * 100:.0f}%, torps {p.torps_remaining}, probes {p.probes_remaining}",
                  "text")

    def _reinforcements(self) -> None:
        if self.tour is None:
            self._log("Starfleet sends reinforcements only on a tour of duty (main menu, Tour of duty).", "caution")
            return
        if self.world.outcome.over:
            self._log("The battle is over.", "dim")
            return
        arrival, msg = self.tour.reinforcement_arrival(self.battle, self.player)
        self._log(msg, "good" if arrival is not None else "caution")

    # ------------------------------------------------------------ time

    def _drain_events(self, stepped: bool = False) -> None:
        events = self.world.take_events()
        self.obs = self.world.observe(self.side)
        self.deeds.extend(ev for ev in events if isinstance(ev, (ObjectiveEnded, ProjectCompleted)))
        self._emit(Ticked(tuple(events), stepped))
        self._crew_react(events)
        if any(isinstance(ev, CommandRejected) and ev.ship_id == self.player_id and ev.issuer == "captain"
               for ev in events):
            self._cue("deny", 0.7)
        self.hits.attacker = self.player_id
        self.hits.ingest(events, self.world.tick)
        names = {c.id: c.label.split(" (")[0] for c in self.obs.contacts().values() if c.identified}
        for line in self.hits.due(self.world.tick, self.world.rules.ticks_per_cycle, names):
            self._log(line, "good")
        for ev in events:
            if isinstance(ev, Message):
                if ev.visible_to is not None and self.side not in ev.visible_to:
                    continue
                if ev.text.startswith("Scanning ") and self.player is not None and "science" in self.player.delegated:
                    continue  # Seven reports what matters herself
                who = f"{ev.speaker}: " if ev.speaker and ev.speaker not in ev.text else ""
                self._log(who + ev.text, EVENT_TONE.get(ev.tone, "text"),
                          channel="bridge" if ev.speaker and ev.speaker != "captain" else "computer")
            elif (isinstance(ev, ScanCompleted) and ev.ship_id == self.player_id
                  and not (self.player is not None and "science" in self.player.delegated)):  # Seven's routine scans stay quiet
                c = self.obs.contact(ev.target_id)
                if c is not None and c.scan is not None:
                    before = self._scans_seen.get(c.id)
                    self._show(reports.scan_lines(self.obs, c, self.player, before), None)
            if isinstance(ev, ScanCompleted) and ev.ship_id == self.player_id:
                c = self.obs.contact(ev.target_id)
                if c is not None and c.scan is not None:
                    self._scans_seen[c.id] = c.scan     # what the next report compares against

    def update(self, dt: float, rate: float | None = None) -> int:
        """Let `dt` seconds of wall-clock time pass at `rate` × (the captain's speed unless given): the
        officers and the language model are heard, running orders go on, and the world steps. Returns the
        number of ticks run."""
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
        self._proposals_tick(dt)
        self._style_tick()
        if self.paused or self.world.outcome.over:
            self.acc = 0.0
            self.obs = self.world.observe(self.side)
            return 0
        tick_len = self.tick_length
        self.acc += dt * (self.speed if rate is None else rate)
        steps = 0
        while self.acc >= tick_len and steps < MAX_STEPS_PER_UPDATE:
            self.world.step()
            self.acc -= tick_len
            steps += 1
            self._drain_events(stepped=True)
            if self.world.outcome.over:
                self._emit(Show("debrief"))
                self._crew_outcome()
                break
        if steps >= MAX_STEPS_PER_UPDATE:
            self.acc = 0.0
        return steps

    def live_chart(self) -> list[str] | None:
        """The chart, when the captain asked for it to stay up (`chart auto`)."""
        return self._chart_lines() if self.chart_auto else None

    # ------------------------------------------------------------ a tour of duty

    def join_tour(self, run: TourRun) -> None:
        """This battle is a stop on a tour: the squadron as its records left it, and Starfleet on call."""
        run.prepare(self.battle)
        self.tour = run
        self.obs = self.world.observe(self.side)

    def finish_tour(self, run: TourRun) -> None:
        """The battle is over (or left): the tour takes its squadron back, with the officers' record."""
        battle = self.battle
        battle.deeds = list(self.deeds)
        best = ""
        if battle.crew is not None and battle.player_ship_id is not None:
            s = standout(battle.crew.officers.values(), battle.player_ship_id, battle.world.command_log, self.deeds)
            best = s.line() if s is not None else ""
        run.finish(battle, best)

    # ------------------------------------------------------------ the end

    def debrief(self, rows: int = 9) -> Debrief:
        """How the battle went, for the end-of-battle screen (everything in it is known to all once it is over)."""
        w = self.world
        score = self.assessment.score(w, self.side)
        me = w.ships.get(self.player_id) if self.player_id is not None else None
        crew = self.battle.crew
        best = None
        if crew is not None and self.player_id is not None:
            best = standout(crew.officers.values(), self.player_id, w.command_log, self.deeds)
        honours = ([self.ribbon_won] if self.ribbon_won else []) + [f"{t} officer" for t in self.trust_news]
        sides = [SideTally(side, w.side_names.get(side, f"Side {side}"), side == self.side, r)
                 for side, r in sorted(self.assessment.sides(w).items())]
        return Debrief(w.outcome.reason or "The engagement is over.", self.assessment.verdict(score), score, w.time,
                       self.side, me, best.line() if best is not None else None, crew is not None, honours, sides,
                       list(w.ships.values())[:rows])

    def in_battle(self) -> bool:
        """Our ship is in a fight: hit lately, or an enemy close by (the red alert)."""
        p = self.player
        return p is not None and p.alive and not self.world.outcome.over and in_battle(self.world, p)

    def close(self) -> None:
        """Leaving the battle: remember how the officers feel, stop any LLM requests."""
        if self.bridge is not None:
            self.bridge.save(self.hidden)
            self.bridge.close()
        if self.translator is not None:
            self.translator.close()
        self.comms.close()
        self.orders.close()


if TYPE_CHECKING:
    def _honours_the_contract(s: BattleSession) -> Session:
        return s        # mypy checks that a BattleSession is a Session


__all__ = ["BattleSession", "CHART", "Commanding", "Listener"]
