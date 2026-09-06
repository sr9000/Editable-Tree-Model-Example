# Packaging

This directory contains assets and helpers used to bundle the application
into standalone formats via [PyInstaller](https://pyinstaller.org/).

## Local build (any OS)

```bash
poetry install --with build
poetry run pyinstaller --noconfirm --clean EditableTreeModel.spec
```

PyInstaller is pinned at 6.22.2 in the optional `build` dependency group; 6.10.0 cannot be used
because it declares `requires_python = "<3.14"`.

The resulting single-file executable is written to `dist/EditableTreeModel`
(`dist/EditableTreeModel.exe` on Windows).

* **Windows** — `dist/EditableTreeModel.exe`. The file can be zipped and
  shipped as-is.
* **macOS** — In addition to the standalone executable, PyInstaller produces
  `dist/EditableTreeModel.app`, which can be packed into a `.dmg`
  with `hdiutil create`.
* **Linux** — The executable is repackaged into an AppImage by the release
  workflow using the helper scripts in `packaging/linux/`
  (`AppRun`, `.desktop`, `.svg` icon) and
  [`appimagetool`](https://github.com/AppImage/AppImageKit).

## Icon assets

The platform-neutral icon source is `packaging/linux/editabletreemodel.svg`,
rasterised to a 256 px PNG at `packaging/linux/editabletreemodel.png`. The
PNG is loaded by `QApplication.setWindowIcon` at runtime (Linux/macOS/Windows)
and bundled by the PyInstaller spec.

The Windows executable additionally embeds a multi-resolution
`packaging/windows/editabletreemodel.ico` as its Win32 resource (taskbar,
Explorer, Alt-Tab). Regenerate it from the PNG with ImageMagick:

```bash
convert packaging/linux/editabletreemodel.png \
    -define icon:auto-resize=256,128,64,48,32,24,16 \
    packaging/windows/editabletreemodel.ico
```

If the `.ico` file is absent, the spec falls back to PyInstaller's default
icon — the build still succeeds on every platform.

## Release pipeline

`.github/workflows/release.yml` is a **manual** workflow
(`workflow_dispatch`). Trigger it from the Actions tab, supply a tag
name (e.g. `v0.1.0`), and it will:

1. Build the app on Windows, macOS, and Linux runners.
2. Produce `EditableTreeModel-<tag>-windows.zip`,
   `EditableTreeModel-<tag>-macos.dmg`, and
   `EditableTreeModel-<tag>-linux-x86_64.AppImage`.
3. Create (or update) a GitHub Release for the supplied tag and upload
   the three artifacts to it.
