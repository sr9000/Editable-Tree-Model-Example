# Phase 4 — File I/O

## Goal

Turn the editor into a real file-backed application: open/save JSON and
YAML, track dirty state per tab, prompt on close, remember recent files.

## Entry criteria

- Phase 3 complete: model mutations are reliable and undoable.

## Exit criteria

- `python main.py path/to/file.{json,yaml}` opens the file directly into
  the first tab.
- File menu offers: New, Open, Save, Save As, Recent, Close Tab, Quit.
- Each `JsonTab` tracks `file_path`, `is_dirty`, and a display name.
- Tab title shows `*` when dirty.
- Closing a dirty tab or the application prompts to save / discard / cancel.
- JSON and YAML round-trips preserve `mpq`, datetimes, and bytes via
  `mpq2py` and `jsontream`.

## Work items

### Loading
- [ ] [io] Implement `MainWindow.setup_model(filename)` to detect format
      by extension and load:
      - `.json` → `json.load` (or `simplejson`/streaming reader)
      - `.yaml` / `.yml` → `yaml.safe_load` with the `mpq2py` YAML
        loader subclass.
      Pass parsed data into `JsonTab(data=..., file_path=...)`.
      — `ui.py:MainWindow.setup_model`
- [ ] [io] Update `JsonTab.__init__` to accept `data` and `file_path`
      parameters. Drop hardcoded demo dict.
      — `json_tab.py:JsonTab.__init__`
- [ ] [io] Add `MainWindow.open_file_dialog()` triggered by a new
      `fileOpenAction` in `mainwindow.ui`. Filters: `*.json *.yaml *.yml`.

### Saving
- [ ] [io] Implement `JsonTab.save()`: dispatch on file extension,
      serialize via `JsonTreeItem.to_json()` plus the right encoder.
      Use `mpq_json_default` for JSON; mpq YAML dumper for YAML.
- [ ] [io] Implement `JsonTab.save_as(path)`: ask via `QFileDialog`,
      then call `save()`.
- [ ] [io] Wire `fileSaveAction` (Ctrl+S) and `fileSaveAsAction`
      (Ctrl+Shift+S) in `MainWindow`.
- [ ] [io] Optionally write through a temp file + atomic rename to
      avoid partial writes.

### Dirty / close flow
- [ ] [tab] Add `JsonTab.is_dirty` boolean. Connect to
      `model.dataChanged`, `rowsInserted`, `rowsRemoved`, plus the undo
      stack's `cleanChanged`.
- [ ] [tab] Emit a `JsonTab.dirtyChanged(bool)` signal; `MainWindow`
      updates the tab title (`name`, `name *`).
- [ ] [shell] `MainWindow.close_tab(index)`: if the tab is dirty, show
      `QMessageBox.question` with Save / Discard / Cancel.
      — `ui.py:MainWindow.close_tab`
- [ ] [shell] Override `closeEvent` on `MainWindow` to walk all tabs
      and confirm.

### Recent files
- [ ] [shell] Add a `File → Recent` submenu populated from
      `QSettings("EditableTreeModel", "recent_files")`. Cap at 8 entries.
- [ ] [shell] Update on every successful open/save.

### MainWindow plumbing
- [ ] [shell] Implement `MainWindow.update_actions()`: enable Save /
      Save As only when there is a current tab; enable insert/remove only
      when the current tab has a valid current index.
      — `ui.py:MainWindow.update_actions`
- [ ] [shell] Connect `tabWidget.currentChanged` to `update_actions`.

### Tests
- [ ] [tests] Round-trip: load a JSON file, mutate, save, reload — tree
      equals expectation.
- [ ] [tests] YAML round-trip with `mpq` values.
- [ ] [tests] Dirty-state flips on edit, clears on save.

## Risks / notes

- YAML loading via `yaml.safe_load` strips type information — make sure
  the `mpq2py` loader is actually wired in so `mpq` and datetimes
  survive.
- `simplejson` may shadow stdlib `json`; the same precaution as Phase 0
  applies for save paths.
- Atomic-rename on Windows requires `os.replace` (already cross-platform
  in modern Python). Worth a one-line note in code.
- Recent-files paths must be stored as absolute and pruned if missing
  on disk.
