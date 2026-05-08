from PySide6.QtCore import QModelIndex

from documents.tab import JsonTab


def test_breadcrumb_callback_updates_on_selection_and_clear(qtbot):
    captured: list[str] = []

    tab = JsonTab(
        lambda *_: None,
        data={"foo": {"bar": [1, "xyz"]}},
        permanent_message_callback=captured.append,
    )
    qtbot.addWidget(tab)

    foo_index = tab.model.index(0, 0, QModelIndex())
    bar_index = tab.model.index(0, 0, foo_index)
    leaf_index = tab.model.index(1, 0, bar_index)

    tab.view.setCurrentIndex(tab._source_to_view(leaf_index))
    assert captured, "expected breadcrumb callback to be called"
    assert captured[-1] == "$.foo.bar[1]  (string, 3 chars)"

    tab.view.selectionModel().clearCurrentIndex()
    assert captured[-1] == ""


def test_breadcrumb_size_hints_for_container_and_binary(qtbot):
    captured: list[str] = []

    tab = JsonTab(
        lambda *_: None,
        data={"obj": {"k": "v"}, "blob": "bXkgbG92ZWx5IGJ5dGVzIQ=="},
        permanent_message_callback=captured.append,
    )
    qtbot.addWidget(tab)

    obj_index = tab.model.index(0, 0, QModelIndex())
    tab.view.setCurrentIndex(tab._source_to_view(obj_index))
    assert captured[-1] == "$.obj  (object, 1 items)"

    blob_name_index = tab.model.index(1, 0, QModelIndex())
    tab.view.setCurrentIndex(tab._source_to_view(blob_name_index))
    assert captured[-1] == "$.blob  (bytes, 16 byte)"
