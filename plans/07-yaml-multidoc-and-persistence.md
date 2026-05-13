# Step 7 — YAML / multi-doc support, schema picker UI, persistence, docs

_Commit-sized: 7 source files + 3 test files; ~450 LOC._

## Scope

The previous six steps assumed a single Python tree against a single
schema. This final step covers the real-world surfaces:

1. **YAML schemas** load through `io_formats.load_file_with_format`,
   not just JSON. Already half-there in Step 2 — round-trip + tests.
2. **YAML multi-document** (`SAVE_FORMAT_YAML_MULTI`) — each doc is
   validated separately; issues are reported with their doc index
   in the `instance_path` prefix (`("[doc 0]", ...)`).
3. **Manual schema picker UI** — file dialog wired to the dock's
   header, "Attach schema…" / "Reload schema" / "Open schema file".
4. **Per-file recall** — after attaching a manual schema for
   `~/projects/foo.json`, opening `foo.json` again restores the
   binding. Persisted via `QSettings` keyed by sha1 of the resolved
   path, matching `state/view_state.state_key`.
5. **mpq sanitisation** — `JsonTreeItem.to_json()` already returns
   `mpq` for floats; `jsonschema-rs` doesn't understand `mpq`. Add a
   `validation/_sanitize.py` step that coerces `mpq` → `Fraction` →
   `float` (best-effort) before validation, with a comment that the
   precision loss is validation-only and never reaches storage.
6. **Docs**: `README.md` section "Validation" with screenshots
   placeholder; `ai-memory/repo-map.md` + `pros-n-cons.md` +
   `todo-n-fixme.md` updates so future audits see the new package.

## Files touched (10)

```
validation/_sanitize.py              # mpq/Decimal/datetime → JSON-clean copy
validation/yaml_validate.py          # validate_yaml_documents(docs, schema)
documents/tab.py                     # revalidate() routes via _sanitize;
                                     # YAML-multi: iterate docs, prefix paths
app/validation_dock.py               # "Attach schema…" / "Reload" / "Open"
                                     # actions in the toolbar overflow menu
state/validation_settings.py         # per-file path recall: read_schema_path /
                                     # write_schema_path / clear_schema_path
README.md                            # +Validation section
ai-memory/repo-map.md                # +§ for validation/, app/validation_dock.py
ai-memory/pros-n-cons.md             # add the feature row, list new tests
ai-memory/todo-n-fixme.md            # close out the planned items; open new
                                     # follow-up: $ref-against-http, draft
                                     # picker, quick fixes
tests/test_validation_yaml.py
tests/test_validation_yaml_multi.py
tests/test_validation_persistence.py
```

## Public API

```python
# validation/yaml_validate.py
def validate_yaml_documents(
    docs: Sequence[Any],
    schema: Mapping[str, Any],
    *,
    max_issues: int = 500,
) -> list[ValidationIssue]:
    """
    For each doc emit issues with instance_path prefixed by a
    synthetic '[doc N]' token; navigation translates that prefix
    into a doc-tab switch (or, for single-doc YAML, drops it).
    """

# validation/_sanitize.py
def to_jsonschema_input(value: Any) -> Any:
    """Recursively replace mpq → float (with warn), Decimal → float,
    datetime → ISO string, bytes → base64 str, gmpy2.mpz → int."""

# state/validation_settings.py
def read_schema_path(doc_path: Path) -> Path | None: ...
def write_schema_path(doc_path: Path, schema_path: Path) -> None: ...
def clear_schema_path(doc_path: Path) -> None: ...
```

## Implementation notes

- **YAML multi**:
  - `JsonTab` already remembers `save_format`; when the format is
    `SAVE_FORMAT_YAML_MULTI`, the tree's root is an array of docs.
  - Validation collapses to: `validate_yaml_documents(docs, schema)`
    where the document container row in the tree is the synthetic
    root.
  - Mapping `("[doc 0]", "a", 1)` → model path
    `(0, row_of_a, 1)` — exactly the existing translator with the
    `[doc N]` prefix consumed first.
- **Sanitisation** keeps datatypes the schema can actually check:
  `mpq("1/3")` → `0.3333333333333333` with a single status-bar
  warning per validation run if any loss happens.
- **Schema picker** dialog:
  - `QFileDialog.getOpenFileName(filter="JSON Schema (*.json *.yaml *.yml);;All files (*)")`;
  - on success, `tab.set_schema(SchemaRef(path=..., inline=None,
    origin="manual"))` + `state.validation_settings.write_schema_path(...)`.
- **Persistence key**: `validation/<sha1(file_path)>` → schema path
  string. Cleared on `Save As` to a new path, like `view_state.discard`.
- Docs:
  - `ai-memory/repo-map.md` gets an extra row in §0 ("Validation /
    schema") and a new §20 covering `validation/`,
    `app/validation_dock.py`, the new model role and theme block;
  - `pros-n-cons.md` adds a "Schema validation" pro and the new
    test count;
  - `todo-n-fixme.md` ticks off the implemented items and opens
    two follow-ups (http $ref resolution, schema-author UX).

## Tests

- `test_validation_yaml.py`: schema is a YAML file, document is YAML;
  inline `$schema: ./my.yaml` works.
- `test_validation_yaml_multi.py`: a 3-doc YAML stream with doc 1
  failing → issue's path resolves to the second top-level row.
- `test_validation_persistence.py`: attach schema → close tab →
  reopen → schema rebinds automatically; "Clear schema" wipes
  the QSettings entry.

## Out of scope (deferred to a follow-up plan)

- Remote `$ref` resolution against http(s).
- Schema-authoring UI / "Draft 7 ↔ 2020-12" picker.
- Per-issue quick-fix actions.
- Validation of partial selections.
- WCAG snapshot tests for the new theme entries
  (`themes/_contrast.py` is already available, but the validation
  colours land in Step 5 without their own accessibility suite).

## Commit message

```
feat(validation): YAML support, multi-doc, schema picker, persistence

- validation.yaml_validate validates each doc of YAML-multi with a
  '[doc N]' prefix that navigation strips on jump
- validation._sanitize coerces mpq/Decimal/datetime/bytes into
  jsonschema-rs-friendly primitives for validation only
- ValidationDock toolbar gains 'Attach schema…' / 'Reload' /
  'Open schema file' / 'Clear schema'
- per-file schema bindings persisted via QSettings sha1-of-path
  keys; cleared on Save As to a new path
- README.md, ai-memory/* updated to reflect the new surface
```
