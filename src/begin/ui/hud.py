"""HUD panels for the battle screen.

Each panel is a small class with `draw(surf, rect, hud)` and a preferred
height. Panels read the player's `Observation` and issue commands through
`hud.issue(...)`, exactly like the console, the AI and the officers.
To add a panel, subclass `Panel` and append it to `BattleScene.panels`.
"""

from __future__ import annotations

import math
from functools import partial
from typing import TYPE_CHECKING, Callable, ClassVar

import pygame

from ..core.angles import bearing, norm360
from ..sim.commands import (
    ConfigureAutoload, ControlProbe, DelegateStation, Dock, Scan, SelectTarget, SetFireMode, SetPhaserSpread,
    SetPointDefense, SetShields, Tractor, Transport,
)
from ..sim.factory import SHIELD_FACINGS
from ..sim.ship import BankRole, FireMode, Kind, PDDoctrine, Ship
from ..sim.systems.phasers import bank_bears, bank_ready
from . import theme
from .hulls import draw_hull, transform

if TYPE_CHECKING:
    from .battle_scene import BattleScene
    from ..sim.observation import ContactView

MODE_LETTER = {FireMode.MANUAL: "M", FireMode.ASSISTED: "A", FireMode.AUTOMATIC: "★"}
MODE_CYCLE = [FireMode.MANUAL, FireMode.ASSISTED, FireMode.AUTOMATIC]
PD_CYCLE = [PDDoctrine.OFF, PDDoctrine.CONSERVATIVE, PDDoctrine.BALANCED, PDDoctrine.AGGRESSIVE]
SUB_GROUPS = [None, "propulsion", "weapons", "shields", "power", "sensors"]


class Panel:
    title: ClassVar[str] = ""
    weight: ClassVar[float] = 1.0   # share of leftover column height
    min_height: ClassVar[int] = 120

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, hud: BattleScene) -> None:
        y = theme.panel(surf, rect, self.title)
        self.body(surf, rect, y, hud)

    def body(self, surf: pygame.Surface, rect: pygame.Rect, y: int, hud: BattleScene) -> None:
        """The panel's contents below its header; `TabbedPanel` calls this for the open tab."""
        raise NotImplementedError

    def tab_label(self, hud: BattleScene) -> str:
        return self.title


def _kv(surf: pygame.Surface, x: int, y: int, k: str, v: str, vcol: theme.Color = theme.TEXT, w: int = 92) -> None:
    theme.text(surf, k, (x, y), theme.TEXT_DIM, 12)
    theme.text(surf, v, (x + w, y), vcol, 12, "mono")


def hull_diagram(surf: pygame.Surface, ship: Ship, box: pygame.Rect, show_shields: bool = True,
                 highlight: set[Kind] | None = None) -> None:
    """Top-down damage-assessment diagram: hull, subsystems coloured by health, shield arcs."""
    k = min(box.width, box.height) / 125.0
    cx, cy = box.centerx, box.centery
    draw_hull(surf, ship.cls.hull, cx, cy, 0.0, k, theme.FRIEND_DIM, fill_alpha=0.18)
    for sub in ship.subsystems():
        (px, py), = transform([sub.pos], cx, cy, 0.0, k)
        col = theme.health_color(sub.health, sub.destroyed)
        r = 3 if sub.kind not in (Kind.REACTOR, Kind.DRIVE) else 4
        if highlight and sub.kind in highlight:
            pygame.draw.circle(surf, theme.CAUTION, (int(px), int(py)), r + 3, 1)
        if sub.kind == Kind.SHIELD:
            continue
        pygame.draw.circle(surf, col, (int(px), int(py)), r)
    if show_shields:
        rad = 58 * k
        for i, sh in enumerate(ship.shields):
            facing = SHIELD_FACINGS[i % 6]
            a0 = math.radians(90 - (facing + 27))
            a1 = math.radians(90 - (facing - 27))
            rect = pygame.Rect(0, 0, rad * 2, rad * 2)
            rect.center = (cx, cy)
            if sh.destroyed:
                col = (70, 74, 86)
            elif not sh.up or sh.effective <= 0.5:
                col = theme.dim(theme.ALERT, 0.6)
            else:
                col = theme.mix(theme.ALERT, theme.SHIELD, sh.effective / 100.0)
            pygame.draw.arc(surf, col, rect, a0, a1, 4 if sh.reinforced else 3)
            if sh.flash > 0:
                pygame.draw.arc(surf, (255, 255, 255), rect.inflate(6, 6), a0, a1, 1)
            mid = math.radians(facing)
            lx, ly = cx + math.sin(mid) * (rad + 11), cy - math.cos(mid) * (rad + 11)
            theme.text(surf, f"{sh.effective:.0f}" if not sh.destroyed else "×", (lx, ly), theme.dim(col, 1.0), 10, "mono",
                       anchor="center")


# ------------------------------------------------------------------ own ship

class OwnShipPanel(Panel):
    title = "Own ship"
    min_height = 262
    weight = 0.0

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, hud: BattleScene) -> None:
        ship = hud.player
        y = theme.panel(surf, rect, self.title)
        if ship is None:
            theme.text(surf, "No ship under command.", (rect.x + 12, y), theme.TEXT_DIM, 13)
            return
        status_col = theme.GOOD if ship.alive else theme.ALERT
        theme.text(surf, ship.name, (rect.x + 12, y - 2), theme.FRIEND, 17, weight="semibold")
        sub = f"{ship.cls.name} · {hud.world.content.factions[ship.faction].name}"
        if not ship.alive:
            sub += f" · {ship.status.value.upper()}"
        theme.text(surf, sub, (rect.x + 12, y + 20), status_col if not ship.alive else theme.TEXT_DIM, 12)
        box = pygame.Rect(rect.x + 8, y + 40, 168, rect.bottom - y - 48)
        hull_diagram(surf, ship, box)
        hud.ui.add(box, lambda: hud.toggle_overlay("damage"), "Damage assessment (I)")
        x = rect.x + 186
        yy = y + 42
        cw = ship.max_attainable_warp
        _kv(surf, x, yy, "Warp", f"{ship.warp:4.1f} → {ship.desired_warp:.1f}  (max {cw:.1f})")
        yy += 18
        _kv(surf, x, yy, "Course", f"{ship.course:5.1f} → {ship.desired_course:.0f}")
        yy += 18
        crew_col = theme.health_color(ship.crew / max(1, ship.cls.crew))
        _kv(surf, x, yy, "Crew", f"{ship.crew} / {ship.cls.crew}", crew_col)
        yy += 18
        hf = max(0.0, ship.structure) / ship.structure_max
        _kv(surf, x, yy, "Hull", f"{hf * 100:5.1f}%", theme.health_color(hf))
        yy += 22
        p = ship.power
        theme.text(surf, "Power", (x, yy), theme.TEXT_DIM, 12)
        theme.text(surf, f"+{p.generation:.0f}  −{p.consumption:.0f}/cyc", (x + 92, yy), theme.TEXT, 12, "mono")
        yy += 17
        cap = max(1.0, p.capacity)
        theme.text(surf, "Battery", (x, yy), theme.TEXT_DIM, 12)
        theme.bar(surf, pygame.Rect(x + 92, yy + 4, rect.right - x - 104, 8), p.stored / cap,
                  theme.GOOD if p.stored / cap > 0.35 else theme.CAUTION)
        yy += 17
        theme.text(surf, "Drives", (x, yy), theme.TEXT_DIM, 12)
        n = max(1, len(ship.drives))
        w = (rect.right - x - 104 - 4 * (n - 1)) // n
        for i, d in enumerate(ship.drives):
            frac = (d.temp - 12.0) / 28.0
            col = theme.GOOD if frac < 0.5 else theme.CAUTION if frac < 0.8 else theme.ALERT
            if d.destroyed:
                col = (70, 74, 86)
            theme.bar(surf, pygame.Rect(x + 92 + i * (w + 4), yy + 4, w, 8), frac, col)
        yy += 19
        _kv(surf, x, yy, "Magazine", f"{ship.torps_remaining} torp · {ship.probes_remaining} probe")
        yy += 18
        rp = ship.repair_priority.value if ship.repair_priority else "all systems"
        _kv(surf, x, yy, "Repairs", rp)
        yy += 22
        bw = (rect.right - x - 12) // 2 - 3
        anyup = any(s.up for s in ship.shields)
        hud.ui.button(surf, pygame.Rect(x, yy, bw, 22), "Lower shields" if anyup else "Raise shields",
                      lambda: hud.issue(SetShields(ship_id=ship.id, up=not anyup)), "Toggle all shields (G)")
        pd = ship.pd_doctrine
        nxt = PD_CYCLE[(PD_CYCLE.index(pd) + 1) % len(PD_CYCLE)]
        hud.ui.button(surf, pygame.Rect(x + bw + 6, yy, bw, 22), f"PD: {pd.value}",
                      lambda: hud.issue(SetPointDefense(ship_id=ship.id, doctrine=nxt)),
                      "Point defense doctrine (V cycles). Reserve banks with right-click on a bank.",
                      active=pd != PDDoctrine.OFF, accent=theme.GOOD)


# ------------------------------------------------------------------ target

class TargetPanel(Panel):
    title = "Target"
    min_height = 210
    weight = 0.0

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, hud: BattleScene) -> None:
        y = theme.panel(surf, rect, self.title, theme.HOSTILE)
        ship = hud.player
        obs = hud.obs
        tid = ship.target if ship else None
        c = obs.contact(tid) if tid is not None else None
        if ship is None or c is None:
            self._contact_list(surf, rect, y, hud)
            return
        col = theme.HOSTILE if c.identified else theme.UNKNOWN
        theme.text(surf, c.label if c.identified else f"Unidentified contact #{c.id}", (rect.x + 12, y - 2), col, 16,
                   weight="semibold")
        d = c.distance_to(ship.x, ship.y)
        brg = bearing(c.x - ship.x, c.y - ship.y)
        rel = norm360(brg - ship.course)
        line = f"{d:,.0f} units · bearing {brg:03.0f} · mark {rel:03.0f}"
        if c.cls is not None:
            line = f"{c.cls.name} · " + line
        theme.text(surf, line, (rect.x + 12, y + 20), theme.TEXT_DIM, 12)
        if not c.visible:
            theme.text(surf, f"Contact lost {c.age:.0f} cycles ago — position estimated", (rect.x + 12, y + 36),
                       theme.CAUTION, 12)
        # their shield facing us
        if c.cls is not None:
            aspect = norm360(bearing(ship.x - c.x, ship.y - c.y) - c.course)
            k = min(range(6), key=lambda i: abs(((aspect - SHIELD_FACINGS[i]) + 180) % 360 - 180))
            theme.text(surf, f"Their shield {k + 1} faces us", (rect.x + 12, y + 52), theme.TEXT_DIM, 12)
        # in-arc summary
        bears = sum(1 for b in ship.banks if bank_bears(ship, b, brg))
        ready = sum(1 for b in ship.banks if bank_bears(ship, b, brg) and bank_ready(ship, b))
        in_range = d <= ship.cls.banks_range
        rng_col = theme.GOOD if in_range else theme.TEXT_DIM
        theme.text(surf, f"Banks bearing {bears}/{len(ship.banks)} · charged {ready} · "
                         f"{'in range' if in_range else 'out of range'}",
                   (rect.right - 12, y + 52), rng_col, 12, anchor="topright")
        # subsystem targeting
        yy = y + 74
        theme.text(surf, "Aim at", (rect.x + 12, yy + 4), theme.TEXT_DIM, 12)
        x = rect.x + 64
        cur = ship.target_subsystem
        for g in SUB_GROUPS:
            label = g or "hull"
            w = theme.text_width(label, 11) + 14
            hud.ui.button(surf, pygame.Rect(x, yy, w, 22), label,
                          partial(hud.issue, SelectTarget(ship_id=ship.id, target=c.id, subsystem=g)),
                          "Precision fire at a subsystem group (R cycles)", active=cur == g, accent=theme.CAUTION, size=11)
            x += w + 4
        # scan
        yy += 30
        pend = hud.world.pending_scan(ship.id)
        label = "Scanning…" if pend else "Scan (X)"
        hud.ui.button(surf, pygame.Rect(rect.x + 12, yy, 92, 22), label,
                      lambda: hud.issue(Scan(ship_id=ship.id, target=c.id)), "Detailed sensor scan", enabled=pend is None)
        self._close_actions(surf, rect, yy + 50, hud, ship, c.id, d)
        self._switch_row(surf, rect, hud, c.id, y - 4)
        sc = c.scan
        if sc is None:
            theme.text(surf, "No scan data.", (rect.x + 114, yy + 4), theme.TEXT_FAINT, 12)
            return
        age = (obs.tick - sc.tick) * obs.rules.dt
        x = rect.x + 114
        for i, v in enumerate(sc.shields):
            r = pygame.Rect(x + i * 30, yy + 2, 26, 8)
            theme.bar(surf, r, max(0.0, v) / 100.0, theme.SHIELD if v > 0 else theme.ALERT)
            theme.text(surf, str(i + 1), (r.centerx, r.bottom + 2), theme.TEXT_FAINT, 9, anchor="midtop")
        theme.text(surf, f"crew ~{sc.crew}  hull {sc.structure_frac * 100:.0f}%  banks {sc.charged_banks}  "
                         f"tubes {sc.loaded_tubes}  ({age:.0f}s old, {sc.confidence * 100:.0f}% conf.)",
                   (rect.x + 12, yy + 28), theme.TEXT_DIM, 11)
        hud.ui.add(pygame.Rect(rect.x, yy - 2, rect.width, 44), lambda: hud.toggle_overlay("scan"), "Open scan view")

    @staticmethod
    def _sensed(hud: BattleScene) -> list[ContactView]:
        """Every contact the sensors can see now, nearest first."""
        p = hud.player
        if p is None:
            return []
        return sorted((c for c in hud.obs.contacts().values() if c.visible), key=lambda c: c.distance_to(p.x, p.y))

    def _contact_list(self, surf: pygame.Surface, rect: pygame.Rect, y: int, hud: BattleScene) -> None:
        """No target yet: list everything on sensors, each row selects it."""
        p = hud.player
        cs = self._sensed(hud)
        if p is None or not cs:
            theme.text(surf, "No target, and nothing on sensors.", (rect.x + 12, y), theme.TEXT_DIM, 13)
            return
        theme.text(surf, "No target. Choose one (or click it on the map, or press Tab):", (rect.x + 12, y),
                   theme.TEXT_DIM, 12)
        yy = y + 20
        for c in cs:
            if yy + 24 > rect.bottom - 6:
                theme.text(surf, f"… and {len(cs) - cs.index(c)} more (Tab cycles through all)", (rect.x + 12, yy),
                           theme.TEXT_FAINT, 11)
                break
            name = c.label if c.identified else f"Unidentified #{c.id}"
            d = c.distance_to(p.x, p.y)
            brg = bearing(c.x - p.x, c.y - p.y)
            what = c.cls.name if c.cls is not None else "unknown class"
            text = f"{name}  ·  {what}  ·  {d:,.0f}  ·  bearing {brg:03.0f}" + ("  ·  hazy" if c.haze > 0 else "")
            hud.ui.button(surf, pygame.Rect(rect.x + 12, yy, rect.width - 24, 22), text,
                          partial(hud.issue, SelectTarget(ship_id=p.id, target=c.id, subsystem=p.target_subsystem)),
                          f"Target {name}", accent=theme.HOSTILE if c.identified else theme.UNKNOWN, size=12)
            yy += 26

    def _switch_row(self, surf: pygame.Surface, rect: pygame.Rect, hud: BattleScene, current: int, yy: int) -> None:
        """With a target: the other contacts on sensors as small buttons, top right beside the target's name."""
        p = hud.player
        others = [c for c in self._sensed(hud) if c.id != current]
        if p is None or not others:
            return
        x = rect.right - 12
        for c in others:
            name = c.label if c.identified else f"#{c.id}"
            w = theme.text_width(name, 11) + 14
            if x - w < rect.centerx:
                break
            x -= w
            hud.ui.button(surf, pygame.Rect(x, yy, w, 20), name,
                          partial(hud.issue, SelectTarget(ship_id=p.id, target=c.id, subsystem=p.target_subsystem)),
                          f"Switch target to {name} ({c.distance_to(p.x, p.y):,.0f} units)",
                          accent=theme.HOSTILE if c.identified else theme.UNKNOWN, size=11)
            x -= 4

    @staticmethod
    def _close_actions(surf: pygame.Surface, rect: pygame.Rect, yy: int, hud: BattleScene, ship: Ship, tid: int,
                       d: float) -> None:
        """Tractor and boarding (Begin 2.0): buttons plus how close we are to each range."""
        rules = hud.world.rules
        x = rect.x + 12
        has_tractor = ship.cls.has_tractor and ship.tractor is not None
        holding = ship.tractor_target == tid
        tractor_ok = has_tractor and ship.tractor is not None and ship.tractor.intact
        hud.ui.button(surf, pygame.Rect(x, yy, 92, 22), "Release" if holding else "Tractor",
                      (lambda: hud.issue(Tractor(ship_id=ship.id, target=None if holding else tid))),
                      f"Tractor beam: holds and drags the target (range {rules.tractor_range:,.0f}). Console: 'tractor'"
                      if has_tractor else "This ship has no tractor beam.",
                      active=holding, enabled=tractor_ok or holding, accent=theme.SHIELD)
        n = ship.boarding_party()
        transporters = any(not t.destroyed for t in ship.transporters)
        hud.ui.button(surf, pygame.Rect(x + 98, yy, 92, 22), f"Board ×{n}",
                      (lambda: hud.issue(Transport(ship_id=ship.id, target=tid, count=n))),
                      f"Beam {n} crew across as a boarding party (range {rules.beam_range:,.0f}). Their shield facing us "
                      "and ours facing them must be down. Console: 'board <ship> <crew>'",
                      enabled=transporters, accent=theme.CREW)
        if d <= rules.tractor_range:
            note, col = "in tractor and transporter range", theme.GOOD
        elif d <= rules.beam_range:
            note, col = f"in transporter range · tractor at {rules.tractor_range:,.0f}", theme.GOOD
        else:
            note, col = f"close to {rules.beam_range:,.0f} to board", theme.TEXT_FAINT
        tgt = hud.world.ships.get(tid)
        if tgt is not None and tgt.boarders > 0 and tgt.boarder_side == ship.side:
            note, col = f"our boarders aboard: {tgt.boarders}", theme.CREW
        theme.text(surf, note, (rect.right - 12, yy + 4), col, 11, anchor="topright")


# ------------------------------------------------------------------ weapons

class WeaponsPanel(Panel):
    title = "Weapons"
    min_height = 188
    weight = 0.0

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, hud: BattleScene) -> None:
        y = theme.panel(surf, rect, self.title, theme.PHASER)
        ship = hud.player
        if ship is None:
            return
        obs = hud.obs
        tgt = obs.contact(ship.target) if ship.target is not None else None
        brg = bearing(tgt.x - ship.x, tgt.y - ship.y) if tgt else None
        x0 = rect.x + 12
        # phasers
        theme.text(surf, "Phasers", (x0, y), theme.TEXT_DIM, 12, weight="medium")
        n = len(ship.banks)
        bw = 40
        for i, b in enumerate(ship.banks):
            r = pygame.Rect(x0 + 64 + i * (bw + 4), y - 2, bw, 30)
            frac = b.charge / ship.cls.banks_charge
            bears = brg is not None and bank_bears(ship, b, brg)
            edge = theme.GOOD if bears else theme.BORDER
            pygame.draw.rect(surf, theme.BG_INPUT, r, border_radius=3)
            pygame.draw.rect(surf, edge, r, 1, border_radius=3)
            col = theme.health_color(b.health, b.destroyed) if not b.intact else (
                theme.GOOD if frac >= 0.999 else theme.CAUTION)
            theme.bar(surf, pygame.Rect(r.x + 4, r.bottom - 8, r.width - 8, 4), frac if b.intact else 0, col)
            role = {BankRole.OFFENSE: "O", BankRole.FLEX: "", BankRole.DEFENSE: "PD"}[b.role]
            theme.text(surf, f"{i + 1}", (r.x + 5, r.y + 3), theme.TEXT if b.intact else theme.ALERT, 11, "mono")
            theme.text(surf, MODE_LETTER[b.fire_mode] + (" " + role if role else ""), (r.right - 4, r.y + 3),
                       theme.TEXT_DIM, 10, anchor="topright")
            hud.ui.add(r, partial(hud.fire_phasers, (i,)),
                       f"Bank {i + 1}: {b.charge:.1f}/{ship.cls.banks_charge:.0f} · arc {b.mount.arc_width:.0f}° · "
                       f"{b.fire_mode.value} · {b.role.value}. Click fires, right-click toggles PD reserve.",
                       right=partial(hud.toggle_reserve, i))
        yy = y + 34
        hud.ui.button(surf, pygame.Rect(x0, yy, 110, 22), "Fire phasers (F)", lambda: hud.fire_phasers(None),
                      "Fire every charged bank that bears on the target", accent=theme.PHASER)
        sp = ship.banks[0].spread if ship.banks else 45.0
        hud.ui.button(surf, pygame.Rect(x0 + 116, yy, 22, 22), "−",
                      lambda: hud.issue(SetPhaserSpread(ship_id=ship.id, spread=max(10.0, sp - 5))), "Narrower spread: more damage")
        theme.text(surf, f"{sp:.0f}°", (x0 + 160, yy + 11), theme.TEXT, 12, "mono", anchor="center")
        hud.ui.button(surf, pygame.Rect(x0 + 182, yy, 22, 22), "+",
                      lambda: hud.issue(SetPhaserSpread(ship_id=ship.id, spread=min(45.0, sp + 5))), "Wider spread: easier to hit")
        mode = ship.banks[0].fire_mode if ship.banks else FireMode.MANUAL
        nm = MODE_CYCLE[(MODE_CYCLE.index(mode) + 1) % 3]
        hud.ui.button(surf, pygame.Rect(x0 + 212, yy, 110, 22), f"Mode: {mode.value}",
                      lambda: hud.issue(SetFireMode(ship_id=ship.id, weapon="phaser", mode=nm)),
                      "Manual: on your order. Assisted: computer fires at your target when the shot is good. "
                      "Automatic: computer picks targets.", active=mode != FireMode.MANUAL, accent=theme.PHASER)
        # tubes
        yy += 32
        theme.text(surf, "Tubes", (x0, yy + 6), theme.TEXT_DIM, 12, weight="medium")
        n_bear = 0
        for i, t in enumerate(ship.tubes):
            r = pygame.Rect(x0 + 64 + i * (bw + 4), yy, bw, 30)
            bears = False
            if tgt is not None and brg is not None:
                rel = norm360(brg - ship.course)
                from ..core.angles import in_arc
                bears = not hud.world.rules.tube_arcs or in_arc(rel, t.mount.arc_center, t.mount.arc_width)
            pygame.draw.rect(surf, theme.BG_INPUT, r, border_radius=3)
            pygame.draw.rect(surf, theme.GOOD if bears and t.loaded else theme.BORDER, r, 1, border_radius=3)
            if t.loaded:
                # loaded but the target is outside this tube's arc: dimmed, so it's clear why it won't fire
                lab, col = t.loaded.ordnance.upper()[:4], theme.GOOD if bears or tgt is None else theme.TEXT_DIM
            elif not t.intact:
                lab, col = "DMG", theme.ALERT
            elif ship.torps_remaining <= 0:
                lab, col = "no torp", theme.ALERT
            elif not t.autoload and not t.manual_load_pending:
                lab, col = "empty", theme.TEXT_FAINT
            else:
                lab, col = f"{t.charge:.0f}%", theme.CAUTION
            theme.text(surf, f"{i + 1}", (r.x + 5, r.y + 3), theme.TEXT, 11, "mono")
            theme.text(surf, lab, (r.centerx + 4, r.bottom - 12), col, 10, "mono", anchor="center")
            prox = t.loaded.prox if t.loaded else t.load_prox
            hud.ui.add(r, partial(hud.fire_torpedoes, (i,)),
                       f"Tube {i + 1}: {('loaded ' + t.loaded.ordnance.upper() + f' prox {prox:.0f}') if t.loaded else lab} · "
                       f"autoload {'on' if t.autoload else 'off'} {t.load_ordnance.upper()}"
                       + (f" · arc {t.mount.arc_width:.0f}°" if hud.world.rules.tube_arcs else "")
                       + (" · target outside its arc" if tgt is not None and not bears else ""))
            n_bear += bool(t.loaded and bears)
        if tgt is not None and ship.tubes:
            theme.text(surf, f"{n_bear} bear", (x0, yy + 20), theme.GOOD if n_bear else theme.TEXT_FAINT, 10)
        yy += 34
        hud.ui.button(surf, pygame.Rect(x0, yy, 110, 22), "Fire torps (T)", lambda: hud.fire_torpedoes(None),
                      "Fire every loaded tube whose arc covers the target", accent=theme.TORPEDO, enabled=bool(ship.tubes))
        if ship.tubes:
            t0 = ship.tubes[0]
            on = t0.autoload
            spec = hud.world.content.torpedoes.get(t0.load_ordnance)
            pr = t0.load_prox or (spec.max_prox if spec else 0)
            hud.ui.button(surf, pygame.Rect(x0 + 116, yy, 206, 22),
                          f"Autoload {'on' if on else 'off'} · {t0.load_ordnance.upper()} · prox {pr:.0f}",
                          lambda: hud.issue(ConfigureAutoload(ship_id=ship.id, weapon="tube", enabled=not on)),
                          "Autoload keeps tubes loaded; it never fires. Console: 'al tor al mk7 400'",
                          active=on, accent=theme.GOOD)
        # probes
        yy += 30
        theme.text(surf, "Probes", (x0, yy + 4), theme.TEXT_DIM, 12, weight="medium")
        lx = x0 + 64
        for i, lch in enumerate(ship.launchers):
            lab = lch.loaded.code if lch.loaded else ("DMG" if not lch.intact else "…")
            col = theme.GOOD if lch.loaded else theme.TEXT_FAINT
            r = pygame.Rect(lx + i * 48, yy, 44, 22)
            pygame.draw.rect(surf, theme.BG_INPUT, r, border_radius=3)
            pygame.draw.rect(surf, theme.BORDER, r, 1, border_radius=3)
            theme.text(surf, lab, r.center, col, 11, "mono", anchor="center")
        px = lx + max(1, len(ship.launchers)) * 48 + 6
        hud.ui.button(surf, pygame.Rect(px, yy, 86, 22), "Launch (P)", hud.launch_probe,
                      "Launch a probe at the target", enabled=bool(ship.launchers), accent=theme.PROBE)
        mine = [p for p in obs.ordnance() if p.friendly and p.kind == "probe" and p.owner == ship.id]
        hud.ui.button(surf, pygame.Rect(px + 92, yy, 86, 22), f"Detonate ({len(mine)})",
                      lambda: hud.issue(ControlProbe(ship_id=ship.id, detonate=True)), "Detonate all our probes",
                      enabled=bool(mine), accent=theme.ALERT)


# ------------------------------------------------------------------ contacts

class CrewPanel(Panel):
    """The bridge officers: who runs each station, with a toggle to hand it over or take it back."""

    title = "Bridge crew"
    min_height = 128
    weight = 0.0

    def tab_label(self, hud: BattleScene) -> str:
        ship = hud.player
        n = len(ship.delegated) if ship is not None else 0
        return f"Crew · {n} on duty" if n else "Crew"

    def body(self, surf: pygame.Surface, rect: pygame.Rect, y: int, hud: BattleScene) -> None:
        ship = hud.player
        bridge = hud.bridge
        if ship is None or bridge is None:
            theme.text(surf, "No officers aboard.", (rect.x + 12, y), theme.TEXT_FAINT, 12)
            return
        rh = 22
        for k, (station, o) in enumerate(bridge.crew.officers.items()):
            ry = y + k * rh
            if ry + rh > rect.bottom - 2:
                break
            on = station in ship.delegated
            theme.text(surf, station.title(), (rect.x + 12, ry + 3), theme.TEXT_DIM, 12)
            name_r = pygame.Rect(rect.x + 100, ry, rect.width - 214, rh - 2)
            hover = name_r.collidepoint(hud.ui.mouse)
            theme.text(surf, o.title, (name_r.x, ry + 3), theme.CREW if on or hover else theme.TEXT, 12)
            hud.ui.add(name_r, partial(hud.address, o.aliases[0] if o.aliases else o.id),
                       f"Talk to {o.name} (type after the comma)")
            btn = pygame.Rect(rect.right - 106, ry, 94, rh - 3)
            hud.ui.button(surf, btn, "Officer" if on else "Captain",
                          partial(hud.issue, DelegateStation(ship_id=ship.id, station=station, on=not on)),
                          f"{'Take back' if on else 'Hand over'} the {station} station", active=on, accent=theme.CREW,
                          size=11)


class ContactsPanel(Panel):
    title = "Contacts"
    min_height = 90
    weight = 1.0

    def tab_label(self, hud: BattleScene) -> str:
        n = sum(1 for c in hud.obs.contacts().values() if c.visible)
        return f"Contacts · {n}"

    def body(self, surf: pygame.Surface, rect: pygame.Rect, y: int, hud: BattleScene) -> None:
        ship = hud.player
        obs = hud.obs
        if ship is None:
            return
        rows: list[tuple[float, str, theme.Color, int, str]] = []
        for s in obs.own_ships(alive_only=False):
            if s.id == ship.id or not s.exists:
                continue
            d = math.hypot(s.x - ship.x, s.y - ship.y)
            rows.append((d, s.name + ("" if s.alive else f" ({s.status.value})"), theme.ALLY, s.id,
                         f"{s.cls.abbrev} · ally"))
        for c in obs.contacts().values():
            d = c.distance_to(ship.x, ship.y)
            col = theme.HOSTILE if c.identified else theme.UNKNOWN
            if not c.visible:
                col = theme.dim(col, 0.55)
            what = c.cls.abbrev if c.cls else "?"
            rows.append((d, c.label if c.identified else f"Contact #{c.id}", col, c.id,
                         f"{what} · {('hazy' if c.haze > 0 else 'tracking') if c.visible else 'lost'}"))
        rows.sort()
        rh = 20
        for k, (d, name, col, sid, note) in enumerate(rows):
            ry = y + k * rh
            if ry + rh > rect.bottom - 4:
                theme.text(surf, f"+{len(rows) - k} more", (rect.x + 12, ry), theme.TEXT_FAINT, 11)
                break
            r = pygame.Rect(rect.x + 4, ry - 2, rect.width - 8, rh)
            if sid == ship.target or sid == hud.selected_ally:
                pygame.draw.rect(surf, theme.BG_PANEL_HI, r, border_radius=3)
            elif r.collidepoint(hud.ui.mouse):
                pygame.draw.rect(surf, (16, 27, 49), r, border_radius=3)
            theme.text(surf, name, (rect.x + 12, ry), col, 12)
            theme.text(surf, note, (rect.x + rect.width * 0.48, ry), theme.TEXT_DIM, 11)
            theme.text(surf, f"{d:>7,.0f}", (rect.right - 12, ry), theme.TEXT, 12, "mono", anchor="topright")
            if sid in obs.contacts():
                hud.ui.add(r, partial(hud.issue, SelectTarget(ship_id=ship.id, target=sid, subsystem=ship.target_subsystem)),
                           "Select as target")
            else:
                hud.ui.add(r, partial(hud.select_ally, sid), "Give this ally orders",
                           right=partial(hud.center_on, sid))


# ------------------------------------------------------------------ fleet

# (label, order, needs our target, tooltip): one-click standing orders, the same as `tell <ally> ...`
FLEET_ORDERS: list[tuple[str, str, bool, str]] = [
    ("Escort me", "escort", False, "Stay with the flagship at 3,000 and fight what comes near."),
    ("Defend me", "defend", False, "Stay close and shoot whatever threatens the flagship."),
    ("Attack target", "attack", True, "Close and attack the flagship's current target."),
    ("Run", "run", False, "Run away from the enemy."),
    ("Withdraw", "withdraw", False, "Pull back out of torpedo range and wait."),
    ("Stop", "stop", False, "All stop."),
    ("Cancel", "cancel", False, "Cancel movement orders: the ally's own captain takes over."),
]


class FleetPanel(Panel):
    """Orders for one ally at a time: the `tell` vocabulary as buttons, plus docking and transfers with it."""

    title = "Fleet"

    def tab_label(self, hud: BattleScene) -> str:
        n = len(hud.allies())
        return f"Fleet · {n}" if n else "Fleet"

    def body(self, surf: pygame.Surface, rect: pygame.Rect, y: int, hud: BattleScene) -> None:
        ship = hud.player
        allies = hud.allies()
        if ship is None or not allies:
            theme.text(surf, "No allies under your command.", (rect.x + 12, y), theme.TEXT_FAINT, 12)
            return
        ids = [a.id for a in allies]
        if hud.selected_ally not in ids:
            hud.selected_ally = ids[0]
        k = ids.index(hud.selected_ally)
        a = allies[k]
        x0 = rect.x + 12
        # selector
        hud.ui.button(surf, pygame.Rect(x0, y, 22, 22), "‹", lambda: hud.select_ally(ids[(k - 1) % len(ids)]),
                      "Previous ally", enabled=len(ids) > 1, size=14)
        d = math.hypot(a.x - ship.x, a.y - ship.y)
        name_r = pygame.Rect(x0 + 28, y, rect.width - 80, 22)
        theme.text(surf, a.name, (name_r.x, y + 2), theme.ALLY, 14, weight="semibold")
        nx = name_r.x + theme.text_width(a.name, 14, weight="semibold") + 8
        hf = max(0.0, a.structure) / a.structure_max
        theme.text(surf, f"{a.cls.abbrev} · {d:,.0f} · hull {hf * 100:.0f}%", (nx, y + 5), theme.TEXT_DIM, 11)
        hud.ui.add(name_r, lambda: hud.center_on(a.id), "Centre the map on this ally")
        hud.ui.button(surf, pygame.Rect(rect.right - 34, y, 22, 22), "›", lambda: hud.select_ally(ids[(k + 1) % len(ids)]),
                      "Next ally", enabled=len(ids) > 1, size=14)
        st = hud.obs.ally_order(a.id)
        names = {s.id: s.name for s in hud.world.ships.values()}
        mission = st.summary(names) if st is not None else ""
        theme.text(surf, "Mission", (x0, y + 28), theme.TEXT_DIM, 11)
        theme.text(surf, mission or "own initiative", (x0 + 56, y + 28), theme.TEXT if mission else theme.TEXT_FAINT, 11)
        # orders
        yy = y + 48
        bw = (rect.width - 24 - 4 * 3) // 4
        cells: list[tuple[str, Callable[[], object], str, bool, bool]] = []
        for label, order, needs_target, tip in FLEET_ORDERS:
            tgt: int | None = ship.target if needs_target else (ship.id if order in ("escort", "defend") else None)
            active = st is not None and ((st.movement == order and st.move_target in (None, ship.id))
                                         or (order == "attack" and st.target is not None and st.target == ship.target))
            enabled = not needs_target or ship.target is not None
            cells.append((label, partial(hud.order_ally, a.id, order, tgt), f"{tip} Console: 'tell {a.name} {order}'",
                          active, enabled))
        holding = st is not None and st.hold_fire
        cells.insert(3, ("Open fire" if holding else "Hold fire", partial(hud.order_ally, a.id, "open" if holding else "hold"),
                         "Weapons free" if holding else "Hold fire until told otherwise", holding, True))
        if a.docked_to is not None:
            cells.append(("Undock", partial(hud.order_ally, a.id, "undock"), f"Leave {names.get(a.docked_to, 'the base')}",
                          True, True))
        else:
            base = hud.nearest_base(a)
            cells.append(("Dock at base", partial(hud.order_ally, a.id, "dock", base.id if base else None),
                          f"Go and dock with {base.name} to repair and resupply" if base else "No friendly base with docking bays.",
                          st is not None and st.movement == "dock", base is not None))
        cells.append(("Disengage", partial(hud.order_ally, a.id, "disengage"), "Forget the ordered target; pick our own",
                      False, st is not None and st.target is not None))
        towing = a.tractor_target is not None
        cells.append(("Release tow", partial(hud.order_ally, a.id, "release"), "Drop the tractor beam", towing, towing))
        cells.append(("Report", partial(hud.ally_report, a.id), f"Status report from {a.name}. Console: 'tell {a.name} report'",
                      False, True))
        for i, (label, fn, tip, active, enabled) in enumerate(cells):
            r = pygame.Rect(x0 + (i % 4) * (bw + 4), yy + (i // 4) * 26, bw, 22)
            hud.ui.button(surf, r, label, fn, tip, active=active, enabled=enabled, accent=theme.ALLY, size=11)
        yy += 26 * ((len(cells) + 3) // 4) + 4
        # groups
        theme.text(surf, "Group", (x0, yy + 4), theme.TEXT_DIM, 11)
        group = st.group if st is not None else None
        for g in (1, 2, 3):
            r = pygame.Rect(x0 + 48 + (g - 1) * 30, yy, 26, 22)
            hud.ui.button(surf, r, str(g), partial(hud.order_ally, a.id, "leave" if group == g else "join", None,
                                                    None if group == g else float(g)),
                          f"{'Leave' if group == g else 'Join'} group {g}; then 'tell {g} ...' orders the whole group",
                          active=group == g, accent=theme.ALLY, size=11)
        # our own ship with this ally: dock, beam crew, transfer command
        x = x0 + 48 + 3 * 30 + 12
        bays = a.cls.mass_capacity > 0
        docked = ship.docked_to == a.id
        hud.ui.button(surf, pygame.Rect(x, yy, 74, 22), "Undock" if docked else "Dock",
                      partial(hud.issue, Dock(ship_id=ship.id, host=None if docked else a.id)),
                      f"Dock with {a.name} to repair and resupply (range {hud.world.rules.dock_range:,.0f})" if bays
                      else f"The {a.cls.name} has no docking bays.", active=docked, enabled=bays or docked, accent=theme.GOOD,
                      size=11)
        hud.ui.button(surf, pygame.Rect(x + 78, yy, 74, 22), "Beam 20",
                      partial(hud.issue, Transport(ship_id=ship.id, target=a.id, count=20)),
                      f"Beam 20 crew to {a.name} (range {hud.world.rules.beam_range:,.0f}, facing shields down). "
                      f"Console: 'beam {a.name} <crew>'", accent=theme.CREW, size=11)
        hud.ui.button(surf, pygame.Rect(x + 156, yy, rect.right - 12 - (x + 156), 22), "Take command",
                      partial(hud.take_command, a.id), f"Beam aboard {a.name} and command her. Console: 'beam {a.name}'",
                      accent=theme.FRIEND, size=11)


class TabbedPanel(Panel):
    """Several panels sharing one slot, with a tab strip for a header."""

    weight = 1.0
    min_height = 150

    def __init__(self, tabs: list[Panel]) -> None:
        self.tabs = tabs
        self.active = 0

    def show(self, cls: type[Panel]) -> None:
        for i, t in enumerate(self.tabs):
            if isinstance(t, cls):
                self.active = i

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, hud: BattleScene) -> None:
        theme.panel(surf, rect)
        x = rect.x + 6
        for i, t in enumerate(self.tabs):
            label = t.tab_label(hud).upper()
            w = theme.text_width(label, 11, weight="semibold") + 20
            r = pygame.Rect(x, rect.y + 2, w, 22)
            on = i == self.active
            if on:
                pygame.draw.line(surf, theme.FRIEND, (r.x + 4, rect.y + 1), (r.x + 28, rect.y + 1), 2)
            elif r.collidepoint(hud.ui.mouse):
                pygame.draw.rect(surf, theme.BG_PANEL_HI, r, border_radius=3)
            theme.text(surf, label, (r.x + 4, rect.y + 7), theme.TEXT if on else theme.TEXT_FAINT, 11, weight="semibold")
            hud.ui.add(r, partial(setattr, self, "active", i), t.title)
            x += w + 2
        self.tabs[self.active].body(surf, rect, rect.y + 28, hud)


__all__ = [
    "ContactsPanel", "CrewPanel", "FLEET_ORDERS", "FleetPanel", "OwnShipPanel", "Panel", "TabbedPanel", "TargetPanel",
    "WeaponsPanel", "hull_diagram",
]
