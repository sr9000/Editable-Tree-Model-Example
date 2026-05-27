---
## Post-migration status (2026-05-27)
The 10-stage plan in `plans/00-overview.md` ... `plans/10-allowlist-and-precommit-hook.md`
has been executed. Every probe previously listed in this report has been
removed or relocated. The current production-tree state, scanned with the
same commands at the top of this report:
```bash
grep -RIn --include='*.py' --exclude-dir=.venv --exclude-dir=tests \
    -E '\b(get|has)attr\(' .
```
returns matches in exactly three files, all of them by design:
| File                          | Rationale                                                          |
|-------------------------------|--------------------------------------------------------------------|
| `jsontream/__init__.py`       | Generic streaming-encoder probing arbitrary user data shapes.      |
| `validation/error_adapter.py` | Dedicated foreign jsonschema-error adapter (added in stage 06).    |
| `app/runtime_compat.py`       | Qt / PyInstaller / tzinfo / Traversable / QByteArray runtime probes (added in stage 08). |
The pre-commit hook in `.githooks/pre-commit` and the CI mirror at
`.githooks/pre-commit-ci` (wired to `make check-no-reflection` and to
`.github/workflows/no-reflection.yml`) enforce the allowlist on every
future change. Tests may still use reflection but must justify it with
an inline `# allow: <reason>` comment.
