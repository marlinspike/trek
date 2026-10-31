"""Where the game keeps the player's own files: the project's `config/` folder.

Everything the player sets lives next to the code, in `<project>/config/`:

    config/settings.json   window, speed, battle options, officers' language model (gitignored)
    config/begin2.key      Begin 2.0 key macros, one `F5 fire all phasers` per line (gitignored)
    config/help/           manual pages that replace or add to the bundled ones (gitignored)

`BEGIN_HOME` names a different folder (the tests use it). The downloadable
build (a single program made by PyInstaller) keeps the same files in a
`Begin config` folder beside the program, never in the home folder: beside
`Begin.exe` on Windows, beside the `begin` file on Linux, and beside
`Begin.app` on macOS (not inside the bundle, which macOS treats as sealed).
When the game is installed without its project folder, it falls back to `~/.begin-remake`.
Versions before this one kept everything in `~/.begin-remake`; the first
run brings those files into `config/` (the old folder is left untouched).
"""

from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

LEGACY_DIR = Path.home() / ".begin-remake"
PACKAGED_DIR_NAME = "Begin config"
_FILES = ("settings.json", "begin2.key")
_seeded: list[Path] = []      # the packaged config folder has been given its README and examples this run


def is_packaged() -> bool:
    """True when running from the downloadable build rather than from Python."""
    return bool(getattr(sys, "frozen", False))


def packaged_home(executable: str | Path | None = None) -> Path:
    """The folder beside the packaged program: next to the .exe or Linux binary, or next to the macOS .app."""
    exe = Path(executable if executable is not None else sys.executable).resolve()
    for parent in exe.parents:
        if parent.suffix == ".app":           # Begin.app/Contents/MacOS/Begin
            return parent.parent
    return exe.parent


def config_writable(path: Path | None = None) -> bool:
    """Whether settings can be saved in the config folder (it is created if missing)."""
    target = path if path is not None else config_dir()
    try:
        target.mkdir(parents=True, exist_ok=True)
        probe = target / ".write-test"
        probe.write_text("")
        probe.unlink()
        return True
    except OSError:
        return False


def seed_dir() -> Path | None:
    """The README and example files packed into the downloadable build, or None when running from Python."""
    base = getattr(sys, "_MEIPASS", None)
    if not is_packaged() or base is None:
        return None
    d = Path(base) / "config_seed"
    return d if d.is_dir() else None


def seed_config(target: Path, source: Path | None) -> list[str]:
    """Put the README and example files into a fresh config folder, never replacing a file already there."""
    if source is None or not source.is_dir():
        return []
    copied: list[str] = []
    try:
        target.mkdir(parents=True, exist_ok=True)
        for f in sorted(source.iterdir()):
            dest = target / f.name
            if f.is_file() and not dest.exists():
                shutil.copyfile(f, dest)     # not copy2: the packed copies are private to the program
                copied.append(f.name)
    except OSError:
        pass
    return copied


def open_folder(path: Path) -> bool:
    """Show a folder in Explorer, Finder or the desktop's file manager. False if that couldn't be done."""
    import subprocess

    try:
        path.mkdir(parents=True, exist_ok=True)
        if sys.platform == "win32":
            os.startfile(str(path))  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            subprocess.Popen(["open", str(path)])
        else:
            subprocess.Popen(["xdg-open", str(path)])
        return True
    except (OSError, AttributeError):
        return False


def config_warning() -> str | None:
    """A line for the main menu when the packaged game cannot save its settings, else None."""
    if not is_packaged() or os.environ.get("BEGIN_HOME") or config_writable():
        return None
    if sys.platform == "darwin":
        return ("Settings can't be saved here. Drag Begin.app into Applications (or any folder of yours) "
                "and open it from there.")
    return f"Settings can't be saved: the folder beside the game ({config_dir()}) is read-only. Move the game somewhere you can write to."


def project_root() -> Path | None:
    """The source checkout this package runs from (it has pyproject.toml), or None for a plain install."""
    root = Path(__file__).resolve().parents[2]
    return root if (root / "pyproject.toml").is_file() and (root / "src" / "begin").is_dir() else None


def config_dir() -> Path:
    base = os.environ.get("BEGIN_HOME")
    if base:
        return Path(base)
    if is_packaged():
        target = packaged_home() / PACKAGED_DIR_NAME
        if not _seeded:
            _seeded.append(target)
            seed_config(target, seed_dir())
        return target
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


__all__ = ["LEGACY_DIR", "PACKAGED_DIR_NAME", "config_dir", "config_warning", "config_writable", "is_packaged",
           "migrate_legacy", "open_folder", "packaged_home", "project_root", "seed_config", "seed_dir"]
