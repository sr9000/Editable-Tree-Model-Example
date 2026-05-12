"""Property-based fuzz for drag-and-drop.

Composes random sequences of internal moves through the public
``proxy.dropMimeData`` path and asserts the following invariants after
every step:

1. **Serializability** — the entire tree round-trips through ``to_json``.
2. **Conservation of leaves** — when moving primitive leaves, the
   multiset of *leaf primitive values* never grows or shrinks; items
   only relocate.
3. **OBJECT key validity** — every OBJECT child has a non-empty unique
   string name.
4. **Undo round-trip** — ``undo_stack.undo()`` to depth 0 restores the
   exact original tree.

These properties together catch the failure modes that surfaced as
"null rows", "items disappearing", "off-by-one container placement",
and "duplicate keys after move".
"""
from __future__ import annotations

import random
from typing import Any

from PySide6.QtCore import QItemSelection, QItemSelectionModel, QModelIndex, Qt

import pytest

from documents.tab import JsonTab


# ---------------------------------------------------------------------------
# Reusable helpers (mirroring test_drag_drop_matrix.py for self-containedness)
# ---------------------------------------------------------------------------

def _make_tab(qtbot, data) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data)
    qtbot.addWidget(tab)
    return tab


def _pidx(tab, path):
    idx = QModelIndex()
    for r in path:
        idx = tab.proxy.index(r, 0, idx)
    return idx


def _select(tab, proxy_indexes):
    sm = tab.view.selectionModel()
    sel = QItemSelection()
    for pidx in proxy_indexes:
        sel.select(pidx, pidx)
    sm.select(sel, QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows)


def _drop(tab, sel_paths, row, col, parent_path):
    sel = [_pidx(tab, p) for p in sel_paths]
    _select(tab, sel)
    mime = tab.proxy.mimeData(sel)
    parent = QModelIndex() if parent_path is None else _pidx(tab, parent_path)
    return tab.proxy.dropMimeData(mime, Qt.DropAction.MoveAction, row, col, parent)


def _enumerate_paths(item, prefix=()) -> list[tuple[tuple[int, ...], bool]]:
    """Return ``[(path, is_container), ...]`` for every node beneath *item*."""
    out: list[tuple[tuple[int, ...], bool]] = []
    for i, child in enumerate(item.child_items):
        path = prefix + (i,)
        out.append((path, child.json_type.name in ("OBJECT", "ARRAY")))
        if child.child_items:
            out.extend(_enumerate_paths(child, path))
    return out


def _validate_object_names(item, breadcrumb="$") -> None:
    if item.json_type.name == "OBJECT":
        seen: set[str] = set()
        for child in item.child_items:
            assert isinstance(child.name, str) and child.name, (
                f"OBJECT child has invalid name at {breadcrumb}: {child.name!r}"
            )
            assert child.name not in seen, f"Duplicate OBJECT key {child.name!r} at {breadcrumb}"
            seen.add(child.name)
    for i, child in enumerate(item.child_items):
        crumb = f"{breadcrumb}[{i}]" if item.json_type.name == "ARRAY" else f"{breadcrumb}.{child.name}"
        _validate_object_names(child, crumb)


def _collect_leaf_primitives(value: Any) -> list[Any]:
    """Flatten a JSON value into the multiset of its primitive leaves."""
    if isinstance(value, dict):
        out = []
        for v in value.values():
            out.extend(_collect_leaf_primitives(v))
        return out
    if isinstance(value, list):
        out = []
        for v in value:
            out.extend(_collect_leaf_primitives(v))
        return out
    return [value]


# ---------------------------------------------------------------------------
# Random scenario engine
# ---------------------------------------------------------------------------

def _try_random_drop(tab, rng) -> str:
    """Make one random drop attempt. Returns a description for diagnostics."""
    all_paths = _enumerate_paths(tab.model.root_item)
    if not all_paths:
        return "noop: empty tree"

    # Pick 1-3 random sources at the same depth-1 layer to keep the move tractable.
    source_path, _is_container = rng.choice(all_paths)
    sources = [source_path]
    # 30% chance: add a sibling source for multi-row drag.
    if len(source_path) == 1 and rng.random() < 0.3:
        siblings_at_root = [p for (p, _c) in all_paths if len(p) == 1 and p != source_path]
        if siblings_at_root:
            sources.append(rng.choice(siblings_at_root))

    # Choose a target. Mix of indicator positions.
    targets = [p for (p, _c) in all_paths if p not in sources]
    if not targets and not _enumerate_paths(tab.model.root_item):
        return "noop: nowhere to drop"

    mode = rng.choice(["above", "below", "on", "viewport"])
    if mode == "viewport":
        ok = _drop(tab, sources, -1, -1, None)
        return f"viewport sources={sources} ok={ok}"

    if not targets:
        return "noop: no targets"

    target_path = rng.choice(targets)
    target_is_container = next(c for (p, c) in all_paths if p == target_path)
    parent_path = target_path[:-1] or ()
    last_row = target_path[-1]

    if mode == "above":
        ok = _drop(tab, sources, last_row, 0, parent_path if parent_path else None)
        return f"above target={target_path} sources={sources} ok={ok}"
    if mode == "below":
        ok = _drop(tab, sources, last_row + 1, 0, parent_path if parent_path else None)
        return f"below target={target_path} sources={sources} ok={ok}"
    # OnItem
    if not target_is_container:
        # OnItem of a leaf is rejected; treat as a no-op attempt.
        ok = _drop(tab, sources, -1, -1, target_path)
        return f"on(leaf) target={target_path} sources={sources} ok={ok}"
    ok = _drop(tab, sources, -1, -1, target_path)
    return f"on target={target_path} sources={sources} ok={ok}"


# ---------------------------------------------------------------------------
# Property tests
# ---------------------------------------------------------------------------

FIXTURES: list[tuple[str, Any]] = [
    ("flat array primitives", ["a", "b", "c", "d", "e", "f"]),
    ("flat array objects", [{"a": 1}, {"b": 2}, {"c": 3}, {"d": 4}, {"e": 5}, {"f": 6}]),
    ("mixed array", [{"k": 1}, 2, [3, 4], "s", {"deep": {"x": 9}}, None]),
    ("nested object", {
        "left": {"a": 1, "b": 2, "c": 3},
        "right": [10, 20, 30],
        "mix": {"arr": [{"q": 0}], "obj": {"r": 1, "s": 2}},
    }),
    ("two-tier array", [[1, 2, 3], [4, 5, 6], [7, 8, 9]]),
]


@pytest.mark.parametrize("fixture_name,initial", FIXTURES)
@pytest.mark.parametrize("seed", [0xC0FFEE, 0xDEADBEEF, 0x1337])
def test_property_random_drops_preserve_invariants(qtbot, fixture_name, initial, seed):
    rng = random.Random(seed ^ hash(fixture_name))
    tab = _make_tab(qtbot, initial)
    initial_snap = tab.model.root_item.to_json()
    initial_leaves = sorted(repr(x) for x in _collect_leaf_primitives(initial_snap))

    history: list[str] = []
    for step in range(40):
        try:
            desc = _try_random_drop(tab, rng)
        except Exception as exc:  # pragma: no cover — diagnostic path
            pytest.fail(f"[{fixture_name}] drop raised at step {step}: {exc!r}\nhistory={history}")
        history.append(desc)

        # 1. Serializability.
        snap = tab.model.root_item.to_json()
        assert isinstance(snap, (dict, list)), (
            f"[{fixture_name}] root collapsed to {type(snap)} at step {step}\nhistory={history}"
        )

        # 2. Conservation of primitive leaves.
        leaves = sorted(repr(x) for x in _collect_leaf_primitives(snap))
        assert leaves == initial_leaves, (
            f"[{fixture_name}] leaf multiset changed at step {step}\n"
            f"  before: {initial_leaves}\n  now:    {leaves}\n  history={history}"
        )

        # 3. OBJECT key invariants.
        _validate_object_names(tab.model.root_item)

    # 4. Undo back to the original.
    while tab.undo_stack.canUndo():
        tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == initial_snap, (
        f"[{fixture_name}] undo to depth 0 did not restore original\nhistory={history}"
    )

    # And redo back to the final post-fuzz state must succeed without error.
    while tab.undo_stack.canRedo():
        tab.undo_stack.redo()
    _validate_object_names(tab.model.root_item)
    leaves_after_redo = sorted(repr(x) for x in _collect_leaf_primitives(tab.model.root_item.to_json()))
    assert leaves_after_redo == initial_leaves
