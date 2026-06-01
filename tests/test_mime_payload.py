"""Step 2 — Reusable MIME (de)serializer for multi-selection.

Tests for build_tree_mime / entries_from_mime canonical wire format.
"""

import json

from PySide6.QtCore import QMimeData, QModelIndex

from tree.model import JsonTreeModel
from tree_actions.clipboard import (MIME_JSON_TREE, build_tree_mime,
                                    entries_from_mime)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _rows(model: JsonTreeModel, *row_nums, parent=None):
    p = parent if parent is not None else QModelIndex()
    return [model.index(r, 0, p) for r in row_nums]


# ---------------------------------------------------------------------------
# Test 1 — Round-trip: entries_from_mime(build_tree_mime(model, rows))
# ---------------------------------------------------------------------------


def test_round_trip_preserves_name_and_value(qtbot):
    model = JsonTreeModel({"alpha": 1, "beta": [2, 3], "gamma": "hello"})
    rows = _rows(model, 0, 1, 2)

    mime = build_tree_mime(model, rows)
    assert mime is not None
    assert mime.hasFormat(MIME_JSON_TREE)

    entries = entries_from_mime(mime)
    assert entries is not None
    assert len(entries) == 3

    names = [e["name"] for e in entries]
    values = [e["value"] for e in entries]
    assert names == ["alpha", "beta", "gamma"]
    assert values == [1, [2, 3], "hello"]


def test_round_trip_order_stable_regardless_of_input_order(qtbot):
    """build_tree_mime sorts by _index_path; round-trip order must match source order."""
    model = JsonTreeModel({"x": 10, "y": 20, "z": 30})
    # Pass rows in reverse order — encoder must sort them.
    rows = list(reversed(_rows(model, 0, 1, 2)))

    mime = build_tree_mime(model, rows)
    entries = entries_from_mime(mime)
    assert [e["name"] for e in entries] == ["x", "y", "z"]


# ---------------------------------------------------------------------------
# Test 2 — Disjoint cross-parent selection encodes to list text payload
# ---------------------------------------------------------------------------


def test_disjoint_cross_parent_encodes_to_list(qtbot):
    model = JsonTreeModel({"obj1": {"a": 1}, "obj2": {"b": 2}})
    model.expandAll = lambda: None  # not needed; just access children

    obj1 = model.index(0, 0, QModelIndex())
    obj2 = model.index(1, 0, QModelIndex())

    # Children of different parents
    child_a = model.index(0, 0, obj1)
    child_b = model.index(0, 0, obj2)

    mime = build_tree_mime(model, [child_a, child_b])
    assert mime is not None

    text = mime.text()
    parsed = json.loads(text)
    # Disjoint parents → list payload
    assert isinstance(parsed, list)
    assert sorted(parsed) == [1, 2]


# ---------------------------------------------------------------------------
# Test 3 — Same-OBJECT-parent → dict in text/plain, entries list in binary
# ---------------------------------------------------------------------------


def test_same_object_parent_dict_text_payload(qtbot):
    model = JsonTreeModel({"a": 1, "b": 2, "c": 3})
    rows = _rows(model, 0, 1, 2)

    mime = build_tree_mime(model, rows)
    assert mime is not None

    # text/plain must be a dict
    text = mime.text()
    parsed = json.loads(text)
    assert isinstance(parsed, dict)
    assert parsed == {"a": 1, "b": 2, "c": 3}

    # binary MIME_JSON_TREE still uses the entries list format
    raw = mime.data(MIME_JSON_TREE).data().decode("utf-8")
    blob = json.loads(raw)
    assert "entries" in blob
    assert isinstance(blob["entries"], list)
    assert len(blob["entries"]) == 3


# ---------------------------------------------------------------------------
# Test 4 — Decoder accepts plain-text JSON object from another app
# ---------------------------------------------------------------------------


def test_decoder_accepts_plain_text_json_object(qtbot):
    mime = QMimeData()
    mime.setText('{"foo": 42, "bar": "baz"}')

    entries = entries_from_mime(mime)
    assert entries is not None
    assert len(entries) == 2
    names = {e["name"] for e in entries}
    assert names == {"foo", "bar"}
    values = {e["name"]: e["value"] for e in entries}
    assert values["foo"] == 42
    assert values["bar"] == "baz"


def test_decoder_accepts_plain_text_json_array(qtbot):
    mime = QMimeData()
    mime.setText("[1, 2, 3]")

    entries = entries_from_mime(mime)
    assert entries is not None
    assert [e["value"] for e in entries] == [1, 2, 3]
    assert all(e["name"] is None for e in entries)


# ---------------------------------------------------------------------------
# Test 5 — Decoder returns None for malformed JSON without raising
# ---------------------------------------------------------------------------


def test_decoder_rejects_malformed_json(qtbot):
    mime = QMimeData()
    mime.setText("this is { not valid JSON !!")

    result = entries_from_mime(mime)
    assert result is None


def test_decoder_returns_none_for_empty_mime(qtbot):
    mime = QMimeData()
    result = entries_from_mime(mime)
    assert result is None


def test_decoder_returns_none_for_none(qtbot):
    assert entries_from_mime(None) is None


# ---------------------------------------------------------------------------
# Test 6 — build_tree_mime returns None for empty rows
# ---------------------------------------------------------------------------


def test_build_tree_mime_empty_rows_returns_none(qtbot):
    model = JsonTreeModel({"a": 1})
    assert build_tree_mime(model, []) is None


# ---------------------------------------------------------------------------
# Test 7 — MIME_JSON_TREE constant defined exactly once (import smoke)
# ---------------------------------------------------------------------------


def test_mime_json_tree_constant_value():
    from tree_actions.clipboard import MIME_JSON_TREE as reexported

    assert reexported == MIME_JSON_TREE == "application/x-json-tree"
