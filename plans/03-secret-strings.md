# Plan 03 — Secret strings (passwords / tokens / secrets)

## Goal

A dedicated `JsonType.SECRET` text variant that is **never** auto-classified
as anything else (not `STRING`, not `UNICODE`, not `MULTILINE`, not `BYTES`,
not a color, not a base64 blob). Secrets:

- are **hidden by default** in the tree view (rendered as `••••••••` with a
  fixed glyph count, regardless of length, to avoid leaking length info);
- can be **revealed per-cell** via a context-menu action ("Reveal value")
  with a configurable auto-hide timeout;
- are **detected by field name** (e.g. `password`, `token`, `secret`,
  `api_key`, …); the list of matching name patterns is **configurable** via
  `settings.py`;
- are stored as plain strings on disk (no encryption — out of scope), but
  their **kind** (`SECRET`) is persisted and restored on load even when the
  field name does not match the configured patterns (manual override wins).

## Non-goals

- Encryption at rest. The threat model is *shoulder-surfing* and *accidental
  screenshots / screen sharing*, not adversarial disk access.
- Clipboard scrubbing (could be a follow-up).
- Multi-line secrets (out of scope; secret is single-line; a multi-line
  certificate or PEM blob stays `MULTILINE`/`TEXT` unless manually pinned).

## Design notes

- New `JsonType.SECRET = "secret"` in `tree/types.py`.
- New helper module: `validation/secret_names.py`:

  ```python
  def name_looks_secret(field_name: str, patterns: Iterable[str]) -> bool: ...
  ```

  Patterns are case-insensitive substrings **and** regexes (a pattern
  starting with `re:` is treated as regex, otherwise substring).
- Detection points (in priority order):
  1. **Persisted kind** from the file (if loader saw `SECRET`).
  2. **Manual override** via the type-delegate dropdown (last user wins).
  3. **Name heuristic**: only on *new* values or values currently classified
     into `TEXT_FAMILY`; never demotes a `MULTILINE` blob to `SECRET`.
- `parse_json_type` does **not** know about field names (it sees only
  values). Name-based promotion happens one layer up in the model when a
  cell's name *or* its value changes.
- View masking is implemented in `delegates/value_formatting.py` via a
  per-row "revealed" flag held in the model (transient; not persisted).

## Persisted form

To survive round-trip without encryption-flavored magic, dump a `SECRET`
string as a plain JSON/YAML string but tag the kind in the **schema sidecar**
(if present) or via a per-tab in-memory map. If no sidecar exists, the
loader falls back to the name heuristic — which is acceptable because the
name patterns are exactly what would have classified it on first creation.

(If the project later gains schema sidecars at the field level, this slots
in cleanly. For now we accept the heuristic-based reload.)

## Commits

### Commit 1 — `settings.py`

Add:

```python
SECRET_NAME_PATTERNS: tuple[str, ...] = (
    "password", "passwd", "pwd",
    "secret", "token", "api_key", "apikey",
    "access_key", "private_key",
    "re:auth.*token",
)
SECRET_REVEAL_TIMEOUT_MS = 8_000   # 0 = no auto-hide
SECRET_MASK_GLYPHS = 8             # fixed glyph count when masked
SECRET_MASK_CHAR = "•"
```

**DoD**

- Settings module imports cleanly.
- A tiny unit test (`tests/test_settings_secret.py`) asserts the constants
  exist and have the documented types.

### Commit 2 — `validation/secret_names.py` (new)

Implement `name_looks_secret(name, patterns)`:

- Substring match: case-insensitive.
- Regex match: pattern `"re:<expr>"` → `re.search(expr, name, re.IGNORECASE)`.
- Empty / non-string `name` → `False`.

**DoD**

- `tests/test_secret_names.py`:
  - `name_looks_secret("Password", default_patterns) is True`.
  - `name_looks_secret("user_token_v2", default_patterns) is True`.
  - `name_looks_secret("description", default_patterns) is False`.
  - Custom regex `("re:^x_.*key$",)` matches `"x_super_key"` only.
- Pure stdlib; no imports from app modules.

### Commit 3 — `tree/types.py`

- Add `JsonType.SECRET = "secret"`.
- Extend `TEXT_FAMILY` to **exclude** `SECRET` (intentional: secrets are
  not a free text-axis transition target).
- Add `SECRET_FAMILY = frozenset({JsonType.SECRET})`.
- `parse_json_type` is *not* changed (no name visibility); add a docstring
  note explaining promotion happens in the model.

**DoD**

- Existing tests green.
- `JsonType.SECRET` is exported and usable.

### Commit 4 — Model integration

Files: `tree/item.py` and/or `tree/item_coercion.py` (whichever owns
"on-name-change" / "on-value-change" hooks — verify before editing).

- When a cell's *name* changes or a *new cell* is created in `TEXT_FAMILY`,
  call `name_looks_secret(name, settings.SECRET_NAME_PATTERNS)` and promote
  to `SECRET` if matched and the user has not manually pinned a different
  type.
- A "manual pin" flag (`Qt.UserRole + N`) suppresses future auto-promotion.

**DoD**

- `tests/test_secret_promotion.py`:
  - Renaming a `STRING` cell to `"password"` promotes it to `SECRET`.
  - Renaming back to `"comment"` demotes to `STRING` (only if not manually
    pinned).
  - Manually setting type to `STRING` on a `password` field sets the pin
    and survives a subsequent name re-edit.
- Promotion does **not** modify the stored value.

### Commit 5 — `delegates/value_formatting.py`

- Render `SECRET` cells as `SECRET_MASK_CHAR * SECRET_MASK_GLYPHS`.
- Tooltip is also masked (no length leak).
- A transient per-row "revealed" flag (held in a `WeakKeyDictionary` keyed by
  model index's internal id, or in the model's user-role) toggles the
  rendering.

**DoD**

- A `SECRET` cell with value `"hunter2"` displays `••••••••` (exactly
  `SECRET_MASK_GLYPHS` chars).
- Setting the reveal flag shows the real value; clearing it re-masks.
- Other cells unaffected.

### Commit 6 — `delegates/type_delegate.py`

- Allow `SECRET` in the dropdown for `TEXT_FAMILY` cells (and from `SECRET`
  back to `STRING`/`UNICODE`).
- Selecting `SECRET` sets the manual-pin flag.

**DoD**

- Dropdown shows `secret` for a string cell.
- Picking `secret` then re-renaming the field to `description` keeps it
  `SECRET` (manual pin honored).
- Switching back to `STRING` clears the pin.

### Commit 7 — Context menu: Reveal / Hide

File: most likely `tree/view.py` (verify owns context menu) or a new
`tree_actions/secret_actions.py`.

- Add `"Reveal value"` and `"Hide value"` actions, enabled only on
  `SECRET` cells.
- On reveal: set the transient flag, start a `QTimer` for
  `SECRET_REVEAL_TIMEOUT_MS` (when > 0) that auto-hides.
- Multiple reveals across cells are tracked independently.

**DoD**

- Right-click on a `SECRET` cell shows "Reveal value".
- After clicking, value is shown; after `SECRET_REVEAL_TIMEOUT_MS` it
  auto-masks again.
- Setting `SECRET_REVEAL_TIMEOUT_MS = 0` disables auto-hide; only manual
  "Hide value" re-masks.
- Tab/window switch does *not* leak: optional behavior to auto-hide on
  focus-out is implemented and covered in commit body (toggleable via a
  setting `SECRET_HIDE_ON_FOCUS_OUT = True`).

### Commit 8 — Editor behavior

File: whichever editor handles single-line text (likely
`delegates/value.py` or a sibling).

- When editing a `SECRET` cell, the editor uses `QLineEdit.Password` echo
  mode by default with a "show" toggle (eye icon) inside the field.
- Copy/paste works normally (clipboard scrubbing is out of scope but a
  TODO is added to `ai-memory/todo-n-fixme.md`).

**DoD**

- Double-click on a `SECRET` cell opens an editor that masks input by
  default.
- Toggle button reveals plaintext for the duration of the edit session.
- Committing the edit re-masks in the view.

### Commit 9 — `io_formats/dump.py` + `io_formats/load.py`

- Dump writes the secret as a plain string.
- Load relies on the model's name-heuristic promotion (Commit 4) to
  re-classify on import. Document this in a module docstring.

**DoD**

- `tests/test_io_secret.py`: a tree with a field named `password = "hunter2"`
  saved and reloaded comes back as `SECRET`.
- A field named `notes = "hunter2"` saved as `SECRET` (manual pin), then
  reloaded with the *same* name, **falls back to `STRING`** (documented
  limitation: no per-field schema sidecar yet). Test asserts this and
  references the future-work TODO.

### Commit 10 — Docs

Update `README.md`, `ai-memory/repo-map.md`, and append a TODO entry in
`ai-memory/todo-n-fixme.md`:

- Document `SECRET` kind and the name-pattern config.
- Document the persistence limitation (manual pins not preserved without a
  schema sidecar).
- Add TODO: "Persist `SECRET` manual pin per field — needs schema sidecar
  or out-of-band metadata file."
- Add TODO: "Clipboard scrubbing for revealed `SECRET` values."

**DoD**

- All three docs updated.
- No code changes in this commit.
