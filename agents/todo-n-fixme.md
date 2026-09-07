# TODO & FIXME

_Last updated: **2026-09-07**. Open work only — completed items are deleted, not
archived. Format: `- [ ] [scope] description — file:symbol`. Reference symbols,
not line numbers: line numbers rot silently._

## Windows/macOS packaging (settled — do not re-investigate)

_A dedicated investigation concluded a Windows `.exe` cannot be built on this
Linux host. Every fact below is measured, not assumed — cite this section
instead of re-deriving it._

- A local Windows build is impossible for two independent, inherent reasons:
  (1) PyInstaller cannot cross-compile — it freezes using the *running*
  interpreter, so a Windows `.exe` requires a Windows Python; this is a
  PyInstaller limitation, not a gap in this repo. (2) Wine was tried as a way
  to get a Windows Python on Linux, via the image `tobix/pywine:3.14`. It
  genuinely provides Windows CPython 3.14.7 (`sys.platform == "win32"`), and
  every non-Qt native dependency installs from win_amd64 wheels and imports
  cleanly under it with no source builds — gmpy2, numpy, pandas, jsonschema,
  PyYAML, simplejson, python-dateutil. ONLY Qt fails: `Qt6Core.dll` imports
  `icuuc.dll` — the ICU library Windows itself has shipped as an OS component
  since Windows 10 version 1703 — and Wine 11.0 does not provide it, so
  PySide6's QtCore, QtWidgets and QtNetwork all fail to load. The PySide6
  wheel is fine on real Windows; the gap belongs to Wine.
- Prebuilt ICU4C DLLs do NOT close this gap: they export version-suffixed
  symbols (e.g. `u_strlen_74`), while Qt links against the unsuffixed Windows
  system ABI.
- A produced `.exe` is NOT evidence of a working build: PyInstaller still
  emitted a 22.8MB `.exe` under Wine despite the Qt failure above — its Qt
  hook hit the same failure, logged it only at WARNING level, and silently
  fell back to static hooks.
- `requirements.txt` is a current, fully-pinned `poetry export` carrying
  `python_version == "3.14"` markers. This was explicitly checked: it is NOT
  stale post-Poetry-migration. **Future agents must not "fix" it.**
- macOS hits a strictly harder version of the same wall: it needs Apple
  tooling, and the spec's `BUNDLE()` step is darwin-only.
- Windows and macOS builds are now **DONE**, proven working, via
  `.github/workflows/release.yml` (`workflow_dispatch`; matrix includes
  `windows-latest` and `macos-latest`; `PYTHON_VERSION` 3.14,
  `PYINSTALLER_VERSION` 6.22.2, spec mode). GHA is the only route to these two
  platforms — the local-impossibility reasoning above is exactly why — but on
  GHA it works cleanly. The workflow's `tag` input is now optional (default
  `""`): a tagless dispatch builds all three platforms and uploads artifacts
  while publishing nothing (the `release` job is gated on
  `if: inputs.tag != ''`); packaging steps fall back to naming assets
  `dev-<7-char-sha>` when the tag is empty. A dispatch with a tag additionally
  publishes a GitHub Release.
  — `.github/workflows/release.yml`
- Proof, tagless build — run `34116256891`: all three Build jobs green,
  `Publish GitHub Release` correctly skipped. Artifacts: linux AppImage
  134503586 bytes, windows zip 92971831 bytes, macos dmg 73473150 bytes.
- Proof, full release path — run `34118803328`, dispatched on **master** with
  `tag=v1.4.0`: all four jobs green including Publish. Three assets attached,
  named `EditableTreeModel-v1.4.0-<platform>.<ext>` (AppImage 134583488 bytes,
  dmg 74575924 bytes, windows zip 92942999 bytes). This is the released
  artifact set; **v1.4.0 is the first release built on Poetry + Python 3.14**.
- Validity evidence for the Windows binary — a produced `.exe` is not by
  itself proof of a working build (see the Wine `.exe` above). Three
  independent checks on `EditableTreeModel.exe` (93705189 bytes) from v1.4.0:
  1. PE structure: `MZ` -> `PE\0\0` -> machine `0x8664` -> PE32+ (`0x20b`) ->
     subsystem 2 (GUI).
  2. PyInstaller CArchive cookie (magic `MEI\014\013\012\013\016`) 88 bytes
     from EOF: embedded package 93312485 bytes — 99.6% of the file — Python
     version `314`, bundled runtime `python314.dll`.
  3. The archive's **TOC, enumerated**: 3617 entries, including
     `PySide6\Qt6Core.dll`, `Qt6Gui/Widgets/Quick/Qml/Pdf/OpenGL/Network`,
     the `QtCore/QtGui/QtWidgets/QtNetwork` `.pyd` modules, `python314.dll`,
     `PySide6\plugins\platforms\qwindows.dll`, and the `main` entry script.
  To parse the TOC yourself, note the entry header is **18** bytes
  (`!iIIIBc`); a 22-byte guess silently truncates every name and makes a
  correct bundle look empty.
  Grepping the onefile `.exe` for `Qt6Core` returns nothing, but that is
  **inconclusive by construction** — the payload is compressed. The TOC is the
  valid check, and it is positive. Do not read the grep as a failure.
  The build log has ZERO occurrences of `icuuc` or `DLL load failed`, and
  PyInstaller processed `hook-PySide6.py` as a standard module hook — the
  direct contrast with the Wine attempt, where the same hook failed at WARNING
  level while still emitting an `.exe`.
- ICU is absent from the bundle (0 TOC entries) and that is **correct** for a
  Windows target: `icuuc.dll` is an OS component there. The Wine failure was
  the OS side not providing it, not the bundle omitting it. Do not "fix" this
  by bundling ICU.
- CI fact worth keeping so nobody re-derives it: `workflow_dispatch` inputs
  are validated by GitHub against the workflow file **on the dispatched ref**,
  not the one on the default branch. A tagless dispatch worked from a feature
  branch while master's copy still declared `tag` as required — master has
  since been fixed by the same PR, but the rule is the durable part.
- `windows-latest` build log warning `WARNING: Hidden import "jinja2" not
  found!` is investigated and dismissed as benign. pandas is imported in this
  codebase only for its datetime types (`Timestamp`/`Timedelta`, in
  `tree/types.py`, `tree/item.py`, `tree/item_coercion.py`,
  `tree/types_datetime.py`, `qt2py/__init__.py`,
  `editors/inline/datetime/__init__.py`,
  `editors/inline/datetime/better_dt_editor.py`,
  `delegates/formatting/value_formatting.py`, `core/datetime_parsing/compat.py`).
  A repo-wide search for `.style`, `Styler`, `to_html`, `to_latex`, and
  `to_excel` found no pandas styling or HTML/Excel/LaTeX export usage
  anywhere in the app — the only `to_html`-shaped hit is the unrelated
  `color_to_html` in `tree/codecs/color_codec.py`. jinja2 is not in
  `poetry.lock` and is not installed in the project venv. PyInstaller emits
  the warning only because pandas declares jinja2 as an optional extra for
  `pandas.Styler`; since the app never exercises that path, nothing is
  missing at runtime. **Do not add jinja2 as a dependency, and do not
  re-investigate this warning when it reappears in future build logs.**
  — `.github/workflows/release.yml`
- [ ] [ci] Master's `.github/workflows/release.yml` still pins
  `PYTHON_VERSION: "3.12"` and `PYINSTALLER_VERSION: "6.10.0"`. PyInstaller
  6.10.0 declares `requires_python <3.14` and cannot build this app at all —
  only this branch (`migrate-to-poetry-py314`) has the 3.14 / 6.22.2 fix, so
  the Release workflow is broken on master until this branch merges.
  — `.github/workflows/release.yml`
- [ ] [ci] The debug prerelease `v0.0.0-ci-debug.1` (from proof run
  `34117094101`) is a disposable throwaway, not a real product release —
  delete it once it is no longer needed as evidence.

## High priority

- [ ] [ci] No CI job runs the test suite. `no-reflection.yml` runs only the
  reflection check and the `requirements.txt` freshness check, and
  `release.yml` is `workflow_dispatch`-only, so the whole gate is local-only and
  a pull request can pass having run nothing but a grep.
  — `.github/workflows/no-reflection.yml`
- [ ] [tests] `tests/test_value_delegate.py` — full delegate matrix: editor
  widget class per `JsonType`; `setEditorData` / `setModelData` round-trip for
  INTEGER, mpq FLOAT/PERCENT, BOOLEAN, DATE/TIME/DATETIME/DATETIMEZONE,
  STRING/UNICODE; dialog delegates (MULTILINE/TEXT/BYTES/ZLIB/GZIP) commit via
  `QPersistentModelIndex` + `JsonTab.commit_set_data`.
- [ ] [tests] `tests/test_io_roundtrip.py` — parametrized load → mutate → save →
  reload property tests against `data.json` / `data.yaml` (+ JSONL /
  YAML-multi), asserting mpq and tz-aware datetimes survive every format.

## Medium priority

- [ ] [refactor] Split `tree_actions/structure.py` (774 lines) into
  `structure_insert` / `structure_move` / `structure_sort` / `structure_expand`.
- [ ] [refactor] Extract a `FileOperationsPresenter` from `app/main_window.py`
  (560 lines): `_confirm_reload_dirty_tab`, `_reload_tab_from_path`, `_save_tab`.
- [ ] [hygiene] Narrow `IoController.save()` exception handling — catch specific
  I/O and serialization errors and surface structured diagnostics for malformed
  datetime / bytes. — `documents/states/io_controller.py:IoController.save`
- [ ] [tests] Model invariants: `setData` emits `dataChanged` covering cols 0..2;
  `removeRows` updates persistent indices; 3-level `parent()`/`index()`
  round-trip; `change_type` `lossy=True` only with prior children;
  `unique_child_name` collision avoidance.

## Low priority — hygiene

- [ ] [tooling] `make lint` runs bare `autoflake .`, which without `--in-place`
  only prints diffs and never modifies files — the step has always been a silent
  no-op. Decide whether to drop it or enable it (`--in-place
  --remove-all-unused-imports`); enabling it rewrites imports across the tree, so
  it needs its own commit. — `Makefile:lint`
- [ ] [tooling] Replace the **file:line** allowlist in
  `.githooks/_check_tree_isolation.sh` with a marker comment (e.g. an inline
  `# allow: <reason>`, matching the reflection hook's convention). The current
  form breaks or silently exempts the wrong import whenever an edit shifts a
  line. — `.githooks/_check_tree_isolation.sh`
- [ ] [tooling] Commit a coverage snapshot to `agents/coverage.md`; `pytest-cov`
  is already declared in the Poetry `test` group.
- [ ] [hygiene] Rename the underscore-prefixed helpers re-exported across
  `tree_actions/` (`_resolve_model`, `_to_source_index`, …) — they are a shared
  internal API, not module-private. — `tree_actions/selection.py`
- [ ] [tests] Add a `Document`-protocol conformance check (mypy or a dedicated
  test) verifying `JsonTab` implements every `Document` attribute.
- [ ] [smell] `JsonTreeItem.row()` returns `0` for the root; return `-1` to
  signal "no parent". — `tree/item.py:JsonTreeItem.row`
- [ ] [smell] `create_value_editor` raises `ValueError` for OBJECT/ARRAY/NULL
  (unreachable via `flags()`); `return None` degrades more gracefully.
  — `editors/factory.py:create_value_editor`

## Feature follow-ups (deferred)

- [ ] [secret] Persist secret kind for non-matching field names (schema-sidecar /
  metadata) so sticky secrets survive rename + reload. — `tree/item.py`,
  `io_formats/{dump,load}.py`
- [ ] [secret, security] Clipboard scrubbing for revealed secrets (clear/expire
  after copy). — `tree_actions/clipboard.py`
- [ ] [validation] URL schema staleness — add `ETag` / `If-Modified-Since`
  conditional requests on `reload()`. — `validation/schema_registry.py`,
  `validation/schema_source.py`
- [ ] [validation] Remote `$ref` resolution against `http(s)://` (currently
  silently ignored). — `validation/schema_source.py`, `validation/_engine.py`
- [ ] [ux] Match-highlight delegate (`ValueDelegate.paint` yellow span over
  substring matches when a filter is active). — `delegates/value.py`
- [ ] [docs] README theming section + `themes/builtin/schema.md` (YAML grammar,
  fallback semantics, icon path resolution, worked examples).
