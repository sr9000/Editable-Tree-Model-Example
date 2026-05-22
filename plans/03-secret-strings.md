# Plan 03 — Secret strings (passwords / tokens / secrets)

> **Revision note (2026-05-22 v3):** Detection remodelled from substring /
> regex patterns to word-prefix matching. Icons added (new Commit 4).
> See **Decisions** below.

## Goal

Two dedicated `JsonType` variants that are **never** auto-classified as
any non-secret kind:

| Kind                   | Mirrors              | Typical use                               |
|------------------------|----------------------|-------------------------------------------|
| `JsonType.SECRET_LINE` | `STRING` / `UNICODE` | password, token, API key — single line    |
| `JsonType.SECRET_TEXT` | `MULTILINE` / `TEXT` | PEM certificate, private key — multi-line |

Both variants:

- are **hidden by default** in the tree view (rendered as `••••••••` with a
  **fixed glyph count**, regardless of length, so length does not leak);
- are **detected by field name** using a **word-prefix** heuristic
  (configurable via settings + dialog);
- are **sticky**: once a cell is either secret kind, renaming the field to
  something innocuous does **not** demote it back;
- use different editors:
  - `SECRET_LINE` → masked `QLineEdit` (Password echo) with eye-icon toggle;
  - `SECRET_TEXT` → masked `QPlainTextEdit` with eye-icon toggle;
- **auto-hide on focus-out / tab-switch**: the editor closes and the cell
  re-masks when the window/tab loses focus;
- are stored as **plain strings** on disk (no encryption — out of scope).
  On reload, name-heuristic re-classification restores the kind.

### Detection: word-prefix heuristic

1. **Split** the field name into words on `_`, `-`, `.`, space, and
   camelCase boundaries (`myApiKey` → `["my", "api", "key"]`).
2. **Check** whether any word starts with one of the configurable
   **secret word prefixes** (case-insensitive).

Default prefixes (user-configurable):

| Prefix    | Matches                                   |
|-----------|-------------------------------------------|
| `passw`   | `password`, `passwd`                      |
| `auth`    | `auth`, `authentication`, `authorization` |
| `token`   | `token`, `tokens`                         |
| `key`     | `key`, `keystore`, `api_key` → word `key` |
| `secret`  | `secret`, `secrets`                       |
| `private` | `private`, `private_key` → word `private` |
| `cert`    | `cert`, `certificate`                     |

This model is simpler and more predictable than substring / regex patterns:
`description` is never a false positive; `x_api_key` matches on the word
`key`; `authToken` (camelCase) matches on the word `auth`.

### Kind selection heuristic

- Name heuristic fires → inspect the current value:
  - value contains newline(s) → promote to `SECRET_TEXT`;
  - otherwise → promote to `SECRET_LINE`.
- Content coercion: if a newline is later typed into a `SECRET_LINE` cell
  the kind upgrades to `SECRET_TEXT` (one-way; sticky).

## Non-goals (v1)

- Encryption at rest. Threat model = shoulder-surfing, screenshots, screen
  sharing — **not** adversarial disk access.
- Clipboard scrubbing — tracked as TODO.
- Persisting secret kind for fields whose **name does not** match the
  patterns (would need a schema sidecar). Tracked as TODO.
- A "Reveal value" context-menu action with a global timer (deferred to v2;
  in v1 reveal happens only inside the editor).
- A type-delegate dropdown entry for secret kinds / manual override
  (deferred to v2).

## Decisions (from interview, updated)

| Topic                | Decision                                                                                                                        |
|----------------------|---------------------------------------------------------------------------------------------------------------------------------|
| v1 scope             | `SECRET_LINE` + `SECRET_TEXT`, masked rendering, name-based auto-detect, masked editors with eye toggle, auto-hide on focus-out |
| Detection model      | **Word-prefix** on split words + **sticky** (rename never demotes)                                                              |
| Kind selection       | Value has newlines → `SECRET_TEXT`; otherwise `SECRET_LINE`; content coercion upgrades LINE → TEXT on newline entry             |
| Manual pin semantics | No pin concept (no manual override surface in v1)                                                                               |
| Masking              | Fixed 8 glyphs, no length leak                                                                                                  |
| Reveal scope         | Only inside the editor; closes on focus-out; optional inactivity timer                                                          |
| Persistence          | Heuristic-only on load; accepted limitation                                                                                     |
| Editor UX            | `SECRET_LINE` → `QLineEdit.Password` + eye toggle; `SECRET_TEXT` → `QPlainTextEdit` + eye toggle                                |
| Name patterns        | Prefix list editable in `settings.py` **and** in a Settings dialog                                                              |
| Icons                | `lock_line` → `SECRET_LINE`; `certificate_2_line` → `SECRET_TEXT`                                                               |

## Design notes

- New `JsonType.SECRET_LINE = "secret_line"` and
  `JsonType.SECRET_TEXT = "secret_text"` in `tree/types.py`.
- `SECRET_FAMILY = frozenset({JsonType.SECRET_LINE, JsonType.SECRET_TEXT})`.
- `TEXT_FAMILY` is **not** extended to include either secret kind.
- New helper module `validation/secret_names.py`:

  ```python
  def _split_words(name: str) -> list[str]:
      """Split on _/- /. and camelCase boundaries, return lowercase words."""
      s = re.sub(r'(?<=[a-z0-9])(?=[A-Z])', '_', name)
      return [w for w in re.split(r'[_\-\.\s]+', s.lower()) if w]

  def name_looks_secret(name: str, prefixes: Iterable[str]) -> bool:
      if not name or not isinstance(name, str):
          return False
      words = _split_words(name)
      lc_prefixes = [p.lower() for p in prefixes]
      return any(w.startswith(p) for w in words for p in lc_prefixes)
  ```

- `parse_json_type` is **not** name-aware. Promotion happens in the model
  on name-change / value-change / cell-create hooks.
- Sticky rule: once `kind in SECRET_FAMILY`, name changes do not alter kind.
  Content coercion may upgrade `SECRET_LINE → SECRET_TEXT` but never
  downgrades.
- View masking lives in `delegates/value_formatting.py`. No reveal state in
  the view-layer model for v1 (reveal is editor-local).
- Icons:
  - Source (neutral): `themes/builtin/mingcute/lock_line.svg` and
    `certificate_2_line.svg` — already cleaned (single `<path>`, `fill='#000000'`).
  - Dark variant (`#a8b4d8`): `themes/builtin/mingcute-dark/`.
  - Light variant (`#3f4550`): `themes/builtin/mingcute-light/`.
  - All six files are **already committed** (done before code work).

## Commits

### Commit 1 — `settings.py`

```python
SECRET_WORD_PREFIXES: tuple[str, ...] = (
    "passw",    # password, passwd
    "auth",     # auth, authentication, authorization
    "token",    # token
    "key",      # key, keystore; also matches "api_key" → word "key"
    "secret",   # secret, secrets
    "private",  # private; also "private_key" → word "private"
    "cert",     # cert, certificate
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

Implement `name_looks_secret(name, prefixes)` using `_split_words` (see
Design notes above). No `re:` prefix support — pure prefix matching.

**DoD** — `tests/test_secret_names.py`:
- `"Password"` ✔ (word `password` starts with `passw`).
- `"user_token_v2"` ✔ (word `token` starts with `token`).
- `"private_key"` ✔ (word `private` starts with `private`; `key` starts
  with `key`).
- `"certificate"` ✔ (word `certificate` starts with `cert`).
- `"myApiKey"` ✔ (camelCase split → word `key` matches `key`).
- `"description"` ✘.
- `"keynote"` ✔ (word `keynote` starts with `key` — acceptable; users who
  disagree can narrow the prefix to `"keysto"` etc.).
- Stdlib only.

### Commit 3 — `tree/types.py`

- Add `JsonType.SECRET_LINE = "secret_line"`.
- Add `JsonType.SECRET_TEXT = "secret_text"`.
- Add `SECRET_FAMILY = frozenset({JsonType.SECRET_LINE, JsonType.SECRET_TEXT})`.
- `TEXT_FAMILY` unchanged (does **not** include either secret kind).
- Docstring on `parse_json_type` noting name-based promotion and content
  coercion are the model's responsibility.

**DoD** — existing tests green; both new kinds exported.

### Commit 4 — Icons: SVG assets + theme YAML mapping

**SVG files (already on disk, no edits needed):**
- `themes/builtin/mingcute/lock_line.svg` — cleaned neutral source.
- `themes/builtin/mingcute/certificate_2_line.svg` — cleaned neutral source.
- `themes/builtin/mingcute-dark/lock_line.svg` — dark variant (`#a8b4d8`).
- `themes/builtin/mingcute-dark/certificate_2_line.svg` — dark variant.
- `themes/builtin/mingcute-light/lock_line.svg` — light variant (`#3f4550`).
- `themes/builtin/mingcute-light/certificate_2_line.svg` — light variant.

**Theme YAML updates** (all four themes: `dark.yaml`, `light.yaml`,
`monokai.yaml`, `monokai-light.yaml`):

Add type style entries:
```yaml
secret_line:
  fg: '<theme-appropriate amber>'   # suggested: near date/time color family
secret_text:
  fg: '<same>'
  italic: true
```

Add icon map entries:
```yaml
secret_line: lock_line
secret_text: certificate_2_line
```

**DoD**
- Icons appear in the tree view for `SECRET_LINE` and `SECRET_TEXT` cells
  in all four built-in themes.
- Colors are visually distinct from `string`/`multiline` and do not clash
  with the boolean red or bytes orange.

### Commit 5 — Model integration (sticky promotion + content coercion)

Files: `tree/item.py` and/or `tree/item_coercion.py` (verify ownership of
name-change / value-change hooks before editing).

**Promotion on name change / new cell:**
- Cell `kind in TEXT_FAMILY` and `name_looks_secret(name, SECRET_WORD_PREFIXES)`:
  - value has `\n` → promote to `SECRET_TEXT`;
  - otherwise → promote to `SECRET_LINE`.
- Cell `kind in SECRET_FAMILY`: name change does **not** alter kind (sticky).

**Content coercion (value change):**
- Cell `kind == SECRET_LINE` and new value contains `\n` → upgrade to
  `SECRET_TEXT` (sticky).
- `SECRET_TEXT` with no newlines stays `SECRET_TEXT`.

Promotion and coercion never modify the stored value.

**DoD** — `tests/test_secret_promotion.py`:
- Rename `STRING` "comment" → "password" with single-line value → `SECRET_LINE`.
- Rename `STRING` "comment" → "private_key" with PEM value (`\n`) → `SECRET_TEXT`.
- Rename `SECRET_LINE` "password" → "comment" → stays `SECRET_LINE` (sticky).
- Creating new field `api_key` with no value → `SECRET_LINE`.
- Pasting a multiline value into a `SECRET_LINE` cell → upgrades to `SECRET_TEXT`.
- Removing newlines from a `SECRET_TEXT` value → stays `SECRET_TEXT`.

### Commit 6 — `delegates/value_formatting.py` (masked rendering)

- Cells with `kind in SECRET_FAMILY` render `SECRET_MASK_CHAR * SECRET_MASK_GLYPHS`.
- Tooltip identical (no length leak; no value substring).
- Other kinds unaffected.

**DoD**
- `SECRET_LINE` cell with value `"hunter2"` displays exactly `••••••••`.
- `SECRET_TEXT` cell with multi-line PEM value displays exactly `••••••••`.
- Cell with value `""` also displays `••••••••`.
- Tooltip equals the mask string for both secret kinds.

### Commit 7 — Editors: masked `QLineEdit` & `QPlainTextEdit` + eye toggle

File: whichever delegate creates the single-line and multi-line text
editors (likely `delegates/value.py` and a sibling — verify).

**`SECRET_LINE` editor:**
- `QLineEdit` with `EchoMode.Password` by default.
- Embedded eye-icon `QAction` toggles to `EchoMode.Normal` for the edit
  session.

**`SECRET_TEXT` editor:**
- `QPlainTextEdit` (or a subclass) where characters are rendered as `•`
  while masked. Toggle eye icon shows/hides plaintext.
  - Implementation option A: custom font that maps all glyphs to `•`.
  - Implementation option B: `QSyntaxHighlighter` that sets text color equal
    to background (invisible), draws `•` overlay in `paintEvent`.
  - Choose whichever is simpler and does not break copy/paste semantics when
    revealed.

**Shared behavior (both editors):**
- `SECRET_HIDE_ON_FOCUS_OUT`: intercept `focusOut` /
  `applicationStateChanged` → inactive → `commitData` + `closeEditor` →
  view re-masks.
- Optional inactivity timer (`SECRET_REVEAL_INACTIVITY_MS > 0`): resets on
  key/mouse activity; on timeout flips back to masked mode inside the editor.

**DoD**
- Double-click on `SECRET_LINE` cell → `QLineEdit` with bullets, eye icon.
- Double-click on `SECRET_TEXT` cell → `QPlainTextEdit` with masked content,
  eye icon.
- Click eye → plaintext; click again → masks.
- Switching apps / tabs closes either editor; view shows `••••••••`.
- After commit, view re-masks (covered by Commit 6).

### Commit 8 — Settings dialog: editable word prefixes

Files: the existing app settings UI (locate under `app/` — likely a
preferences dialog; if none exists, add a minimal modal under `dialogs/`).

- Add a list editor for `SECRET_WORD_PREFIXES` (add / remove / edit row;
  each row is a plain lowercase prefix string; placeholder text explains the
  word-split semantics).
- Persist via the existing settings mechanism. If `settings.py` is a frozen
  module, introduce a thin runtime override layer rather than mutating the
  module.
- Live-apply: changing prefixes re-evaluates promotion **only on next
  name/value edit** (no retroactive scan — keeps sticky semantics clean).

**DoD**
- Adding `"dbpass"` causes a new field `dbpassword` to be detected as secret
  (word `dbpassword` starts with `dbpass`).
- Removing `"passw"` means a *new* `password` field does not auto-promote
  (existing secret cells stay sticky).
- Prefixes survive app restart.

### Commit 9 — `io_formats/dump.py` + `io_formats/load.py`

- Dump: write both secret kinds as plain strings. No magic marker.
- Load: rely on Commit 5's name heuristic + content coercion to re-classify.
  Document this in module docstrings.

**DoD** — `tests/test_io_secret.py`:
- Field `password = "hunter2"` saved and reloaded → `SECRET_LINE`.
- Field `private_key = "<PEM with \\n>"` saved and reloaded → `SECRET_TEXT`.
- Field `notes = "hunter2"` whose kind is `SECRET_LINE` (sticky from a
  prior rename) is saved and reloaded → falls back to `STRING`. Test asserts
  this limitation and references the TODO.

### Commit 10 — Docs + TODOs

Update `README.md`, `ai-memory/repo-map.md`:
- Document `SECRET_LINE` and `SECRET_TEXT` kinds, word-prefix detection,
  sticky semantics, settings + dialog config, and persistence limitation.

Append to `ai-memory/todo-n-fixme.md`:
- Persist secret kind for non-matching names (needs schema sidecar).
- Clipboard scrubbing for revealed secret values.
- Manual override surface (type-delegate dropdown / context menu) — v2.
- Reveal-in-view (context menu + global timer) — v2.

**DoD** — docs updated; no code changes.

## Deferred to v2 (explicitly out of v1)

1. Context-menu "Reveal value" / "Hide value" with global per-cell timer.
2. Type-delegate dropdown entry for secret kinds (manual override).
3. Session-wide "reveal all secrets" toggle.
4. Schema sidecar for per-field kind persistence.
5. Clipboard scrubbing.
