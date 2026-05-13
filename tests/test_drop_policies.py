from __future__ import annotations

import simplejson
from PySide6.QtCore import QMimeData, Qt

from documents.tab import JsonTab
from tree_actions.clipboard import MIME_JSON_TREE


def _make_tab(qtbot, data, show_root=False, status_cb=None) -> JsonTab:
    tab = JsonTab(lambda *_: None, status_message_callback=status_cb, data=data, show_root=show_root)
    qtbot.addWidget(tab)
    return tab


def _idx(tab: JsonTab, *path: int):
    return tab._index_from_path(path)


def _mime_without_source_paths(entries: list[dict]) -> QMimeData:
    mime = QMimeData()
    mime.setData(MIME_JSON_TREE, simplejson.dumps({"entries": entries}).encode("utf-8"))
    mime.setText(simplejson.dumps([e["value"] for e in entries]))
    return mime


def test_can_drop_rejects_cycle_before_mutation(qtbot):
    tab = _make_tab(qtbot, {"outer": {"inner": {"leaf": 1}}})
    outer = _idx(tab, 0)
    inner = _idx(tab, 0, 0)
    mime = tab.model.mimeData([outer])

    assert not tab.model.canDropMimeData(mime, Qt.DropAction.MoveAction, -1, -1, inner)
    assert tab.model.root_item.to_json() == {"outer": {"inner": {"leaf": 1}}}


def test_on_leaf_drop_bubbles_to_sibling_after(qtbot):
    tab = _make_tab(qtbot, {"src": {"a": 1}, "dst": {"x": 0, "y": 2}})
    src = _idx(tab, 0)
    dst = _idx(tab, 1)

    a = tab.model.index(0, 0, src)
    x_leaf = tab.model.index(0, 0, dst)
    mime = tab.model.mimeData([a])

    assert tab.model.dropMimeData(mime, Qt.DropAction.MoveAction, -1, -1, x_leaf)
    assert tab.model.root_item.to_json() == {"src": {}, "dst": {"x": 0, "a": 1, "y": 2}}


def test_move_action_requires_source_paths_but_copy_does_not(qtbot):
    tab = _make_tab(qtbot, {"dst": []})
    dst = _idx(tab, 0)
    mime = _mime_without_source_paths([{"name": None, "value": 10}])

    assert not tab.model.canDropMimeData(mime, Qt.DropAction.MoveAction, 0, 0, dst)
    assert tab.model.canDropMimeData(mime, Qt.DropAction.CopyAction, 0, 0, dst)


def test_copy_vs_move_action_semantics(qtbot):
    tab = _make_tab(qtbot, {"src": {"a": 1, "b": 2}, "dst": {}})
    src = _idx(tab, 0)
    dst = _idx(tab, 1)

    a = tab.model.index(0, 0, src)
    mime_copy = tab.model.mimeData([a])
    assert tab.model.dropMimeData(mime_copy, Qt.DropAction.CopyAction, 0, 0, dst)
    assert tab.model.root_item.to_json() == {"src": {"a": 1, "b": 2}, "dst": {"a": 1}}

    a_again = tab.model.index(0, 0, src)
    mime_move = tab.model.mimeData([a_again])
    assert tab.model.dropMimeData(mime_move, Qt.DropAction.MoveAction, 1, 0, dst)
    assert tab.model.root_item.to_json() == {"src": {"b": 2}, "dst": {"a": 1, "a_2": 1}}


def test_successful_drop_emits_status_message(qtbot):
    messages: list[str] = []

    def _status(msg: str, _timeout: int) -> None:
        messages.append(msg)

    tab = _make_tab(qtbot, {"src": {"a": 1}, "dst": {}}, status_cb=_status)
    src = _idx(tab, 0)
    dst = _idx(tab, 1)

    a = tab.model.index(0, 0, src)
    mime = tab.model.mimeData([a])
    assert tab.model.dropMimeData(mime, Qt.DropAction.MoveAction, 0, 0, dst)

    assert messages
    assert messages[-1] == "Moved 1 row under $.dst"
