# Responsibility segregation — focused action plan

**Date:** 2026-05-30
**Author:** architecture review (follow-up to `repo_responsibility_segregation_review.md`)
**Method:** read of the *current* tree (not `repo-map.md`, which has drifted), plus
import-graph tracing for every module called out below.
**Status:** plan only — owner-approved decisions baked in (see §6). No code moved yet.

**Approved decisions (2026-05-30):**

- Editor widget packages may be renamed/restructured freely, **but each stays a
  self-hosted, app-agnostic QWidget** (no coupling to `app/`, `documents/`, or
  `tree/`). They are reusable widgets that happen to live in this repo.
- Dialogs: **first extract a `.ui` schema** for each hand-built dialog, **then**
  reorganize into `app/dialogs/` (app workflows) and `editors/windowed/` (value
  editors).
- `model_actions.py`: **delete** and retarget its two tests onto
  `tree_actions/structure.py`.
- Generated UI (`mainwindow.py`, `documents/json_tab_ui.py`): **move to a
  top-level `ui/`** and update the `Makefile` `pyside6-uic` paths.

This report is deliberately **operational**, not strategic. The earlier review
(`repo_responsibility_segregation_review.md`) made the high-level case. This one
names the exact files to move, merge, or delete, with the import evidence behind
each call, so the work can be executed as discrete PRs.

---

## 0. TL;DR — what is actually wrong

The package layout has three concrete segregation failures that you can fix
mechanically:

1. **Loose modules at repo root** that have nothing to do with each other and do
   not belong at top level: `header_view_editor.py`, `model_actions.py`,
   `tree_filter_proxy.py`, `qmultiline_editor.py`, `mainwindow.py`, `settings.py`.
2. **Editor widgets are scattered across 6+ locations** with no separation
   between *inline (in-cell)* editors and *windowed (modal)* editors. The dispatch
   that wires them (`delegates/editor_factory.py`) lives in `delegates/`, which
   should only hold paint/edit delegates.
3. **`documents/` is a 30-module / ~3150-LOC grab bag** mixing composition,
   controllers, passive state, seams, and test-only re-exports.

Plus a small pile of **dead code** to delete outright.

---

## 1. Loose root modules — disposition table

Everything at repo root that is not an entry point (`main.py`) or genuine
project-level config (`settings.py`, `pytest.ini`, `Makefile`, …) is a homing
failure. Evidence is from a full-repo import grep.

| File                    | LOC | Importers (non-test)                             | Verdict                                                      |
|-------------------------|-----|--------------------------------------------------|--------------------------------------------------------------|
| `header_view_editor.py` | 79  | **none** (only self-references)                  | **DELETE** — dead code                                       |
| `model_actions.py`      | 162 | **none** — tests only                            | **DELETE** — retarget tests onto `tree_actions/structure.py` |
| `tree_filter_proxy.py`  | 53  | `documents/states/view_state.py`                 | **MOVE** → `tree/filter_proxy.py`                            |
| `qmultiline_editor.py`  | 280 | `dialogs/qmultiline_dlg.py`                      | **MOVE** → editor-widget package (see §2)                    |
| `mainwindow.py`         | 175 | `app/main_window.py` (generated UI)              | **MOVE** → top-level `ui/` (it is `pyside6-uic` output)      |
| `settings.py`           | 57  | many (`SECRET_*`, `*_LIMIT_*`, `APPLICATION_ID`) | **KEEP/RENAME** → `app_config.py`; strip dead enums (§5)     |

### 1.1 `header_view_editor.py` — delete

`HeaderViewEditorMixin` / `EscapableLineEdit` are referenced **only inside the
file itself**. The `todo-n-fixme.md` entry "decide whether to keep" can be closed:
nothing wires it (the call site was commented out long ago). Delete the file.

### 1.2 `model_actions.py` — delete, retarget tests onto `tree_actions/structure.py`

`model_actions.py` is a **parallel, test-only implementation** of structural row
operations (`action_insert_row_*`, `action_duplicate`, `action_move_up/down`,
`action_sort_keys`, `action_insert_child`). The real app path is
`tree_actions/structure.py` (628 LOC) routed through the undo system. The only
importers are `tests/test_tree_actions_structure.py` and
`tests/test_tree_correctness.py`.

**Decision:** delete the module. Rewrite the two tests to assert the same
behaviours against `tree_actions/structure.py` (the real, undo-routed path), so the
structural logic lives in exactly one place. Before deletion, confirm
`structure.py` covers each behaviour the tests check (insert-before/after,
duplicate-with-rename, move-up across parent boundary, recursive sort, insert-child);
fill any genuine gap in `structure.py` rather than reviving the root module.

### 1.3 `tree_filter_proxy.py` — move into `tree/`

`TreeFilterProxy(QSortFilterProxyModel)` is a Qt **model adapter** that depends on
`tree.model.JsonTreeModel` and `tree.types`. It is consumed by
`documents/states/view_state.py`. It belongs beside the model it filters:
`tree/filter_proxy.py`. This matches the review's "tree domain vs Qt adapter"
direction — it is squarely a Qt adapter.

---

## 2. Editor widgets — collect windowed together, separate from inline

This is the largest segregation win and the one explicitly requested. Today the
value-editor widgets are spread across **six** locations with no inline/windowed
distinction:

| Location                                   | What it holds                                  | Inline / Windowed  |
|--------------------------------------------|------------------------------------------------|--------------------|
| `qbigint_spinbox/__init__.py` (271)        | `QBigIntSpinBox`                               | inline             |
| `qmpq_spinbox/__init__.py` (295)           | `QMpqSpinBox`                                  | inline             |
| `datetime_editor/` (784)                   | `BetterDateTimeEditor` + validator/regex/enums | inline             |
| `delegates/number_affix_delegate.py` (153) | `AffixCompositeEditor`                         | inline             |
| `delegates/editor_factory.py` (485)        | `_SecretLineEdit`, plus **all dispatch**       | inline + dispatch  |
| `delegates/base.py`                        | `_CapsLockSafeLineEdit`                        | inline             |
| `qmultiline_editor.py` (280, root)         | `QMultilineEditor` widget                      | windowed (content) |
| `qhexedit/` (1745)                         | hex-editor widget + chunks/commands/colors     | windowed (content) |
| `dialogs/qmultiline_dlg.py` (126)          | `QMultilineDialog` wrapper                     | **windowed**       |
| `dialogs/qhexedit_dlg.py` (137)            | `QHexDialog` wrapper                           | **windowed**       |

`delegates/editor_factory.py::create_value_editor` is the dispatcher. Tracing its
`match item.json_type` shows the inline/windowed split cleanly:

- **Inline (returns a widget, edits in the cell):** affix composite, `QBigIntSpinBox`
  (INTEGER), `QMpqSpinBox` (FLOAT/PERCENT), `QComboBox` (BOOLEAN), `_CapsLockSafeLineEdit`
  (text line family), `_SecretLineEdit` (SECRET_LINE), `BetterDateTimeEditor`
  (DATE/TIME/DATETIME…).
- **Windowed (opens a modal, returns `None`):** `QMultilineDialog`
  (MULTILINE/TEXT and SECRET_TEXT), `QColorDialog` (COLOR_RGB/RGBA),
  `QHexDialog` (BYTES/ZLIB/GZIP).

### 2.1 Target layout

Introduce an `editors/` package that owns *value-editing widgets only*, split by
interaction model, and move the dispatcher out of `delegates/`:

```text
editors/
  __init__.py
  factory.py                 # was delegates/editor_factory.py (dispatch + set/get data)
  context.py                 # EditorContextProtocol (currently inline in factory)
  inline/
    bigint_spinbox.py        # was qbigint_spinbox/
    mpq_spinbox.py           # was qmpq_spinbox/
    datetime/                # was datetime_editor/  (better_dt_editor, validator, regex, enums)
    affix_composite.py       # was delegates/number_affix_delegate.py (editor part)
    secret_line.py           # _SecretLineEdit (extracted from editor_factory)
    caps_safe_line.py        # _CapsLockSafeLineEdit (extracted from delegates/base)
  windowed/
    multiline_widget.py      # was qmultiline_editor.py (root)
    multiline_dialog.py      # was dialogs/qmultiline_dlg.py
    hexedit/                 # was qhexedit/ (widget + chunks/commands/color_manager)
    hex_dialog.py            # was dialogs/qhexedit_dlg.py
    color_dialog.py          # thin QColorDialog wiring lifted out of factory.py
```

Then `delegates/` is left with **only** delegate responsibilities:

```text
delegates/
  name_delegate.py
  type_delegate.py
  value.py                   # ValueDelegate: paint + createEditor → editors.factory
  base.py                    # delegate base only (line-edit moves to editors/inline)
  formatting/                # value_formatting, bytes_codec, color_codec  (pure helpers)
  validation_badge.py        # presentation helper
  edit_context.py            # delegate-side edit context
```

### 2.2 Why this is the right cut

- `qbigint_spinbox`, `qmpq_spinbox`, `qhexedit`, `datetime_editor`, `qmultiline_editor`
  are advertised in `pros-n-cons.md` as "independently useful packages." Under
  `editors/inline/*` and `editors/windowed/*` they **stay self-hosted,
  app-agnostic QWidgets** — the binding rule (approved) is that nothing under
  `editors/` may import from `app/`, `documents/`, or `tree/`. The grouping makes
  the inline/windowed contract explicit instead of implicit in a `match` statement,
  while preserving each widget's reusability.
- It removes the **two responsibilities currently fused in `delegates/`**: delegates
  (paint + when-to-edit) vs editors (the widgets themselves). Right now
  `editor_factory.py` (485 LOC) constructs every widget *and* defines
  `_SecretLineEdit` *and* owns set/getEditorData dispatch — that is an editors
  concern living in the delegates package.
- The factory/context (`editors/factory.py`, `editors/context.py`) is the **only**
  seam allowed to know about the host: it takes an `EditorContextProtocol`. The
  concrete widgets stay context-free, so the "self-hosted QWidget" rule holds even
  for the dispatcher's collaborators.
- `dialogs/` then keeps only **application dialogs** (`attach_schema_dlg.py`,
  `secret_prefixes_dlg.py`) — not value editors. Those two are window-level
  workflows, conceptually closer to `app/` than to cell editing (see §6 decision 1).

### 2.3 Migration notes

1. **Extract `.ui` first (approved).** The dialog wrappers
   (`qmultiline_dlg.py`, `qhexedit_dlg.py`, and the app dialogs
   `attach_schema_dlg.py`, `secret_prefixes_dlg.py`) currently build their layouts
   in hand-written Python. Before relocating, extract a Qt Designer `.ui` schema for
   each and regenerate via `pyside6-uic` (same pipeline as `mainwindow.ui` /
   `json_tab.ui`). Only after the `.ui` split should the wrappers move to
   `app/dialogs/` or `editors/windowed/`. This keeps layout declarative and
   consistent with the rest of the app.
2. **Split fat `__init__.py` files.** The widget packages put **all** code in
   `__init__.py` (271 / 295 / 1130 lines). When moving them under
   `editors/inline` / `editors/windowed`, also split those files into named modules
   (`spinbox.py`, `validator.py`, …). A 1130-line widget buried in
   `qhexedit/__init__.py` is its own segregation smell.
3. **Free to rename (approved).** Because these are app-internal-in-this-repo but
   self-hosted, internal symbol/file names may be modernized freely; there is no
   external import-name contract to preserve.

---

## 3. `documents/` — split the grab bag

`documents/` is 30 modules / ~3150 LOC. It mixes five distinct roles. Proposed
sub-package split (no behaviour change, pure relocation):

```text
documents/
  tab.py                     # thin QWidget facade (keep)
  composition/
    init.py                  # tab_init.bootstrap
    setup.py                 # tab_setup
    factory.py               # tab_factory
    dependencies.py          # tab_dependencies (JsonTabHost / JsonTabServices)
    marker.py                # tab_marker
    demo_data.py             # tab_demo_data
  controllers/
    appearance.py            # tab_appearance
    navigation.py            # tab_navigation
    editability.py           # tab_editability
    validation.py            # tab_validation
    validation_view.py       # tab_validation_view (if still present)
    history.py               # tab_history
    view.py                  # view_controller
    status.py                # tab_status
  states/                    # (already exists) io / view / editing
  seams/
    mutation_gateway.py
    document_protocol.py
  # json_tab_ui.py (generated UI) moves to top-level ui/ (approved, §1 / §6)
```

### 3.1 Kill the test-only re-exports in `tab.py`

`documents/tab.py` lines 27–34 re-export eight private undo command classes
(`_ChangeTypeCmd`, `_EditValueCmd`, … `_MoveRowsCmd`) **purely so tests can import
them from `documents.tab`**. This couples the tab facade to undo internals for no
runtime reason. Migrate those tests to `from undo.commands import …` and delete the
re-export block. This is the single clearest "documents is a convenience namespace,
not a boundary" smell.

### 3.2 `EditingController` is still a forwarding façade

`documents/states/editing_controller.py` (199 LOC) is ~30 one-line methods that
forward to four real collaborators it constructs:

- `MoveViewState` (move/expand state)
- `InlineEditController` (inline edit lifecycle)
- `CommandDispatcher` (undo command construction, 356 LOC)
- `DiffApplier` (surgical replay)

Recommendation: stop forwarding. Expose the collaborators as named properties
(`editing.commands`, `editing.inline`, `editing.move`, `editing.diff`) and let
callers use them directly. The façade currently hides which sub-service owns each
operation — the exact "bucket of forwarded methods" the prior review flagged.

---

## 4. `tree/` and `tree_actions/` — minor homing

- After §1.3, `tree/filter_proxy.py` joins `tree/model.py`, `tree/view.py` — the Qt
  adapter trio now lives together.
- After §1.2, `tree_actions/` becomes the **single** home for structural row
  operations (no parallel `model_actions.py` at root).

No deeper `tree/` domain-vs-Qt split is proposed here — that is the larger redesign
the prior review (its §5.5) already covers and should stay a separate effort.

---

## 5. Dead / unwired code to delete

| Item                                                                      | Evidence                                                    | Action                                                                                                   |
|---------------------------------------------------------------------------|-------------------------------------------------------------|----------------------------------------------------------------------------------------------------------|
| `header_view_editor.py` (whole file)                                      | no importers                                                | delete                                                                                                   |
| `settings.IntegerInfo` / `FloatInfo` / `MultiLineInfo` / `SingleLineInfo` | defined, **zero references** repo-wide                      | delete or wire (these look like stubs for the "numeric/multiline preview" wishlist in `todo-n-fixme.md`) |
| `documents/tab_demo_data.py` legacy seed                                  | `todo-n-fixme.md` line 99; only bare-`JsonTab()` test paths | delete once those tests pass explicit `data=`                                                            |
| `model_actions.py` (whole file)                                           | test-only                                                   | delete after §1.2                                                                                        |

---

## 6. Resolved decisions (2026-05-30)

These were open questions; the owner has decided:

1. **`dialogs/` split — approved with a prerequisite.** First extract a `.ui`
   schema for each hand-built dialog (see §2.3.1). Then: `attach_schema_dlg.py` and
   `secret_prefixes_dlg.py` → `app/dialogs/`; `qmultiline_dlg.py` and
   `qhexedit_dlg.py` → `editors/windowed/`.
2. **`editors/` packaging — rename freely, stay self-hosted.** Restructure the
   widget packages as needed, but enforce the rule that nothing under `editors/`
   imports from `app/`, `documents/`, or `tree/`; each editor is an independent,
   reusable QWidget (see §2.2).
3. **Generated UI — move to top-level `ui/`.** Relocate `mainwindow.py` and
   `documents/json_tab_ui.py` (and their `.ui` sources) under `ui/`, and update the
   `Makefile` `pyside6-uic` generation paths.
4. **`model_actions.py` — delete + retarget tests** onto
   `tree_actions/structure.py` (see §1.2).
5. **Scope — report only for now.** No code is moved until this plan is reviewed.

### Still to confirm

- **`settings.py` rename** to `app_config.py`. Recommended (it currently reads like
  a sibling of the `state/` *preferences* package, but holds app constants/IDs).
  Deferred — costs ~10 test-import updates; left as the author's recommendation, not
  a decision.

---

## 7. Recommended execution order (low risk → high)

1. **Delete dead code** — `header_view_editor.py`, the four `settings` enums.
   (Zero runtime risk.)
2. **Home the single-purpose modules** — `tree_filter_proxy.py` → `tree/filter_proxy.py`;
   **delete** `model_actions.py` and retarget its two tests onto
   `tree_actions/structure.py`.
3. **Extract `.ui` schemas** for the four hand-built dialogs; regenerate via
   `pyside6-uic`. (Prerequisite for step 5.)
4. **Move generated UI to top-level `ui/`** — `mainwindow.py`, `json_tab_ui.py`,
   their `.ui` sources, and the `Makefile` paths.
5. **Carve `editors/`** — move widget packages + dialog editors (now `.ui`-backed);
   lift the dispatcher out of `delegates/`; enforce the no-`app`/`documents`/`tree`
   import rule; split fat `__init__.py` files; relocate app dialogs to `app/dialogs/`.
6. **Kill `documents/tab.py` undo re-exports** — migrate test imports to `undo.commands`.
7. **Split `documents/` into composition / controllers / states / seams.**
8. **De-façade `EditingController`** — expose collaborators, drop pass-throughs.

Each step is independently shippable and gated by `make test` (the suite is the
safety net for these pure relocations).
