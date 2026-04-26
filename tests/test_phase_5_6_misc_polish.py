from PySide6.QtCore import QModelIndex

from json_tab import JsonTab
from ui import MainWindow


def test_view_menu_expand_collapse_toggles_expansion(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)

    tab = win._add_tab(data={"foo": {"bar": 1}}, file_path=None)
    assert tab is not None

    root = tab.model.index(0, 0, QModelIndex())
    root_view = tab._source_to_view(root)

    win.viewCollapseAllAction.trigger()
    assert not tab.view.isExpanded(root_view)

    win.viewExpandAllAction.trigger()
    assert tab.view.isExpanded(root_view)


def test_model_reset_calls_resize_key_columns(qtbot):
    tab = JsonTab(lambda *_: None, data={"foo": 1}, show_root=True)
    qtbot.addWidget(tab)

    calls: list[int] = []
    original = tab.resize_key_columns

    def _spy() -> None:
        calls.append(1)
        original()

    tab.resize_key_columns = _spy

    tab.model.beginResetModel()
    tab.model.endResetModel()

    assert calls, "expected modelReset to trigger key-column resize"


def test_view_zoom_actions_call_tab_zoom_and_resize(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)

    tab = win._add_tab(data={"foo": 1}, file_path=None)
    assert tab is not None

    calls: list[int] = []
    original = tab.resize_key_columns

    def _spy() -> None:
        calls.append(1)
        original()

    tab.resize_key_columns = _spy

    before = tab.view.font().pointSize()
    win.viewZoomInAction.trigger()
    after_in = tab.view.font().pointSize()
    win.viewResetZoomAction.trigger()
    after_reset = tab.view.font().pointSize()

    assert after_in >= before
    assert after_reset == tab._default_font_pt
    assert len(calls) >= 2
