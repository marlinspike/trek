"""Where the game keeps the player's own files: the project's `config/` folder.

Everything the player sets lives next to the code, in `<project>/config/`:

    config/settings.json   window, speed, battle options, officers' language model (gitignored)
    config/begin2.key      Begin 2.0 key macros, one `F5 fire all phasers` per line (gitignored)
    config/help/           manual pages that replace or add to the bundled ones (gitignored)

`BEGIN_HOME` names a different folder (the tests use it). When the game is
installed without its project folder, it falls back to `~/.begin-remake`.
Versions before this one kept everything in `~/.begin-remake`; the first
run brings those files into `config/` (the old folder is left untouched).
"""

from __future__ import annotations

import json
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
    """Bring settings, key macros and help pages over from the old home folder, once.

    Nothing already in `new` is overwritten. If `new/settings.json` exists, the
    old file's settings are merged in only where the new one has no value (so
    rapport carries over beside settings written by hand). A `.migrated`
    marker stops it running again. Returns the names brought across.
    """
    marker = new / ".migrated"
    if old == new or not old.is_dir() or marker.exists():
        return []
    copied: list[str] = []
    try:
        new.mkdir(parents=True, exist_ok=True)
        if (old / "settings.json").is_file():
            if (new / "settings.json").exists():
                if _merge_settings(old / "settings.json", new / "settings.json"):
                    copied.append("settings.json")
            else:
                shutil.copy2(old / "settings.json", new / "settings.json")
                copied.append("settings.json")
        if (old / "begin2.key").is_file() and not (new / "begin2.key").exists():
            shutil.copy2(old / "begin2.key", new / "begin2.key")
            copied.append("begin2.key")
        if (old / "help").is_dir():
            for f in (old / "help").iterdir():
                dest = new / "help" / f.name
                if f.is_file() and not dest.exists():
                    dest.parent.mkdir(exist_ok=True)
                    shutil.copy2(f, dest)
                    copied.append(f"help/{f.name}")
        marker.write_text("Settings from ~/.begin-remake were brought across. Delete this file to do it again.\n")
    except OSError:
        pass
    return copied


def _merge_settings(old: Path, new: Path) -> bool:
    """Fill gaps in `new` from `old`, one level deep for dict values. True if anything changed."""
    try:
        src = json.loads(old.read_text())
        dst = json.loads(new.read_text())
    except (OSError, ValueError):
        return False
    if not isinstance(src, dict) or not isinstance(dst, dict):
        return False
    changed = False
    for k, v in src.items():
        if k not in dst:
            dst[k], changed = v, True
        elif isinstance(v, dict) and isinstance(dst[k], dict):
            for kk, vv in v.items():
                if kk not in dst[k]:
                    dst[k][kk], changed = vv, True
    if changed:
        new.write_text(json.dumps(dst, indent=2))
    return changed


__all__ = ["LEGACY_DIR", "config_dir", "migrate_legacy", "project_root"]
