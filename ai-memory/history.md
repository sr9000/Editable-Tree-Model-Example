# Historical changelog (archive)
_This file holds the **resolved/historical** items pulled out of
`todo-n-fixme.md` so that doc stays compact for active LLM context.
Nothing here is open. Re-open an item by moving it back to
`todo-n-fixme.md` with a fresh repro._
## How to read this file
- Items are grouped by feature plan / phase, most-recent first.
- Each entry preserves the original wording so audits don't re-explore
  resolved problems.
- For broader context (what each module currently does) see
  `repo-map.md`. For the current TODO/FIXME surface see
  `todo-n-fixme.md`.
---
---

## Resolved (kept for posterity)

The following bugs/features were fixed or delivered in past phases;
listed once here so future audits don't reopen them.

### File-UX sweep (shipped 2026-05-26, branch `file-ux`)

Single squashed series of commits. New menu/clipboard/context-menu UX
plus a couple of undo and field-case bug fixes.

- **Reload from Disk** — `Ctrl+R`, `app/main_window.py::reload_from_disk`
  + `_confirm_reload_dirty_tab` + `_reload_tab_from_path`. Three-button
  dialog: Discard memory edits / Overwrite disk with memory / Cancel.
  Reloads via `load_file_with_format` and replays through
  `tab._diff_apply`; clears undo stack and `setClean()` on success.
  Disabled when no `tab.file_path`.
- **Close Tab / Reopen Closed Tab** — `Ctrl+W` / `Ctrl+Shift+T`,
  LIFO `_closed_tabs_stack` capped at `_MAX_CLOSED_TABS = 10`. Empty
  untitled tabs close without prompt; non-empty untitled tabs prompt
  via `confirm_close(..., prompt_for_untitled_nonempty=True)`
  (`app/close_confirm.py`). Discard-on-close stores file-path-only
  snapshot; reopen reloads from disk instead of resurrecting dirty
  data.
- **New From Clipboard** — `Ctrl+Space`, `MainWindow.new_from_clipboard`
  → `tree_actions.clipboard.clipboard_to_tab_data()` (JSON, then YAML
  single-doc, then YAML multi-doc; rejects bare scalars). Action gated
  on `clipboard_text_is_valid_data()`.
- **Copy as YAML text** — checkable File-menu toggle persists via
  `state/clipboard_settings.py` (`clipboard/text_format` =
  `json` | `yaml`). All copy paths (`build_tree_mime`,
  `copy_selection_with_name`, `copy_selection_value_only`) route
  through `_dump_text(payload)` which honours the setting and falls
  back to a normalised JSON→YAML path when YAML's representer can't
  encode `NumberAffix` etc.
- **YAML paste** — `entries_from_mime` tries JSON first, then
  `yaml.safe_load` accepting only `dict` / `list`. Internal
  `application/x-json-tree` MIME still takes priority.
- **Context-menu polish** — `tree_actions/context_menu.py::_add`
  returns `None` for disabled actions, so inactive entries are hidden
  rather than greyed. Type column (col 1) shows no menu instead of
  Expand/Collapse-All. **Expand Recursively / Collapse Recursively**
  scope to the selected subtree (root selection = whole document)
  via `expand_selection_recursive` / `collapse_selection_recursive`
  in `tree_actions/structure.py`. Switch Case on the root applies
  document-wide. **Go To** action appears only while the tab's
  `search_edit` has text; clears the filter, expands the path, and
  selects the clicked cell.
- **Save enabled only when dirty** — `main_window_actions.update_actions`
  now also gates `fileSaveAction` on `tab.is_dirty`, gates
  `fileReloadAction` on `tab.file_path`, gates close/reopen actions
  appropriately, and is hooked into `fileMenu.aboutToShow` /
  `viewMenu.aboutToShow` so menu state is fresh on open.
- **Tab tooltips show full path** — `_refresh_tab_presentation(tab)`
  sets both `tabText(display_name)` and `tabToolTip(file_path or
  "Untitled")`; called from `_add_tab`, `_on_tab_dirty`, and the
  reload path.
- **Field-case tokenizer rewrite** — `tree_actions/field_case.py`
  replaces the single regex with `_tokenize` that distinguishes
  *hard separators* (`.`, `:`, …) from *standard separators*
  (`_`, `-`). Each segment is re-rendered in the target case;
  punctuation separators are preserved verbatim. Adds Unicode-letter
  support and digit/letter boundary splitting (`http2` →
  `Http2`/`http_2`). New cases covered in
  `tests/test_field_case_actions.py`.
- **Cross-parent move undo bug** — `undo/commands.py::_MoveRowsCmd`
  now snapshots `source_names` at command construction. On redo into
  an OBJECT parent that already contains a colliding name, the redo
  path auto-renames (`x` → `x_2`); undo previously restored the
  renamed string into the source. Both `redo` and `undo` arms now
  consult `_original_name_for(...)` so undo restores the original
  `name` exactly. Regression in
  `tests/test_undo_multimove.py::test_cross_parent_move_undo_restores_original_name_after_collision_rename`.
- **Tests** — new suites `test_reload_from_disk` (4),
  `test_tab_lifecycle` (close/reopen, 14), `test_clipboard_yaml`
  (21), `test_context_menu_visibility`, `test_context_menu_goto_search`,
  `test_root_context_actions` (6). Existing
  `test_tree_actions_clipboard` adjusted for the new JSON-wrapped
  single-row copy format. `test_shortcuts_and_menu` gains
  `test_main_menu_actions_are_disabled_when_inactive` and
  `test_tab_tooltip_uses_full_path`.

### Step 7 — YAML support, multi-doc, schema picker, persistence (shipped 2026-05-16)
- **`validation/_sanitize.py`** — `to_jsonschema_input` coerces `mpq`/`Decimal`/
  `datetime`/`date`/`time`/`bytes` to jsonschema-compatible primitives; precision loss is
  validation-only, never stored.
- **`validation/yaml_validate.py`** — `validate_yaml_documents(docs, schema)`
  validates each doc separately and prefixes issue `instance_path` with `'[doc N]'`.
- **`validation/json_pointer.py`** — `instance_path_to_model_path` extended to
  accept `'[doc N]'` string tokens (via `_list_index_from_token`) in addition to
  plain `int` tokens when traversing a list.
- **`state/validation_settings.py`** — `clear_schema_path` added; key format
  updated to `validation/<sha1[:16]>` (was raw path string).
- **`documents/tab.py`** — `JsonTab.__init__` accepts `save_format=None` so the
  first `revalidate()` during construction already knows the format; `_init_validation_state`
  falls back to persisted manual binding when `discover_schema` returns `origin=="none"`;
  `revalidate()` routes through `to_jsonschema_input` sanitization and dispatches to
  `validate_yaml_documents` when `save_format == SAVE_FORMAT_YAML_MULTI`.
- **`app/validation_dock.py`** — New signals `attachSchemaRequested`,
  `reloadSchemaRequested`, `openSchemaFileRequested`; new "Schema ▸" `QToolButton`
  with `QMenu` (Attach / Reload / Open); `_on_schema_changed` enables/disables
  Reload and Open based on `ref.path`.
- **`app/main_window.py`** — Wires new dock signals; `_on_attach_schema_requested`
  opens `QFileDialog` and calls `write_schema_path`; `_on_clear_schema_requested`
  calls `clear_schema_path` before `tab.clear_schema()`; `_save_tab` calls
  `clear_schema_path(old_path)` on Save As to a new path; `_open_path` passes
  `save_format` directly to `_add_tab` / `JsonTab.__init__`.
- **3 new test suites**: `test_validation_yaml` (7), `test_validation_yaml_multi`
  (11), `test_validation_persistence` (10).
- **`README.md`** and **`ai-memory/`** documents updated.

### Drag-and-drop / multi-action plan — Steps 1–10 (shipped 2026-05-13)
- **Step 1 — multiselect foundation.** Promoted
  `_selected_rows` / `_top_level_selected_rows` to public
  `selected_source_rows` / `top_level_source_rows`; added
  `selection_spans_multiple_parents`. Back-compat underscore
  aliases retained. `tests/test_multiselect_foundation.py`.
- **Step 2 — reusable MIME (de)serializer.** Extracted
  `build_tree_mime(model, source_rows) -> QMimeData | None` and
  pure decoder `entries_from_mime(mime)`. `MIME_JSON_TREE`,
  both helpers re-exported from `tree_actions/__init__.py`.
  `tests/test_mime_payload.py`.
- **Step 3 — atomic multi-row undo move.** `_MoveRowsCmd` with
  pre-pop `target_row` arithmetic for same-parent forward/backward
  moves; `JsonTab.push_move_rows(sources, target_parent, target_row)`
  with cycle guard; `push_move_row` now delegates. `mergeWith` always
  `False`. `tests/test_undo_multimove.py`.
- **Step 4 — keyboard multimove with bubble-out.** Alt+Up/Down on
  any selection (single, contiguous, disjoint, multi-parent); at
  the parent boundary the selection promotes/demotes across the
  parent. `_select_placed_rows` preserves the multi-selection
  through redo/undo. `tests/test_keyboard_multimove*.py`.
- **Step 5 — preserve collapse / expansion state across moves.**
  Move commands capture subtree-relative expansion and selection
  state and replay them. `tests/test_move_preserves_expansion.py`.
- **Step 6 — native drag-and-drop wired to multi-move.**
  `JsonTreeModel.mimeTypes / mimeData / canDropMimeData /
  dropMimeData / supportedDrag,DropActions / flags()`;
  `tree_actions/dnd.py::can_drop / handle_drop`;
  `documents/tab_setup.py` flips on
  `setDragEnabled / setAcceptDrops / setDropIndicatorShown /
  setDragDropMode(DragDrop)`; `model.attach_view(view)` plumbing.
  `tree/view.py::JsonTreeView` overrides `startDrag` so Qt's
  `clearOrRemove` doesn't delete the freshly-placed destination
  rows. `tests/test_drag_drop_internal.py` +
  `test_drag_drop_matrix.py` + `test_drag_drop_property.py`.
- **Step 7 — drop policies, indicators & visual cues.** Cycle
  guard via `source_paths_from_mime` envelope key in MIME;
  `_resolve_drop_target` covers row≥0, row=−1 on container, row=−1
  on leaf (sibling-after), row=−1 on invalid root. Transient
  status message `"Moved N rows under $.foo"` /
  `"Copied N rows under $.bar"`. `tests/test_drop_policies.py`.
- **Step 8 — shortcuts, menu labels, repo-map refresh.** Hooked
  `Alt+Up/Down`, `Ctrl+Alt+Up/Down` (move out of parent),
  `Ctrl+Shift+V` (paste-insert-zip), `Ctrl+Alt+V` (paste-replace-zip)
  per-tab; documented in §4 / §5 of `repo-map.md`.
- **Step 9 — move-mechanics + multi-action redesign.** Collapsed
  the three move branches (`_move_same_parent`,
  `_multi_parent_common_grandparent_move`,
  `_move_multi_parent_fallback`) into a single anchor-based
  primitive in `tree_actions/anchors.py`
  (`MoveAnchor`, `anchor_at_end / before / after`,
  `resolve_anchor_target`, `pre_pop_target_row_to_anchor`,
  `anchor_is_cycle / no_op`).
  `JsonTab.push_move_rows_anchor` is the single entry point;
  `push_move_rows` is a thin shim. New filter-mode projection in
  multi-copy; new `paste_clones_at_targets`, `paste_insert_zip`
  helpers. `tests/test_anchor_move.py` +
  `test_multi_action_semantics.py`.
- **Step 10 — multi-action paste + context-menu fixes.** Renamed
  the original `paste_insert_zip` (which actually replaced values)
  to `paste_replace_zip` (Ctrl+Alt+V); added a real
  `paste_insert_after_zip` (Ctrl+Shift+V) that inserts each
  clipboard entry as sibling-after its matching target. Added
  `paste_auto` dispatcher (single ⇒ legacy paste,
  multi ⇒ `paste_clones_at_targets`) and routed Ctrl+V through it.
  `tree_actions/context_menu.py` now preserves multi-selection on
  right-click inside the selection and collapses to the hit row
  otherwise. `tests/test_context_menu_multiselect.py`.

### Former `plans/` phases (shipped between 2026-05-06 and 2026-05-08)
- **Phase 1 — context-menu polish.** Type column shows only
  Expand/Collapse; column-aware Copy on name (`copy_selection_with_name`)
  and value (`copy_selection_value_only`) columns;
  `tree_actions/clipboard.py` exposes the three variants.
- **Phase 2 — zoom-column preservation.** `JsonTab` now tracks
  `_user_sized_columns` and a `_programmatic_column_resize` guard so
  font-zoom and `resize_key_columns` no longer poison user-resized
  widths. Wired in `documents/tab_setup.py`.
- **Phase 3 — kind-switch coercion overhaul.**
  `tree/item_coercion.py::coerce_value_for_type(..., old_type=...)`
  with: bool→str lowercase; DATE/TIME/DATETIME/DATETIMEZONE "now"
  fallback; integer sec/ms ↔ DATETIME round-trip;
  BYTES/ZLIB/GZIP encode-on-switch and lossless cross-format
  re-encode when `old_type` is known; ARRAY↔OBJECT child preservation
  with `item1, item2, …` keys; `tree/stubs.py` random "famous"
  placeholders for unrecoverable cases. Tests in
  `tests/test_kind_switch_coercion.py`.
- **Phase 4 — display & preview.** Container preview
  `[N items]  v1, v2, …` / `{N keys}  k: v, …` with first 5 children,
  suppressed when row is expanded; PERCENT renders as `%` everywhere;
  multiline previews use `_MULTILINE_SEPARATOR = " | "`. Implementation
  in `delegates/value_formatting.py::_format_container_preview`; tests
  in `tests/test_container_preview.py`.
- **Phase 5 — full-app theming via Qt color scheme.**
  `app/theme_controller.py::_sync_app_color_scheme` calls
  `QStyleHints.setColorScheme(Qt.ColorScheme.{Light,Dark})` to flip
  Qt's bundled chrome to match the active theme's `mode`. No custom
  palette/stylesheet; per-type cell colouring stays in delegates.
  Tests in `tests/test_app_color_scheme.py` and
  `test_theme_switching::test_color_scheme_follows_selected_theme`
  (the 3 offscreen-only failures are tracked under FIXME above).
- **Phase 6 — tests / memory refresh.** This memory pass + the new
  test files above. `themes/_contrast.py` (WCAG luminance / contrast
  helpers) landed as scaffolding for the not-yet-written
  accessibility suite.

### Theme phases 1–6 (2026-05-06)
- Phase 1 — `themes/spec.py`, `themes/loader.py`,
  `themes/_defaults.py`: frozen/hashable theme dataclasses, YAML
  parsing, total fallback semantics, icon-block parsing.
- Phase 2 — `themes/builtin/light.yaml` / `dark.yaml`,
  `themes/registry.py`, `themes/auto.py`, `state/theme_settings.py`:
  built-in/user discovery, system-mode detection, persisted theme
  preferences.
- Phase 3 — `ValueDelegate` / `JsonTypeDelegate` became theme-aware;
  `JsonTab.set_theme(...)` repaints open tabs via `dataChanged`
  instead of rebuilding models/views.
- Phase 4 — `themes/icon_provider.py` with `StubIconProvider` /
  `FileIconProvider`, icon-path resolution, reloadable icon caching.
- Phase 5 — bundled SVG icons under `themes/builtin/icons/`,
  `JsonTreeModel` returns `DecorationRole` for col 1, the type
  combobox reuses the same icon provider.
- Phase 6 — live View → Theme switching, follow-system persistence,
  opt-in `QFileSystemWatcher` hot reload, `colorSchemeChanged`
  handling; follow-system selection bug fixed; logic refactored into
  `app/theme_controller.py`.

### Phase 0
- `tests/test_mpq2py.py::test_mpq_with_json` — fixed by returning
  `mpq_serialization(obj)[0]` from `mpq_json_default`.
- `MainWindow.copy_action` syntactically incomplete — replaced.
- `MainWindow.insert_row` / `insert_child` / `remove_row` referenced
  non-existent `self.view` — replaced with `_current_view()`.
- `MainWindow.close_tab` had a `pass` body — now Save/Discard/Cancel
  flow.
- `ui.py` unused imports stripped; embedded C++ docstring blocks
  removed from `tree_model.py`, `tree_item.py`, `ui.py`.

### Phase 1 (original)
- `JsonTreeModel` always-False column insert/remove API removed.
- `JsonTreeItem.insert_children` now seeds `value=None`
  (single NULL row) instead of `[None] * columns`.
- `unique_child_name` introduced for OBJECT children.
- `parse_json_type` made total (returns STRING with logger warning).
- `_looks_like_base64` strict + datetime-first heuristic.
- PERCENT auto-detection narrowed.
- `flags()` decode moved to cached `JsonTreeItem.editable`.

### Phase 2
- `JsonTypeDelegate.setModelData` / `setEditorData` — proper preselect
  + commit.
- `JsonTreeItem.set_data` total across columns 0/1/2 with
  `coerce_value_for_type`.
- Type pinning via `explicit_type`.
- `ValueDelegate.setEditorData` BOOLEAN branch fixed.

### Phase 3
- Cut / Delete / Paste actions wired.
- Insert before / after distinguished.
- Typed `QUndoCommand` subclasses replace whole-document snapshots.

### Phase 4
- `MainWindow.setup_model` loads CLI files into a tab.
- File menu (Open / Save / Save As / Recent / Close-confirm /
  closeEvent) wired.
- Atomic write via `os.replace`.
- `JsonTab` accepts `data` / `file_path`; dirty-state via
  `undo_stack.cleanChanged`; `*` tab marker; `dirtyChanged` signal.
- Recent-files persisted via `QSettings`, capped at 8, missing-file
  pruning.
- JSONL and YAML multi-document formats added beyond original
  Phase-4 scope.

### Phase 5.1 – 5.6
- 5.1: `JsonTypeDelegate._interactive` flag + `JsonTab._on_type_changed`
  auto-reopen via `QTimer.singleShot(0, ...)`; dialog-edit callbacks
  use `QPersistentModelIndex` and route through
  `ValueDelegate._commit` → `JsonTab.commit_set_data`; `QHexDialog`
  decode wrapped in try/except surfacing failures via `_notify_status`;
  `_RenameCmd` / `_EditValueCmd` `id()` + `mergeWith` 500 ms window.
- 5.2: `JsonTreeModel` exposes `JSON_TYPE_ROLE` and `Qt.ToolTipRole`
  for long values; `ValueDelegate.initStyleOption` / `displayText`
  formats PERCENT, mpq, BYTES family, long strings; `units.format_bytes`
  helper.
- 5.3: `permanent_message_callback`; breadcrumb
  `$.qualified.path  (type, size hint)`; transient action messages.
- 5.4: `view_state.py` (`state_key` / `save` / `restore` / `discard`);
  `MainWindow._add_tab` / `close_tab` / `closeEvent` / `_save_tab`
  wired; font zoom on `JsonTab` (`Ctrl++`, `Ctrl+-`, `Ctrl+0`,
  persisted).
- 5.5: `tree_filter_proxy.TreeFilterProxy` recursive name+value
  filter; `JsonTab.search_edit` with 150 ms debounce; Ctrl+F focus;
  proxy↔source mapping helpers in delegates and tree-action helpers.
- 5.6: `JsonTab.resize_key_columns` on tab switch / `model.modelReset`;
  Expand/Collapse all in tree context menu and View menu; Zoom
  actions in View menu.

### Package refactor (Phases 01–37, 2026-04-26)
- Top-level "god modules" split into cohesive packages and removed:
  `json_tab.py` → `documents/`, `ui.py` → `app/`,
  `tree_view.py` → `tree_actions/`, `tree_model.py` + `tree_item.py`
  + `enums.py` → `tree/`, `delegate.py` → `delegates/`,
  `file_io.py` → `io_formats/`, `view_state.py` → `state/`.
- Undo command classes and diff replay extracted to `undo/commands.py`
  + `undo/diff.py` (`DiffApplier`).
- Compatibility shims removed in Phase 37; all internal imports use
  canonical package paths. No source file (other than generated
  `mainwindow.py`) exceeds ~580 lines.
- Full suite stayed green at 401 passed throughout every phase.
