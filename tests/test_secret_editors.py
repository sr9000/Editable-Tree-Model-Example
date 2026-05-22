from PySide6.QtCore import QModelIndex, QEvent, Qt
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QApplication, QAbstractItemView, QLineEdit, QPlainTextEdit, QToolButton

from documents.tab import JsonTab
from settings import SECRET_MASK_CHAR


def test_secret_line_editor_is_password_with_toggle(qtbot):
    tab = JsonTab(lambda *_: None, data={"password": "hunter2"})
    qtbot.addWidget(tab)
    tab.show()

    src = tab.model.index(0, 2, QModelIndex())
    idx = tab._source_to_view(src)
    tab.view.setCurrentIndex(idx)
    tab.view.edit(idx)

    qtbot.waitUntil(lambda: tab.view.findChild(QLineEdit) is not None)
    editor = tab.view.findChild(QLineEdit)
    assert editor is not None
    assert editor.echoMode() == QLineEdit.EchoMode.Password

    toggle = next((a for a in editor.actions() if a.text() == "Show"), None)
    assert toggle is not None
    toggle.trigger()
    assert editor.echoMode() == QLineEdit.EchoMode.Normal


def test_secret_text_editor_masks_and_reveals(qtbot):
    value = "line1\nline2"
    tab = JsonTab(lambda *_: None, data={"private_key": value})
    qtbot.addWidget(tab)
    tab.show()

    src = tab.model.index(0, 2, QModelIndex())
    idx = tab._source_to_view(src)
    tab.view.setCurrentIndex(idx)
    tab.view.edit(idx)

    qtbot.waitUntil(lambda: tab.view.findChild(QPlainTextEdit) is not None)
    text_edit = tab.view.findChild(QPlainTextEdit)
    button = tab.view.findChild(QToolButton)
    assert text_edit is not None
    assert button is not None
    assert value not in text_edit.toPlainText()
    assert SECRET_MASK_CHAR in text_edit.toPlainText()

    qtbot.mouseClick(button, Qt.MouseButton.LeftButton)
    assert text_edit.toPlainText() == value


def test_secret_editor_closes_on_focus_out(qtbot):
    tab = JsonTab(lambda *_: None, data={"password": "hunter2"})
    qtbot.addWidget(tab)
    tab.show()

    src = tab.model.index(0, 2, QModelIndex())
    idx = tab._source_to_view(src)
    tab.view.setCurrentIndex(idx)
    tab.view.edit(idx)

    qtbot.waitUntil(lambda: tab.view.findChild(QLineEdit) is not None)
    editor = tab.view.findChild(QLineEdit)
    assert editor is not None

    QApplication.sendEvent(editor, QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.MouseFocusReason))

    qtbot.waitUntil(lambda: tab.view.state() != QAbstractItemView.State.EditingState)
