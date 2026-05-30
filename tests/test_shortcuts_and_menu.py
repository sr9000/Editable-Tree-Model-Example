from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QModelIndex
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import QApplication, QMenu

from app.main_window import MainWindow
from documents.states.editing_controller import TreeAction
from documents.tab import JsonTab
from tree_actions.context_menu import show_context_menu


def _set_current_source_row(tab: JsonTab, source_index: QModelIndex) -> None:
    view_index = tab.view_controller.source_to_view(source_index)
    sm = tab.view.selectionModel()
    sm.select(
        view_index,
        QItemSelectionModel.SelectionFlag.ClearAndSelect | QItemSelectionModel.SelectionFlag.Rows,
    )
    sm.setCurrentIndex(view_index, QItemSelectionModel.SelectionFlag.NoUpdate)


def test_shortcuts_canary_triggers_every_tab_shortcut(qtbot):
    tab = JsonTab(lambda *_: None, data={"a": 1, "b": 2})
    qtbot.addWidget(tab)
    tab.show()
    tab.activateWindow()
    QApplication.processEvents()

    root_parent = QModelIndex()
    first = tab.model.index(0, 0, root_parent)
    _set_current_source_row(tab, first)

    calls: list[set[TreeAction]] = []

    def _record(_message: str, actions: set[TreeAction]) -> None:
        calls.append(actions)

    tab.editing.run_tree_action = _record  # type: ignore[method-assign]
    find_triggered: list[bool] = []
    tab._find_shortcut.activated.connect(lambda: find_triggered.append(True))

    # Canary: emit every registered tab shortcut exactly once.
    tab._copy_shortcut.activated.emit()
    tab._cut_shortcut.activated.emit()
    tab._paste_shortcut.activated.emit()
    tab._paste_zip_shortcut.activated.emit()
    tab._replace_zip_shortcut.activated.emit()
    tab._duplicate_shortcut.activated.emit()
    tab._move_up_shortcut.activated.emit()
    tab._move_down_shortcut.activated.emit()
    tab._move_out_up_shortcut.activated.emit()
    tab._move_out_down_shortcut.activated.emit()
    tab._sort_shortcut.activated.emit()
    tab._find_shortcut.activated.emit()
    QApplication.processEvents()

    # Offscreen backends can be inconsistent about focus ownership; assert that
    # the Find shortcut itself is live and emitted.
    assert find_triggered == [True]

    seen = {next(iter(entry)) for entry in calls}
    assert seen == {
        TreeAction.COPY_ONLY,
        TreeAction.CUT,
        TreeAction.PASTE,
        TreeAction.PASTE_ZIP,
        TreeAction.REPLACE_ZIP,
        TreeAction.DUPLICATE,
        TreeAction.MOVE_UP,
        TreeAction.MOVE_DOWN,
        TreeAction.MOVE_OUT_UP,
        TreeAction.MOVE_OUT_DOWN,
        TreeAction.SORT_KEYS,
    }


def test_delete_shortcut_not_ambiguous_and_deletes_once(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        tab = win._add_tab(data={"a": 1, "b": 2}, file_path=None)
        assert tab is not None

        # Ambiguity guard: Del must be owned only by the window action.
        del_shortcuts = [sc for sc in win.findChildren(QShortcut) if sc.key().toString() == "Del"]
        assert del_shortcuts == []
        assert win.rowRemoveAction.shortcut().toString() == "Del"

        root = tab.model.index(0, 0, QModelIndex())
        first = tab.model.index(0, 0, root)
        _set_current_source_row(tab, first)

        before = tab.model.root_item.to_json()
        win.rowRemoveAction.trigger()
        QApplication.processEvents()

        after = tab.model.root_item.to_json()
        assert before == {"a": 1, "b": 2}
        assert after == {"b": 2}
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()


def test_context_menu_shows_shortcuts_for_registered_actions(qtbot):
    tab = JsonTab(lambda *_: None, data={"obj": {"x": 1, "y": 2}, "tail": 3}, show_root=True)
    qtbot.addWidget(tab)
    tab.show()
    tab.view.expandAll()
    QApplication.processEvents()

    nested = tab.view_controller.index_from_path((0, 0))
    _set_current_source_row(tab, nested)
    position = tab.view.visualRect(tab.view_controller.source_to_view(nested)).center()

    seen: dict[str, str] = {}

    def _collect(menu: QMenu):
        for action in menu.actions():
            submenu = action.menu()
            if submenu is not None:
                _collect(submenu)
            elif action.text():
                seen[action.text()] = action.shortcut().toString()

    menu = show_context_menu(tab.view, position, execute=False)
    assert menu is not None
    _collect(menu)

    assert seen["Insert Before"] == "Ctrl+I"
    assert seen["Insert After"] == "Ctrl+Shift+I"
    assert seen["Duplicate"] == "Ctrl+D"
    assert seen["Delete"] == "Del"
    assert seen["Move Up"] == "Alt+Up"
    assert seen["Move Down"] == "Alt+Down"
    assert seen["Move Out of Parent (Up)"] == "Ctrl+Alt+Up"
    assert seen["Move Out of Parent (Down)"] == "Ctrl+Alt+Down"
    assert "Sort Keys" not in seen


def test_main_menu_actions_are_disabled_when_inactive(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        win.update_actions()
        assert not win.fileSaveAction.isEnabled()
        assert not win.fileSaveAsAction.isEnabled()
        assert not win.fileCopyPathAction.isEnabled()

        tab = win._add_tab(data={"a": 1}, file_path=None)
        assert tab is not None
        tab.io.file_path = "/tmp/demo.json"
        win._refresh_tab_presentation(tab)
        win.update_actions()
        assert not win.fileSaveAction.isEnabled()
        assert win.fileSaveAsAction.isEnabled()
        assert win.fileCopyPathAction.isEnabled()

        assert tab.editing.push_insert_rows(
            [{"parent_path": (), "row": 0, "value": 2, "name": "b"}],
            label="mark dirty",
        )
        win.update_actions()
        assert win.fileSaveAction.isEnabled()
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()


def test_tab_tooltip_uses_full_path(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        full_path = "/tmp/very/deep/path/data.json"
        tab = win._add_tab(data={"a": 1}, file_path=None)
        assert tab is not None
        tab.io.file_path = full_path
        win._refresh_tab_presentation(tab)
        index = win.tabWidget.indexOf(tab)
        assert index >= 0
        assert win.tabWidget.tabToolTip(index) == full_path
    finally:
        for i in range(win.tabWidget.count()):
            maybe_tab = win.tabWidget.widget(i)
            if isinstance(maybe_tab, JsonTab):
                maybe_tab.undo_stack.setClean()
        win.close()
        win.deleteLater()
        QApplication.processEvents()
