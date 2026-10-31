# PyInstaller recipe for the downloadable game: `pyinstaller packaging/begin.spec`.
#
# Windows and Linux get one self-contained program (Begin.exe, begin). macOS gets
# Begin.app, which the release workflow zips. The game's data files (ship art,
# fonts, manual pages, content tables) travel inside; the player's settings do
# not: they live in a "Begin config" folder beside the program (see begin.paths).
# The officers' language model is optional: Ollama and OpenAI-compatible servers
# need nothing extra, and the `anthropic` SDK is bundled when it is installed
# (`pip install .[llm]`, as the release workflow does).
# ruff: noqa
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

ROOT = Path(SPECPATH).resolve().parent
sys.path.insert(0, str(ROOT / "src"))

datas = collect_data_files("begin", excludes=["**/__pycache__", "**/*.pyc"])
# what a new "Begin config" folder starts with (begin.paths.seed_config); never the player's own files
datas += [(str(ROOT / "packaging" / "config_seed" / "README.md"), "config_seed")]
datas += [(str(f), "config_seed") for f in sorted((ROOT / "config").glob("*.example.*"))]
hiddenimports = collect_submodules("begin")

a = Analysis(
    [str(ROOT / "packaging" / "launcher.py")],
    pathex=[str(ROOT / "src")],
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "pytest", "mypy"],
    noarchive=False,
)
pyz = PYZ(a.pure)

if sys.platform == "darwin":
    exe = EXE(pyz, a.scripts, [], exclude_binaries=True, name="Begin", console=False,
              argv_emulation=False, target_arch=None)
    coll = COLLECT(exe, a.binaries, a.datas, name="Begin")
    app = BUNDLE(
        coll,
        name="Begin.app",
        bundle_identifier="net.marlinspike.begin",
        info_plist={
            "CFBundleDisplayName": "Begin",
            "CFBundleShortVersionString": "0.1.0",
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
else:
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="Begin" if sys.platform == "win32" else "begin",
        console=False if sys.platform == "win32" else True,
        upx=False,
    )
