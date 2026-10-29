"""A small Markdown renderer for the in-game manual.

Supports what the help pages use: headings, paragraphs, bullet and numbered
lists, tables, fenced code (```console blocks become clickable examples),
`---` rules, `> **Tip**` style callouts, and inline `code`, **bold**,
*italic*, [[topic]] / [[topic|label]] links, and {#RRGGBB coloured text} (for colour legends).

`layout()` turns text into positioned draw operations for a given width;
the manual caches it and only redraws, so scrolling stays cheap.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field

import pygame

from . import theme

BODY = 14
LINE = 22


@dataclass
class Span:
    text: str
    bold: bool = False
    italic: bool = False
    code: bool = False
    link: str | None = None
    color: tuple[int, int, int] | None = None


@dataclass
class Block:
    kind: str                    # h1 h2 h3 p li ol code table quote rule
    spans: list[Span] = field(default_factory=list)
    lines: list[str] = field(default_factory=list)       # code
    rows: list[list[list[Span]]] = field(default_factory=list)  # table cells
    lang: str = ""
    level: int = 0
    number: int = 0
    tone: str = ""


_INLINE = re.compile(r"(\{#[0-9A-Fa-f]{6} [^}]+\}|`[^`]+`|\*\*[^*]+\*\*|\[\[[^\]]+\]\]|(?<![*\w])\*[^*\s][^*]*\*(?!\*))")


def inline(text: str) -> list[Span]:
    out: list[Span] = []
    pos = 0
    for m in _INLINE.finditer(text):
        if m.start() > pos:
            out.append(Span(text[pos:m.start()]))
        tok = m.group(0)
        if tok.startswith("{#"):
            hexa = tok[2:8]
            out.append(Span(tok[9:-1], bold=True,
                            color=(int(hexa[0:2], 16), int(hexa[2:4], 16), int(hexa[4:6], 16))))
        elif tok.startswith("`"):
            out.append(Span(tok[1:-1], code=True))
        elif tok.startswith("**"):
            out.extend(Span(s.text, bold=True, code=s.code, link=s.link) for s in inline(tok[2:-2]))
        elif tok.startswith("[["):
            inner = tok[2:-2]
            target, _, label = inner.partition("|")
            out.append(Span(label or target, link=target.strip().lower()))
        else:
            out.append(Span(tok[1:-1], italic=True))
        pos = m.end()
    if pos < len(text):
        out.append(Span(text[pos:]))
    return out


def _cells(row: str) -> list[str]:
    """Split a table row on '|', except inside [[link|label]] and `code`."""
    out, cur, depth, code = [], "", 0, False
    i = 0
    while i < len(row):
        ch = row[i]
        if row.startswith("[[", i) and not code:
            depth += 1
            cur += "[["
            i += 2
            continue
        if row.startswith("]]", i) and depth and not code:
            depth -= 1
            cur += "]]"
            i += 2
            continue
        if ch == "`":
            code = not code
        if ch == "|" and not depth and not code:
            out.append(cur)
            cur = ""
        else:
            cur += ch
        i += 1
    out.append(cur)
    return out


def parse(text: str) -> list[Block]:
    blocks: list[Block] = []
    lines = text.splitlines()
    i = 0
    para: list[str] = []

    def flush() -> None:
        if para:
            blocks.append(Block("p", inline(" ".join(s.strip() for s in para))))
            para.clear()

    while i < len(lines):
        raw = lines[i]
        line = raw.rstrip()
        s = line.strip()
        if s.startswith("```"):
            flush()
            lang = s[3:].strip().lower()
            code: list[str] = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i].rstrip())
                i += 1
            blocks.append(Block("code", lines=code, lang=lang))
            i += 1
            continue
        if not s:
            flush()
        elif s.startswith("#"):
            flush()
            level = min(3, len(s) - len(s.lstrip("#")))
            blocks.append(Block(f"h{level}", inline(s[level:].strip())))
        elif s in ("---", "***"):
            flush()
            blocks.append(Block("rule"))
        elif s.startswith("|"):
            flush()
            rows: list[list[list[Span]]] = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in _cells(lines[i].strip().strip("|"))]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append([inline(c) for c in cells])
                i += 1
            blocks.append(Block("table", rows=rows))
            continue
        elif s.startswith(">"):
            flush()
            q: list[str] = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                q.append(lines[i].strip()[1:].strip())
                i += 1
            text_q = " ".join(q)
            m = re.match(r"\*\*(\w+)\*\*", text_q)
            tone = m.group(1).lower() if m else "note"
            blocks.append(Block("quote", inline(text_q), tone=tone))
            continue
        elif re.match(r"^\s*[-*] ", line):
            flush()
            indent = (len(line) - len(line.lstrip())) // 2
            item = [line.lstrip()[2:]]
            while i + 1 < len(lines) and lines[i + 1].startswith("  " * (indent + 1)) and lines[i + 1].strip() \
                    and not re.match(r"^\s*([-*]|\d+\.) ", lines[i + 1]):
                i += 1
                item.append(lines[i].strip())
            blocks.append(Block("li", inline(" ".join(item)), level=indent))
        elif re.match(r"^\s*\d+\. ", line):
            flush()
            n, _, rest = line.strip().partition(". ")
            blocks.append(Block("ol", inline(rest), number=int(n)))
        else:
            para.append(s)
        i += 1
    flush()
    return blocks


# ------------------------------------------------------------------ layout

@dataclass
class Op:
    kind: str                        # text rect line
    rect: pygame.Rect
    text: str = ""
    color: theme.Color = theme.TEXT
    size: int = BODY
    family: str = "ui"
    weight: str = "regular"
    radius: int = 0
    width: int = 0


@dataclass
class Hot:
    rect: pygame.Rect
    kind: str        # link | try
    value: str


@dataclass
class Layout:
    ops: list[Op]
    hots: list[Hot]
    height: int
    anchors: dict[str, int]


TONES = {
    "tip": theme.CAUTION, "coach": theme.GOOD, "note": theme.ALLY, "warning": theme.ALERT, "example": theme.FRIEND,
    "begin": theme.UNKNOWN,
}


def _style(span: Span, base_size: int, base_weight: str, base_color: theme.Color) -> tuple[int, str, str, theme.Color]:
    if span.code:
        return base_size - 1, "mono", "regular", theme.PHASER_FRIEND
    if span.link:
        return base_size, "ui", "medium", theme.FRIEND
    weight = "semibold" if span.bold else base_weight
    color = theme.TEXT if span.bold and base_color == theme.TEXT_DIM else base_color
    return base_size, "ui", weight, span.color or color


def _flow(spans: list[Span], x0: int, y: int, width: int, ops: list[Op], hots: list[Hot], size: int = BODY,
          weight: str = "regular", color: theme.Color = theme.TEXT, line_h: int = LINE) -> int:
    """Word-wrap spans from (x0, y) within width; returns the y below the last line."""
    x = x0
    right = x0 + width
    for span in spans:
        sz, fam, wt, col = _style(span, size, weight, color)
        words = re.split(r"(\s+)", span.text)
        if span.code and theme.text_width(span.text, sz, fam, wt) + 8 <= width:
            words = [span.text]  # keep a short command on one chip
        for w in words:
            if not w:
                continue
            if w.isspace():
                if x > x0:
                    sw = theme.text_width(" ", sz, fam, wt)
                    if span.link:
                        ops.append(Op("line", pygame.Rect(x, y + (line_h - sz - 6) // 2 + sz + 4, sw, 1),
                                      color=theme.FRIEND_DIM))
                    x += sw
                continue
            ww = theme.text_width(w, sz, fam, wt)
            pad = 4 if span.code else 0  # room for the code chip on both sides
            if x + ww + 2 * pad > right and x > x0:
                x = x0
                y += line_h
            x += pad
            r = pygame.Rect(x, y + (line_h - sz - 6) // 2, ww, sz + 6)
            if span.code:
                ops.append(Op("rect", r.inflate(6, 0), color=theme.BG_INPUT, radius=3))
            ops.append(Op("text", r, w, col, sz, fam, wt))
            if span.link:
                ops.append(Op("line", pygame.Rect(r.x, r.bottom - 2, ww, 1), color=theme.FRIEND_DIM))
                hots.append(Hot(r, "link", span.link))
            x += ww + pad
    return y + line_h


def layout(blocks: list[Block], width: int) -> Layout:
    ops: list[Op] = []
    hots: list[Hot] = []
    anchors: dict[str, int] = {}
    y = 0
    for b in blocks:
        if b.kind in ("h1", "h2", "h3"):
            size = {"h1": 26, "h2": 19, "h3": 15}[b.kind]
            color = {"h1": theme.TEXT, "h2": theme.FRIEND, "h3": theme.CAUTION}[b.kind]
            y += {"h1": 4, "h2": 18, "h3": 10}[b.kind]
            anchors["".join(s.text for s in b.spans).strip().lower()] = y
            y = _flow(b.spans, 0, y, width, ops, hots, size, "semibold", color, size + 12)
            if b.kind == "h2":
                ops.append(Op("line", pygame.Rect(0, y - 4, width, 1), color=theme.BORDER))
                y += 6
        elif b.kind == "p":
            y = _flow(b.spans, 0, y, width, ops, hots) + 8
        elif b.kind == "li":
            ind = 18 + b.level * 20
            ops.append(Op("rect", pygame.Rect(ind - 11, y + LINE // 2 - 2, 5, 5), color=theme.FRIEND_DIM, radius=2))
            y = _flow(b.spans, ind, y, width - ind, ops, hots) + 2
        elif b.kind == "ol":
            ops.append(Op("text", pygame.Rect(0, y + 2, 20, LINE), f"{b.number}.", theme.FRIEND, BODY, "mono"))
            y = _flow(b.spans, 26, y, width - 26, ops, hots) + 2
        elif b.kind == "rule":
            y += 8
            ops.append(Op("line", pygame.Rect(0, y, width, 1), color=theme.BORDER))
            y += 12
        elif b.kind == "quote":
            col = TONES.get(b.tone, theme.ALLY)
            sub_ops: list[Op] = []
            sub_hots: list[Hot] = []
            h = _flow(b.spans, 18, y + 10, width - 30, sub_ops, sub_hots, color=theme.TEXT) - y + 6
            ops.append(Op("rect", pygame.Rect(0, y, width, h), color=theme.mix(theme.BG_PANEL, col, 0.08), radius=4))
            ops.append(Op("rect", pygame.Rect(0, y, 3, h), color=col))
            ops.extend(sub_ops)
            hots.extend(sub_hots)
            y += h + 10
        elif b.kind == "code":
            runnable = b.lang == "console"
            lh = 22 if runnable else 19
            h = lh * len(b.lines) + 16
            ops.append(Op("rect", pygame.Rect(0, y, width, h), color=theme.BG_INPUT, radius=4))
            ops.append(Op("rect", pygame.Rect(0, y, width, h), color=theme.BORDER, radius=4, width=1))
            yy = y + 8
            for line in b.lines:
                if runnable and line.strip() and not line.strip().startswith("#"):
                    ops.append(Op("text", pygame.Rect(12, yy + 3, 14, lh), "›", theme.FRIEND, 13, "mono"))
                    r = pygame.Rect(30, yy + 3, theme.text_width(line, 13, "mono"), 16)
                    ops.append(Op("text", r, line, theme.TEXT, 13, "mono"))
                    hots.append(Hot(pygame.Rect(4, yy, width - 8, lh), "try", line.strip()))
                else:
                    col = theme.TEXT_FAINT if line.strip().startswith("#") else theme.TEXT
                    ops.append(Op("text", pygame.Rect(14, yy + 2, 0, lh), line, col, 13, "mono"))
                yy += lh
            y += h + 12
        elif b.kind == "table" and b.rows:
            ncol = max(len(r) for r in b.rows)
            # column widths from content, scaled down to fit
            nat = [0] * ncol
            least = [48] * ncol  # the longest single word must still fit
            for ri, row in enumerate(b.rows):
                wt = "semibold" if ri == 0 else "regular"
                for ci, cell in enumerate(row):
                    fams = [("mono" if sp.code else "ui", sp.text) for sp in cell]
                    w = sum(theme.text_width(t, 13, f, wt) + (8 if f == "mono" else 0) for f, t in fams) + 20
                    nat[ci] = max(nat[ci], min(w, 360))
                    for f, t in fams:
                        for word in t.split():
                            least[ci] = max(least[ci], theme.text_width(word, 13, f, wt) + (8 if f == "mono" else 0) + 18)
            total = sum(nat) or 1
            widths = [max(lo, int(n * min(1.0, width / total))) for n, lo in zip(nat, least)]
            over = sum(widths) - width
            slack = sum(w - lo for w, lo in zip(widths, least))
            if over > 0 and slack > 0:  # take the excess from columns that can wrap
                widths = [w - math.ceil(over * (w - lo) / slack) for w, lo in zip(widths, least)]
            for ri, row in enumerate(b.rows):
                row_ops: list[Op] = []
                row_hots: list[Hot] = []
                x = 0
                bottom = y
                for ci in range(ncol):
                    cell = row[ci] if ci < len(row) else []
                    yb = _flow(cell, x + 8, y + 4, widths[ci] - 16, row_ops, row_hots, 13,
                               "semibold" if ri == 0 else "regular", theme.TEXT_DIM if ri == 0 else theme.TEXT, 19)
                    bottom = max(bottom, yb + 4)
                    x += widths[ci]
                bg = theme.BG_PANEL_HI if ri == 0 else (theme.BG_PANEL if ri % 2 else theme.mix(theme.BG_PANEL, theme.BG_INPUT, 0.5))
                ops.append(Op("rect", pygame.Rect(0, y, min(width, sum(widths)), bottom - y), color=bg))
                ops.extend(row_ops)
                hots.extend(row_hots)
                y = bottom
            y += 14
    return Layout(ops, hots, y, anchors)


def draw(surf: pygame.Surface, lay: Layout, origin: tuple[int, int], clip: pygame.Rect) -> None:
    ox, oy = origin
    prev = surf.get_clip()
    surf.set_clip(clip)
    for op in lay.ops:
        r = op.rect.move(ox, oy)
        if r.bottom < clip.top or r.top > clip.bottom:
            continue
        if op.kind == "rect":
            pygame.draw.rect(surf, op.color, r, op.width, border_radius=op.radius)
        elif op.kind == "line":
            pygame.draw.rect(surf, op.color, r)
        else:
            theme.text(surf, op.text, r.topleft, op.color, op.size, op.family, op.weight)
    surf.set_clip(prev)


__all__ = ["Block", "Layout", "Span", "draw", "inline", "layout", "parse"]
