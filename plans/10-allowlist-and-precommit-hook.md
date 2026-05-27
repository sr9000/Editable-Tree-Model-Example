# Stage 10 — Allowlist and pre-commit grep hook

Final stage. Turns the rule on permanently.

## Allowlist (after stages 01–09 land)

Production files where `getattr` / `hasattr` are permitted:

| Path                                  | Rationale                                                                 |
|---------------------------------------|---------------------------------------------------------------------------|
| `jsontream/__init__.py`               | Generic streaming encoder probing arbitrary user data shapes.             |
| `validation/error_adapter.py`         | Single, dedicated foreign-error normalization boundary (stage 06).        |
| `app/runtime_compat.py`               | Centralized Qt / PyInstaller / tzinfo / Traversable / QByteArray probes (stage 08). |

Tests (`tests/`) are scanned with a relaxed rule (see hook below) — they
often need reflection for fixture introspection, but new test files must
still document the reason.

## Pre-commit hook

Add `.githooks/pre-commit` (or a `pre-commit` framework entry). The hook
runs only on staged Python files and fails if any **non-allowlisted**
file under version control contains `getattr(` or `hasattr(`.

```bash
#!/usr/bin/env bash
# .githooks/pre-commit — block new getattr/hasattr outside allowlist
set -euo pipefail

ALLOWLIST=(
    "jsontream/__init__.py"
    "validation/error_adapter.py"
    "app/runtime_compat.py"
)

is_allowlisted() {
    local path="$1"
    for allowed in "${ALLOWLIST[@]}"; do
        [[ "$path" == "$allowed" ]] && return 0
    done
    return 1
}

staged_py=$(git diff --cached --name-only --diff-filter=ACMR -- '*.py')
fail=0
for f in $staged_py; do
    # Tests get a softer rule: require an inline justification comment.
    if [[ "$f" == tests/* ]]; then
        if git diff --cached -- "$f" | grep -E '^\+.*\b(get|has)attr\(' \
            | grep -vE '# *allow: ' >/dev/null; then
            echo "::error file=$f::new getattr/hasattr in tests must end with '# allow: <reason>'"
            fail=1
        fi
        continue
    fi
    if is_allowlisted "$f"; then
        continue
    fi
    if grep -nE '\b(get|has)attr\(' "$f" >/dev/null; then
        echo "::error file=$f::getattr/hasattr is forbidden outside the allowlist"
        grep -nE '\b(get|has)attr\(' "$f"
        fail=1
    fi
done

exit $fail
```

Install with:

```bash
git config core.hooksPath .githooks
chmod +x .githooks/pre-commit
```

## CI gate

Mirror the same check in CI so PRs cannot bypass the local hook:

```yaml
# .github/workflows/lint.yml (excerpt)
- name: Forbid getattr/hasattr outside allowlist
  run: |
      bash .githooks/pre-commit-ci   # variant that scans full tree, not staged
```

Provide a companion script `.githooks/pre-commit-ci` that iterates over
all tracked `.py` files (`git ls-files '*.py'`) using the same allowlist.

## Inline escape hatch (optional, discouraged)

If a future case truly needs reflection outside the allowlisted files,
the only escape is to **add the file to the allowlist** in a dedicated
PR that:

1. Updates this stage 10 document with the rationale.
2. Updates `reports/getattr-usage-analysis.md` with the new boundary.
3. Adds a code comment `# allowlist: <reason>` next to the call.

No silent `# noqa` comments are accepted.

## Steps

1. Verify the allowlist matches reality: stages 01–09 must be merged
   first; `grep -RIn 'getattr\|hasattr' --include='*.py'` against the
   workspace must show only the three allowlisted files (plus tests).
2. Add `.githooks/pre-commit` and `.githooks/pre-commit-ci` as above.
3. Wire `core.hooksPath` via `Makefile` target (e.g. `make dev-setup`)
   and document it in `README.md`.
4. Add the CI job and confirm it fails on a deliberately introduced
   `getattr(...)` in a non-allowlisted file (sanity test).
5. Update `reports/getattr-usage-analysis.md` with a final post-migration
   summary table (counts → 0 outside allowlist).

## Acceptance criteria

- `grep -RIn --include='*.py' --exclude-dir=.venv 'getattr\|hasattr' .`
  outside `tests/` returns matches **only** in:
  - `jsontream/__init__.py`
  - `validation/error_adapter.py`
  - `app/runtime_compat.py`
- Pre-commit hook installed and reject test verified.
- CI workflow contains the same enforcement.
- `README.md` documents `make dev-setup` (or equivalent) for activating
  the hook on a fresh clone.
- `reports/getattr-usage-analysis.md` updated with the post-migration
  counts and a link back to `plans/getattr-elimination/`.
