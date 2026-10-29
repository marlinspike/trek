"""HUD panels for the battle screen.

Each panel is a small class with `draw(surf, rect, hud)` and a preferred
height. Panels read the player's `Observation` and issue commands through
`hud.issue(...)`, exactly like the console, the AI and the officers.
To add a panel, subclass `Panel` and append it to `BattleScene.panels`.
"""

from __future__ import annotations

import math
from typing import TYPE_CHECKING, ClassVar

import pygame

from ..core.angles import bearing, norm360
from ..sim.commands import (
    ConfigureAutoload, ControlProbe, DelegateStation, FirePhasers, FireTorpedoes, LaunchProbe, Scan, SelectTarget, SetFireMode,
    SetPhaserSpread, SetPointDefense, SetShields,
)
from ..sim.factory import SHIELD_FACINGS
from ..sim.ship import BankRole, FireMode, Kind, PDDoctrine, Ship
from ..sim.systems.phasers import bank_bears, bank_ready
from . import theme
from .hulls import draw_hull, transform

if TYPE_CHECKING:
    from .battle_scene import BattleScene

MODE_LETTER = {FireMode.MANUAL: "M", FireMode.ASSISTED: "A", FireMode.AUTOMATIC: "★"}
MODE_CYCLE = [FireMode.MANUAL, FireMode.ASSISTED, FireMode.AUTOMATIC]
PD_CYCLE = [PDDoctrine.OFF, PDDoctrine.CONSERVATIVE, PDDoctrine.BALANCED, PDDoctrine.AGGRESSIVE]
SUB_GROUPS = [None, "propulsion", "weapons", "shields", "power", "sensors"]


class Panel:
    title: ClassVar[str] = ""
    weight: ClassVar[float] = 1.0   # share of leftover column height
    min_height: ClassVar[int] = 120

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, hud: BattleScene) -> None:
        raise NotImplementedError


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
    min_height = 196
    weight = 0.0

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, hud: BattleScene) -> None:
        y = theme.panel(surf, rect, self.title, theme.HOSTILE)
        ship = hud.player
        obs = hud.obs
        tid = ship.target if ship else None
        c = obs.contact(tid) if tid is not None else None
        if ship is None or c is None:
            theme.text(surf, "No target. Click a contact, or press Tab.", (rect.x + 12, y), theme.TEXT_DIM, 13)
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
                          (lambda g=g: hud.issue(SelectTarget(ship_id=ship.id, target=c.id, subsystem=g))),
                          "Precision fire at a subsystem group (R cycles)", active=cur == g, accent=theme.CAUTION, size=11)
            x += w + 4
        # scan
        yy += 30
        pend = hud.world.pending_scan(ship.id)
        label = "Scanning…" if pend else "Scan (X)"
        hud.ui.button(surf, pygame.Rect(rect.x + 12, yy, 92, 22), label,
                      lambda: hud.issue(Scan(ship_id=ship.id, target=c.id)), "Detailed sensor scan", enabled=pend is None)
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


# ------------------------------------------------------------------ weapons

class WeaponsPanel(Panel):
    title = "Weapons"
    min_height = 238
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
            hud.ui.add(r, (lambda i=i: hud.fire_phasers((i,))),
                       f"Bank {i + 1}: {b.charge:.1f}/{ship.cls.banks_charge:.0f} · arc {b.mount.arc_width:.0f}° · "
                       f"{b.fire_mode.value} · {b.role.value}. Click fires, right-click toggles PD reserve.",
                       right=(lambda i=i: hud.toggle_reserve(i)))
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
        for i, t in enumerate(ship.tubes):
            r = pygame.Rect(x0 + 64 + i * (bw + 4), yy, bw, 30)
            bears = False
            if tgt is not None and brg is not None:
                rel = norm360(brg - ship.course)
                from ..core.angles import in_arc
                bears = in_arc(rel, t.mount.arc_center, t.mount.arc_width)
            pygame.draw.rect(surf, theme.BG_INPUT, r, border_radius=3)
            pygame.draw.rect(surf, theme.GOOD if bears and t.loaded else theme.BORDER, r, 1, border_radius=3)
            if t.loaded:
                lab, col = t.loaded.ordnance.upper(), theme.GOOD
            elif not t.intact:
                lab, col = "DMG", theme.ALERT
            elif not t.autoload and not t.manual_load_pending:
                lab, col = "empty", theme.TEXT_FAINT
            else:
                lab, col = f"{t.charge:.0f}%", theme.CAUTION
            theme.text(surf, f"{i + 1}", (r.x + 5, r.y + 3), theme.TEXT, 11, "mono")
            theme.text(surf, lab, (r.centerx + 4, r.bottom - 12), col, 10, "mono", anchor="center")
            prox = t.loaded.prox if t.loaded else t.load_prox
            hud.ui.add(r, (lambda i=i: hud.fire_torpedoes((i,))),
                       f"Tube {i + 1}: {('loaded ' + t.loaded.ordnance.upper() + f' prox {prox:.0f}') if t.loaded else lab} · "
                       f"autoload {'on' if t.autoload else 'off'} {t.load_ordnance.upper()} · arc {t.mount.arc_width:.0f}°")
        yy += 34
        hud.ui.button(surf, pygame.Rect(x0, yy, 110, 22), "Fire torps (T)", lambda: hud.fire_torpedoes(None),
                      "Fire every loaded tube with a solution", accent=theme.TORPEDO, enabled=bool(ship.tubes))
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

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, hud: BattleScene) -> None:
        y = theme.panel(surf, rect, self.title)
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
            hud.ui.add(name_r, (lambda o=o: hud.address(o.aliases[0] if o.aliases else o.id)),
                       f"Talk to {o.name} (type after the comma)")
            btn = pygame.Rect(rect.right - 106, ry, 94, rh - 3)
            hud.ui.button(surf, btn, "Officer" if on else "Captain",
                          (lambda st=station, on=on: hud.issue(DelegateStation(ship_id=ship.id, station=st, on=not on))),
                          f"{'Take back' if on else 'Hand over'} the {station} station", active=on, accent=theme.CREW,
                          size=11)


class ContactsPanel(Panel):
    title = "Contacts"
    min_height = 90
    weight = 1.0

    def draw(self, surf: pygame.Surface, rect: pygame.Rect, hud: BattleScene) -> None:
        y = theme.panel(surf, rect, self.title)
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
                         f"{what} · {'tracking' if c.visible else 'lost'}"))
        rows.sort()
        rh = 20
        for k, (d, name, col, sid, note) in enumerate(rows):
            ry = y + k * rh
            if ry + rh > rect.bottom - 4:
                theme.text(surf, f"+{len(rows) - k} more", (rect.x + 12, ry), theme.TEXT_FAINT, 11)
                break
            r = pygame.Rect(rect.x + 4, ry - 2, rect.width - 8, rh)
            if sid == ship.target:
                pygame.draw.rect(surf, theme.BG_PANEL_HI, r, border_radius=3)
            elif r.collidepoint(hud.ui.mouse):
                pygame.draw.rect(surf, (16, 27, 49), r, border_radius=3)
            theme.text(surf, name, (rect.x + 12, ry), col, 12)
            theme.text(surf, note, (rect.x + rect.width * 0.48, ry), theme.TEXT_DIM, 11)
            theme.text(surf, f"{d:>7,.0f}", (rect.right - 12, ry), theme.TEXT, 12, "mono", anchor="topright")
            if sid in obs.contacts():
                hud.ui.add(r, (lambda sid=sid: hud.issue(SelectTarget(ship_id=ship.id, target=sid,
                                                                      subsystem=ship.target_subsystem))),
                           "Select as target")
            else:
                hud.ui.add(r, (lambda sid=sid: hud.center_on(sid)), "Centre the map on this ally")


__all__ = ["ContactsPanel", "CrewPanel", "OwnShipPanel", "Panel", "TargetPanel", "WeaponsPanel", "hull_diagram"]
