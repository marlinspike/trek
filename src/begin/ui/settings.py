"""Persisted user settings (JSON in the user's home directory)."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass, field
from pathlib import Path


def settings_dir() -> Path:
    base = os.environ.get("BEGIN_HOME")
    return Path(base) if base else Path.home() / ".begin-remake"


@dataclass
class Settings:
    window: tuple[int, int] = (1600, 900)
    fullscreen: bool = False
    speed: float = 1.0
    custom: dict[str, object] = field(default_factory=dict)
    llm: dict[str, object] = field(default_factory=dict)       # provider settings (no secrets: keys come from env)
    hidden: dict[str, object] = field(default_factory=dict)    # the game's own hidden state

    @staticmethod
    def path() -> Path:
        return settings_dir() / "settings.json"

    @staticmethod
    def load() -> Settings:
        try:
            data = json.loads(Settings.path().read_text())
        except (OSError, ValueError):
            return Settings()
        s = Settings()
        for k, v in data.items():
            if hasattr(s, k):
                setattr(s, k, tuple(v) if k == "window" else v)
        return s

    def save(self) -> None:
        try:
            p = self.path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(asdict(self), indent=2))
        except OSError:
            pass


__all__ = ["Settings", "settings_dir"]
