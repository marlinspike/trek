"""No words run off the screen or out of their panel, on any screen, at any common window size.

Every screen is drawn while `theme.watching()` records each line of text and each panel (cards, buttons, tool
tips, the battle column's panels). A line must sit inside the screen, or inside the area a scrolling list clips
to, and a line that starts inside a panel must end inside it. Text a scrolling list has moved out of view is fine;
half a word cut by an edge is not."""

from __future__ import annotations

import os
from collections.abc import Callable

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from begin.ui import theme  # noqa: E402

SIZES = [(1024, 640), (1440, 860), (1920, 1080)]


def overflows(ink: list[theme.Ink]) -> list[str]:
    """What ran over: one line per offending piece of text, saying where it went."""
    bad: list[str] = []
    panels: list[theme.Ink] = []
    for k in ink:
        if k.kind == "panel":
            panels.append(k)
            continue
        r = k.rect
        if not k.text.strip() or r.width <= 0:
            continue
        whole = k.surf.get_rect()
        view = k.clip.clip(whole)
        scrolling = view != whole
        if scrolling and not r.colliderect(view):
            continue                                  # scrolled out of sight
        if r.left < view.left or r.right > view.right or (not scrolling and (r.top < view.top or r.bottom > view.bottom)):
            bad.append(f"{k.text!r} at {tuple(r)} runs past the edge of {tuple(view)}")
            continue
        under = [p for p in panels if p.surf is k.surf and p.rect.clip(p.clip).collidepoint(r.topleft)]
        if under:
            box = under[-1].rect                      # the panel drawn last under it: the one it is written on
            if r.left < box.left or r.right > box.right or (not scrolling and r.bottom > box.bottom):
                bad.append(f"{k.text!r} at {tuple(r)} runs out of its panel {tuple(box)}")
    return bad


class Sweep:
    """Draws screens and gathers what overflowed, named by screen and window size."""

    def __init__(self) -> None:
        self.found: dict[str, str] = {}

    def draw(self, name: str, draw: Callable[[pygame.Surface], object], surf: pygame.Surface) -> None:
        with theme.watching() as ink:
            draw(surf)
        for b in overflows(ink):
            self.found.setdefault(b.split(" at ")[0], f"{name} {surf.get_size()}: {b}")

    def report(self) -> str:
        return "\n".join(sorted(self.found.values()))


@pytest.fixture()
def sweep(content):  # type: ignore[no-untyped-def]
    pygame.init()
    theme.font.cache_clear()
    theme._fallback.cache_clear()
    yield Sweep()


# ------------------------------------------------------------------ the helpers

def test_wrap_fits_every_line_and_keeps_counts_with_their_ships() -> None:
    pygame.font.init()
    from begin.ui.menu_scene import roster

    words = roster(["Dreadnought"] * 3 + ["Battle Cruiser"] * 3 + ["Frigate"] * 2 + ["Escort"] * 2 + ["Scout"])
    assert words == "3 × Dreadnought, 3 × Battle Cruiser, 2 × Frigate, 2 × Escort, Scout"
    for width in (120, 200, 333):
        lines = theme.wrap(words, 13, width)
        assert all(theme.text_width(ln, 13) <= width for ln in lines)
        assert " ".join(lines) == words
        assert not any(ln.endswith(" ×") or ln.startswith("×") for ln in lines)
    long = theme.wrap("Supercalifragilisticexpialidocious", 14, 60)    # one word wider than the room: broken up
    assert len(long) > 1 and all(theme.text_width(ln, 14) <= 60 for ln in long)
    assert theme.wrap("one\n\ntwo", 14, 400) == ["one", "", "two"]


def test_fit_and_clip_lines_end_in_an_ellipsis_only_when_cut() -> None:
    pygame.font.init()
    assert theme.fit("Short", 12, 200) == "Short"
    cut = theme.fit("A line far too long to fit in so little room", 12, 90)
    assert cut.endswith("…") and theme.text_width(cut, 12) <= 90
    kept = theme.clip_lines(["one", "two", "three"], 2, 12, 200)
    assert kept[0] == "one" and kept[1].endswith("…") and len(kept) == 2
    assert theme.clip_lines(["one"], 3, 12, 200) == ["one"]


def test_watching_costs_nothing_outside_a_test() -> None:
    pygame.font.init()
    surf = pygame.Surface((200, 50))
    assert theme._ink is None
    with theme.watching() as ink:
        theme.text(surf, "Hello", (5, 5))
        theme.panel(surf, pygame.Rect(0, 0, 100, 40))
    assert theme._ink is None and [k.kind for k in ink] == ["text", "panel"]
    with theme.watching() as ink:
        theme.panel(surf, pygame.Rect(0, 0, 60, 40))
        theme.text(surf, "A much longer line", (5, 5))
    assert overflows(ink) and "runs out of its panel" in overflows(ink)[0]


# ------------------------------------------------------------------ every screen

def test_the_main_menu_presets_and_settings(sweep, content) -> None:  # type: ignore[no-untyped-def]
    from begin.settings import Settings
    from begin.ui.menu_scene import MenuScene

    for size in SIZES:
        surf = pygame.display.set_mode(size)
        m = MenuScene(content, Settings(), lambda setup: None, lambda: None)
        m.surf = surf
        for page in ("main", "custom", "about"):
            m.page = page
            sweep.draw(f"menu {page}", m.draw, surf)
        m.page = "presets"
        for i, p in enumerate(m.presets):          # the briefing: every fleet's ships on the card
            m.preset_i = i
            sweep.draw(f"preset {p.title}", m.draw, surf)
        m.open_settings()
        for sec in m.hub.sections:
            m.hub.go(sec.key)
            sweep.draw(f"settings {sec.key}", m.draw, surf)
    assert not sweep.found, sweep.report()


def test_the_battle_screen_its_panels_and_tabs(sweep, content) -> None:  # type: ignore[no-untyped-def]
    from begin.battle import build_battle
    from begin.presets import load_presets
    from begin.settings import Settings
    from begin.ui.battle_scene import BattleScene
    from begin.ui.menu_scene import MenuScene

    presets = {p.title: p for p in load_presets()}
    for size in SIZES:
        surf = pygame.display.set_mode(size)
        m = MenuScene(content, Settings(), lambda setup: None, lambda: None)
        m.custom.update(wingmen=29, enemies=30)
        setups = [("60 ships", m._custom_setup()), ("Pirate Hunt", presets["Pirate Hunt"].setup()),
                  ("Fleet Action", presets["Fleet Action"].setup())]
        for name, setup in setups:
            sc = BattleScene(build_battle(content, setup), size, lambda: None)
            sc.paused = False
            for _ in range(200):
                sc.update(1 / 30)
            sc.draw(surf)                              # lays the column out (and folds panels into tabs if short)
            for i in range(len(sc.side_tabs.tabs)):
                sc.side_tabs.active = i
                sweep.draw(f"{name} tab {sc.side_tabs.tabs[i].title}", sc.draw, surf)
            sc.side_tabs.active = 0
            for line in ("status banks", "chart by distance", "hud bridge full"):
                sc.run_console(line)
                sweep.draw(f"{name} after {line!r}", sc.draw, surf)
            for overlay in ("help", "menu", "damage", "scan", "voice"):
                sc.overlay = overlay
                sweep.draw(f"{name} {overlay}", sc.draw, surf)
            sc.overlay = None
            if sc.player is not None and sc.open_wheel(sc.player.id):
                sweep.draw(f"{name} wheel", sc.draw, surf)
                sc.wheel = None
    assert not sweep.found, sweep.report()


def test_a_short_window_moves_panels_into_the_tabs_rather_than_off_the_screen(content) -> None:  # type: ignore[no-untyped-def]
    from begin.battle import build_battle
    from begin.presets import load_presets
    from begin.ui.battle_scene import BattleScene
    from begin.ui.hud import TargetPanel, WeaponsPanel

    pygame.init()
    tall = BattleScene(build_battle(content, load_presets()[0].setup()), (1920, 1200), lambda: None)
    assert len(tall.column_panels(tall.col_rect.height)) == 4 and not tall.side_tabs.folded
    short = BattleScene(build_battle(content, load_presets()[0].setup()), (1024, 640), lambda: None)
    shown = short.column_panels(short.col_rect.height)
    assert [type(p) for p in short.side_tabs.folded] == [TargetPanel, WeaponsPanel]
    assert sum(p.min_height for p in shown) + 8 * (len(shown) - 1) <= short.col_rect.height
    short.side_tabs.show(WeaponsPanel)
    assert isinstance(short.side_tabs.tabs[short.side_tabs.active], WeaponsPanel)


def test_the_tours(sweep, content) -> None:  # type: ignore[no-untyped-def]
    from begin.settings import Settings
    from begin.ui.tour_scene import TourScene

    for size in SIZES:
        surf = pygame.display.set_mode(size)
        ts = TourScene(content, Settings(), lambda run: None, lambda: None)
        ts.open()
        for i, t in enumerate(ts.tours):
            ts.tour_i = i
            for page in ("tours", "squadron"):
                ts.page = page
                ts.update(0.1)
                sweep.draw(f"tour {t.id} {page}", ts.draw, surf)
        ts.tour_i, ts.escorts = 0, []
        ts.commission()
        ts.update(0.1)
        sweep.draw("tour ready", ts.draw, surf)
        assert ts.run is not None
        ts.run.state.over = "won"
        ts.page = "end"
        sweep.draw("tour end", ts.draw, surf)
    assert not sweep.found, sweep.report()


def test_every_manual_page_on_a_small_window(sweep, content) -> None:  # type: ignore[no-untyped-def]
    from begin.help.coach import HelpContext
    from begin.help.docs import BUNDLED_DIR, HelpLibrary
    from begin.ui.manual import ManualView
    from begin.ui.widgets import UI

    surf = pygame.display.set_mode((1024, 640))
    lib = HelpLibrary(dirs=(BUNDLED_DIR,))
    view = ManualView(lambda: HelpContext(content), lambda s: None, lambda: None, lib)
    ui = UI()
    rect = surf.get_rect().inflate(-48, -48)
    for tid in lib.topics:
        view.go(tid)
        ui.begin_frame()
        sweep.draw(f"manual {tid}", lambda s: view.draw(s, rect, ui), surf)
    assert not sweep.found, sweep.report()


def test_the_ready_room_keeps_every_button_and_the_officers_on_a_small_window(content) -> None:  # type: ignore[no-untyped-def]
    """Found by the full sweep: at 1024×640 the reinforcements button shrank to '…' and the officers' view vanished."""
    from begin.settings import Settings
    from begin.ui.tour_scene import TourScene

    pygame.init()
    surf = pygame.display.set_mode((1024, 640))
    ts = TourScene(content, Settings(), lambda run: None, lambda: None)
    ts.open()
    ts.tour_i, ts.escorts = 0, []
    ts.commission()
    ts.update(0.1)
    with theme.watching() as ink:
        ts.draw(surf)
    said = [k.text for k in ink if k.kind != "panel"]
    assert "YOUR OFFICERS' VIEW" in said
    assert any(t.startswith(("Request reinforcements", "Reinforcements")) for t in said)
    assert any(t.startswith("Set course") for t in said)
