# Phase 2 — Type & Name Editing

## Goal

Make the `Name` and `Type` columns first-class editable cells. After this
phase a user can rename any object key and change any node's `JsonType`
through the UI, with sensible value coercion.

## Entry criteria

- Phase 1 complete: model insertions are correct, `set_data` already
  recomputes `json_type` from the value.

## Exit criteria

- Editing column 0 (Name) renames the underlying `JsonTreeItem.name`.
  Duplicate names under the same `OBJECT` parent are rejected.
- Editing column 1 (Type) via `JsonTypeDelegate` mutates `json_type` and
  coerces `value` to a sane default for the new type.
- The Type combo preselects the **current** type when opened.
- Auto-classification can be **overridden**: a node explicitly typed as
  `STRING` stays `STRING` even if the value would parse as datetime /
  base64 / multiline.

## Work items

### Name column
- [ ] [type] Extend `JsonTreeItem.set_data(0, value)` to update `self.name`.
      Reject empty names and duplicates under an `OBJECT` parent (return
      `False`).
      — `tree_item.py:JsonTreeItem.set_data`
- [ ] [type] In `JsonTreeModel.flags()`, mark column 0 as editable only
      when the parent is an `OBJECT`. ARRAY children expose their index
      as read-only.
      — `tree_model.py:JsonTreeModel.flags`
- [ ] [type] In `JsonTreeItem.data(0)`, return the row index for ARRAY
      children instead of `<no name>`.
      — `tree_item.py:JsonTreeItem.data`
- [ ] [tests] Unit tests: rename success, rename to duplicate fails,
      ARRAY child rename refused.

### Type column
- [ ] [BUG] Implement `JsonTypeDelegate.setModelData` to push the
      selected `JsonType` through `model.setData(index, type, EditRole)`.
      — `delegate.py:JsonTypeDelegate.setModelData`
- [ ] [BUG] Move combo population from `setEditorData` into `createEditor`,
      and have `setEditorData` set the current text from
      `index.internalPointer().json_type`.
      — `delegate.py:JsonTypeDelegate`
- [ ] [type] Extend `JsonTreeItem.set_data(1, json_type)` to mutate
      `self.json_type` and coerce `self.value`. Define a coercion table:
      | from\to | NULL | BOOLEAN | INTEGER | FLOAT/PERCENT | STRING/MULTILINE | DATE/TIME/DT/DTZ | BYTES/ZLIB/GZIP | ARRAY | OBJECT |
      |---------|------|---------|---------|---------------|------------------|------------------|-----------------|-------|--------|
      Cells are filled with reasonable defaults (e.g. INTEGER → 0, ARRAY
      → []). Where the existing value is convertible, prefer it
      (`"42"` → `42`).
      — `tree_item.py:JsonTreeItem.set_data`
- [ ] [type] When switching to/from `OBJECT` or `ARRAY`, clear
      `child_items` and emit the proper
      `beginRemoveRows`/`endRemoveRows` (or `beginInsertRows`) sequence
      via the model. Likely needs a model-level helper
      `JsonTreeModel.change_type(index, new_type)` that owns the
      bookkeeping.

### Type pinning (override auto-classification)
- [ ] [type] Persist an `explicit_type: bool` flag on `JsonTreeItem`. When
      `True`, `set_data(2, value)` does **not** re-run `parse_json_type`
      — it only validates against the existing `json_type`.
      — `tree_item.py:JsonTreeItem`
- [ ] [type] Setting `json_type` via column 1 sets `explicit_type=True`.
      Rebuilding from raw input (load) clears it.
- [ ] [tests] Unit tests for pinning: assign STRING to a value that looks
      like base64, confirm it stays STRING after `set_data`.

### Editor wiring
- [ ] [type] After a successful type change, the view must reopen the
      `Value` editor with the right delegate. The model can emit
      `dataChanged` for the (col-2) sibling index to nudge the view.
- [ ] [ux] When a coercion drops information (e.g. OBJECT → STRING),
      show a confirmation dialog or status-bar warning.

## Tips & Deep Dives

### Funnel all mutations through the model

Phase 2 introduces structural changes (type swap → drop children,
rename → re-key). Do **not** mutate `JsonTreeItem` directly from the
delegate. Add a model-level helper that owns Qt's begin/end
bookkeeping:

```python
class JsonTreeModel(QAbstractItemModel):
    def change_type(self, index: QModelIndex, new_type: JsonType) -> bool:
        item = self.get_item(index)
        old_type = item.json_type
        if old_type is new_type:
            return False

        had_children = old_type in (JsonType.ARRAY, JsonType.OBJECT)
        will_have_children = new_type in (JsonType.ARRAY, JsonType.OBJECT)

        if had_children and item.child_count() > 0:
            self.beginRemoveRows(index, 0, item.child_count() - 1)
            item.child_items.clear()
            self.endRemoveRows()

        item.json_type = new_type
        item.value = _default_value_for(new_type, old_value=item.value)
        item.explicit_type = True
        item._editable = item._compute_editable()

        # Notify all three columns: name, type, value
        top = self.index(index.row(), 0, index.parent())
        bot = self.index(index.row(), 2, index.parent())
        self.dataChanged.emit(top, bot, [Qt.ItemDataRole.DisplayRole, Qt.ItemDataRole.EditRole])

        if will_have_children:
            # nothing to insert yet; user adds children explicitly
            pass
        return True
```

Then `JsonTypeDelegate.setModelData` becomes a one-liner:

```python
def setModelData(self, editor, model, index):
    new_type = JsonType(editor.currentText())
    model.change_type(index, new_type)
```

### Coercion table

Define once, in `enums.py` next to `JsonType`:

```python
def _default_value_for(t: JsonType, old_value=None):
    # Prefer convertible existing value when possible.
    match t:
        case JsonType.NULL:        return None
        case JsonType.BOOLEAN:     return bool(old_value)
        case JsonType.INTEGER:
            try:    return int(old_value) if old_value is not None else 0
            except: return 0
        case JsonType.FLOAT:
            try:    return mpq(str(old_value))
            except: return mpq(0)
        case JsonType.PERCENT:
            try:
                v = mpq(str(old_value))
                return v if 0 <= v <= 1 else mpq(0)
            except: return mpq(0)
        case JsonType.STRING | JsonType.MULTILINE:
            return "" if old_value is None else str(old_value)
        case JsonType.DATE:        return "1970-01-01"
        case JsonType.TIME:        return "00:00"
        case JsonType.DATETIME:    return "1970-01-01T00:00"
        case JsonType.DATETIMEZONE:return "1970-01-01T00:00:00+00:00"
        case JsonType.BYTES | JsonType.ZLIB | JsonType.GZIP:
            return ""  # empty base64
        case JsonType.ARRAY:       return []
        case JsonType.OBJECT:      return {}
    raise ValueError(f"Unknown {t}")
```

Document **lossy** transitions (OBJECT/ARRAY → primitive throws away
children; non-numeric STRING → INTEGER → 0). Surface a confirm dialog
for these in `JsonTab`/`MainWindow`, not in the model.

### Combo population and preselection

The current `JsonTypeDelegate` populates the combo from `setEditorData`
on every edit, which is both wasteful and wrong. Fix:

```python
class JsonTypeDelegate(QStyledItemDelegate):
    def createEditor(self, parent, option, index):
        editor = QComboBox(parent)
        for t in JsonType:
            editor.addItem(t.value, t)         # display = value, data = enum
        return editor

    def setEditorData(self, editor: QComboBox, index):
        item = index.internalPointer()
        idx = editor.findData(item.json_type)
        editor.setCurrentIndex(idx if idx >= 0 else 0)

    def setModelData(self, editor, model, index):
        model.change_type(index, editor.currentData())
```

### Renaming under OBJECT

```python
def set_data(self, column: int, value):
    if column == 0:  # name
        if not isinstance(value, str) or not value:
            return False
        if self.parent_item and self.parent_item.json_type is JsonType.OBJECT:
            siblings = {c.name for c in self.parent_item.child_items if c is not self}
            if value in siblings:
                return False
        self.name = value
        return True
    ...
```

For ARRAY children, column 0 is read-only: `JsonTreeModel.flags()` must
strip `ItemIsEditable` when `parent.json_type is ARRAY`.

### Type pinning rules

- `explicit_type=True` after `set_data(1, ...)` (column 1 edit).
- `explicit_type=False` when the item is constructed from raw input
  (loading a file).
- In `set_data(2, value)`:
  - If `explicit_type` is `True` → keep `json_type`, just store the
    coerced value. Reject incompatible values (return `False`).
  - If `explicit_type` is `False` → recompute `json_type` from the new
    value (Phase 1 behaviour).

### Re-opening the value editor after a type change

After `change_type()`, the active value editor (if any) is now of the
wrong widget class. Force the view to close and reopen:

```python
view.closePersistentEditor(value_index)
view.edit(value_index)  # Qt schedules a fresh createEditor()
```

Wire this from `JsonTab` after listening to a model signal — keep the
delegate stateless.

## Risks / notes

- The coercion table is the largest design decision in this phase.
  Document it in `enums.py` next to `JsonType`.
- Be careful with `PERCENT`: storage stays in the `[0, 1]` `mpq`
  fraction; the editor multiplies by 100. Type changes must respect
  this.
- Renaming under an `OBJECT` must preserve sibling order
  (`child_items` is a list). Re-keying must not move the row.
