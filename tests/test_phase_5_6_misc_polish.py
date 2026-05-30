from PySide6.QtCore import QModelIndex

from app.main_window import MainWindow
from documents.tab import JsonTab
from tree.types import JsonType


def test_view_menu_expand_collapse_toggles_expansion(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)

    tab = win._add_tab(data={"foo": {"bar": 1}}, file_path=None)
    assert tab is not None

    root = tab.data_store.model.index(0, 0, QModelIndex())
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

    def _spy(force: bool = False) -> None:
        calls.append(1)
        original(force=force)

    tab.resize_key_columns = _spy

    tab.data_store.model.beginResetModel()
    tab.data_store.model.endResetModel()

    assert calls, "expected modelReset to trigger key-column resize"


def test_view_zoom_actions_call_tab_zoom_and_resize(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)

    tab = win._add_tab(data={"foo": 1}, file_path=None)
    assert tab is not None

    before = tab.view.font().pointSize()
    win.viewZoomInAction.trigger()
    after_in = tab.view.font().pointSize()
    win.viewResetZoomAction.trigger()
    after_reset = tab.view.font().pointSize()

    assert after_in >= before
    assert after_reset == tab.data_store._default_font_pt


def test_zoom_preserves_user_column_widths(qtbot):
    """After the user manually resizes a column, zoom must not snap it back."""
    tab = JsonTab(lambda *_: None, data={"foo": 1, "bar": 2})
    qtbot.addWidget(tab)

    # Simulate the user dragging col 0 to a custom width.
    custom_width = 200
    tab.view.setColumnWidth(0, custom_width)
    tab.data_store._user_sized_columns.add(0)  # mark as user-sized (normally done by sectionResized handler)

    # Zoom in three times.
    for _ in range(3):
        tab.zoom_in()

    # Col 0 must remain unchanged because it is user-sized.
    assert (
        tab.view.columnWidth(0) == custom_width
    ), f"Expected col 0 to stay at {custom_width}, got {tab.view.columnWidth(0)}"

    # Col 1 (not hand-resized) should have been scaled up.
    assert tab.view.columnWidth(1) > 0


def test_zoom_updates_tree_icon_size(qtbot):
    tab = JsonTab(lambda *_: None, data={"foo": 1}, show_root=True)
    qtbot.addWidget(tab)

    before = tab.view.iconSize().height()
    tab.zoom_in()
    after_in = tab.view.iconSize().height()
    tab.zoom_out()
    after_out = tab.view.iconSize().height()

    assert after_in >= before
    assert after_out <= after_in


def test_float_to_integer_type_change_shows_fraction_loss_warning(qtbot):
    messages: list[tuple[str, int]] = []

    def _status(text: str, timeout_ms: int) -> None:
        messages.append((text, timeout_ms))

    tab = JsonTab(lambda *_: None, data={"v": 3.5}, show_root=True, status_message_callback=_status)
    qtbot.addWidget(tab)

    root_idx = tab.data_store.model.index(0, 0, QModelIndex())
    type_idx = tab.data_store.model.index(0, 1, root_idx)
    assert tab.push_change_type(type_idx, JsonType.INTEGER)
    assert any("Fractional part discarded" in text for text, _ in messages)
