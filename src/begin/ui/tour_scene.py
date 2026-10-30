"""Tours of duty, between the battles [E]: choosing a tour, the squadron, the Ready Room, the log, the end.

Pages, all drawn over the tour's patrol chart:

- tours: the tours you can fly (shipped and your own from config/tours/), and the one in hand;
- squadron: pick your escorts within the tour's fleet budget, each ship lit and slowly turning;
- ready: the Ready Room. The officer's briefing for the next stop, the choice it asks of you,
  your squadron as Geordi expects it to arrive, a call to Starfleet for reinforcements, and launch;
- log: the captain's log, one page per stop. Your officers and captains have written their parts;
  the captain's entry is drafted for you and is yours to rewrite (click it);
- end: the tour's rating.

The scene saves after every change (`config/tours/<tour id>.json`) and keeps the log as
Markdown beside it. With a language model configured, the officers rewrite their entries in
their own voices in the background.
"""

from __future__ import annotations

from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Callable

import pygame

from ..content.schema import ContentDB
from ..paths import config_dir
from ..tour.log import OFFICER_ORDER, OFFICER_TITLES, read_markdown_edits, voice_request, write_markdown
from ..tour.model import TourDef, check_tour, load_tours
from ..tour.run import TourRun
from ..tour.state import ShipRecord, TourState, fleet_cost
from . import theme
from .settings import Settings
from .tour_art import GLIDE_SECONDS, draw_chart, glass, portrait, ship_art, wrap
from .widgets import UI

if TYPE_CHECKING:
    from ..llm.service import LLMService

TURN_RATE = 7.0           # degrees a second the squadron's ships turn on their stands
MAX_ESCORTS = 5
OUTCOME_WORDS = {"victory": "Victory", "withdrew": "Withdrew", "lost": "Flagship lost", "base lost": "Starbase lost"}


def tours_dir() -> Path:
    return config_dir() / "tours"


class TourScene:
    def __init__(self, content: ContentDB, settings: Settings, launch: Callable[[TourRun], object],
                 leave: Callable[[], None]) -> None:
        self.content = content
        self.settings = settings
        self.launch = launch
        self.leave = leave
        self.ui = UI()
        self.size = (1600, 900)
        self.page = "tours"
        self.t = 0.0
        self.glide = 1.0
        self.tours: list[TourDef] = []
        self.problems: list[str] = []
        self.tour_i = 0
        self.run: TourRun | None = None
        self.escorts: list[str] = []
        self.note = ""                          # the last word from Starfleet or the crew, shown in the Ready Room
        self.log_i = 0
        self.log_scroll = 0
        self.editing = False
        self.edit_buf = ""
        self.confirm_new = False
        self.voices: LLMService | None = None   # the officers' language model, once they have written
        self._asked: dict[int, tuple[int, str]] = {}
        self.refresh()

    # ------------------------------------------------------------ tours and saving

    def refresh(self) -> None:
        tours, problems = load_tours(tours_dir())
        classes = set(self.content.classes)
        self.tours = [t for t in tours if not check_tour(t, classes)]
        self.problems = problems + [p for t in tours for p in check_tour(t, classes)]
        self.tour_i = min(self.tour_i, max(0, len(self.tours) - 1))

    def open(self) -> None:
        self.refresh()
        self.page = "tours"
        self.confirm_new = False

    @property
    def tour(self) -> TourDef | None:
        return self.tours[self.tour_i] if self.tours else None

    def saved(self, tour: TourDef) -> TourState | None:
        return TourState.load(tours_dir(), tour.id)

    def save(self) -> None:
        if self.run is None:
            return
        try:
            self.run.state.save(tours_dir())
            write_markdown(self.run, tours_dir())
        except OSError as e:
            self.note = f"Couldn't save the tour: {e}"

    def resume(self, tour: TourDef) -> None:
        state = self.saved(tour)
        if state is None:
            return
        read_markdown_edits(state, tours_dir())      # your edits to the Markdown log, between sessions
        self.run = TourRun(tour, state, self.content)
        self.save()
        self.note = ""
        self.glide = 1.0
        self.page = "end" if state.over else "ready"

    def new_tour(self) -> None:
        self.escorts = []
        self.page = "squadron"
        self.confirm_new = False

    def commission(self) -> None:
        tour = self.tour
        if tour is None:
            return
        seed = (pygame.time.get_ticks() * 7919 + len(self.escorts)) % 100000 + 1
        self.run = TourRun.new(tour, self.content, list(self.escorts), seed=seed)
        self.save()
        self.note = ""
        self.glide = 0.0
        self.page = "ready"

    def after_battle(self, run: TourRun) -> None:
        """Back from a stop's battle: save, open the new log page, and have the officers write it up."""
        self.run = run
        self.save()
        self.log_i = len(run.state.log) - 1
        self.log_scroll = 0
        self.glide = 0.0
        self.page = "log"
        self.note = ""
        self._ask_voices(self.log_i)

    # ------------------------------------------------------------ the officers' voices

    def _ask_voices(self, idx: int) -> None:
        """With a language model configured, each writer puts their entry in their own voice, in the background."""
        run = self.run
        if run is None or not (0 <= idx < len(run.state.log)):
            return
        if self.voices is None:
            try:
                from ..llm.providers import config_from_settings, make_provider
                from ..llm.service import LLMService

                cfg = config_from_settings(self.settings.llm)
                if cfg is None:
                    return
                self.voices = LLMService(make_provider(cfg), workers=2)
            except Exception:  # noqa: BLE001 - no model, no voices: the drafted entries stand
                return
        from ..crew.characters import load_officers

        try:
            profiles = load_officers(traits_file=config_dir() / "officers.toml")
        except (OSError, ValueError):
            profiles = {}
        entry = run.state.log[idx]
        writers = [o for o in OFFICER_ORDER if o in entry.stations] + list(entry.captains) + ["captain"]
        for who in writers:
            if who in entry.voiced or (who == "captain" and entry.edited):
                continue
            prof = profiles.get(who)
            persona = (prof.persona + (" Traits: " + ", ".join(prof.traits) + "." if prof.traits else "")) if prof else ""
            style = prof.response_style if prof else ""
            system, user = voice_request(entry, who, persona, style)
            rid = self.voices.submit(f"log:{who}", system, [{"role": "user", "content": user}])
            self._asked[rid] = (idx, who)

    def _poll_voices(self) -> None:
        if self.voices is None or self.run is None or not self._asked:
            return
        changed = False
        for reply in self.voices.poll():
            idx, who = self._asked.pop(reply.request_id, (-1, ""))
            if idx < 0 or not reply.text or idx >= len(self.run.state.log):
                continue
            entry = self.run.state.log[idx]
            text = " ".join(reply.text.strip().strip('"').split())
            if not text:
                continue
            if who == "captain":
                if entry.edited or (self.editing and idx == self.log_i):
                    continue
                entry.captain = text
            elif who in entry.stations:
                entry.stations[who] = text
            elif who in entry.captains:
                entry.captains[who] = text
            entry.voiced.append(who)
            changed = True
        if changed:
            self.save()

    def writing(self) -> bool:
        return bool(self._asked)

    # ------------------------------------------------------------ frame

    def layout(self, size: tuple[int, int]) -> None:
        self.size = size

    def update(self, dt: float) -> None:
        self.t += dt
        self.glide = min(1.0, self.glide + dt / GLIDE_SECONDS)
        self.ui.mouse = pygame.mouse.get_pos()
        self._poll_voices()

    def handle(self, ev: pygame.event.Event) -> None:
        if ev.type == pygame.VIDEORESIZE:
            self.layout((ev.w, ev.h))
        elif self.editing and ev.type in (pygame.KEYDOWN, pygame.TEXTINPUT):
            self._edit_key(ev)
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
            h = self.ui.hit(ev.pos)
            if h is not None:
                if ev.button == 3 and h.right is not None:
                    h.right()
                elif ev.button == 1:
                    h.action()
        elif ev.type == pygame.MOUSEWHEEL and self.page == "log":
            self.log_scroll = max(0, self.log_scroll - ev.y * 40)
        elif ev.type == pygame.KEYDOWN:
            self._key(ev)

    def _key(self, ev: pygame.event.Event) -> None:
        k = ev.key
        if k == pygame.K_ESCAPE:
            if self.page == "log" and self.run is not None and not self.run.over:
                self.page = "ready"
            elif self.page in ("squadron",):
                self.page = "tours"
            else:
                self.close()
        elif self.page == "tours" and k in (pygame.K_UP, pygame.K_DOWN) and self.tours:
            self.tour_i = (self.tour_i + (1 if k == pygame.K_DOWN else -1)) % len(self.tours)
            self.confirm_new = False
        elif self.page == "log" and k in (pygame.K_LEFT, pygame.K_RIGHT) and self.run is not None:
            self._turn_page(-1 if k == pygame.K_LEFT else 1)

    def close(self) -> None:
        self.save()
        self.editing = False
        self.leave()

    # ------------------------------------------------------------ editing the captain's entry

    def _start_edit(self) -> None:
        if self.run is None or not self.run.state.log:
            return
        self.editing = True
        self.edit_buf = self.run.state.log[self.log_i].captain
        pygame.key.start_text_input()

    def _finish_edit(self, keep: bool) -> None:
        if keep and self.run is not None:
            e = self.run.state.log[self.log_i]
            text = self.edit_buf.strip()
            if text and text != e.captain.strip():
                e.captain = text
                e.edited = True
                self.save()
        self.editing = False

    def _edit_key(self, ev: pygame.event.Event) -> None:
        if ev.type == pygame.TEXTINPUT:
            self.edit_buf += ev.text
            return
        k = ev.key
        if k == pygame.K_ESCAPE:
            self._finish_edit(False)
        elif k in (pygame.K_RETURN, pygame.K_KP_ENTER):
            if ev.mod & pygame.KMOD_SHIFT:
                self.edit_buf += "\n"
            else:
                self._finish_edit(True)
        elif k == pygame.K_BACKSPACE:
            if ev.mod & (pygame.KMOD_CTRL | pygame.KMOD_ALT | pygame.KMOD_META):
                self.edit_buf = self.edit_buf.rstrip()
                cut = max(self.edit_buf.rfind(" "), self.edit_buf.rfind("\n"))
                self.edit_buf = self.edit_buf[:cut + 1] if cut >= 0 else ""
            else:
                self.edit_buf = self.edit_buf[:-1]

    # ------------------------------------------------------------ the Ready Room's actions

    def _launch(self) -> None:
        run = self.run
        if run is None or run.over or run.needs_choice():
            return
        self.save()
        self.launch(run)

    def _reinforce(self) -> None:
        if self.run is not None:
            self.note = self.run.request_from_ready_room()
            self.save()

    def _choose(self, i: int) -> None:
        if self.run is not None:
            self.run.choose(i)
            self.save()

    def _toggle_reserve(self, rec: ShipRecord) -> None:
        if rec.role == "flagship" or rec.lost:
            return
        rec.reserve = not rec.reserve
        self.note = (f"USS {rec.name} will stay at {self.run.tour.starbase if self.run else 'the starbase'} for a refit."
                     if rec.reserve else f"USS {rec.name} rejoins the squadron.")
        self.save()

    def _turn_page(self, d: int) -> None:
        if self.run is None or not self.run.state.log:
            return
        self.log_i = max(0, min(len(self.run.state.log) - 1, self.log_i + d))
        self.log_scroll = 0
        self.editing = False

    def _open_log(self) -> None:
        if self.run is not None and self.run.state.log:
            self.log_i = len(self.run.state.log) - 1
            self.log_scroll = 0
            self.page = "log"

    # ------------------------------------------------------------ drawing

    def draw(self, surf: pygame.Surface) -> None:
        self.ui.begin_frame()
        surf.fill(theme.BG)
        w, h = surf.get_size()
        tour = self.run.tour if self.run is not None and self.page != "tours" else self.tour
        if tour is not None:
            st = self.run.state if self.run is not None and self.page != "tours" else None
            outcomes = [r.outcome for r in st.results] if st is not None else []
            current = st.stop if st is not None else 0
            glide = self.glide if st is not None else 0.0
            dim = {"tours": 0.25, "squadron": 0.45, "log": 0.5, "end": 0.45}.get(self.page, 0.0)
            draw_chart(surf, surf.get_rect(), tour, [], outcomes, current, glide, self.t, dim)
        if self.page == "tours":
            self._tours(surf)
        elif self.page == "squadron":
            self._squadron(surf)
        elif self.page == "ready":
            self._ready(surf)
        elif self.page == "log":
            self._log(surf)
        elif self.page == "end":
            self._end(surf)
        self.ui.draw_tooltip(surf)

    def _heading(self, surf: pygame.Surface, title: str, sub: str) -> None:
        theme.text(surf, title.upper(), (40, 28), theme.CAUTION, 26, "display", weight="semibold")
        if sub:
            theme.text(surf, sub, (42, 66), theme.TEXT_DIM, 14)

    # ---- tours

    def _tours(self, surf: pygame.Surface) -> None:
        w, h = surf.get_size()
        self._heading(surf, "Tour of duty", "Linked battles: your squadron carries its damage, crews, torpedoes and prizes "
                                            "from one stop to the next.")
        x, y = 40, 110
        for i, t in enumerate(self.tours):
            st = self.saved(t)
            mark = "  ·  under way" if st is not None and not st.over else "  ·  completed" if st is not None and st.over == "won" else ""
            self.ui.button(surf, pygame.Rect(x, y, 340, 40), t.title + mark, partial(self._pick, i),
                           t.source if t.source != "shipped" else "", active=i == self.tour_i, size=14, face="display")
            y += 48
        self.ui.button(surf, pygame.Rect(x, y + 14, 160, 36), "Back", self.close, "Esc", size=13)
        if self.problems:
            yy = h - 24 - 18 * len(self.problems[:4])
            for p in self.problems[:4]:
                theme.text(surf, p, (x, yy), theme.CAUTION, 12)
                yy += 18
        tour = self.tour
        if tour is None:
            theme.text(surf, "No tours found.", (420, 120), theme.TEXT_DIM, 15)
            return
        r = pygame.Rect(420, 110, min(720, w - 460), 0)
        lines = wrap(tour.description, 15, r.width - 40)
        stops = [f"{i + 1}. {s.title}  ({s.system})" for i, s in enumerate(tour.stops)]
        r.height = 150 + 24 * len(lines) + 22 * len(stops)
        y = glass(surf, r, tour.sector or "Tour of duty", theme.CAUTION)
        theme.text(surf, tour.title, (r.x + 20, y), theme.TEXT, 22, "display", weight="semibold")
        y += 38
        for ln in lines:
            theme.text(surf, ln, (r.x + 20, y), theme.TEXT, 15)
            y += 24
        y += 8
        for s in stops:
            theme.text(surf, s, (r.x + 24, y), theme.TEXT_DIM, 13)
            y += 22
        cls = self.content.classes[tour.flagship]
        theme.text(surf, f"Flagship: a {cls.name.lower()}  ·  fleet budget {tour.budget}  ·  "
                         f"{tour.reinforcement_calls} calls to Starfleet", (r.x + 20, r.bottom - 34), theme.TEXT_DIM, 13)
        st = self.saved(tour)
        by = r.bottom + 16
        if st is not None and not st.over:
            stop = tour.stops[min(st.stop, len(tour.stops) - 1)]
            self.ui.button(surf, pygame.Rect(r.x, by, 300, 42), f"Continue: stop {st.stop + 1}, {stop.title}",
                           lambda: self.resume(tour), "Back to the Ready Room", size=14, accent=theme.GOOD, face="ui")
            label = "Click again to abandon it" if self.confirm_new else "Start a new tour"
            self.ui.button(surf, pygame.Rect(r.x + 316, by, 240, 42), label, self._new_confirmed,
                           "Abandons the tour under way", size=14, accent=theme.ALERT if self.confirm_new else theme.FRIEND)
        else:
            self.ui.button(surf, pygame.Rect(r.x, by, 260, 42), "Assemble the squadron", self.new_tour, size=14,
                           accent=theme.GOOD)
            if st is not None:
                self.ui.button(surf, pygame.Rect(r.x + 276, by, 240, 42), "Read the last log", lambda: self._read_old(tour),
                               size=14)

    def _pick(self, i: int) -> None:
        self.tour_i = i
        self.confirm_new = False

    def _new_confirmed(self) -> None:
        if self.confirm_new:
            self.new_tour()
        else:
            self.confirm_new = True

    def _read_old(self, tour: TourDef) -> None:
        self.resume(tour)
        self._open_log()

    # ---- squadron

    def _classes(self, tour: TourDef) -> list[str]:
        cl = [c for c in self.content.classes_of(tour.faction, include_bases=False) if c.banks > 0]
        return [c.id for c in cl]

    def _squadron(self, surf: pygame.Surface) -> None:
        tour = self.tour
        if tour is None:
            self.page = "tours"
            return
        w, h = surf.get_size()
        left = TourRun.budget_left(tour, self.content, self.escorts)
        self._heading(surf, "Assemble your squadron", f"{tour.title}: choose the ships that sail with the flagship.")
        # the budget
        br = pygame.Rect(40, 100, 360, 70)
        y = glass(surf, br, "Fleet budget", theme.CAUTION)
        theme.bar(surf, pygame.Rect(br.x + 14, y + 4, br.width - 120, 12), left / max(1, tour.budget),
                  theme.GOOD if left > 0 else theme.CAUTION)
        theme.text(surf, f"{left} of {tour.budget}", (br.right - 14, y), theme.TEXT, 14, "mono", anchor="topright")
        # the yard: classes to add
        yr = pygame.Rect(40, 186, 360, 70 + 48 * len(self._classes(tour)))
        y = glass(surf, yr, "Starfleet yard")
        for cid in self._classes(tour):
            cls = self.content.classes[cid]
            cost = fleet_cost(cid, self.content)
            ok = cost <= left and len(self.escorts) < MAX_ESCORTS
            tip = (f"{cls.crew} crew · {cls.banks} phaser banks · {cls.tubes} tubes · warp {cls.max_warp:g}" if ok else
                   "Over budget" if cost > left else f"At most {MAX_ESCORTS} escorts")
            self.ui.button(surf, pygame.Rect(yr.x + 14, y, yr.width - 28, 40), f"{cls.name}  ·  {cost} points",
                           partial(self.escorts.append, cid), tip, enabled=ok, size=14, face="ui")
            y += 48
        # the squadron: the flagship and the escorts, lit and turning
        sx = 430
        sr = pygame.Rect(sx, 100, w - sx - 40, h - 200)
        glass(surf, sr, "The squadron", theme.FRIEND, alpha=150)
        ships = [(tour.flagship, "Enterprise (flagship)", None)] + [
            (cid, self.content.classes[cid].name, i) for i, cid in enumerate(self.escorts)]
        cols = 3
        cw = (sr.width - 40) // cols
        chh = min(260, (sr.height - 50) // 2)
        for n, (cid, label, idx) in enumerate(ships):
            cx = sr.x + 20 + (n % cols) * cw
            cy = sr.y + 40 + (n // cols) * chh
            cls = self.content.classes[cid]
            length = int(min(cw, chh) * (0.55 if cid == tour.flagship else 0.45) * (0.7 + 0.3 * min(1.0, cls.mass / 190)))
            img = ship_art(cls, max(30, length), (self.t * TURN_RATE + n * 50) % 360)
            surf.blit(img, img.get_rect(center=(cx + cw // 2, cy + chh // 2 - 14)))
            theme.text(surf, label, (cx + cw // 2, cy + chh - 34), theme.TEXT, 14, "display", anchor="center")
            theme.text(surf, f"{cls.crew} crew · {cls.banks} banks · {cls.tubes} tubes", (cx + cw // 2, cy + chh - 14),
                       theme.TEXT_DIM, 12, anchor="center")
            if idx is not None:
                self.ui.button(surf, pygame.Rect(cx + cw - 44, cy + 6, 30, 26), "x", partial(self.escorts.pop, idx),
                               "Send her back", size=13, accent=theme.ALERT)
        self.ui.button(surf, pygame.Rect(w - 300, h - 80, 260, 44), "Begin the tour", self.commission, size=15,
                       accent=theme.GOOD)
        self.ui.button(surf, pygame.Rect(w - 460, h - 80, 140, 44), "Back", lambda: setattr(self, "page", "tours"), size=13)

    # ---- the Ready Room

    def _ready(self, surf: pygame.Surface) -> None:
        run = self.run
        if run is None:
            self.page = "tours"
            return
        if run.over:
            self.page = "end"
            return
        stop = run.stop
        assert stop is not None
        w, h = surf.get_size()
        st = run.state
        self._heading(surf, "Ready Room", f"{run.tour.title}  ·  stop {st.stop + 1} of {len(run.tour.stops)}  ·  "
                                          f"stardate {st.stardate()}")
        # the briefing, from the officer who gives it
        bw = min(520, int(w * 0.34))
        lines = wrap(stop.briefing, 14, bw - 150)
        lessons = [ln for lesson in run.lesson_lines() for ln in wrap(lesson, 13, bw - 40)]
        enemies = self._enemy_words(run)
        br = pygame.Rect(40, 100, bw, 130 + 21 * max(len(lines), 5) + 19 * len(lessons) + (26 if enemies else 0))
        y = glass(surf, br, f"Briefing: {stop.title}", theme.CAUTION)
        pic = portrait(stop.officer, 104)
        surf.blit(pic, (br.x + 14, y + 4))
        name = OFFICER_TITLES.get(stop.officer, stop.officer).split(",")[0]
        for k, part in enumerate(wrap(name, 11, 104)):
            theme.text(surf, part, (br.x + 66, y + 114 + 15 * k), theme.CREW, 11, anchor="midtop")
        ty = y
        for ln in lines:
            theme.text(surf, ln, (br.x + 132, ty), theme.TEXT, 14)
            ty += 21
        ty = max(ty, y + 150) + 6
        if enemies:
            theme.text(surf, enemies, (br.x + 14, ty), theme.HOSTILE, 13)
            ty += 26
        for ln in lessons:
            theme.text(surf, ln, (br.x + 14, ty), theme.CAUTION, 13)
            ty += 19
        # the choice the stop asks of you
        y = br.bottom + 14
        if stop.choices:
            cr = pygame.Rect(40, y, bw, 46 + sum(30 + 18 * len(wrap(c.consequence, 12, bw - 40)) for c in stop.choices))
            yy = glass(surf, cr, "Your decision", theme.ALERT if run.needs_choice() else theme.GOOD)
            for i, c in enumerate(stop.choices):
                cons = wrap(c.consequence, 12, bw - 40)
                box = pygame.Rect(cr.x + 10, yy - 4, cr.width - 20, 26 + 18 * len(cons))
                chosen = st.choice == i
                if chosen:
                    pygame.draw.rect(surf, theme.mix(theme.BG_PANEL, theme.GOOD, 0.22), box, border_radius=4)
                self.ui.add(box, partial(self._choose, i), "Choose this")
                pygame.draw.rect(surf, theme.GOOD if chosen else theme.BORDER_HI if box.collidepoint(self.ui.mouse) else theme.BORDER,
                                 box, 1, border_radius=4)
                theme.text(surf, c.label, (box.x + 10, box.y + 5), theme.TEXT, 14, weight="medium")
                for k, ln in enumerate(cons):
                    theme.text(surf, ln, (box.x + 10, box.y + 26 + 18 * k), theme.TEXT_DIM, 12)
                yy = box.bottom + 8
            y = cr.bottom + 14
        if self.note:
            for k, ln in enumerate(wrap(self.note, 13, bw)):
                theme.text(surf, ln, (42, y + 18 * k), theme.GOOD, 13)
        # the squadron, as Geordi expects it to arrive
        self._squadron_panel(surf, run, pygame.Rect(w - min(560, int(w * 0.36)) - 40, 100, min(560, int(w * 0.36)), h - 200))
        # the buttons along the bottom
        by = h - 76
        launch_tip = "Make your decision first" if run.needs_choice() else f"{run.transit_cycles():.0f} cycles to {stop.system}"
        self.ui.button(surf, pygame.Rect(w - 340, by, 300, 46), f"Set course for {stop.system}", self._launch, launch_tip,
                       enabled=not run.needs_choice(), size=15, accent=theme.GOOD, face="ui")
        calls = st.calls_left
        self.ui.button(surf, pygame.Rect(w - 640, by, 280, 46),
                       f"Request reinforcements ({calls})", self._reinforce,
                       f"Starfleet's ships take {stop.eta:.0f} cycles to reach {stop.system}. You can also call from the "
                       f"battle: 'request reinforcements'.", enabled=calls > 0, size=14, face="ui")
        self.ui.button(surf, pygame.Rect(40, by, 200, 46), "Captain's log", self._open_log,
                       "Every stop's page, and your entries", enabled=bool(st.log), size=14)
        self.ui.button(surf, pygame.Rect(256, by, 200, 46), "Save and leave", self.close, "Esc", size=14)

    def _enemy_words(self, run: TourRun) -> str:
        stop = run.stop
        if stop is None:
            return ""
        names: dict[str, int] = {}
        for cid in stop.enemy_ships(run.flags()):
            cls = self.content.classes[cid]
            n = f"{self.content.factions[cls.faction].name} {cls.name.lower()}"
            names[n] = names.get(n, 0) + 1
        parts = [f"{k} ×{v}" if v > 1 else k for k, v in names.items()]
        more = " and more expected" if stop.active_waves(run.flags()) else ""
        return "Sensors: " + ", ".join(parts) + more if parts else ""

    def _squadron_panel(self, surf: pygame.Surface, run: TourRun, r: pygame.Rect) -> None:
        y = glass(surf, r, "Squadron, as Geordi expects it to arrive", theme.FRIEND)
        projected = {p.name: p for p in run.projected()}
        recs = [x for x in run.state.squadron if not x.lost] + [x for x in run.state.squadron if x.lost]
        row_h = max(64, min(96, (r.height - 90) // max(1, len(recs))))
        ch = run.chosen()
        for n, rec in enumerate(recs):
            cls = self.content.classes[rec.class_id]
            p = projected.get(rec.name, rec)
            box = pygame.Rect(r.x + 10, y, r.width - 20, row_h - 8)
            if box.bottom > r.bottom - 50:
                theme.text(surf, f"and {len(recs) - n} more", (r.x + 14, y), theme.TEXT_DIM, 12)
                break
            pygame.draw.rect(surf, theme.mix(theme.BG_PANEL, theme.BG_PANEL_HI, 0.6), box, border_radius=4)
            art = ship_art(cls, int(row_h * 0.8), (self.t * TURN_RATE + n * 70) % 360, rec.hull, seed=n + 1)
            if rec.lost:
                art = art.copy()
                art.fill((90, 90, 90, 255), special_flags=pygame.BLEND_RGBA_MULT)
            surf.blit(art, art.get_rect(center=(box.x + row_h // 2 + 4, box.centery)))
            tx = box.x + row_h + 12
            role = {"flagship": "flagship", "prize": "prize", "reinforcement": "from Starfleet"}.get(rec.role, "")
            title = f"USS {rec.name}" if cls.faction == run.tour.faction else rec.name
            col = theme.TEXT_FAINT if rec.lost else theme.FRIEND
            theme.text(surf, title, (tx, box.y + 6), col, 15, "display", weight="medium")
            sub = f"{cls.name}{'  ·  ' + role if role else ''}{'  ·  ' + rec.captain if rec.captain else ''}"
            theme.text(surf, sub, (tx, box.y + 26), theme.TEXT_DIM, 12)
            if rec.lost:
                theme.text(surf, "Lost" + (f" at {self._stop_title(run, rec.lost_at)}" if rec.lost_at else ""),
                           (tx, box.y + 44), theme.ALERT, 12)
                continue
            bw = 120
            theme.bar(surf, pygame.Rect(tx, box.y + 48, bw, 8), p.hull, theme.health_color(p.hull))
            if p.hull > rec.hull + 0.005:
                theme.bar(surf, pygame.Rect(tx, box.y + 48, int(bw * rec.hull), 8), 1.0, theme.health_color(rec.hull))
            theme.text(surf, f"hull {rec.hull:.0%}" + (f" → {p.hull:.0%}" if abs(p.hull - rec.hull) > 0.005 else ""),
                       (tx + bw + 8, box.y + 44), theme.TEXT, 12, "mono")
            dmg = len(p.damage)
            stats = f"crew {p.crew_now(self.content)}/{cls.crew}  ·  torps {p.torps_now(self.content)}/{cls.torps_carried}"
            stats += f"  ·  {dmg} system{'s' if dmg != 1 else ''} damaged" if dmg else "  ·  systems sound"
            if box.height > 70:
                theme.text(surf, stats, (tx, box.y + 62), theme.TEXT_DIM, 12)
            if rec.role != "flagship":
                label = "Recall" if rec.reserve else "Keep at base"
                self.ui.button(surf, pygame.Rect(box.right - 116, box.y + 8, 106, 26), label,
                               partial(self._toggle_reserve, rec),
                               "She misses the next fight and is refitted at the starbase" if not rec.reserve else
                               "She sails with the squadron again", active=rec.reserve, size=11, face="ui")
            y += row_h
        note = ("A full refit at the starbase: every ship made good." if ch is not None and ch.refit else
                f"{run.transit_cycles():.0f} cycles of travel: crews patch hulls to "
                f"{run.rules.hull_field_limit:.0%} at most, and a supply ship tops up the magazines.")
        for k, ln in enumerate(wrap("Geordi: " + note, 12, r.width - 28)):
            theme.text(surf, ln, (r.x + 14, r.bottom - 40 + 16 * k), theme.CREW, 12)

    @staticmethod
    def _stop_title(run: TourRun, stop_id: str) -> str:
        return next((s.system for s in run.tour.stops if s.id == stop_id), stop_id)

    # ---- the log

    def _log(self, surf: pygame.Surface) -> None:
        run = self.run
        if run is None or not run.state.log:
            self.page = "ready"
            return
        w, h = surf.get_size()
        self.log_i = max(0, min(self.log_i, len(run.state.log) - 1))
        e = run.state.log[self.log_i]
        r = pygame.Rect(0, 0, min(980, w - 80), h - 120)
        r.midtop = (w // 2, 30)
        y0 = glass(surf, r, "Captain's log", theme.CAUTION, alpha=225)
        theme.text(surf, f"{e.title}", (r.x + 24, y0), theme.TEXT, 22, "display", weight="semibold")
        outcome = OUTCOME_WORDS.get(e.outcome, e.outcome)
        col = theme.GOOD if e.outcome == "victory" else theme.CAUTION if e.outcome == "withdrew" else theme.ALERT
        theme.text(surf, f"Stardate {e.stardate}  ·  {outcome}", (r.right - 24, y0 + 6), col, 14, "mono", anchor="topright")
        if self.writing():
            dots = "." * (1 + int(self.t * 2) % 3)
            theme.text(surf, f"Your officers are writing their entries{dots}", (r.x + 24, y0 + 34), theme.CREW, 12)
        body = pygame.Rect(r.x + 16, y0 + 56, r.width - 32, r.bottom - y0 - 120)
        clip = surf.get_clip()
        surf.set_clip(body)
        y = body.y - self.log_scroll
        tw = body.width - 40
        # the captain's entry: yours
        theme.text(surf, "THE CAPTAIN", (body.x + 8, y), theme.TEXT_DIM, 11, "display", weight="medium")
        tag = "edited by you" if e.edited else "drafted for you: click to rewrite it"
        theme.text(surf, tag, (body.x + 130, y + 1), theme.TEXT_FAINT, 11)
        y += 20
        text = self.edit_buf if self.editing else e.captain
        lines = wrap(text, 15, tw - 20)
        box = pygame.Rect(body.x + 4, y - 4, body.width - 8, 24 * len(lines) + 16)
        hover = box.collidepoint(self.ui.mouse) and body.collidepoint(self.ui.mouse)
        pygame.draw.rect(surf, theme.BG_INPUT if self.editing else theme.mix(theme.BG_PANEL, theme.BG_PANEL_HI, 0.5), box,
                         border_radius=4)
        pygame.draw.rect(surf, theme.CAUTION if self.editing else theme.BORDER_HI if hover else theme.BORDER, box, 1,
                         border_radius=4)
        for k, ln in enumerate(lines):
            theme.text(surf, ln, (box.x + 12, box.y + 8 + 24 * k), theme.TEXT, 15)
        if self.editing and int(self.t * 2) % 2 == 0:
            last = lines[-1] if lines else ""
            cx = box.x + 12 + theme.text_width(last, 15)
            cy = box.y + 8 + 24 * (len(lines) - 1)
            pygame.draw.line(surf, theme.CAUTION, (cx + 1, cy + 2), (cx + 1, cy + 19), 2)
        if not self.editing and body.collidepoint(self.ui.mouse):
            self.ui.add(box.clip(body), self._start_edit, "Click to rewrite your entry")
        y = box.bottom + 18
        # the officers' entries
        for oid in OFFICER_ORDER:
            if oid not in e.stations:
                continue
            pic = portrait(oid, 44)
            surf.blit(pic, (body.x + 8, y))
            theme.text(surf, OFFICER_TITLES.get(oid, oid).upper(), (body.x + 64, y), theme.CREW, 11, "display",
                       weight="medium")
            ls = wrap(e.stations[oid], 14, tw - 60)
            for k, ln in enumerate(ls):
                theme.text(surf, ln, (body.x + 64, y + 18 + 20 * k), theme.TEXT, 14)
            y += max(54, 22 + 20 * len(ls)) + 10
        # each captain's report
        if e.captains:
            theme.text(surf, "THE SQUADRON'S CAPTAINS", (body.x + 8, y + 4), theme.TEXT_DIM, 11, "display", weight="medium")
            y += 26
            for name, rep in e.captains.items():
                theme.text(surf, f"USS {name}", (body.x + 8, y), theme.FRIEND, 13, weight="medium")
                ls = wrap(rep, 13, tw - 160)
                for k, ln in enumerate(ls):
                    theme.text(surf, ln, (body.x + 150, y + 19 * k), theme.TEXT_DIM, 13)
                y += 19 * len(ls) + 10
        content_h = y + self.log_scroll - body.y
        surf.set_clip(clip)
        self.log_scroll = max(0, min(self.log_scroll, content_h - body.height + 20))
        if content_h > body.height:
            frac = body.height / content_h
            bar = pygame.Rect(body.right - 4, body.y + int(body.height * self.log_scroll / content_h), 3,
                              max(20, int(body.height * frac)))
            pygame.draw.rect(surf, theme.BORDER_HI, bar, border_radius=2)
        # footer
        fy = r.bottom - 52
        if self.editing:
            theme.text(surf, "Enter keeps your entry, Shift+Enter starts a new paragraph, Esc puts it back.",
                       (r.x + 24, fy + 12), theme.CAUTION, 12)
        else:
            path = tours_dir() / f"{run.tour.id}-log.md"
            theme.text(surf, f"Also kept as {self._short(path)}: edit it there too.", (r.x + 24, fy + 12),
                       theme.TEXT_FAINT, 12)
        n = len(run.state.log)
        self.ui.button(surf, pygame.Rect(r.right - 430, fy, 44, 34), "<", lambda: self._turn_page(-1), "Earlier page",
                       enabled=self.log_i > 0, size=14)
        theme.text(surf, f"{self.log_i + 1} / {n}", (r.right - 356, fy + 17), theme.TEXT_DIM, 13, "mono", anchor="center")
        self.ui.button(surf, pygame.Rect(r.right - 326, fy, 44, 34), ">", lambda: self._turn_page(1), "Later page",
                       enabled=self.log_i < n - 1, size=14)
        nxt = "The tour's end" if run.over else "To the Ready Room"
        self.ui.button(surf, pygame.Rect(r.right - 264, fy, 240, 34), nxt,
                       lambda: setattr(self, "page", "end" if run.over else "ready"), size=14, accent=theme.GOOD)

    @staticmethod
    def _short(path: Path) -> str:
        """The log's path as the player knows it: config/tours/... in the project, else in full."""
        return f"config/tours/{path.name}" if path.parent.parent.name == "config" else str(path)

    # ---- the end

    def _end(self, surf: pygame.Surface) -> None:
        run = self.run
        if run is None:
            self.page = "tours"
            return
        w, h = surf.get_size()
        grade, lines = run.rating()
        won = run.state.over == "won"
        r = pygame.Rect(0, 0, min(860, w - 80), 0)
        crew = [x for x in run.state.squadron]
        r.height = 260 + 26 * len(lines) + 24 * len(crew)
        r.center = (w // 2, h // 2)
        y = glass(surf, r, f"{run.tour.title}: the end of the tour", theme.CAUTION if won else theme.ALERT, alpha=230)
        last = run.state.results[-1] if run.state.results else None
        head = ("Tour complete" if won else
                "The flagship was lost" if last is not None and last.outcome == "lost" else
                f"{run.tour.starbase} has fallen" if last is not None and last.outcome == "base lost" else "Tour failed")
        theme.text(surf, head.upper(), (r.centerx, y + 8), theme.TEXT, 28, "display", weight="semibold", anchor="midtop")
        theme.text(surf, grade, (r.centerx, y + 52), theme.CAUTION if won else theme.ALERT, 17, weight="medium",
                   anchor="midtop")
        y += 96
        for ln in lines:
            theme.text(surf, ln, (r.x + 40, y), theme.TEXT, 15)
            y += 26
        y += 10
        for rec in crew:
            cls = self.content.classes[rec.class_id]
            state = (f"lost at {self._stop_title(run, rec.lost_at)}" if rec.lost else
                     f"hull {rec.hull:.0%}, crew {rec.crew_now(self.content)}/{cls.crew}, {rec.kills} kills")
            theme.text(surf, f"{rec.name}", (r.x + 40, y), theme.TEXT_FAINT if rec.lost else theme.FRIEND, 13, weight="medium")
            theme.text(surf, f"{cls.name}  ·  {state}", (r.x + 220, y), theme.TEXT_DIM, 13)
            y += 24
        by = r.bottom - 56
        self.ui.button(surf, pygame.Rect(r.x + 24, by, 200, 38), "Read the log", self._open_log, enabled=bool(run.state.log),
                       size=14)
        self.ui.button(surf, pygame.Rect(r.right - 224, by, 200, 38), "Main menu", self.close, size=14, accent=theme.GOOD)
        self.ui.button(surf, pygame.Rect(r.right - 440, by, 200, 38), "Another tour", self.open, size=14)


__all__ = ["TourScene", "tours_dir"]
