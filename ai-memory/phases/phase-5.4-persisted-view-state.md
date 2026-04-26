# Phase 5.4 — Persisted view state

## Goal

Remember per-file column widths, expansion, last selection, and font
zoom across sessions via `QSettings`.

## Entry criteria

- Phase 5.1 merged.

## Exit criteria

- Reopening the same file restores its tree expansion, column widths,
  last-selected path, and font point size.
- New / unknown files use the existing defaults
  (`expandAll`, `resizeColumnToContents`).
- `Save As` to a new path migrates the entry; the old key is deleted.
- Ctrl+`+` / Ctrl+`-` / Ctrl+`0` zoom in / out / reset on the active
  tab; the chosen size is persisted alongside the rest of view state.

## Work items

### `view_state.py` helper module
- [ ] [shell] New module `view_state.py` exposing:
      - `state_key(path: str) -> str` (sha1 hash, 16 hex chars,
        prefixed `view_state/`).
      - `save(tab) -> None`: column widths (3 ints), expanded paths
        (`list[list[int]]`), current path, font point size.
      - `restore(tab) -> bool`: returns `True` when state was found
        and applied; `False` when the caller should fall back to
        defaults.
      - `discard(path: str) -> None`: remove the group; used on
        `Save As`.
      Use `QSettings(APPLICATION_ID, "view_state")`.
      — `view_state.py` (new)
- [ ] [tests] Unit-test `state_key` stability across runs and that
      `save → restore` round-trips for a synthetic tab fixture.

### Wire into `MainWindow`
- [ ] [shell] In `_add_tab`, after the existing `expandAll` /
      `resizeColumnToContents` defaults, call
      `view_state.restore(tab)`; if it returns `False`, keep defaults.
      — `ui.py:MainWindow._add_tab`
- [ ] [shell] In `close_tab`, call `view_state.save(widget)` before
      `removeTab`. Also call from `closeEvent` for each tab.
      — `ui.py:MainWindow.close_tab`, `closeEvent`
- [ ] [shell] In `_save_tab` (when `save_as=True` and
      `tab.file_path` changed), call `view_state.discard(old_path)`
      then `view_state.save(tab)` for the new path. Capture
      `old_path = tab.file_path` before delegating to `tab.save_as()`.
      — `ui.py:MainWindow._save_tab`

### Font zoom on `JsonTab`
- [ ] [tab] Add `_font_pt` attribute initialized from
      `self.view.font().pointSize()`.
      — `json_tab.py:JsonTab.__init__`
- [ ] [tab] Add `zoom_in / zoom_out / zoom_reset` methods that update
      `self.view.font()` (clamp 6–48) and store the new pt.
      — `json_tab.py:JsonTab`
- [ ] [tab] Bind `QShortcut(QKeySequence.ZoomIn, self.view)` etc. and
      `Ctrl+0` for reset.
- [ ] [tests] New test confirms zoom in / out adjusts
      `view.font().pointSize()` and is persisted by
      `view_state.save → restore`.

## Risks / notes

- `QSettings` value types differ between platforms. Always coerce to
  `int` / `list[int]` on read; treat unknown shapes as "no state".
- Expanded paths can grow large for huge files; cap to e.g. 5000
  entries and log a warning past that.
- Keep `view_state.save` cheap and synchronous — it's called on tab
  close.
