"""Where the game keeps the player's own files: the project's `config/` folder.

Everything the player sets lives next to the code, in `<project>/config/`:

    config/settings.json   window, speed, battle options, officers' language model (gitignored)
    config/begin2.key      Begin 2.0 key macros, one `F5 fire all phasers` per line (gitignored)
    config/help/           manual pages that replace or add to the bundled ones (gitignored)

`BEGIN_HOME` names a different folder (the tests use it). When the game is
installed without its project folder, it falls back to `~/.begin-remake`.
Versions before this one kept everything in `~/.begin-remake`; the first
run copies those files into `config/` (the old folder is left untouched).
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

LEGACY_DIR = Path.home() / ".begin-remake"
_FILES = ("settings.json", "begin2.key")


def project_root() -> Path | None:
    """The source checkout this package runs from (it has pyproject.toml), or None for a plain install."""
    root = Path(__file__).resolve().parents[2]
    return root if (root / "pyproject.toml").is_file() and (root / "src" / "begin").is_dir() else None


def config_dir() -> Path:
    base = os.environ.get("BEGIN_HOME")
    if base:
        return Path(base)
    root = project_root()
    if root is None:
        return LEGACY_DIR
    target = root / "config"
    migrate_legacy(LEGACY_DIR, target)
    return target


def migrate_legacy(old: Path, new: Path) -> list[str]:
    """Copy settings, key macros and help pages from the old home folder into `new`, once.

    Nothing is overwritten: a file already in `new` wins. Returns the names copied.
    """
    if old == new or not old.is_dir() or (new / "settings.json").exists():
        return []
    copied: list[str] = []
    try:
        new.mkdir(parents=True, exist_ok=True)
        for name in _FILES:
            if (old / name).is_file() and not (new / name).exists():
                shutil.copy2(old / name, new / name)
                copied.append(name)
        if (old / "help").is_dir():
            for f in (old / "help").iterdir():
                dest = new / "help" / f.name
                if f.is_file() and not dest.exists():
                    dest.parent.mkdir(exist_ok=True)
                    shutil.copy2(f, dest)
                    copied.append(f"help/{f.name}")
    except OSError:
        pass
    return copied


__all__ = ["LEGACY_DIR", "config_dir", "migrate_legacy", "project_root"]
