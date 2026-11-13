"""The captain's manual [E] (help/book.py, docs/MANUAL.md) must keep up with the game. These fail when something
the manual covers changes and the book isn't rebuilt, or when the game gains a ship, an officer, a power, a battle,
a tour or an order that the manual doesn't mention. Fix: write about it in a help page, then run
`python -m begin.help.book` and commit docs/MANUAL.md with the change."""

from __future__ import annotations

import re

import pytest

from begin.console.vocab import VERBS
from begin.crew.characters import load_officers
from begin.help.book import MANUAL_PATH, build
from begin.help.docs import BUNDLED_DIR, HelpLibrary
from begin.presets import load_presets
from begin.tour.model import load_tours

REBUILD = "docs/MANUAL.md is out of date: run `python -m begin.help.book` and commit the result"


@pytest.fixture(scope="module")
def book(content) -> str:  # type: ignore[no-untyped-def]
    return build(content)


@pytest.fixture(scope="module")
def lib() -> HelpLibrary:
    lib = HelpLibrary(dirs=(BUNDLED_DIR,))
    lib.refresh()
    return lib


def test_the_manual_is_up_to_date(book: str) -> None:
    assert MANUAL_PATH.read_text(encoding="utf-8") == book, REBUILD


def test_every_power_ship_officer_battle_and_tour_is_in_the_manual(book: str, content) -> None:  # type: ignore[no-untyped-def]
    missing = [f.long_name or f.name for f in content.factions.values() if (f.long_name or f.name) not in book]
    missing += [c.name for c in content.classes.values() if c.name not in book]
    missing += [o.name for o in load_officers().values() if o.name not in book]
    missing += [p.title for p in load_presets() if p.title not in book]
    missing += [t.title for t in load_tours(user_dir=None)[0] if t.title not in book]
    assert not missing, f"the manual never mentions {missing}"


def test_every_order_has_a_page_in_the_manual(book: str) -> None:
    missing = [v for v in VERBS if f"| `{v}` |" not in book]
    assert not missing, f"orders missing from the manual's index: {missing}"
    unexplained = re.findall(r"^\| `([a-z]+)` \| [^|]* \| - \|$", book, re.M)
    assert not unexplained, f"orders no help page lists in its aliases: {unexplained}"


def test_every_help_page_is_a_chapter_or_a_section(book: str, lib: HelpLibrary) -> None:
    missing = [t.id for t in lib.topics.values() if f'<a id="topic-{t.id}"></a>' not in book]
    assert not missing


def test_every_link_in_the_manual_lands_somewhere(book: str, lib: HelpLibrary) -> None:
    anchors = set(re.findall(r'<a id="([^"]+)"></a>', book))
    targets = set(re.findall(r"\]\(#([^)]+)\)", book))
    assert not targets - anchors
    assert "{{" not in book and "[[" not in book


def test_help_pages_link_only_to_pages_that_exist(lib: HelpLibrary) -> None:
    broken = []
    for t in lib.topics.values():
        for target in re.findall(r"\[\[([^\]|]+)", t.body):
            if target.strip() not in lib.topics:
                broken.append(f"{t.id} → {target}")
        broken += [f"{t.id} see → {s}" for s in t.see if s not in lib.topics]
    assert not broken, broken


def test_the_chapters_come_first_and_in_order(book: str, lib: HelpLibrary) -> None:
    chapters = [t for t in lib.ordered() if t.category == "Captain's manual"]
    assert len(chapters) >= 9
    positions = [book.index(f'<a id="topic-{t.id}"></a>') for t in chapters]
    assert positions == sorted(positions) and positions[-1] < book.index("# Part Two")
