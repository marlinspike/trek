"""Keyboard, mouse and the console's input line.

Part of `BattleScene` (see `ui/battle_scene.py`), which mixes these methods in; they share its state."""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, Callable

import pygame

from ...core.angles import bearing, norm360
from ...sim.commands import Pursue, Scan, SelectTarget, SetHelm, SetPointDefense, SetShields
from ...sim.ship import Ship
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
        if k in FKEYS and self.run_key(FKEYS[k]):
            return
        if ev.mod & pygame.KMOD_CTRL and pygame.K_a <= k <= pygame.K_z and self.run_key("^" + chr(k)):
            return
        if k == pygame.K_ESCAPE:
            self._escape()
            return
        if self.overlay == "debrief":
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.on_exit()
            return
        if self.overlay and self.overlay.startswith("help") and k not in (pygame.K_F1, pygame.K_h):
            self.overlay = None
        shift = bool(ev.mod & pygame.KMOD_SHIFT)
        scene_action = SCENE_KEYS.get(k)
        if scene_action is not None:
            scene_action(self, k, shift)
            return
        p = self.player
        ship_action = SHIP_KEYS.get(k)
        if p is not None and ship_action is not None:
            ship_action(self, p, shift)

    def _escape(self: BattleScene) -> None:
        """Esc closes the printout, then the overlay; with nothing open it brings up the battle menu."""
        if self.overlay is None and self.printout is not None:
            self.printout = None
            self.chart_auto = False
        elif self.overlay in (None, "help_brief"):
            self.overlay = "menu"
        elif self.overlay == "debrief":
            self.on_exit()
        else:
            self.overlay = None

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



# ------------------------------------------------------------ single-key controls (see CONTROLS for the list shown to the player)

def _open_console(s: BattleScene, k: int, shift: bool) -> None:
    s.console_focus = True
    pygame.key.start_text_input()


def _pan(s: BattleScene, k: int, shift: bool) -> None:
    step = 80
    dx = {pygame.K_LEFT: step, pygame.K_RIGHT: -step}.get(k, 0)
    dy = {pygame.K_UP: step, pygame.K_DOWN: -step}.get(k, 0)
    s.cam.pan_pixels(dx, dy)


def _mute(s: BattleScene, k: int, shift: bool) -> None:
    muted = s.audio.toggle_mute()
    s.toast = ("Sound off (M)" if muted else "Sound on (M)", theme.TEXT_DIM, 1.5)


def _pause(s: BattleScene, k: int, shift: bool) -> None:
    s.paused = not s.paused


def _faster(s: BattleScene, k: int, shift: bool) -> None:
    s.speed = SPEEDS[min(len(SPEEDS) - 1, SPEEDS.index(s.speed) + 1)]


def _slower(s: BattleScene, k: int, shift: bool) -> None:
    s.speed = SPEEDS[max(0, SPEEDS.index(s.speed) - 1)]


def _zoom_in(s: BattleScene, k: int, shift: bool) -> None:
    s.cam.zoom_at(1.25, *s.map_rect.center)


def _zoom_out(s: BattleScene, k: int, shift: bool) -> None:
    s.cam.zoom_at(0.8, *s.map_rect.center)


def _arcs(s: BattleScene, k: int, shift: bool) -> None:
    s.view.show_arcs = not s.view.show_arcs


def _follow(s: BattleScene, k: int, shift: bool) -> None:
    s.cam.follow = s.player_id


def _omniscient(s: BattleScene, k: int, shift: bool) -> None:
    s.omniscient = not s.omniscient


SceneKey = Callable[["BattleScene", int, bool], None]

# keys that work with or without a ship under command
SCENE_KEYS: dict[int, SceneKey] = {
    pygame.K_SPACE: _pause,
    pygame.K_RIGHTBRACKET: _faster, pygame.K_PERIOD: _faster,
    pygame.K_LEFTBRACKET: _slower, pygame.K_COMMA: _slower,
    pygame.K_RETURN: _open_console, pygame.K_KP_ENTER: _open_console, pygame.K_SLASH: _open_console, pygame.K_BACKQUOTE: _open_console,
    pygame.K_F1: lambda s, k, shift: s.open_manual("controls"),
    pygame.K_h: lambda s, k, shift: s.open_manual(),
    pygame.K_i: lambda s, k, shift: s.toggle_overlay("damage"),
    pygame.K_q: _arcs,
    pygame.K_c: _follow,
    pygame.K_EQUALS: _zoom_in, pygame.K_PLUS: _zoom_in, pygame.K_KP_PLUS: _zoom_in,
    pygame.K_MINUS: _zoom_out, pygame.K_KP_MINUS: _zoom_out,
    pygame.K_LEFT: _pan, pygame.K_RIGHT: _pan, pygame.K_UP: _pan, pygame.K_DOWN: _pan,
    pygame.K_m: _mute,
    pygame.K_F9: _omniscient,
}


def _warp(s: BattleScene, p: Ship, step: int) -> None:
    warp = min(p.cls.max_warp, math.floor(p.desired_warp + 1)) if step > 0 else max(0.0, math.ceil(p.desired_warp - 1))
    s.issue(SetHelm(ship_id=p.id, warp=warp))


def _turn(s: BattleScene, p: Ship, sign: int, shift: bool) -> None:
    s.issue(SetHelm(ship_id=p.id, course=norm360(p.desired_course + sign * (5 if shift else 15))))


def _scan(s: BattleScene, p: Ship, shift: bool) -> None:
    if p.target is not None:
        s.issue(Scan(ship_id=p.id, target=p.target))


def _cycle_aim(s: BattleScene, p: Ship, shift: bool) -> None:
    if p.target is not None:
        i = SUB_GROUPS.index(p.target_subsystem) if p.target_subsystem in SUB_GROUPS else 0
        s.issue(SelectTarget(ship_id=p.id, target=p.target, subsystem=SUB_GROUPS[(i + 1) % len(SUB_GROUPS)]))


def _cycle_pd(s: BattleScene, p: Ship, shift: bool) -> None:
    nxt = PD_CYCLE[(PD_CYCLE.index(p.pd_doctrine) + 1) % len(PD_CYCLE)]
    s.issue(SetPointDefense(ship_id=p.id, doctrine=nxt))
    s.toast = (f"Point defense: {nxt.value}", theme.GOOD, 2.0)


ShipKey = Callable[["BattleScene", Ship, bool], None]

# keys that act on the ship under command
SHIP_KEYS: dict[int, ShipKey] = {
    pygame.K_w: lambda s, p, shift: _warp(s, p, +1),
    pygame.K_s: lambda s, p, shift: _warp(s, p, -1),
    pygame.K_a: lambda s, p, shift: _turn(s, p, -1, shift),
    pygame.K_d: lambda s, p, shift: _turn(s, p, +1, shift),
    pygame.K_f: lambda s, p, shift: s.fire_phasers(None),
    pygame.K_t: lambda s, p, shift: s.fire_torpedoes(None),
    pygame.K_p: lambda s, p, shift: s.launch_probe(),
    pygame.K_x: _scan,
    pygame.K_TAB: lambda s, p, shift: s._cycle_target(-1 if shift else 1),
    pygame.K_r: _cycle_aim,
    pygame.K_g: lambda s, p, shift: s.issue(SetShields(ship_id=p.id, up=not any(sh.up for sh in p.shields))),
    pygame.K_v: _cycle_pd,
}


__all__ = ["InputMixin"]
