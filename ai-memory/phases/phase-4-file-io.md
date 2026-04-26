# Phase 4 — File I/O

## Goal

Turn the editor into a real file-backed application: open/save JSON and
YAML, track dirty state per tab, prompt on close, remember recent files.

## Status snapshot (2026-04-26)

- Core Phase 4 plumbing is implemented in `ui.py`, `json_tab.py`, and
  new `file_io.py`.
- New tests `tests/test_file_io_phase4.py` pass along with
  `tests/test_smoke_mainwindow.py`.
- Full suite currently reports **346 passed**, but there is still a
  post-pytest interpreter teardown segfault to investigate separately.

## Entry criteria

- ✅ Phase 3 complete (2026-04-26): model mutations are reliable and
  undoable through typed action/compensation commands. Each `JsonTab`
  owns a `QUndoStack`; `commit_set_data()` and the seven
  `push_*` helpers are the single mutation API for tree actions and
  delegates. **All Phase 4 dirty-state work should hang off
  `undo_stack.cleanChanged`** — never off `dataChanged` directly —
  because the typed commands already collapse cleanly there.

## Already available from Phases 0–3

- `MainWindow._current_tab()` / `MainWindow._current_view()` helpers.
- `MainWindow.close_tab(index)` removes the tab and `deleteLater()`s it
  (no dirty check yet — Phase 4 adds it).
- `JsonTab.file_path: str | None` attribute is declared (always `None`).
- `JsonTab` accepts a `status_message_callback`, used here to surface
  load/save errors.
- `JsonTreeModel.typeChanged` / `dataChanged` / `rowsInserted` /
  `rowsRemoved` are reliable dirty-state triggers.
- `mainwindow.ui` already declares `fileOpenAction`, `fileSaveAction`,
  `fileSaveAsAction`, `fileCreateNewAction`, `appExitAction` — Phase 4
  only wires their `triggered` signals.
- ✅ `JsonTab.undo_stack` (Phase 3) exposes `cleanChanged(bool)` —
  Phase 4 dirty tracking should consume that signal directly. After a
  successful save call `self.undo_stack.setClean()` to mark the new
  baseline.
- ✅ `JsonTab.commit_set_data` / `push_*` (Phase 3) are the only
  mutation entry points — file-loading code should bypass them and
  build the model fresh, then `setClean()` afterwards (loading is not
  itself an undoable action).

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
- [x] [io] Implement `MainWindow.setup_model(filename)` to detect format
      by extension and load:
      - `.json` → `simplejson.load(parse_float=mpq)`
      - `.yaml` / `.yml` → `yaml.load(Loader=MpqSafeLoader)`
      Pass parsed data into `JsonTab(data=..., file_path=...)`.
      — `ui.py:MainWindow.setup_model`
      Empty `filename` (the test fixture passes `""`) must remain a no-op.
- [x] [io] Update `JsonTab.__init__` to accept `data` and `file_path`
      keyword parameters. Drop the hardcoded demo dict in favour of the
      passed-in `data`. When `data is None`, default to `{}` (empty
      object). Keep the existing `update_actions_callback` and
      `status_message_callback` parameters.
      — `json_tab.py:JsonTab.__init__`
- [ ] [io] Keep `JsonTab` backward compatibility: preserve demo seed only
      for legacy/tests that call bare `JsonTab(...)`; explicit
      `data={}` in `MainWindow.create_new_file()` yields an empty file tab.
- [x] [io] Add `MainWindow.open_file_dialog()` triggered by
      `fileOpenAction`. Filters: `*.json *.yaml *.yml`.
      The action already exists in `mainwindow.ui` — only the
      `triggered.connect(...)` wiring and the slot are new.

### Saving
- [x] [io] Implement `JsonTab.save()`: dispatch on file extension,
      serialize via `JsonTreeItem.to_json()` plus the right encoder.
      Use `mpq_json_default` for JSON; mpq YAML dumper for YAML.
- [x] [io] Implement `JsonTab.save_as(path)`: ask via `QFileDialog`,
      then call `save()`.
- [x] [io] Wire `fileSaveAction` (Ctrl+S) and `fileSaveAsAction`
      (Ctrl+Shift+S) in `MainWindow`.
- [x] [io] Optionally write through a temp file + atomic rename to
      avoid partial writes.

### Dirty / close flow
- [x] [tab] Add `JsonTab.is_dirty` boolean. Connect to
      `model.dataChanged`, `rowsInserted`, `rowsRemoved`, plus the undo
      stack's `cleanChanged` (introduced in Phase 3).
- [x] [tab] Emit a `JsonTab.dirtyChanged(bool)` signal; `MainWindow`
      updates the tab title (`name`, `name *`).
- [x] [shell] Extend the existing `MainWindow.close_tab(index)` (currently
      always closes) with a dirty-check + `QMessageBox.question` (Save /
      Discard / Cancel) before removal.
      — `ui.py:MainWindow.close_tab`
- [x] [shell] Override `closeEvent` on `MainWindow` to walk all tabs
      and confirm.

### Recent files
- [x] [shell] Add a `File → Recent` submenu populated from
      `QSettings("EditableTreeModel", "recent_files")`. Cap at 8 entries.
- [x] [shell] Update on every successful open/save.

### MainWindow plumbing
- [x] [shell] Implement `MainWindow.update_actions()`: enable Save /
      Save As only when there is a current tab; enable insert/remove only
      when the current tab has a valid current index.
      — `ui.py:MainWindow.update_actions`
- [x] [shell] Connect `tabWidget.currentChanged` to `update_actions`.

### Tests
- [ ] [tests] Round-trip: load a JSON file, mutate, save, reload — tree
      equals expectation.
- [ ] [tests] YAML round-trip with `mpq` values.
- [x] [tests] Dirty-state flips on edit, clears on save.

## Tips & Deep Dives

### What's already in `mainwindow.ui`

Re-check the .ui before adding new actions — these already exist and
just need `triggered.connect()` plumbing:

- `fileOpenAction` (Ctrl+O)
- `fileSaveAction` (Ctrl+S)
- `fileSaveAsAction` (Ctrl+Shift+S)
- `fileCreateNewAction` (Ctrl+N)
- `rowInsertAction` / `rowInsertAfterAction` / `rowRemoveAction`
- `appExitAction`

So Phase 4 mostly **wires** existing actions, plus adds a `Recent`
submenu (no .ui change required — it can be built dynamically in
`MainWindow.__init__`).

### Format dispatch

Centralise the dispatch in one place:

```python
def detect_format(path: str) -> str:
    ext = Path(path).suffix.lower()
    if ext in (".json",):       return "json"
    if ext in (".yaml", ".yml"): return "yaml"
    raise ValueError(f"Unknown format: {ext}")

def load_file(path: str):
    fmt = detect_format(path)
    with open(path, "r", encoding="utf-8") as f:
        if fmt == "json":
            import simplejson as sj   # only here Decimals/mpq survive
            return sj.load(f, parse_float=mpq)
        return yaml.load(f, Loader=MpqSafeLoader)

def save_file(path: str, data) -> None:
    fmt = detect_format(path)
    text = (
        sj.dumps(data, default=mpq_json_default, indent=2)
        if fmt == "json"
        else yaml.dump(data, Dumper=MpqSafeDumper, sort_keys=False, allow_unicode=True)
    )
    _atomic_write(path, text)
```

Atomic write:

```python
def _atomic_write(path: str, text: str) -> None:
    tmp = f"{path}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)
    os.replace(tmp, path)  # atomic on POSIX and modern Windows
```

### `JsonTab` constructor signature

```python
class JsonTab(QWidget):
    dirtyChanged = Signal(bool)

    def __init__(self, *, data=None, file_path: str | None = None,
                 parent=None):
        super().__init__(parent)
        ...
        self.model = JsonTreeModel(data if data is not None else {}, self.view)
        self.file_path = file_path
        self._dirty = False
        self.undo_stack.cleanChanged.connect(self._on_clean_changed)

    def _on_clean_changed(self, clean: bool):
        self._set_dirty(not clean)
```

Tying dirty state to **`QUndoStack.cleanChanged`** (Phase 3) is cleaner
than listening to `dataChanged`/`rowsInserted`/etc. After save, call
`self.undo_stack.setClean()` to mark the current position as the new
saved baseline.

### Display name & dirty marker

```python
def display_name(self) -> str:
    base = Path(self.file_path).name if self.file_path else "Untitled"
    return f"{base} *" if self._dirty else base
```

Wire from `MainWindow`:

```python
def _on_tab_dirty(self, tab: JsonTab, _dirty: bool):
    idx = self.tabWidget.indexOf(tab)
    if idx >= 0:
        self.tabWidget.setTabText(idx, tab.display_name())
```

### Close confirmation flow

```python
def _confirm_close(self, tab: JsonTab) -> bool:
    if not tab._dirty:
        return True
    btn = QMessageBox.question(
        self, "Unsaved changes",
        f"Save changes to {tab.display_name()}?",
        QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel,
    )
    if btn == QMessageBox.Cancel:
        return False
    if btn == QMessageBox.Save:
        return self._save_tab(tab)  # False if save dialog cancelled
    return True

def close_tab(self, index: int):
    tab = self.tabWidget.widget(index)
    if not self._confirm_close(tab):
        return
    self.tabWidget.removeTab(index)
    tab.deleteLater()

def closeEvent(self, event):
    for i in reversed(range(self.tabWidget.count())):
        if not self._confirm_close(self.tabWidget.widget(i)):
            event.ignore()
            return
    super().closeEvent(event)
```

### Recent files

Keep the storage code small; bind dynamically:

```python
def _refresh_recent_menu(self):
    s = QSettings("EditableTreeModel", "app")
    recent = s.value("recent_files", [], type=list)
    self.recentMenu.clear()
    for path in recent:
        if not Path(path).exists():
            continue
        a = self.recentMenu.addAction(path)
        a.triggered.connect(lambda _=False, p=path: self._open_path(p))
    self.recentMenu.setEnabled(bool(self.recentMenu.actions()))

def _push_recent(self, path: str):
    s = QSettings("EditableTreeModel", "app")
    recent = [str(Path(path).resolve())] + [
        p for p in s.value("recent_files", [], type=list)
        if p != str(Path(path).resolve())
    ]
    s.setValue("recent_files", recent[:8])
    self._refresh_recent_menu()
```

The `lambda _=False, p=path:` capture trick avoids the classic
late-binding bug.

### `update_actions` driven by current tab

```python
def update_actions(self):
    tab = self._current_tab()
    has_tab = tab is not None
    has_index = bool(tab and tab.view.selectionModel().currentIndex().isValid())

    self.fileSaveAction.setEnabled(has_tab and tab._dirty)
    self.fileSaveAsAction.setEnabled(has_tab)
    self.rowInsertAction.setEnabled(has_index)
    self.rowInsertAfterAction.setEnabled(has_index)
    self.rowRemoveAction.setEnabled(has_index)
```

Trigger it from `tabWidget.currentChanged` and from each tab's
`selectionChanged` / `dirtyChanged` signals.

### Round-trip caveat for `simplejson`

On the current pinned `simplejson` version, `load(..., use_decimal=True)`
cannot be combined with `parse_float=mpq` (`TypeError: use_decimal=True
implies parse_float=Decimal`). The compatible load path is
`load(parse_float=mpq)`.

For dumps, keeping `use_decimal=True` is still desirable because
`mpq_json_default` may return `Decimal` for terminating fractions.

### Test sketch

```python
def test_json_roundtrip(tmp_path):
    src = tmp_path / "in.json"
    src.write_text('{"q": 1, "f": 1.25}')
    data = load_file(str(src))
    save_file(str(src), data)
    assert json.loads(src.read_text()) == {"q": 1, "f": 1.25}
```

YAML test mirrors `tests/test_mpq2py.py::test_mpq_with_yaml`.

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
