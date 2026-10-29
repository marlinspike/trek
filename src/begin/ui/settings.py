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
    keys: dict[str, str] = field(default_factory=dict)         # Begin 2.0 `key` macros: "F5" -> "fire all phasers 10"

    @staticmethod
    def path() -> Path:
        return settings_dir() / "settings.json"

    @staticmethod
    def load() -> Settings:
        try:
            data = json.loads(Settings.path().read_text())
        except (OSError, ValueError):
            data = {}
        s = Settings()
        for k, v in data.items():
            if hasattr(s, k):
                setattr(s, k, tuple(v) if k == "window" else v)
        s.keys.update(read_key_file(settings_dir() / "begin2.key"))
        return s

    def save(self) -> None:
        try:
            p = self.path()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(json.dumps(asdict(self), indent=2))
        except OSError:
            pass


def read_key_file(path: Path) -> dict[str, str]:
    """Begin 2.0 read Begin2.key at startup: one `<key> <string>` definition per line, without the word Key."""
    out: dict[str, str] = {}
    try:
        lines = path.read_text().splitlines()
    except OSError:
        return out
    for line in lines:
        parts = line.strip().split(None, 1)
        if len(parts) == 2 and not parts[0].startswith("#"):
            name = parts[0].upper() if parts[0].lower().startswith("f") else parts[0].lower()
            out[name] = parts[1]
    return out


__all__ = ["Settings", "read_key_file", "settings_dir"]
