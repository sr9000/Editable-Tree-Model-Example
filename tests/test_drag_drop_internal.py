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
