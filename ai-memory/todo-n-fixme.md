# TODO & FIXME

_Last updated: **2026-06-01** (post code-quality audit). Minor smells
and speculative wishlist entries were pruned; only actionable,
meaningful work remains. Format:
`- [ ] [scope] description — file:symbol`._

## High priority — architecture (audit §8)

- [ ] [arch] Resolve the 11 `tree/` upward imports. Tracked in detail by
  `plans/refactor-tree-upward-imports.md`.
  — `tree/item.py`, `tree/item_coercion.py`, `tree/types.py`
- [ ] [tooling] Pin `pytest-qt` in `requirements.txt` and confirm the
  `make test` target runs `QT_QPA_PLATFORM=offscreen pytest -q`.
- [ ] [tests] `tests/test_value_delegate.py` — full delegate matrix:
  editor widget class per `JsonType`; `setEditorData` /
  `setModelData` round-trip for INTEGER, mpq FLOAT/PERCENT, BOOLEAN,
  DATE/TIME/DATETIME/DATETIMEZONE, STRING/UNICODE; dialog delegates
  (MULTILINE/TEXT/BYTES/ZLIB/GZIP) commit via `QPersistentModelIndex`
  + `JsonTab.commit_set_data`.
- [ ] [tests] `tests/test_io_roundtrip.py` — parametrized load → mutate
  → save → reload property tests against `data.json` / `data.yaml`
  (+ JSONL / YAML-multi), asserting mpq and tz-aware datetimes
  survive every format.

## Medium priority

- [ ] [refactor] Split `tree_actions/structure.py` (774 lines) into
  `structure_insert` / `structure_move` / `structure_sort` /
  `structure_expand`.
- [ ] [refactor] Extract a `FileOperationsPresenter` from
  `app/main_window.py` (637 lines): `_confirm_reload_dirty_tab`,
  `_reload_tab_from_path`, `_save_tab`.
- [ ] [hygiene] Narrow `IoController.save()` exception handling — catch
  specific I/O / serialization errors and surface structured
  diagnostics for malformed datetime / bytes.
  — `documents/states/io_controller.py:54`
- [ ] [tests] Model invariants: `setData` emits `dataChanged` covering
  cols 0..2; `removeRows` updates persistent indices; 3-level
  `parent()`/`index()` round-trip; `change_type` `lossy=True` only
  with prior children; `unique_child_name` collision avoidance.

## Low priority — hygiene & dead code (audit §6)

- [ ] [hygiene] Remove deprecated shims `_closed_tabs_stack` /
  `_MAX_CLOSED_TABS` and the no-op stubs `_setup_validation_dock` /
  `_setup_schemas_menu` once tests migrate.
  — `app/main_window.py:200-204,356-358`
- [ ] [hygiene] Rename underscore-prefixed helpers re-exported across
  `tree_actions/` (`_resolve_model`, `_to_source_index`, …) — they
  are a shared internal API, not module-private.
  — `tree_actions/selection.py`
- [ ] [tests] Add a `Document`-protocol conformance check (mypy or a
  dedicated test) verifying `JsonTab` implements every `Document`
  attribute.
- [ ] [tooling] Add `pytest-cov` and commit a coverage snapshot to
  `ai-memory/coverage.md`.
- [ ] [smell] `JsonTreeItem.row()` returns `0` for the root; return `-1`
  to signal "no parent". — `tree/item.py:73`
- [ ] [smell] `ValueDelegate.createEditor` raises `ValueError` for
  OBJECT/ARRAY/NULL (unreachable via `flags()`); `return None`
  degrades more gracefully. — `editors/factory.py:232`

## Feature follow-ups (deferred)

- [ ] [secret] Persist secret kind for non-matching field names
  (schema-sidecar / metadata) so sticky secrets survive
  rename + reload. — `tree/item.py`, `io_formats/{dump,load}.py`
- [ ] [secret, security] Clipboard scrubbing for revealed secrets
  (clear/expire after copy). — `tree_actions/clipboard.py`
- [ ] [validation] URL schema staleness — add `ETag` /
  `If-Modified-Since` conditional requests on `reload()`.
  — `validation/schema_registry.py`, `validation/schema_source.py`
- [ ] [validation] Remote `$ref` resolution against `http(s)://`
  (currently silently ignored). — `validation/schema_source.py`,
  `validation/_engine.py`
- [ ] [ux] Match-highlight delegate (`ValueDelegate.paint` yellow span
  over substring matches when a filter is active).
  — `delegates/value.py`
- [ ] [docs] README theming section + `themes/builtin/schema.md`
  (YAML grammar, fallback semantics, icon path resolution, worked
  examples).
