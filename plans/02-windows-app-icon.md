# Issue 02 — Windows executable uses default PyInstaller icon

**Status:** open
**Severity:** Medium (branding / professionalism)
**Target commit:** `fix(win): bundle application icon in PyInstaller spec`

## Context

The current `EditableTreeModel.spec` does not pass an `icon=` argument to
`EXE(...)`, so the produced `EditableTreeModel.exe` ships with PyInstaller's
default icon. The same icon is shown in:

- Windows Explorer file listing
- Taskbar
- Alt-Tab switcher
- Window title bar (when no `QWindow.setIcon` is set)

A platform-neutral source SVG already exists at
`packaging/linux/editabletreemodel.svg`, but no Windows `.ico` is generated.

## Proposed change

1. Add a Windows icon source under `packaging/windows/editabletreemodel.ico`,
   generated from the existing SVG (multi-resolution: 16, 24, 32, 48, 64, 128,
   256 px). Document the regeneration command in `packaging/README.md`
   (`magick convert ... editabletreemodel.ico` or `pillow`-based script).
2. In `EditableTreeModel.spec`:
   ```python
   _ICON = _SRC_ROOT / "packaging" / "windows" / "editabletreemodel.ico"
   ...
   exe = EXE(
       ...,
       icon=str(_ICON) if _ICON.exists() and sys.platform == "win32" else None,
   )
   ```
3. In `app/main_window.py` (or wherever `QApplication` is set up), call
   `QApplication.setWindowIcon(QIcon(":/.../editabletreemodel.png"))` so the
   *running* window also shows the icon (independent of the .exe resource).
   Reuse the same source via Qt resources or a bundled PNG under
   `themes/builtin/` or a new `assets/` data folder added to `datas`.
4. Also export a 256 px PNG used at runtime (Linux/macOS benefit too).

## Out of scope

- macOS `.icns` bundling (already `icon=None` in the BUNDLE block; track
  separately).
- Redesigning the icon artwork.
- Installer (MSI / NSIS) integration.

## Definition of Done

- [ ] `packaging/windows/editabletreemodel.ico` exists and contains at least
      sizes 16/32/48/256 px.
- [ ] A built `EditableTreeModel.exe` shows the new icon in Explorer,
      taskbar and title bar (verified manually on Windows 10 or 11).
- [ ] Running app on Linux still shows the icon in the window title and
      taskbar.
- [ ] `packaging/README.md` documents how to regenerate the `.ico` from the
      source SVG.
- [ ] CI build (if any) still succeeds; spec stays portable on platforms
      where the `.ico` is absent (graceful fallback to no icon).
- [ ] One commit; no functional code changes outside packaging + a single
      `setWindowIcon` call.
