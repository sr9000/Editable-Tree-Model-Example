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

## Risks / notes

- The `flags()` rework affects every row repaint — benchmark with a
  10k-row document before merging.
- Narrowing `PERCENT` and `BYTES` heuristics is **breaking** for the
  current demo data in `JsonTab`. Update the demo accordingly so
  manual smoke testing still shows all editor types.
- Cached `editable` must be invalidated whenever `value` or `json_type`
  changes; document this contract on `JsonTreeItem`.
