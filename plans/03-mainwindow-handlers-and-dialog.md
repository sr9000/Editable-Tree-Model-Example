# Step 3 — MainWindow handlers + extracted dialog

_Commit-sized: 4 source files + 1 test file; ~300 LOC (net delete)._

## Scope

Collapse the four MainWindow handlers introduced by the json-schema
plan into thin wrappers around `SchemaRegistry`, and pull the
inline `_AttachDialog` (defined inside `_on_attach_schema_requested`,
`app/main_window.py` L178–213, verified) into its own module.

## Files touched (5)

```
app/main_window.py             # shrink _on_attach / _on_reload / _on_open / _on_go_to
dialogs/attach_schema_dlg.py   # new: extracted _AttachDialog (own widget)
validation/schema_registry.py  # +open_in_browser(SchemaSource), used by handler
tests/test_validation_navigation.py  # update _schema_url_source assertion
tests/test_attach_schema_dialog.py   # new
```

## Current state (verified against `app/main_window.py`)

- `_on_attach_schema_requested` (L160–246): defines a local `_AttachDialog`
  class, hand-rolls URL vs file detection, calls `load_schema_from_url`
  / `load_schema`, finally `tab.set_schema(...)` + `write_schema_ref_str`.
- `_on_reload_schema_requested` (L248–273): re-reads file or URL,
  builds a fresh `SchemaRef`.
- `_on_open_schema_file_requested` (L275–294): `QDesktopServices.openUrl`
  for URLs, `_open_path` for files.
- `_on_go_to_schema_rule_requested` (L296–360): uses
  `widget._schema_url_source` to look up an already-open URL-as-tab.

## After Step 3

- `dialogs/attach_schema_dlg.py` exports `AttachSchemaDialog`
  returning a parsed `SchemaSource | None` (does its own URL/path
  validation + existence check). No business logic in the handler.
- The four handlers shrink to (sketched):

```python
def _on_attach_schema_requested(self) -> None:
    tab = self._current_tab()
    if tab is None:
        return
    source = AttachSchemaDialog.ask(self, start_dir=tab.file_path or "")
    if source is None:
        return
    entry = schema_registry.acquire(source, tab)
    if entry is None:
        self.statusBar.showMessage(self.tr(f"Could not load schema: {source.display}"), 3000)
        return
    tab.set_schema_from_source(source)
    if tab.file_path:
        write_schema_ref_str(Path(tab.file_path), source.key)
    self.statusBar.showMessage(self.tr(f"Schema attached: {source.display}"), 2000)

def _on_reload_schema_requested(self) -> None:
    tab = self._current_tab()
    if tab and tab.schema_source is not None:
        if schema_registry.reload(tab.schema_source) is not None:
            tab.revalidate()
            self.statusBar.showMessage(self.tr("Schema reloaded"), 2000)
```

- `_schema_url_source` attribute is **removed**. The schema-as-tab
  lookup in `_on_go_to_schema_rule_requested` reads
  `widget.schema_source` (None for a non-schema tab). A URL-backed
  schema tab gets `widget.schema_source = SchemaSource.for_url(url)`
  set after `_add_tab`.

## Tests

- `tests/test_attach_schema_dialog.py`: feed a path → returns
  `SchemaSource(kind="file")`; feed `https://…` → returns
  `kind="url"`; feed non-existent path → returns `None`
  (caller surfaces the error).
- `tests/test_validation_navigation.py`: replace the existing
  `assert getattr(schema_tab, "_schema_url_source", None) == schema_url`
  with `assert schema_tab.schema_source.key == schema_url`.

## Out of scope

- Recents (Step 5).
- File watcher (Step 4).
- Dialog UI polish / recents combo (Step 6).

## Commit message

```
refactor(app): MainWindow schema handlers go through SchemaRegistry

- extract AttachSchemaDialog into dialogs/attach_schema_dlg.py
- collapse _on_attach/_on_reload/_on_open/_on_go_to_schema_rule_*
  handlers; load/lookup logic lives in SchemaRegistry now
- drop the ad-hoc _schema_url_source attribute; identity comes
  from JsonTab.schema_source.key
```
