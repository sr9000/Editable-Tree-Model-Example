# JSON Editor — Pros & Cons

_Last analysis: **2026-09-06** (branch `migrate-to-poetry-py314`). Carries
forward the 2026-06-01 architecture audit (overall grade **A−**); that review's
report file has since been removed from `reports/`._

A PySide6 desktop **structured-data editor** (JSON / JSONL / YAML / YAML-multi)
built on a three-column `Name | Type | Value` tree model, with exact-rational
numerics (`gmpy2.mpq`), a typed undo/redo system, JSON-Schema validation, and a
theming stack. See `repo-map.md` for the module breakdown.

_Test surface: see `AGENTS.md` §7 for the expected count. `make gate` runs lint
→ `check-no-reflection` (which chains data-store leaks, JsonTab-import leaks,
editors isolation, and tree isolation) → tests._

---

## ✅ Pros

### Architecture & responsibility segregation (audit grade A−)

- **`JsonTab` is a genuinely thin facade** (222 lines) — its `__init__` is a
  single `tab_init.bootstrap()` call; every method routes to a controller,
  state, or seam. `documents/` is a textbook facade + controllers + states +
  seams layout.
- **Single mutation chokepoint** — `DocumentMutationGateway` is the *only* entry
  point for tree edits. Every rename / edit / type-change / insert / remove /
  move / sort / case-switch flows through `commit_set_data` or a `push_*` method
  into a typed `QUndoCommand`. Read-only state is triple-guarded.
- **Narrow, typed seams** — `@runtime_checkable` `Document` protocol,
  `TreeModelLike`, `JsonTabHost`, `EditorContextProtocol` /
  `ValueDelegateProtocol`. Consumers depend on protocols, not concrete classes.
- **Isolation enforced by CI** — `tree/` does not import upward, and concrete
  editors import nothing from `app/`, `documents/`, or `tree/`. Both are hooks,
  not conventions.
- **Reflection ban enforced by CI** — `getattr` / `hasattr` / `TYPE_CHECKING` /
  `AttributeError` forbidden outside a three-file allowlist.
- **Clean dependency injection** — `JsonTabServices` frozen dataclass +
  `JsonTabHost` protocol; no framework.
- **Strong module cohesion (audit grade A)** — every module has a single clear
  purpose; `state/` modules are focused QSettings wrappers.

### Type system & numerics

- **Rich `JsonType` enum** (34 members) — the scalar kinds plus number-affix,
  secret, color, and derived pseudo-text (`EMPTY_*` / `WS_*`) families. This is a
  structured-data editor, not just a JSON editor.
- **Centralized type logic** — `tree/types.py` (inference) and
  `tree/item_coercion.py` (conversion) are the single source of truth; type logic
  does not leak into the UI.
- **Total, conservative detection** — `parse_json_type` falls back to STRING with
  a logged warning; datetime is checked before bytes; type pinning
  (`explicit_type`) keeps base64-like and newline strings as plain STRING.
- **Exact numeric arithmetic** — `gmpy2.mpq` end-to-end via `QBigIntSpinBox` /
  `QMpqSpinBox`; no float precision loss in storage or display; round-trips
  across all four formats via `mpq2py`.
- **UTC datetime** — `DATETIMEUTC` with `Z` suffix and a full conversion lattice,
  including a real tz-shift on `DATETIMEZONE → DATETIMEUTC`. Nanosecond stepping
  (1–9 fraction digits) preserves the user's original format.
- **Number affixes** — frozen `NumberAffix(kind, affix, space, number)` with
  `number: int | mpq`, composite editor, per-tab affix MRU, JSON/YAML round-trip
  (only strings that re-parse are promoted back).
- **Secret strings** — `SECRET_LINE/_TEXT`, never auto-classified as a non-secret
  kind; name-driven promotion with runtime-configurable prefixes; masked
  rendering with a fixed glyph count so length never leaks; reveal-toggle editors
  with focus-out auto-hide.
- **Pseudo-text family** — empty / whitespace-only strings surface as visible
  chips without changing editable behaviour.

### Undo / redo

- **Typed-command system (audit grade A)** — 8 `QUndoCommand` subclasses with
  path-based addressing (sidesteps `QModelIndex` invalidation); `DiffApplier`
  emits minimal `dataChanged` signals so expansion and selection survive
  undo/redo.
- **`mergeWith` collapsing** — same-path renames / value edits within 500 ms
  collapse into one undo step.
- **Anchor-based moves** — every move (keyboard, drag-drop, paste cleanup) feeds
  one `MoveAnchor` into `push_move_rows_anchor`.
- **Viewport via signal** — undo commands never call `setCurrentIndex` directly;
  they emit `viewportRequested(kind, payload)`.

### UX / functional features

- **Multi-format file I/O** — JSON, JSONL/NDJSON, YAML, YAML-multi; atomic writes
  via `os.replace`.
- **File UX** — Reload from Disk (`Ctrl+R`, dirty-aware), Close (`Ctrl+W`) /
  Reopen Closed Tab (`Ctrl+Shift+T`, LIFO ×10), New From Clipboard
  (`Ctrl+Space`), Copy-as-YAML toggle, search-aware Go To, dirty-aware Save.
- **Drag-and-drop with multi-selection** — move/copy between OBJECT/ARRAY
  containers; Ctrl-drag copies; cycle guard via MIME `source_paths`; leaf-drop
  becomes sibling-after. Expansion survives moves and undo/redo.
- **Multi-action paste** — `Ctrl+V`, `Ctrl+Shift+V` (insert-after-zip),
  `Ctrl+Alt+V` (replace-zip).
- **Keyboard multimove** — `Alt+Up/Down` with parent-boundary bubble-out;
  `Ctrl+Alt+Up/Down` promote-out.
- **Smart kind-switch coercion** — bool→str lowercase, datetime→`"now"` fallback,
  int↔datetime, lossless cross-format bytes re-encode, ARRAY↔OBJECT child
  preservation.
- **Type-aware presentation** — PERCENT `50%`, BYTES `<24 byte>`, mpq exact
  decimal, 80-char elision, container preview when collapsed, 4 KB tooltips,
  breadcrumb status bar.
- **Per-file persisted view state** — column widths, expansion, selection, font
  zoom (SHA1-keyed, 5000-entry cap).
- **Base64 cell ergonomics** — Attach-from / Save-as for BYTES/ZLIB/GZIP with
  size-warning guards.
- **Recent files** — 8-entry persisted menu with missing-file pruning; drop files
  onto the window.

### Validation

- **JSON-Schema validation** — auto-detection (inline `$schema`, sibling
  `.schema.json`), manual binding persisted per-file, YAML schemas, YAML
  multi-doc validated independently, `mpq`/`Decimal`/`datetime`/`bytes` sanitized
  for validation only.
- **Shared registry** — one `SchemaEntry` per source across bound tabs,
  `QFileSystemWatcher` hot reload, identity-based schema-tab reuse, recent-schemas
  picker (cap 12).
- **In-tree markers** — uniform red wave badge on offending cells; single-line
  dock summary.

### Theming

- **Self-contained `themes/` package** — immutable hashable `ThemeSpec` /
  `Palette` / `TypeStyle`; YAML loading with total fallback; built-in light/dark;
  user overrides; opt-in hot reload (250 ms debounce).
- **Live switching** preserving undo / expansion / selection; follow-system color
  scheme with clean signal disconnect on shutdown; app-level `Qt.ColorScheme`
  sync so native dialogs match; WCAG contrast helpers ready (`themes/_contrast.py`).

### Code quality & tooling

- Modern Python 3.14 (`match`/`case`, `StrEnum`, type hints).
- **Dependencies declared and locked with Poetry** (`pyproject.toml` + committed
  `poetry.lock`); `requirements.txt` is generated from the lock and CI fails if it
  drifts.
- **No `TODO`/`FIXME`/`XXX`/`HACK` markers in production code.**
- Only one production file exceeds 800 lines.

---

## ❌ Cons

### CI coverage gap (highest current risk)

**No CI job runs the test suite.** `no-reflection.yml` runs only the reflection
check and the `requirements.txt` freshness check; `release.yml` is
`workflow_dispatch`-only. The suite is a purely local gate, so a pull request can
go green having run nothing but a grep. This is now the most consequential gap in
the repo.

### File-size outliers (audit Low)

- `editors/windowed/hexedit/widget.py` — 1130 lines; cohesive, but the one file
  over 800.
- `tree_actions/structure.py` — 774 lines (insert/delete/move/sort/expand —
  splittable).
- `tree/item_coercion.py` — 644 lines.
- `app/main_window.py` — 560 lines; file-operation workflows could move to a
  presenter.
- `tree_actions/context_menu.py` — 547 lines.

### Dead / deprecated code (audit Low)

- `tree_actions/selection.py` — underscore-prefixed helpers (`_resolve_model`,
  `_to_source_index`, …) re-exported across sibling modules; they are a shared
  internal API, and the naming is misleading at package scope.

### Test gaps (audit grade B)

- **Delegate matrix** missing (`tests/test_value_delegate.py`): editor type per
  `JsonType`, `setEditorData` / `setModelData` round-trips, dialog-delegate
  commits via `QPersistentModelIndex`.
- **I/O round-trip property tests** missing: load → mutate → save → reload
  equality with mpq + datetime + tz across all four formats.
- **Model invariants** missing: `setData` covers cols 0..2, `removeRows`
  persistent-index update, 3-level `parent()`/`index()` round-trip, `change_type`
  lossy gating, `unique_child_name` collisions.
- **WCAG / theme-snapshot suites** missing despite `_contrast.py` being ready.
- **End-to-end MainWindow smoke** is only partial.

### Tooling gaps (audit grade B)

- `pytest-cov` is declared in the Poetry `test` group, but no coverage snapshot
  has been committed to `agents/coverage.md`.
- `make lint`'s `autoflake` step runs bare `autoflake .` with no `--in-place`, so
  it only prints diffs and has never removed an unused import. `make lint` is
  effectively isort + black.
- No CI check that `JsonTab` actually satisfies the `Document` protocol; a mypy
  or conformance test would catch drift.

### Smaller seam / hygiene concerns (audit Low / Very Low)

- Two lazy upward imports remain in `tree/item.py`, inside
  `_default_secret_name_predicate`, allowlisted by **file:line** in
  `.githooks/_check_tree_isolation.sh`. Injection via `SecretNamePredicate` is the
  real path; the lazy fallback exists so headless fixtures can construct a
  `JsonTreeItem` unwired. The file:line allowlist is brittle — an edit that
  shifts those lines must fix the allowlist in the same commit.
- `IoController.save()` catches `Exception` broadly — no structured user-facing
  diagnostics for malformed datetime / bytes.
- `IoController.save_as()` couples to `QFileDialog` directly.
- Undo commands hold a `_tab` reference typed `"JsonTab"`; could narrow to
  `Document`.
- `JsonTreeItem.row()` returns `0` for the root rather than `-1` (footgun).
- `ValueDelegate.createEditor` raises `ValueError` for OBJECT/ARRAY/NULL
  (unreachable via `flags()`, but `return None` would degrade more gracefully).
- `state.view_state` persists expansion/current as positional `(int,…)` paths; a
  structural mutation before save→reload can land on a different node.

### Feature follow-ups (deferred, not blocking)

- Secret strings: no schema-sidecar metadata for non-matching names, no clipboard
  scrubbing, no manual override surface, no cell-level reveal.
- Validation: URL schema staleness (no `ETag` / `If-Modified-Since`), no
  content-hash dedup for embedded inline schemas, no remote `$ref` resolution.
- Theming: hot reload watches YAML but not icon-asset folders; no match-highlight
  delegate; no theme docs / schema reference.

---

## TL;DR

The editor is **functionally complete for daily use** and the codebase is **well
above average** — the responsibility-segregation refactor was executed
thoroughly, the undo gateway is a real chokepoint, and isolation plus the
reflection ban are enforced by CI (audit **A−**). The `tree/` upward-import
inversion that dominated earlier revisions of this document has been resolved.

The remaining work is **not about design flaws**:

1. **High priority** — add a CI job that runs the test suite. Everything else on
   this list is guarded by a gate that only runs on a developer's machine.
2. **High priority** — add the delegate-matrix and I/O round-trip property tests.
3. **Medium** — split `tree_actions/structure.py`, extract a file-operation
   presenter from `MainWindow`, narrow `IoController.save()`.
4. **Low** — rename the underscore-prefixed cross-module helpers, add a
   `Document`-protocol conformance check, commit a coverage snapshot.
