# Editable-Tree-Model-Example — repo map

_Last scanned: **2026-05-13**. PySide6 desktop **structured-data
editor** (originated from Qt's "Editable Tree Model" example).
**Drag-and-drop plan is fully shipped**: Steps 1–10 (multiselect
foundation → MIME helpers → atomic multi-row undo move → keyboard
Alt±arrow multimove with boundary bubble-out → expansion preservation
across moves → native QTreeView drag-and-drop → drop policies & cycle
guards → shortcuts/menu/docs → move-mechanics + multi-action redesign
on anchors → multi-action context-menu paste/zip fixes) are all in
mainline. The tree gained a `JsonTreeView` subclass that owns
`startDrag` so the model can fully own internal moves without Qt's
default post-drag row removal. Tests: **776 passing, 3 known
offscreen-only failures** (color-scheme sync — see `todo-n-fixme.md`).

---

## 0) LLM quick-orientation table

| If you need to…                                       | Look at                                                              |
| ----------------------------------------------------- | -------------------------------------------------------------------- |
| App entry / window setup                              | `main.py`, `app/main_window.py`, `mainwindow.ui`                     |
| Menu wiring + enable/disable                          | `app/main_window_actions.py`                                         |
| Per-document tab (model/view/undo/search)             | `documents/tab.py` + `documents/tab_*.py`                            |
| Tree data model & node                                | `tree/model.py`, `tree/item.py`, `tree/model_roles.py`               |
| Custom tree view (owns `startDrag`)                   | `tree/view.py` (`JsonTreeView`)                                      |
| Type system / inference                               | `tree/types.py` (`JsonType`, `parse_json_type`)                      |
| Cross-type coercion (kind switch)                     | `tree/item_coercion.py` (+ `tree/stubs.py`)                          |
| Editors per type / display formatting                 | `delegates/value.py`, `delegates/value_formatting.py`                |
| Type-column combobox                                  | `delegates/type_delegate.py`                                         |
| Name column rename                                    | `delegates/name_delegate.py`                                         |
| Modal editors (multiline / hex)                       | `dialogs/qmultiline_dlg.py`, `dialogs/qhexedit_dlg.py`               |
| Context menu / clipboard / paste / structural ops     | `tree_actions/`                                                      |
| Drag-and-drop policy / dispatch                       | `tree_actions/dnd.py`, `tree/model.py`, `tree/view.py`               |
| Anchor-based move primitive                           | `tree_actions/anchors.py`                                            |
| Filter / search                                       | `tree_filter_proxy.py`, `documents/tab_setup.py::init_search_filter` |
| Typed undo commands + diff replay                     | `undo/commands.py`, `undo/diff.py`                                   |
| File I/O (JSON / JSONL / YAML / YAML-multi)           | `io_formats/`                                                        |
| Persisted view state (column widths, expansion, zoom) | `state/view_state.py`                                                |
| Theme system (specs/loader/registry/icons)            | `themes/`                                                            |
| Theme menu + follow-system + hot reload + scheme sync | `app/theme_controller.py`                                            |
| Per-tab status / breadcrumb                           | `documents/tab_status.py`                                            |
| Custom widgets                                        | `qhexedit/`, `qmultiline_editor.py`, `datetime_editor/`, `qbigint_spinbox/`, `qmpq_spinbox/` |

---

## 1) What this repo is

A PySide6 desktop **structured-data editor** with:

- Tabbed multi-document shell (`app/`, `documents/`).
- Three-column JSON tree (`Name | Type | Value`) with type-aware
  delegates and live container previews.
- Typed `QUndoCommand`-based undo/redo with `mergeWith` collapsing of
  consecutive same-path edits, and a `QUndoView` history dialog.
- Context menu / clipboard / cut / copy / paste / duplicate / move /
  sort, all routed through the typed undo stack.
- Recursive name+value filter proxy (`Ctrl+F`, debounced 150 ms).
- Per-file persisted view state (column widths, expansion, current
  selection, font zoom) under `QSettings`.
- File I/O across JSON / JSON Lines / YAML / YAML multi-document, with
  atomic writes and `mpq2py` round-trip for exact rationals.
- Theme system: immutable YAML-backed `ThemeSpec`, built-in
  light/dark, per-`JsonType` colors+fonts, bundled SVG icons,
  follow-system, opt-in user-folder hot reload, **app-level
  `Qt.ColorScheme` sync** with the active theme's mode.
- Smart kind-switch coercion (lowercase bool→str, "now" temporal
  fallback, int↔datetime epoch s/ms, bytes encode-on-switch,
  array↔object child preservation, friendly `tree/stubs.py`
  placeholders for unrecoverable cases).
- Reusable widget stack: hex editor, multiline editor, segmented
  datetime editor, big-int and exact-rational spin boxes.

---

## 2) Top-level layout (file inventory)

```text
main.py                       # CLI entry → MainWindow
mainwindow.py / mainwindow.ui # generated; never hand-edit
settings.py                   # APPLICATION_ID, default sizes, info enums
model_actions.py              # direct-mutation fallbacks for headless tests
tree_filter_proxy.py          # TreeFilterProxy (recursive name+value)
header_view_editor.py         # dormant mixin, not wired
qmultiline_editor.py          # QPlainTextEdit subclass for multiline dialog
plan.txt                      # long-term wishlist (no active phase status)
drag-n-drop.patch             # full Step-1..10 patch archive (reference only)

app/                          (≈800 LOC)
  main_window.py              # MainWindow (~418 lines)
  main_window_actions.py      # setup_connections + update_actions
  theme_controller.py         # menu, persistence, watcher, color-scheme sync
  font_controller.py          # global editor font / monospace toggle
  recent_files.py             # 8-entry recent-files list (QSettings)
  close_confirm.py            # Save/Discard/Cancel modal
  history.py                  # History menu + QUndoView dialog

documents/                    (≈1330 LOC)
  tab.py                      # JsonTab (~980 lines): undo, search, zoom, push API,
                              # push_move_rows_anchor (anchor-based primitive)
  tab_setup.py                # layout, delegates, shortcuts, filter, column-resize,
                              # drag/drop flags, model.attach_view(view) for DnD callbacks
  tab_paths.py                # proxy↔source, $.path helpers
  tab_status.py               # breadcrumb + size hint per JsonType
  tab_io.py                   # save / save-as / snapshot

tree/                         (≈1520 LOC)
  types.py                    # JsonType + parse_json_type / infer_text_json_type
  item.py                     # JsonTreeItem
  item_coercion.py            # coerce_value_for_type (Phase-3 overhaul)
  item_names.py               # validate_object_child_name / unique_child_name
  stubs.py                    # friendly placeholder values for unrecoverable coercions
  model.py                    # JsonTreeModel (drag-drop hooks: mimeTypes/mimeData/
                              # canDropMimeData/dropMimeData/supportedDrag/DropActions;
                              # _drag_source_rows cache + consume_drag_source_rows;
                              # attach_view; flags() returns ItemIsDragEnabled per row
                              # and ItemIsDropEnabled on root + OBJECT/ARRAY)
  model_roles.py              # JSON_TYPE_ROLE + display/font/tooltip helpers
  view.py                     # JsonTreeView — QTreeView subclass overriding startDrag
                              # to skip Qt's default clearOrRemove when the model
                              # already handled the internal move

delegates/                    (≈620 LOC)
  base.py                     # _CapsLockSafeLineEdit, _TextEditorDelegateBase
  value.py                    # ValueDelegate (per-JsonType editors + theme-aware paint).
                              # initStyleOption reads raw value + type directly from the
                              # JsonTreeItem when possible so bigints > 2**63-1 don't
                              # overflow Shiboken's QVariant boxing.
  value_formatting.py         # format_default / format_with_type / container preview / _apply_type_style
  bytes_codec.py              # decode_bytes / encode_bytes (BYTES/ZLIB/GZIP)
  type_delegate.py            # JsonTypeDelegate (combobox with icons)
  name_delegate.py            # NameDelegate

tree_actions/                 (≈2120 LOC)
  selection.py                # _resolve_model, proxy/source mapping, ancestor checks,
                              # selected_source_rows / top_level_source_rows /
                              # deepest_selected_rows / selection_shape (Step 9)
  anchors.py                  # MoveAnchor + anchor_at_end / before / after factories,
                              # resolve_anchor_target / resolve_anchor_insert_row,
                              # pre_pop_target_row_to_anchor, anchor_is_cycle/no_op
                              # — single anchor primitive for every move caller (Step 9)
  clipboard.py                # MIME format, build_tree_mime / entries_from_mime /
                              # source_paths_from_mime (Step 7 envelope key);
                              # copy_selection / *_with_name / *_value_only;
                              # filter-mode projection on multi-copy (Step 9)
  paste.py                    # paste_from_clipboard + collision avoidance,
                              # paste_entries_at, paste_auto (multi-aware dispatch),
                              # paste_clones_at_targets, paste_insert_after_zip,
                              # paste_replace_zip, paste_insert_zip (Steps 9–10)
  dnd.py                      # can_drop / handle_drop (Steps 6–7).
                              # MoveAction: drains model.consume_drag_source_rows()
                              # and routes to tab.push_move_rows; marks the originating
                              # view so JsonTreeView.startDrag skips clearOrRemove.
                              # CopyAction / cross-tab: routes to paste_entries_at.
                              # _resolve_drop_target: row>=0 → (parent,row);
                              # row==-1 on container → append; row==-1 on leaf →
                              # sibling-after via parent.parent(). Cycle guard rejects
                              # any source-path that is an ancestor of target_parent.
  structure.py                # insert/cut/delete/duplicate/move/sort/expand/collapse
                              # — anchor-based; single algorithm replaces 3 prior branches.
                              # move_selection_out_up / out_down promote selection out
                              # of the parent for keyboard bubble-out.
  context_menu.py             # column-aware show_context_menu; right-click inside the
                              # multi-selection preserves it (Step 10), right-click
                              # outside collapses to the single hit row (legacy).

undo/                         (≈540 LOC)
  commands.py                 # _MoveRowCmd (kept for back-compat), _MoveRowsCmd
                              # (anchor-based; _select_placed_rows helper preserves the
                              # multi-selection through redo/undo), _RenameCmd,
                              # _EditValueCmd, _ChangeTypeCmd, _InsertRowsCmd,
                              # _RemoveRowsCmd, _SortKeysCmd
  diff.py                     # DiffApplier — surgical Qt-signal undo/redo replay

io_formats/                   (≈110 LOC)
  detect.py                   # SAVE_FORMAT_* constants + extension dispatch
  load.py                     # load_file / load_file_with_format
  dump.py                     # dump_text + mpq-safe serialization
  atomic.py                   # atomic_write / save_file (os.replace)

state/                        (≈245 LOC)
  view_state.py               # state_key / save / restore / discard
  theme_settings.py           # theme/* QSettings + resolve_active_theme
  qsettings_coercion.py       # cross-platform QSettings shape helpers

themes/                       (≈660 LOC)
  spec.py                     # ThemeSpec / Palette / TypeStyle (frozen, hashable)
  loader.py                   # YAML → ThemeSpec with total fallback
  _defaults.py                # built-in LIGHT_DEFAULT / DARK_DEFAULT
  _contrast.py                # WCAG relative_luminance / contrast_ratio
  auto.py                     # detect_system_mode (styleHints + palette fallback)
  registry.py                 # discover built-in + user themes
  icon_provider.py            # StubIconProvider / FileIconProvider
  builtin/
    light.yaml                # built-in light theme
    dark.yaml                 # built-in dark theme
    icons/                    # 18 SVGs, one per JsonType key

dialogs/                      # QHexDialog, QMultilineDialog (modal, persisted)
datetime_editor/              # BetterDateTimeEditor (segments, partial regex, TZ)
qhexedit/                     # QHexEdit + ColorManager + chunks/commands
qbigint_spinbox/              # arbitrary-precision integer spin
qmpq_spinbox/                 # exact-rational spin (gmpy2.mpq)
mpq2py/                       # mpq_serialization, mpq_json_default, MpqSafeLoader/Dumper
jsontream/                    # streaming JSON encoder (iterables)
units/                        # bits, format_bytes
coalesce/, binary/, qt2py/    # small utility packages
tests/                        # 576 collected
ai-memory/                    # this folder
```

Canonical imports:

```python
from app.main_window import MainWindow
from app.theme_controller import ThemeController
from documents.tab import JsonTab
from tree.model import JsonTreeModel
from tree.model_roles import JSON_TYPE_ROLE
from tree.item import JsonTreeItem
from tree.item_coercion import coerce_value_for_type
from tree.types import JsonType, parse_json_type, infer_text_json_type, TEXT_FAMILY
from tree.stubs import stub_integer, stub_float, stub_percent, stub_string, stub_multiline, stub_bytes_raw
from tree.view import JsonTreeView
from delegates.value import ValueDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.name_delegate import NameDelegate
from tree_actions.context_menu import show_context_menu
from tree_actions.clipboard import (
    MIME_JSON_TREE, build_tree_mime, entries_from_mime, source_paths_from_mime,
    copy_selection, copy_selection_with_name, copy_selection_value_only,
)
from tree_actions.paste import (
    paste_from_clipboard, paste_auto, paste_clones_at_targets,
    paste_insert_after_zip, paste_replace_zip, paste_entries_at,
)
from tree_actions.dnd import can_drop, handle_drop
from tree_actions.anchors import (
    MoveAnchor, anchor_at_end, anchor_before_index, anchor_after_index,
    resolve_anchor_target, pre_pop_target_row_to_anchor,
)
from io_formats.load import load_file_with_format
from io_formats.dump import dump_text
from io_formats.detect import SAVE_FORMAT_JSON, SAVE_FORMAT_JSONL, SAVE_FORMAT_YAML, SAVE_FORMAT_YAML_MULTI
from io_formats.atomic import atomic_write, save_file
from state.view_state import save, restore, discard, state_key
from state.theme_settings import resolve_active_theme
from themes import ThemeRegistry, ThemeSpec, LIGHT_DEFAULT, DARK_DEFAULT
```

---

## 3) Field formats — `JsonType` matrix

`JsonType` (StrEnum, `tree/types.py`); editors in `delegates/value.py`;
display in `delegates/value_formatting.py`; coercion in
`tree/item_coercion.py`.

| JsonType       | enum value      | Inline editor                | Display formatting                       | Coercion notes                                                   |
| -------------- | --------------- | ---------------------------- | ---------------------------------------- | ---------------------------------------------------------------- |
| `INTEGER`      | `"integer"`     | `QBigIntSpinBox`             | `str(int)`                               | int↔float/percent rounding; int sec/ms ↔ datetime parse          |
| `FLOAT`        | `"float"`       | `QMpqSpinBox`                | `mpq_serialization` decimal              | stored as `gmpy2.mpq`                                            |
| `PERCENT`      | `"percent"`     | `QMpqSpinBox` (`0..100 %`)   | `"50%"`, `"33.33%"`                      | UI is 0–100, storage is 0–1 mpq; auto-inferred when value ∈ [0,1] |
| `BOOLEAN`      | `"boolean"`     | `QComboBox` (true/false)     | `"true"` / `"false"`                     | bool → str produces lowercase `"true"`/`"false"`                 |
| `STRING`       | `"string"`      | `_CapsLockSafeLineEdit`      | elide at 80 chars                        | ASCII single-line                                                |
| `UNICODE`      | `"utf-8 line"`  | `_CapsLockSafeLineEdit`      | elide at 80 chars                        | non-ASCII single-line                                            |
| `MULTILINE`    | `"multiline"`   | `QMultilineDialog` (modal)   | `"line1 \| line2 \| ..."` joined preview | ASCII, has `\n` and (>1 newline OR >80 chars)                    |
| `TEXT`         | `"utf-8 text"`  | `QMultilineDialog` (modal)   | joined preview                           | non-ASCII multiline                                              |
| `DATE`         | `"date"`        | `BetterDateTimeEditor`       | ISO date string                          | "now" placeholder if unparseable                                 |
| `TIME`         | `"time"`        | `BetterDateTimeEditor`       | ISO time string                          | "now" placeholder                                                |
| `DATETIME`     | `"datetime"`    | `BetterDateTimeEditor`       | ISO no-tz                                | int sec/ms parsing supported; "now" fallback                     |
| `DATETIMEZONE` | `"dt+timezone"` | `BetterDateTimeEditor`       | ISO with offset                          | "now" fallback in local tz                                       |
| `BYTES`        | `"bytes"`       | `QHexDialog` (modal)         | `"<24 byte>"` via `units.format_bytes`   | base64 wire format; encode-on-switch from string/int             |
| `ZLIB`         | `"zlib"`        | `QHexDialog` (modal)         | `"<…>"`                                  | base64+zlib; cross-format re-encode lossless when `old_type` known |
| `GZIP`         | `"gzip"`        | `QHexDialog` (modal)         | `"<…>"`                                  | base64+gzip                                                      |
| `OBJECT`       | `"object"`      | n/a (children edited inline) | `"{N keys}  k: v, k2: v2, …"` (collapsed) | array→object preserves children, drops keys                      |
| `ARRAY`        | `"array"`       | n/a                          | `"[N items]  v1, v2, v3"` (collapsed)    | object→array preserves children, drops keys                      |
| `NULL`         | `"null"`        | n/a (col 2 not editable)     | `"null"`                                 | always editable type; never serialised as a string               |

Inference (`parse_json_type`):
- floats / mpq in `[0, 1]` → `PERCENT`; else → `FLOAT`.
- strings: multiline→`MULTILINE`/`TEXT`; else datetime parse first
  (`DATETIME`/`DATETIMEZONE`/`TIME`/`DATE`); else strict base64 →
  `ZLIB`/`GZIP`/`BYTES`; else `STRING`/`UNICODE`.
- `parse_json_type` is **total**: returns `STRING` + logger warning
  for unknown types.
- `JsonTreeItem.explicit_type` pins user choices so re-inference cannot
  flip them.
- `TEXT_FAMILY = {STRING, UNICODE, MULTILINE, TEXT}`. Within the family,
  `text_pseudotype_for` switches only along the ASCII axis (preserves
  single-line vs multiline shape).

Container preview (`delegates/value_formatting.py`):
- `_format_container_preview` shows `[N items]` / `{N keys}` plus the
  first 5 children, but **only when the row is collapsed**
  (`option.widget.isExpanded(siblingAtColumn(0))` is False).

---

## 4) Keyboard shortcuts

Defined in `mainwindow.ui` (window-level QActions) and
`documents/tab_setup.py::init_shortcuts` (per-tab `QShortcut`s).

| Shortcut       | Scope  | Action                                       |
| -------------- | ------ | -------------------------------------------- |
| `Ctrl+N`       | window | New (empty) tab                              |
| `Ctrl+O`       | window | Open file dialog                             |
| `Ctrl+S`       | window | Save                                         |
| `Ctrl+Shift+S` | window | Save As                                      |
| `Ctrl+Q`       | window | Exit                                         |
| `Ctrl+I`       | window | Insert sibling **before**                    |
| `Ctrl+Shift+I` | window | Insert sibling **after**                     |
| `Del`          | window | Remove row                                   |
| `Ctrl++`       | window | Zoom In                                      |
| `Ctrl+-`       | window | Zoom Out                                     |
| `Ctrl+0`       | window | Reset zoom                                   |
| `Ctrl+F`       | tab    | Focus filter line edit                       |
| `Ctrl+C`       | tab    | Copy selection                               |
| `Ctrl+X`       | tab    | Cut selection                                |
| `Ctrl+V`       | tab    | Paste                                        |
| `Ctrl+Shift+V` | tab    | **Multi-insert** (`paste_insert_after_zip`) — zip-pair clipboard top-level entries with top-level selected targets; inserts each entry as sibling-after the matching target |
| `Ctrl+Alt+V`   | tab    | **Multi-replace** (`paste_replace_zip`) — zip-pair clipboard top-level entries with top-level selected targets; replaces each target's value |
| `Ctrl+D`       | tab    | Duplicate selection                          |
| `Alt+Up`       | tab    | Move selected row(s) up; at row 0 bubble out before parent |
| `Alt+Down`     | tab    | Move selected row(s) down; at last row bubble out after parent |
| `Ctrl+Alt+Up`  | tab    | Move selection **out of parent** (promote to grandparent, before parent) |
| `Ctrl+Alt+Down`| tab    | Move selection **out of parent** (promote to grandparent, after parent)  |
| `Ctrl+Alt+S`   | tab    | Sort keys (under selected OBJECT)            |
| `F2` / Enter   | tree   | Edit current cell (Qt default)               |
| _mouse_        | tree   | **Drag-and-drop** — left-click+drag moves selection between/onto OBJECT/ARRAY rows; Ctrl-drag = copy; cycle-guard rejects drops into self/descendant; drop on a leaf becomes sibling-after |

Undo/redo have no explicit shortcuts wired — the **History** menu owns
Undo, Redo and "Show History…" via `app/history.py` (Qt's built-in
Ctrl+Z / Ctrl+Shift+Z still work on focused widgets but not on the
tree itself).

---

## 5) Menus

### Menu bar (from `mainwindow.ui` + runtime additions)

- **File**: New, Open, *Recent* (submenu, ≤ 8, runtime), Save, Save As,
  Exit.
- **Actions**: Insert Row (before), Insert Row after, Remove Row.
  `aboutToShow` triggers `update_actions`.
- **View**: Expand All, Collapse All, Zoom In/Out/Reset, **Theme**
  submenu (runtime via `ThemeController.setup_theme_menu`).
- **History** (runtime via `app/history.py`): Undo, Redo, Show
  History….

### Theme submenu (built by `ThemeController`)

- **Follow system** (checkable)
- **Watch user theme folder** (checkable, opt-in `QFileSystemWatcher`
  with 250 ms debounce)
- **Light themes** / **Dark themes** submenus, exclusive `QActionGroup`s
- **Reload themes**
- **Open themes folder…**

### Tree context menu (`tree_actions/context_menu.py::show_context_menu`)

Column-aware. Top-level layout (when col 0 / col 2 has a selection):

- **Copy** — column-aware: name col → `copy_selection_with_name`,
  value col → `copy_selection_value_only`, otherwise full `copy_selection`.
- **Cut**
- **Paste ▸** (whole submenu disabled when clipboard has no tree-paste-able
  content; per-item enable also gated by selection / container constraints)
  - **Paste (auto)** — smart placement (container ⇒ child append,
    primitive ⇒ sibling after); calls `paste_from_clipboard`
  - **Paste Before** — `paste_before`
  - **Paste After** — `paste_after`
  - **Paste as Child** — `paste_as_child` (enabled iff current is
    OBJECT/ARRAY)
  - **Paste — Replace Value** — `paste_replace_value`; replaces the
    current node's entire subtree with the clipboard value via
    `tab.push_edit_value`. Requires exactly one clipboard entry.
- **Insert ▸** (fresh empty/null node)
  - **Insert Before** — `insert_sibling_before`
  - **Insert After**  — `insert_sibling_after`
  - **Insert as Child** — `insert_child_current` (enabled iff current is
    OBJECT/ARRAY)
- **Duplicate**, **Delete** (disabled on root)
- **Move Up / Move Down** (boundary-aware)
- **Sort Keys / Sort Keys (Recursive)** (only enabled under OBJECT)
- **Expand All / Collapse All**

Column 1 (type column) shows only `Expand All` / `Collapse All` to avoid
accidental edits while clicking the type cell.

Clipboard MIME type is `application/x-json-tree`; payload preserves names
so paste keeps full type info. Name-collision avoidance under OBJECT
parents uses `_copy_name` / `unique_child_name` to generate `_copy`,
`_copy_2`, … suffixes. The placement-aware paste functions all share
`_paste_entries_at` and `_resolve_paste_target` in
`tree_actions/paste.py`.

---

## 6) File I/O matrix

Defined in `io_formats/`. `detect_format(path)` dispatches by
extension.

| Format     | Extensions          | Constant                 | Load                                              | Dump                                                                         |
| ---------- | ------------------- | ------------------------ | ------------------------------------------------- | ---------------------------------------------------------------------------- |
| JSON       | `.json`             | `SAVE_FORMAT_JSON`       | `simplejson.load(parse_float=mpq)`                | `simplejson.dumps(..., use_decimal=True, default=mpq_json_default, indent=2)` |
| JSON Lines | `.jsonl`, `.ndjson` | `SAVE_FORMAT_JSONL`      | line-by-line `simplejson.loads(parse_float=mpq)`  | one `dumps` per row                                                          |
| YAML       | `.yaml`, `.yml`     | `SAVE_FORMAT_YAML`       | `yaml.load_all(MpqSafeLoader)` (single doc)       | `yaml.dump(MpqSafeDumper)`                                                   |
| YAML multi | `.yaml`, `.yml`     | `SAVE_FORMAT_YAML_MULTI` | `yaml.load_all` returns list                      | `yaml.dump_all(MpqSafeDumper)`                                               |

Atomic writes via `os.replace` in `atomic_write(path, text)` →
`save_file(path, data, save_format)`.

The detected format is stashed on the tab as `tab.save_format` so a
subsequent `Save` keeps the original shape (notably YAML-multi).
`Save As` opens `QFileDialog.getSaveFileName` with four format
filters. On a successful Save-As to a new path,
`state.view_state.discard(old_path)` is called.

`simplejson` cannot combine `parse_float=mpq` with `use_decimal=True`
on the pinned version; load uses `parse_float=mpq` only, save uses
`use_decimal=True`. Documented incompatibility, not a bug.

---

## 7) Status bar / breadcrumb

`documents/tab_status.py`:
- `_on_current_changed` writes a permanent message of the form
  `$.foo.bar[2].baz  (string, 24 chars)` via
  `permanent_message_callback`.
- `size_hint_for_item` per JsonType:
  - text family → `… chars`
  - OBJECT → `… keys`
  - ARRAY → `… items`
  - bytes family → `format_bytes(len(decoded))`
- Transient action messages (Open/Save/copy/cut/paste/etc.) go through
  `status_message_callback(text, timeout_ms)`.

`tree/model_roles.py::ToolTipRole` returns the full value capped at
4 KB + ellipsis when raw text > 80 chars.

---

## 8) Tree model — `tree/`

### `tree/model.py` — `JsonTreeModel`

- `QAbstractItemModel` over a single `root_item: JsonTreeItem`.
- Three fixed columns: `Name | Type | Value`.
- `show_root: bool` exposes the synthetic root row (tabs use
  `show_root=True`; legacy tests use `False`).
- `flags()` is data-aware (col 0 editable only under OBJECT parents;
  col 1 always editable; col 2 keyed off cached
  `JsonTreeItem.editable`).
- `setData` routes through `JsonTreeItem.set_data` (col 0/2) or
  `change_type` (col 1, with `typeChanged(QModelIndex, lossy:bool)`).
- Optional `icon_provider`; `data(..., DecorationRole)` for col 1
  returns the type icon. `set_icon_provider` swaps with identity
  short-circuit.
- Mutation helpers: `move_row`, `change_type`, `sort_keys`
  (recursive option), `insertRows` / `removeRows` via context-managed
  `beginInsert*` / `beginRemove*`.

### `tree/model_roles.py`

- `JSON_TYPE_ROLE = UserRole + 1` for col 2 — consumed by
  `ValueDelegate.initStyleOption`.
- `EditRole`: raw value (`mpq`, `int`, `bool`, `None`, base64-`str`).
- `DisplayRole`: stringified path for non-delegate clients
  (`"true"/"false"`, `"null"`, `mpq_serialization` for mpq).
- `ToolTipRole`: full value capped at 4 KB.
- `FontRole`: italicizes col-0 names with non-ASCII characters.
- Theme colors are **not** in model roles; only col-1 icons are.

### `tree/item.py` — `JsonTreeItem`

- One JSON node. Stores `name`, `value`, `parent_item`,
  `child_items`, cached `editable` / lazy `row()`, and
  `explicit_type` (user-pinned).
- Recursively expands `dict` → OBJECT, `list` → ARRAY.
- `set_data(column, value)` is total across cols 0/1/2.
- `to_json()` rebuilds Python primitives; raises `ValueError` for any
  remaining unnamed OBJECT child.

### `tree/item_coercion.py` — Phase-3 overhaul

`coerce_value_for_type(new_type, value, *, strict, old_type=None)`:
- bool → str produces lowercase `"true"`/`"false"`.
- DATE/TIME/DATETIME/DATETIMEZONE: when value is unparseable, fall
  back to `_now_for_type` (current time at minute/second precision)
  instead of the 1970 epoch zero.
- Integer ↔ DATETIME round-trip: integers in seconds and milliseconds
  parse to a datetime; reverse path emits seconds-since-epoch.
- BYTES/ZLIB/GZIP: encoding-on-switch from text/int; cross-format
  re-encode is lossless when `old_type` is provided.
- ARRAY ↔ OBJECT: morph preserves children. Object→array drops keys
  in insertion order; array→object names children `item1`, `item2`, …
- Unrecoverable cases (with `strict=False`) substitute `tree/stubs.py`
  placeholders (`stub_integer`, `stub_float`, `stub_percent`,
  `stub_string`, `stub_multiline`, `stub_bytes_raw`) — random picks
  from a curated "famous values" pool so the user notices it's a
  placeholder rather than blank `0` / `""`.

### `tree/item_names.py`

- `validate_object_child_name` — duplicate/empty rejection.
- `unique_child_name(base="new_key", used_names=None)` — `new_key`,
  `new_key_2`, … fallback chain.

---

## 9) Editing layer — `delegates/`

### `delegates/value.py` — `ValueDelegate(_TextEditorDelegateBase)`

Editors per JsonType: see § 3. Routing rules:
- Inline numeric / boolean / string / datetime editors commit via
  `_commit(...)` → ascends parent chain to find a `JsonTab` host and
  calls `tab.commit_set_data(idx, value, role)`. Falls back to
  `model.setData` when no tab ancestor exists (headless tests).
- Modal editors (`QMultilineDialog`, `QHexDialog`) capture
  `QPersistentModelIndex` on open and commit via the same `_commit`
  path on close, surviving row mutations during the modal session.
- BYTES decode wrapped in
  `try/except (ValueError, OSError, zlib.error, binascii.Error)`;
  failures surface via `_notify_status` (status-bar callback) and
  return `None` instead of raising.
- `initStyleOption`: reads `JSON_TYPE_ROLE` + `EditRole`, sets
  `option.text` via `format_with_type(...)`, applies the theme's
  `TypeStyle` foreground/background/bold/italic, suppresses container
  preview when the row is expanded, and preserves platform selection
  highlight.

### `delegates/value_formatting.py`

- `format_default(value, max_text_len=80)` — null/bool/mpq/bytes/long
  string formatting.
- `format_with_type(value, json_type, *, item, show_preview)` —
  PERCENT %, BYTES family `<…>`, MULTILINE/TEXT joined with
  `_MULTILINE_SEPARATOR = " | "`, container preview when
  `show_preview=True` and item supplied.
- `_apply_type_style(option, style, *, selected, allow_background)` —
  shared by both ValueDelegate and JsonTypeDelegate.

### `delegates/type_delegate.py` — `JsonTypeDelegate`

- Combobox of all `JsonType` entries; preselect via `findData`.
- Theme-aware: paints the cell with the row's `TypeStyle` foreground
  when not selected; combo items show the `IconProvider`'s type icon.
- Commits route through `JsonTab.commit_set_data` if a tab ancestor
  exists.

### `delegates/name_delegate.py` — `NameDelegate`

- `_CapsLockSafeLineEdit` for col-0 rename; commits via the same
  `_commit` path.

### `delegates/base.py`

- `_CapsLockSafeLineEdit` and `_TextEditorDelegateBase` swallow
  lock-key `KeyPress` and layout-switch `FocusOut` events so xkb
  layout switches don't collapse the editor mid-typing.

---

## 10) Per-tab editor — `documents/`

`documents.tab.JsonTab(QWidget)` (~580 lines) is the single source of
truth for one document.

- Holds `JsonTreeModel`, `TreeFilterProxy`, three column delegates
  (`NameDelegate` col 0, `JsonTypeDelegate` col 1, `ValueDelegate`
  col 2), a `QUndoStack`, and the current `ThemeSpec` + `IconProvider`.
- Constructor: `update_actions_callback`, `status_message_callback`,
  `data` (default `_DEFAULT_DATA` legacy demo, explicit `data={}`
  empty), `file_path`, `show_root`, `permanent_message_callback`,
  `theme`, `icon_provider`.
- Owns the search line edit (debounced 150 ms via `QTimer`, Ctrl+F).
- Typed-command push API: `push_move_row` (delegates to `push_move_rows`),
  `push_move_rows(sources, target_parent, target_row)` (Step 3 — N-row
  atomic move, cycle-guard included), `push_rename`,
  `push_edit_value`, `push_change_type`, `push_insert_rows`,
  `push_remove_rows`, `push_sort_keys`. `commit_set_data(index, value,
  role)` is the single delegate-side mutation entry point and
  dispatches by column.
- `mergeWith` collapses consecutive same-path edits within a 500 ms
  window for `_RenameCmd` / `_EditValueCmd` (ids `0x0E710001` /
  `0x0E710002`).
- Undo/redo replay via `undo.diff.DiffApplier` — emits surgical Qt
  model signals so expansion and selection survive replay.
- Move commands capture subtree-relative expansion + selection state and
  replay it on redo/undo, so moved branches keep open/closed state.
- Dirty state tied to `undo_stack.cleanChanged`; `dirtyChanged(bool)`
  signal updates the tab title (`*` suffix) via `display_name()`.
- `set_theme(theme, icon_provider=None)` updates both theme-aware
  delegates and the model icon provider, then emits recursive
  `dataChanged` spans with `Foreground/Background/Font/DecorationRole`;
  undo stack, expansion and selection all survive.
- Font zoom: `Ctrl++`, `Ctrl+-`, `Ctrl+0`. Persisted as `_font_pt` in
  view state.
- **Column-resize tracking** (Phase 2): `_user_sized_columns: set[int]`
  + `_programmatic_column_resize` guard flag. The `sectionResized`
  handler records user-driven resizes only; zoom helpers and
  `resize_key_columns` set the guard so they never poison the set.

### `documents/tab_setup.py`

- Builds a `tree.view.JsonTreeView` (subclass of `QTreeView`) with
  `UniformRowHeights`, `AlternatingRowColors`, `ExtendedSelection`,
  `SelectItems`, `ScrollPerPixel`, and native drag/drop:
  `setDragEnabled(True)`, `setAcceptDrops(True)`,
  `setDropIndicatorShown(True)`,
  `setDragDropMode(QAbstractItemView.DragDropMode.DragDrop)`,
  `setDefaultDropAction(Qt.DropAction.MoveAction)`.
- Calls `tab.model.attach_view(tab.view)` so
  `JsonTreeModel.dropMimeData` can dispatch to
  `tree_actions/dnd.py::handle_drop(view, ...)`.
- Attaches delegates, wires shortcuts (including `Alt+Up/Down`,
  `Ctrl+Alt+Up/Down` move-out, `Ctrl+Shift+V` paste-insert-zip,
  `Ctrl+Alt+V` paste-replace-zip), search proxy, font-zoom helpers,
  and column-resize tracking.

### `documents/tab_paths.py`

- Pure helpers on `(model, proxy)`: `proxy_to_source`, `source_to_view`,
  `index_path`, `index_from_path`, `qualified_name` (returns
  JSON-style `$.foo.bar[2]`).

### `documents/tab_io.py`

- `save()` (uses stored `save_format` if set, else detects from
  extension) and `save_as(path=None)` opens
  `QFileDialog.getSaveFileName` with four format filters.

---

## 11) Tree actions / clipboard — `tree_actions/`

- `selection.py`: `_resolve_model`, `_to_source_index`, `_to_view_index`,
  `_index_path`, `_is_ancestor`.
  **Public helpers (Step 1):** `selected_source_rows(view)`,
  `top_level_source_rows(view)` (ancestor-pruned), and
  `selection_spans_multiple_parents(rows) -> bool`.
  Private-underscore aliases kept for back-compat one release.
- `clipboard.py`: **Canonical MIME (de)serializer (Step 2):**
  `build_tree_mime(model, source_rows) -> QMimeData | None` — builds the
  wire payload (binary `application/x-json-tree` + `text/plain` fallback,
  sorted by `_index_path`).
  `entries_from_mime(mime) -> list[dict] | None` — pure decoder (no
  clipboard access).  `_clipboard_entries()` wraps it for system clipboard.
  `copy_selection`, `copy_selection_with_name`, `copy_selection_value_only`
  are thin orchestrators that call `build_tree_mime` and push to the
  clipboard. MIME type constant `MIME_JSON_TREE = "application/x-json-tree"`.
  All three public names re-exported from `tree_actions/__init__.py`.
- `paste.py`: `paste_from_clipboard` with collision avoidance and reusable
  `paste_entries_at(...)` for decoded payload insertion.
  **Multi-aware paste dispatchers (Steps 9–10):** `paste_auto(view)`
  is the Ctrl+V entry point — single selection ⇒ legacy
  `paste_from_clipboard`, multi-selection ⇒ `paste_clones_at_targets`
  (every selected row receives a clone of the entire clipboard payload).
  `paste_insert_after_zip(view)` (Ctrl+Shift+V) and
  `paste_replace_zip(view)` (Ctrl+Alt+V) zip-pair the top-level
  clipboard entries with the top-level selection (no deep scan,
  truncated to `min(len(entries), len(targets))`).
- `dnd.py`: `can_drop(...)` / `handle_drop(...)`.
  - Reads `source_paths_from_mime(mime)` to enforce a **cycle guard**:
    no source path may be a prefix of `target_parent`'s path.
  - `_resolve_drop_target(model, row, parent)`: `row >= 0` →
    `(parent, clamp(row))`; `row == -1` on OBJECT/ARRAY → append at end;
    `row == -1` on a leaf → sibling-after (`parent.parent()`,
    `parent.row()+1`); `row == -1` on the invalid root index → append
    at root.
  - `MoveAction`: drains `model.consume_drag_source_rows()` (set by
    `JsonTreeModel.mimeData`, top-level-only), routes to
    `tab.push_move_rows(...)` for a single undo step, then calls
    `view.mark_drag_handled_internally()` so `JsonTreeView.startDrag`
    skips Qt's default post-drag row removal.
  - `CopyAction` / cross-tab: routes to `paste_entries_at(...)`.
  - Pushes a transient status message
    (`"Moved N rows under $.foo"` / `"Copied N rows under $.bar"`).
- `anchors.py` (Step 9): single move primitive shared by Alt+Up/Down,
  Ctrl+Alt+Up/Down move-out, drag-drop, paste, and duplicate.
  `MoveAnchor(parent_path, before_path, after_path)` describes the gap
  *between* two siblings (or end-of-parent); helpers
  `anchor_at_end / anchor_before_index / anchor_after_index` build
  them, `resolve_anchor_target` / `resolve_anchor_insert_row` /
  `pre_pop_target_row_to_anchor` convert them to a pre-pop
  `target_row` after the sources are removed, and
  `anchor_is_cycle` / `anchor_is_no_op` short-circuit invalid moves.
- `structure.py`: `insert_sibling_before/after`, `insert_child_current`,
  `delete_selection`, `cut_selection`, `duplicate_selection`,
  `move_selection_up/down`, `move_selection_out_up/out_down`
  (Ctrl+Alt+Up/Down bubble-out — promote selection to the grandparent
  level, before/after the original parent), `sort_selection_keys(recursive)`,
  `expand_all`, `collapse_all`. All move callers feed `MoveAnchor`s
  into `JsonTab.push_move_rows_anchor`.
- `context_menu.py`: column-aware menu (see § 5).
  **Selection preservation (Step 10):** when the right-click hit is
  *inside* an existing multi-selection, the menu keeps the whole
  selection; right-click *outside* collapses to the single hit row.

Each action routes through `JsonTab.push_*` typed helpers when the
view's ancestor is a `JsonTab`, else falls back to `model_actions.py`
direct mutators (headless tests).

---

## 12) Filter proxy — `tree_filter_proxy.py`

`TreeFilterProxy(QSortFilterProxyModel)`:
- `setRecursiveFilteringEnabled(True)` keeps ancestors of matches
  visible.
- `set_filter_text(text)` normalises (strip + casefold) and calls
  `invalidate()`.
- `filterAcceptsRow` matches the needle against `name`; for leaves,
  also against the value text. Containers pass when any descendant
  passes.

---

## 13) View state — `state/`

### `state/view_state.py`

- `state_key(path)` → `"view_state/<sha1[:16]>"` keyed off the resolved
  absolute path.
- `save(tab)` persists column widths, expanded paths, current-selection
  path, and `_font_pt` under `QSettings(APPLICATION_ID, "view_state")`.
- `restore(tab)` returns `True` when state was found and applied;
  callers fall back to defaults (`expandAll` +
  `resizeColumnToContents`) on `False`.
- `iter_expanded_relative_paths(view, source_index)` and
  `apply_expanded_relative_paths(view, source_index, paths)` support
  move-time subtree expansion preservation.
- `discard(path)` removes the group on `Save As` to a new path.
- Hard cap `MAX_EXPANDED_PATHS = 5000`.

### `state/qsettings_coercion.py`

- `_coerce_int`, `_coerce_int_list`, `_coerce_path`, `_coerce_paths` —
  cross-platform `QSettings` shape helpers.

### `state/theme_settings.py`

- `QSettings(APPLICATION_ID, "theme")` keys: `theme/follow_system`,
  `theme/light_name`, `theme/dark_name`, `theme/manual_name`,
  `theme/watch_user_dir`.
- `resolve_active_theme(registry, app)` — manual mode falls back to
  manual name → mode-preferred name → built-in default.

---

## 14) Theming — `themes/` + `app/theme_controller.py`

- `themes/spec.py`: frozen `TypeStyle(fg, bg, bold, italic, icon)`,
  `Palette`, `ThemeSpec(name, mode, palette, types, icon_search_paths)`.
  `ThemeSpec.types` is always complete across all `JsonType`.
- `themes/loader.py`: `load_theme_yaml`, `parse_theme_mapping`. Total
  fallback semantics; required `name`/`mode`; warns-and-ignores
  malformed optional fields. Unknown keys logged.
- `themes/_defaults.py`: `LIGHT_DEFAULT` / `DARK_DEFAULT`.
- `themes/_contrast.py`: WCAG `relative_luminance`, `contrast_ratio`.
- `themes/auto.py`: `detect_system_mode(app)` prefers
  `styleHints().colorScheme()`, falls back to palette window lightness.
- `themes/registry.py`: built-ins via `importlib.resources`, user
  overrides via `QStandardPaths.AppConfigLocation/themes/*.yaml`.
  `list_themes()` sorted by `(mode, casefolded name)`. User themes
  with the same name as a built-in override that built-in.
  `build_icon_provider(theme)` returns `FileIconProvider` when any
  type has an icon key, else `StubIconProvider`.
- `themes/icon_provider.py`: `StubIconProvider` returns empty
  `QIcon()`; `FileIconProvider` resolves `<key>.svg/.png/.ico` across
  configured search paths, caches per-`JsonType`, warns once per
  missing asset, supports `reload()`.
- `themes/builtin/light.yaml` / `dark.yaml` reproduce the shipped
  defaults; `themes/builtin/icons/` carries 18 SVGs (one per
  JsonType key).

`app/theme_controller.py::ThemeController`:
- Owns the View → Theme submenu (see § 5).
- Persists follow-system, per-mode preferred names, manual override,
  watch flag.
- 250 ms debounce on `QFileSystemWatcher` events.
- Reacts to `QGuiApplication.styleHints().colorSchemeChanged`.
- **`_sync_app_color_scheme(theme)`** (Phase-5 app theming): when a
  theme is applied, calls
  `styleHints().setColorScheme(Qt.ColorScheme.{Light,Dark})` to flip
  Qt's bundled chrome (menus, dialogs, toolbars) to match the theme's
  `mode`. Suppresses the resulting `colorSchemeChanged` signal via
  `_suppress_scheme_signal`. No custom palette/stylesheet is
  installed; per-type cell colouring stays in delegates.
- `shutdown()` disconnects `colorSchemeChanged` so a closed window
  stops responding to stale signals.

---

## 15) Undo system — `undo/`

Typed `QUndoCommand` subclasses (`undo/commands.py`):
`_MoveRowCmd` (kept for import compatibility), `_MoveRowsCmd` (Steps 3
+ 9 — anchor-based N-row atomic cross-parent move; `mergeWith` always
`False`; internal `_select_placed_rows` helper rebuilds the
`QItemSelection` for every placed row using
`ClearAndSelect | Rows` so the multi-selection survives both `redo`
and `undo`),
`_RenameCmd`, `_EditValueCmd`, `_ChangeTypeCmd`,
`_InsertRowsCmd`, `_RemoveRowsCmd`, `_SortKeysCmd`. Path-based
addressing avoids `QModelIndex` invalidation across mutations.

`undo/diff.py::DiffApplier.apply(parent_path, old, new)` performs
surgical insert/remove/move/setData calls so view expansion and
current selection survive replay.

History UI: `app/history.py::setup_history_menu` adds the **History**
menu (`Undo`, `Redo`, `Show History…`); the modal dialog is a
`QUndoView` bound to the active tab's `QUndoStack` via
`bind_undo_signals(tab)`.

`MainWindow.update_actions` enables `Save`/`Save As`/`Expand`/
`Collapse`/`Zoom*` whenever a tab exists; insert/remove require a
valid current index.

---

## 16) Tests

`tests/` collects **779 tests** as of 2026-05-13; **776 pass, 3 fail**
under `QT_QPA_PLATFORM=offscreen`. The failing ones —
`test_app_color_scheme.py::test_light_theme_sets_light_color_scheme`,
`test_app_color_scheme.py::test_dark_theme_sets_dark_color_scheme`,
`test_theme_switching.py::test_color_scheme_follows_selected_theme` —
fail because Qt's offscreen QPA platform reports
`Qt.ColorScheme.Unknown` after `setColorScheme`. Not a code bug; runs
green on real platforms.

**Drag-and-drop / multi-action suites (Steps 1–10):**
- `test_multiselect_foundation.py` — Step 1: public
  `selected_source_rows` / `top_level_source_rows` /
  `selection_spans_multiple_parents` + ancestor pruning + round-trip
  copy/paste.
- `test_mime_payload.py` — Step 2: `build_tree_mime` /
  `entries_from_mime` round-trip, order stability, malformed-JSON
  guards, MIME constant check.
- `test_undo_multimove.py` — Step 3: 8-case `_MoveRowsCmd` matrix
  (same-parent forward/backward block move, cross-parent move,
  cycle guard, no-merge, single-row delegation, forward/backward
  block invariants).
- `test_keyboard_multimove.py` + `test_keyboard_multimove_app_mode.py`
  — Step 4: Alt+Up/Down on multi-selection under both
  `SelectRows` and live `SelectItems` modes, bubble-out at parent
  boundary, multi-selection preserved across the move
  (`_select_placed_rows`).
- `test_move_preserves_expansion.py` — Step 5: subtree expansion +
  current/selection state round-trip across redo/undo.
- `test_drag_drop_internal.py` — Step 6: model-level `mimeData` →
  `dropMimeData` pipeline (no synthetic mouse events) for same-parent
  / cross-parent / cross-tab moves, copy via `CopyAction`, single
  undo step.
- `test_drag_drop_matrix.py` + `test_drag_drop_property.py` — extra
  matrix and property-style coverage on the resolved-target/cycle
  matrix.
- `test_drop_policies.py` — Step 7: self-into-descendant cycle guard,
  on-leaf drop becomes sibling-after, empty-viewport drop policy,
  Ctrl-drag copy vs no-Ctrl move, status callback receives
  `"Moved N rows"` / `"Copied N rows"`.
- `test_anchor_move.py` — Step 9: `MoveAnchor` primitive, anchor
  resolution / cycle / no-op detection,
  `pre_pop_target_row_to_anchor` arithmetic.
- `test_multi_action_semantics.py` — Step 9–10: `paste_auto`
  multi-dispatch, `paste_clones_at_targets`, `paste_insert_after_zip`,
  `paste_replace_zip`.
- `test_context_menu_multiselect.py` — Step 10: right-click inside
  the selection preserves it; right-click outside collapses to the
  single hit row.

Notable suites:
- Phase-3 coercion: `test_kind_switch_coercion.py` (bool→str
  lowercase, "now" temporal fallback, int sec/ms ↔ datetime,
  bytes encode-on-switch, array↔object morph).
- Phase-4 preview: `test_container_preview.py` (`[N items]` /
  `{N keys}` + first 5 children, expand suppresses preview).
- Phase-5 app color scheme: `test_app_color_scheme.py` +
  `test_theme_switching::test_color_scheme_follows_selected_theme`.
- Theme stack: `test_theme_loader.py`, `test_theme_registry.py`,
  `test_icon_provider.py`, `test_value_delegate_theme.py`
  (includes the bigint-overflow regression on
  `ValueDelegate.initStyleOption`), `test_icons_in_view.py`,
  `test_theme_switching.py`.
- Editor / phase suites: `test_smoke_model.py`,
  `test_smoke_mainwindow.py`, `test_tree_correctness.py`,
  `test_type_editing.py`, `test_tree_actions_clipboard.py`,
  `test_tree_actions_structure.py`, `test_undo_redo.py`,
  `test_undo_redo_scenario.py`, `test_typed_undo_commands.py`,
  `test_typed_undo_perf.py`, `test_perf_smoke.py`,
  `test_file_io_phase4.py`, `test_phase_5_*.py`.
- Widget-stack: `test_better_datetime_buffer`,
  `test_datetime_editor`, `test_dialog_settings`, `test_jsontream`,
  `test_mpq2py`, `test_partial_float_re`, `test_partial_regex`,
  `test_pretty_jsontream`, `test_qhexedit_highlighting`,
  `test_units`, `test_validator`.

---

## 17) Sample data & dependencies

Sample fixtures: `data.yaml`, `data.json`, `data.jsonl`,
`data-multidoc.yaml`, `john-doe.yaml`, `nginx-hpa.yaml`.

`requirements.txt`:
```
PySide6==6.11.0
PyYAML==6.0.3
python-dateutil==2.9.0.post0
gmpy2==2.3.0
pytest==9.0.3
tzdata==2026.2
simplejson==4.1.1
```
`pytest-qt` is **not pinned** even though `qtbot` is used by theme
tests.

`Makefile`: `lint:` runs `autoflake .`, `isort . --extend-skip
mainwindow.py`, `black . --line-length 120 --extend-exclude
mainwindow.py`. No `make test` / `themes-check` target.

`pytest.ini`: `pythonpath = .`.

---

## 18) Suggested reading order

1. `main.py` → `app/main_window.py` → `app/main_window_actions.py`
2. `documents/tab.py` (push API, dirty state, zoom) +
   `documents/tab_setup.py` (delegate + shortcut wiring)
3. `tree/types.py` → `tree/model.py` + `tree/model_roles.py` →
   `tree/item.py` → `tree/item_coercion.py` + `tree/stubs.py`
4. `delegates/value.py` + `delegates/value_formatting.py` →
   `delegates/type_delegate.py` + `delegates/name_delegate.py`
5. `undo/commands.py` + `undo/diff.py`
6. `tree_actions/context_menu.py` + the rest of `tree_actions/`
7. `tree_filter_proxy.py`, `state/view_state.py`
8. `io_formats/{detect,load,dump,atomic}.py`
9. `themes/` + `app/theme_controller.py`
10. `model_actions.py` (headless fallback)
11. `datetime_editor/`, `qhexedit/`, `qbigint_spinbox/`, `qmpq_spinbox/`

---

## 19) Practical mental model

- **Shell layer** — `main.py` → `app/` → `state/` / `io_formats/` /
  `settings.py`
- **Tab layer** — `documents/` (owns `QUndoStack`, typed-command push
  API, search, breadcrumb, column-resize tracking)
- **Undo** — `undo/commands.py` + `undo/diff.py`
- **Tree data** — `tree/` (types, item, model, coercion, stubs)
- **Filter** — `tree_filter_proxy.py`
- **Editing** — `delegates/` (+ `dialogs/`, `qmultiline_editor.py`)
- **Actions / clipboard** — `tree_actions/` + `model_actions.py`
- **Advanced editor widgets**:
  - datetime → `datetime_editor/`
  - binary → `qhexedit/` + `dialogs/qhexedit_dlg.py`
  - multiline → `qmultiline_editor.py` + `dialogs/qmultiline_dlg.py`
  - exact numerics → `qbigint_spinbox/`, `qmpq_spinbox/`, `mpq2py/`
- **Theming** — `themes/` + `app/theme_controller.py` (delegate
  styling + app-level `Qt.ColorScheme` sync)
- **Utilities / tests** — `jsontream/`, `units/`, `qt2py/`,
  `coalesce/`, `binary/`, `tests/`
