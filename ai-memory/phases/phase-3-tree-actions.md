# Phase 3 — Tree Mutation Actions

## Goal

Make the tree fully **manipulable** through the UI: cut, copy, paste,
delete, duplicate, move up/down, sort keys, plus undo/redo. After this
phase, editing a JSON document feels like editing in a real outliner.

## Entry criteria

- Phase 2 complete: name/type editing works, model mutations go through
  a unified `JsonTreeModel` API.

## Exit criteria

- Context menu and keyboard shortcuts cover: Cut (Ctrl+X), Copy (Ctrl+C),
  Paste (Ctrl+V), Delete (Del), Duplicate (Ctrl+D), Move Up (Alt+↑),
  Move Down (Alt+↓), Insert Sibling Before / After, Sort Keys.
- All mutations go through a `QUndoStack`; Ctrl+Z / Ctrl+Y reverse and
  reapply them.
- Pasting clipboard JSON into a node either replaces (when types
  match) or inserts as child / sibling depending on the target.
- The dead "Insert Column" entry is gone.

## Work items

### Clipboard
- [ ] [tree] `Copy` action: serialize selection to JSON via
      `tree_view.to_json` (already exists). Multi-selection copies a JSON
      array.
      — `tree_view.py`
- [ ] [tree] `Cut` = `Copy` + `Delete`. Wire the missing
      `cut_action.triggered.connect(...)` in `tree_view.show_context_menu`.
      — `tree_view.py:show_context_menu`
- [ ] [tree] `Paste`: parse clipboard text as JSON; if target is
      OBJECT/ARRAY, insert as child; otherwise insert as sibling after.
      Reject if clipboard is not valid JSON.
- [ ] [tree] `Delete`: remove selected rows. Connect the orphan
      `delete_action`. Bind `Qt.Key_Delete`.

### Sibling / child insertion polish
- [ ] [tree] Add **Insert Sibling Before** action (the existing
      `rowInsertAction` was wired identically to "after"; split them).
      — `ui.py:setup_connections`
- [ ] [tree] Add **Insert Child** keyboard shortcut and toolbar button
      (already present in context menu).
- [ ] [tree] Add **Duplicate** (Ctrl+D): deep-copy the selected
      `JsonTreeItem` subtree and insert as next sibling.
- [ ] [tree] Add **Move Up / Move Down**: swap `child_items[i]` with
      neighbour, emitting `layoutChanged` or a row-move signal.
- [ ] [tree] Add **Sort Keys** (recursive option): only meaningful for
      `OBJECT` parents; sort `child_items` by `name`.

### Remove dead entries
- [ ] [hygiene] Drop the "Insert Column" context menu entry and its
      toolbar action; matches the model-side removal in Phase 1.
      — `tree_view.py:show_context_menu`, `mainwindow.ui`
- [ ] [hygiene] Drop `model_actions.action_insert_column` (or convert to
      a no-op + `DeprecationWarning`).
      — `model_actions.py`

### Undo / redo
- [ ] [tree] Introduce a `QUndoStack` per `JsonTab`. Wrap each mutation
      (set value, rename, change type, insert, remove, move, sort) in a
      `QUndoCommand`.
- [ ] [tree] Bind `MainWindow` Edit menu actions: Undo (Ctrl+Z),
      Redo (Ctrl+Shift+Z).
- [ ] [tree] Decide merge policy: consecutive value edits to the same
      cell should collapse into one undo step (`mergeWith`).
- [ ] [tests] Round-trip test: random sequence of mutations →
      `undo()` until empty → tree equals the original.

### Cross-cutting fixes
- [ ] [BUG] Audit dialog-based delegates (`MULTILINE`, `BYTES`, `ZLIB`,
      `GZIP`) so their commit goes through the new undo stack rather
      than directly calling `model.setData`. Stale-index risk shrinks
      because the `QPersistentModelIndex` form is preferred.
      — `delegate.py:ValueDelegate.createEditor`
- [ ] [BUG] In dialog callbacks, capture `QPersistentModelIndex(index)`
      instead of the raw `QModelIndex`.

## Tips & Deep Dives

### Anatomy of a `QUndoCommand`

Build a tiny base class to share boilerplate:

```python
from PySide6.QtGui import QUndoCommand
from PySide6.QtCore import QPersistentModelIndex

class TreeCommand(QUndoCommand):
    def __init__(self, model, text):
        super().__init__(text)
        self.model = model
```

Then concrete commands:

```python
class SetValueCommand(TreeCommand):
    def __init__(self, model, index, new_value):
        super().__init__(model, "edit value")
        self.pidx = QPersistentModelIndex(index)
        self.new = new_value
        self.old = model.data(index, Qt.EditRole)

    def redo(self):
        idx = self.model.index(self.pidx.row(), self.pidx.column(), self.pidx.parent())
        self.model.setData(idx, self.new, Qt.EditRole)

    def undo(self):
        idx = self.model.index(self.pidx.row(), self.pidx.column(), self.pidx.parent())
        self.model.setData(idx, self.old, Qt.EditRole)

    def mergeWith(self, other):  # collapse rapid edits to same cell
        if isinstance(other, SetValueCommand) and other.pidx == self.pidx:
            self.new = other.new
            return True
        return False

    def id(self):  # required for mergeWith to be considered
        return 1001
```

Always store **`QPersistentModelIndex`** in commands, never raw
`QModelIndex` — rows shift around as siblings are added/removed.

### Insert / remove commands need a deep snapshot

Removing a subtree must remember it for undo:

```python
class RemoveRowsCommand(TreeCommand):
    def __init__(self, model, parent_index, position, count):
        super().__init__(model, "remove rows")
        self.pparent = QPersistentModelIndex(parent_index)
        self.position = position
        self.count = count
        # snapshot
        parent_item = model.get_item(parent_index)
        self.snapshot = [_clone_item(c) for c in parent_item.child_items[position:position+count]]

    def redo(self):
        ...
        self.model.removeRows(self.position, self.count, parent_index)

    def undo(self):
        ...
        # re-attach cloned items at self.position
```

`_clone_item(item)` should rebuild a fresh `JsonTreeItem` tree from
`item.to_json()` (no shared state with the live tree).

### Routing edits through the undo stack

The cleanest pattern: turn `JsonTab` into the *only* place where commands
are pushed. Replace direct `model.setData(...)` calls in delegates with
a tab-level helper:

```python
class JsonTab(QWidget):
    def __init__(...):
        self.undo_stack = QUndoStack(self)
        ...

    def commit_value(self, index, value):
        self.undo_stack.push(SetValueCommand(self.model, index, value))
```

Delegates emit a custom `valueCommitted` signal or call the helper
directly through `index.model().parent().commit_value(...)`. Either way,
the goal is: **no widget bypasses the undo stack**.

### Multi-selection actions

Qt convention: act on `selectionModel().selectedRows(0)` (column 0
indices, one per selected row). For Cut/Delete/Duplicate:

```python
indices = sorted(view.selectionModel().selectedRows(0),
                 key=lambda i: (i.parent().internalPointer() is whatever, i.row()),
                 reverse=True)
```

Reverse-sorting ensures `removeRows(i)` doesn't shift later indices.
Wrap the whole batch in a single `QUndoCommand` macro:

```python
self.undo_stack.beginMacro("delete selection")
for idx in indices:
    self.undo_stack.push(RemoveRowsCommand(model, idx.parent(), idx.row(), 1))
self.undo_stack.endMacro()
```

### Clipboard format

Use a single MIME type the editor recognises so paste round-trips
exactly:

```python
MIME_JSON_TREE = "application/x-json-tree"

def copy_subtree(items):
    payload = json.dumps([i.to_json() for i in items],
                         default=mpq_json_default, indent=2)
    md = QMimeData()
    md.setData(MIME_JSON_TREE, payload.encode("utf-8"))
    md.setText(payload)  # plain text fallback for external apps
    QApplication.clipboard().setMimeData(md)
```

On paste, prefer `MIME_JSON_TREE` if present (preserves type tags), fall
back to parsing plain text.

### Move up/down via `QAbstractItemModel.moveRow`

```python
def move_row(self, parent_index, src_row, dst_row):
    if src_row == dst_row:
        return False
    # Qt requires dst > src to be src+2 (post-removal index)
    qt_dst = dst_row if dst_row < src_row else dst_row + 1
    if not self.beginMoveRows(parent_index, src_row, src_row, parent_index, qt_dst):
        return False
    parent_item = self.get_item(parent_index)
    moved = parent_item.child_items.pop(src_row)
    parent_item.child_items.insert(dst_row, moved)
    self.endMoveRows()
    return True
```

The `qt_dst` adjustment is a Qt API quirk — easy to get wrong; cover with
a unit test.

### Sort Keys

Two-pass to keep undo cheap:

```python
class SortKeysCommand(TreeCommand):
    def __init__(self, model, index, recursive=False):
        super().__init__(model, "sort keys")
        self.pidx = QPersistentModelIndex(index)
        self.recursive = recursive
        self.old_orders = {}  # path -> list[str] of original key order

    def redo(self):
        item = self.model.get_item(self._idx())
        self._sort(item, "")

    def _sort(self, item, path):
        if item.json_type is JsonType.OBJECT:
            self.old_orders[path] = [c.name for c in item.child_items]
            item.child_items.sort(key=lambda c: c.name or "")
        if self.recursive:
            for c in item.child_items:
                self._sort(c, f"{path}/{c.name or c.row()}")
        self.model.layoutChanged.emit()

    def undo(self):
        # restore original orders by name lookup
        ...
```

`layoutChanged` is the broad-stroke signal for whole-subtree shuffles —
acceptable here. If perf matters, switch to per-parent `beginMoveRows`.

### Dialog delegates and undo

In `ValueDelegate.createEditor` for `MULTILINE`/`BYTES`/`ZLIB`/`GZIP`:

```python
pidx = QPersistentModelIndex(index)
def on_commit(payload):
    if not pidx.isValid():
        return  # row was deleted while dialog was open
    tab = view.parent()  # JsonTab via Qt parent chain
    tab.commit_value(pidx, payload)

QHexDialog(parent=parent, data=..., callback=on_commit).open()
return None
```

This kills both bugs simultaneously: stale-index writes and dialogs
that bypass undo.

## Risks / notes

- A `QUndoCommand` for an `OBJECT/ARRAY → primitive` type change has to
  remember the entire subtree to be reversible. Storage cost is
  acceptable because it is bounded by the user's edit history.
- Multi-selection editing: decide whether actions operate on the
  current index only or the full selection (Qt convention is usually
  full selection, with the menu disabled if the selection is
  inconsistent).
- Sort Keys is destructive without undo — make sure the undo command
  captures the original key order.
