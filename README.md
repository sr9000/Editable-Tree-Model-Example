# Editable JSON / YAML Tree Editor

A desktop editor for structured data files. It opens JSON, JSON Lines,
YAML, and multi-document YAML as an editable tree with typed cells,
schema validation, undo/redo, search, themes, and file-safe saves.

It started from Qt's
[Editable Tree Model](https://doc.qt.io/qt-6/qtwidgets-itemviews-editabletreemodel-example.html)
example, but the current app is a practical editor for configuration
files, data fixtures, schema-backed documents, and structured text that
is awkward to maintain in a plain text editor.

---

## Quick start

### Install

```bash
git clone <this repo>
cd Editable-Tree-Model-Example
python3.12 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

Python **3.12+** is expected. Dependencies are pinned in
`requirements.txt` and include PySide6, PyYAML, simplejson, gmpy2,
python-dateutil, tzdata, pytest, and `jsonschema[format]`.

### Run the app

```bash
python main.py
python main.py data.json
python main.py data.yaml
```

You can also drag one or more local `.json`, `.jsonl`, `.ndjson`,
`.yaml`, or `.yml` files onto the main window; each opens in its own
tab.

### First minute in the UI

1. Open a file with **File ▸ Open** or by passing a path to
   `python main.py`.
2. Edit the **Value** column. The editor matches the value type
   (spin box, datetime editor, line edit, multiline dialog, hex
   dialog, color picker, etc.).
3. Edit the **Type** column to intentionally reinterpret a value.
   The app preserves data when it can and uses explicit placeholders
   when a conversion would otherwise be ambiguous.
4. Press `Ctrl+S` to save. Plain Save keeps the detected file format;
   Save As lets you choose a different supported format.

---

## What it is useful for

- **Inspecting and editing nested configuration** without losing the
  shape of objects and arrays.
- **Working with JSON/YAML data that has richer semantics** than plain
  text: exact rationals, percents, dates, timezones, base64 payloads,
  colors, currency/unit numbers, and secret-like fields.
- **Schema-guided editing**: attach or auto-discover JSON Schemas,
  see validation issues in a dock, and jump to offending rows.
- **Large or sensitive fields**: open multiline, binary, and secret
  values in dedicated editors with warning limits and masked display.
- **Bulk tree edits**: move, duplicate, paste, delete, and drag/drop
  multiple rows with undo support.
- **Fixture maintenance**: round-trip JSON/YAML fixtures while keeping
  exact numbers and typed display/editor behaviour.

---

## Main features

### File formats

- JSON (`.json`)
- JSON Lines / NDJSON (`.jsonl`, `.ndjson`)
- YAML (`.yaml`, `.yml`)
- YAML multi-document streams
- Atomic writes via `os.replace`
- Exact rational round-trip through `gmpy2.mpq` helpers

### Tree editing

- Three-column tree: **Name | Type | Value**.
- Editable objects, arrays, primitive values, and the synthetic root.
- Multi-selection copy/cut/paste/delete/duplicate.
- Native drag-and-drop: move by default, copy with `Ctrl`.
- Drop cycle guard: a row cannot be moved into its own descendant.
- Context menu adapts to the selection — disabled actions are hidden
  rather than greyed; **Expand / Collapse Recursively** scopes to
  the selected subtree (or the whole document when the root is
  selected).
- Undo/redo and a **History** dialog powered by Qt's `QUndoStack`.

### Tabs and files

- Multiple documents open in tabs; the title bar shows a `*` for
  unsaved changes and the tab tooltip shows the full file path.
- **Reload from Disk** (`Ctrl+R`) re-reads the current file; if the
  tab has unsaved edits you can Discard them, Overwrite the file with
  the in-memory copy, or Cancel.
- **Close Tab** (`Ctrl+W`) and **Reopen Closed Tab**
  (`Ctrl+Shift+T`) — last 10 closed tabs are remembered. Empty
  untitled tabs close without a prompt; untitled tabs that contain
  data prompt to save first.
- **New From Clipboard** (`Ctrl+Space`) opens a fresh tab from a
  JSON or YAML payload on the system clipboard.

### Clipboard

- **Copy as YAML text** — File-menu toggle that switches the copy
  text format between JSON (default) and YAML. The internal MIME
  payload still round-trips through other tabs without loss.
- Paste accepts JSON or YAML text from other apps; bare scalars are
  ignored.

### Typed values and editors

The app infers and displays a `JsonType` for each value. Common kinds:

- Numbers: integer, exact rational float, percent, currency, units.
- Text: ASCII/UTF-8 line, multiline text, empty/whitespace previews.
- Secrets: single-line and multiline values are masked in the tree.
- Dates: date, time, naive datetime, timezone datetime, UTC `Z`
  datetime.
- Binary: bytes, zlib, gzip, stored as base64-compatible text.
- Colors: `rgb` / `rgba` hex values with swatch previews.
- Structure: object, array, null, boolean.

Specialized editors include arbitrary-precision spin boxes, segmented
datetime editing, multiline and hex dialogs, masked secret editors,
and a color dialog.

### Validation

- JSON Schema validation with `jsonschema[format]`.
- Schema discovery from inline local `$schema`, sibling schema files,
  and persisted per-file manual bindings.
- Manual schema attach from local JSON/YAML schema files or `http(s)`
  URLs.
- Local schema files hot-reload and revalidate all bound tabs.
- YAML multi-doc validation reports issues per document.
- Validation dock shows issues, navigates to rows, and can open the
  schema rule for an issue.

### Search, view state, and themes

- `Ctrl+F` recursive name/value filter; matching descendants keep
  their ancestors visible.
- Per-file view state: column widths, expanded rows, current row, and
  zoom level.
- Persistent window geometry, recent files, recent schemas, and dock
  layout.
- Built-in light/dark themes, type icons, follow-system mode, and
  optional user-theme hot reload.

### Safety and ergonomics

- Confirm-before-open thresholds for very large string, multiline,
  binary, and attach-file operations.
- Context-menu **Attach from…** / **Save as…** for base64-like binary
  cells.
- Secret field masking is for shoulder-surfing/screen sharing only;
  secrets are still saved as plain strings on disk.

---

## Common workflows

### Validate a document against a schema

1. Open the document.
2. Show **View ▸ Validation Panel**.
3. Use **Schema ▸ Attach schema…** in the dock or top-level
   **Schemas** menu.
4. Click an issue to jump to the row; use the issue context menu to
   open the matching schema rule.

### Edit a large multiline value

1. Edit the value cell.
2. If the field exceeds the configured limit, confirm that you want to
   open the modal editor.
3. Save in the dialog; the edit is committed through undo/redo.

### Work with binary/base64 data

1. Select a `bytes`, `zlib`, or `gzip` value.
2. Right-click the row.
3. Use **Attach from…** to encode a file into the cell, or **Save
   as…** to decode the cell to disk.

### Configure secret detection

Secret fields are detected by word-prefixes in field names (for
example `password`, `api_key`, `authToken`, `private_key`). To edit the
prefix list, use **File ▸ Secret word prefixes…**.

### Find a row through the search filter

1. Press `Ctrl+F` and type part of a key or value.
2. Right-click a match and choose **Go To** — the filter clears and
   the editor jumps to that row.

### Reload a file edited externally

If another tool changes the file on disk, press `Ctrl+R`. If you have
unsaved edits in the tab, choose Discard to take the disk version,
Overwrite to save your edits over disk, or Cancel.

---

## Essential shortcuts

| Shortcut                       | Action                                                       |
|--------------------------------|--------------------------------------------------------------|
| `Ctrl+N` / `Ctrl+O`            | New / Open                                                   |
| `Ctrl+Space`                   | New tab from clipboard (JSON or YAML)                        |
| `Ctrl+R`                       | Reload current tab from disk                                 |
| `Ctrl+S` / `Ctrl+Shift+S`      | Save / Save As                                               |
| `Ctrl+W` / `Ctrl+Shift+T`      | Close current tab / Reopen last closed tab                   |
| `Ctrl+F`                       | Focus filter                                                 |
| `F2` or `Enter`                | Edit current cell                                            |
| `Ctrl+I` / `Ctrl+Shift+I`      | Insert sibling before / after                                |
| `Del`                          | Remove selection                                             |
| `Ctrl+D`                       | Duplicate selection                                          |
| `Ctrl+C` / `Ctrl+X` / `Ctrl+V` | Copy / Cut / Paste                                           |
| `Ctrl+Shift+V`                 | Multi-paste: insert clipboard entries after selected targets |
| `Ctrl+Alt+V`                   | Multi-paste: replace selected target values                  |
| `Alt+↑` / `Alt+↓`              | Move selection up / down                                     |
| `Ctrl+Alt+↑` / `Ctrl+Alt+↓`    | Promote selection out of its parent                          |
| `Ctrl+Alt+S`                   | Sort keys under selected object                              |
| `Ctrl++` / `Ctrl+-` / `Ctrl+0` | Zoom in / out / reset                                        |

---

## Development

### Run tests

```bash
QT_QPA_PLATFORM=offscreen pytest
```

The suite currently collects **1023 tests**. A small set of
color-scheme tests is known to be platform-sensitive under Qt's
offscreen QPA plugin because offscreen does not round-trip
`QStyleHints.setColorScheme` like real desktop platforms do.

### Lint and format

```bash
make lint
```

The `lint` target runs autoflake, isort, and black with the repository
configuration.

---

## Project documentation

- `ai-memory/repo-map.md` — dense module-by-module map for agents and
  contributors.
- `ai-memory/pros-n-cons.md` — current strengths, caveats, and gaps.
- `ai-memory/todo-n-fixme.md` — active open work only.
- `ai-memory/history.md` — archived resolved phase/feature history.
- `plans/` — feature plans and definitions of done for larger changes.
