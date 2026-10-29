"""Decision traces: why an AI or computer did what it did (for debugging, the debrief and tests)."""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, field


@dataclass
class Trace:
    limit: int = 200
    entries: deque[tuple[int, str]] = field(default_factory=deque)

    def add(self, tick: int, text: str) -> None:
        self.entries.append((tick, text))
        while len(self.entries) > self.limit:
            self.entries.popleft()

    def recent(self, n: int = 10) -> list[tuple[int, str]]:
        return list(self.entries)[-n:]


__all__ = ["Trace"]
