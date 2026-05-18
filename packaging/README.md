# Packaging

This directory contains assets and helpers used to bundle the application
into standalone formats via [PyInstaller](https://pyinstaller.org/).

## Local build (any OS)

```bash
pip install -r requirements.txt
pip install pyinstaller==6.10.0
pyinstaller --noconfirm --clean EditableTreeModel.spec
```

The resulting one-folder distribution is written to `dist/EditableTreeModel/`.

* **Windows** — `dist/EditableTreeModel/EditableTreeModel.exe` plus its
  support files. The folder can be zipped and shipped as-is.
* **macOS** — In addition to the folder, PyInstaller produces
  `dist/EditableTreeModel.app`, which can be packed into a `.dmg`
  with `hdiutil create`.
* **Linux** — The folder is repackaged into an AppImage by the release
  workflow using the helper scripts in `packaging/linux/`
  (`AppRun`, `.desktop`, `.svg` icon) and
  [`appimagetool`](https://github.com/AppImage/AppImageKit).

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
