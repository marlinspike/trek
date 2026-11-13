"""The captain's manual as one book [E]: docs/MANUAL.md, built from the help library and the game's data.

Nothing in the book is written twice. Part One is the help pages in the "Captain's manual" category (the
chapters: the powers, the crew, how a battle works, tactics). Part Two is every other help page, by category.
The appendices are the live tables (ships, weapons, battles, tours, every order). The in-game manual shows the same
pages, so the book and the game never disagree.

Only what ships with the game goes in: the bundled help pages, the shipped officers and tours. A player's own
pages in config/help/ never leak into the book.

    python -m begin.help.book            # rewrite docs/MANUAL.md
    python -m begin.help.book --check    # exit 1 if docs/MANUAL.md is out of date (tests/test_manual.py does this)

Change a help page, an officer, a ship, a weapon, a battle, a tour or a console verb, run it, and commit the
result. The test fails until you do.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

from ..content.loader import default_content
from ..content.schema import ContentDB
from .coach import HelpContext, expand
from .docs import BUNDLED_DIR, HelpLibrary, Topic

MANUAL_PATH = Path(__file__).resolve().parents[3] / "docs" / "MANUAL.md"
CHAPTERS = "Captain's manual"
TITLE = "BEGIN : TREK: The Captain's Manual"

APPENDICES: tuple[tuple[str, str, str], ...] = (
    ("ships", "Ship classes", "class_table"),
    ("torpedoes", "Torpedoes", "torpedo_table"),
    ("probes", "Probes", "probe_table"),
    ("phaser-falloff", "Phaser damage by range", "phaser_falloff"),
    ("orders", "Every order the console knows", "order_index"),
)

_LINK = re.compile(r"\[\[([^\]|]+)(?:\|([^\]]+))?\]\]")
_COLOUR = re.compile(r"\{#[0-9A-Fa-f]{6} ([^}]*)\}")
_HEADING = re.compile(r"^(#{1,4}) ", re.M)
_FENCE = re.compile(r"^```console$", re.M)


def anchor(topic_id: str) -> str:
    return f"topic-{topic_id}"


def _links(md: str, lib: HelpLibrary) -> str:
    """[[topic|text]] becomes a link inside the book; an unknown topic is left as plain text."""
    def sub(m: re.Match[str]) -> str:
        tid, text = m.group(1).strip(), m.group(2)
        t = lib.topics.get(tid)
        if t is None:
            return text or tid
        return f"[{text or t.title}](#{anchor(t.id)})"
    return _LINK.sub(sub, md)


def _page(t: Topic, lib: HelpLibrary, ctx: HelpContext, depth: int) -> str:
    """One help page as a section of the book, its own headings pushed down under the page's title."""
    body = expand(t.body, ctx)
    body = _COLOUR.sub(lambda m: m.group(1), body)          # the in-game colour swatches, as plain words
    body = _FENCE.sub("```text", body)
    body = _HEADING.sub(lambda m: "#" * min(6, len(m.group(1)) + depth - 1) + " ", body)
    body = _links(body, lib)
    head = "#" * depth
    out = [f'<a id="{anchor(t.id)}"></a>', "", f"{head} {t.title}", ""]
    if t.summary:
        out += [f"*{t.summary}*", ""]
    out += [body.strip(), ""]
    if t.see:
        see = [f"[{lib.topics[s].title}](#{anchor(s)})" for s in t.see if s in lib.topics]
        if see:
            out += [f"See also: {', '.join(see)}.", ""]
    return "\n".join(out)


def build(content: ContentDB | None = None) -> str:
    """The whole book, as Markdown."""
    content = content or default_content()
    lib = HelpLibrary(dirs=(BUNDLED_DIR,))
    lib.refresh()
    ctx = HelpContext(content)
    chapters = [t for t in lib.ordered() if t.category == CHAPTERS]
    groups = [(cat, ts) for cat, ts in lib.categories() if cat != CHAPTERS]

    toc = ["## Contents", "", "**Part One: Command**", ""]
    toc += [f"{i}. [{t.title}](#{anchor(t.id)})" for i, t in enumerate(chapters, 1)]
    toc += ["", "**Part Two: The ship's manual**", ""]
    for cat, ts in groups:
        toc.append(f"- {cat}: " + ", ".join(f"[{t.title}](#{anchor(t.id)})" for t in ts))
    toc += ["", "**Appendices**", ""]
    toc += [f"- [{title}](#appendix-{aid})" for aid, title, _ in APPENDICES]

    out = [
        f"# {TITLE}",
        "",
        "> This manual is built from the game itself: the same pages the in-game manual shows (press **H**), and "
        "tables drawn from the game's own data. When the game changes, so does this book. Regenerate it with "
        "`python -m begin.help.book`.",
        "",
        *toc,
        "",
        "# Part One: Command",
        "",
    ]
    for t in chapters:
        out.append(_page(t, lib, ctx, 2))
    out += ["# Part Two: The ship's manual", ""]
    for cat, ts in groups:
        out += [f"## {cat}", ""]
        for t in ts:
            out.append(_page(t, lib, ctx, 3))
    out += ["# Appendices", ""]
    from .coach import BLOCKS

    for aid, title, block in APPENDICES:
        table = _links(_COLOUR.sub(lambda m: m.group(1), BLOCKS[block](ctx)), lib)
        out += [f'<a id="appendix-{aid}"></a>', "", f"## {title}", "", table, ""]
    return "\n".join(out).rstrip() + "\n"


def main(argv: list[str] | None = None) -> int:
    args = sys.argv[1:] if argv is None else argv
    text = build()
    if "--check" in args:
        current = MANUAL_PATH.read_text(encoding="utf-8") if MANUAL_PATH.exists() else ""
        if current != text:
            print(f"{MANUAL_PATH} is out of date: run `python -m begin.help.book`.")
            return 1
        print("The manual is up to date.")
        return 0
    MANUAL_PATH.write_text(text, encoding="utf-8")
    print(f"Wrote {MANUAL_PATH} ({len(text.splitlines()):,} lines).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = ["MANUAL_PATH", "anchor", "build", "main"]
