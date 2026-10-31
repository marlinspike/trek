"""Keyboard, mouse and the console's input line.

Part of `BattleScene` (see `ui/battle_scene.py`), which mixes these methods in; they share its state."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING

import pygame

from ...core.angles import bearing, norm360
from ...sim.commands import Pursue, Scan, SelectTarget, SetHelm, SetPointDefense, SetShields
from .. import theme
from ..hud import PD_CYCLE, SUB_GROUPS
from .common import FKEYS, SPEEDS
from .state import SceneState

if TYPE_CHECKING:
    from ..battle_scene import BattleScene


class InputMixin(SceneState):
    def handle(self: BattleScene, ev: pygame.event.Event) -> None:
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

    def _mouse_down(self: BattleScene, ev: pygame.event.Event) -> None:
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

    def _left_click(self: BattleScene, pos: tuple[int, int]) -> None:
        p = self.player
        sid = self.view.pick(self.obs, self.now, *pos)
        if p is None:
            return
        if sid is not None and sid in self.obs.contacts():
            self.issue(SelectTarget(ship_id=p.id, target=sid, subsystem=p.target_subsystem))
        elif sid is not None and sid != p.id and self.obs.own(sid) is not None:
            self.select_ally(sid)

    def _right_click(self: BattleScene, pos: tuple[int, int]) -> None:
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

    def _key(self: BattleScene, ev: pygame.event.Event) -> None:
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

    def _cycle_target(self: BattleScene, step: int) -> None:
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

    def _console_key(self: BattleScene, ev: pygame.event.Event) -> None:
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

    def _submit_console(self: BattleScene) -> None:
        text = self.console.strip()
        self.console = ""
        if not text:
            self.console_focus = False
            return
        self.history.append(text)
        self.hist_i = len(self.history)
        self.run_console(text)

    def _key_binding(self: BattleScene, val: tuple[str, str] | None) -> None:
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

    def run_key(self: BattleScene, name: str) -> bool:
        text = self.keys.get(name)
        if not text:
            return False
        self.run_console(text)
        return True


__all__ = ["InputMixin"]
