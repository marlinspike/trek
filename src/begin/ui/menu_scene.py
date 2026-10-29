"""Main menu, preset list and custom battle setup."""

from __future__ import annotations

import random
from typing import Callable

import pygame

from ..battle import BattleSetup, FleetSpec, ShipSpec, quick_battle
from ..content.schema import ContentDB
from ..presets import Preset, load_presets
from . import theme
from .hulls import draw_hull
from .settings import Settings
from .widgets import UI

FACTIONS = ["federation", "klingon", "romulan", "orion"]


class MenuScene:
    def __init__(self, content: ContentDB, settings: Settings, start: Callable[[BattleSetup], None],
                 quit_: Callable[[], None], show_help: Callable[[], None] | None = None) -> None:
        self.content = content
        self.settings = settings
        self.start = start
        self.quit = quit_
        self.ui = UI()
        self.page = "main"
        self.presets: list[Preset] = load_presets()
        self.preset_i = 0
        self.size = (1600, 900)
        cs = settings.custom
        self.custom = {
            "player_faction": cs.get("player_faction", "federation"),
            "player_class": cs.get("player_class", "federation.hc"),
            "wingmen": int(cs.get("wingmen", 0)),
            "enemy_faction": cs.get("enemy_faction", "klingon"),
            "enemy_class": cs.get("enemy_class", "klingon.bc"),
            "enemies": int(cs.get("enemies", 1)),
            "seed": int(cs.get("seed", 1)),
        }
        self.t = 0.0

    def layout(self, size: tuple[int, int]) -> None:
        self.size = size

    def update(self, dt: float) -> None:
        self.t += dt
        self.ui.mouse = pygame.mouse.get_pos()

    def handle(self, ev: pygame.event.Event) -> None:
        if ev.type == pygame.VIDEORESIZE:
            self.layout((ev.w, ev.h))
        elif ev.type == pygame.MOUSEBUTTONDOWN and ev.button in (1, 3):
            h = self.ui.hit(ev.pos)
            if h is not None:
                if ev.button == 3 and h.right is not None:
                    h.right()
                elif ev.button == 1:
                    h.action()
        elif ev.type == pygame.KEYDOWN:
            if ev.key == pygame.K_ESCAPE:
                if self.page == "main":
                    self.quit()
                else:
                    self.page = "main"
            elif self.page == "presets" and ev.key in (pygame.K_UP, pygame.K_DOWN):
                d = -1 if ev.key == pygame.K_UP else 1
                self.preset_i = (self.preset_i + d) % len(self.presets)
            elif self.page == "presets" and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.start(self.presets[self.preset_i].setup())
            elif self.page == "main" and ev.key in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self._quick()

    # ------------------------------------------------------------ actions

    def _quick(self) -> None:
        seed = random.randrange(1, 100000)
        self.start(quick_battle(self.content, seed, self.custom["player_faction"]))

    def _custom_setup(self) -> BattleSetup:
        c = self.custom
        self.settings.custom = dict(c)
        self.settings.save()
        mine = [ShipSpec(c["player_class"])] + [ShipSpec(c["player_class"]) for _ in range(c["wingmen"])]
        theirs = [ShipSpec(c["enemy_class"]) for _ in range(c["enemies"])]
        pn = self.content.factions[c["player_faction"]].name
        en = self.content.factions[c["enemy_faction"]].name
        return BattleSetup(
            [FleetSpec(0, mine, player=True, center=(0.0, -12000.0)), FleetSpec(1, theirs, center=(0.0, 12000.0))],
            seed=c["seed"], title="Custom battle",
            description=f"{len(mine)} {pn} vs {len(theirs)} {en}",
        )

    def _cycle(self, key: str, options: list[str], step: int = 1) -> None:
        i = options.index(self.custom[key]) if self.custom[key] in options else 0
        self.custom[key] = options[(i + step) % len(options)]
        if key == "player_faction":
            self.custom["player_class"] = self._classes(self.custom["player_faction"], True)[0]
        if key == "enemy_faction":
            self.custom["enemy_class"] = self._classes(self.custom["enemy_faction"], False)[0]

    def _classes(self, faction: str, player: bool) -> list[str]:
        cl = [c for c in self.content.classes_of(faction, include_bases=not player) if c.banks > 0]
        return [c.id for c in sorted(cl, key=lambda c: -c.mass)]

    # ------------------------------------------------------------ drawing

    def draw(self, surf: pygame.Surface) -> None:
        self.ui.begin_frame()
        surf.fill(theme.BG)
        w, h = surf.get_size()
        # quiet grid backdrop
        off = (self.t * 6) % 80
        for x in range(-80, w + 80, 80):
            pygame.draw.line(surf, theme.GRID, (x + off, 0), (x + off, h))
        for y in range(0, h, 80):
            pygame.draw.line(surf, theme.GRID, (0, y), (w, y))
        theme.text(surf, "BEGIN", (80, 70), theme.FRIEND, 64, weight="semibold")
        theme.text(surf, "A tactical starship simulation · a remake of Begin 2", (84, 150), theme.TEXT_DIM, 16)
        if self.page == "main":
            self._main(surf)
        elif self.page == "presets":
            self._presets(surf)
        elif self.page == "custom":
            self._custom(surf)
        elif self.page == "about":
            self._about(surf)
        self.ui.draw_tooltip(surf)

    def _main(self, surf: pygame.Surface) -> None:
        x, y = 84, 220
        items = [
            ("Quick battle", self._quick, "A seeded random engagement (Enter)"),
            ("Preset battles", lambda: setattr(self, "page", "presets"), "Curated scenarios"),
            ("Custom battle", lambda: setattr(self, "page", "custom"), "Choose fleets"),
            ("About & licensing", lambda: setattr(self, "page", "about"), ""),
            ("Quit", self.quit, "Esc"),
        ]
        for label, act, tip in items:
            self.ui.button(surf, pygame.Rect(x, y, 300, 44), label, act, tip, size=16)
            y += 56
        pf = self.custom["player_faction"]
        self.ui.button(surf, pygame.Rect(x, y + 12, 300, 30), f"Quick battle side: {self.content.factions[pf].name}",
                       lambda: self._cycle("player_faction", FACTIONS), "Which faction you command in a quick battle",
                       size=12)
        # a silhouette parade on the right
        w, h = surf.get_size()
        cx = int(w * 0.68)
        for i, cid in enumerate(["federation.hc", "klingon.bc", "romulan.bp", "orion.an"]):
            cls = self.content.classes[cid]
            yy = 250 + i * 150
            col = theme.FRIEND if cls.faction == "federation" else theme.HOSTILE
            draw_hull(surf, cls.hull, cx, yy, 90.0 + 4 * (i % 2), 1.25, col)
            theme.text(surf, f"{cls.name} · {self.content.factions[cls.faction].name}", (cx + 90, yy - 8), theme.TEXT_DIM, 13)

    def _presets(self, surf: pygame.Surface) -> None:
        x, y = 84, 210
        for i, p in enumerate(self.presets):
            self.ui.button(surf, pygame.Rect(x, y, 300, 34), p.title, (lambda i=i: setattr(self, "preset_i", i)),
                           active=i == self.preset_i, size=14)
            y += 40
        self.ui.button(surf, pygame.Rect(x, y + 14, 140, 34), "Back", lambda: setattr(self, "page", "main"), size=13)
        p = self.presets[self.preset_i]
        r = pygame.Rect(420, 210, min(760, surf.get_width() - 460), 420)
        yy = theme.panel(surf, r, p.title)
        words = p.description.split()
        line = ""
        for wd in words:
            if theme.text_width(line + " " + wd, 15) > r.width - 40:
                theme.text(surf, line.strip(), (r.x + 20, yy), theme.TEXT, 15)
                yy += 24
                line = ""
            line += " " + wd
        theme.text(surf, line.strip(), (r.x + 20, yy), theme.TEXT, 15)
        yy += 40
        for f in p.fleets:
            side = int(f["side"])
            names = [self.content.classes[c].name for c in f["ships"]]
            fac = self.content.classes[f["ships"][0]].faction
            col = theme.FRIEND if f.get("player") else theme.HOSTILE
            lab = self.content.factions[fac].name + (" (you)" if f.get("player") else "")
            theme.text(surf, lab, (r.x + 20, yy), col, 14, weight="medium")
            theme.text(surf, ", ".join(names), (r.x + 200, yy), theme.TEXT_DIM, 13)
            yy += 24 + 0 * side
        self.ui.button(surf, pygame.Rect(r.right - 180, r.bottom - 50, 160, 36), "Start (Enter)",
                       lambda: self.start(p.setup()), size=14, accent=theme.GOOD)

    def _custom(self, surf: pygame.Surface) -> None:
        c = self.custom
        x, y = 84, 210
        rows = [
            ("Your faction", self.content.factions[c["player_faction"]].name,
             lambda s=1: self._cycle("player_faction", FACTIONS, s)),
            ("Your ship", self.content.classes[c["player_class"]].name,
             lambda s=1: self._cycle("player_class", self._classes(c["player_faction"], True), s)),
            ("Wingmen", str(c["wingmen"]), lambda s=1: self.custom.__setitem__("wingmen", max(0, min(29, c["wingmen"] + s)))),
            ("Enemy faction", self.content.factions[c["enemy_faction"]].name,
             lambda s=1: self._cycle("enemy_faction", FACTIONS, s)),
            ("Enemy ships", self.content.classes[c["enemy_class"]].name,
             lambda s=1: self._cycle("enemy_class", self._classes(c["enemy_faction"], False), s)),
            ("Enemy count", str(c["enemies"]), lambda s=1: self.custom.__setitem__("enemies", max(1, min(30, c["enemies"] + s)))),
            ("Seed", str(c["seed"]), lambda s=1: self.custom.__setitem__("seed", max(1, c["seed"] + s))),
        ]
        for label, value, fn in rows:
            theme.text(surf, label, (x, y + 8), theme.TEXT_DIM, 14)
            self.ui.button(surf, pygame.Rect(x + 160, y, 300, 34), value, fn,
                           "Click for next, right-click for previous", size=14, right=lambda fn=fn: fn(-1))
            y += 44
        self.ui.button(surf, pygame.Rect(x + 160, y + 16, 300, 40), "Start battle",
                       lambda: self.start(self._custom_setup()), size=15, accent=theme.GOOD)
        self.ui.button(surf, pygame.Rect(x, y + 16, 140, 40), "Back", lambda: setattr(self, "page", "main"), size=13)
        theme.text(surf, "Begin's limit is 60 ships in one battle.", (x, y + 76), theme.TEXT_FAINT, 12)

    def _about(self, surf: pygame.Surface) -> None:
        lines = [
            "A personal, non-commercial fan remake of Begin 2 (Clockwork Software).",
            "Mechanics follow the Begin 1.65 manual and the fireflyk64/begin reconstruction;",
            "remake extensions are documented in docs/DEVIATIONS.md.",
            "Star Trek names and factions belong to their owners. Not for distribution as-is:",
            "a public release would need a renamed content pack (see LICENSING.md).",
            "Fonts: Inter (SIL OFL 1.1), JetBrains Mono (OFL 1.1).",
        ]
        y = 220
        for ln in lines:
            theme.text(surf, ln, (84, y), theme.TEXT, 15)
            y += 28
        self.ui.button(surf, pygame.Rect(84, y + 20, 140, 36), "Back", lambda: setattr(self, "page", "main"), size=13)


__all__ = ["MenuScene"]
