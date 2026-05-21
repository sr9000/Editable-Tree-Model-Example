# Issue 04 — Add "Copy Full File Path" action to File menu

**Status:** open
**Severity:** Low (quality of life)
**Target commit:** `feat: add "Copy Full File Path" action in File menu`

## Context

Once issue #03 is fixed, tab titles correctly show only the basename. Users
still occasionally need the **absolute path** of the currently open document
(to paste into a terminal, a chat, a diff tool, etc.). There is currently no
in-app way to retrieve it.

## Proposed change

1. **UI definition** — `mainwindow.ui`:
   - Add `<action name="fileCopyPathAction">` with text
     `Copy Full File &Path` and shortcut `Ctrl+Shift+C` (verify no conflict
     with existing copy bindings; otherwise use `Ctrl+Alt+C` or no shortcut).
   - Insert it into `<widget class="QMenu" name="fileMenu">` after
     `fileSaveAsAction`, separated by a `<addaction name="separator"/>`.
2. **Wiring** — `app/main_window_actions.py` (or wherever File menu actions
   are connected):
   - Connect `fileCopyPathAction.triggered` to a new
     `MainWindow.copy_current_file_path()` method.
3. **Behavior** — `app/main_window.py`:
   ```python
   def copy_current_file_path(self) -> None:
       tab = self._current_tab()
       if tab is None or not tab.file_path:
           self.statusBar().showMessage("No file path to copy", 2000)
           return
       QGuiApplication.clipboard().setText(tab.file_path)
       self.statusBar().showMessage(f"Copied: {tab.file_path}", 2000)
   ```
4. **Action enablement** — disable the action in `update_actions()` when the
   current tab has no `file_path` (untitled buffer).
5. **Tooltip** — set `actionCopyPath.setToolTip(tab.file_path)` dynamically,
   or at least a static hint "Copy absolute path of the current document".

## Out of scope

- Right-click "Copy Path" on the tab bar (potential follow-up).
- "Copy relative path" / "Reveal in Explorer" actions.
- Localization of the new label (handled by the existing i18n track).

## Definition of Done

- [ ] New action visible in File menu, after "Save As", separated.
- [ ] Action is disabled when current tab is unsaved (no file_path).
- [ ] Triggering the action puts the absolute path on the system clipboard
      and shows a transient status-bar confirmation.
- [ ] Verified on Windows (path uses `\\`) and Linux (`/`).
- [ ] Shortcut documented in `README.md` keymap section (if such a section
      exists).
- [ ] One commit; UI + handler + enablement only.
