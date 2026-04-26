# Phase 5.2 — Display formatting

## Goal

Render values in a human-friendly form without changing what editors
or saves see. Long strings elide; tooltips show full content; mpq /
PERCENT / bytes get pretty rendering.

## Entry criteria

- Phase 5.1 merged (dialogs commit through `commit_set_data`, decode
  failures don't escape).

## Exit criteria

- `JsonTreeModel.data(index, EditRole)` returns **raw** values
  (`mpq`, `int`, `bytes`-encoded `str`, `None`, …); editors and the
  model `setData` round-trip unchanged.
- `JsonTreeModel.data(index, DisplayRole)` keeps stringy fallback for
  generic clients (tests that rely on `str(...)`-shaped output stay
  green).
- `ValueDelegate.displayText` formats the rendered cell:
  - PERCENT → `"50%"` (using `:g`)
  - mpq FLOAT → `mpq_serialization(value)[0]`
  - long STRING / MULTILINE → first 80 chars + `…`
  - BYTES / ZLIB / GZIP → `"<24 byte>"` etc. via `units` helper
- Hovering a long cell shows the full content in a tooltip (≤ 4 KB).

## Work items

### Model role split
- [ ] [model] In `JsonTreeModel.data`, branch on role:
      - `EditRole` → return raw `item.data(column)` (no `str(...)`,
        no mpq serialization, no `"true"` lowercasing).
      - `DisplayRole` → keep current stringification path.
      - `ToolTipRole` for column 2 → return full value, capped at
        4096 chars (`+ "…"` if truncated).
      — `tree_model.py:JsonTreeModel.data`
- [ ] [tests] New unit test: `data(index, EditRole)` for an mpq float
      returns the raw `mpq`; for a None returns `None`; for a bool
      returns the actual `bool`. (Existing tests that assert on
      `DisplayRole` keep passing.)

### `units` helper
- [ ] [units] Add `format_bytes(n: int) -> str` to `units/__init__.py`
      as a thin alias delegating to `bits(n)` so the phase-doc API
      reads naturally. Keep `bits` for backward compatibility.
      — `units/__init__.py`

### `ValueDelegate.displayText`
- [ ] [delegate] Override `displayText(value, locale)`:
      - `value is None` → `"null"`.
      - `bool` → `"true"/"false"`.
      - `mpq` → `mpq_serialization(value)[0]`.
      - `str` len > 80 → `value[:80] + "…"`.
      - `bytes` → `f"<{units.format_bytes(len(value))}>"` (only if a
        bytes-typed value sneaks through; usual case is base64 str —
        see `paint` note).
      - else → `str(value)`.
      `displayText` does not have access to the index, so PERCENT and
      BYTES/ZLIB/GZIP need a small `paint()` override that fetches
      the item via `index.data(EditRole)` plus
      `index.data(Qt.UserRole + 1)` (a new `JsonTypeRole` exposed by
      the model) — or simpler: use `option.index` on Qt 6 (available
      via `option.index` in `QStyleOptionViewItem`).
      — `delegate.py:ValueDelegate.displayText`,
      `delegate.py:ValueDelegate.paint`
- [ ] [model] Define `JSON_TYPE_ROLE = Qt.ItemDataRole.UserRole + 1`
      and have `JsonTreeModel.data` return `item.json_type` for that
      role (column 2 only). This avoids fragile `option.index` use
      and keeps `displayText` purely presentational.
      — `tree_model.py`
- [ ] [delegate] In `displayText`, when stack has access to the type
      role (override `initStyleOption` to stash it onto
      `option.text`), format PERCENT and bytes-shaped types correctly.
      Concretely: override `initStyleOption(option, index)` and set
      `option.text = self._format(index)` where `_format` reads
      `index.data(EditRole)` and `index.data(JSON_TYPE_ROLE)`.
      — `delegate.py:ValueDelegate.initStyleOption`

### Tooltip plumbing
- [ ] [model] Already in the role split above; verify `view.setMouseTracking`
      is on (Qt default for `QTreeView` is fine) and the cell shows the
      tooltip on hover. No code change to `JsonTab` expected.
- [ ] [tests] New test: a 5000-char string row's tooltip data is exactly
      4097 chars and ends with `"…"`.

### Type column icons (deferred)
- This stays in the parent Phase 5 doc as a stretch goal; tracked
  separately. Not in 5.2 scope.

## Risks / notes

- Splitting `EditRole` to raw will break any test that previously
  assumed `data(EditRole)` returned a string. Audit
  `tests/` for `data(...EditRole...)` usages before merging.
- `displayText` runs per paint — keep `_format` allocation-free in the
  common case (short strings, ints).
- mpq formatting via `mpq_serialization` allocates a Decimal per call;
  cache by `id(value)` if profiling shows it dominates the paint path.
