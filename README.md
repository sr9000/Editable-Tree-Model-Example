# JSON / YAML Tree Editor

A PySide6 desktop **structured-data editor**. Originated from Qt's
[Editable Tree Model](https://doc.qt.io/qt-6/qtwidgets-itemviews-editabletreemodel-example.html)
example; rebuilt as a real editor for JSON, JSON Lines, YAML, and
multi-document YAML, with type-aware cell editors, undo/redo, themes,
JSON-Schema validation, and a hot-reloadable schema registry.

---

## Part 1 — Fast start

### 1. Install

```bash
git clone <this repo>
cd Editable-Tree-Model-Example
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Pinned dependencies (see `requirements.txt`):

- `python-dateutil==2.9.0.post0`
- `PySide6==6.11.1`
- `PyYAML==6.0.3`
- `pytest==9.0.3`
- `gmpy2==2.3.0`
- `tzdata==2026.2`
- `simplejson==4.1.1`
- `jsonschema[format]==4.26.0`

Python **3.12+** is required (the code uses `match` / `case`,
`StrEnum`). Validation support is part of the pinned dependency set;
no extra install step is needed beyond `pip install -r requirements.txt`.

### 2. Run

```bash
python main.py                       # empty window, restores last geometry
python main.py path/to/data.yaml     # open one document on startup
```

You can also **drag-and-drop one or many files** from your system file
manager onto the main window — each is opened in its own tab.

### 3. Edit a value

1. Click a row's **Value** cell — an inline editor matched to the
   cell's `JsonType` opens (numeric spin box, datetime segments,
   true/false combo, line edit, hex dialog, multiline dialog, colour
   picker, …).
2. Press `Enter` (or `F2`) to commit, `Esc` to cancel.
3. The **Type** cell (middle column) opens a combo of every supported
   type; switching morphs the value when possible
   (e.g. `int` ↔ `datetime epoch s/ms`, `bytes` ↔ base64, `array` ↔
   `object`) and falls back to a friendly placeholder when not.

### 4. Insert / move / paste

- `Ctrl+I` / `Ctrl+Shift+I` — insert sibling **before** / **after**
- `Del` — delete row, `Ctrl+D` — duplicate row
- `Alt+↑` / `Alt+↓` — move selection up / down (bubble out of parent
  at the boundary)
- `Ctrl+Alt+↑` / `Ctrl+Alt+↓` — promote selection out of the current
  parent
- `Ctrl+C` / `Ctrl+X` / `Ctrl+V` — copy / cut / paste (multi-row
  aware; MIME type `application/x-json-tree`)
- `Ctrl+Shift+V` — paste-insert-zip (pair clipboard entries with
  selected rows, insert each after its target)
- `Ctrl+Alt+V` — paste-replace-zip (replace each selected row's value)
- Left-click + drag — move; hold `Ctrl` while dragging — copy. Drop
  onto a container appends; drop onto a leaf becomes sibling-after.
  Cycle drops (parent into descendant) are rejected.

### 5. Save

`Ctrl+S` (Save) and `Ctrl+Shift+S` (Save As). The originally-detected
format (`.json` / `.jsonl` / `.ndjson` / `.yaml` / multi-doc YAML) is
preserved on plain Save. Save As lets you pick a different format
filter. All writes are **atomic** (`os.replace`).

### 6. History

Use the **History** menu (Undo, Redo, Show History…). The
`Show History…` dialog is a live `QUndoView` bound to the active
tab's stack. Consecutive same-path rename / edit-value commands
merge within a 500 ms window so typing is one undo step.

### 7. Search / filter

Press `Ctrl+F` to focus the filter line. Substring match on names and
on leaf values; matches' ancestors are always shown.

### 8. Validate against a JSON Schema

Open the bottom **Validation** dock (View ▸ Validation Panel). The
editor auto-detects a schema in this order:

1. Inline `$schema` key pointing at a local file (relative or
   absolute). Remote `http(s)://` URIs are ignored by discovery.
2. Sibling `<doc>.schema.json` next to the document.
3. The last manual binding persisted for this exact file path.

To attach a schema manually, use the dock's **Schema ▸ Attach
schema…** action and pick a `.json` / `.yaml` / `.yml` file *or* paste
an `http(s)://` URL. The binding is persisted per file path. The
top-level **Schemas** menu mirrors the same actions plus a Recent
submenu.

Local schemas are watched with `QFileSystemWatcher` and hot-reload
across every bound tab on external edits. URL schemas are read-only
and can be refreshed with **Reload schema**.

---

## Part 2 — Features by mechanic

### Data model & type system
- **Three-column tree**: `Name | Type | Value`.
- **Cell types** (`tree/types.py::JsonType`):
  `integer`, `float`, `percent`,
  `int currency` (e.g. `$1234`), `int units` (e.g. `1234 kg`),
  `float currency` (e.g. `$ 3.5`), `float units` (e.g. `3.14 rad`),
  `boolean`,
  `string`, `utf-8 line`, `multiline`, `utf-8 text`,
  `secret_line`, `secret_text`,
  `date`, `time`, `datetime`, `dt+timezone`,
  `bytes`, `zlib`, `gzip`,
  `rgb`, `rgba`,
  plus structural `object`, `array`, `null`.
- **Exact arithmetic** — floats and percents are stored as
  `gmpy2.mpq`; integers are arbitrary-precision via
  `qbigint_spinbox`.
- **Smart kind-switch coercion** (`tree/item_coercion.py`):
  `bool → "true"/"false"`, `"now"` fallback for unparseable
  datetimes, `int ↔ datetime` (sec & ms), `bytes ↔ zlib ↔ gzip`
  lossless re-encode when the source type is known, `array ↔ object`
  preserves children. Placeholders from `tree/stubs.py` flag truly
  unrecoverable cases.
- **Synthetic editable root** — toggle via
  `JsonTreeModel.show_root`.

### Editors per cell type
- `QBigIntSpinBox` for integers (no 64-bit cap).
- `QMpqSpinBox` for floats and percents (`0–100 %` UI, `0–1 mpq`
  storage).
- Affix-number composite editor for affix numeric kinds: exactly three
  widgets in a tight row — affix combo, inline space toggle, numeric
  spin box (prefix/suffix order depends on type).
- `BetterDateTimeEditor` (segmented) for date / time / datetime / tz.
- CapsLock-safe `QLineEdit` for ASCII / UTF-8 single-line text.
- Modal `QMultilineDialog` for multiline ASCII / UTF-8 text.
- Secret editors: masked single-line (`secret_line`) and masked multiline
  (`secret_text`) with an inline Show/Hide toggle; editors auto-close on
  focus/app deactivation so the view returns to masked cells.
- Modal `QHexDialog` for binary blobs (`bytes` / `zlib` / `gzip`),
  base64 wire format on disk.
- Non-modal `QColorDialog` for `rgb` / `rgba`; cell shows a swatch
  with checkerboard alpha preview.
- `QComboBox` for `boolean` and for the Type column.
- **Confirm-before-open** dialogs for very large strings, multiline
  blocks, and binary payloads — limits configurable in
  **File ▸ Edit Warning Limits**.
- Percent remains a separate numeric kind; it is not absorbed into the
  affix-number types.

### Multi-selection, clipboard, drag-and-drop
- Multi-row contiguous and disjoint selection.
- MIME format `application/x-json-tree` with `text/plain` fallback;
  payload includes names so paste preserves full type info.
- Anchor-based move primitive (`tree_actions/anchors.py`) shared by
  Alt-move, Ctrl+Alt move-out, drag-and-drop, paste, and duplicate.
- Atomic multi-row undo (`undo/_MoveRowsCmd`) — every move is one
  undo step and re-selects the placed rows after redo / undo.
- Native QTreeView drag-and-drop with cycle guard. `JsonTreeView`
  overrides `startDrag` so the model fully owns internal moves.
- Multi-action paste dispatch: `paste_auto` (Ctrl+V),
  `paste_clones_at_targets`, `paste_insert_after_zip`
  (Ctrl+Shift+V), `paste_replace_zip` (Ctrl+Alt+V).
- Column-aware context menu: column 0 → Copy-with-name, column 2 →
  Copy-value-only, column 1 (Type) → opens the type combobox.
- Right-click inside a multi-selection preserves it; right-click
  outside collapses to the single hit row.

### Base64 cell ergonomics
- Context menu adds **Attach from…** (encode an arbitrary file into
  the cell) and **Save as…** (decode the cell to disk) for `bytes` /
  `zlib` / `gzip` leaves.
- Both honour the configurable attach-file size warning limit.

### Undo / redo
- Typed `QUndoCommand` subclasses for rename, edit-value,
  change-type, insert, remove, move (single + multi), sort-keys.
- Path-based addressing survives row mutations.
- `DiffApplier` replays edits with surgical Qt-signal updates so
  expansion state and current selection persist across replay.
- **History** menu owns Undo / Redo and a live `QUndoView` dialog.

### Filter / search
- `TreeFilterProxy` (recursive, 150 ms debounce) matches against
  names and leaf values; ancestors of matches stay visible.

### File I/O
- Auto-detect by extension: `.json`, `.jsonl` / `.ndjson`, `.yaml` /
  `.yml`, multi-document YAML.
- `mpq2py` keeps `gmpy2.mpq` rationals exact through every
  round-trip.
- Atomic writes via `os.replace`; Save preserves the originally
  detected format (notably YAML multi-doc).
- Secret kinds are saved as plain strings. On reload, secret kind
  restoration is heuristic (field-name prefix match + newline check), so
  sticky secret fields renamed to neutral names reload as normal text.

### Secret field detection
- Name detection uses word-prefix matching (split on `_`, `-`, `.`, space,
  and camelCase boundaries).
- Defaults come from `settings.SECRET_WORD_PREFIXES`; runtime overrides are
  editable in **File ▸ Secret word prefixes...** and persisted with `QSettings`.
- Promotion is sticky in-session (`secret_line`/`secret_text` do not demote
  on rename), and `secret_line` auto-upgrades to `secret_text` on newline edits.

### Themes & fonts
- Built-in light & dark YAML themes (`themes/builtin/`) plus 18
  bundled SVG type icons.
- User overrides under `QStandardPaths.AppConfigLocation/themes/*.yaml`.
- Follow-system mode reacts to
  `QGuiApplication.styleHints().colorSchemeChanged`.
- Optional hot reload of the user themes folder
  (`QFileSystemWatcher`, 250 ms debounce).
- Per-`JsonType` foreground / background / bold / italic + icon.
- App-level `Qt.ColorScheme` syncs with the active theme's mode
  (`Light` / `Dark`), so Qt's bundled chrome (menus, dialogs)
  matches.
- Global editor font controls: regular family, monospace family,
  monospace-fields toggle (`Ctrl+Shift+M`), and zoom (`Ctrl++` /
  `Ctrl+-` / `Ctrl+0`).

### Validation
- JSON Schema validation via pinned `jsonschema[format]`
  (`jsonschema==4.26.0` with format extras).
- Auto-detected schemas (inline `$schema`, sibling `.schema.json`)
  plus manual attachment via local file or `http(s)://` URL.
- Per-file binding persisted under
  `QSettings(APPLICATION_ID, "validation")` keyed by sha1 of the
  resolved absolute path.
- YAML multi-doc validates each document independently; issues
  carry a `[doc N]` prefix that resolves to the right row.
- `mpq` / `Decimal` / `datetime` / `bytes` are sanitized to plain
  JSON primitives before validation — never written back to the
  tree.
- **In-tree badges** — failing cells get a red wave overlay
  (`VALIDATION_SEVERITY_ROLE` + `delegates/validation_badge.py`).
- Validation dock lists every issue; click navigates to the row,
  context "Go to schema rule" opens the schema tab at the rule.
- Status bar shows a compact `Validation: N issue(s)` summary.
- Format validation uses `jsonschema.FormatChecker`; installing from
  `requirements.txt` also pulls the optional `format` extras used by
  `jsonschema` for richer checks.

### Schema registry
- Shared `SchemaEntry` per `SchemaSource(kind="file"|"url")`. Two
  tabs attached to the same source share one loaded dict.
- Local files watched with `QFileSystemWatcher`; external edits
  reload in place and revalidate every bound tab.
- URL sources are normalised and treated as read-only by the UI.
- `state.recent_schemas` persists a cap-12 MRU list, available from
  the attach dialog and from the **Schemas ▸ Recent** menu.
- `SchemaTabPool` reuses one open tab per schema source for
  schema-rule navigation.

### Persisted view state
- Per-file column widths, expanded paths (capped at 5000), current
  selection path, and font zoom — `QSettings` keyed by sha1 of the
  absolute path.
- Window geometry / maximized / fullscreen mode persisted across
  sessions (`QSettings(APPLICATION_ID, "app")::window/*`).
- Validation dock visibility and dock layout state persisted.
- Recent files (cap 8) and recent schemas (cap 12).

### Status / breadcrumb
- Status bar shows `$.foo.bar[2].baz  (string, 24 chars)` for the
  current row. Counts use compact `K` / `M` / `B` suffixes
  (`units.counts()`); byte sizes use binary suffixes
  (`units.format_bytes()`).

### Configurable edit-warning limits
- **File ▸ Edit Warning Limits ▸** opens four `QInputDialog`s:
  - String edit limit (chars, default 10 000)
  - Multiline text limit (chars, default 100 000)
  - Bytes edit limit (default 100 KiB)
  - Attach file size limit (default 100 KiB)
- Editors / attach actions check the matching threshold and pop a
  confirmation dialog before opening the modal editor.

### Custom reusable widgets
Each lives in its own package and is importable standalone:
- `qhexedit/` — hex editor widget with overlay highlighting.
- `qmultiline_editor.py` + `dialogs/qmultiline_dlg.py` — multiline
  text dialog that survives row mutations.
- `datetime_editor/` — segmented datetime editor with partial-regex
  validation and timezone parsing.
- `qbigint_spinbox/`, `qmpq_spinbox/` — arbitrary-precision and
  exact-rational spin boxes.
- `mpq2py/` — `gmpy2.mpq` ↔ JSON / YAML helpers (`MpqSafeLoader`,
  `MpqSafeDumper`, `mpq_serialization`).
- `jsontream/` — streaming JSON encoder over generators.
- `units/` — `bits` / `format_bytes` / `counts` formatting.

### Keyboard shortcuts (summary)

| Shortcut         | Action                                        |
| ---------------- | --------------------------------------------- |
| `Ctrl+N` / `Ctrl+O` / `Ctrl+S` / `Ctrl+Shift+S` | New / Open / Save / Save As |
| `Ctrl+Q`         | Exit                                          |
| `Ctrl+F`         | Focus filter line                             |
| `Ctrl+I` / `Ctrl+Shift+I` | Insert sibling before / after        |
| `Del`            | Remove row                                    |
| `Ctrl+D`         | Duplicate selection                           |
| `Ctrl+C` / `Ctrl+X` / `Ctrl+V` | Copy / Cut / Paste              |
| `Ctrl+Shift+V`   | Paste-insert-zip (multi-paste)                |
| `Ctrl+Alt+V`     | Paste-replace-zip                             |
| `Alt+↑` / `Alt+↓`| Move selection up / down (bubble-out at boundary) |
| `Ctrl+Alt+↑` / `Ctrl+Alt+↓` | Promote selection out of parent    |
| `Ctrl+Alt+S`     | Sort keys under selected OBJECT               |
| `Ctrl++` / `Ctrl+-` / `Ctrl+0` | Zoom in / out / reset           |
| `Ctrl+Shift+M`   | Toggle monospace fields                       |
| `F2` / `Enter`   | Edit current cell                             |

---

## Tests

```bash
QT_QPA_PLATFORM=offscreen pytest
```

The suite collects **922 tests**. Three tests under offscreen QPA
relate to `QStyleHints.setColorScheme` and are platform-only
failures; they pass on real X11 / Wayland / Win / Mac.

## Lint

```bash
make lint        # autoflake + isort + black (line-length 120)
```

## Project map

See `ai-memory/repo-map.md` for the full module-by-module map
(intended as an index for LLM agents). `ai-memory/pros-n-cons.md`
captures the current strengths and known gaps;
`ai-memory/todo-n-fixme.md` tracks open issues.
