# Plan 03 — Secret strings (passwords / tokens / secrets)

> **Revision note (2026-05-22):** plan re-aligned with user interview. See
> **Decisions** below. Several commits from the original draft are deferred
> to a v2 follow-up.

## Goal

A dedicated `JsonType.SECRET` text kind that is **never** auto-classified
as anything else (not `STRING`, `UNICODE`, `MULTILINE`, `BYTES`, color, or
base64). Secrets:

- are **hidden by default** in the tree view (rendered as `••••••••` with a
  **fixed glyph count**, regardless of length, so length does not leak);
- are **detected by field name** (e.g. `password`, `token`, `secret`,
  `api_key`, …) using a **user-editable** pattern list (settings + dialog);
- are **sticky**: once a cell is `SECRET`, renaming the field to something
  innocuous does **not** demote it back. (In v1 there is no manual override,
  so sticky + no-pin is unambiguous.);
- can be **revealed only while editing** (double-click → masked `QLineEdit`
  with an eye-icon toggle); committing the edit re-masks in the view;
- **auto-hide on focus-out / tab-switch**: if the editor is open and the
  window/tab loses focus, the editor closes and the cell re-masks;
- are stored as **plain strings** on disk (no encryption — out of scope).
  On reload, name-heuristic re-classification is the only way `SECRET`-ness
  is restored. This is an accepted limitation (see Non-goals).

## Non-goals (v1)

- Encryption at rest. Threat model = shoulder-surfing, screenshots, screen
  sharing — **not** adversarial disk access.
- Clipboard scrubbing — tracked as TODO.
- Persisting `SECRET` kind for fields whose **name does not** match the
  patterns (would need a schema sidecar). Tracked as TODO.
- A "Reveal value" context-menu action with a global timer (deferred to v2;
  in v1 reveal happens only inside the editor).
- A type-delegate dropdown entry for `SECRET` / manual kind override
  (deferred to v2).
- `MULTILINE` + `SECRET` combinations (e.g. PEM blobs). See **Open item**
  below — flagged because the interview answer was ambiguous.

## Decisions (from interview)

| Topic                 | Decision                                                                                                                  |
|-----------------------|---------------------------------------------------------------------------------------------------------------------------|
| v1 scope              | `JsonType.SECRET`, masked rendering, name-based auto-detect, password-echo editor with eye toggle, auto-hide on focus-out |
| Detection model       | Name heuristic + **sticky** (rename never demotes)                                                                        |
| Manual pin semantics  | No pin concept (no manual override surface in v1)                                                                         |
| Masking               | Fixed 8 glyphs, no length leak                                                                                            |
| Reveal scope          | Only inside the editor; closes on focus-out; optional inactivity timer                                                    |
| Persistence           | Heuristic-only on load; accept documented limitation                                                                      |
| Text-family interplay | **Open** — see below                                                                                                      |
| Editor UX             | `QLineEdit.Password` + eye-icon toggle                                                                                    |
| Name patterns         | Editable in `settings.py` **and** in a Settings dialog                                                                    |

### Open item — `SECRET` × `MULTILINE`

User indicated SECRET should be able to "wrap any text variant, incl.
MULTILINE for PEM keys", but also opted **out** of a flag/modifier model.
Resolved for v1 as: **SECRET is a single, flat kind that accepts arbitrary
string content (newlines allowed in the stored value).** The editor remains
single-line `QLineEdit` in v1; multi-line secret editing (PEM-style) is a
v2 follow-up that would either (a) introduce a multi-line secret editor or
(b) re-model SECRET as an orthogonal flag. Flagged in TODO.

## Design notes

- New `JsonType.SECRET = "secret"` in `tree/types.py`.
- `TEXT_FAMILY` is **not** extended to include `SECRET` (transitions in/out
  of SECRET are not free text-axis moves).
- New helper module `validation/secret_names.py` with
  `name_looks_secret(name, patterns) -> bool`:
  - case-insensitive substring match by default;
  - `"re:<expr>"` prefix → regex match (`re.IGNORECASE`);
  - empty / non-string `name` → `False`.
- `parse_json_type` is **not** name-aware. Promotion happens in the model
  on name-change / cell-create hooks.
- Sticky rule lives entirely in the model: once `kind == SECRET`, name
  changes do not alter `kind`.
- View masking lives in `delegates/value_formatting.py`. No reveal state in
  the view-layer model for v1 (reveal is editor-local).

## Commits

### Commit 1 — `settings.py`

```python
SECRET_NAME_PATTERNS: tuple[str, ...] = (
    "password", "passwd", "pwd",
    "secret", "token", "api_key", "apikey",
    "access_key", "private_key",
    "re:auth.*token",
)
SECRET_MASK_GLYPHS = 8          # fixed glyph count when masked
SECRET_MASK_CHAR = "•"
SECRET_HIDE_ON_FOCUS_OUT = True # auto-close editor + re-mask on focus loss
SECRET_REVEAL_INACTIVITY_MS = 0 # 0 = no inactivity auto-mask in editor
```

**DoD**
- Module imports cleanly.
- `tests/test_settings_secret.py` asserts constants exist with documented
  types.

### Commit 2 — `validation/secret_names.py` (new)

Implement `name_looks_secret(name, patterns)`.

**DoD** — `tests/test_secret_names.py`:
- `"Password"` ✔, `"user_token_v2"` ✔, `"description"` ✘.
- Custom `("re:^x_.*key$",)` matches `"x_super_key"` only.
- Stdlib only.

### Commit 3 — `tree/types.py`

- Add `JsonType.SECRET = "secret"`.
- Add `SECRET_FAMILY = frozenset({JsonType.SECRET})`.
- `TEXT_FAMILY` unchanged (does **not** include SECRET).
- Docstring on `parse_json_type` noting name-based promotion is the model's
  responsibility.

**DoD** — existing tests green; `JsonType.SECRET` exported.

### Commit 4 — Model integration (sticky promotion)

Files: `tree/item.py` and/or `tree/item_coercion.py` (verify ownership of
name-change / value-change hooks before editing).

- On **new** cell in `TEXT_FAMILY` **or** name change of a `TEXT_FAMILY`
  cell: if `name_looks_secret(name, SECRET_NAME_PATTERNS)` → promote to
  `SECRET`.
- Once `kind == SECRET`: **sticky** — subsequent name changes do not
  demote.
- Promotion never modifies the stored value.

**DoD** — `tests/test_secret_promotion.py`:
- Rename `STRING` "comment" → "password" promotes to `SECRET`.
- Rename `SECRET` "password" → "comment" stays `SECRET` (sticky).
- Creating a new field named `api_key` starts as `SECRET`.

### Commit 5 — `delegates/value_formatting.py` (masked rendering)

- `SECRET` cells render `SECRET_MASK_CHAR * SECRET_MASK_GLYPHS`.
- Tooltip identical (no length leak; no value substring).
- Other kinds unaffected.

**DoD**
- `SECRET` cell with value `"hunter2"` displays exactly `••••••••`.
- Cell with value `""` also displays `••••••••` (no `<empty>` leak).
- Tooltip equals the mask string.

### Commit 6 — Editor: masked `QLineEdit` + eye toggle

File: whichever delegate creates the single-line text editor (likely
`delegates/value.py` — verify).

- For `SECRET` cells: editor is a `QLineEdit` with `EchoMode.Password` by
  default; embedded eye-icon `QAction` toggles to `EchoMode.Normal` for the
  duration of the edit.
- **Focus-out / tab-switch behavior** (when `SECRET_HIDE_ON_FOCUS_OUT`):
  intercept `focusOut` / app `applicationStateChanged` to inactive →
  `commitData` + `closeEditor`, which causes the view to re-mask.
- Optional inactivity timer (`SECRET_REVEAL_INACTIVITY_MS > 0`): while in
  Normal echo, restart on key/mouse activity; on timeout flip back to
  Password echo (editor stays open).

**DoD**
- Double-click on `SECRET` cell → editor with bullets, eye icon visible.
- Click eye → plaintext; click again → bullets.
- Switching apps / focusing another tab closes the editor and the view
  shows `••••••••`.
- After commit, the view re-masks (covered by Commit 5).

### Commit 7 — Settings dialog: editable name patterns

Files: the existing app settings UI (locate under `app/` — likely a
preferences dialog; if none exists, add a minimal modal under `dialogs/`).

- Add a list editor for `SECRET_NAME_PATTERNS` (add / remove / edit row;
  `re:` prefix supported and indicated in placeholder text).
- Changes persist via the existing settings mechanism (verify whether
  `settings.py` is a frozen module or backed by `QSettings`; if frozen,
  introduce a thin runtime override layer rather than mutating the module).
- Live-apply: changing patterns re-evaluates promotion **only on next
  name/value edit** (we do not retroactively scan existing cells — keeps
  sticky semantics clean).

**DoD**
- Patterns added in the dialog cause new fields matching them to be
  detected as `SECRET`.
- Removing the default `"password"` pattern means a *new* field named
  `password` does **not** auto-promote (existing `SECRET` cells stay
  sticky).
- Patterns survive app restart.

### Commit 8 — `io_formats/dump.py` + `io_formats/load.py`

- Dump: write `SECRET` as a plain string. No magic marker.
- Load: rely on Commit 4's name heuristic to re-promote on import.
  Document this in a module docstring.

**DoD** — `tests/test_io_secret.py`:
- Tree with `password = "hunter2"` saved and reloaded → `SECRET`.
- Tree with `notes = "hunter2"` whose kind is `SECRET` (sticky from a
  prior `password` rename) is saved and reloaded → falls back to `STRING`.
  Test asserts this limitation and references the TODO.

### Commit 9 — Docs + TODOs

Update `README.md`, `ai-memory/repo-map.md`:
- Document the `SECRET` kind, sticky semantics, name-pattern config (file
  + dialog), and the persistence limitation.

Append to `ai-memory/todo-n-fixme.md`:
- Persist `SECRET` kind for non-matching names (needs schema sidecar /
  metadata file).
- Clipboard scrubbing for revealed `SECRET` values.
- Manual override surface (type-delegate dropdown / context menu) — v2.
- Reveal-in-view (context menu + global timer) — v2.
- Multi-line `SECRET` (PEM blobs) — decide flag-vs-kind modeling — v2.

**DoD** — docs updated; no code changes.

## Deferred to v2 (explicitly out of v1)

1. Context-menu "Reveal value" / "Hide value" with global per-cell timer.
2. Type-delegate dropdown entry for `SECRET` (manual override).
3. Session-wide "reveal all secrets" toggle.
4. Schema sidecar for per-field kind persistence.
5. Multi-line secret editor (PEM keys, certificates).
6. Clipboard scrubbing.
