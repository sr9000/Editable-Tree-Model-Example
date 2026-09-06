# Plan — Migrate to Poetry on Python 3.14

_Branch: `migrate-to-poetry-py314`. Created 2026-09-06._

**Definition of done:** the project builds, lints, tests, and bundles under Poetry
with Python 3.14, `poetry.lock` committed, all docs updated, nothing pushed to
`master`.

## 0. Decisions (fixed — do not relitigate)

| Decision | Choice |
|:---|:---|
| Python target | **3.14** (`requires-python = ">=3.14,<3.15"`) |
| Version pinning | **Caret ranges + committed `poetry.lock`** |
| `requirements.txt` | **Kept, generated** from the lock via `poetry export` |
| Tool config | **All** of black/isort/autoflake/pytest moved into `pyproject.toml` |
| Package mode | **`package-mode = false`** — this is an app, not a distributable library |

### Why `package-mode = false`

18 flat top-level packages (`app/`, `tree/`, `editors/`, `documents/`, `core/`,
`delegates/`, `undo/`, `validation/`, `themes/`, `state/`, `io_formats/`, `ui/`,
`tree_actions/`, `units/`, `binary/`, `coalesce/`, `jsontream/`, `mpq2py/`,
`qt2py/`) plus `main.py`. Enumerating them in `packages = [...]` or restructuring
to `src/` would break every import, the PyInstaller spec, and the isolation
hooks. Poetry manages the venv + lock only; imports keep working via pytest's
`pythonpath`.

## 1. Discovered drift (the real reason this migration is non-trivial)

- **`requirements.txt` was incomplete.** `make gate` depends on `black`, `isort`,
  `autoflake` — none declared. Also undeclared but installed: `mypy`, `vulture`,
  `pytest-qt`, `pytest-cov`, `pyinstaller`.
- **Two `todo-n-fixme.md` items are already resolved in practice** — `pytest-qt`
  (4.5.0) and `pytest-cov` (7.0.0) are installed, just never declared.
- **`pandas` drifted a major version** — declared `>=2.0.0`, installed `3.0.3`.
  Imported in 17 places.
- **`.venv` is broken** — built for 3.12, `bin/python3` symlinks to system
  `/usr/bin/python3` which is now 3.14, so `lib/python3.12/site-packages` is off
  `sys.path`. Nothing runs until it is rebuilt.
- **Unused installed packages to drop:** `pillow`, `arrow`, `ast_serialize`,
  `librt`, `PySide6_QHexEdit`, `shiboken6_generator`, `pandas_stubs`, `build`,
  `scikit_build_core` — zero imports in source.

## 2. Hard blocker found up front

**PyInstaller 6.10.0 declares `requires_python = "<3.14,>=3.8"` — it excludes
Python 3.14.** Minimum viable is **6.15.0** (`<3.15`); latest 6.x is 6.22.2.
Moving to 3.14 therefore *forces* a PyInstaller upgrade.

Risk: `release.yml` is `workflow_dispatch`-only, so a broken bundle will not
surface until a release is cut. The spec (`EditableTreeModel.spec`) carries
hand-tuned `collect_all` workarounds for NumPy 2.x internals that newer
`pyinstaller-hooks-contrib` may now handle itself.

Everything else is clean on 3.14 — PySide6 6.11.1 (abi3/cp310), gmpy2 2.3.0,
PyYAML 6.0.3, simplejson 4.1.1, pandas 3.0.3 all ship cp314 wheels.

## 3. Execution model

- **Coordinator (Opus, high effort):** architecture, sequencing, all blocker
  resolution, review of every diff.
- **Workers (Sonnet, low effort):** one small prescriptive task each,
  self-contained, ≤200 lines of context.
- **Workers never resolve blockers.** They stop and escalate to the coordinator.
- One plan item → one gate run → one commit. Mark `[x]` only after the commit.

## 4. Task list

### Phase 0 — Baseline

- [x] **T1** Prove the codebase passes `make gate` on Python 3.14 in a throwaway
  venv, before Poetry enters the picture. **Result: fully green — 1813 passed,
  zero lint drift.** The 3.14 jump was validated independently of Poetry.
- [x] **T2** Resolve what T1 surfaced (all environment gaps, no code defects).

### Phase 1 — Poetry bootstrap — commit `b2a70b7`

- [x] **T3** Poetry 2.4.3 installed via `uv tool install`; in-project venv
  configured via committed `poetry.toml`.
- [x] **T4** `pyproject.toml` authored with `package-mode = false` and
  main / dev / test / optional-build groups.
- [x] **T5** Broken `.venv` removed, `poetry install` clean, `poetry.lock`
  committed (48 packages installed, 3.14.4).

### Phase 2 — Config consolidation — commit `1937f35`

- [x] **T6** `[tool.black]` and `[tool.isort]` moved into `pyproject.toml`.
  Used `extend_skip`, not `skip`: `skip` *replaces* isort's built-in skip list
  (which covers `.venv`, `build`, `dist`) rather than adding to it.
  **No `[tool.autoflake]`** — see §6.
- [x] **T7** `pytest.ini` folded into `[tool.pytest.ini_options]` and deleted.
  pytest confirms `configfile: pyproject.toml`.
- [x] **T8** Makefile targets now use `poetry run`.

### Phase 3 — Interop — commit `3f1f4a8`

- [x] **T9** `poetry-plugin-export` added; `requirements.txt` regenerated
  (9 hand-written lines → 26 transitive pins, correctly dropping `pytest`);
  `make requirements` target added.
- [x] **T10** CI freshness job added, with Poetry pinned to 2.4.3 so export
  formatting differences cannot fail it spuriously.
- [x] **T11** `release.yml` moved to Python 3.14 / PyInstaller 6.22.2.

### Phase 4 — Verify the bundle

- [x] **T12** PyInstaller 6.22.2 build succeeds on 3.14. 114 MB single-file
  binary starts cleanly under offscreen Qt with no missing modules. The spec's
  numpy/pandas `collect_all` block was left untouched and still works.

### Phase 5 — Sync agent memory — commit `0f6add7`

- [x] **T13**–**T18** All six doc files updated. Stale facts corrected along the
  way: test count was 1023/1124/1181 across docs (actual 1813), the packaging
  README described a one-folder distribution when the spec builds single-file,
  the `ai-memory/history.md` link was dangling, and the README's claim of flaky
  offscreen color-scheme tests was obsolete.

## 6. Findings worth keeping

- **`make lint`'s `autoflake` step has always been a no-op.** It runs bare
  `autoflake .`; without `--in-place` autoflake only prints diffs. Verified
  empirically. Left as-is and tracked in `agents/todo-n-fixme.md` rather than
  "fixed" here, because enabling it would rewrite imports repo-wide.
- **black 25.1.0 → 25.12.0 produced zero net diff.** The formatter bump was a
  non-event, confirmed against the pre-migration baseline.
- **Environment gaps hit along the way** (all sandbox provisioning, no code
  defects): `python3.14-venv`, the Qt runtime libraries, and `libpython3.14`
  (required by PyInstaller). CI is unaffected — `actions/setup-python` ships a
  shared library and the release workflow already installs the Qt libs.
- **`release.yml` remains `workflow_dispatch`-only.** There is still no CI job
  that runs the test suite, so the bundle path is only exercised on demand.

## 5. Final gate

- [x] `make gate` green under Poetry on 3.14.
- [x] `poetry.lock` committed.
- [x] Feature branch only. **Never pushed to `master`.**
