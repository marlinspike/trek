"""The downloadable build keeps its settings beside the program, never in the home folder."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from begin import paths


def _frozen(monkeypatch: pytest.MonkeyPatch, exe: Path, meipass: Path | None = None) -> None:
    monkeypatch.delenv("BEGIN_HOME", raising=False)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    if meipass is not None:
        monkeypatch.setattr(sys, "_MEIPASS", str(meipass), raising=False)
    monkeypatch.setattr(paths, "_seeded", [])


def test_packaged_home_beside_exe_and_beside_mac_app(tmp_path: Path) -> None:
    assert paths.packaged_home(tmp_path / "Games" / "Begin.exe") == (tmp_path / "Games").resolve()
    mac = tmp_path / "Applications" / "Begin.app" / "Contents" / "MacOS" / "Begin"
    assert paths.packaged_home(mac) == (tmp_path / "Applications").resolve()


def test_packaged_config_is_beside_the_program_and_gets_examples(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    seed = tmp_path / "bundle" / "config_seed"
    seed.mkdir(parents=True)
    (seed / "README.md").write_text("readme")
    (seed / "officers.example.toml").write_text("[spock]\n")
    game = tmp_path / "Downloads"
    game.mkdir()
    _frozen(monkeypatch, game / "begin", tmp_path / "bundle")
    target = paths.config_dir()
    assert target == game.resolve() / paths.PACKAGED_DIR_NAME
    assert (target / "README.md").read_text() == "readme"
    assert (target / "officers.example.toml").exists()
    assert paths.config_writable(target)
    assert paths.config_warning() is None


def test_seed_never_replaces_the_players_files(tmp_path: Path) -> None:
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "README.md").write_text("new")
    (seed / "settings.example.json").write_text("{}")
    target = tmp_path / "cfg"
    target.mkdir()
    (target / "README.md").write_text("mine")
    assert paths.seed_config(target, seed) == ["settings.example.json"]
    assert (target / "README.md").read_text() == "mine"
    assert paths.seed_config(target, None) == []


def test_warning_only_when_the_packaged_folder_cannot_be_written(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    assert paths.config_warning() is None                    # running from Python: never
    _frozen(monkeypatch, tmp_path / "begin")
    monkeypatch.setattr(paths, "config_writable", lambda path=None: False)
    warning = paths.config_warning()
    assert warning is not None and "can't be saved" in warning


def test_checkout_still_uses_the_project_config_folder(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("BEGIN_HOME", raising=False)
    monkeypatch.setattr(paths, "migrate_legacy", lambda old, new: [])
    root = paths.project_root()
    if root is not None:
        assert paths.config_dir() == root / "config"
