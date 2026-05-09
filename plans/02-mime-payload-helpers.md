# Step 2 — Reusable MIME (de)serializer for multi-selection

## Why
`copy_selection` builds the `application/x-json-tree` payload inline.
Drag-and-drop (step 6) and `JsonTreeModel.mimeData` (step 6) need the
exact same bytes, and `paste_from_clipboard` already parses entries
through a private `_clipboard_entries`. We extract one canonical
encoder + decoder so the wire format is owned in one place.

## Scope (single commit)

### Files to touch
1. `tree_actions/clipboard.py`
   - Extract `build_tree_mime(model, source_rows) -> QMimeData`
     (returns `None` when no rows). Internally uses
     `_build_copy_entries` + `_entries_text_payload`. Sets the
     `MIME_JSON_TREE` blob and the human-readable `text/plain`.
   - Extract `entries_from_mime(mime: QMimeData) -> list[dict] | None`
     by splitting `_clipboard_entries` into:
       - `entries_from_mime(mime)` — pure (no clipboard access)
       - `_clipboard_entries()` — `entries_from_mime(QApplication.clipboard().mimeData())`
   - `copy_selection*` rewritten as 4-line orchestrators that call
     `build_tree_mime` and push to the clipboard.
2. `tree_actions/paste.py`
   - `paste_from_clipboard` continues to call `_clipboard_entries`; no
     behaviour change. Drag-drop drop handler (step 6) will call
     `entries_from_mime(event_mime)` directly.
3. `tree_actions/__init__.py` (or new top-level `tree_actions/dnd_mime.py`
   if cleaner) — re-export `MIME_JSON_TREE`, `build_tree_mime`,
   `entries_from_mime`.
4. `tests/test_mime_payload.py` (new).
5. `ai-memory/repo-map.md` — extend §11 to mention the new helpers and
   the canonical wire format.

### Wire-format contract (locked here)
- `application/x-json-tree`: UTF-8 JSON object
  `{"entries": [{"name": str|null, "value": <json>}...]}`
- `text/plain` fallback:
  - Single entry → `simplejson.dumps(value, indent=2)`
  - All entries share an OBJECT parent and have unique str names →
    dict literal
  - Otherwise → array literal
- The encoder MUST sort entries by `_index_path` so order is stable
  across drag and clipboard.

## Definition of Done
- [ ] `pytest tests/test_mime_payload.py -q` passes:
    1. Round-trip: `entries_from_mime(build_tree_mime(model, rows))`
       returns a list with the same `name`/`value` pairs in source
       order.
    2. Disjoint cross-parent selection encodes to a list payload.
    3. Same-OBJECT-parent named selection encodes to a dict payload in
       the `text/plain` fallback (binary payload still uses the
       `entries` list).
    4. Decoder accepts a plain-text JSON object pasted from another
       app (no `MIME_JSON_TREE` blob present) and produces named
       entries.
    5. Decoder rejects malformed JSON without raising
       (`entries_from_mime` returns `None`).
- [ ] All existing clipboard tests
      (`tests/test_tree_actions_clipboard.py`) still pass unchanged.
- [ ] `grep "MIME_JSON_TREE" -nR --include='*.py'` shows the constant
      is defined once.

## Manual smoke
```
QT_QPA_PLATFORM=offscreen pytest -q tests/test_mime_payload.py tests/test_tree_actions_clipboard.py
```
