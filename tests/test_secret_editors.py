from PySide6.QtCore import QEvent, QModelIndex, Qt
from PySide6.QtGui import QFocusEvent
from PySide6.QtWidgets import QAbstractItemView, QApplication, QDialogButtonBox, QLineEdit, QPushButton

from dialogs.qmultiline_dlg import QMultilineDialog
from documents.tab import JsonTab


def test_secret_line_editor_is_password_with_toggle(qtbot):
    tab = JsonTab(lambda *_: None, data={"password": "hunter2"})
    qtbot.addWidget(tab)
    tab.show()

    src = tab.model.index(0, 2, QModelIndex())
    idx = tab.view_controller.source_to_view(src)
    tab.view.setCurrentIndex(idx)
    tab.view.edit(idx)

    qtbot.waitUntil(lambda: tab.view.findChild(QLineEdit) is not None and tab.view.findChild(QPushButton) is not None)
    editor = tab.view.findChild(QLineEdit)
    assert editor is not None
    assert editor.echoMode() == QLineEdit.EchoMode.Password

    toggle = tab.view.findChild(QPushButton)
    assert toggle is not None
    assert toggle.text() == "Hidden"
    qtbot.mouseClick(toggle, Qt.MouseButton.LeftButton)
    assert toggle.text() == "Shown"
    assert editor.echoMode() == QLineEdit.EchoMode.Normal


def test_secret_text_editor_masks_and_reveals(qtbot):
    value = "line1\nline2"
    tab = JsonTab(lambda *_: None, data={"private_key": value})
    qtbot.addWidget(tab)
    tab.show()

    src = tab.model.index(0, 2, QModelIndex())
    idx = tab.view_controller.source_to_view(src)
    tab.view.setCurrentIndex(idx)
    tab.view.edit(idx)

    qtbot.waitUntil(lambda: tab.findChild(QMultilineDialog) is not None)
    dlg = tab.findChild(QMultilineDialog)
    assert dlg is not None
    assert dlg.windowTitle() == "Edit Secret Text"
    assert dlg.editor.toPlainText() == value

    dlg.editor.setPlainText("line1\nline2\nline3")
    ok = dlg.buttonBox.button(QDialogButtonBox.StandardButton.Ok)
    assert ok is not None
    qtbot.mouseClick(ok, Qt.MouseButton.LeftButton)

    src_after = tab.model.index(0, 2, QModelIndex())
    assert str(src_after.data(Qt.ItemDataRole.EditRole) or "") == "line1\nline2\nline3"


def test_secret_editor_closes_on_focus_out(qtbot):
    tab = JsonTab(lambda *_: None, data={"password": "hunter2"})
    qtbot.addWidget(tab)
    tab.show()

    src = tab.model.index(0, 2, QModelIndex())
    idx = tab.view_controller.source_to_view(src)
    tab.view.setCurrentIndex(idx)
    tab.view.edit(idx)

    qtbot.waitUntil(lambda: tab.view.findChild(QLineEdit) is not None)
    editor = tab.view.findChild(QLineEdit)
    assert editor is not None

    QApplication.sendEvent(editor, QFocusEvent(QEvent.Type.FocusOut, Qt.FocusReason.MouseFocusReason))

    qtbot.waitUntil(lambda: tab.view.state() != QAbstractItemView.State.EditingState)
