from PySide6.QtCore import QModelIndex

from json_tab import JsonTab


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

    tab.view.setCurrentIndex(leaf_index)
    assert captured, "expected breadcrumb callback to be called"
    assert captured[-1] == "$.foo.bar[1]  (string, 3 chars)"

    tab.view.selectionModel().clearCurrentIndex()
    assert captured[-1] == ""


def test_breadcrumb_size_hints_for_container_and_binary(qtbot):
    captured: list[str] = []

    tab = JsonTab(
        lambda *_: None,
        data={"obj": {"k": "v"}, "blob": "dGVzdA=="},
        permanent_message_callback=captured.append,
    )
    qtbot.addWidget(tab)

    obj_index = tab.model.index(0, 0, QModelIndex())
    tab.view.setCurrentIndex(obj_index)
    assert captured[-1] == "$.obj  (object, 1 items)"

    blob_name_index = tab.model.index(1, 0, QModelIndex())
    tab.view.setCurrentIndex(blob_name_index)
    assert captured[-1] == "$.blob  (bytes, 4 byte)"
