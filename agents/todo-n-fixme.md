# TODO & FIXME

_Last updated: **2026-09-06**. Open work only — completed items are deleted, not
archived. Format: `- [ ] [scope] description — file:symbol`. Reference symbols,
not line numbers: line numbers rot silently._

## High priority

- [ ] [ci] No CI job runs the test suite. `no-reflection.yml` runs only the
  reflection check and the `requirements.txt` freshness check, and
  `release.yml` is `workflow_dispatch`-only, so the whole gate is local-only and
  a pull request can pass having run nothing but a grep.
  — `.github/workflows/no-reflection.yml`
- [ ] [tests] `tests/test_value_delegate.py` — full delegate matrix: editor
  widget class per `JsonType`; `setEditorData` / `setModelData` round-trip for
  INTEGER, mpq FLOAT/PERCENT, BOOLEAN, DATE/TIME/DATETIME/DATETIMEZONE,
  STRING/UNICODE; dialog delegates (MULTILINE/TEXT/BYTES/ZLIB/GZIP) commit via
  `QPersistentModelIndex` + `JsonTab.commit_set_data`.
- [ ] [tests] `tests/test_io_roundtrip.py` — parametrized load → mutate → save →
  reload property tests against `data.json` / `data.yaml` (+ JSONL /
  YAML-multi), asserting mpq and tz-aware datetimes survive every format.

## Medium priority

- [ ] [refactor] Split `tree_actions/structure.py` (774 lines) into
  `structure_insert` / `structure_move` / `structure_sort` / `structure_expand`.
- [ ] [refactor] Extract a `FileOperationsPresenter` from `app/main_window.py`
  (560 lines): `_confirm_reload_dirty_tab`, `_reload_tab_from_path`, `_save_tab`.
- [ ] [hygiene] Narrow `IoController.save()` exception handling — catch specific
  I/O and serialization errors and surface structured diagnostics for malformed
  datetime / bytes. — `documents/states/io_controller.py:IoController.save`
- [ ] [tests] Model invariants: `setData` emits `dataChanged` covering cols 0..2;
  `removeRows` updates persistent indices; 3-level `parent()`/`index()`
  round-trip; `change_type` `lossy=True` only with prior children;
  `unique_child_name` collision avoidance.

## Low priority — hygiene

- [ ] [tooling] `make lint` runs bare `autoflake .`, which without `--in-place`
  only prints diffs and never modifies files — the step has always been a silent
  no-op. Decide whether to drop it or enable it (`--in-place
  --remove-all-unused-imports`); enabling it rewrites imports across the tree, so
  it needs its own commit. — `Makefile:lint`
- [ ] [tooling] Replace the **file:line** allowlist in
  `.githooks/_check_tree_isolation.sh` with a marker comment (e.g. an inline
  `# allow: <reason>`, matching the reflection hook's convention). The current
  form breaks or silently exempts the wrong import whenever an edit shifts a
  line. — `.githooks/_check_tree_isolation.sh`
- [ ] [tooling] Commit a coverage snapshot to `agents/coverage.md`; `pytest-cov`
  is already declared in the Poetry `test` group.
- [ ] [hygiene] Rename the underscore-prefixed helpers re-exported across
  `tree_actions/` (`_resolve_model`, `_to_source_index`, …) — they are a shared
  internal API, not module-private. — `tree_actions/selection.py`
- [ ] [tests] Add a `Document`-protocol conformance check (mypy or a dedicated
  test) verifying `JsonTab` implements every `Document` attribute.
- [ ] [smell] `JsonTreeItem.row()` returns `0` for the root; return `-1` to
  signal "no parent". — `tree/item.py:JsonTreeItem.row`
- [ ] [smell] `create_value_editor` raises `ValueError` for OBJECT/ARRAY/NULL
  (unreachable via `flags()`); `return None` degrades more gracefully.
  — `editors/factory.py:create_value_editor`

## Feature follow-ups (deferred)

- [ ] [secret] Persist secret kind for non-matching field names (schema-sidecar /
  metadata) so sticky secrets survive rename + reload. — `tree/item.py`,
  `io_formats/{dump,load}.py`
- [ ] [secret, security] Clipboard scrubbing for revealed secrets (clear/expire
  after copy). — `tree_actions/clipboard.py`
- [ ] [validation] URL schema staleness — add `ETag` / `If-Modified-Since`
  conditional requests on `reload()`. — `validation/schema_registry.py`,
  `validation/schema_source.py`
- [ ] [validation] Remote `$ref` resolution against `http(s)://` (currently
  silently ignored). — `validation/schema_source.py`, `validation/_engine.py`
- [ ] [ux] Match-highlight delegate (`ValueDelegate.paint` yellow span over
  substring matches when a filter is active). — `delegates/value.py`
- [ ] [docs] README theming section + `themes/builtin/schema.md` (YAML grammar,
  fallback semantics, icon path resolution, worked examples).
