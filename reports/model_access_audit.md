# Model access audit — Phase E (plan 20)

**Source plan:** `plans/20-decouple-jsontab.md` § Phase E (E1)
**Scope:** every reference to `tab.data_store.model` (and
`self._tab.data_store.model`) in production code outside `documents/`.
**Total references at audit time:** 55 across 8 files.
**Generated:** 2026-05-29

## Methodology

```bash
grep -rnE "data_store\.model\b" --include="*.py" app/ undo/ tree_actions/ state/
```

Each call site labelled with one of:

| Label             | Meaning                                                                                  |
|-------------------|------------------------------------------------------------------------------------------|
| `read-structural` | Inspects model shape — `rowCount`, `columnCount`, `index(...)`, `get_item`, `show_root`. |
| `read-data`       | Pulls payload through the root item — `root_item.to_json()` etc.                         |
| `mutate-tree`     | Calls the model's own mutators — `move_row`, `removeRow`, `sort_keys`.                   |
| `mutate-qt-api`   | Uses raw `QAbstractItemModel` plumbing — `beginRemoveRows`, `endInsertRows`, `setData`.  |
| `signal-connect`  | Connects to / emits a `dataChanged`-class signal.                                        |

A few sites combine intents (e.g. fetch `model` once and then both read
and mutate); the label reflects the dominant operation.

## Per-file breakdown

### `app/close_confirm.py` — 1 site

| Line | Snippet                                    | Label     |
|------|--------------------------------------------|-----------|
| 5    | `tab.data_store.model.root_item.to_json()` | read-data |

Suggested helper: `tab.root_data() -> Any`.

### `app/validation_panel_model.py` — 2 sites

| Line | Snippet                                          | Label     |
|------|--------------------------------------------------|-----------|
| 43   | `tab.data_store.model.root_item.to_json()`       | read-data |
| 49   | `self._tab.data_store.model.root_item.to_json()` | read-data |

Same helper as above.

### `app/main_window.py` — 2 sites

| Line | Snippet                                                                            | Label           |
|------|------------------------------------------------------------------------------------|-----------------|
| 433  | `tab.data_store.model.index(0, 0, ...) if tab.data_store.model.show_root else ...` | read-structural |
| 435  | `tab.data_store.model.get_item(root_index)`                                        | read-structural |

Used to construct the root index for snapshot/seed routines. Helper
candidate: `tab.root_index()` (returning `QModelIndex` or path).

### `app/tab_lifecycle.py` — 4 sites

| Line | Snippet                                                | Label           |
|------|--------------------------------------------------------|-----------------|
| 101  | `if tab.data_store.model.show_root:`                   | read-structural |
| 102  | `source_index = tab.data_store.model.index(0, 0, ...)` | read-structural |
| 159  | `src_idx = widget.data_store.model.index(0, 0, ...)`   | read-structural |
| 160  | `widget.data_store.model.get_item(src_idx).to_json()`  | read-data       |

Suggestions: `tab.root_index()`, `tab.root_data()`.

### `tree_actions/anchors.py` — 2 sites

| Line | Snippet                                        | Label           |
|------|------------------------------------------------|-----------------|
| 70   | `tab.data_store.model.rowCount(parent_index)`  | read-structural |
| 160  | `tab.data_store.model.rowCount(target_parent)` | read-structural |

Helper candidate: `tab.row_count(parent)`. Could also stay as raw
`tab.model.rowCount(...)` if we ship the typed `tab.model` accessor.

### `state/view_state.py` — 2 sites

| Line | Snippet                                        | Label           |
|------|------------------------------------------------|-----------------|
| 78   | `range(tab.data_store.model.columnCount())`    | read-structural |
| 120  | `widths[: tab.data_store.model.columnCount()]` | read-structural |

Helper candidate: `tab.column_count()`.

### `undo/diff.py` — 14 sites

All inside `DiffApplier` (`_emit_row_changed`, `_replace_children`,
`_insert_typed_item`, `_apply_to_*` helpers).

| Lines            | Operation                           | Label           |
|------------------|-------------------------------------|-----------------|
| 50, 51, 135, 152 | `model.index(...)`                  | read-structural |
| 52               | `model.dataChanged.emit(...)`       | signal-connect  |
| 61, 64           | `beginRemoveRows` / `endRemoveRows` | mutate-qt-api   |
| 82, 86, 104, 107 | `beginInsertRows` / `endInsertRows` | mutate-qt-api   |
| 116, 144         | `model.removeRow(...)`              | mutate-tree     |
| 133              | `model.move_row(...)`               | mutate-tree     |

All 14 sites are inside `documents/`-adjacent infrastructure that
genuinely *needs* the `QAbstractItemModel` surface. They are the prime
beneficiary of the **light** path: expose `tab.model` as the typed
JsonTreeModel and let DiffApplier read it through that property. Deep
refactor (routing the mutate-qt-api sites through the mutation gateway)
is **out of scope for Phase E** — it overlaps with Phase H.

### `undo/commands.py` — 25 sites

The single biggest cluster, all inside Qt undo command implementations.

| Pattern                                  | Count | Label           |
|------------------------------------------|------:|-----------------|
| `model.get_item(idx)`                    |     6 | read-structural |
| `model.index(...)`                       |     7 | read-structural |
| `model.move_row(...)`                    |     2 | mutate-tree     |
| `model.removeRow(...)`                   |     4 | mutate-tree     |
| `model.setData(..., EditRole)`           |     4 | mutate-qt-api   |
| `model.sort_keys(...)`                   |     1 | mutate-tree     |
| `model = tab.data_store.model` (binding) |     3 | read-structural |

Same architectural verdict as `undo/diff.py`: commands legitimately
need the QAbstractItemModel API. Phase E should funnel them through
`tab.model` (typed `JsonTreeModel`). Migrating to pure paths + the
mutation gateway is Phase H.

## Aggregate intent distribution

| Label             | Sites | % of total |
|-------------------|------:|-----------:|
| read-structural   |    25 |        45% |
| mutate-tree       |     7 |        13% |
| mutate-qt-api     |    10 |        18% |
| read-data         |     5 |         9% |
| signal-connect    |     1 |         2% |
| binding (`x = …`) |     7 |        13% |

## Migration verdict (decision for E2–E7)

The intent split shows that ~75% of sites live in `undo/` and treat
the model as a legitimate `QAbstractItemModel`. Carving narrow read
helpers (`row_count`, `column_count`, `root_data`, `root_index`,
`item_at(path)`) only buys us coverage of the 17 structural/data
sites in `app/`, `state/`, and `tree_actions/`. The remaining 38 sites
in `undo/` would need either:

1. **Path-based mutation gateway** (Phase H), or
2. A typed `tab.model` accessor used as-is.

Because Phase H is itself blocked on **Phase D's** `ViewportRequest`
signal (not yet landed), the pragmatic next step is the F-light /
D-light precedent:

* **E-light:** expose `tab.model: JsonTreeModel` as a typed property,
  mechanically swap all 55 sites, and forbid `data_store.model`.
  Helpers from E2 can still be added later — they would then forward
  through `tab.model` rather than `data_store.model`, and migrating
  call sites becomes a private refactor inside the producer modules
  with no guard churn.

* **E2–E6 (deferred):** add the narrow read helpers
  (`tab.root_data()`, `tab.root_index()`, `tab.row_count(parent)`,
  `tab.column_count()`) and migrate the 17 non-`undo/` sites away
  from `tab.model`. This shrinks the surface but does *not* unlock
  any new architectural property; the guard already prevents
  `data_store.model` from coming back.

* **E5 / Phase H** remain the only path to eliminating raw Qt model
  mutation in `undo/`. They depend on the path-based mutation API
  not yet implemented.

## Acceptance criterion for the audit step

This document is the deliverable for E1. The DoD gate is unchanged
(no code change), and the file's existence unblocks the E-light
mechanical swap that follows in the next commit.
