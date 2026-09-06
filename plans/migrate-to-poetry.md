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

- [ ] **T1** Prove the codebase passes `make gate` on Python 3.14 in a throwaway
  venv, before Poetry enters the picture. Isolates "does 3.14 work" from "does
  Poetry work". *(worker)*
- [ ] **T2** Resolve whatever T1 surfaces. *(coordinator)*

### Phase 1 — Poetry bootstrap

- [ ] **T3** Install Poetry (`uv tool install poetry`; no poetry/pipx present),
  set `virtualenvs.in-project true` so `.venv/` stays put and `agent.md`'s
  `. .venv/bin/activate` contract survives. *(worker)*
- [ ] **T4** Author `pyproject.toml`: `package-mode = false`,
  `requires-python = ">=3.14,<3.15"`, dependency groups `main` / `dev` / `test` /
  `build`. *(coordinator — architecture artifact)*
- [ ] **T5** Remove the broken `.venv`, run `poetry install`, commit
  `poetry.lock`. *(worker)*

### Phase 2 — Config consolidation

- [ ] **T6** Move `[tool.black]`, `[tool.isort]`, `[tool.autoflake]` config from
  Makefile CLI flags into `pyproject.toml`. Black auto-discovers `pyproject.toml`
  once it exists, so leaving config split risks silent divergence. *(worker)*
- [ ] **T7** Move `pytest.ini` into `[tool.pytest.ini_options]` and **delete
  `pytest.ini`** — it wins over `pyproject.toml` otherwise. `pythonpath = ["."]`
  is load-bearing for the flat layout and must carry over exactly. *(worker)*
- [ ] **T8** Rewrite Makefile targets to use `poetry run` so they work without an
  activated shell. *(worker)*

### Phase 3 — Interop

- [ ] **T9** Add `poetry-plugin-export`; regenerate `requirements.txt` from the
  lock (main group only); add a `make requirements` target. *(worker)*
- [ ] **T10** Add a CI freshness check so the generated `requirements.txt` cannot
  silently rot — the known failure mode of the export approach. *(worker)*
- [ ] **T11** Update `release.yml`: `PYTHON_VERSION` 3.12→3.14,
  `PYINSTALLER_VERSION` 6.10.0→6.15.0+. `no-reflection.yml` is pure bash and is
  untouched. *(worker)*

### Phase 4 — Verify the bundle

- [ ] **T12** Local PyInstaller build on 3.14 with the upgraded version; confirm
  the produced binary launches. Check whether the spec's numpy/pandas
  `collect_all` block is still required. *(worker, escalate on failure)*

### Phase 5 — Sync agent memory

- [ ] **T13** `README.md` — quick start (venv/pip → Poetry), Development section,
  and the dangling `ai-memory/history.md` reference at line 271.
- [ ] **T14** `agent.md` §1 First commands.
- [ ] **T15** `packaging/README.md` local build steps + PyInstaller version.
- [ ] **T16** `ai-memory/repo-map.md` §11 Commands & Gates.
- [ ] **T17** `ai-memory/pros-n-cons.md` — Tooling gaps section: `pytest-qt` and
  `pytest-cov` are now declared.
- [ ] **T18** `ai-memory/todo-n-fixme.md` — mark the two `[tooling]` items `[x]`.

## 5. Final gate

- [ ] `make gate` green under Poetry on 3.14.
- [ ] `poetry.lock` committed.
- [ ] Feature branch only. **Never pushed to `master`.**
