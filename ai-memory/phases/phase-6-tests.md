# Phase 6 — Tests

## Goal

Bring test coverage of the **GUI / model layer** up to the level of the
existing widget packages. The widget stack (datetime, hex, mpq,
jsontream) is well covered; the JSON tree editor itself is not.

## Entry criteria

- Phases 0–5 complete. Behaviour is stable enough to write
  regression tests against.

## Exit criteria

- `pytest -q` covers the model, item, delegates, file I/O, and at
  least one end-to-end GUI smoke flow.
- CI-equivalent target in `Makefile` (`make test`) runs the suite
  headlessly with `QT_QPA_PLATFORM=offscreen`.
- A coverage report (text-only is fine) is generated and committed to
  `ai-memory/coverage.md` (or similar).

## Work items

### Model / item unit tests
- [ ] [tests] `tests/test_tree_item.py`
      - construction from dict / list / scalar
      - `to_json` round-trip including `mpq`, datetimes, bytes
      - `set_data(0/1/2, ...)` for rename, type change, value change
      - `insert_children` produces a single NULL row
      - duplicate-name rejection under OBJECT
- [ ] [tests] `tests/test_tree_model.py`
      - `flags()` is O(1) and never raises on malformed bytes payloads
      - `rowCount` / `columnCount` / `parent` / `index` invariants
      - `setData` emits `dataChanged`
      - `removeRows` updates persistent indices correctly
      - `setData` on a malformed BYTES cell doesn't crash flags
- [ ] [tests] `tests/test_enums_parse.py`
      - boundary cases for `parse_json_type`: short strings, ambiguous
        base64, datetimes with/without TZ, nested types, unknown types
        (do not raise)
      - explicit-type pinning honoured

### Delegate tests
- [ ] [tests] `tests/test_value_delegate.py` (uses `pytest-qt`)
      - editor type matches `JsonType`
      - `setEditorData` / `setModelData` round-trip integers, mpq,
        booleans, datetimes
      - dialog-based delegates (multiline / hex) commit through
        `QPersistentModelIndex`
- [ ] [tests] `tests/test_type_delegate.py`
      - combo preselects current type
      - `setModelData` triggers a model-level type change

### File I/O tests
- [ ] [tests] `tests/test_io_roundtrip.py`
      - JSON: load `data.json`, mutate, save, reload — equal
      - YAML: same with `data.yaml`
      - mpq values survive both formats
      - datetimes survive both formats with TZ intact
- [ ] [tests] `tests/test_dirty_state.py`
      - dirty flips on edit, clears on save, clears on undo-to-clean

### GUI smoke (`pytest-qt`)
- [ ] [tests] `tests/test_smoke_app.py`
      - launch `MainWindow(filename)` with offscreen QPA
      - open a sample file, expand all, resize columns, no exception
      - trigger every menu/toolbar action that does not require user
        input; assert no exception and dirty/undo states remain
        consistent
      - close the app — confirm dialog suppressed in test mode

### Tooling
- [ ] [tooling] Add `pytest-qt` to `requirements.txt`.
- [ ] [tooling] Add a `make test` target running
      `QT_QPA_PLATFORM=offscreen pytest -q`.
- [ ] [tooling] Add `coverage`/`pytest-cov` and produce a short
      summary committed to `ai-memory/coverage.md`.

## Risks / notes

- `pytest-qt` brings in a `qtbot` fixture that conflicts with bare
  `QApplication` constructed in `main.py`. Tests should always use
  `qtbot.app` rather than instantiating a second `QApplication`.
- Headless `offscreen` mode hides clipboard access — tests for
  copy/paste should mock `QApplication.clipboard()` or use
  `QGuiApplication.clipboard().setText`.
- File I/O round-trip tests should write to `tmp_path`, never to the
  repo's `data.json` / `data.yaml`.
