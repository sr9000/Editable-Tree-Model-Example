# Step 9 — Move-mechanics redesign + multi-action semantics

_Status: **design / pause**. Drag-and-drop steps 06–08 are paused until
this lands. No code changes in this commit — research output only._

## 0) TL;DR

The current move mechanics are correct on the *happy path* but
**fragile**: three independent code paths in
`tree_actions/structure.py` each do their own pre-pop / post-pop
arithmetic on row numbers, the multi-parent fallback re-uses
stale `idx.row()` snapshots across in-flight mutations, and the
`_MoveRowsCmd` couples model internals, view selection, and
row-index arithmetic into a single class.

**Proposed direction**: collapse all move math behind one primitive
— *anchor-based move* — and define a small, orthogonal vocabulary
for multi-action behaviour (copy / paste / insert).

| Concept       | New primitive                                      | Replaces                                                   |
| ------------- | -------------------------------------------------- | ---------------------------------------------------------- |
| Move          | `Move(items, gap_anchor)`                          | `_move_same_parent` + `_multi_parent_common_grandparent_move` + `_move_multi_parent_fallback` + pre-pop math in callers |
| Copy          | `collect_clipboard_entries(rows, mode=AUTO)`       | `top_level_source_rows` + ad-hoc text payload builders     |
| Paste         | `paste_clones_at_targets(targets, entries)`        | `paste_from_clipboard` looping once on `currentIndex`      |
| Insert (1:1)  | `paste_zip_at_targets(targets, entries)`           | (new, no current equivalent)                               |

---

## 1) Audit of the existing move pipeline

### 1.1 Three callers, one command, four sets of row-math

```
Alt+Up / Alt+Down         drag-drop (future)
        │                       │
        ▼                       ▼
move_selection_up/down ───► _move_selection_with_tab ────┐
                                                         │
       ┌──────────────────────┬─────────────────────────┐│
       ▼                      ▼                         ▼▼
_move_same_parent   _multi_parent_common_grandparent_move   _move_multi_parent_fallback
       │                      │                                     │
       │                      │           macro of N independent ops│
       └──────────┬───────────┴────────────────────────┬────────────┘
                  ▼                                    ▼
         tab.push_move_rows(sources, t_parent, target_row, label=…)
                                    │
                                    ▼
                            _MoveRowsCmd(sources_paths, target_path, target_row)
```

Each red node converts "user intent" (block up by one / promote to
grandparent / drop here) into a **pre-pop integer `target_row`**.
That convention is Qt-native but is reinvented at every level:

| Caller                                       | Formula for `target_row` (pre-pop)                                  |
| -------------------------------------------- | ------------------------------------------------------------------- |
| `_move_same_parent` up (interior)            | `min_row - 1`                                                       |
| `_move_same_parent` up (bubble out)          | `parent_row` (in grandparent)                                       |
| `_move_same_parent` down (interior)          | `max_row + 2` (the *+2* is "skip one row, add one for pre-pop")     |
| `_move_same_parent` down (bubble out)        | `parent_row + 1` (in grandparent)                                   |
| `_multi_parent_common_grandparent_move` up   | `min(parent.row() for parent in selected-parents)`                  |
| `_multi_parent_common_grandparent_move` down | `max(parent.row()) + 1`                                             |
| `_move_multi_parent_fallback` up             | `source_row - 1`                                                    |
| `_move_multi_parent_fallback` down           | `source_row + 2`                                                    |
| `push_move_row` (single)                     | `dst + 1 if src < dst else dst`                                     |
| Paste / Duplicate                            | post-pop `row + 1` (different convention entirely)                  |

That table is the bug surface.

### 1.2 Concrete defects

#### Bug A — multi-parent fallback uses stale `source_row` values

`_move_multi_parent_fallback` computes `operations` *up front* from
`idx.row()`, then plays them inside a macro that mutates the model
between iterations:

```python
for idx in ordered:                       # ←  ordered = original indexes
    source_row = idx.row()                # ←  captured before any move
    ...
    operations.append((parent_path, source_row, target_row))

# later, inside the macro:
for parent_path, source_row, target_row in operations:
    source_idx = model.index(source_row, 0, parent)  # ← may be stale
```

For a selection like `[P/3, P/5, Q/2]` (two parents, two of them
under the same parent `P`):

1. First op moves `P/3` → `P/2`. After this, `P`'s former row 5 has
   shifted to row 4.
2. Second op asks for `model.index(5, 0, P)`. If `P` had exactly 6
   children, that row is now invalid (only rows 0..4 exist), and the
   command no-ops silently.
3. Even when not out-of-range, the *wrong* item is moved.

This is the bug the user is hitting. Reproduction:

```yaml
# data.yaml
top:
  - a
  - b
  - c
  - d
  - e
  - f
other: 1
```

Select `top[2]`, `top[4]`, `other`. Alt+Up. Observed: only the first
move lands cleanly; the second moves the wrong sibling. Expected:
each row moves up by one (or the operation is rejected with a clear
status message).

#### Bug B — `_move_multi_parent_fallback` re-selection math is hand-tuned

```python
# For a same-parent move, pre-pop target_row adjusts:
# up: source > target so no adjustment → lands at target_row
# down: source < target so adjustment subtracts 1 → lands at target_row - 1
dest = target_row if up else target_row - 1
```

This is the same pre-pop ↔ post-pop conversion repeated again, here
for the *selection restore* side. Any future change to
`_MoveRowsCmd` semantics has to update *both* sides in lockstep.

#### Bug C — `_MoveRowsCmd.redo` calls `_select_placed_rows` directly

The command writes to the view's `selectionModel` from inside
`redo()`. That:

- couples a `QUndoCommand` to a `QTreeView`,
- is invoked during *redo of an already-applied move* (e.g. when a
  user undo-redos through history), at which point the view may have
  been disposed (multi-tab close, headless test that drove a macro
  manually),
- means tests that assert the command's row math have to spin up a
  full `JsonTab` with a real view.

Selection restoration belongs in an **action-layer post-hook**, not
in the undo command.

#### Bug D — no idempotency / no-op guard in `push_move_rows`

```python
tab.push_move_rows([idx], idx.parent(), idx.row() + 1, ...)
# = move row to immediately-after-itself = pre-pop adj = no movement
```

still pushes a command and dirties the document. The same is true
of `Alt+Up` on row 0 of a top-level row inside a multi-selection
where every other row also can't move — the fallback silently does
nothing for some rows but still pushes a (potentially empty) macro.

#### Bug E — `_MoveRowsCmd` cycle-guard is in `push_move_rows`, not in the command

The check `target_parent_path[:len(sp)] == sp` lives outside the
command. A future caller (e.g. drag-drop's `dropMimeData`) that
forgets to call `push_move_rows` and instantiates `_MoveRowsCmd`
directly will skip the cycle guard.

#### Bug F — `child_items.insert(ins_row, item)` clamps out-of-range

`_MoveRowsCmd.redo` ends with `t_parent_item.child_items.insert(...)`.
Python's `list.insert` clamps; an out-of-range `target_row` produces
no error, just lands the item at the end. Silent drift if a caller
passes a bad row.

#### Bug G — `_unique_child_name` / name-collision in cross-parent move

Cross-parent move of an OBJECT child into another OBJECT can collide
on key names. `_MoveRowsCmd` does not rename — it just transplants
the `JsonTreeItem` carrying its existing `name`. Two children with
the same key are now possible until the user notices. (`to_json()`
will raise on save, so it's surfaced eventually, but late.)

### 1.3 What's correct and should be preserved

- Identity preservation: move keeps the same `JsonTreeItem` instance,
  so view expansion of subtrees survives. **This is the key
  invariant** that distinguishes move from cut+paste.
- Path-based addressing in the command — `_index_path` snapshots
  before redo, so the command tolerates view/proxy rebuilds.
- Cycle guard exists at all.
- Descending source order during pop, ascending re-insert — correct
  Qt convention.

---

## 2) Proposed primitive — anchor-based move

### 2.1 Anchor descriptor

```python
@dataclass(frozen=True)
class MoveAnchor:
    parent_path: tuple[int, ...]
    # exactly one of these is set:
    before_sibling_path: tuple[int, ...] | None = None
    after_sibling_path:  tuple[int, ...] | None = None
    at_end: bool = False    # append as last child
    at_start: bool = False  # prepend as first child
```

An anchor names a **gap** in the destination parent by reference
to a *non-moving* sibling (or "first" / "last" sentinels), not by
integer row number. This makes the anchor stable under any number
of removals: the named sibling either still exists at some row, or
the sentinel still describes "first / last".

### 2.2 The single move primitive

```python
def move_items(
    model: JsonTreeModel,
    sources: list[tuple[parent_path, row]],   # snapshot of source positions
    anchor: MoveAnchor,
    *,
    rename_on_collision: bool = True,         # OBJECT-parent safety
) -> list[tuple[parent_path, row]]:
    """
    Detach every (parent_path, row) item, then re-insert in
    source-order at the gap described by *anchor*. Returns
    the final (parent_path, row) of every placed item.
    """
```

All row arithmetic lives *inside* this function. Callers never
compute pre-pop targets. The function:

1. Resolves `sources` to live `JsonTreeItem` references *before*
   any mutation.
2. Resolves the anchor's reference sibling to a live `JsonTreeItem`
   too (so it survives removals of *other* siblings).
3. Detaches items in descending `(parent_path, row)` order.
4. Re-computes the anchor's row by looking at the destination
   parent's `child_items` and finding the reference sibling
   (or using the `at_start` / `at_end` sentinel).
5. Re-attaches items in ascending source order at the resolved row.
6. Resolves OBJECT name collisions via `_unique_child_name`
   (with `rename_on_collision`).

This eliminates Bugs **A, B, D, F, G** by construction. There is
nothing for callers to get wrong — they describe *where* the
items should go, not what integer index to pass.

### 2.3 New `_MoveRowsCmd`

```python
class _MoveRowsCmd(QUndoCommand):
    def __init__(self, tab, label, sources, anchor):
        ...
        self._sources = sources             # snapshot before redo
        self._anchor  = anchor
        self._placed: list[...] | None = None
        self._renames: dict[id, str] | None = None  # for undo-on-collision

    def redo(self):
        self._placed = move_items(self._tab.model, self._sources, self._anchor)

    def undo(self):
        # Inverse anchor = "the gap each item came from" — also
        # describable via sibling references, captured in redo().
        move_items(self._tab.model, self._placed, self._origin_anchor)
        # Undo collision-renames if any.
```

Selection restore moves to a **post-hook** invoked by the action
layer (or by a generic `QUndoStack` listener), not inside `redo()`.

```python
def push_move_rows(self, sources, anchor, *, label):
    cmd = _MoveRowsCmd(self, label, sources, anchor)
    self.undo_stack.push(cmd)
    self._restore_selection_from_command(cmd)   # post-hook
    return True
```

### 2.4 Move = cut-and-paste one row above

The user's mental model lands cleanly:

```python
def move_selection_up(view):
    rows = top_level_source_rows(view)
    if not rows:
        return False
    top = min(rows, key=index_path)
    anchor_sibling = previous_sibling_or_parent_promotion(top)
    if anchor_sibling is None:
        return False  # already at the top of the document
    return tab.push_move_rows(
        sources_from(rows),
        MoveAnchor(parent_path=anchor_parent_path,
                   before_sibling_path=anchor_sibling_path),
        label="move up",
    )
```

Bubble-out is just "the previous sibling is in the grandparent."
No special case, no separate code path.

---

## 3) Selection vocabulary for multi-actions

Three helpers, three semantics:

| Helper                                | Returns                          | Used for                              |
| ------------------------------------- | -------------------------------- | ------------------------------------- |
| `selected_source_rows(view)`          | every selected row, no pruning   | counting, status bar                  |
| `top_level_source_rows(view)`         | ancestors win over descendants   | **destructive**: cut / move / delete  |
| `deepest_selected_rows(view)`         | descendants win over ancestors   | **filter-mode copy** (new)            |

A selected set has three shapes:

1. **Disjoint** — no (ancestor, descendant) pairs.
   `top_level == deepest == selected`.
2. **Filter** — at least one (ancestor, descendant) pair.
   `top_level` keeps ancestors; `deepest` keeps descendants.
3. **Single node**.

Multi-actions branch on shape × action, not on ad-hoc heuristics.

---

## 4) Multi-action semantics

### 4.1 Multi-copy ( `Ctrl+C` )

> "Build a new object from all selected values. If one value is the
> successor of others — they work like a natural filter, only
> selected successors are kept. Else the whole subtree is copied."

**Algorithm**:

1. Collect `selected = selected_source_rows(view)`.
2. Detect shape:
   - **Disjoint**: build entries from each selected row's full subtree
     (current behaviour). One entry per selected row; preserves names
     under OBJECT parents.
   - **Filter** (any ancestor/descendant pair):
     - For each top-level ancestor `A` in the selection that has
       selected descendants under it, build a **pruned subtree**
       containing only paths that lead from `A` down to selected
       descendants. Non-selected siblings along those paths are
       dropped.
     - For each top-level ancestor `B` *without* selected descendants
       (mixed selections are possible), include `B` whole.

This yields one consistent rule: *the selection acts as a projection
mask on each top-level subtree*.

**Wire format**: same `application/x-json-tree` MIME — the entries
list just carries the pruned subtrees. No new MIME type.

**`entries_text_payload`** (the human-readable `text/plain` half):
- Disjoint same-parent OBJECT → `{name: value, …}` (existing).
- Disjoint same-parent ARRAY  → `[value, …]` (existing).
- Filter mode → `[subtree, …]` ordered by `_index_path`. Or, if all
  ancestors are under the same OBJECT parent and their projected
  subtrees are named, an OBJECT literal of `{name: subtree, …}`.

### 4.2 Multi-paste ( `Ctrl+V` )

> "Pastes clones everywhere."

**Algorithm**:

1. `targets = selected_source_rows(view)` (no pruning — every
   selected row is a paste target).
2. `entries = entries_from_clipboard()`.
3. For each target:
   - If target is a container (OBJECT / ARRAY): paste *all* entries
     as last children (same as `paste_as_child`).
   - Otherwise: paste *all* entries as siblings *after* the target.
4. Wrap the whole thing in a single `beginMacro("paste")` so undo
   is one step.
5. Selection after: the newly-pasted clones at every site, with
   `current_index` on the first clone of the first target.

Name collisions on OBJECT targets use the existing `_copy_name`
chain. Type/coercion handled by `_insert_typed_item`.

**Edge cases**:
- Empty selection → fall back to root-append (current behaviour).
- Mixed targets (some containers, some leaves) → each target uses
  its own auto rule. This is the user's "everywhere" intent
  generalised consistently.

### 4.3 Multi-insert ( **new** — proposed shortcut `Ctrl+Shift+V` )

> "Pastes each value/key at its own selection, top level only, no
> deep scan."

**Algorithm**:

1. `targets = top_level_source_rows(view)`, sorted by `_index_path`.
2. `entries = entries_from_clipboard()`. **Only the top-level
   entries** — never recursed into.
3. Pair `targets[i]` with `entries[i % len(entries)]` (or refuse if
   counts mismatch — pick **one** policy in the implementation
   commit; see § 7).
4. For each pair, **replace** the target's value with the entry's
   value (this is the `paste_replace_value` semantics applied
   per-target). Names are preserved on the target side — entry
   names are ignored.
5. Single macro on the undo stack.

This is genuinely different from multi-paste:
- multi-paste *inserts new rows next to* each selection,
- multi-insert *overwrites* each selection.

If the user instead wants positional sibling-after inserts, that's
a third action (`Ctrl+Alt+V`?) but I'd hold it back until users ask.

### 4.4 Move = multi-cut + paste-before-anchor

With the new vocabulary, **move is fully derivable**:

```
move_up(selection) ==
    macro:
        anchor = previous_sibling_or_parent_promotion(top_of(selection))
        move_items(selection, MoveAnchor(before_sibling=anchor))
```

The "cut + paste" framing makes the user model and the
implementation match exactly. The *only* reason `_MoveRowsCmd`
stays as a distinct command (rather than literal `_RemoveRowsCmd` +
`_InsertRowsCmd`) is to preserve `JsonTreeItem` identity so view
expansion of subtrees survives. That stays a private detail of the
move primitive.

---

## 5) Required source changes (when this plan is unblocked)

Single-commit plan, file-by-file:

1. `tree_actions/selection.py`
   - Add `deepest_selected_rows(view) -> list[QModelIndex]`.
   - Add `selection_shape(rows) -> Literal["disjoint", "filter", "single"]`.
   - Document `top_level_source_rows` as the "destructive" helper.

2. `tree_actions/anchors.py` *(new)*
   - `MoveAnchor` dataclass.
   - `anchor_before(idx)`, `anchor_after(idx)`, `anchor_at_start(parent)`,
     `anchor_at_end(parent)`, `previous_sibling_or_parent_promotion(idx)`.

3. `tree/model.py`
   - `move_items(sources, anchor)` — the new primitive. Wraps
     `beginInsertRows` / `beginRemoveRows` (or `beginMoveRows`
     when source-parent == target-parent + the destination is
     resolvable as a Qt move) so views animate correctly.

4. `undo/commands.py`
   - Rewrite `_MoveRowsCmd` to take `(sources, anchor)` instead of
     `(sources, target_parent_path, target_row)`.
   - Move `_select_placed_rows` out of `redo()` into a public
     `placed_indexes` property; selection update becomes an
     action-layer hook.
   - Keep the **constructor signature backwards-compatible** via a
     classmethod `from_row_anchor(sources, target_parent, target_row)`
     so old tests don't need rewriting.

5. `documents/tab.py`
   - `push_move_rows(sources, anchor, *, label)` becomes the
     canonical API.
   - `push_move_row(parent, src, dst)` becomes a thin wrapper that
     constructs an anchor.
   - Post-hook `_restore_selection_from_command` invoked after
     `undo_stack.push(cmd)` succeeds.

6. `tree_actions/structure.py`
   - Delete `_move_same_parent`, `_multi_parent_common_grandparent_move`,
     `_move_multi_parent_fallback`. Replace with the four-line
     `move_selection_up/down` shown in § 2.4.
   - `delete_selection` and `cut_selection` stay on
     `top_level_source_rows`.

7. `tree_actions/clipboard.py`
   - Branch by `selection_shape`.
   - Add `_build_filter_entries(model, selected)` to build pruned
     subtrees for the filter mode.
   - Existing `_entries_text_payload` extended to handle the new
     filter-mode entries (mostly straight-through; mainly a unit
     test addition).

8. `tree_actions/paste.py`
   - Split `paste_from_clipboard` into:
     - `paste_clones_at_targets(view, targets, entries)` — multi-paste.
     - `paste_zip_at_targets(view, targets, entries)` — multi-insert.
   - Wire `Ctrl+V` → `paste_clones_at_targets(view, selected_source_rows(view), entries)`.
   - Wire `Ctrl+Shift+V` → `paste_zip_at_targets(view, top_level_source_rows(view), entries)`.

9. `documents/tab_setup.py`
   - Bind `Ctrl+Shift+V` to multi-insert. Single-line addition.

10. `tree_actions/context_menu.py`
    - Add a "Paste at each ▸ Replace" entry alongside the existing
      Paste submenu when there are >1 selected rows.

11. Tests (new):
    - `tests/test_anchor_move.py` — the four anchor primitives,
      same-parent / cross-parent / start / end coverage, identity
      preservation.
    - `tests/test_multi_copy_filter.py` — disjoint vs filter shapes.
    - `tests/test_multi_paste_clones.py` — every target gets a clone.
    - `tests/test_multi_insert_zip.py` — pairing rules, count
      mismatch policy.
    - `tests/test_move_no_op_guard.py` — no command is pushed when
      the anchor equals the current position.

12. `ai-memory/repo-map.md`
    - § 4 keyboard table: explain new `Ctrl+Shift+V`.
    - § 11: document `selection_shape`, `MoveAnchor`,
      `move_items`, `paste_clones_at_targets`,
      `paste_zip_at_targets`.
    - § 15: new `_MoveRowsCmd` shape.

---

## 6) Backwards compatibility & migration

- `push_move_row(parent, src, dst)` stays a thin wrapper — no
  caller has to change.
- Old `push_move_rows(sources, target_parent, target_row)` keeps
  working via a deprecation shim that constructs the anchor under
  the hood. Mark with a deprecation comment; remove after one cycle.
- MIME format unchanged → clipboard payloads written by the old
  build round-trip through the new decoder.
- Old `_MoveRowsCmd` tests use the classmethod constructor and
  remain green.

---

## 7) Open design questions (call these before coding)

1. **Multi-insert count mismatch** — when `len(targets) != len(entries)`,
   should we (a) refuse, (b) round-robin entries, (c) zip-to-shortest?
   *Recommendation*: **(c) zip-to-shortest** with a status-bar
   message `"Inserted N of M; selection longer than clipboard"`.

2. **Filter-mode multi-copy — empty projection** — if an ancestor
   is selected with descendants and *all* its non-trivial children
   are also unselected, the projection collapses to an empty
   OBJECT/ARRAY. Keep it (`{}` / `[]`) or fall back to the full
   subtree? *Recommendation*: **keep the empty projection** — it's
   the consistent rule and makes the operation predictable.

3. **`Ctrl+Shift+V` collision with existing OS shortcuts** — Qt
   doesn't reserve it, but some environments map it to "paste
   without formatting". *Recommendation*: bind it but make it
   configurable via the same `settings.json` slot reserved for the
   future keymap (see `todo-n-fixme.md`).

4. **Should move on a no-op return `True` or `False`?**
   *Recommendation*: **`False`** + no command pushed + no
   status-bar message. Matches the user's expectation that "nothing
   happened".

5. **Drag-and-drop step 06 resumption** — after this lands, the
   internal-drop step is *much smaller*: `dropMimeData` builds a
   `MoveAnchor` from the drop indicator and calls
   `tab.push_move_rows(sources, anchor)`. No row arithmetic
   anywhere in `tree_actions/dnd.py`.

---

## 8) Acceptance criteria

When this lands:

- All four kinds of selection (single, disjoint, filter, same-parent
  block) behave identically under `Alt+Up` / `Alt+Down`: every row
  in the selection moves one slot toward the edge, bubble-out
  promotes to the grandparent, no row is silently skipped or
  swapped with the wrong sibling.
- Cycle guard, name-collision, and out-of-range guards all live
  inside `move_items` — no caller can bypass them.
- Selection restore is observable in the action layer and absent
  from `_MoveRowsCmd.redo`.
- `Ctrl+C` / `Ctrl+V` / `Ctrl+Shift+V` follow the rules of § 4
  with test coverage per § 5.
- Code count: `tree_actions/structure.py` move-related code drops
  from ~135 lines (three branches + fallback + selection restore)
  to ~25 lines (two callers + one helper).
- `pytest -q` is green; the 3 offscreen-only colour-scheme failures
  remain the only allowed reds.
