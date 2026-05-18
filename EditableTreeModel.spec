# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for the EditableTreeModel PySide6 application.

Build with:
    pyinstaller --noconfirm --clean EditableTreeModel.spec

Produces a one-folder distribution under ``dist/EditableTreeModel`` and,
on macOS, an additional ``dist/EditableTreeModel.app`` bundle.
"""
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

APP_NAME = "EditableTreeModel"
ENTRY_SCRIPT = "main.py"

# Bundle the YAML theme specs and icon assets that live under themes/builtin/.
# ``themes.builtin`` is loaded via ``importlib.resources`` at runtime so it
# must be present on disk inside the frozen distribution.
datas = collect_data_files("themes.builtin", include_py_files=False)

# Pull in optional submodules that may be loaded indirectly.
hiddenimports = []
hiddenimports += collect_submodules("jsonschema")
hiddenimports += [
    "gmpy2",
    "dateutil",
    "dateutil.tz",
    "simplejson",
    "yaml",
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
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name=APP_NAME,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name=APP_NAME,
)

if sys.platform == "darwin":
    app = BUNDLE(
        coll,
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
