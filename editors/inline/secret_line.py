from __future__ import annotations

from PySide6.QtCore import QEvent, QObject, QPersistentModelIndex, Qt
from PySide6.QtGui import QFont, QFontMetrics
from PySide6.QtWidgets import QApplication, QHBoxLayout, QLineEdit, QPushButton, QWidget

from editors.context import ValueDelegateProtocol
from editors.inline.caps_safe_line import _CapsLockSafeLineEdit
from settings import SECRET_HIDE_ON_FOCUS_OUT


class _SecretLineEdit(QWidget):
    """Inline editor for SECRET_LINE values with a reveal/hide toggle."""

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self._revealed = False
        self._line_edit = _CapsLockSafeLineEdit(self)
        self._line_edit.setEchoMode(QLineEdit.EchoMode.Password)
        self._toggle_btn = QPushButton(self)
        self._toggle_btn.setCheckable(True)
        self._toggle_btn.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        self._toggle_btn.setAutoDefault(False)
        self._toggle_btn.setDefault(False)
        self._toggle_btn.toggled.connect(self._set_revealed)

        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(0, 0, 0, 0)
        self._layout.setSpacing(4)
        self._layout.addWidget(self._toggle_btn)
        self._layout.addWidget(self._line_edit)

        self.setFocusProxy(self._line_edit)
        self._sync_toggle_button()

        # Bubble up line-edit signals so Qt's delegate infrastructure is happy.
        self.textChanged = self._line_edit.textChanged
        self.textEdited = self._line_edit.textEdited
        self.returnPressed = self._line_edit.returnPressed

        self._update_button_width()

    def text(self) -> str:
        return self._line_edit.text()

    def setText(self, text: str) -> None:
        self._line_edit.setText(text)

    def _set_revealed(self, checked: bool) -> None:
        self._revealed = bool(checked)
        self._line_edit.setEchoMode(QLineEdit.EchoMode.Normal if self._revealed else QLineEdit.EchoMode.Password)
        self._sync_toggle_button()

    def _sync_toggle_button(self) -> None:
        label = "Shown" if self._revealed else "Hidden"
        self._toggle_btn.setText(label)
        self._toggle_btn.setToolTip(label)
        if self._toggle_btn.isChecked() != self._revealed:
            self._toggle_btn.blockSignals(True)
            self._toggle_btn.setChecked(self._revealed)
            self._toggle_btn.blockSignals(False)
        self._update_button_width()

    def _update_button_width(self) -> None:
        metrics = QFontMetrics(self._toggle_btn.font())
        width = max(metrics.horizontalAdvance("Hidden"), metrics.horizontalAdvance("Shown")) + 18
        self._toggle_btn.setFixedWidth(width)

    def setFont(self, font: QFont) -> None:
        super().setFont(font)
        self._line_edit.setFont(font)
        self._toggle_btn.setFont(font)
        self._update_button_width()


class _SecretEditorWatcher(QObject):
    """Hides a secret editor on focus-out / app-deactivation transitions."""

    def __init__(self, delegate: ValueDelegateProtocol, editor: QWidget, index: QPersistentModelIndex):
        super().__init__(editor)
        self._delegate = delegate
        self._editor = editor
        self._index = index

        # Listen for application-wide focus transitions to hide sensitive inputs immediately
        app = QApplication.instance()
        if app is not None:
            app.applicationStateChanged.connect(self._on_app_state_changed)

    def cleanup(self) -> None:
        app = QApplication.instance()
        if app is not None:
            try:
                app.applicationStateChanged.disconnect(self._on_app_state_changed)
            except (RuntimeError, TypeError):
                pass

    def eventFilter(self, watched, event):  # type: ignore[override]
        if event.type() == QEvent.Type.FocusOut and SECRET_HIDE_ON_FOCUS_OUT:
            self._delegate._finalize_secret_editor(self._editor, self._index)
        return super().eventFilter(watched, event)

    def _on_app_state_changed(self, state) -> None:
        if SECRET_HIDE_ON_FOCUS_OUT and state != Qt.ApplicationState.ApplicationActive:
            self._delegate._finalize_secret_editor(self._editor, self._index)
