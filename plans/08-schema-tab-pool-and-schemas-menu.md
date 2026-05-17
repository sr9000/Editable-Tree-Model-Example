# Step 8 — Schema tab pool + top-level `Schemas` menu

_Commit-sized: 6 source files + 2 test files; ~300 LOC._

## Scope

Add a **single pool of opened schema tabs** so schema navigation is
identity-based and deterministic:

- if a schema tab for the same `SchemaSource` is already open, focus it;
- otherwise open exactly one new viewer tab and register it in the pool.

Also add a top-level **`Schemas`** menu to the main menubar. It lists
recently used schemas, clearly marks each one as **Local** or **URL**,
and provides actions to open the schema tab or **copy the full path**
(`source.key`) to the clipboard.

Important behavioural rule for this step:

- **URL-based schema tabs are read-only** — they may be viewed and
  navigated, but never edited or saved.

This step is a post-Step-7 follow-up. It does not change the registry's
source identity model introduced in Steps 1–6; it builds UI and tab
ownership on top of it.

## Files touched (8)

```
plans/08-schema-tab-pool-and-schemas-menu.md   # new
app/schema_tab_pool.py                         # new: single pool of open schema tabs
app/main_window.py                             # go-to-schema-rule uses pool; Schemas menu wiring
app/main_window_actions.py                     # disable edit/save actions for read-only schema viewers
documents/tab.py                               # +read-only tab mode API
tree/model.py                                  # model-level read-only gate for URL schema tabs
tests/test_validation_navigation.py            # assert schema tabs are reused, not duplicated
tests/test_schemas_menu.py                     # new
```

## Behaviour contract

### 1. Single pool of open schema tabs

New helper object:

```python
# app/schema_tab_pool.py
class SchemaTabPool(QObject):
    def find(self, source: SchemaSource) -> JsonTab | None: ...
    def register(self, tab: JsonTab, source: SchemaSource, *, read_only: bool) -> None: ...
    def unregister(self, tab: JsonTab) -> None: ...
    def open_or_focus(self, window, source: SchemaSource) -> JsonTab | None: ...
```

Rules:

- pool key is the full `SchemaSource` (`kind`, `key`, `display`);
- one live tab per source at a time;
- pool owns the mapping, not ad-hoc attributes in `MainWindow`;
- `destroyed` / close-time cleanup removes stale registrations;
- file-backed schema tabs opened through normal file-open flows are
  registered when their resolved `file_path` matches a schema source;
- URL-backed schema viewer tabs are always created through the pool.

### 2. `Go to schema rule` is pool-backed

`app/main_window.py::_on_go_to_schema_rule_requested` becomes:

- resolve current tab's `schema_source`;
- ask the pool for an already-open tab;
- if found, focus and navigate;
- if missing, open once through the pool, then navigate.

This removes the current best-effort tab scan and the current failure
mode where a new schema tab is opened even though an equivalent one is
already open.

### 3. Top-level `Schemas` menu

A new top-level menu is added to the main menubar:

```text
File  Actions  Schemas  View
```

Menu contents:

```text
Schemas
├─ Attach schema…
├─ Recent
│  ├─ Local — schema.json
│  ├─ URL — example.com/person.schema.json
│  └─ ...
├─ Open current schema
└─ Copy full path
```

Notes:

- menu labels must explicitly mark source kind as **`Local`** or **`URL`**;
- recent entries remain MRU-ordered and are sourced from
  `state.recent_schemas.recent_schemas()`;
- selecting a recent schema opens/focuses the schema tab via the pool;
- `Copy full path` copies `source.key` to the clipboard;
  - for local schemas this is the resolved absolute filesystem path;
  - for URL schemas this is the canonical URL string.

### 4. URL schema tabs are non-editable

When a schema viewer tab represents `SchemaSource(kind="url", ...)`:

- the tab opens in **read-only** mode;
- all edit operations are blocked at the model level;
- destructive tree actions are disabled;
- `Save` / `Save As` are disabled while that tab is current;
- the dock/menu affordances continue to describe the tab as URL-backed
  and read-only;
- **users can save the schema to a local file** using a new `Save As` option;
  - after saving, a dialog prompts the user:
    - **Yes**: Replace the URL schema tab with a local version (reassign the tab to the saved local file).
    - **No**: Keep the tab as URL-based but save the file locally.

This is stricter than today's tooltip-only hint.

Local file schema tabs remain editable when opened as real files.

## Implementation notes

### `documents/tab.py`

Add a small tab-level API:

```python
class JsonTab(QWidget):
    @property
    def is_read_only(self) -> bool: ...
    def set_read_only(self, enabled: bool) -> None: ...
```

Responsibilities:

- persist a `_read_only` flag;
- delegate to the underlying model/view so in-place editing cannot start;
- expose the flag to `MainWindow.update_actions()`.

Do **not** overload `schema_source.kind == "url"` as the sole runtime
check; the pool should set read-only explicitly when it opens a URL
schema viewer tab.

### `tree/model.py`

Add a model-level gate, e.g. `set_read_only()` / `is_read_only()`.

When enabled:

- `flags()` must not include `Qt.ItemFlag.ItemIsEditable`;
- row drag/drop should be disabled for safety;
- `setData()`, `change_type()`, `insertRows()`, `removeRows()`,
  `move_row()`, and `sort_keys()` should return `False` early.

This keeps URL schema viewer tabs safe even if an action or test bypasses
view-layer editor affordances.

### `app/schema_tab_pool.py`

Recommended structure:

- primary mapping: `dict[SchemaSource, JsonTab]`;
- reverse mapping: `dict[JsonTab, SchemaSource]` for unregistering;
- on `register(...)`, connect `tab.destroyed` to automatic cleanup;
- on `open_or_focus(window, source)`:
  - `find(source)` first;
  - for `file` sources, prefer an already-open file tab whose
    `file_path == source.key` before opening a new one;
  - for `url` sources, use `schema_registry.lookup(source)` first, then
    fall back to `schema_registry.acquire(source, sentinel)` if needed;
  - create a viewer tab through `window._add_tab(...)` only when no tab exists;
  - set `tab._schema_source` / `tab.schema_source` consistently through the
    existing tab API, not via a one-off hidden attribute when avoidable;
  - set read-only `True` for URL sources, `False` for local files.

### `app/main_window.py`

- instantiate `self._schema_tab_pool` in `__init__`;
- rebuild the new `Schemas` menu on `aboutToShow`;
- add handlers:
  - `_open_schema_source(source: SchemaSource) -> None`
  - `_copy_schema_source_key(source: SchemaSource) -> None`
  - `_rebuild_schemas_menu() -> None`
- route `_on_go_to_schema_rule_requested()` through the pool.

`_copy_schema_source_key()` should use `QApplication.clipboard().setText(...)`
and show a short status message.

### `app/main_window_actions.py`

Update `update_actions(window)` so current-tab edit/save actions respect
`tab.is_read_only`.

Minimum expectation:

- `fileSaveAction` disabled for read-only tabs;
- `fileSaveAsAction` disabled for read-only tabs;
- row insert/remove actions disabled for read-only tabs.

If additional edit actions already exist elsewhere in the window,
include them in the same pass.

## Tests

### `tests/test_validation_navigation.py`

Extend navigation coverage:

- URL-backed schema:
  - first `go to schema rule` call opens a tab;
  - second call reuses the same tab;
  - `tabWidget.count()` stays constant on the second call;
  - current tab is read-only.
- file-backed schema:
  - open the schema file as a tab once;
  - `go to schema rule` focuses that existing tab instead of opening another.

### `tests/test_schemas_menu.py`

New menu-level tests:

- recent entries are listed as:
  - `Local — <display>` for file sources;
  - `URL — <display>` for URL sources;
- clicking a recent entry opens/focuses the schema tab through the pool;
- `Copy full path` copies the resolved path / URL string to the clipboard;
- current URL schema tab disables save/edit actions.

## Out of scope

- Editing restrictions for **attached local** schemas used as validators;
  this step only requires URL **viewer tabs** to be read-only.
- Separate pinned/favourite schemas list.
- Per-schema metadata beyond source kind and key.
- Reworking the existing dock `Schema ▸` button; it may remain as a
  secondary surface, but the new top-level `Schemas` menu becomes the
  canonical global entry point.

## Commit message

```
feat(app): add schema tab pool and top-level Schemas menu

- introduce a single SchemaTabPool so schema tabs are reused by source identity
- Go to schema rule now focuses an existing schema tab before opening a new one
- add a Schemas menubar entry with MRU local/URL-labelled schema entries
- replace reveal/copy ambiguity with a direct "Copy full path" action
- URL-backed schema viewer tabs are now explicitly read-only
```
