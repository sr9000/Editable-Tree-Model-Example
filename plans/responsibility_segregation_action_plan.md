# Responsibility segregation — focused action plan

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

## 0.5 Progress snapshot (reviewed 2026-06-01)

Branch `strict-responsibility-segregation`. Gates at review time:
`pytest` = **1124 passed (18.5s)**, `make check-no-reflection` green, tree clean.

| Step (§7)                             | Status         | Notes                                                                                                                            |
|---------------------------------------|----------------|----------------------------------------------------------------------------------------------------------------------------------|
| 1. Delete dead code                   | ✅ **done**     | `header_view_editor.py` + 4 `settings` enums gone.                                                                               |
| 2. Home single-purpose modules        | ✅ **done**     | `tree/filter_proxy.py`; `model_actions.py` deleted, 2 tests retargeted onto `structure.py` (+168 LOC).                           |
| 3. Extract `.ui` schemas              | ✅ **done**     | 4 dialogs now `.ui`-backed under `ui/dialogs/`.                                                                                  |
| 4. Move generated UI to `ui/`         | ✅ **done**     | `mainwindow.*`, `json_tab*` moved; Makefile `pyside6-uic` paths updated.                                                         |
| 5. Carve `editors/`                   | 🟡 **partial** | Relocation + dispatcher move done; **symbol extractions, fat-`__init__` split, and the isolation rule are NOT done** (see §2.4). |
| 6. Kill `documents/tab.py` re-exports | ⬜ **todo**     | 8 `from undo.commands import _…` re-exports still in `tab.py` (lines 27–34).                                                     |
| 7. Split `documents/`                 | ⬜ **todo**     | See §3 (partially overtaken — `json_tab_ui.py` already in `ui/`).                                                                |
| 8. De-façade `EditingController`      | ⬜ **todo**     | Collaborators already extracted by commits T1–T6; only the 199-LOC forwarding shell remains (see §3.2).                          |

**Net:** Part 1 (§1 + §5 dead code) is complete. Part 2 (§2 editors) is at the
"relocation complete, refactor incomplete" stage — the directory tree exists but
the per-symbol extractions, the `__init__.py` splits, and the binding isolation
rule remain open (tracked in the new §2.4 closeout checklist).

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

  > **Rule clarification (2026-06-01).** The blanket "no `app`/`documents`/`tree`
  > imports" wording is too strong for `editors/factory.py`, which **must** read
  > `tree.types.JsonType` / `tree.item.JsonTreeItem` to dispatch. The rule is
  > therefore scoped as:
  > - **Concrete widgets** (`inline/*`, `windowed/*`) — **zero** imports from
      > `app/`, `documents/`, `tree/`. This is the reusability contract.
  > - **`editors/factory.py` + `editors/context.py`** — the single dispatch seam —
      > **may** import `tree.types` / `tree.item` for type dispatch, but still **never**
      > `app/` or `documents/` (host access goes through `EditorContextProtocol`).
  >
  > Two current violations must be fixed before §7 step 5 can be marked done:
  > 1. `editors/windowed/hexedit/chunks.py` imports `app.runtime_compat.qba_to_bytes`
       > — vendor that helper into `editors/` (it is a pure `QByteArray→bytes` shim).
  > 2. `editors/factory.py` imports `tree.*` — allowed under the scoped rule above,
       > but the concrete-widget files must be audited to confirm none do.

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

### 2.4 §7-step-5 closeout checklist (what "carve `editors/`" still needs)

Relocation landed (commits `f4c69f9`…`58a9244`, `8159a4c`, `7dbda11`, `a0b79b4`),
but the following sub-tasks from §2.1 / §2.3 are **still open**. Step 5 is **not**
done until every box is checked and the gate in §2.5 passes.

- [ ] **Extract `editors/context.py`** — move `EditorContextProtocol` (currently
  inline in `factory.py`, ~line 55) into its own module; `factory.py` imports it.
- [ ] **Extract `editors/inline/secret_line.py`** — move `_SecretLineEdit`
  (`factory.py` ~line 77) and its watcher out of the dispatcher.
- [ ] **Extract `editors/inline/caps_safe_line.py`** — move `_CapsLockSafeLineEdit`
  out of `delegates/base.py` (it is an editor widget, not a delegate).
- [ ] **Extract `editors/inline/affix_composite.py`** — move `AffixCompositeEditor`
  out of `delegates/number_affix_delegate.py` (leave the pure affix helpers
  —`is_affix_json_type`, `kind_for_json_type`, …— wherever the delegate needs them).
- [ ] **Extract `editors/windowed/color_dialog.py`** — lift the `QColorDialog`
  wiring out of `factory.py`.
- [ ] **Split fat `__init__.py`** (§2.3.2) — `inline/bigint_spinbox/__init__.py`
  (271), `inline/mpq_spinbox/__init__.py` (295), `windowed/hexedit/__init__.py`
  (1130) into named modules (`spinbox.py`, `validator.py`, `chunks.py` is already
  split, etc.). A 1130-line `__init__.py` is itself the segregation smell.
- [ ] **Create `delegates/formatting/`** (§2.1 target) — group `value_formatting.py`,
  `bytes_codec.py`, `color_codec.py` as pure helpers so `delegates/` is delegate
  logic + a formatting helper package only.
- [ ] **Fix isolation violations** — vendor `qba_to_bytes` into `editors/` (remove the
  `app.runtime_compat` import in `windowed/hexedit/chunks.py`); audit concrete
  widgets for any `app`/`documents`/`tree` imports.

### 2.5 Gate / DoD for `editors/` (§7 step 5)

- **Acceptance:** every box in §2.4 checked; `delegates/` contains only delegate
  modules + `formatting/`; no concrete editor widget imports `app`/`documents`/`tree`.
- **Enforcement gate (new):** add a `check-editors-isolation` target to the
  `Makefile` (and wire it into `gate`) that fails if any file under
  `editors/inline/` or `editors/windowed/` imports `app`, `documents`, or `tree`,
  and if any file under `editors/` imports `app` or `documents`. Mirror it in
  `.githooks/pre-commit-ci` so it runs per-commit like `check-no-reflection`.
- **Test gate:** `make gate` green (lint → reflection → editors-isolation → tests),
  1124+ tests still passing.

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
  # json_tab_ui.py — ALREADY moved to top-level ui/ (§7 step 4 done); listed here
  # only as a reminder that no generated UI remains under documents/.
```

### 3.1 Kill the test-only re-exports in `tab.py`

`documents/tab.py` lines 27–34 re-export eight private undo command classes
(`_ChangeTypeCmd`, `_EditValueCmd`, … `_MoveRowsCmd`) **purely so tests can import
them from `documents.tab`**. This couples the tab facade to undo internals for no
runtime reason. Migrate those tests to `from undo.commands import …` and delete the
re-export block. This is the single clearest "documents is a convenience namespace,
not a boundary" smell.

**Status (2026-06-01):** still present — `documents/tab.py` lines 27–34 import 8
`_*Cmd` classes with `# noqa: F401 — re-exported for test imports`.

**DoD / gate:** the re-export block is deleted; `grep -rn "from documents.tab import _"
tests/` returns nothing; affected tests import from `undo.commands`; `make gate` green.

### 3.2 `EditingController` is still a forwarding façade

> **Update (2026-06-01).** The collaborators have **already been extracted** (commits
> `T1`–`T6`, now on `master`) into `documents/states/editing/`:
> `command_dispatcher.py` (356), `inline_edit_controller.py` (97),
> `move_view_state.py` (188), `tree_actions.py` (53), `context.py` (16). What remains
> is the **199-LOC forwarding shell** `documents/states/editing_controller.py`. So
> this step is now purely "stop forwarding," not "extract collaborators."

`documents/states/editing_controller.py` (199 LOC) is ~30 one-line methods that
forward to the collaborators it constructs:

- `MoveViewState` (`move_view_state.py` — move/expand state)
- `InlineEditController` (`inline_edit_controller.py` — inline edit lifecycle)
- `CommandDispatcher` (`command_dispatcher.py` — undo command construction, 356 LOC;
  owns the `DiffApplier` surgical-replay path)
- `TreeActionController` (`tree_actions.py`) and the shared `EditingContext` (`context.py`)

Recommendation: stop forwarding. Expose the collaborators as named properties
(`editing.commands`, `editing.inline`, `editing.move`, `editing.actions`) and let
callers use them directly. The façade currently hides which sub-service owns each
operation — the exact "bucket of forwarded methods" the prior review flagged.

**DoD / gate:** `editing_controller.py` exposes the collaborators as properties and
holds **no** pass-through one-liners; every former forwarder call site updated to the
property path; `grep` shows no `editing\.<verb>` forwarders remain; `make gate` green.


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

Status legend: ✅ done · 🟡 partial · ⬜ todo. Every step is gated by `make gate`
(lint → reflection → tests; plus `check-editors-isolation` once §2.5 lands).

1. ✅ **Delete dead code** — `header_view_editor.py`, the four `settings` enums.
   *DoD:* files gone, no importers, gate green. **(done — commit `4093ba6`)**
2. ✅ **Home the single-purpose modules** — `tree_filter_proxy.py` →
   `tree/filter_proxy.py`; **deleted** `model_actions.py` and retargeted its two
   tests onto `tree_actions/structure.py`.
   *DoD:* `structure.py` covers insert-before/after, duplicate-with-rename,
   move-up across parent boundary, recursive sort, insert-child; gate green.
   **(done — commit `4093ba6`, `structure.py` +168 LOC)**
3. ✅ **Extract `.ui` schemas** for the four hand-built dialogs; regenerate via
   `pyside6-uic`. *DoD:* each dialog `.ui`-backed; gate green. **(done — `f2cc12a`)**
4. ✅ **Move generated UI to top-level `ui/`** — `mainwindow.*`, `json_tab*`, their
   `.ui` sources, and Makefile paths. *DoD:* nothing generated left at root or under
   `documents/`; `make ui` regenerates in place; gate green. **(done — `9aad897`)**
5. 🟡 **Carve `editors/`** — relocation landed; **finish the §2.4 checklist** (extract
   `context`/`secret_line`/`caps_safe_line`/`affix_composite`/`color_dialog`, split the
   fat `__init__.py` files, create `delegates/formatting/`, fix the isolation
   violations). *DoD/gate:* see **§2.4 + §2.5** (incl. the new `check-editors-isolation`
   gate). **(partial — directory tree done; symbol extraction + isolation pending)**
6. ⬜ **Kill `documents/tab.py` undo re-exports** — migrate test imports to
   `undo.commands`. *DoD/gate:* see **§3.1**.
7. ⬜ **Split `documents/` into composition / controllers / states / seams.**
   *Note:* `json_tab_ui.py` already moved (step 4). *DoD:* `tab.py` stays a thin
   facade; each former `tab_*.py` lands in exactly one sub-package; no module imports
   its old path; repo-map updated; gate green.
8. ⬜ **De-façade `EditingController`** — collaborators already extracted (T1–T6);
   expose them as properties and drop the pass-throughs. *DoD/gate:* see **§3.2**.

Each step is independently shippable and gated by `make gate` (the suite is the
safety net for these pure relocations).
