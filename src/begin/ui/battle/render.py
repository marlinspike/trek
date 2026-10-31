"""Drawing the battle screen: map, panels, printouts, banners and the overlays (help, damage, scan, debrief).

Part of `BattleScene` (see `ui/battle_scene.py`), which mixes these methods in; they share its state."""

from __future__ import annotations

import math
import time
from functools import partial
from typing import TYPE_CHECKING

import pygame

from ...console import reports
from ...crew.review import standout
from ...sim.ship import Kind
from ...sim.systems.repair import in_battle, under_repair
from .. import comms_view, officer_view, theme
from ..hud import diagram_legend, hull_diagram
from .common import CONTROLS, RED_ALERT_FLOOR, RED_ALERT_PERIOD, RED_ALERT_PULSE, SPEEDS, ratio
from .state import SceneState

if TYPE_CHECKING:
    from ..battle_scene import BattleScene


class RenderMixin(SceneState):
    def draw(self: BattleScene, surf: pygame.Surface) -> None:
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

    def _red_alert(self: BattleScene) -> float:
        """How red the panel borders are right now: a slow pulse while the ship is in a fight, else 0."""
        p = self.player
        if p is None or not p.alive or self.world.outcome.over or not in_battle(self.world, p):
            return 0.0
        return RED_ALERT_FLOOR + RED_ALERT_PULSE * (0.5 + 0.5 * math.sin(time.monotonic() * math.tau / RED_ALERT_PERIOD))

    def _map_overlay_text(self: BattleScene, surf: pygame.Surface) -> None:
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

    def _draw_conn_banner(self: BattleScene, surf: pygame.Surface, top: int) -> None:
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

    def _draw_evasive_banner(self: BattleScene, surf: pygame.Surface, top: int) -> None:
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

    def _draw_printout(self: BattleScene, surf: pygame.Surface) -> None:
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

    def _bottom(self: BattleScene, surf: pygame.Surface) -> None:
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

    def _column(self: BattleScene, surf: pygame.Surface) -> None:
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

    def _modal(self: BattleScene, surf: pygame.Surface, w: int, h: int, title: str, accent: theme.Color = theme.FRIEND) -> pygame.Rect:
        shade = pygame.Surface(surf.get_size(), pygame.SRCALPHA)
        shade.fill((2, 5, 12, 170))
        surf.blit(shade, (0, 0))
        r = pygame.Rect(0, 0, w, h)
        r.center = (surf.get_width() // 2, surf.get_height() // 2)
        theme.panel(surf, r, title, accent)
        return r

    def _draw_overlay(self: BattleScene, surf: pygame.Surface) -> None:
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

    def _damage_view(self: BattleScene, surf: pygame.Surface) -> None:
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

    def _scan_view(self: BattleScene, surf: pygame.Surface) -> None:
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

    def _debrief(self: BattleScene, surf: pygame.Surface) -> None:
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
                     ("phasers", ratio(st.phaser_hits, st.phaser_shots), theme.TEXT),
                     ("torpedoes", ratio(st.torpedo_hits, st.torpedoes_fired), theme.TEXT),
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


__all__ = ["RenderMixin"]
