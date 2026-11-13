"""The type checker passes over the whole game.

The screen is typed against the `Session` protocol (session/interface.py), and the mixins against the state they
share: those contracts only hold while mypy runs clean, so the suite runs it. Skipped where mypy isn't installed
(it is in the `dev` extra). It reuses mypy's cache, so after the first run it takes a few seconds."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


def test_mypy_finds_no_errors() -> None:
    pytest.importorskip("mypy")
    # in its own process: mypy run in-process leaves state behind that other tests on the same worker would meet
    run = subprocess.run([sys.executable, "-m", "mypy", "--config-file", str(ROOT / "pyproject.toml"), "--cache-dir",
                          str(ROOT / ".mypy_cache"), "--no-error-summary"], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode == 0, run.stdout + run.stderr
