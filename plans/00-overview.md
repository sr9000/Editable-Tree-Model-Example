# Schema Registry — integration plan

_Goal: stop every `JsonTab` from owning its own private copy of a
loaded JSON Schema. Introduce a shared registry that loads each
schema **once**, tracks whether the source is a **local file** (mutable,
watched for changes) or a **remote URL** (read-only), and remembers a
**recently-used schemas** list for fast re-attach across tabs._

## Why

Today (branch `master`, audit dated 2026-05-16):

- `validation/schema_source.py::load_schema` re-reads the file/URL
  every time it is called.
- `documents/tab.py::set_schema` does
  `self._schema = dict(loaded) if loaded is not None else None` —
  each tab keeps its own in-memory copy of the same schema.
- `app/main_window.py` re-implements load logic four times
  (`_on_attach_schema_requested`, `_on_reload_schema_requested`,
  `_on_open_schema_file_requested`, `_on_go_to_schema_rule_requested`)
  and tags URL-backed tabs with a free-floating `_schema_url_source`
  attribute (only place in the tree where the URL identity is kept).
- There is no notification when a user edits a local schema file in
  another tab — validation silently uses the stale dict.
- The only recents list is `app/recent_files.py` for documents;
  schemas have no equivalent quick-pick.

## Feature checklist

1. **Dedup by source identity** — a schema referenced as the same
   resolved path / canonicalised URL is loaded exactly once and
   shared across all bound tabs.
2. **Source kind tracked explicitly** — `kind="file"` vs `kind="url"`;
   the dock toolbar reflects "URL schema — read-only" in
   `_on_schema_changed`.
3. **Hot reload of local schema files** via `QFileSystemWatcher`;
   bound tabs revalidate automatically (independent of the existing
   auto-rescan checkbox, which only debounces *document* mutations).
4. **Recent schemas** — a global list (cap 12) of `SchemaSource`s
   pushed every time a schema is attached, surfaced in the
   attach dialog and in a "Recent ▸" submenu under the dock's
   `Schema ▸` button.

## Constraints

- **Each step = one commit**, ≤ 10 files, ≤ 500 LOC of *new* code
  (test files don't count toward LOC, still count toward file cap).
- No regression in the existing test suite (805+ tests, see
  `ai-memory/pros-n-cons.md` for the exact count).
- `QSettings(APPLICATION_ID, "validation")` is the only persistence
  channel for the new `recent_schemas` key; consistent with
  `state/validation_settings.py`.
- All UI strings go through `tr()`.
- `SchemaRef` (the existing signal payload) stays — Step 2 adds a
  parallel `SchemaSource` type rather than breaking listeners.

## Step map

| # | File                                  | Theme                                                  |
| - | ------------------------------------- | ------------------------------------------------------ |
| 1 | `01-schema-source-model.md`           | `SchemaSource` + `SchemaRegistry` core (pure logic)    |
| 2 | `02-tab-integration.md`               | `JsonTab` acquires/releases via registry               |
| 3 | `03-mainwindow-handlers-and-dialog.md`| Collapse the four MainWindow handlers + extract dialog |
| 4 | `04-file-watcher.md`                  | `QFileSystemWatcher` hot reload + dock read-only hint  |
| 5 | `05-recent-schemas-persistence.md`    | `state/recent_schemas.py` + registry-side push         |
| 6 | `06-recent-schemas-ui.md`             | Attach-dialog combo + dock "Recent ▸" submenu          |
| 7 | `07-docs-and-memory.md`               | README + `ai-memory/*` updates                         |

Each step file lists: scope, files touched, public API delta,
tests, commit message template, and explicit "out-of-scope" notes.

## Public surface, after Step 6

```python
from validation.schema_registry import (
    SchemaSource,            # frozen: kind ("file"|"url"), key, display
    SchemaEntry,             # loaded inline + mtime/etag + bound tabs
    SchemaRegistry,          # acquire / release / reload / lookup
    schema_registry,         # process-wide singleton
)
from state.recent_schemas import (
    push_recent_schema,
    recent_schemas,
    clear_recent_schemas,
)

# documents/tab.py gains:
class JsonTab(QWidget):
    @property
    def schema_source(self) -> SchemaSource | None: ...
    def set_schema_from_source(self, source: SchemaSource) -> None: ...
```

`ValidationDock` gains `attachRecentSchemaRequested = Signal(object)`.

## Non-goals (do not creep)

- HTTP `ETag` / `If-Modified-Since` for URL schemas — `reload()` always re-fetches.
- Content-hash dedup for **inline** `$schema` (origin `"inline"` /
  `"sibling"` with the JSON literal embedded in the document) — these
  bypass the registry. Revisit only if duplicate inline schemas
  appear in practice.
- Schema-authoring UI / draft-version picker (deferred from the
  jsonschema plan's non-goals — still deferred).
- Per-issue quick-fix actions.
