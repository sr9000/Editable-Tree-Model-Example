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
    collect_data_files,
    collect_submodules,
    copy_metadata,
)
APP_NAME = "EditableTreeModel"
ENTRY_SCRIPT = "main.py"
# ---------------------------------------------------------------------------
# Data files bundled into the executable.
# ---------------------------------------------------------------------------
# Theme specs / icons loaded via importlib.resources("themes.builtin").
datas = collect_data_files("themes.builtin", include_py_files=False)
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
    # Resources accessed via importlib.resources must be importable as
    # packages, but they have no static `import` statements anywhere in
    # the codebase, so PyInstaller's graph misses them.
    "themes",
    "themes.builtin",
    "gmpy2",
    "dateutil",
    "dateutil.tz",
    "dateutil.zoneinfo",
    "simplejson",
    "yaml",
    "_yaml",
    "tzdata",
]
block_cipher = None
a = Analysis(
    [ENTRY_SCRIPT],
    pathex=[str(Path(SPECPATH))],
    binaries=[],
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
    # ``importlib.resources.files("themes.builtin")`` needs the package's
    # ``__init__.py`` to live on disk next to the data files, otherwise
    # the Traversable returned by the frozen importer can't ``iterdir``.
    # ``pyz+py`` ships the module both inside PYZ (for fast import) and
    # as a plain file on disk (for resource discovery).
    module_collection_mode={
        "themes": "pyz+py",
        "themes.builtin": "pyz+py",
    },
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
