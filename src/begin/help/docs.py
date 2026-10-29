"""The help library: Markdown topic files with a small front-matter header.

Topics ship in `begin/assets/help/*.md`. Players can edit them, or add
their own, in the user help folder (`~/.begin-remake/help/`, or the folder
named by the BEGIN_HELP_DIR environment variable): a file there with the
same name replaces the bundled one. Files are re-read when they change, so
edits show up the next time the manual opens.

Front matter (all optional except title):

    ---
    title: Torpedoes
    category: Weapons
    aliases: tor, torp, torpedo, fire torpedoes
    summary: One line shown in lists and search results.
    see: fire, lock, load
    order: 20
    ---

Body: Markdown (headings, paragraphs, lists, tables, ``` code blocks,
`inline code`, **bold**, *italic*, > callouts, [[topic]] links). A fenced
block tagged `console` holds example commands the reader can click to try.
`{{name}}` inserts a live block (weapon tables, the coach); see `coach.py`.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path

BUNDLED_DIR = Path(__file__).resolve().parent.parent / "assets" / "help"

CATEGORY_ORDER = ("Getting started", "Coach", "Helm", "Weapons", "Defense", "Sensors and status", "Ship systems",
                  "Allies", "Game")


def user_help_dir() -> Path:
    env = os.environ.get("BEGIN_HELP_DIR")
    if env:
        return Path(env)
    base = os.environ.get("BEGIN_HOME")
    return (Path(base) if base else Path.home() / ".begin-remake") / "help"


@dataclass
class Topic:
    id: str
    title: str
    body: str
    category: str = "Game"
    aliases: tuple[str, ...] = ()
    summary: str = ""
    see: tuple[str, ...] = ()
    order: int = 50
    path: Path | None = None

    @property
    def search_text(self) -> str:
        return f"{self.title} {' '.join(self.aliases)} {self.summary} {self.body}".lower()


@dataclass
class HelpLibrary:
    dirs: tuple[Path, ...] = field(default_factory=lambda: (BUNDLED_DIR, user_help_dir()))
    topics: dict[str, Topic] = field(default_factory=dict)
    _stamp: tuple[tuple[str, float], ...] = ()

    def _files(self) -> dict[str, Path]:
        files: dict[str, Path] = {}
        for d in self.dirs:
            if d.is_dir():
                for p in sorted(d.glob("*.md")):
                    files[p.stem] = p  # later folders (the user's) override bundled topics
        return files

    def refresh(self) -> bool:
        """Reload if any file was added, removed or edited. Returns True when it reloaded."""
        files = self._files()
        stamp = tuple(sorted((str(p), _mtime(p)) for p in files.values()))
        if stamp == self._stamp and self.topics:
            return False
        self._stamp = stamp
        self.topics = {}
        for tid, p in files.items():
            try:
                self.topics[tid] = parse_topic(tid, p.read_text(encoding="utf-8"), p)
            except (OSError, UnicodeDecodeError):
                continue
        return True

    def ordered(self) -> list[Topic]:
        def key(t: Topic) -> tuple[int, int, str]:
            cat = CATEGORY_ORDER.index(t.category) if t.category in CATEGORY_ORDER else len(CATEGORY_ORDER)
            return cat, t.order, t.title.lower()
        return sorted(self.topics.values(), key=key)

    def categories(self) -> list[tuple[str, list[Topic]]]:
        out: list[tuple[str, list[Topic]]] = []
        for t in self.ordered():
            if not out or out[-1][0] != t.category:
                out.append((t.category, []))
            out[-1][1].append(t)
        return out

    def resolve(self, query: str) -> Topic | None:
        """Find the topic for `help <query>`: id, title or alias; then a command prefix; then a word search."""
        self.refresh()
        q = " ".join(query.lower().split())
        if not q:
            return self.topics.get("index")
        for t in self.ordered():
            if q == t.id or q == t.title.lower() or q in t.aliases:
                return t
        # 'help tor' → the verb 'torp' → the topic that lists it as an alias
        from ..console.parser import VERBS, _match

        words = q.split()
        verb = _match(words[0], VERBS)
        if verb is not None:
            for t in self.ordered():
                if verb in t.aliases or verb == t.id:
                    if len(words) > 1:  # 'help fire torpedoes' → the torpedo page if there is one
                        sub = self.resolve(" ".join(words[1:]))
                        if sub is not None and sub.id != "index":
                            return sub
                    return t
        for t in self.ordered():
            if any(a.startswith(q) for a in (t.id, t.title.lower(), *t.aliases)):
                return t
        hits = self.search(q)
        return hits[0] if hits else None

    def search(self, query: str) -> list[Topic]:
        words = query.lower().split()
        if not words:
            return self.ordered()
        scored = []
        for t in self.ordered():
            text = t.search_text
            if all(w in text for w in words):
                head = f"{t.title} {' '.join(t.aliases)}".lower()
                scored.append((-(sum(w in head for w in words) * 10 + sum(text.count(w) for w in words)), t.title, t))
        return [t for *_, t in sorted(scored, key=lambda s: (s[0], s[1]))]


def _mtime(p: Path) -> float:
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


_FRONT = re.compile(r"^---\s*\n(.*?)\n---\s*\n?", re.S)


def parse_topic(tid: str, text: str, path: Path | None = None) -> Topic:
    meta: dict[str, str] = {}
    m = _FRONT.match(text)
    if m:
        for line in m.group(1).splitlines():
            if ":" in line:
                k, v = line.split(":", 1)
                meta[k.strip().lower()] = v.strip()
        text = text[m.end():]

    def lst(v: str) -> tuple[str, ...]:
        v = v.strip().strip("[]")
        return tuple(x.strip().strip("'\"").lower() for x in v.split(",") if x.strip())

    title = meta.get("title") or tid.replace("-", " ").title()
    try:
        order = int(meta.get("order", "50"))
    except ValueError:
        order = 50
    return Topic(tid, title, text.strip("\n"), meta.get("category", "Game"), lst(meta.get("aliases", "")),
                 meta.get("summary", ""), lst(meta.get("see", "")), order, path)


_LIBRARY: HelpLibrary | None = None


def library() -> HelpLibrary:
    global _LIBRARY
    if _LIBRARY is None:
        _LIBRARY = HelpLibrary()
    _LIBRARY.refresh()
    return _LIBRARY


__all__ = ["BUNDLED_DIR", "HelpLibrary", "Topic", "library", "parse_topic", "user_help_dir"]
