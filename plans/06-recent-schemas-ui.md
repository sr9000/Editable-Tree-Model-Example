# Step 6 — Recent schemas UI (dialog combo + dock submenu)

_Commit-sized: 4 source files + 2 test files; ~300 LOC._

## Scope

Surface the recents from Step 5 in two places:

1. The `AttachSchemaDialog` (created in Step 3) — a "Recent schemas"
   combo above the existing path/URL line edit.
2. The dock's `Schema ▸` button (defined in `app/validation_dock.py`
   L71–83, verified) — a new "Recent ▸" submenu listing the top 8.

## Files touched (6)

```
dialogs/attach_schema_dlg.py            # +recents combo, prefills line edit
app/validation_dock.py                  # +Recent ▸ submenu, attachRecentSchemaRequested signal
app/main_window.py                      # connect new signal → set_schema_from_source
validation/schema_registry.py           # +exists(SchemaSource) used to grey out missing files
tests/test_validation_recent_schemas_ui.py   # new
tests/test_attach_schema_dialog.py      # extend with recents combo cases
```

## Behaviour spec

- Dock submenu shows up to 8 most-recent entries:
  - `📂 schema.json` for `kind="file"`, dimmed (action disabled) when
    the file no longer exists;
  - `🌐 example.com/foo.json` for `kind="url"`;
  - `<empty>` placeholder action (disabled) when the list is empty.
- Clicking an entry emits `attachRecentSchemaRequested(SchemaSource)`;
  the MainWindow handler calls `tab.set_schema_from_source(source)`,
  then `write_schema_ref_str` like the manual attach path.
- The Attach dialog's combo shows the same entries, sorted MRU-first;
  selecting an entry fills the line edit (user can still edit before
  pressing OK). Empty combo state hides the row entirely.
- `AttachSchemaDialog.ask()` returns the user-selected `SchemaSource`,
  not the combo entry directly — the line edit remains the source of
  truth so the user can tweak a path before accepting.

## Tests

- `tests/test_validation_recent_schemas_ui.py` (qtbot):
  - seed `state.recent_schemas` with two entries (one file, one URL);
  - open the dock's `Schema ▸ Recent ▸` menu and assert action labels
    and enabled state;
  - simulate a click on the URL entry → assert
    `attachRecentSchemaRequested` emitted with the right
    `SchemaSource` and `tab.schema_source` updated.
- `tests/test_attach_schema_dialog.py` (extend):
  - combo populated from `state.recent_schemas`;
  - selecting a combo row prefills the line edit;
  - empty recents → combo row hidden.

## Out of scope

- Pinning / favouriting entries.
- Per-document recents (the existing per-doc binding in
  `state/validation_settings.py` already covers automatic reattach).

## Commit message

```
feat(ui): recent schemas picker in dock menu and attach dialog

- ValidationDock gains a "Recent ▸" submenu under Schema ▸ with
  📄/🌐 icons; emits attachRecentSchemaRequested(SchemaSource)
- AttachSchemaDialog gains a recents combo that prefills the path
  field while keeping the line edit authoritative
- MainWindow wires both surfaces to tab.set_schema_from_source
```
