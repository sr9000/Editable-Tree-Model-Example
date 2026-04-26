# Phase 5 — UX Polish

## Goal

Make the editor pleasant to use day-to-day: human-friendly value
display, persistent layout, status-bar feedback, and a search/filter bar.

## Entry criteria

- Phase 4 complete: files open, save, dirty state works.
- Phase 3 carry-over (deferred to this phase, see
  `phase-3-tree-actions.md` for context):
  - auto-reopen value editor after a user-initiated `typeChanged`
  - `QUndoCommand.mergeWith` for consecutive value/name edits to the
    same path (typed commands already store path + old/new — merge is
    a small addition on `_EditValueCmd` / `_RenameCmd`)
  - convert `ValueDelegate.createEditor` dialog callbacks
    (`MULTILINE` / `BYTES` / `ZLIB` / `GZIP`) to use
    `QPersistentModelIndex` *and* route the commit through
    `JsonTab.commit_set_data` so dialog edits land on the typed undo
    stack instead of bypassing it via `model.setData`.

## Exit criteria

- Long values are elided in the table; full text is in a tooltip.
- Percentages display as `50%`, mpq fractions as their decimal form,
  datetimes in ISO-8601 with timezone where present.
- Status bar shows current path "Object > items > 3 > name" plus type
  and size hints.
- Column widths and tree expansion state are persisted per file path
  via `QSettings`.
- A search/filter bar above each tree filters by name and value
  substring.

## Work items

### Display formatting
- [ ] [ux] Implement `ValueDelegate.displayText(value, locale)`:
      - PERCENT → `f"{value*100:g}%"`
      - mpq FLOAT → `mpq_serialization(value)[0]`
      - long STRING / MULTILINE → first 80 chars + ellipsis
      - BYTES / ZLIB / GZIP → `f"<{units.format_bytes(len(raw))}>"`
      — `delegate.py:ValueDelegate`
- [ ] [ux] Implement `JsonTreeModel.data` for `Qt.ToolTipRole` to return
      the full value (capped at e.g. 4 KB) for long cells.
      — `tree_model.py:JsonTreeModel.data`
- [ ] [ux] Render the Type column with an icon per `JsonType` (optional
      stretch; can be deferred).

### Status bar
- [ ] [ux] When selection changes, write a breadcrumb to
      `MainWindow.statusBar()`: `Path: a > b > 3 (string, 24 chars)`.
- [ ] [ux] When a long-running action runs (load/save/sort), show a
      transient status message.

### Persisted view state
- [ ] [ux] On tab close / app close, persist per-file:
      - column widths
      - expansion state (set of tree paths)
      - last selected path
      Use `QSettings("EditableTreeModel", "view_state").setValue(path, ...)`.
- [ ] [ux] On open, restore the same. Fall back to defaults
      (`expandAll`, `resizeColumnToContents`) when unknown.

### Search / filter
- [ ] [ux] Add a `QLineEdit` above the tree in `JsonTab` (Ctrl+F to
      focus). Filter rows whose name or value substring-matches; keep
      ancestors visible.
- [ ] [ux] Use a `QSortFilterProxyModel` subclass that overrides
      `filterAcceptsRow` with recursive include-ancestor logic.
- [ ] [ux] Highlight matched substrings via a custom delegate
      (`paint` override) — optional stretch.

### Misc polish
- [ ] [ux] Resize columns to contents on `currentChanged`
      (tab switch) and `model.modelReset`.
- [ ] [ux] Add zoom in / out (Ctrl++/Ctrl+-) for tree font.
- [ ] [ux] Provide "Collapse All" / "Expand All" entries in context
      menu and View menu.

### Phase 3 carry-over
- [ ] [ux] **Auto-reopen value editor** after
      `JsonTreeModel.typeChanged` when the change came from the user
      (not programmatic `setData`). Approaches: track an "interactive"
      flag on the type combo's commit path, or hook `view.commitData`
      from `JsonTypeDelegate` and call `view.edit(value_index)` only
      from there. Must keep
      `tests/test_smoke_mainwindow.py::test_cycling_inline_types_does_not_log_edit_failed`
      green. — `json_tab.py:JsonTab._on_type_changed`,
      `delegate.py:JsonTypeDelegate.setModelData`.
- [ ] [undo] Implement `mergeWith` on `_EditValueCmd` and `_RenameCmd`
      so consecutive edits to the *same path* within a small time
      window collapse into one undo entry. Typed-command shape already
      supports this — see `json_tab.py`.
- [ ] [delegate] Convert `ValueDelegate.createEditor` dialog callbacks
      (`_save_multiline`, `_save_binary`) to capture
      `QPersistentModelIndex` and route the commit through
      `JsonTab.commit_set_data(index, value, EditRole)` instead of
      calling `model.setData` directly. This keeps dialog edits on the
      typed undo stack and survives row insertions/removals during the
      modal session. — `delegate.py:ValueDelegate.createEditor`.
- [ ] [delegate] Wrap `decode_bytes(item.value, item.json_type)` inside
      `createEditor` for `BYTES` / `ZLIB` / `GZIP` in try/except;
      surface decode failures via the status bar instead of letting
      them propagate out of `createEditor`.
      — `delegate.py:ValueDelegate.createEditor`.

## Tips & Deep Dives

### `displayText` vs model `data()`

Two layers can format a cell:

1. `JsonTreeModel.data(index, DisplayRole)` — what the view fetches.
2. `ValueDelegate.displayText(value, locale)` — what the view *renders*
   when there is a delegate.

Prefer the **delegate** layer for value-only formatting (PERCENT, mpq,
ellipsis) so editors continue to receive raw `mpq`/`int`/`str` from
`data(EditRole)`. Keep `data(DisplayRole)` returning the *raw value*
or `str(raw)` and put presentation in:

```python
class ValueDelegate(QStyledItemDelegate):
    def displayText(self, value, locale):
        # value is what data(DisplayRole) returned
        return _format_for_display(value)  # purely presentational
```

If `displayText` becomes type-aware, fetch the item via the model
during `paint()` instead — `displayText` itself does not have the index.

### Eliding & tooltips

Let Qt do the eliding (it's GPU-accelerated). Just provide the full
text via `Qt.ToolTipRole` and rely on the default
`Qt.TextElideMode.ElideRight`:

```python
def data(self, index, role=Qt.DisplayRole):
    if role == Qt.ToolTipRole and index.column() == 2:
        item = index.internalPointer()
        if item.json_type in (JsonType.STRING, JsonType.MULTILINE):
            text = str(item.value)
            return text[:4096] + ("…" if len(text) > 4096 else "")
    ...
```

### Breadcrumb status bar

```python
def _path_for(self, index: QModelIndex) -> str:
    parts = []
    while index.isValid():
        item = index.internalPointer()
        parts.append(item.name if item.name is not None else f"[{item.row()}]")
        index = index.parent()
    return " › ".join(reversed(parts)) or "/"
```

Hook to `selectionChanged`:

```python
def _on_selection_changed(self):
    idx = self.view.selectionModel().currentIndex()
    item = idx.internalPointer() if idx.isValid() else None
    if item is None:
        self.window().statusBar().clearMessage()
        return
    self.window().statusBar().showMessage(
        f"{self._path_for(idx)}  ({item.json_type})"
    )
```

### Persisted view state — keys and migration

Use file-path-keyed `QSettings` groups, but **always** with a hash
fallback so very long paths don't blow past Windows registry limits:

```python
def _state_key(self, path: str) -> str:
    h = hashlib.sha1(str(Path(path).resolve()).encode()).hexdigest()[:16]
    return f"view_state/{h}"

def save_view_state(self, tab: JsonTab):
    if not tab.file_path:
        return
    s = QSettings("EditableTreeModel", "view_state")
    s.beginGroup(self._state_key(tab.file_path))
    s.setValue("col_widths", [tab.view.columnWidth(c) for c in range(3)])
    s.setValue("expanded", list(self._collect_expanded_paths(tab)))
    s.endGroup()
```

On `Save As` (path change), call `save_view_state` for the new path and
delete the old group.

### Recursive filter proxy

```python
class TreeFilterProxy(QSortFilterProxyModel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setRecursiveFilteringEnabled(True)  # Qt 5.10+

    def filterAcceptsRow(self, src_row, src_parent):
        idx = self.sourceModel().index(src_row, 0, src_parent)
        if not idx.isValid():
            return False
        item = idx.internalPointer()
        needle = self.filterRegularExpression()
        if needle.pattern() == "":
            return True
        text_name = "" if item.name is None else str(item.name)
        text_value = "" if item.value is None else str(item.value)
        return bool(needle.match(text_name).hasMatch()
                    or needle.match(text_value).hasMatch())
```

`setRecursiveFilteringEnabled(True)` does the "keep ancestors visible"
work for free — no manual ancestor walk needed.

**Delegate impact**: with a proxy in front, `index.internalPointer()`
returns `None` because Qt strips the pointer through the proxy. Audit
delegates to map first:

```python
def _item(self, index: QModelIndex) -> JsonTreeItem:
    if isinstance(index.model(), QSortFilterProxyModel):
        index = index.model().mapToSource(index)
    return index.internalPointer()
```

### Debounce the search box

```python
self._filter_timer = QTimer(self)
self._filter_timer.setSingleShot(True)
self._filter_timer.setInterval(150)
self._filter_timer.timeout.connect(self._apply_filter)
self.search_edit.textChanged.connect(lambda _: self._filter_timer.start())
```

Prevents one filter recomputation per keystroke on large documents.

### Zoom

`QAbstractItemView` doesn't have a native font zoom; track a scale
yourself:

```python
self._font_pt = self.view.font().pointSize()

def zoom_in(self):  self._set_font_pt(self._font_pt + 1)
def zoom_out(self): self._set_font_pt(max(6, self._font_pt - 1))

def _set_font_pt(self, pt):
    self._font_pt = pt
    f = self.view.font(); f.setPointSize(pt); self.view.setFont(f)
```

Persist `_font_pt` per tab in the same `QSettings` group.

### Type icons (optional)

Once `JsonTypeDelegate` shows the type, paint a small icon in column 1
via `data(DecorationRole)`:

```python
_ICONS = {
    JsonType.OBJECT:  QIcon(":/icons/object.svg"),
    JsonType.ARRAY:   QIcon(":/icons/array.svg"),
    ...
}

def data(self, index, role):
    if role == Qt.DecorationRole and index.column() == 1:
        return _ICONS.get(index.internalPointer().json_type)
    ...
```

Defer to a follow-up if SVG resource plumbing isn't in place yet.

## Risks / notes

- A custom proxy model interacts with the `internalPointer()`
  contract: selection delegates must call
  `proxy.mapToSource(index).internalPointer()`. Audit `ValueDelegate`
  and `JsonTypeDelegate` accordingly.
- Persisted view state keyed by file path needs migration logic if
  the path changes (Save As). Drop or copy the entry on save-as.
- Search performance on a 100k-row document needs a one-pass index
  rather than re-walking on every keystroke; introduce a debounce.
