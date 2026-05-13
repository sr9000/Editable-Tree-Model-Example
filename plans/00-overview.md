# JSON Schema Validation — integration plan

_Goal: wire `jsonschema-rs` (PyPI: `jsonschema-rs`, Rust core) into the
editor so every loaded JSON / YAML document can be validated against
a JSON Schema, with results displayed in a movable dock panel,
clickable to jump to the offending tree row, decorated in the tree
itself, and (optionally) hot-rescanned on every edit._

## Feature checklist (from the user request)

1. **Movable validation log window** — `QDockWidget` allowed in
   `Left | Bottom | Right` dock areas (no top, no floating-only).
2. **Jump-to-problem on click** — clicking an issue selects and
   centres the offending row in the active tab's `JsonTreeView`.
3. **In-tree problem indication** — each row carrying (or containing)
   a validation error gets a severity badge / coloured foreground.
4. **Hot auto-rescan checkbox** — when checked, every model mutation
   triggers a debounced re-validation; unchecked = manual `Rescan`
   button only.

## Constraints

- **Each step = one commit**, ≤ 10 files, ≤ 500 LOC of *new* code
  (test files excluded from the LOC budget when they push beyond it,
  but kept under the file-count cap).
- No regressions in the existing 776-passing test suite.
- Pure-Python wrapper layer around `jsonschema-rs` so we can swap the
  engine later (e.g. `fastjsonschema` fallback) without touching UI.
- All persistence flows through `QSettings(APPLICATION_ID, ...)`,
  consistent with `state/theme_settings.py`.
- All UI strings go through tr() where MainWindow already does so.

## Step map

| # | File                                  | Theme                                                |
| - | ------------------------------------- | ---------------------------------------------------- |
| 1 | `01-validator-core.md`                | Dependency, `validation/` package, pointer mapper, tests |
| 2 | `02-schema-source-and-tab-state.md`   | Schema discovery + per-tab schema/issues state       |
| 3 | `03-validation-dock-panel.md`         | `QDockWidget` (Left/Bottom/Right movable), issues model |
| 4 | `04-jump-to-problem.md`               | Click ↔ tree selection + path resolution             |
| 5 | `05-in-tree-indication.md`            | Severity role + delegate badge + theme entries       |
| 6 | `06-auto-rescan-and-toolbar.md`       | Hot rescan checkbox + debounce + toolbar             |
| 7 | `07-yaml-multidoc-and-persistence.md` | YAML/YAML-multi, schema picker, per-file recall, docs |

Each step file lists: scope, files touched, public API delta,
tests, commit message template, and explicit "out-of-scope" notes.

## Public surface, after Step 7

```python
from validation.validator import validate_document, ValidationIssue
from validation.schema_source import discover_schema, SchemaRef
from validation.index import IssueIndex
from app.validation_dock import ValidationDock
from documents.tab import JsonTab  # gains .schema, .issue_index,
                                   # .revalidate(), signals
                                   # schemaChanged / validationChanged
```

`tree/model_roles.py` gains
`VALIDATION_SEVERITY_ROLE = UserRole + 2`.

## Non-goals (do not creep)

- Online `$ref` resolution against http(s) (only local files +
  inline `$defs`).
- Schema *authoring* UI.
- Quick-fix actions for individual issues.
- Validation of partial selections (whole-doc only).
- Draft selection UI — `jsonschema-rs` auto-detects via `$schema`,
  defaults to Draft 2020-12.
