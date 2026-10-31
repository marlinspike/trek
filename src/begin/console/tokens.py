"""Reading a typed order a word at a time, with Begin's shortcuts: filler words skipped, mount lists, numbers."""

from __future__ import annotations

import re

from .vocab import AIM_WORDS, FILLER, is_num, match_word


class ParseError(Exception):
    pass


class Tokens:
    def __init__(self, text: str) -> None:
        self.raw = text
        text = text.replace(",", " ").replace("°", " ")
        text = re.sub(r"(?<=[a-z])-(?=[a-z])", " ", text.lower())      # "cease-fire", "stand-down"
        # "Cease fire!", "evasive!", "stand down." : the punctuation that ends an order is not part of a word
        self.toks = [t if is_num(t) else (t.rstrip("!?.") or t) for t in text.split()]
        self.i = 0
        self.max_mount = 12

    def peek(self, k: int = 0) -> str | None:
        j = self.i + k
        return self.toks[j] if j < len(self.toks) else None

    def next(self) -> str | None:
        t = self.peek()
        if t is not None:
            self.i += 1
        return t

    def done(self) -> bool:
        return self.i >= len(self.toks)

    def rest(self) -> list[str]:
        out = self.toks[self.i:]
        self.i = len(self.toks)
        return out

    def skip_filler(self) -> None:
        while self.peek() in FILLER:
            self.i += 1

    def is_word(self, *words: str, k: int = 0) -> bool:
        t = self.peek(k)
        return t is not None and any(t == w or (len(t) >= 2 and w.startswith(t)) for w in words)

    def take_word(self, *words: str) -> bool:
        """Consume the next token if it is (a prefix ≥ 2 of) one of `words`."""
        self.skip_filler()
        if self.is_word(*words):
            self.i += 1
            return True
        return False

    def number(self, what: str) -> float:
        self.skip_filler()
        t = self.next()
        if t is None or not is_num(t):
            raise ParseError(f"Expected a number for {what}.")
        return float(t)

    def opt_number(self) -> float | None:
        self.skip_filler()
        t = self.peek()
        if is_num(t):
            self.i += 1
            return float(t)  # type: ignore[arg-type]
        return None

    def is_mount(self, t: str | None) -> bool:
        if t is None:
            return False
        if re.match(r"^\d+-\d+$", t):
            return True
        return t.isdigit() and 1 <= int(t) <= self.max_mount

    def mount_list(self) -> tuple[int, ...] | None:
        """'all'/'al' → None; '1 2', '1,2', '1 2 and 3', '1-3' → zero-based indices; nothing → None."""
        self.skip_filler()
        t = self.peek()
        if t in ("all", "al", "every"):
            self.i += 1
            return None
        out: list[int] = []
        while True:
            t = self.peek()
            if t == "and" and out and self.is_mount(self.peek(1)):
                self.i += 1
                continue
            if t is None or not self.is_mount(t):
                break
            m = re.match(r"^(\d+)-(\d+)$", t)
            if m:
                a, b = int(m.group(1)), int(m.group(2))
                out.extend(range(min(a, b) - 1, max(a, b)))
            else:
                out.append(int(t) - 1)
            self.i += 1
        return tuple(out) if out else None


def aim_ahead(tok: Tokens, skip: int = 0) -> bool:
    """A system is named next (after `skip` words), without consuming it."""
    i = tok.i
    tok.i += skip
    try:
        return take_aim(tok) is not None
    finally:
        tok.i = i


def take_aim(tok: Tokens) -> str | None:
    """A subsystem group named next ("warp core", "life support", "shields"), consumed; "hull" gives ""."""
    tok.skip_filler()
    a, b = tok.peek(), tok.peek(1)
    if a is None:
        return None
    if a in ("hull", "ship"):
        tok.next()
        return ""
    if b is not None:
        g = match_word(a + b, AIM_WORDS, min_len=99)
        if g is not None:
            tok.next()
            tok.next()
            if tok.peek() in ("system", "systems", "generator", "generators"):
                tok.next()
            return g
    g = match_word(a, AIM_WORDS)
    if g is not None:
        tok.next()
        if tok.peek() in ("system", "systems", "generator", "generators"):
            tok.next()
    return g


__all__ = ["ParseError", "Tokens", "aim_ahead", "take_aim"]
