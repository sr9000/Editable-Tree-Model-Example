# Phase 1 — Tree / Model Correctness

## Goal

Make the tree model behave correctly for all JSON shapes: inserting,
removing, naming, and serializing nodes. After this phase the data layer
must be **trustworthy** — Phases 2–5 will build editing and I/O on top of
it, and they must not have to re-fix model bugs.

## Entry criteria

- Phase 0 complete: tests green, no crashes, dead code removed.

## Exit criteria

- Inserting a row produces a single blank `JsonType.NULL` node, not an
  ARRAY-of-NULLs.
- Inserting a row under an `OBJECT` parent yields a unique, valid
  string name; round-tripping via `to_json()` produces valid JSON.
- `JsonTreeItem.to_json()` never emits `{None: ...}`.
- `JsonTreeModel.flags()` is O(1) and never decodes/decompresses
  payloads.
- `parse_json_type()` does not raise on unknown types — it returns a
  sentinel (e.g. `JsonType.STRING`) or a new `JsonType.UNKNOWN`, and
  callers handle it.
- `insertColumns` / `removeColumns` either do nothing (no Qt signals
  emitted) or are removed entirely from `JsonTreeModel`.

## Work items

### Insertion semantics
- [ ] [BUG] Fix `JsonTreeItem.insert_children` to seed new rows as a
      single blank node (`value=None`, `name=None`, `json_type=NULL`),
      not `value=[None]*columns`.
      — `tree_item.py:JsonTreeItem.insert_children`
- [ ] [tree] When inserting under an `OBJECT` parent, auto-generate a
      unique name (e.g. `new_key`, `new_key_2`, ...). Expose it via a
      helper `JsonTreeItem._unique_child_name(base="new_key")`.
- [ ] [tree] When inserting under an `ARRAY` parent, leave `name=None`
      but ensure indices are derived from `row()` at serialization time.
- [ ] [tree] Make `model_actions.action_insert_row` / `action_insert_child`
      stop calling `setData(child, "[No data]", ...)` — that string is a
      hold-over from the original Qt example and conflicts with typed
      JSON values.
      — `model_actions.py`

### Cache `json_type` on mutation
- [ ] [tree] When `JsonTreeItem.set_data(2, value)` runs, recompute
      `self.json_type = parse_json_type(value)` so the type cell stays
      consistent with the value.
      — `tree_item.py:JsonTreeItem.set_data`
- [ ] [tree] Add a unit test confirming that setting an INTEGER cell to
      `"hello"` flips `json_type` to STRING.

### `flags()` hot-path
- [ ] [BUG] Move the b64/zlib/gzip decode out of
      `JsonTreeModel.flags()` and into `JsonTreeItem` as a cached
      `editable: bool` field, recomputed only on `set_data()`.
      Catch `binascii.Error` / `zlib.error` / `OSError` and treat
      malformed payloads as **not editable** rather than crashing the
      row.
      — `tree_model.py:JsonTreeModel.flags`,
        `tree_item.py:JsonTreeItem`

### Type detection robustness
- [ ] [BUG] Make `parse_json_type` total: never raise. For unsupported
      Python types fall back to `JsonType.STRING` (storing `repr(value)`)
      and log a warning.
      — `enums.py:parse_json_type`
- [ ] [tree] Skip the `BYTES` branch unless the candidate string passes a
      stricter heuristic (e.g. length ≥ 16, only base64 alphabet, padding
      multiple of 4, not a known datetime). Otherwise treat as `STRING`.
- [ ] [tree] Skip the `MULTILINE` branch when the string is short
      (< 80 chars and ≤ 1 newline) — keep `STRING` for simple multi-word
      cases.
- [ ] [tree] Narrow the `PERCENT` heuristic: only when the original
      source explicitly tagged it (or an `mpq` denominator is `100`,
      `1000`, ...). Avoid auto-promoting `0.5` from a probability-style
      JSON document.

### Dead column API
- [ ] [BUG] Remove `JsonTreeModel.insertColumns` /
      `removeColumns` / `setHeaderData` (and the matching `JsonTreeItem`
      methods) — they always fail and emit misleading Qt signals. Or, if
      kept, make them return `False` *without* calling
      `beginInsertColumns`/`endInsertColumns`.
      — `tree_model.py`, `tree_item.py`
- [ ] [tree] Remove `model_actions.action_insert_column` and the
      "Insert Column" entries from the context menu and toolbar.
      — `model_actions.py`, `tree_view.py`, `mainwindow.ui`

### Serialization correctness
- [ ] [BUG] In `JsonTreeItem.to_json()`, raise a clear `ValueError` (not
      a silent `{None: value}`) if a child of an `OBJECT` has `name=None`.
      Phase 2 will guarantee this never happens through the UI; for now
      we just want loud failure.

## Tips & Deep Dives

### Why insertion is currently broken

`model_actions.action_insert_row` calls `model.insertRow(...)`, which
ends up at `JsonTreeItem.insert_children(position, count, columns=3)`.
Today the inserted child is built via:

```python
JsonTreeItem(parent_item=self, value=[None] * columns)
```

Because `value` is a `list`, `parse_json_type` classifies the new node
as `JsonType.ARRAY`, which then expands `[None, None, None]` into three
`NULL` children. The fix is **stop using `insertRows` to inject typed
defaults via the column API** and instead pass `value=None`:

```python
def insert_children(self, position: int, count: int, _columns: int = 0) -> bool:
    if not (0 <= position <= len(self.child_items)):
        return False
    new_items = []
    for offset in range(count):
        name = self._unique_child_name() if self.json_type is JsonType.OBJECT else None
        new_items.append(JsonTreeItem(parent_item=self, value=None, name=name))
    self.child_items[position:position] = new_items
    return True
```

The `_columns` argument is preserved for ABI parity with the Qt API but
ignored — drop it later in Phase 1's "Dead column API" task.

### `_unique_child_name`

```python
def _unique_child_name(self, base: str = "new_key") -> str:
    used = {c.name for c in self.child_items if c.name is not None}
    if base not in used:
        return base
    i = 2
    while f"{base}_{i}" in used:
        i += 1
    return f"{base}_{i}"
```

Run unit tests with multiple inserts in a row to confirm names don't
collide.

### Caching `editable` on `JsonTreeItem`

```python
class JsonTreeItem:
    EDITABLE_BLOB_LIMIT = 10_000

    def __init__(self, ...):
        ...
        self._editable = self._compute_editable()

    def _compute_editable(self) -> bool:
        if self.json_type in (JsonType.NULL, JsonType.ARRAY, JsonType.OBJECT):
            return False
        try:
            match self.json_type:
                case JsonType.STRING | JsonType.MULTILINE:
                    return len(self.value) <= self.EDITABLE_BLOB_LIMIT
                case JsonType.BYTES:
                    raw = base64.b64decode(self.value, validate=True)
                    return len(raw) <= self.EDITABLE_BLOB_LIMIT
                case JsonType.ZLIB:
                    raw = base64.b64decode(self.value, validate=True)
                    return len(zlib.decompress(raw)) <= self.EDITABLE_BLOB_LIMIT
                case JsonType.GZIP:
                    raw = base64.b64decode(self.value, validate=True)
                    return len(gzip.decompress(raw)) <= self.EDITABLE_BLOB_LIMIT
                case _:
                    return True
        except (binascii.Error, zlib.error, OSError, ValueError):
            return False  # malformed payload → not editable, but don't crash flags()
```

Then `JsonTreeModel.flags()` reduces to a constant-time check:

```python
def flags(self, index):
    if not index.isValid():
        return Qt.ItemFlag.NoItemFlags
    base = QAbstractItemModel.flags(self, index)
    if index.column() != 2:
        return base
    item = index.internalPointer()
    return base | Qt.ItemFlag.ItemIsEditable if item._editable else base
```

Recompute `_editable` from `set_data()` whenever value or type changes.
Document this contract on the class.

### Stricter base64 detection

A single `base64.b64decode(..., validate=True)` is too permissive — many
short Latin words (`"abcd"`, `"test"`) round-trip cleanly. Layered
heuristic:

```python
import re
_B64_RE = re.compile(r"^[A-Za-z0-9+/]+={0,2}$")

def _looks_like_base64(s: str) -> bool:
    if len(s) < 16 or len(s) % 4 != 0:
        return False
    if not _B64_RE.fullmatch(s):
        return False
    # Also require either padding or one byte that isn't a typical text char
    raw = base64.b64decode(s, validate=True)
    text_ratio = sum(32 <= b < 127 for b in raw) / max(len(raw), 1)
    return text_ratio < 0.85  # mostly non-text → probably bytes
```

This still catches actual binary blobs while rejecting ASCII tokens.

### Narrowing `MULTILINE`

```python
if "\n" in s and (s.count("\n") > 1 or len(s) > 80):
    return JsonType.MULTILINE
```

A trailing-newline `"hi\n"` stays `STRING`.

### Narrowing `PERCENT`

```python
case gmpy2.mpq():
    num, den = value.as_integer_ratio()
    if den in (100, 1000, 10_000) and 0 <= value <= 1:
        return JsonType.PERCENT
    return JsonType.FLOAT
```

For native `float` in `[0, 1]`, simply do **not** auto-promote. PERCENT
becomes opt-in via the type column in Phase 2.

### Removing the column API safely

`JsonTreeModel.insertColumns/removeColumns` currently emit
`beginInsertColumns`/`endInsertColumns` *around* a no-op result. Even
when removing the methods, double-check that nothing in the codebase
calls `model.insertColumn(...)` and silently no-ops:

```bash
grep -rn "insertColumn\|removeColumn\|setHeaderData" *.py
```

Today the only callers are `model_actions.action_insert_column` and
`action_insert_child` (which calls `insertColumn(0, index)` when
`columnCount(index) == 0`). Since `columnCount()` is constant `3`, that
branch is dead — `action_insert_child` can drop it entirely.

### `to_json` strictness

```python
def to_json(self):
    match self.json_type:
        case JsonType.ARRAY:
            return [c.to_json() for c in self.child_items]
        case JsonType.OBJECT:
            for c in self.child_items:
                if c.name is None:
                    raise ValueError(f"OBJECT child has no name (row {c.row()})")
            return {c.name: c.to_json() for c in self.child_items}
    return self.value
```

Loud failure beats silent `{None: ...}` corruption.

## Risks / notes

- The `flags()` rework affects every row repaint — benchmark with a
  10k-row document before merging.
- Narrowing `PERCENT` and `BYTES` heuristics is **breaking** for the
  current demo data in `JsonTab`. Update the demo accordingly so
  manual smoke testing still shows all editor types.
- Cached `editable` must be invalidated whenever `value` or `json_type`
  changes; document this contract on `JsonTreeItem`.
