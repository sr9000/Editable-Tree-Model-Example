# JSON Editor — Pros & Cons

_Last analysis: **2026-06-01** (branch `strict-responsibility-segregation`).
Reflects the completed responsibility-segregation refactor (Plan 20 /
Plan 21, all 8 steps) and the 2026-06-01 code review
(`reports/code-review-2026-06-01.md`, overall grade **A−**)._

A PySide6 desktop **structured-data editor** (JSON / JSONL / YAML /
YAML-multi) built on a three-column `Name | Type | Value` tree model,
with exact-rational numerics (`gmpy2.mpq`), a typed undo/redo system,
JSON-Schema validation, and a theming stack. See `repo-map.md` for the
module breakdown.

_Test surface: **1124 collected**. `make gate` runs lint →
no-reflection → editor-isolation → tests._

---

## ✅ Pros

### Architecture & responsibility segregation (audit grade A−)

- **`JsonTab` is a genuinely thin facade** (~219 lines) — its `__init__`
  is a single `tab_init.bootstrap()` call; every method routes to a
  controller, state, or seam. The `documents/` package is a textbook
  facade + controllers + states + seams layout
  (`composition/`, `controllers/`, `seams/`, `states/`).
- **Single mutation chokepoint** — `DocumentMutationGateway` is the
  *only* entry point for tree edits. Every rename / edit / type-change /
  insert / remove / move / sort / case-switch flows through
  `commit_set_data` or a `push_*` method into a typed `QUndoCommand`.
  Verified unbroken end-to-end; read-only state is triple-guarded.
- **Narrow, typed seams** — `@runtime_checkable` `Document` protocol
  (tab → app/tree_actions), `TreeModelLike` (model → tree_actions),
  `JsonTabHost` (host → tab), `EditorContextProtocol` /
  `ValueDelegateProtocol` (tab/delegate → editors). Consumers depend on
  protocols, not the concrete `JsonTab`.
- **Editor isolation enforced by CI** — concrete editors in
  `editors/inline/*` and `editors/windowed/*` import nothing from
  `app/`, `documents/`, or `tree/`; guarded by
  `make check-editors-isolation`. They are reusable, headless-testable
  widgets.
- **Reflection ban enforced by CI** — `getattr` / `hasattr` /
  `TYPE_CHECKING` / `AttributeError` are forbidden outside a tiny
  allowlist (`.githooks/pre-commit-ci`).
- **Clean dependency injection** — `JsonTabServices` frozen dataclass +
  `JsonTabHost` protocol; no framework, with a legacy-callback bridge.
- **Strong module cohesion (audit grade A)** — every module has a
  single clear purpose; `io_formats/dump.py` (47 lines) and `load.py`
  (83 lines) are exemplary; `state/` modules are focused QSettings
  wrappers.

### Type system & numerics

- **Rich `JsonType` enum** — INTEGER, FLOAT, PERCENT, BOOLEAN, STRING,
  UNICODE, MULTILINE, TEXT, DATE, TIME, DATETIME, DATETIMEZONE,
  DATETIMEUTC, BYTES, ZLIB, GZIP, OBJECT, ARRAY, NULL — plus the four
  number-affix kinds (`INTEGER/FLOAT_CURRENCY/_UNITS`), two secret kinds
  (`SECRET_LINE/_TEXT`), two color kinds (`COLOR_RGB/_RGBA`), and the
  derived pseudo-text family (`EMPTY_*` / `WS_*`). This is a
  structured-data editor, not just a JSON editor.
- **Centralized type logic** — `tree/types.py` (inference) and
  `tree/item_coercion.py` (conversion) are the single source of truth;
  type logic does not leak into the UI.
- **Total, conservative detection** — `parse_json_type` falls back to
  STRING with a logged warning; datetime is checked before bytes; type
  pinning (`explicit_type`) keeps base64-like / newline strings as plain
  STRING.
- **Exact numeric arithmetic** — `gmpy2.mpq` end-to-end via
  `QBigIntSpinBox` / `QMpqSpinBox`; no float precision loss in storage
  or display; round-trips across all four formats via `mpq2py`.
- **UTC datetime** — `DATETIMEUTC` with `Z` suffix and a full
  conversion lattice (`tree/types_datetime.py`), including a real
  tz-shift on `DATETIMEZONE → DATETIMEUTC`.
- **Number affixes** — frozen `NumberAffix(kind, affix, space, number)`
  with `number: int | mpq`, composite editor, per-tab affix MRU,
  JSON/YAML round-trip (only strings that re-parse are promoted back).
- **Secret strings** — `SECRET_LINE/_TEXT`, never auto-classified as a
  non-secret kind; name-driven promotion via
  `validation.secret_names.name_looks_secret` (runtime-configurable
  prefixes); masked rendering with fixed glyph count (length never
  leaks); reveal-toggle editors with focus-out auto-hide.
- **Pseudo-text family** — empty / whitespace-only strings surface as
  visible chips without changing editable behaviour; excluded from
  `USER_SELECTABLE_TYPES`; mapped back via `PSEUDO_TEXT_PARENT`.

### Undo / redo

- **Typed-command system (audit grade A)** — 8 `QUndoCommand`
  subclasses with path-based addressing (sidesteps `QModelIndex`
  invalidation); `DiffApplier` emits minimal `dataChanged` signals so
  expansion and selection survive undo/redo.
- **`mergeWith` collapsing** — same-path renames / value edits within a
  500 ms window collapse into one undo step.
- **Anchor-based moves** — every move (keyboard, drag-drop, paste
  cleanup) feeds one `MoveAnchor` into `push_move_rows_anchor`,
  collapsing three formerly overlapping algorithms.
- **Viewport via signal** — undo commands never call `setCurrentIndex`
  directly; they emit `viewportRequested(kind, payload)`.
- **History dialog** — `QUndoView` bound to the active tab's stack.

### UX / functional features

- **Multi-format file I/O** — JSON, JSONL/NDJSON, YAML, YAML-multi;
  atomic writes via `os.replace`.
- **File-UX** — Reload from Disk (`Ctrl+R`, dirty-aware), Close
  (`Ctrl+W`) / Reopen Closed Tab (`Ctrl+Shift+T`, LIFO ×10), New From
  Clipboard (`Ctrl+Space`, JSON+YAML), Copy-as-YAML toggle, YAML paste,
  search-aware Go To, dirty-aware Save, full-path tab tooltips.
- **Drag-and-drop with multi-selection** — mouse move/copy between
  OBJECT/ARRAY containers; Ctrl-drag = copy; cycle guard via MIME
  `source_paths`; leaf-drop becomes sibling-after; transient status
  feedback. Expansion state preserved across moves and undo/redo.
- **Multi-action paste** — `Ctrl+V` (`paste_auto`), `Ctrl+Shift+V`
  (`paste_insert_after_zip`), `Ctrl+Alt+V` (`paste_replace_zip`).
- **Keyboard multimove** — `Alt+Up/Down` (disjoint multi-selection,
  parent-boundary bubble-out); `Ctrl+Alt+Up/Down` (promote-out).
- **Smart kind-switch coercion** — bool→str lowercase, datetime→`"now"`
  fallback, int↔datetime, lossless cross-format bytes re-encode,
  ARRAY↔OBJECT child preservation, friendly stub placeholders.
- **Type-aware presentation** — PERCENT `50%`, BYTES `<24 byte>`, mpq
  exact decimal, 80-char elision, container preview when collapsed,
  4 KB tooltips on long values, breadcrumb status bar.
- **Per-file persisted view state** — column widths, expansion,
  selection, font zoom (SHA1-keyed, safe coercion, 5000-entry cap);
  zoom respects user-resized columns.
- **Base64 cell ergonomics** — Attach-from / Save-as for
  BYTES/ZLIB/GZIP with size-warning guards; configurable Edit Warning
  Limits.
- **Recent files** — 8-entry persisted menu with missing-file pruning;
  drop files onto the window; window-mode persistence.
- **CapsLock-safe inline editing** and dialog edits that survive row
  mutations via `QPersistentModelIndex` + `commit_set_data`.

### Validation

- **JSON-Schema validation** — schema auto-detection (inline `$schema`,
  sibling `.schema.json`), manual binding persisted per-file, YAML
  schemas, YAML multi-doc validated independently, `mpq`/`Decimal`/
  `datetime`/`bytes` sanitized validation-only.
- **Shared registry** — one `SchemaEntry` per source across bound tabs,
  `QFileSystemWatcher` hot reload, identity-based schema-tab reuse
  (`SchemaTabPool`), recent-schemas picker (cap 12).
- **In-tree markers** — uniform red wave badge on offending cells;
  single-line dock summary.

### Theming

- **Self-contained `themes/` package** — immutable hashable
  `ThemeSpec` / `Palette` / `TypeStyle`; YAML loading with total
  fallback; built-in light/dark; user overrides; opt-in
  `QFileSystemWatcher` hot reload (250 ms debounce).
- **Live switching** preserving undo / expansion / selection; type
  icons via `FileIconProvider`; follow-system color scheme with clean
  signal disconnect on shutdown; app-level `Qt.ColorScheme` sync so
  native dialogs match the theme; WCAG contrast helpers ready
  (`themes/_contrast.py`).

### Code quality & tooling

- Modern Python 3.12+ (`match`/`case`, `StrEnum`, type hints).
- **No `TODO`/`FIXME`/`XXX`/`HACK` markers in production code** (verified
  2026-06-01).
- `make gate` chains lint, no-reflection, editor-isolation, and tests;
  pre-commit hooks enforce the data-store-leak and reflection bans.
- All production files except the self-contained
  `editors/windowed/hexedit/widget.py` (1130 lines) are under 800 lines.

---

## ❌ Cons

### Architectural inversions — `tree/` reaches upward (audit Medium)

The data layer imports from packages above it. **11 upward imports**
(verified 2026-06-01):

- `tree/item.py` → `editors.inline.datetime` (×2), `state.secret_settings`,
  `validation.secret_names`.
- `tree/item_coercion.py` → `editors.inline.datetime` (×2),
  `delegates.formatting.bytes_codec` / `color_codec` (lazy, ×5).
- `tree/types.py` → `editors.inline.datetime`.

Lazy imports avoid circular-import crashes, but the dependency direction
violates the documented rule that `tree/` is the low-level data package.
**This is the single biggest architectural debt** and the subject of the
active refactor plan (`plans/refactor-tree-upward-imports.md`).

### File-size outliers (audit Low)

- `editors/windowed/hexedit/widget.py` — 1130 lines (cohesive, but the
  one outlier; the historical `pros-n-cons` "~580 line" claim was
  inaccurate).
- `tree_actions/structure.py` — 774 lines (insert/delete/move/sort/
  expand/collapse — splittable).
- `app/main_window.py` — 637 lines (file-operation workflows could move
  to a presenter).

### Dead / deprecated code (audit Low)

- `app/main_window.py` — `_closed_tabs_stack` / `_MAX_CLOSED_TABS`
  deprecated shims; `_setup_validation_dock` / `_setup_schemas_menu`
  no-op stubs retained for test back-compat.
- `tree_actions/selection.py` — underscore-prefixed helpers
  (`_resolve_model`, `_to_source_index`, …) re-exported across sibling
  modules; misleading at package scope.

### Test gaps (audit grade B)

- **Delegate matrix** missing (`tests/test_value_delegate.py`): editor
  type per `JsonType`, `setEditorData` / `setModelData` round-trips,
  dialog-delegate commits via `QPersistentModelIndex`.
- **I/O round-trip property tests** missing: load → mutate → save →
  reload equality with mpq + datetime + tz across all four formats.
- **Model invariants** missing: `setData` covers cols 0..2, `removeRows`
  persistent-index update, 3-level `parent()`/`index()` round-trip,
  `change_type` lossy gating, `unique_child_name` collisions.
- **WCAG / theme-snapshot suites** missing despite `_contrast.py` being
  ready.
- **End-to-end MainWindow smoke** is only partial.

### Tooling gaps (audit grade B)

- `pytest-qt` not pinned in `requirements.txt` (theme tests use
  `qtbot`).
- No coverage snapshot (`pytest-cov` → `ai-memory/coverage.md`).
- No CI check that `JsonTab` actually satisfies the `Document` protocol
  (a `mypy` or conformance test would catch drift).

### Smaller seam / hygiene concerns (audit Low / Very Low)

- `IoController.save()` catches `Exception` broadly — no structured
  user-facing diagnostics for malformed datetime / bytes.
- `IoController.save_as()` couples to `QFileDialog` directly.
- Undo commands hold a `_tab` reference typed `"JsonTab"`; could narrow
  to `Document`.
- `JsonTreeItem.row()` returns `0` for the root rather than `-1`
  (footgun).
- `ValueDelegate.createEditor` raises `ValueError` for OBJECT/ARRAY/NULL
  (unreachable via `flags()`, but `return None` would degrade more
  gracefully).
- `state.view_state` persists expansion/current as positional `(int,…)`
  paths; a structural mutation before save→reload can land on a
  different node (acceptable, keyed per-file on close).

### Feature follow-ups (deferred, not blocking)

- Secret strings: no schema-sidecar metadata for non-matching names, no
  clipboard scrubbing, no manual override surface, no cell-level reveal.
- Validation: URL schema staleness (no `ETag`/`If-Modified-Since`), no
  content-hash dedup for embedded inline schemas, no remote `$ref`
  resolution.
- Theming: hot reload watches YAML, not icon-asset folders; no
  match-highlight delegate; no theme docs / schema reference.

---

## TL;DR

The editor is **functionally complete for daily use** and the codebase
is **well above average** — the responsibility-segregation refactor has
been executed thoroughly, the undo gateway is a real chokepoint, and
editor isolation plus the reflection ban are enforced by CI (audit
**A−**).

The remaining work is **not about design flaws** but about tightening
the last architectural inversion and closing QA gaps:

1. **High priority** — resolve the 11 `tree/` upward imports (extract
   shared datetime-parsing and bytes/color codecs out of `editors/` and
   `delegates/`; inject secret-name matching into `JsonTreeItem`). See
   `plans/refactor-tree-upward-imports.md`.
2. **High priority** — pin `pytest-qt`, wire `make test`, add the
   delegate-matrix and I/O round-trip property tests.
3. **Medium** — split `tree_actions/structure.py`, extract a
   file-operation presenter from `MainWindow`, narrow
   `IoController.save()`.
4. **Low** — delete the deprecated shims / no-op stubs, rename the
   underscore-prefixed cross-module helpers, add a `Document`-protocol
   conformance check.
