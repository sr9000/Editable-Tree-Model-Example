from __future__ import annotations

from PySide6.QtCore import QModelIndex, Qt

from documents.tab import JsonTab


def _make_tab(qtbot, data) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data)
    qtbot.addWidget(tab)
    return tab


def _idx(tab: JsonTab, *path: int):
    return tab._index_from_path(path)


def test_internal_drag_drop_move_and_single_undo(qtbot):
    tab = _make_tab(
        qtbot,
        {
            "src": {"a": 1, "b": 2, "c": 3},
            "other": {"q": 9},
        },
    )

    src = _idx(tab, 0)
    other = _idx(tab, 1)
    row_a = tab.model.index(0, 0, src)
    row_b = tab.model.index(1, 0, src)

    mime = tab.model.mimeData([row_a, row_b])
    assert mime is not None

    ok = tab.model.dropMimeData(mime, Qt.DropAction.MoveAction, 1, 0, other)
    assert ok

    root = tab.model.root_item.to_json()
    assert root["src"] == {"c": 3}
    assert list(root["other"].items())[1:] == [("a", 1), ("b", 2)]

    assert tab.undo_stack.count() == 1
    tab.undo_stack.undo()
    assert tab.model.root_item.to_json() == {
        "src": {"a": 1, "b": 2, "c": 3},
        "other": {"q": 9},
    }


def test_cross_tab_copy_drop_keeps_source_unchanged(qtbot):
    source = _make_tab(qtbot, {"left": {"a": 1, "b": 2}})
    target = _make_tab(qtbot, {"right": {}})

    left = _idx(source, 0)
    a = source.model.index(0, 0, left)
    b = source.model.index(1, 0, left)
    mime = source.model.mimeData([a, b])

    right = _idx(target, 0)
    ok = target.model.dropMimeData(mime, Qt.DropAction.CopyAction, 0, 0, right)
    assert ok

    assert source.model.root_item.to_json() == {"left": {"a": 1, "b": 2}}
    assert target.model.root_item.to_json() == {"right": {"a": 1, "b": 2}}


def test_can_drop_rejects_on_row_drop_onto_primitive(qtbot):
    tab = _make_tab(qtbot, {"obj": {"a": 1}, "dst": {"x": 0}})
    obj = _idx(tab, 0)
    src_child = tab.model.index(0, 0, obj)
    mime = tab.model.mimeData([src_child])

    dst = _idx(tab, 1)
    primitive = tab.model.index(0, 0, dst)

    assert not tab.model.canDropMimeData(
        mime,
        Qt.DropAction.MoveAction,
        -1,
        0,
        primitive,
    )


def test_move_action_without_internal_source_falls_back_to_copy(qtbot):
    source = _make_tab(qtbot, {"left": {"a": 1}})
    target = _make_tab(qtbot, {"right": {}})

    left = _idx(source, 0)
    a = source.model.index(0, 0, left)
    mime = source.model.mimeData([a])

    right = _idx(target, 0)
    ok = target.model.dropMimeData(mime, Qt.DropAction.MoveAction, 0, 0, right)
    assert ok

    assert source.model.root_item.to_json() == {"left": {"a": 1}}
    assert target.model.root_item.to_json() == {"right": {"a": 1}}


def test_internal_move_ignores_immediate_followup_remove_rows(qtbot):
    tab = _make_tab(qtbot, {"src": {"a": 1, "b": 2, "c": 3}, "dst": {}})

    src = _idx(tab, 0)
    dst = _idx(tab, 1)
    a = tab.model.index(0, 0, src)

    mime = tab.model.mimeData([a])
    assert tab.model.dropMimeData(mime, Qt.DropAction.MoveAction, 0, 0, dst)

    # Simulate Qt calling removeRows on the source right after a move-drop.
    assert tab.model.removeRows(0, 1, src)

    root = tab.model.root_item.to_json()
    assert root["dst"] == {"a": 1}
    assert root["src"] == {"b": 2, "c": 3}


def test_internal_move_auto_renames_object_key_collisions(qtbot):
    tab = _make_tab(qtbot, {"src": {"k": 1}, "dst": {"k": 2}})

    src = _idx(tab, 0)
    dst = _idx(tab, 1)
    k = tab.model.index(0, 0, src)
    mime = tab.model.mimeData([k])

    assert tab.model.dropMimeData(mime, Qt.DropAction.MoveAction, 1, 0, dst)
    assert tab.model.root_item.to_json() == {"src": {}, "dst": {"k": 2, "k_2": 1}}


def test_internal_move_array_child_into_object_gets_generated_name(qtbot):
    tab = _make_tab(qtbot, {"arr": [10], "obj": {"a": 1}})

    arr = _idx(tab, 0)
    obj = _idx(tab, 1)
    item = tab.model.index(0, 0, arr)
    mime = tab.model.mimeData([item])

    assert tab.model.dropMimeData(mime, Qt.DropAction.MoveAction, 1, 0, obj)

    result = tab.model.root_item.to_json()
    assert result["arr"] == []
    assert result["obj"]["a"] == 1
    assert 10 in result["obj"].values()


def test_repeated_internal_moves_keep_model_serializable(qtbot):
    tab = _make_tab(
        qtbot,
        {
            "left": {"a": 1, "b": 2, "c": 3},
            "right": {"x": 9},
        },
    )

    left = _idx(tab, 0)
    right = _idx(tab, 1)

    for _ in range(20):
        a = tab.model.index(0, 0, left)
        mime1 = tab.model.mimeData([a])
        assert tab.model.dropMimeData(mime1, Qt.DropAction.MoveAction, 1, 0, right)

        x = tab.model.index(0, 0, right)
        mime2 = tab.model.mimeData([x])
        assert tab.model.dropMimeData(mime2, Qt.DropAction.MoveAction, 0, 0, left)

    # Main invariant: no unnamed OBJECT children and stable full serialization.
    snapshot = tab.model.root_item.to_json()
    assert isinstance(snapshot, dict)
