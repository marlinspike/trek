"""The in-game manual: topic files, lookup, live blocks, layout and the coach."""

from __future__ import annotations

import os
import re
from pathlib import Path

import pytest

from begin.console.parser import VERBS
from begin.help.coach import BLOCKS, HelpContext, expand
from begin.help.docs import BUNDLED_DIR, HelpLibrary, parse_topic


@pytest.fixture()
def lib() -> HelpLibrary:
    lib = HelpLibrary(dirs=(BUNDLED_DIR,))
    lib.refresh()
    return lib


def test_every_bundled_topic_parses(lib: HelpLibrary) -> None:
    assert len(lib.topics) >= 30
    for t in lib.topics.values():
        assert t.title and t.summary and t.body.strip(), t.id
        assert not t.body.startswith("---"), t.id


def test_every_command_has_a_page(lib: HelpLibrary) -> None:
    covered = {a for t in lib.topics.values() for a in (t.id, *t.aliases)}
    assert [v for v in VERBS if v not in covered] == []


def test_links_and_see_also_point_at_real_pages(lib: HelpLibrary) -> None:
    for t in lib.topics.values():
        for link in re.findall(r"\[\[([^\]|]+)", t.body):
            assert link in lib.topics, f"{t.id} links to missing page {link}"
        for s in t.see:
            assert s in lib.topics, f"{t.id} sees missing page {s}"


@pytest.mark.parametrize("query, page", [
    ("", "index"), ("tor", "torpedoes"), ("torp", "torpedoes"), ("fire", "fire"), ("fire torpedoes", "torpedoes"),
    ("fir pro", "probes"), ("phasers", "phasers"), ("coach", "coach"), ("helm", "helm"), ("stop", "helm"),
    ("drop", "shields"), ("self", "destruct"), ("beam", "transport"), ("tell", "tell"), ("key", "keys"),
    ("dmg", "status"), ("library", "library"), ("pause", "time"), ("which torpedo", "weapons-guide"),
])
def test_help_queries_find_the_right_page(lib: HelpLibrary, query: str, page: str) -> None:
    t = lib.resolve(query)
    assert t is not None and t.id == page


def test_search_finds_words_in_the_body(lib: HelpLibrary) -> None:
    hits = [t.id for t in lib.search("proximity")]
    assert "torpedoes" in hits


def test_user_pages_override_and_reload(tmp_path: Path) -> None:
    lib = HelpLibrary(dirs=(BUNDLED_DIR, tmp_path))
    lib.refresh()
    assert lib.topics["torpedoes"].path is not None and lib.topics["torpedoes"].path.parent == BUNDLED_DIR
    p = tmp_path / "torpedoes.md"
    p.write_text("---\ntitle: My torpedoes\naliases: tor\n---\nMine.\n", encoding="utf-8")
    assert lib.refresh()
    assert lib.resolve("tor").title == "My torpedoes"  # type: ignore[union-attr]
    (tmp_path / "brand-new.md").write_text("---\ntitle: Brand new\n---\nHello.\n", encoding="utf-8")
    os.utime(tmp_path / "brand-new.md")
    assert lib.refresh() and "brand-new" in lib.topics
    assert not lib.refresh()  # nothing changed


def test_front_matter_lists() -> None:
    t = parse_topic("x", "---\ntitle: X\naliases: [a, 'B', c d]\nsee: y\norder: 3\n---\nBody")
    assert t.aliases == ("a", "b", "c d") and t.see == ("y",) and t.order == 3 and t.body == "Body"


def test_live_blocks_expand_without_a_battle(content) -> None:  # type: ignore[no-untyped-def]
    ctx = HelpContext(content)
    for name in BLOCKS:
        out = expand("{{" + name + "}}", ctx)
        assert out.strip() and "{{" not in out, name
    table = expand("{{torpedo_table}}", ctx)
    for t in content.torpedoes.values():
        assert t.name in table or t.special
    assert expand("{{nonsense}}", ctx) == "{{nonsense}}"


def test_coach_reads_a_live_battle(content) -> None:  # type: ignore[no-untyped-def]
    from begin.battle import build_battle
    from begin.presets import load_presets

    b = build_battle(content, load_presets()[0].setup())
    side = b.world.ships[b.player_ship_id].side
    ctx = HelpContext(content, b.world.observe(side), b.world.ships[b.player_ship_id])
    advice = expand("{{coach}}", ctx)
    assert "Coach" in advice or "**" in advice
    assert "```console" in advice  # every tip carries a command to try
    assert expand("{{my_weapons}}", ctx).strip()


# ------------------------------------------------------------------ rendering (headless pygame)

pygame = pytest.importorskip("pygame")
os.environ.setdefault("SDL_VIDEODRIVER", "dummy")


@pytest.fixture()
def surf():  # type: ignore[no-untyped-def]
    pygame.init()
    from begin.ui import theme

    theme.font.cache_clear()
    theme._fallback.cache_clear()
    return pygame.display.set_mode((1400, 860))


def test_markdown_layout_has_links_and_examples(surf) -> None:  # type: ignore[no-untyped-def]
    from begin.ui import markdown

    blocks = markdown.parse("# T\n\nSee [[fire|Fire]] and **bold**.\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n"
                            "```console\nfire all\n```\n\n> **Tip** text\n\n- item\n1. one\n")
    kinds = [b.kind for b in blocks]
    for k in ("h1", "p", "table", "code", "quote", "li", "ol"):
        assert k in kinds
    lay = markdown.layout(blocks, 700)
    assert lay.height > 0
    assert any(h.kind == "link" and h.value == "fire" for h in lay.hots)
    assert any(h.kind == "try" and h.value == "fire all" for h in lay.hots)
    markdown.draw(surf, lay, (10, 10), surf.get_rect())


def test_every_page_draws(surf, content) -> None:  # type: ignore[no-untyped-def]
    from begin.ui.manual import ManualView
    from begin.ui.widgets import UI

    lib = HelpLibrary(dirs=(BUNDLED_DIR,))
    view = ManualView(lambda: HelpContext(content), lambda s: None, lambda: None, lib)
    ui = UI()
    rect = pygame.Rect(24, 24, 1352, 812)
    for tid in list(lib.topics):
        view.go(tid)
        ui.begin_frame()
        view.draw(surf, rect, ui)
        view.scroll = 1e9
        view.draw(surf, rect, ui)


def test_help_command_opens_the_manual_in_battle(surf, content) -> None:  # type: ignore[no-untyped-def]
    from begin.battle import build_battle
    from begin.presets import load_presets
    from begin.ui.battle_scene import BattleScene

    sc = BattleScene(build_battle(content, load_presets()[0].setup()), surf.get_size(), lambda: None)
    sc.run_console("man tor")
    assert sc.overlay == "manual" and sc.manual.topic_id == "torpedoes"
    sc.draw(surf)
    tried: list[str] = []
    sc.manual.on_try = tried.append
    sc.manual.go("coach")
    sc.draw(surf)
    sc.manual.back()
    assert sc.manual.topic_id == "torpedoes"
    sc.run_console("help")
    assert sc.manual.topic_id == "index"


def test_table_cells_keep_links_and_code_whole() -> None:
    from begin.ui.markdown import _cells

    assert _cells(" [[phasers|Phasers]] | `a|b` | x ") == [" [[phasers|Phasers]] ", " `a|b` ", " x "]


def test_the_coach_and_manual_open_from_the_main_menu(content) -> None:  # type: ignore[no-untyped-def]
    from begin.ui.menu_scene import MenuScene
    from begin.ui.settings import Settings

    pygame.init()
    surf = pygame.display.set_mode((1400, 860))
    menu = MenuScene(content, Settings(), lambda setup: None, lambda: None)
    menu.draw(surf)
    menu.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_c, mod=0, unicode="c"))
    menu.handle(pygame.event.Event(pygame.TEXTINPUT, text="c"))      # the same key press: not a search
    assert menu.page == "manual" and menu.manual is not None and menu.manual.topic_id == "coach"
    assert menu.manual.search == ""
    menu.draw(surf)
    body = menu.manual._page_text(menu.manual.topic, HelpContext(content))   # type: ignore[arg-type]
    assert "training run" in body and "fire all torpedoes" in body and "{{" not in body
    menu.handle(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_ESCAPE, mod=0, unicode=""))
    assert menu.page == "main"
