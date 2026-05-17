# Step 7 — Docs + ai-memory updates

_Commit-sized: ≤6 markdown files; no LOC budget._

## Scope

Land documentation in lockstep with code so the next audit doesn't
have to re-derive the registry's behaviour from grep.

## Files touched (≤6)

```
README.md                         # +"Schema registry" subsection under Validation
ai-memory/repo-map.md             # +§ for validation/schema_registry, state/recent_schemas,
                                  #  dialogs/attach_schema_dlg
ai-memory/pros-n-cons.md          # add the dedup + hot-reload + recents pros
ai-memory/todo-n-fixme.md         # close the matching todo lines; open follow-ups
                                  # (URL ETag, content-hash dedup for inline)
plans/00-overview.md              # mark Steps 1–6 ✅ once landed
```

## Memory deltas

- `repo-map.md` §0 quick-orientation table — add row:
  `Schema registry / source identity → validation/schema_registry.py, state/recent_schemas.py, dialogs/attach_schema_dlg.py`.
- `repo-map.md` add subsection 20.x covering:
  - `validation/schema_registry.py` (singleton, `SchemaSource`, `SchemaEntry`);
  - `state/recent_schemas.py` (cap 12, `"file:" / "url:"` serialisation);
  - hot-reload contract (registry → tab → IssueIndex → dock).
- `pros-n-cons.md` — add under "Pros / Validation":
  > **Centralised schema ownership** — one `SchemaEntry` per source
  > shared across all bound tabs, with `QFileSystemWatcher`-driven
  > hot reload for local files and a normalised URL identity for
  > remote schemas. `state.recent_schemas` (cap 12) backs the dock's
  > "Recent ▸" picker.
- `todo-n-fixme.md` — close any open todos that referenced "no
  schema-file watcher" / "per-tab schema duplication" / "no recents
  for schemas". Open two follow-ups:
  - URL schema staleness (no `ETag` / `If-Modified-Since` check on
    reload);
  - inline `$schema` blocks (no content-hash dedup yet).

## Out of scope

- Screenshots in `README.md` — placeholders only.

## Commit message

```
docs(validation): document schema registry + recent schemas

- README: Validation section gains a "Schema registry" subsection
- ai-memory/repo-map: orientation table + dedicated subsection
- ai-memory/pros-n-cons: dedup / hot-reload / recents pros listed
- ai-memory/todo-n-fixme: closed-out + 2 follow-ups opened
```
