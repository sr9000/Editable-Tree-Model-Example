# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the EditableTreeModel PySide6 application.
Produces a *single-file*, fully self-contained executable. The resulting
binary is large but has no external Python / Qt / data-file dependencies
beyond the platform's standard system libraries.
Build with:
    pyinstaller --noconfirm --clean EditableTreeModel.spec
"""
import sys
from pathlib import Path
from PyInstaller.utils.hooks import (
    collect_all,
    collect_submodules,
    copy_metadata,
)
APP_NAME = "EditableTreeModel"
ENTRY_SCRIPT = "main.py"# ---------------------------------------------------------------------------
# Data files bundled into the executable.
# ---------------------------------------------------------------------------
# Ship the entire `themes/builtin/` subtree under `<_MEIPASS>/themes/builtin/`.
#
# We *deliberately* avoid `collect_data_files("themes.builtin")`: it spawns
# an isolated subprocess to import the package, and that subprocess does
# NOT have the project's source directory on `sys.path`, so it silently
# emits zero entries with a `WARNING: ... is not a package` log line.
# A direct, source-tree-relative enumeration is bulletproof.
_SRC_ROOT = Path(SPECPATH)
_BUILTINS_SRC = _SRC_ROOT / "themes" / "builtin"
_WIN_ICON = _SRC_ROOT / "packaging" / "windows" / "editabletreemodel.ico"
_RUNTIME_ICON_PNG = _SRC_ROOT / "packaging" / "linux" / "editabletreemodel.png"
datas = []
# Bundle the PNG icon used at runtime by ``QApplication.setWindowIcon``.
# Shipped on every platform so Linux/macOS get the in-app icon too.
if _RUNTIME_ICON_PNG.is_file():
    datas.append((str(_RUNTIME_ICON_PNG), "packaging/linux"))
for _path in _BUILTINS_SRC.rglob("*"):
    if not _path.is_file():
        continue
    if _path.suffix == ".pyc":
        continue
    if "__pycache__" in _path.parts:
        continue
    # `dst` is the destination *directory* (relative to <_MEIPASS>) where the
    # file will be placed, mirroring the source tree.
    _rel_dir = _path.parent.relative_to(_SRC_ROOT)
    datas.append((str(_path), str(_rel_dir)))
# Several runtime deps call importlib.metadata.version(<pkg>) at import time
# (gmpy2 is the one that crashed; the others are bundled defensively so we
# don't play whack-a-mole as users upgrade libraries).
for dist in (
    "gmpy2",
    "PySide6",
    "shiboken6",
    "jsonschema",
    "jsonschema-specifications",
    "referencing",
    "rpds-py",
    "attrs",
    "simplejson",
    "PyYAML",
    "python-dateutil",
    "six",
    "tzdata",
    "numpy",
    "pandas",
):
    try:
        datas += copy_metadata(dist)
    except Exception:
        # Distribution not installed in this environment - skip silently so
        # the spec stays portable across the build matrix.
        pass
# ---------------------------------------------------------------------------
# Hidden imports for things loaded indirectly (entry points, plugins, etc.).
# ---------------------------------------------------------------------------
hiddenimports = []
hiddenimports += collect_submodules("jsonschema")
hiddenimports += collect_submodules("jsonschema_specifications")
hiddenimports += collect_submodules("referencing")
hiddenimports += [
    "gmpy2",
    "dateutil",
    "dateutil.tz",
    "dateutil.zoneinfo",
    "simplejson",
    "yaml",
    "_yaml",
    "tzdata",
]

# ---------------------------------------------------------------------------
# numpy / pandas need a *full* collection. NumPy 2.x relocated its C-extension
# internals under `numpy._core` (e.g. `numpy._core._exceptions`,
# `numpy._core._multiarray_umath`). PyInstaller's static analysis misses these
# dynamically-imported submodules and their compiled `.so`/`.pyd` payloads,
# which causes a runtime `ModuleNotFoundError: No module named
# 'numpy._core._exceptions'` followed by pandas failing to import numpy.
# `collect_all` gathers submodules + binaries + data files for each package.
binaries = []
for _pkg in ("numpy", "pandas"):
    _pkg_datas, _pkg_binaries, _pkg_hidden = collect_all(_pkg)
    datas += _pkg_datas
    binaries += _pkg_binaries
    hiddenimports += _pkg_hidden

block_cipher = None
a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[str(Path(SPECPATH))],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "pytest",
        "_pytest",
        "tests",
        "tkinter",
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)
pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)
# ---------------------------------------------------------------------------
# One-file build: pass binaries/zipfiles/datas straight to EXE and skip
# COLLECT entirely.
# ---------------------------------------------------------------------------
exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon=str(_WIN_ICON) if _WIN_ICON.is_file() and sys.platform == "win32" else None,
)
if sys.platform == "darwin":
    app = BUNDLE(
        exe,
        name=f"{APP_NAME}.app",
        icon=None,
        bundle_identifier="com.example.editabletreemodel",
        info_plist={
            "CFBundleName": APP_NAME,
            "CFBundleDisplayName": APP_NAME,
            "CFBundleShortVersionString": "0.0.0",
            "NSHighResolutionCapable": True,
        },
    )
