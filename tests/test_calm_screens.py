"""The deep sweep of the screens (2026-11-13): words never drawn over other words, a log that reads to the end of
each line, a map that opens on the enemy, and a menu that doesn't end the game on one stray Esc."""

from __future__ import annotations

import os

import pytest

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
pygame = pytest.importorskip("pygame")

from begin.ui import theme  # noqa: E402

SIZES = [(1024, 640), (1280, 800), (1920, 1080)]
COVERS = 400       # a panel at least this wide drawn later is a page laid over what was under it


def collisions(ink: list[theme.Ink], surf: pygame.Surface, skip: pygame.Rect | None = None) -> list[str]:
    """Lines of text drawn over other lines on `surf`. Text a later page covers, text a scrolling view has cut
    (it is half out of its clip) and text inside `skip` (the battle map, which places its own names) don't count."""
    shown: list[theme.Ink] = []
    for k in ink:
        if k.surf is not surf:
            continue
        if k.kind == "panel":
            if k.rect.width >= COVERS:
                shown = [t for t in shown if not t.rect.colliderect(k.rect)]
            continue
        if not k.text.strip() or k.rect.width <= 0 or not k.clip.contains(k.rect):
            continue
        if skip is not None and skip.colliderect(k.rect):
            continue
        shown.append(k)
    bad = []
    for i, a in enumerate(shown):
        for b in shown[i + 1:]:
            o = a.rect.clip(b.rect)
            if o.width > 3 and o.height > 4 and a.text != b.text:
                bad.append(f"{a.text[:40]!r} {tuple(a.rect)} under {b.text[:40]!r} {tuple(b.rect)}")
    return bad


@pytest.fixture()
def fresh():  # type: ignore[no-untyped-def]
    pygame.init()
    theme.font.cache_clear()
    theme._fallback.cache_clear()


def test_no_words_drawn_over_words_on_the_menus_settings_and_tours(fresh, content) -> None:  # type: ignore[no-untyped-def]
    from begin.settings import Settings
    from begin.ui.menu_scene import MenuScene
    from begin.ui.tour_scene import TourScene

    found: dict[str, str] = {}
    for size in SIZES:
        surf = pygame.display.set_mode(size)
        m = MenuScene(content, Settings(), lambda s: None, lambda: None)
        pages = [("main", None), ("custom", None), ("about", None), ("presets", None)]
        for page, _ in pages:
            m.page = page
            with theme.watching() as ink:
                m.draw(surf)
            for b in collisions(ink, surf):
                found.setdefault(f"menu {page}", f"{size}: {b}")
        m.open_settings()
        for sec in m.hub.sections:
            m.hub.go(sec.key)
            with theme.watching() as ink:
                m.draw(surf)
            for b in collisions(ink, surf):
                found.setdefault(f"settings {sec.key}", f"{size}: {b}")
        ts = TourScene(content, Settings(), lambda run: None, lambda: None)
        ts.open()
        for i, t in enumerate(ts.tours):
            ts.tour_i = i
            for page in ("tours", "squadron"):
                ts.page = page
                ts.update(0.1)
                ts.draw(surf)                     # the chart learns where the panels and buttons are
                with theme.watching() as ink:
                    ts.draw(surf)
                for b in collisions(ink, surf):
                    found.setdefault(f"tour {t.id} {page}", f"{size}: {b}")
    assert not found, "\n".join(f"{k}: {v}" for k, v in sorted(found.items()))


def test_no_words_drawn_over_words_on_the_battle_screen_and_its_pages(fresh, content) -> None:  # type: ignore[no-untyped-def]
    from begin.battle import build_battle
    from begin.presets import load_presets
    from begin.ui.battle_scene import BattleScene

    presets = {p.id: p for p in load_presets()}
    found: dict[str, str] = {}
    for size in SIZES:
        surf = pygame.display.set_mode(size)
        for pid in ("fleet-action", "borg-cube"):
            sc = BattleScene(build_battle(content, presets[pid].setup()), size, lambda: None)
            sc.paused = False
            for _ in range(300):
                sc.update(1 / 30)
            sc.paused = True
            sc.overlay = None
            with theme.watching() as ink:
                sc.draw(surf)
            for b in collisions(ink, surf, skip=sc.map_rect):
                found.setdefault(f"{pid} battle", f"{size}: {b}")
            for overlay in ("help", "damage", "scan", "debrief", "debrief_details"):
                sc.overlay = overlay
                with theme.watching() as ink:
                    sc.draw(surf)
                modal = [k.rect for k in ink if k.kind == "panel" and k.rect.width >= COVERS]
                page = modal[-1] if modal else None
                inside = [k for k in ink if k.kind == "panel" or page is None or page.contains(k.rect)]
                for b in collisions(inside, surf):
                    found.setdefault(f"{pid} {overlay}", f"{size}: {b}")
            sc.overlay = None
            sc.toggle_counsel(True)
            with theme.watching() as ink:
                sc.draw(surf)
            for b in collisions(ink, surf):
                if "PAUSED" in b:          # the banner keeps clear of the counsel
                    found.setdefault(f"{pid} counsel", f"{size}: {b}")
            sc.toggle_counsel(False)
    assert not found, "\n".join(f"{k}: {v}" for k, v in sorted(found.items()))


def test_the_log_wraps_a_long_line_instead_of_cutting_it(fresh, content) -> None:  # type: ignore[no-untyped-def]
    from begin.battle import build_battle
    from begin.presets import load_presets
    from begin.ui.battle_scene import BattleScene

    surf = pygame.display.set_mode((1024, 640))
    sc = BattleScene(build_battle(content, load_presets()[0].setup()), (1024, 640), lambda: None)
    sc.overlay = None
    end = "and this is the very end of the report"
    sc._log("Spock: " + "a long report on the state of the ship, " * 4 + end, theme.TEXT, channel="bridge")
    with theme.watching() as ink:
        sc.draw(surf)
    shown = " ".join(k.text for k in ink if k.kind == "text" and sc.bottom_rect.contains(k.rect))
    assert end in shown and "…" not in shown


def test_one_esc_on_the_main_menu_asks_and_a_second_quits(fresh, content) -> None:  # type: ignore[no-untyped-def]
    from begin.settings import Settings
    from begin.ui.menu_scene import MenuScene

    pygame.display.set_mode((1280, 800))
    quit_ = []
    m = MenuScene(content, Settings(), lambda s: None, lambda: quit_.append(1))
    esc = pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode="\x1b")
    m.handle(esc)
    assert not quit_
    m.update(5.0)                  # a long pause: the first press has lapsed
    m.handle(esc)
    assert not quit_
    m.update(0.5)
    m.handle(esc)
    assert quit_


def test_settings_keep_back_on_a_short_window_and_answer_number_keys(fresh, content) -> None:  # type: ignore[no-untyped-def]
    from begin.settings import Settings
    from begin.ui.menu_scene import MenuScene

    surf = pygame.display.set_mode((1024, 640))
    m = MenuScene(content, Settings(), lambda s: None, lambda: None)
    m.open_settings()
    m.draw(surf)
    back = [h.rect for h in m.ui.hotspots if h.tooltip.startswith("Back to the main menu")]
    assert back and surf.get_rect().contains(back[0])
    m.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_3, mod=0, unicode="3"))
    assert m.hub.section == m.hub.sections[2].key


def test_the_map_opens_with_the_nearest_enemy_in_view(fresh, content) -> None:  # type: ignore[no-untyped-def]
    from begin.battle import build_battle
    from begin.presets import load_presets
    from begin.ui.battle_scene import BattleScene

    presets = {p.id: p for p in load_presets()}
    for pid in ("pirate-hunt", "borg-cube", "border-incident"):
        sc = BattleScene(build_battle(content, presets[pid].setup()), (1280, 800), lambda: None)
        sc.view.draw(pygame.display.set_mode((1280, 800)), sc.obs, None, sc.now, 1.0, sc.player_id, None, None, None)
        foes = [c for c in sc.obs.contacts().values() if c.side != sc.obs.side and c.id in sc.now.ships]
        me = sc.now.ships[sc.player_id]
        near = min(foes, key=lambda c: (sc.now.ships[c.id][0] - me[0]) ** 2 + (sc.now.ships[c.id][1] - me[1]) ** 2)
        x, y = sc.cam.to_screen(*sc.now.ships[near.id][:2])
        assert sc.map_rect.collidepoint(x, y), pid


def test_the_engineer_says_nothing_of_a_scratch_and_grows_grave_only_below_half(content) -> None:  # type: ignore[no-untyped-def]
    from begin.crew.chatter import damage_words, hull_band

    assert hull_band(1.0) == hull_band(0.99) == hull_band(0.76) == 3
    assert hull_band(0.74) == 2 and hull_band(0.3) == 1 and hull_band(0.0) == 0

    class Sub:
        def __init__(self, label: str, damage: int, destroyed: bool = False) -> None:
            self.label, self.damage, self.destroyed = label, damage, destroyed

    words = damage_words([Sub("Reactor 7", 100, True), Sub("Phaser bank 6", 26)])  # type: ignore[list-item]
    assert words == "reactor 7 is destroyed and phaser bank 6 is 26% damaged"


# ------------------------------------------------------------------ calm big fights (2026-11-14)

def test_names_on_a_crowded_map_never_cover_each_other(fresh, content) -> None:  # type: ignore[no-untyped-def]
    from begin.battle import build_battle
    from begin.presets import load_presets
    from begin.ui.battle_scene import BattleScene

    presets = {p.id: p for p in load_presets()}
    found: dict[str, str] = {}
    seen = 0
    for size in SIZES:
        surf = pygame.display.set_mode(size)
        sc = BattleScene(build_battle(content, presets["fleet-action"].setup()), size, lambda: None)
        sc.overlay = None
        sc.paused = False
        for step in range(900):
            sc.update(1 / 30)
            if step % 150 != 149:
                continue
            for reach in (6000, 15000, 40000):           # close in, the whole fight, and far out
                sc.set_display_range(reach)
                sc.draw(surf)
                with theme.watching() as ink:
                    sc.draw(surf)
                names = [k for k in ink if k.kind == "label" and sc.map_rect.contains(k.rect)]
                seen = max(seen, len(names))
                for i, a in enumerate(names):
                    for b in names[i + 1:]:
                        o = a.rect.clip(b.rect)
                        if o.width > 2 and o.height > 2:
                            found.setdefault(f"{size} step {step} range {reach}",
                                             f"{a.text!r} {tuple(a.rect)} over {b.text!r} {tuple(b.rect)}")
    assert seen >= 8, seen              # it was a crowded map
    assert not found, "\n".join(f"{k}: {v}" for k, v in sorted(found.items()))


def test_a_name_keeps_its_side_and_the_ones_that_matter_always_show() -> None:
    from begin.ui.labels import Ask, Placer

    area = pygame.Rect(0, 0, 400, 300)
    p = Placer()
    asks = [Ask(1, 200, 150, 20, 60, 14, (0.0, 0.0), True), Ask(2, 205, 152, 20, 60, 14, (3.0, 500.0)),
            Ask(3, 203, 149, 20, 60, 14, (3.0, 900.0))]
    first = p.place(asks, area, [(1, 200, 150, 16), (2, 205, 152, 16), (3, 203, 149, 16)])
    assert set(first) == {1, 2, 3}
    rects = [s.rect for s in first.values()]
    assert all(not a.colliderect(b) for i, a in enumerate(rects) for b in rects[i + 1:])
    again = p.place(asks, area, [(1, 200, 150, 16), (2, 205, 152, 16), (3, 203, 149, 16)])
    assert {k: s.slot for k, s in again.items()} == {k: s.slot for k, s in first.items()}    # no hopping about
    # a pile of names on one point: the low ones give way, ours never does
    pile = [Ask(i, 200, 150, 10, 120, 14, (3.0, float(i)), i == 0) for i in range(40)]
    out = Placer().place(pile, area, [])
    assert 0 in out and len(out) < 40
    assert Placer().place([Ask(9, 900, 150, 10, 60, 14)], area, []) == {}      # off the map: no half a name


def test_distant_names_fade_only_in_a_crowd() -> None:
    from begin.ui.labels import FADE_MAX, fade

    assert fade(4, 50000.0, False, 8000.0, 20000.0) == 0.0          # a quiet map: nothing fades
    assert fade(20, 50000.0, True, 8000.0, 20000.0) == 0.0          # ours and the target never do
    assert fade(20, 3000.0, False, 8000.0, 20000.0) == 0.0          # nor anything close
    assert fade(20, 50000.0, False, 8000.0, 20000.0) == FADE_MAX


def test_one_card_on_the_map_at_a_time() -> None:
    from begin.ui.battle.stage import MISSION_NEWS, Stage, news_key

    st = Stage()
    news = news_key("open", "rescue", "Close to 3,000 of her (8,400 now).", "dim")
    assert st.pick(1.0, news=news, subtitle=True) == "mission"           # the mission's news first
    assert not st.subtitle                                                # the line waits in the log
    assert st.pick(1.1, news=news, proposal=True, subtitle=True) == "proposal"
    assert st.pick(1.2, news=news, comms=True, urgent=True) == "comms"
    assert st.pick(1.3, news=news, urgent=True) == "urgent" and st.subtitle
    t = 1.3
    while st.pick(t, news=news, subtitle=True) == "mission":              # the card's own turn runs out
        t += 0.2
    assert MISSION_NEWS - 1 < t - 1.3 < MISSION_NEWS + 1 and st.shown == "subtitle"
    closer = news_key("open", "rescue", "Close to 3,000 of her (6,100 now).", "dim")
    assert st.pick(t + 0.1, news=closer, subtitle=True) == "subtitle"     # a closing range isn't news
    assert st.pick(t + 0.2, news=closer, hover=True) == "mission"         # resting the pointer on the strip is
    assert st.pick(t + 0.3, counsel=True, proposal=True) == "counsel"
