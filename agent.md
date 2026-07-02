# Agent Guide — Editable-Tree-Model-Example (compact)

_High-signal rules for AI agents. Keep this brief and actionable._
**Last updated:** 2026-06-13

## 1) First commands (always)

```bash
. .venv/bin/activate
timeout 1200 make gate
```

- Tools live in `.venv`.
- `make gate` is mandatory before every commit.

## 2) Mandatory delivery loop (do not skip steps)

For plan-based work, execute exactly this loop:

1. **Pick one next unchecked plan item** (single scope).
2. **Implement only that scope**.
3. **Run targeted tests** for touched files.
4. **Run full gate** (`timeout 1200 make gate`).
5. **Commit immediately** (message references plan item).
6. **Mark plan checkbox `[x]`** only after commit.
7. Repeat for the next item.

Hard rules:
- If tests/gate fail: go back to implementation; **no commit**.
- Do not batch multiple plan items into one commit unless plan explicitly says so.
- Do not stop at “green but uncommitted”.

## 3) Critical architecture facts (easy to miss)

1. **Undo edit path bypasses `JsonTreeItem.set_data()`**
   - Real replay path: `DocumentMutationGateway` → undo command → `undo/diff.py:DiffApplier.apply()`.
   - Type/value fixes often require changes in both item logic and `DiffApplier`.

2. **`mpq` whole numbers are inferred as FLOAT unless converted**
   - Convert `mpq(n,1)` to `int` where integer semantics are required.

3. **UI uses proxy model**
   - Map indices proxy↔source before touching tree items.

4. **Base64 auto-inference has a persisted minimum-length guard**
   - Automatic string→`BYTES`/`ZLIB`/`GZIP` inference only runs when the string length meets the current
     `edit_limits/base64_min_length_chars` threshold (default `100`).
   - Short valid base64 stays `STRING` unless the type is pinned explicitly or the threshold is lowered.

## 4) Isolation constraints (must hold)

- `editors/inline/*`, `editors/windowed/*` must not import `app/`, `documents/`, `tree/`.
- `editors/factory.py`, `editors/context.py` must not import `app/`, `documents/`.
- `tree/` must not import `app/`, `documents/`, `editors/`, `delegates/`, `state/`, `validation/`.
- No reflection (`getattr` / `hasattr` / `TYPE_CHECKING`) outside allowlist.

## 5) Minimal file map for common work

- Types/coercion: `tree/types.py`, `tree/item_coercion.py`
- Item/model behavior: `tree/item.py`, `tree/model.py`
- Undo replay: `undo/commands.py`, `undo/diff.py`
- Tab composition/lifecycle: `documents/composition/*`, `app/tab_lifecycle.py`, `app/main_window.py`
- Validation: `documents/controllers/validation.py`, `validation/*`

## 6) Testing quick rules

- Use `QT_QPA_PLATFORM=offscreen` for pytest.
- Prefer focused tests during development, then full gate.
- Add regression tests for every bug fix or plan checkpoint.
