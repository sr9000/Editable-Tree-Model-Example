from __future__ import annotations

from PySide6.QtCore import QItemSelectionModel, QModelIndex, Qt
from PySide6.QtGui import QShortcut
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from documents.tab import JsonTab


def _set_current_source_row(tab: JsonTab, source_index: QModelIndex) -> None:
    view_index = tab._source_to_view(source_index)
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

    calls: list[set[str]] = []

    def _record(_message: str, **flags) -> None:
        calls.append({k for k, v in flags.items() if v})

    tab._run_tree_action = _record  # type: ignore[method-assign]

    # Canary: emit every registered tab shortcut exactly once.
    tab._copy_shortcut.activated.emit()
    tab._cut_shortcut.activated.emit()
    tab._paste_shortcut.activated.emit()
    tab._paste_zip_shortcut.activated.emit()
    tab._replace_zip_shortcut.activated.emit()
    tab._duplicate_shortcut.activated.emit()
    tab._move_up_shortcut.activated.emit()
    tab._move_down_shortcut.activated.emit()
    tab._sort_shortcut.activated.emit()
    tab._find_shortcut.activated.emit()
    QApplication.processEvents()

    assert tab.search_edit.hasFocus()

    seen = {next(iter(entry)) for entry in calls}
    assert seen == {
        "copy_only",
        "cut",
        "paste",
        "paste_zip",
        "replace_zip",
        "duplicate",
        "move_up",
        "move_down",
        "sort_keys",
    }


def test_delete_shortcut_not_ambiguous_and_deletes_once(qtbot):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        tab = win._add_tab(data={"a": 1, "b": 2}, file_path=None)
        assert tab is not None

        # Ambiguity guard: Del must be owned only by the window action.
        del_shortcuts = [
            sc
            for sc in win.findChildren(QShortcut)
            if sc.key().toString() == "Del"
        ]
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
