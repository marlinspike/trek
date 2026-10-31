"""What an officer says: one line for the log, with any commands they suggest."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from .characters import OfficerProfile


@dataclass
class Utterance:
    officer: str        # officer id
    speaker: str        # what the log shows
    text: str
    tone: str = "crew"  # crew | caution | dim
    commands: list[str] = field(default_factory=list)   # suggestions the captain can click or type


# runs a console line on behalf of an officer; returns an error, or None when it was carried out
RunCommand = Callable[[str, OfficerProfile], "str | None"]


__all__ = ["RunCommand", "Utterance"]
