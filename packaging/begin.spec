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
from begin import __version__ as VERSION

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
              argv_emulation=False, target_arch=None, icon=str(ROOT / "packaging" / "icon.icns"))
    coll = COLLECT(exe, a.binaries, a.datas, name="Begin")
    app = BUNDLE(
        coll,
        name="Begin.app",
        icon=str(ROOT / "packaging" / "icon.icns"),
        bundle_identifier="net.marlinspike.begin",
        info_plist={
            "CFBundleName": "Begin",
            "CFBundleDisplayName": "Begin",
            "NSHumanReadableCopyright": "A personal, non-commercial fan project. Code: MIT.",
            "LSApplicationCategoryType": "public.app-category.simulation-games",
            "CFBundleShortVersionString": VERSION,
            "CFBundleVersion": VERSION,
            "NSHighResolutionCapable": True,
            "LSMinimumSystemVersion": "11.0",
        },
    )
else:
    # Windows: the name, version and description Explorer shows under Properties > Details
    VERSION_FILE = Path(workpath) / "version_info.txt"
    if sys.platform == "win32":
        nums = tuple(int(p) for p in VERSION.split(".")[:3]) + (0,)
        VERSION_FILE.parent.mkdir(parents=True, exist_ok=True)
        VERSION_FILE.write_text(f"""VSVersionInfo(
  ffi=FixedFileInfo(filevers={nums}, prodvers={nums}),
  kids=[
    StringFileInfo([StringTable('040904B0', [
      StringStruct('ProductName', 'Begin'),
      StringStruct('FileDescription', 'Begin: a tactical starship simulation'),
      StringStruct('FileVersion', '{VERSION}'),
      StringStruct('ProductVersion', '{VERSION}'),
      StringStruct('OriginalFilename', 'Begin.exe'),
      StringStruct('LegalCopyright', 'A personal, non-commercial fan project. Code: MIT.')])]),
    VarFileInfo([VarStruct('Translation', [1033, 1200])])
  ]
)
""")
    exe = EXE(
        pyz, a.scripts, a.binaries, a.datas, [],
        name="Begin" if sys.platform == "win32" else "begin",
        console=False if sys.platform == "win32" else True,
        upx=False,
        icon=str(ROOT / "packaging" / "icon.ico"),
        version=str(VERSION_FILE) if sys.platform == "win32" else None,
    )
