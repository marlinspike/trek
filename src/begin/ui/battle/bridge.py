"""The bridge on screen: subtitles, tactical focus, pointing, the command wheel and officers' proposals [E].

Part of `BattleScene` (see `ui/battle_scene.py`), which mixes these methods in; they share its state.

- Readbacks and proposals are the session's (`session/voices.py`); this draws them and takes the Y and N.
- Subtitles: officers' words show low on the map, one voice at a time (`ui/subtitles.py`); the log keeps them all.
- Tactical focus: while the captain types an order the battle eases to a quarter speed (or pauses), the map
  gets an amber edge and the sound steps back; it lapses after a few idle seconds, and nothing is ever slower
  than the speed the captain chose once the order is given.
- Pointing: "fire at him" means the ship under the mouse (`console/pointing.py`).
"""

from __future__ import annotations

import time
from typing import TYPE_CHECKING

import pygame

from ...console.parser import ParseResult
from ...console.readback import readback
from ...console.pointing import points, resolve_pointing
from ...crew.proposals import Proposal
from .. import order_marks, theme
from ..subtitles import STATION_COLOR, station_mark
from ...session.prefs import FOCUS, MODES, PROPOSALS, READBACKS, SUBTITLES
from ..wheel import RING, CommandWheel, Slice, fill
from .state import SceneState
from .. import gfx

if TYPE_CHECKING:
    from ..battle_scene import BattleScene

FOCUS_SPEED = 0.25      # tactical focus eases the battle to this speed (or to a stop, with `hud focus pause`)
FOCUS_EASE = 0.35       # seconds to ease in or out
FOCUS_LAPSE = 8.0       # seconds without a keystroke before focus lets the battle run again
COUNSEL_LAPSE = 20.0    # [E] seconds the counsel panel holds the battle back while you read it


class BridgeMixin(SceneState):
    # ------------------------------------------------------------ tactical focus

    def _focus_target(self: BattleScene) -> float:
        if self.prefs.focus == "off" or self.paused or self.obs.outcome.over or self.overlay is not None:
            return 0.0
        if self.console_focus and self.focus_idle < FOCUS_LAPSE:
            return 1.0
        # [E] reading the officers' counsel steps the battle back too, until a plan is run or the panel closes
        return 1.0 if self.counsel_open and self.focus_idle < COUNSEL_LAPSE else 0.0

    def _focus_update(self: BattleScene, dt: float) -> None:
        if self.console_focus or self.counsel_open:
            self.focus_idle += dt
        want = self._focus_target()
        step = dt / FOCUS_EASE
        self.focus_k = min(want, self.focus_k + step) if want > self.focus_k else max(want, self.focus_k - step)
        self.audio.focus = self.focus_k

    def focus_keystroke(self: BattleScene) -> None:
        self.focus_idle = 0.0

    def effective_speed(self: BattleScene) -> float:
        """The speed the battle runs at this frame: the captain's, eased down while they give an order."""
        k = self.focus_k
        if k <= 0:
            return self.speed
        floor = 0.0 if self.prefs.focus == "pause" else min(self.speed, FOCUS_SPEED)
        return self.speed + (floor - self.speed) * k

    def _draw_focus(self: BattleScene, surf: pygame.Surface) -> None:
        k = self.focus_k
        if k <= 0.01:
            return
        r = self.map_rect
        edge = gfx.Surface(r.size, pygame.SRCALPHA)
        col = theme.CAUTION
        for i, a in enumerate((90, 46, 22)):
            gfx.draw.rect(edge, (*col, int(a * k)), edge.get_rect().inflate(-2 * i * 3, -2 * i * 3), 3, border_radius=6)
        surf.blit(edge, r)

    # ------------------------------------------------------------ pointing

    def pointed_ship(self: BattleScene) -> int | None:
        """The ship under the mouse, if the mouse is on the map and on a ship other than ours."""
        mx, my = self.ui.mouse
        if not self.map_rect.collidepoint(mx, my):
            return None
        sid = self.view.pick(self.obs, self.now, mx, my)
        return sid if sid is not None and sid != self.player_id else None

    def _with_pointing(self: BattleScene, text: str, sid: int | None) -> str:
        if sid is None or not points(text):
            return text
        return resolve_pointing(text, self.ship_name(sid))

    # ------------------------------------------------------------ preview and completion

    def preview(self: BattleScene) -> ParseResult | None:
        """What the line being typed would do, parsed but not run (refreshed as the battle moves)."""
        text = self.console.strip()
        if not (self.prefs.preview and self.console_focus and text) or self.player_id is None:
            return None
        sid = self.pointed_ship()
        key = (text, self.obs.tick // 5, sid)
        if self._preview_key != key:
            self._preview_key = key
            res = self.session.preview(self._with_pointing(text, sid))
            self._preview = res if res is not None and res.error is None and res.commands else None
        return self._preview

    def preview_text(self: BattleScene) -> str | None:
        res = self.preview()
        if res is None:
            return None
        return " ".join(readback(c, self.ship_name) for c in res.commands[:3])

    def complete_console(self: BattleScene) -> None:
        """Tab: finish the word being typed (a command, a ship, an officer, a system, a named order)."""
        names = []
        for s in self.obs.own_ships():
            names.append(s.name)
        for c in self.obs.contacts().values():
            if c.identified:
                names.append(c.label.split(" (")[0])
        officers = [o.name.split()[0] for o in self.session.officers().values()]
        self.console = self.completer.complete(self.console, names, officers, list(self.session.named_orders()))

    def _draw_completions(self: BattleScene, surf: pygame.Surface) -> None:
        opts = self.completer.options
        if not (self.console_focus and opts):
            return
        x = self.console_rect.x + 8
        y = self.console_rect.y - 24
        gfx.draw.rect(surf, theme.BG_PANEL, pygame.Rect(self.console_rect.x, y - 3, self.console_rect.width, 25))
        theme.text(surf, "Tab:", (x, y + 4), theme.TEXT_FAINT, 11)
        x += 34
        for i, o in enumerate(opts):
            w = theme.text_width(o, 12, "mono") + 14
            r = pygame.Rect(x, y, w, 20)
            hot = i == self.completer.index
            gfx.draw.rect(surf, theme.BG_PANEL_HI if hot else theme.BG_INPUT, r, border_radius=3)
            gfx.draw.rect(surf, theme.FRIEND if hot else theme.BORDER, r, 1, border_radius=3)
            theme.text(surf, o, (r.x + 7, r.y + 3), theme.TEXT if hot else theme.TEXT_DIM, 12, "mono")
            x += w + 6

    def _draw_preview(self: BattleScene, surf: pygame.Surface) -> None:
        res = self.preview()
        if res is not None:
            order_marks.draw_preview(surf, self.cam, self.obs, self.player, res.commands)

    # ------------------------------------------------------------ the command wheel

    def open_wheel(self: BattleScene, sid: int, pos: tuple[float, float] | None = None) -> bool:
        """Open the wheel on a ship: an enemy's, an ally's or our own. False if there is none for her."""
        p = self.player
        if p is None or not self.prefs.wheel:
            return False
        kind = "own" if sid == p.id else "ally" if self.obs.own(sid) is not None else "enemy"
        if kind == "enemy" and self.obs.contact(sid) is None:
            return False
        slices = self.wheels.get(kind)
        if not slices:
            return False
        if pos is None:
            pose = self.now.ships.get(sid)
            pos = self.cam.to_screen(pose[0], pose[1]) if pose is not None else self.map_rect.center
        r = self.map_rect
        reach = RING + 24
        cx = int(max(r.x + reach, min(r.right - reach, pos[0])))
        cy = int(max(r.y + reach, min(r.bottom - reach - 30, pos[1])))
        self.wheel = CommandWheel(sid, kind, self.ship_name(sid), slices, (cx, cy))
        self.wheel.move(self.ui.mouse)
        self.audio.play("lock", time.monotonic(), 0.0, 0.35)
        return True

    def _wheel_event(self: BattleScene, ev: pygame.event.Event) -> bool:
        """While the wheel is open it takes the mouse and the keys 1-8 and Esc; True if it used the event."""
        w = self.wheel
        if not isinstance(w, CommandWheel):
            return False
        if ev.type == pygame.MOUSEMOTION:
            w.move(ev.pos)
            return True
        pick: Slice | str | None = "stay"
        if ev.type == pygame.MOUSEBUTTONDOWN:
            if ev.button == 1:
                pick = w.click(ev.pos)
            elif ev.button == 3:
                pick = None
            else:
                return True
        elif ev.type == pygame.MOUSEBUTTONUP:
            return True
        elif ev.type == pygame.KEYDOWN:
            if pygame.K_1 <= ev.key <= pygame.K_8:
                pick = w.key(ev.key - pygame.K_1)
            elif ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and w.chosen() is not None:
                pick = w.chosen()
            elif ev.key == pygame.K_e:
                pick = None
            else:
                self.wheel = None
                return ev.key == pygame.K_ESCAPE      # any other key closes the wheel and does its usual job
        else:
            return False
        if pick == "stay":
            return True
        self.wheel = None
        if isinstance(pick, Slice):
            self._wheel_run(self.wheel_line_for(w, pick))
        return True

    def wheel_line_for(self: BattleScene, w: CommandWheel, s: Slice) -> str:
        p = self.player
        tgt = self.ship_name(p.target) if p is not None and p.target is not None else None
        return fill(s.line, w.name, self.ship_name(p.id) if p is not None else "me", tgt)

    def type_line(self: BattleScene, text: str) -> None:
        """Put words in the console for the captain to finish."""
        self.console = text
        self.console_focus = True
        self.focus_keystroke()
        pygame.key.start_text_input()

    def _wheel_run(self: BattleScene, line: str) -> None:
        if line.startswith("type:"):
            self.type_line(line[len("type:"):])
            return
        self.run_console(line)

    def _draw_wheel(self: BattleScene, surf: pygame.Surface) -> None:
        w = self.wheel
        if not isinstance(w, CommandWheel):
            return
        if w.ship_id != self.player_id and self.obs.own(w.ship_id) is None and self.obs.contact(w.ship_id) is None:
            self.wheel = None           # she's gone
            return
        now = time.monotonic()
        dt = min(0.05, now - self._wheel_t) if self._wheel_t else 0.0
        self._wheel_t = now
        pick = w.chosen()
        line = self.wheel_line_for(w, pick) if pick is not None else None
        if line is not None and line.startswith("type:"):
            line = line[len("type:"):] + "…"
        w.draw(surf, line, dt)

    # ------------------------------------------------------------ officers' proposals

    def _proposal_height(self: BattleScene) -> int:
        return 66 if isinstance(self.proposal, Proposal) and not self.console_focus else 0

    def _draw_proposal(self: BattleScene, surf: pygame.Surface) -> None:
        p = self.proposal
        if not isinstance(p, Proposal):
            return
        col = STATION_COLOR.get(p.station, theme.CREW)
        left = max(0.0, 1.0 - p.age / p.life)
        if self.console_focus:
            # while the captain types: a chip above the console, never in the way of the words
            msg = f"{p.name}: {p.text}"
            keys = "Ctrl+Y make it so"
            w = min(self.console_rect.width - 20, theme.text_width(msg, 12) + theme.text_width(keys, 11) + 60)
            r = pygame.Rect(self.console_rect.right - w - 4, self.console_rect.y - 52, w, 24)
            gfx.draw.rect(surf, theme.BG_PANEL_HI, r, border_radius=4)
            gfx.draw.rect(surf, theme.CAUTION if p.urgent else col, r, 1, border_radius=4)
            station_mark(surf, p.station, (r.x + 12, r.centery), 5, col)
            theme.text(surf, msg, (r.x + 24, r.y + 4), theme.TEXT, 12)
            theme.text(surf, keys, (r.right - 10, r.y + 5), theme.CAUTION, 11, weight="semibold", anchor="topright")
            return
        r = self.map_rect
        cb = self.counsel_box if self.counsel_open else None
        if cb is not None and r.right - cb.right > 300:        # the open part of the map, beside the counsel
            r = pygame.Rect(cb.right + 8, r.y, r.right - cb.right - 8, r.height)
        text_w = theme.text_width(p.text, 15) + theme.text_width(p.name.upper(), 11, weight="semibold")
        w = min(r.width - 16, max(420, min(int(r.width * 0.86), text_w + 76)))
        box = pygame.Rect(0, 0, w, 56)
        box.midbottom = (r.centerx, r.bottom - 18)
        theme.shadow(surf, box, 6)
        glass = gfx.Surface(box.size, pygame.SRCALPHA)
        glass.fill((*theme.BG_PANEL_HI, 232))
        surf.blit(glass, box)
        gfx.draw.rect(surf, theme.CAUTION if p.urgent else col, box, 1, border_radius=6)
        station_mark(surf, p.station, (box.x + 18, box.y + 18), 6, col)
        theme.text(surf, p.name.upper(), (box.x + 32, box.y + 11), col, 11, weight="semibold")
        tx = box.x + 32 + theme.text_width(p.name.upper(), 11, weight="semibold") + 12
        theme.text(surf, theme.fit(p.text, 15, box.right - tx - 10), (tx, box.y + 8), theme.TEXT, 15)
        choices = [("Y", "make it so"), ("N", "belay")]
        x = box.x + 32
        for k, label in choices:
            kr = pygame.Rect(x, box.y + 31, 20, 18)
            gfx.draw.rect(surf, theme.BG_INPUT, kr, border_radius=3)
            gfx.draw.rect(surf, theme.BORDER_HI, kr, 1, border_radius=3)
            theme.text(surf, k, kr.center, theme.TEXT, 11, "mono", anchor="center")
            theme.text(surf, label, (kr.right + 6, kr.y + 2), theme.TEXT_DIM, 12)
            self.ui.add(pygame.Rect(kr.x, kr.y, 28 + theme.text_width(label, 12), 18),
                        self.accept_proposal if k == "Y" else self.belay_proposal, f"{label} ({k})")
            x = kr.right + 16 + theme.text_width(label, 12)
        theme.text(surf, f"→ {p.line}", (box.right - 14, box.y + 33), theme.TEXT_FAINT, 11, "mono", anchor="topright")
        bar = pygame.Rect(box.x + 6, box.bottom - 3, int((box.width - 12) * left), 2)
        gfx.draw.rect(surf, theme.dim(col, 0.8), bar)

    # ------------------------------------------------------------ the Bridge setting

    def bridge_setting(self: BattleScene, val: object) -> None:
        """`hud bridge full|quiet|classic`, `hud wheel on|off`, `hud focus slow|pause|off`... (see `session/prefs.py`)."""
        p = self.prefs
        if isinstance(val, tuple):
            key, v = val
            if key == "bridge" and v in MODES:
                p.apply_mode(str(v))
                if p.subtitles == "off":
                    self.subs.clear()
            elif key in ("wheel", "map_orders", "preview") and v in ("on", "off"):
                setattr(p, key, v == "on")
                if key == "wheel" and v == "off":
                    self.wheel = None
            elif key == "focus" and v in FOCUS:
                p.focus = str(v)
            elif key == "proposals" and v in PROPOSALS:
                p.proposals = str(v)
                if v == "off":
                    self.proposal = None
            elif key == "subtitles" and v in SUBTITLES:
                p.subtitles = str(v)
                if v == "off":
                    self.subs.clear()
            elif key == "readbacks" and v in READBACKS:
                p.readbacks = str(v)
        self.bridge_store.clear()
        self.bridge_store.update(p.to_dict())
        self._log(p.describe() + " 'hud bridge full|quiet|classic' sets them all.", theme.TEXT_DIM)


__all__ = ["BridgeMixin", "FOCUS_LAPSE", "FOCUS_SPEED"]
