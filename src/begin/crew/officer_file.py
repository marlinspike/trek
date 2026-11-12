"""Changing one thing about one officer in the captain's config/officers.toml, and nothing else [E].

The Settings page edits an officer's name, rank, traits or response style. The file is the captain's own: it
may hold comments, whole personas, lines for every event and keys this page never shows. So a change is made
line by line, never by re-writing the file from parsed data: only the lines of the one key being changed are
touched (or a line is added under the officer's table), everything else stays byte for byte as it was, and the
result is parsed back before it is written. Nothing is written at all until the captain changes something.
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python 3.10
    import tomli as tomllib

EDITABLE = ("name", "rank", "traits", "response_style")     # what the Settings page offers
LISTS = ("traits",)
NEW_FILE = ("# Your officers, your way. The Settings page writes the lines you change there; the rest is yours\n"
            "# to write by hand. officers.example.toml lists everything an officer can have.\n")

Value = str | list[str] | None


def literal(value: str | list[str]) -> str:
    """A TOML value: a basic string, or an array of them (JSON's escapes are TOML's)."""
    if isinstance(value, list):
        return "[" + ", ".join(json.dumps(v, ensure_ascii=False) for v in value) + "]"
    return json.dumps(value, ensure_ascii=False)


def _header(line: str) -> str | None:
    """The table a `[table]` line opens ("worf", "worf.lines"), or None for any other line."""
    m = re.match(r"^\s*\[\s*([^\[\]]+?)\s*\]\s*(#.*)?$", line)
    if not m:
        return None
    return ".".join(p.strip().strip('"').strip("'") for p in m.group(1).split("."))


def _extent(lines: list[str], i: int, end: int) -> int:
    """The line after a `key = value` that starts at line i (a value can run on: an array, a long string)."""
    for j in range(i, end):
        try:
            tomllib.loads("\n".join(lines[i:j + 1]))
            return j + 1
        except tomllib.TOMLDecodeError:
            continue
    return i + 1


def set_field(path: Path, officer: str, key: str, value: Value) -> None:
    """Set (or, with None or nothing, remove) one key in one officer's table, leaving every other line alone.

    Raises ValueError, and writes nothing, when the file can't be read as TOML before or after the change.
    """
    if key not in EDITABLE:
        raise ValueError(f"The Settings page doesn't edit '{key}'.")
    if isinstance(value, list):
        value = [v.strip() for v in value if v.strip()] or None
    elif isinstance(value, str):
        value = " ".join(value.split()) or None
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        if value is None:
            return                              # nothing to take away from a file that isn't there
        text = NEW_FILE
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as e:
        raise ValueError(f"{path.name} doesn't read as TOML ({e}); fix it by hand first.") from e
    lines = text.splitlines()
    start = next((i for i, ln in enumerate(lines) if _header(ln) == officer), None)
    if start is None:
        if value is None:
            return
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", f"[{officer}]", f"{key} = {literal(value)}"]
    else:
        end = next((i for i in range(start + 1, len(lines)) if _header(lines[i]) is not None), len(lines))
        at = None
        last = start + 1                        # where a new key goes: after the table's last key
        i = start + 1
        while i < end:
            if re.match(r"^\s*[A-Za-z0-9_\-\"']+\s*=", lines[i]):
                stop = _extent(lines, i, end)
                if re.match(rf"^\s*[\"']?{re.escape(key)}[\"']?\s*=", lines[i]):
                    at = (i, stop)
                last = stop
                i = stop
            else:
                i += 1
        new = [] if value is None else [f"{key} = {literal(value)}"]
        if at is not None:
            lines[at[0]:at[1]] = new
        elif new:
            lines[last:last] = new
        else:
            return
    out = "\n".join(lines) + "\n"
    try:
        back = tomllib.loads(out).get(officer, {})
    except tomllib.TOMLDecodeError as e:          # never expected: the change is checked rather than trusted
        raise ValueError(f"That change wouldn't read back ({e}); {path.name} is unchanged.") from e
    if back.get(key) != value:
        raise ValueError(f"That change didn't read back as written; {path.name} is unchanged.")
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_name(path.name + ".tmp")
    tmp.write_text(out, encoding="utf-8")
    os.replace(tmp, path)


def read_field(path: Path, officer: str, key: str) -> Value:
    """What the captain's file itself says (None: nothing, so the shipped value stands)."""
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8")).get(officer, {})
    except (OSError, tomllib.TOMLDecodeError):
        return None
    v = raw.get(key) if isinstance(raw, dict) else None
    if isinstance(v, list):
        return [str(x) for x in v]
    return str(v) if isinstance(v, str) else None


__all__ = ["EDITABLE", "LISTS", "read_field", "set_field"]
