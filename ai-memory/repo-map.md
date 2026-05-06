# Editable-Tree-Model-Example — repo map

_Last scanned: 2026-05-06. Phases 0–6 are shipped, including the full
theming stack and the Phase-6 refactor that extracted
`app/theme_controller.py`. A new shipping plan landed on the same date
under `plans/` (six phases covering context-menu polish, zoom column
preservation, kind-switch coercion overhaul, display/preview, full-app
theming, and cross-phase tests/memory refresh) — none of those phases
have shipped yet. The package refactor (Phases 01–37) remains
complete: all former top-level "god modules" have been split into
cohesive packages and the old compatibility shims (`json_tab.py`,
`ui.py`, `tree_view.py`, `tree_model.py`, `tree_item.py`,
`delegate.py`, `enums.py`, `file_io.py`, `view_state.py`) remain
removed. The last recorded full-suite baseline in memory is **401
passed** (`2026-04-26`); the current tree now **collects 451 tests**,
and the dedicated theming surface (**50 tests**) passes under
`QT_QPA_PLATFORM=offscreen pytest -q`._

## 1) What this repo is

A PySide6 desktop app that started life as Qt's **Editable Tree Model**
example and has been rewritten into a real **structured-data editor**.
After Phases 0–6 plus the package refactor it provides:

- a tabbed multi-document shell with file open / save / save-as / recent
  files / close-confirm / persisted view state
  (`app/`, `documents/`, `state/`, `io_formats/`, `settings.py`)
- a JSON-centric tree model/view stack with type-aware editing
  (`tree/`, `delegates/`)
- typed `QUndoCommand`-based undo/redo with `mergeWith` on consecutive
  same-path edits, plus a `QUndoView` history dialog (`undo/`,
  `app/history.py`)
- a clipboard / cut / copy / paste / duplicate / move / sort tree
  action layer routed through the typed undo stack (`tree_actions/`)
- a debounced recursive name+value filter proxy
  (`tree_filter_proxy.py`) with Ctrl+F focus binding
- font zoom (Ctrl+= / Ctrl+- / Ctrl+0) persisted per file
- a permanent status-bar breadcrumb (`$.foo.bar[2].baz (string, 24 chars)`)
  plus transient action messages
- presentational `ValueDelegate` formatting for PERCENT / mpq /
  bytes-typed cells, with `ToolTipRole` carrying full text for long
  values
- an app-global theming system with immutable YAML-backed theme specs,
  built-in light/dark defaults, type-aware delegate coloring, bundled
  type icons, follow-system theme selection, and opt-in hot reload of
  user theme files (`themes/`, `state/theme_settings.py`,
  `app/theme_controller.py`)
- reusable custom editor widgets (`qhexedit/`, `qmultiline_editor.py`,
  `datetime_editor/`, `qbigint_spinbox/`, `qmpq_spinbox/`) and helper
  packages (`mpq2py/`, `jsontream/`, `coalesce/`, `binary/`, `qt2py/`,
  `units/`)

## 2) Top-level module / package layout

```text
main.py                       # CLI entry → app.main_window.MainWindow
mainwindow.py / mainwindow.ui # generated; never hand-edit
settings.py                   # APPLICATION_ID, default sizes, info enums
model_actions.py              # direct-mutation fallbacks for headless tests
tree_filter_proxy.py          # TreeFilterProxy (debounced recursive filter)
header_view_editor.py         # dormant mixin, kept for future use
qmultiline_editor.py          # QPlainTextEdit subclass for the multiline dialog

app/                          # application shell
  main_window.py              # MainWindow class
  main_window_actions.py      # action wiring + update_actions()
  theme_controller.py         # ThemeController: menu, persistence,
                              # watcher, hot reload, follow-system
  recent_files.py             # QSettings-backed recent-files list
  close_confirm.py            # Save / Discard / Cancel flow
  history.py                  # History menu + QUndoView dialog

documents/                    # per-tab document widget
  tab.py                      # JsonTab class (~500 lines)
  tab_setup.py                # layout/delegate/search/shortcut wiring
  tab_paths.py                # proxy/source mapping, $.path helpers
  tab_status.py               # breadcrumb + size hints
  tab_io.py                   # save / save-as wrappers

undo/                         # typed undo system
  commands.py                 # _MoveRowCmd, _RenameCmd, _EditValueCmd,
                              # _ChangeTypeCmd, _InsertRowsCmd,
                              # _RemoveRowsCmd, _SortKeysCmd
  diff.py                     # DiffApplier — surgical undo/redo replay

tree/                         # data + model layer
  types.py                    # JsonType enum + parse/infer helpers
  item.py                     # JsonTreeItem
  item_coercion.py            # cross-type value coercion table
  item_names.py               # unique-name + object-key validation
  model.py                    # JsonTreeModel
  model_roles.py              # JSON_TYPE_ROLE + display/font helpers

delegates/                    # editing layer
  base.py                     # _CapsLockSafeLineEdit, _TextEditorDelegateBase
  value.py                    # ValueDelegate
  value_formatting.py         # initStyleOption/displayText helpers
  bytes_codec.py              # decode_bytes / encode_bytes
  type_delegate.py            # JsonTypeDelegate
  name_delegate.py            # NameDelegate

tree_actions/                 # context menu + clipboard + structural ops
  selection.py                # proxy/source mapping, ancestor checks
  clipboard.py                # MIME format, copy/cut payloads
  paste.py                    # paste_from_clipboard + collision avoidance
  structure.py                # insert/delete/duplicate/move/sort/expand
  context_menu.py             # show_context_menu

io_formats/                   # file load/save
  detect.py                   # extension dispatch + format constants
  load.py                     # JSON / JSONL / YAML / YAML-multi load paths
  dump.py                     # dump_text + mpq-safe serialization
  atomic.py                   # atomic_write / save_file

state/                        # persisted view state
  view_state.py               # state_key / save / restore / discard
  theme_settings.py           # theme/follow-system/manual/watch prefs
  qsettings_coercion.py       # cross-platform QSettings shape helpers

themes/                       # theming subsystem
  spec.py                     # ThemeSpec / Palette / TypeStyle
  loader.py                   # YAML → ThemeSpec with total fallback
  _defaults.py                # built-in default light/dark specs
  auto.py                     # system light/dark detection
  registry.py                 # discover built-in + user themes
  icon_provider.py            # Stub/File icon providers
  builtin/
    light.yaml                # built-in light theme
    dark.yaml                 # built-in dark theme
    icons/                    # bundled SVG type icon set
```

Canonical imports use these package paths, e.g.:

```python
from app.main_window import MainWindow
from documents.tab import JsonTab
from tree.model import JsonTreeModel
from tree.model_roles import JSON_TYPE_ROLE
from tree.item import JsonTreeItem
from tree.types import JsonType, parse_json_type
from delegates.value import ValueDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.name_delegate import NameDelegate
from tree_actions.context_menu import show_context_menu
from tree_actions.clipboard import copy_selection
from tree_actions.paste import paste_from_clipboard
from io_formats.load import load_file_with_format
from io_formats.dump import dump_text
from io_formats.atomic import atomic_write, save_file
from state.view_state import save, restore, discard, state_key
from state.theme_settings import resolve_active_theme
from themes import ThemeRegistry, ThemeSpec
```

## 3) Runtime entrypoint and main window

### `main.py`
- Creates a `QApplication`.
- Instantiates `app.main_window.MainWindow` with the optional CLI
  filename (defaulting to `data.yaml`).
- Resizes the window to `settings.WINDOW_DEFAULT_SIZE`.

### `app/main_window.py`
- `MainWindow(QMainWindow, Ui_MainWindow)` (~345 lines).
- `setup_model(filename)` opens the file via `_open_path`; no-op on
  empty string (so test fixtures can pass `""`).
- `_add_tab(data, file_path)` creates a `JsonTab` with `show_root=True`,
  passes the active `ThemeSpec` + `IconProvider`, expands all, calls
  `state.view_state.restore`, and sets focus to the synthetic root row.
- `close_tab(index)` and `closeEvent` route through
  `app.close_confirm._confirm_close` (Save / Discard / Cancel) and call
  `state.view_state.save` per tab.
- `copy_action()` delegates to `tree_actions.clipboard.copy_selection`.
- Keeps a small set of underscore compatibility wrappers
  (`_apply_theme`, `_on_theme_selected`, `_on_theme_fs_event`, …)
  that now forward to `ThemeController`; tests still use these entry
  points.

### `app/theme_controller.py`
- Owns the app-global theme state: `ThemeRegistry`, current
  `ThemeSpec`, current `IconProvider`, and the View → Theme submenu.
- Handles:
  - follow-system persistence and per-mode theme preferences,
  - manual theme selection,
  - the opt-in "Watch user theme folder" flag,
  - `QFileSystemWatcher` + 250 ms debounce reload,
  - opening the user theme directory,
  - reacting to `QGuiApplication.styleHints().colorSchemeChanged`,
  - rebuilding menu actions after registry reload.
- Calls back into `MainWindow` via `on_theme_changed(theme,
  icon_provider)` so tabs repaint without model/view rebuilds.

### `app/main_window_actions.py`
- File menu: `New`, `Open`, `Save`, `Save As`, `Recent` submenu (cap 8),
  `Quit`.
- View menu: `Expand All`, `Collapse All`, `Zoom In/Out/Reset`, plus a
  Theme submenu created by `ThemeController`.
- Actions menu: insert before / insert after / remove row.
- `update_actions()` enables Save/SaveAs/View when a tab exists;
  insert/remove require a valid current index.

### `app/recent_files.py`
- Loads/persists/prunes the recent-files list under
  `QSettings(APPLICATION_ID, "app")`. Caps at 8, drops missing paths.

### `app/close_confirm.py`
- Save / Discard / Cancel modal helper for dirty tabs.

### `app/history.py`
- Adds a `History` menu with Undo / Redo / `Show History…` (a
  `QUndoView` dialog bound to the active tab's `QUndoStack`).
- `_bind_undo_signals(tab)` wires `canUndoChanged` / `canRedoChanged`.

### `mainwindow.ui` / `mainwindow.py`
- Designer XML / generated. Declares the standard action set
  (`fileOpenAction`, `fileSaveAction`, `rowInsertAction`, etc.).
  Never hand-edit `mainwindow.py`.

### `settings.py`
- `APPLICATION_ID` (UUID-namespaced for `QSettings`).
- `WINDOW_DEFAULT_SIZE`, `MODAL_WINDOW_SIZE`.
- `IntegerInfo / FloatInfo / MultiLineInfo / SingleLineInfo` `StrEnum`s.

## 4) Per-tab editor — `documents/`

`documents.tab.JsonTab(QWidget)` (~500 lines) is the single source of
truth for one document:

- Holds the source `JsonTreeModel`, a `TreeFilterProxy`, three column
  delegates (`NameDelegate` col 0, `JsonTypeDelegate` col 1,
  `ValueDelegate` col 2), and a `QUndoStack`.
- Also holds the currently active `ThemeSpec` and `IconProvider`, both
  supplied by `MainWindow` / `ThemeController`.
- Constructor: `data` / `file_path` / `show_root` /
  `update_actions_callback` / `status_message_callback` /
  `permanent_message_callback`. When `data is _DEFAULT_DATA`, falls
  back to a built-in demo dictionary (legacy compatibility for tests
  that call bare `JsonTab(...)`); explicit `data={}` gives an empty
  document.
- Owns the `search_edit` `QLineEdit` (debounced 150 ms via `QTimer`),
  bound shortcuts: `Ctrl+F`, `Ctrl+C/X/V`, `Del`, `Ctrl+D`, `Alt+↑/↓`,
  `Ctrl+Alt+S`, `Ctrl+= / Ctrl+- / Ctrl+0`.
- Typed-command push API: `push_move_row`, `push_rename`,
  `push_edit_value`, `push_change_type`, `push_insert_rows`,
  `push_remove_rows`, `push_sort_keys`. `commit_set_data(index, value,
  role)` is the single delegate-side mutation entry point and dispatches
  by column. The typed `QUndoCommand` subclasses live in
  `undo/commands.py`; `mergeWith` collapses consecutive same-path edits
  within a 500 ms window for `_RenameCmd` / `_EditValueCmd`.
- Undo/redo replay uses `undo.diff.DiffApplier` (`apply(parent_path,
  old, new)`) which emits surgical Qt model signals so expansion and
  selection survive.
- Dirty state: tied to `undo_stack.cleanChanged`. `dirtyChanged(bool)`
  signal updates `MainWindow` tab title (`*` suffix). `is_dirty`
  property; `display_name()` formats the title.
- `set_theme(theme, icon_provider=None)` updates both delegates and the
  model icon provider, then emits recursive `dataChanged` spans with
  `ForegroundRole`, `BackgroundRole`, `FontRole`, and
  `DecorationRole`; undo stack, expansion and current selection survive.

### `documents/tab_setup.py`
- Builds the QTreeView, attaches delegates, wires shortcuts, search
  proxy, font-zoom helpers.
- Injects `tab._theme` into `ValueDelegate` / `JsonTypeDelegate` and
  `tab._icon_provider` into `JsonTreeModel` / `JsonTypeDelegate`.

### `documents/tab_paths.py`
- Pure-ish helpers operating on `(model, proxy)`:
  `_proxy_to_source`, `_source_to_view`, `_index_path`,
  `_index_from_path`, `_qualified_name` (returns JSON-style
  `$.foo.bar[2]` paths).

### `documents/tab_status.py`
- `_size_hint_for_item` per JsonType (text/object/array/bytes-family).
- `_on_current_changed` writes the breadcrumb status message.

### `documents/tab_io.py`
- `save()` (uses stored `save_format` if set, else detects from
  extension) and `save_as(path=None)` opens
  `QFileDialog.getSaveFileName` with four format filters.

## 5) Tree data layer — `tree/`

### `tree/model.py` — `JsonTreeModel`
- `QAbstractItemModel` over a single `root_item: JsonTreeItem`.
- Three fixed columns: `Name`, `Type`, `Value`.
- `show_root: bool` exposes the synthetic root row in the view.
- `flags()` is data-aware (column 0 editable only under OBJECT parents;
  column 1 always editable; column 2 keyed off cached
  `JsonTreeItem.editable`).
- `setData` routes through `JsonTreeItem.set_data` (col 0/2) or
  `change_type` (col 1, with `typeChanged(QModelIndex, lossy:bool)`
  signal).
- Accepts an optional `icon_provider`; `data(..., DecorationRole)` for
  column 1 returns the type icon for the row.
- `set_icon_provider(provider)` swaps the provider with an identity
  short-circuit; repaint emission is handled one layer up by
  `JsonTab.set_theme`.
- Mutation helpers used by typed commands: `move_row`, `change_type`,
  `sort_keys` (recursive option), `insertRows` / `removeRows`
  (context-managed `beginInsert*` / `beginRemove*`).

### `tree/model_roles.py`
- `JSON_TYPE_ROLE = UserRole + 1`.
- Display-text / tooltip / font-role helpers.
- `EditRole` returns the raw value (`mpq`, `int`, `bool`, `None`,
  bytes-as-base64-str, …) for round-trip with editors.
- `DisplayRole` keeps a stringified path for non-delegate clients
  (lowercase `true/false`, `null`, `mpq_serialization` for mpq).
- `JSON_TYPE_ROLE` returns `item.json_type` for col 2; consumed by
  `ValueDelegate.initStyleOption` to format PERCENT / BYTES / ZLIB /
  GZIP without re-parsing.
- `ToolTipRole` for col 2 returns the full value capped at 4 KB +
  ellipsis when raw text > 80 chars.
- `FontRole` italicizes col 0 names that contain non-ASCII.
- Theme colors intentionally do **not** live in model roles; the model
  stays theme-agnostic apart from column-1 `DecorationRole` icons.

### `tree/item.py` — `JsonTreeItem`
- One JSON node. Stores `name`, `value`, `parent_item`, `child_items`,
  cached `editable`, lazy cached `row()` index, and `explicit_type`
  flag for user-pinned types.
- Recursively expands `dict` → OBJECT, `list` → ARRAY.
- `set_data(column, value)` is total across columns 0/1/2.
- `to_json()` rebuilds Python primitives; raises `ValueError` for any
  remaining unnamed OBJECT child.

### `tree/item_coercion.py`
- `_coerce_value_for_type`, `_normalize_value_for_type`,
  `_apply_typed_value`, `_compute_editable` — pure(-ish) coercion table
  used by `JsonTreeItem` and `DiffApplier`.

### `tree/item_names.py`
- `validate_object_child_name` — duplicate/empty rejection.
- `unique_child_name(base="new_key", used_names=None)` generates
  `new_key`, `new_key_2`, … suffixes.

### `tree/types.py` — `JsonType` + type detection
- `JsonType`: integer, float, percent, boolean, string, unicode,
  multiline, text, date, time, datetime, datetime-with-timezone,
  bytes, zlib, gzip, object, array, null.
- `parse_json_type(value)` is **total**: returns `STRING` with a logger
  warning for unknown types (no exception).
- Heuristics: floats / mpq in `[0,1]` → PERCENT; other floats / mpq →
  FLOAT.
- `_looks_like_base64` requires syntactic validity; datetime is
  checked before bytes.
- Text-axis helpers: `infer_text_json_type`, `text_pseudotype_for`,
  `TEXT_FAMILY` (single-line vs multiline x ascii-only vs unicode).

## 6) Editing/delegate layer — `delegates/`

### `delegates/value.py` — `ValueDelegate(_TextEditorDelegateBase)`
Editors per JsonType:
- INTEGER → `QBigIntSpinBox`
- FLOAT / PERCENT → `QMpqSpinBox` (PERCENT gets `0..100 %` UI but
  stores `0..1` mpq)
- BOOLEAN → `QComboBox`
- STRING / UNICODE → `_CapsLockSafeLineEdit`
- DATE / TIME / DATETIME / DATETIMEZONE → `BetterDateTimeEditor`
- MULTILINE / TEXT → modal `QMultilineDialog`, commit via
  `QPersistentModelIndex` → `JsonTab.commit_set_data`
- BYTES / ZLIB / GZIP → modal `QHexDialog`; decode wrapped in
  `try/except (ValueError, OSError, zlib.error, binascii.Error)`,
  failures surface via `_notify_status` (status-bar callback)
- `initStyleOption` is theme-aware: it reads `JSON_TYPE_ROLE`, formats
  the text via `format_with_type`, and applies per-type foreground /
  background / bold / italic styling while preserving platform
  selection colors.

### `delegates/value_formatting.py`
- `initStyleOption` reads `EditRole` + `JSON_TYPE_ROLE` and sets
  `option.text` to a type-aware formatted string (PERCENT → `"50%"`,
  BYTES-family → `"<24 byte>"`, mpq → decimal form, long strings
  elide to 80 chars).
- `_apply_type_style(...)` centralizes theme styling so both value and
  type delegates share the same selection-aware font/foreground logic.

### `delegates/base.py`
- `_CapsLockSafeLineEdit` and `_TextEditorDelegateBase` swallow
  lock-key `KeyPress` and layout-switch `FocusOut` events to keep the
  editor open under xkb layout-switch keybinds.

### `delegates/type_delegate.py` — `JsonTypeDelegate(QStyledItemDelegate)`
- Combo box of all `JsonType` entries; preselects the current type via
  `findData`.
- `_interactive` flag set during `setModelData`; commit routes through
  `JsonTab.commit_set_data` if a tab ancestor exists.
- Also receives the active `ThemeSpec` + `IconProvider`: the display
  cell text is theme-colored when not selected, and the editor combo is
  populated with icons via `addItem(icon, text, data)`.

### `delegates/name_delegate.py` — `NameDelegate(_TextEditorDelegateBase)`
- `_CapsLockSafeLineEdit` for col 0 rename. Commit routes through
  `ValueDelegate._commit` so renames land on the typed undo stack.

### `delegates/bytes_codec.py`
- `decode_bytes(b64string, json_type)` / `encode_bytes(data, json_type)`
  round-trip BYTES/ZLIB/GZIP payloads.

## 7) Tree view actions / clipboard — `tree_actions/`

`tree_actions.context_menu.show_context_menu(tree_view, position)`
builds an outliner-style menu:

- Copy (Ctrl+C), Cut (Ctrl+X), Paste (Ctrl+V), Delete (Del)
- Duplicate (Ctrl+D)
- Move Up (Alt+↑) / Move Down (Alt+↓)
- Sort Keys / Sort Keys (Recursive)
- Insert Sibling Before / After
- Insert Child (only when current row is OBJECT/ARRAY)
- Expand All / Collapse All

Each action is proxy-aware via `tree_actions.selection`
(`_resolve_model`, `_to_source_index`, `_to_view_index`,
`_index_path`, `_is_ancestor`, `_top_level_selected_rows`), then
either:
- routes through `JsonTab.push_*` typed helpers when the view's parent
  is a `JsonTab`, or
- falls back to `model_actions.py` direct helpers for headless tests.

Clipboard MIME format is `application/x-json-tree`; the JSON-tree
metadata payload preserves names so paste keeps full type info.
Name-collision avoidance under OBJECT parents during paste/duplicate
uses `_copy_name` / `unique_child_name`, generating `_copy`,
`_copy_2`, … suffixes.

`tree_actions.structure.expand_all(view)` /
`tree_actions.structure.collapse_all(view)` are thin wrappers used by
both the context menu and the View menu.

## 8) Filter proxy — `tree_filter_proxy.py`

`TreeFilterProxy(QSortFilterProxyModel)`:
- `setRecursiveFilteringEnabled(True)` keeps ancestors of matches
  visible.
- `set_filter_text(text)` normalizes (strip + casefold) and calls
  `invalidate()`.
- `filterAcceptsRow` matches the needle against `name` for every row;
  for leaves, also against the value text. Container nodes pass when
  any descendant passes.

## 9) View state — `state/`

### `state/view_state.py`
- `state_key(path)` → `"view_state/<sha1[:16]>"` keyed off the resolved
  absolute path.
- `save(tab)` persists column widths, expanded paths,
  current-selection path, and `_font_pt` under
  `QSettings(APPLICATION_ID, "view_state")`.
- `restore(tab)` returns `True` when any state was found and applied;
  callers fall back to defaults (`expandAll` +
  `resizeColumnToContents`) on `False`.
- `discard(path)` removes the group on `Save As` to a new path.
- Hard cap `MAX_EXPANDED_PATHS = 5000`.

### `state/qsettings_coercion.py`
- `_coerce_int`, `_coerce_int_list`, `_coerce_path`, `_coerce_paths` —
  handle `QSettings`'s platform-dependent shapes (list of ints, string
  with `/` or `,` separators).

### `state/theme_settings.py`
- Stores theme-related `QSettings(APPLICATION_ID, "theme")` values:
  `theme/follow_system`, `theme/light_name`, `theme/dark_name`,
  `theme/manual_name`, and `theme/watch_user_dir`.
- Exposes small coercing getters/setters plus
  `resolve_active_theme(registry, app)`.
- Manual mode falls back to the manual theme name first, then the
  current mode's preferred theme, then the built-in default.

## 9.5) Theming system — `themes/`

### `themes/spec.py`
- Frozen, hashable dataclasses:
  - `TypeStyle(fg, bg, bold, italic, icon)`
  - `Palette(base_fg, base_bg, selection_fg, selection_bg, accent)`
  - `ThemeSpec(name, mode, palette, types, icon_search_paths)`
- `ThemeSpec.types` is always complete across all `JsonType` members.

### `themes/loader.py`
- `load_theme_yaml(path, mode_default=...)` → YAML file to fully merged
  `ThemeSpec`.
- `parse_theme_mapping(...)` accepts partial mappings, validates
  required top-level `name` / `mode`, parses colors with `QColor`,
  warns-and-ignores malformed optional fields, and resolves icon search
  paths relative to the YAML file.
- Unknown type keys in `types:` / `icons.map:` are logged and ignored.

### `themes/_defaults.py`
- Hard-coded `LIGHT_DEFAULT` / `DARK_DEFAULT` specs remain the semantic
  ground truth used for fallback merging and equality tests.

### `themes/auto.py`
- `detect_system_mode(app)` prefers `styleHints().colorScheme()` and
  falls back to palette window lightness.

### `themes/registry.py`
- Discovers built-ins via `importlib.resources` and user overrides via
  `QStandardPaths.AppConfigLocation/themes/*.yaml`.
- `list_themes()` returns `ThemeHandle(name, mode, path)` sorted by
  `(mode, casefolded name)`.
- User themes with the same name as a built-in override that built-in
  and log at INFO.
- `build_icon_provider(theme)` returns `FileIconProvider` whenever any
  type has an icon key, else `StubIconProvider`.

### `themes/icon_provider.py`
- `StubIconProvider` returns empty `QIcon()` for every type.
- `FileIconProvider` resolves `<key>.svg`, then `.png`, then `.ico`
  across configured search paths, caches per-`JsonType`, warns once per
  missing asset, and supports `reload()`.

### `themes/builtin/`
- `light.yaml` / `dark.yaml` reproduce the shipped defaults and point
  at `./icons`.
- `icons/` contains one SVG per `JsonType` key used by the built-ins.

## 10) File I/O — `io_formats/`

### `io_formats/detect.py`
- Format constants: `SAVE_FORMAT_JSON / JSONL / YAML / YAML_MULTI`.
- `detect_format(path)` dispatches by extension (`.json`, `.jsonl`,
  `.ndjson`, `.yaml`, `.yml`).

### `io_formats/load.py`
- `load_file(path)` / `load_file_with_format(path)`:
  - JSON / JSONL → `simplejson.load(parse_float=mpq)` /
    line-by-line `loads`.
  - YAML → `yaml.load_all(MpqSafeLoader)`; returns a list with the
    `YAML_MULTI` marker when there is more than one document.

### `io_formats/dump.py`
- `dump_text(path, data, save_format)`:
  - JSON → `simplejson.dumps(default=mpq_json_default, indent=2,
    use_decimal=True)`.
  - JSONL → one `dumps` per row.
  - YAML / YAML_MULTI → `yaml.dump` / `yaml.dump_all` with
    `MpqSafeDumper`.

### `io_formats/atomic.py`
- `atomic_write(path, text)` uses `os.replace` for cross-platform
  atomic rename. `save_file(path, data, save_format)` is the
  convenience wrapper used by `documents/tab_io.py`.

## 11) Toolbar / menu insert helpers — `model_actions.py`

Direct-mutation helpers used as fallbacks when the view has no
`JsonTab` parent:
- `_copy_name(base, used)` for paste/duplicate name suffixes.
- `action_insert_row_before / _after`, `action_insert_child`,
  `action_duplicate`, `action_move_up / _down`, `action_sort_keys`.
- The toolbar/menu paths in `MainWindow` go through `JsonTab` typed
  commands; `model_actions.py` is mostly dormant in app flow but kept
  as a stable API for headless tests.

## 12) Custom widgets and support packages

### `datetime_editor/`
- `BetterDateTimeEditor` (segment stepping, partial regex / partial
  input support, timezone editing). `regex.py` / `validator.py` /
  `enums.py` back the parser.

### `qhexedit/`
- `QHexEdit` over `QIODevice` chunks; selection / overwrite / insert
  modes; ASCII zone; clipboard; undo; modified-byte highlighting;
  theming via `ColorManager`.

### `dialogs/`
- `qhexedit_dlg.QHexDialog` — modal hex editor with `QSettings`
  persistence.
- `qmultiline_dlg.QMultilineDialog` — modal multiline editor with
  word-wrap / line-numbers / monospaced toggles.

### `qmultiline_editor.py`
- `QPlainTextEdit` derivative used by the multiline dialog.

### Numeric editors
- `qbigint_spinbox.QBigIntSpinBox` — arbitrary-precision integer.
- `qmpq_spinbox.QMpqSpinBox` — exact rational using `gmpy2.mpq` and
  `mpq2py.mpq_serialization` for stable display.

### Helpers
- `mpq2py/` — `mpq_serialization`, `mpq_json_default`,
  `MpqSafeLoader`, `MpqSafeDumper`.
- `jsontream/` — streaming JSON encoder wrapper supporting iterables.
- `units/` — `bits` / `format_bytes` size formatting.
- `coalesce/`, `binary/`, `qt2py/` — small utility packages.

### `header_view_editor.py`
- `HeaderViewEditorMixin` — currently unused by `JsonTab` (commented
  out). Kept for future column header editing.

## 13) Tests

Editor / phase suites:
- `test_smoke_model.py`, `test_smoke_mainwindow.py`,
  `test_tree_correctness.py`, `test_type_editing.py`,
  `test_tree_actions_clipboard.py`, `test_tree_actions_structure.py`,
  `test_undo_redo.py`, `test_undo_redo_scenario.py`,
  `test_typed_undo_commands.py`, `test_typed_undo_perf.py`,
  `test_perf_smoke.py`, `test_file_io_phase4.py`,
  `test_phase_5_1_carryover.py`, `test_phase_5_2_display_formatting.py`,
  `test_phase_5_3_status_bar_breadcrumb.py`,
  `test_phase_5_4_persisted_view_state.py`,
  `test_phase_5_5_search_filter.py`,
  `test_phase_5_6_misc_polish.py`.

Theming / Phase-1–6 suites:
- `test_theme_loader.py`, `test_theme_registry.py`,
  `test_icon_provider.py`, `test_value_delegate_theme.py`,
  `test_icons_in_view.py`, `test_theme_switching.py`.

Pre-existing widget-stack suites: `test_better_datetime_buffer`,
`test_datetime_editor`, `test_dialog_settings`, `test_jsontream`,
`test_mpq2py`, `test_partial_float_re`, `test_partial_regex`,
`test_pretty_jsontream`, `test_qhexedit_highlighting`, `test_units`,
`test_validator`.

Current inventory (`2026-05-06`): **451 tests collected** via
`pytest --collect-only -q`.

Last recorded whole-suite runtime baseline in memory remains the older
`2026-04-26` run: **401 tests passed in ~3 s** under
`QT_QPA_PLATFORM=offscreen`, with no teardown segfault.

Targeted theming validation run (`2026-05-06`): **50 tests passed**
under `QT_QPA_PLATFORM=offscreen pytest -q` across the six theming
files above.

## 14) Sample data

- `data.yaml` / `data.json` / `data.jsonl` / `data-multidoc.yaml` /
  `john-doe.yaml` — multi-format fixtures for manual smoke + future
  Phase 6 round-trip tests.

## 15) Dependencies / tooling

### Python (`requirements.txt`)
- `PySide6==6.11.0`
- `PyYAML==6.0.3`
- `python-dateutil==2.9.0.post0`
- `gmpy2==2.3.0`
- `pytest==9.0.3`
- `tzdata==2026.2`
- `simplejson==4.1.1`

`simplejson` is now pinned. `pytest-qt` is still not pinned even though
theme-switching tests use `qtbot`; some older suites still roll their
own `QApplication` fixture.

### `Makefile`
- `autoflake .`
- `isort . --extend-skip mainwindow.py`
- `black . --line-length 120 --extend-exclude mainwindow.py`
- No `make test` or `themes-check` target yet.

### `pytest.ini`
- `pythonpath = .`

## 16) Suggested reading order for future work

1. `main.py`
2. `app/main_window.py` + `app/main_window_actions.py`
3. `documents/tab.py` — typed commands, push API, dirty state, font
   zoom.
4. `undo/commands.py` + `undo/diff.py` — typed `QUndoCommand`s and
   surgical replay.
5. `tree/model.py` + `tree/model_roles.py` — `data` / `setData` /
   `change_type` / `move_row` / `sort_keys` / `JSON_TYPE_ROLE`.
6. `tree/item.py` + `tree/item_coercion.py` + `tree/item_names.py`.
7. `tree/types.py` — `parse_json_type`, text family heuristics.
8. `delegates/value.py` + `delegates/value_formatting.py` — editors
   per type, `initStyleOption` formatting, `_commit` routing.
9. `tree_actions/context_menu.py` + `tree_actions/{selection,
   clipboard, paste, structure}.py`.
10. `tree_filter_proxy.py` — recursive filter.
11. `state/view_state.py` — persisted column widths / expansion /
    current / font zoom.
12. `io_formats/{detect,load,dump,atomic}.py` — JSON / JSONL / YAML /
    YAML-multi load + save + atomic write.
13. `model_actions.py` — fallback direct mutations for headless tests.
14. `datetime_editor/better_dt_editor.py`
15. `qhexedit/__init__.py`

## 17) Practical mental model

- **Shell layer** — `main.py` → `app/` → `state/` / `io_formats/` /
  `settings.py`
- **Tab layer** — `documents/` (owns `QUndoStack`, typed-command push
  API, search proxy hookup, breadcrumb plumbing)
- **Undo** — `undo/commands.py` + `undo/diff.py`
- **Tree data** — `tree/`
- **Filter** — `tree_filter_proxy.py`
- **Editing** — `delegates/` (+ `dialogs/`, `qmultiline_editor.py`)
- **Actions / clipboard** — `tree_actions/` + `model_actions.py`
- **Advanced editor widgets**:
  - datetime → `datetime_editor/`
  - binary → `qhexedit/` + `dialogs/qhexedit_dlg.py`
  - multiline text → `qmultiline_editor.py` +
    `dialogs/qmultiline_dlg.py`
  - exact numerics → `qbigint_spinbox/`, `qmpq_spinbox/`,
    `mpq2py/`
- **Utilities / tests** — `jsontream/`, `units/`, `qt2py/`,
  `coalesce/`, `binary/`, `tests/`

After Phase 6 plus the package refactor the editor is functionally
complete for daily use and structurally clean: no source file (other
than the generated `mainwindow.py`) exceeds ~540 lines, and the new
theme logic now lives mostly in `app/theme_controller.py` instead of
ballooning `MainWindow`. The remaining surface area is Phase-7-style
polish: contributor docs for theme authors, theme snapshots /
accessibility tests, broader delegate/round-trip QA, and optional UX
work such as match highlighting and full-app palette application.
