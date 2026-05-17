# Step 4 — `QFileSystemWatcher` hot reload for local schemas

_Commit-sized: 3 source files + 1 test file; ~200 LOC._

## Scope

Local schema files become live. When the user edits a `.schema.json`
on disk (in this editor, in another editor, or via VCS), every bound
tab revalidates without manual `Schema ▸ Reload`. URL-backed schemas
are explicitly **not** watched (no polling) and remain read-only.

## Files touched (4)

```
validation/schema_registry.py   # +QFileSystemWatcher membership, _on_file_changed
documents/tab.py                # +slot _on_registry_schema_reloaded → revalidate()
app/validation_dock.py          # +read-only tooltip on _schema_btn for kind=="url"
tests/test_schema_registry_watch.py   # new
```

## Implementation notes

- Registry creates a single `QFileSystemWatcher` on first
  `acquire(kind="file")` and attaches files lazily. `removePath` is
  called when the entry's ref-count reaches zero.
- `fileChanged` slot:
  - re-`stat` the path; if `mtime_ns` matches the cached value, no-op
    (some editors emit two signals);
  - on real change, call `load_schema(...)`, replace `entry.inline`,
    update `mtime_ns`, emit `schemaReloaded(source)`;
  - on read failure (file moved / unreadable), leave `entry.inline`
    intact, log via `logging.getLogger(__name__).warning`, no signal.
- `JsonTab._on_registry_schema_reloaded(source)` checks
  `source == self._schema_source` and, if so, calls `revalidate()`
  (the inline dict it already holds is the same object, mutated
  in-place by the registry — no `set_schema` round-trip needed).
- `ValidationDock._on_schema_changed` adds:
  ```python
  if ref.url is not None:
      self._schema_btn.setToolTip(self.tr("URL schema — read-only"))
  else:
      self._schema_btn.setToolTip("")
  ```

## Tests

`tests/test_schema_registry_watch.py`:
- create a tab with a file-backed schema;
- modify the file on disk; emit `fileChanged` manually
  (`watcher.fileChanged.emit(path)` — avoids waiting for the FS);
- assert `schemaReloaded` fires once, `entry.inline` contains the
  new content, `tab.issue_index` reflects re-validation.
- URL source: assert no watcher entries created.

## Out of scope

- Polling fallback for filesystems without inotify
  (`QFileSystemWatcher` already handles this; documented limitation).
- URL ETag polling.

## Commit message

```
feat(validation): hot reload local schemas via QFileSystemWatcher

- SchemaRegistry owns one QFileSystemWatcher; adds/removes paths
  in lockstep with file-kind entries
- mtime_ns guard collapses duplicate fileChanged bursts
- bound JsonTabs revalidate on schemaReloaded; URL schemas stay
  explicitly unwatched and surface a read-only tooltip in the dock
```
