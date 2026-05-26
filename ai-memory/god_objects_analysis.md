# Analysis of God Objects (God Files) in Editable Tree Model Example

This document presents a comprehensive, high-level analysis of the three files and classes that have evolved into "God Objects" or "God Files":
1. **`documents/tab.py`** -> God Object `JsonTab`
2. **`app/main_window.py`** -> God Object `MainWindow`
3. **`delegates/value.py`** -> God Object `ValueDelegate`

We trace their growth, enumerate their responsibilities, and analyze the modules and dependencies involved in each responsibility. This audit serves as the mandatory pre-refactor evaluation.

---

## 1. `documents/tab.py` ── God Object: `JsonTab`
* **Current Size:** ~1,397 LOC (up from ~580 LOC)
* **Design Classification:** Multi-concern Controller, State-Baggage, and UI Hub.
* **Why it became a God Object:** `JsonTab` is no longer just a container for a single document tab. It serves as:
  1. The central UI widget representing the tab page.
  2. The manager of the `QUndoStack` state and transaction merges for all mutations.
  3. The manager for document-wide verification, JSON/YAML schemas, and issue indexes.
  4. The event filter router of the nested tree view.
  5. The primary coordinator for selection-driven action mutations (copy, paste, move, and edit).

### Enumeration of Responsibilities & Involved Modules

#### A. Document IO Lifecycle, File & Format Monitoring
* **Description:** Tracks file path settings (`file_path`), format options (`save_format`), dirtiness bounds, and updates tab presentation tooltips. Integrates loading, saving, and snapshot generation.
* **Key Symbols:** `JsonTab.__init__`, `self.file_path`, `self.save_format`, `self._dirty`.
* **Involved Modules:**
  * `documents.tab_io` (`save` as `tab_save`, `save_as` as `tab_save_as`, `snapshot` as `tab_snapshot`) — handles saving file payloads to disk.
  * `io_formats.detect` — provides format definitions (such as `SAVE_FORMAT_YAML_MULTI`).
  * `state.view_state` — persists tree state variables such as expansion patterns.

#### B. Component Layout, Setup, and Delegation Plugs
* **Description:** Initializes the UI, configures splitter layouts, links model and view delegates, configures column-resizing parameters, and handles global-to-local font zooms.
* **Key Symbols:** `init_layout`, `init_model`, `init_delegates_and_connections`, `self.font_zoom`.
* **Involved Modules:**
  * `documents.tab_setup` (`init_layout`, `init_model`, `init_delegates_and_connections`, `init_shortcuts`) — contains setup logic which is deeply coupled back into the layout of `JsonTab`.
  * `tree.item.JsonTreeItem` / `tree.model.JsonTreeModel` — sets up core representation.
  * `themes.icon_provider` — provides customized type-aware icons.

#### C. Undo/Redo Transaction Administration & Change Merging
* **Description:** Owns the `QUndoStack`. Tracks index changes, intercepts field edits, merges consecutive keystrokes (within a `_MERGE_WINDOW_SECONDS` window), and runs structured edits via command objects or diff replays.
* **Key Symbols:** `self.undo_stack`, `commit_set_data`, `_on_undo_index_changed`, `_on_clean_changed`.
* **Involved Modules:**
  * `PySide6.QtGui.QUndoStack` — handles Qt history management.
  * `undo.commands` — contains commands: `_ChangeTypeCmd`, `_EditValueCmd`, `_InsertRowsCmd`, `_MoveRowsCmd`, `_RemoveRowsCmd`, `_RenameCmd`, `_SortKeysCmd`, `_SwitchFieldCaseCmd`.
  * `undo.diff.DiffApplier` — replays diff structural frames.

#### D. Active Schema Binding & Full Revalidation Coordinates
* **Description:** Discovers, attaches, reloads, and drops schemas. Sanitizes data for schema processing, coordinates live background threads/timers to re-run schema engines, and constructs the tab-specific `IssueIndex`.
* **Key Symbols:** `revalidate`, `_init_validation_state`, `set_schema`, `clear_schema`, `_on_registry_schema_reloaded`, `self._mutation_debounce_timer`.
* **Involved Modules:**
  * `validation.schema_registry` (`schema_registry`) / `validation.schema_source` — keeps, registers, and tracks active schemas.
  * `validation.validator` (`validate_document`) — runs the local JSON schema validator.
  * `validation.yaml_validate` (`validate_yaml_documents`) — multi-document validation engine loop.
  * `validation._sanitize` (`to_jsonschema_input`) — coerces custom model types down to standard primitives.
  * `validation.index.IssueIndex` — stores, maps, and yields validation issues.

#### E. Active Selection Operations, Moving, and Clipboard Plumbing
* **Description:** Implements keyboard action endpoints, handles row movements (combining nested and grand-parent boundary bubbles), and bridges menu actions down into structural modifiers.
* **Key Symbols:** `push_move_rows_anchor`, context-menu actions, copy/paste keyboard shortcuts.
* **Involved Modules:**
  * `tree_actions.clipboard` — copy as raw or complex strings (JSON/YAML).
  * `tree_actions.paste` — parses insertion streams.
  * `tree_actions.selection` — scans lists of selection ranges.
  * `tree_actions.structure` — structural manipulations like insertions, cuts, deletions, duplicates, and recursive expanding/collapsing.

#### F. Text Filter & Search Dispatch
* **Description:** Manages search edit interactions, triggers debounced filters, and pushes search regex constraints into the proxy model.
* **Key Symbols:** `init_search_filter`, `search_edit`, debouncer connections.
* **Involved Modules:**
  * `tree_filter_proxy.TreeFilterProxy` — implements recursive key/value search on the model.
  * `PySide6.QtCore.QTimer` — debounces user input to avoid performance lag.

#### G. Event Routing & View Keyboard Filtering
* **Description:** Acts as an event filter overlaying the tree view. Directly intercepts keys (such as arrow navigation and spacebar expansion) to override default Qt view behavior.
* **Key Symbols:** `eventFilter`, `_handle_arrow_navigation`, `_toggle_current_row_expansion_with_space`.
* **Involved Modules:**
  * `PySide6.QtCore.QEvent` / `PySide6.QtGui.QKeyEvent`.

---

## 2. `app/main_window.py` ── God Object: `MainWindow`
* **Current Size:** ~1,116 LOC (up from ~418 LOC)
* **Design Classification:** Central Monolithic Shell and Wiring Hub.
* **Why it became a God Object:** This class serves as the root window environment. It is the core hub that coordinates all application sub-systems. Instead of delegating workflows, it directly hosts:
  1. The window wrapper, OS file drops, and layout geometry cache.
  2. The multi-tab container interface and the closed-tabs LIFO history stack.
  3. Action triggering, connection plumbing, and menu-specific enablement checks.
  4. The schema registry, validation dock actions, and rule jumps.
  5. The global application typography and dynamic color scheme controller.
  6. Configuration limits settings for large data types and password prefix managers.

### Enumeration of Responsibilities & Involved Modules

#### A. OS Shell, Window geometry, and File-Drop System
* **Description:** Restores window bounds on launch, processes window exit hooks, and acts as the file drops dispatcher (allowing users to open supported configuration files via drag-and-drop).
* **Key Symbols:** `__init__`, `closeEvent`, `dragEnterEvent`, `dropEvent`, `_restore_window_geometry`.
* **Involved Modules:**
  * `PySide6.QtWidgets.QMainWindow`.
  * `PySide6.QtCore.QSettings` — stores geometric layout bounds.

#### B. Tab Management, Document Assembly, and Reopen Caches
* **Description:** Creates new instances of `JsonTab`, transitions current tab variables, processes close dialog confirmations, and tracks previously closed pages within a LIFO buffer.
* **Key Symbols:** `_add_tab`, `_on_tab_changed`, `close_tab`, `_reopen_tab`, `_closed_tabs_stack`.
* **Involved Modules:**
  * `documents.tab.JsonTab` — instantiated and controlled.
  * `app.close_confirm` (`confirm_close`) — prompts the user with save/discard choices.
  * `io_formats.load` (`load_file_with_format`) — performs the lower-level parsing.

#### C. Menu Routing & Action State Managers
* **Description:** Binds menus, registers menu actions, coordinates UNDO history widgets, maps system shortcuts, and enables/disables commands dynamically depending on what row is selected or whether a document is dirty.
* **Key Symbols:** Menu setup, `save_action`, clipboard inputs, context-menu handlers.
* **Involved Modules:**
  * `app.main_window_actions` (`setup_connections`, `update_actions`) — couples and coordinates menu structures with active tab state metrics.
  * `app.history` (`bind_undo_signals`, `setup_history_menu`) — interacts with undo histories and registers the `QUndoView` modal.

#### D. Scheme Dock Interaction & Issue-Rule Navigation
* **Description:** Houses the validation panel dock, registers "request attach", "reload schema", "clear schema", and "open file" signals, and manages navigation jumps from error markers to schema lines.
* **Key Symbols:** `_setup_validation_dock`, `_on_attach_schema_requested`, `_on_go_to_schema_rule_requested`.
* **Involved Modules:**
  * `app.validation_dock.ValidationDock` — provides the side dock widget.
  * `validation.schema_registry` / `state.validation_settings` — tracks active schemas and paths.
  * `app.schema_tab_pool.SchemaTabPool` — maintains references to active tabs editing schema definitions.

#### E. Theme Switching & Global Presentation Controllers
* **Description:** Collects light/dark scheme choices, tracks user theme hot-reloads, and applies palettes across the main UI thread.
* **Key Symbols:** Theme selection change connections, system-theme sync options.
* **Involved Modules:**
  * `app.theme_controller.ThemeController` — manages system-level theme events and hooks.
  * `themes` — provides standard spec colors.

#### F. Global Typography Management
* **Description:** Launches Font dialogues and operates global-to-local font sizing and monospaced family locks.
* **Key Symbols:** `_normalize_font_for_dialog`, `_on_change_font_requested`.
* **Involved Modules:**
  * `app.font_controller.FontController` — monitors monospace font configuration states and handles repainting.

#### G. Application Configurations, limits, and Secrets Setup
* **Description:** Opens dialogs to modify size warning limits (strings, multiline, binary) and manages word prefixes that classify fields as confidential.
* **Key Symbols:** Limits setters/getters, `SecretPrefixesDialog` callback.
* **Involved Modules:**
  * `state.edit_limits` — gets/sets various byte/character thresholds.
  * `state.secret_settings` — gets/sets prefix keywords.
  * `dialogs.secret_prefixes_dlg` — manages the secret prefix dialog.

---

## 3. `delegates/value.py` ── God Object: `ValueDelegate`
* **Current Size:** ~641 LOC (up from ~300 LOC)
* **Design Classification:** Rendering and Editor Factory Monolith.
* **Why it became a God Object:** Instead of focusing simply on formatting or painting cells, `ValueDelegate` coordinates:
  1. Font styling, color highlights, and type styling based on the active theme.
  2. Generating custom inline widgets for advanced types (such as custom MPQ/bigint spinboxes, date editors, and secure token panels).
  3. Spawning external floating subdialogs (plain text editors and hex editors) for fields exceeding sizing limits.
  4. Bypassing traditional PyQt pipelines to lookup raw C++ data items directly, avoiding integer bit-overflows.
  5. Validation badge annotations/painting.
  6. Transaction interception—passing values back to custom controllers (`JsonTab`) to coordinate undo state creation rather than letting the model store values directly.

### Enumeration of Responsibilities & Involved Modules

#### A. Advanced Cell Styling, Rendering, and Theme Wrapping
* **Description:** Skinning table columns, aligning backgrounds with dark/light themes, and checking container expansion to show preview strings (`[N items]`) on collapsed nodes.
* **Key Symbols:** `paint`, `initStyleOption`, `_apply_monospace_font`.
* **Involved Modules:**
  * `delegates.value_formatting` (`_apply_type_style`, `format_with_type`) — formats container previews.
  * `themes.spec.ThemeSpec` — describes colors for other elements.

#### B. Dynamic Badge & Swatch Construction
* **Description:** Draws color-picker markers for Hex RGB/RGBA fields and paints validation error badges over erroneous fields.
* **Key Symbols:** `_color_swatch_icon`, `draw_severity_badge` hook inside `paint()`.
* **Involved Modules:**
  * `delegates.color_codec` (`parse_color`) — validates string hex fields.
  * `delegates.validation_badge` (`draw_severity_badge`) — draws warning icons.
  * `tree.model_roles` (`VALIDATION_SEVERITY_ROLE`).

#### C. Type-Specific Inline Editor Generation
* **Description:** Yields appropriate widgets inside `createEditor()` based on `JsonType`. Handles special inputs for Mpq, BigInt, DateTimes, or custom password fields with toggle buttons.
* **Key Symbols:** `createEditor`, `setEditorData`, `setModelData`, `_SecretLineEdit`.
* **Involved Modules:**
  * `qbigint_spinbox.QBigIntSpinBox` — big integer spinbox.
  * `qmpq_spinbox.QMpqSpinBox` — rational numeric inputs.
  * `datetime_editor.better_dt_editor.BetterDateTimeEditor` — complex datetime editor.
  * `delegates.number_affix_delegate.AffixCompositeEditor` — currency and metrics inputs.

#### D. Popup Editor Dialog Dispatches & Threshold Safeguards
* **Description:** Checks size limits for large fields and launches modal popup dialogs for Hex arrays or multi-line text blocks.
* **Key Symbols:** `_confirm_large_text_edit`, `_confirm_large_binary_edit`, spawning popup dialogue views.
* **Involved Modules:**
  * `dialogs.qmultiline_dlg.QMultilineDialog` — multi-line text popup.
  * `dialogs.qhexedit_dlg.QHexDialog` — binary data editor popup.
  * `state.edit_limits` — limits configurations.
  * `delegates.bytes_codec` (`decode_bytes`, `encode_bytes`) — compresses/decompresses byte structures (Zlib/GZip).

#### E. Direct C++ Object Inspection
* **Description:** Directly extracts variables from `JsonTreeItem` inside `initStyleOption()` to bypass standard PySide/Shiboken types, avoiding bit-overflow failures.
* **Key Symbols:** `isinstance(item, JsonTreeItem)`, `item.data()`, `item.json_type`.
* **Involved Modules:**
  * `tree.item.JsonTreeItem` / `tree.model_roles.JSON_TYPE_ROLE`.

#### F. Transaction Redirection (Tab Commits)
* **Description:** Intercepts editor commits (using `_find_tab` and `_commit`) to run edits through `JsonTab.commit_set_data` or `JsonTab._on_type_changed`, ensuring undo command histories are merged properly rather than committing straight to the model.
* **Key Symbols:** `_find_tab`, `_commit`, `_notify_status`.
* **Involved Modules:**
  * `documents.tab.JsonTab` — targeted tab container.
  * `PySide6.QtCore.QPersistentModelIndex`.

---

## 4. Architectural Interdependencies & Coupling
The main issue driving these god objects is their tight, bi-directional coupling:

```
                  ┌──────────────────────┐
                  │     MainWindow       │
                  └──────────┬───────────┘
                             │  Tab Lifecycles & Signal Wiring
                             ▼
                  ┌──────────────────────┐
                  │      JsonTab         │◀──────────────────┐
                  └──────────┬───────────┘                   │
                             │                               │ Find Tab & Custom
                             │  Creates / Configures         │ Commit Transaction
                             ▼                               │
                  ┌──────────────────────┐                   │
                  │    ValueDelegate     │───────────────────┘
                  └──────────────────────┘
```

1. **`MainWindow` ── `JsonTab`**: `MainWindow` manages and owns all `JsonTab` instances. However, it also couples into validation details, search triggers, dirty status, file formats, and file revalidation actions directly.
2. **`JsonTab` ── `ValueDelegate`**: `JsonTab` constructs views and configures `ValueDelegate` models.
3. **`ValueDelegate` ── `JsonTab`**: In order to execute safe transaction edits and group undo events (or push warnings into status feeds), `ValueDelegate` crawls up the widget parent-hierarchy looking for `JsonTab` via `_find_tab()` and directly executes `tab.commit_set_data()`. This makes `ValueDelegate` unusable in headless tests or standalone lists where a `JsonTab` is not present in its parent widget tree.

---

## 5. Potential Refactoring Opportunities

To break down these files, several decoupling vectors should be planned:

### A. Extract a `TabHistoryController` / `TabIOController` from `JsonTab`
* **Goal:** Separate document state and history from the view components.
* **Refactor:** Create pure Python classes that own `QUndoStack` and handle file modification triggers, keeping `JsonTab` focused solely on visual layouts and UI connections.

### B. Decouple `ValueDelegate` from `JsonTab` via Signals or Interface Abstractions
* **Goal:** Make `ValueDelegate` lightweight and decoupled from the parent widget hierarchy.
* **Refactor:** Replace `_find_tab` recursive searches and direct parent invocations with standard Qt Signals (e.g., `commitRequested(index, value)`). The model or a controller should bind these signals to transaction routers, making `ValueDelegate` independent of `JsonTab`.

### C. Extract a `TabCollectionManager` / `AppActionManager` from `MainWindow`
* **Goal:** Shrink the monolithic size of `MainWindow`.
* **Refactor:** Move closed-tab histories, tab restoration protocols, recent files menus, and settings/warning limits configurations to independent controller classes. `MainWindow` should act purely as the visual container.
