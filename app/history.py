from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence
from PySide6.QtWidgets import QDialog, QUndoView, QVBoxLayout

from documents.document_protocol import Document


def setup_history_menu(window) -> None:
    window.historyMenu = window.menuBar.addMenu("&History")

    window.undoAction = QAction("&Undo", window)
    window.undoAction.setShortcut(QKeySequence.StandardKey.Undo)
    window.undoAction.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
    window.undoAction.triggered.connect(lambda: do_undo(window))
    window.undoAction.setEnabled(False)

    window.redoAction = QAction("&Redo", window)
    window.redoAction.setShortcuts([QKeySequence.StandardKey.Redo, QKeySequence("Ctrl+Y")])
    window.redoAction.setShortcutContext(Qt.ShortcutContext.ApplicationShortcut)
    window.redoAction.triggered.connect(lambda: do_redo(window))
    window.redoAction.setEnabled(False)

    window.showHistoryAction = QAction("Show History...", window)
    window.showHistoryAction.triggered.connect(lambda: show_history_dialog(window))
    window.showHistoryAction.setEnabled(False)

    window.historyMenu.addAction(window.undoAction)
    window.historyMenu.addAction(window.redoAction)
    window.historyMenu.addSeparator()
    window.historyMenu.addAction(window.showHistoryAction)


def bind_undo_signals(window, tab: Document | None) -> None:
    previous = window._bound_undo_tab
    if previous is not None:
        try:
            previous.undo_stack.canUndoChanged.disconnect(window.undoAction.setEnabled)
            previous.undo_stack.canRedoChanged.disconnect(window.redoAction.setEnabled)
        except (TypeError, RuntimeError):
            pass

    window._bound_undo_tab = tab

    if tab is not None:
        tab.undo_stack.canUndoChanged.connect(window.undoAction.setEnabled)
        tab.undo_stack.canRedoChanged.connect(window.redoAction.setEnabled)
        window.undoAction.setEnabled(tab.undo_stack.canUndo())
        window.redoAction.setEnabled(tab.undo_stack.canRedo())
        window.showHistoryAction.setEnabled(True)
    else:
        window.undoAction.setEnabled(False)
        window.redoAction.setEnabled(False)
        window.showHistoryAction.setEnabled(False)


def do_undo(window) -> None:
    tab = window._current_tab()
    if tab is not None:
        tab.undo_stack.undo()


def do_redo(window) -> None:
    tab = window._current_tab()
    if tab is not None:
        tab.undo_stack.redo()


def show_history_dialog(window) -> None:
    tab = window._current_tab()
    if tab is None:
        return

    if window._history_dialog is None:
        window._history_dialog = QDialog(window)
        window._history_dialog.setWindowTitle("Undo / Redo History")
        window._history_dialog.resize(320, 400)
        layout = QVBoxLayout(window._history_dialog)
        window._history_view = QUndoView(window._history_dialog)
        window._history_view.setEmptyLabel("<initial state>")
        layout.addWidget(window._history_view)

    window._history_view.setStack(tab.undo_stack)
    window._history_dialog.show()
    window._history_dialog.raise_()
    window._history_dialog.activateWindow()
