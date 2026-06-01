"""Presenter for app-wide settings (kill-gods Phase 3.2).

Wraps the File-menu "Edit Warning Limits" submenu and the "Secret word
prefixes..." dialog action. The presenter owns the QAction/QMenu instances;
tests access them directly via ``win._app_settings.limit_string_action`` etc.
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtGui import QAction
from PySide6.QtWidgets import QDialog, QInputDialog, QMenu

from app.dialogs.secret_prefixes_dlg import SecretPrefixesDialog
from state.edit_limits import (
    get_attach_file_warning_limit_bytes,
    get_binary_edit_warning_limit_bytes,
    get_multiline_edit_warning_limit_chars,
    get_string_edit_warning_limit_chars,
    set_attach_file_warning_limit_bytes,
    set_binary_edit_warning_limit_bytes,
    set_multiline_edit_warning_limit_chars,
    set_string_edit_warning_limit_chars,
)
from state.secret_settings import get_secret_word_prefixes, set_secret_word_prefixes
from units import counts, format_bytes


class AppSettingsPresenter(QObject):
    """Owns the edit-warning-limits submenu and the secret-prefixes action."""

    def __init__(self, main_window) -> None:
        super().__init__(main_window)
        self._win = main_window
        self._build_secret_prefixes_action()
        self._build_edit_limits_menu()

    # ── secret prefixes action ───────────────────────────────────────────

    def _build_secret_prefixes_action(self) -> None:
        win = self._win
        self.secret_prefixes_action = QAction(win.tr("Secret word prefixes..."), win)
        self.secret_prefixes_action.triggered.connect(self._edit_secret_prefixes)
        win.fileMenu.insertAction(win.appExitAction, self.secret_prefixes_action)

    def _edit_secret_prefixes(self) -> None:
        win = self._win
        dlg = SecretPrefixesDialog(get_secret_word_prefixes(), win)
        if dlg.exec() != QDialog.DialogCode.Accepted:
            return
        prefixes = set_secret_word_prefixes(dlg.prefixes())
        win.statusBar.showMessage(win.tr("Updated {n} secret prefixes").format(n=len(prefixes)), 2000)

    # ── edit-warning-limits submenu ──────────────────────────────────────

    def _build_edit_limits_menu(self) -> None:
        win = self._win
        self.limits_menu = QMenu(win.tr("Edit Warning Limits"), win)
        self.limit_string_action = QAction(win)
        self.limit_multiline_action = QAction(win)
        self.limit_binary_action = QAction(win)
        self.limit_attach_action = QAction(win)

        self.limit_string_action.triggered.connect(self._set_string_warning_limit)
        self.limit_multiline_action.triggered.connect(self._set_multiline_warning_limit)
        self.limit_binary_action.triggered.connect(self._set_binary_warning_limit)
        self.limit_attach_action.triggered.connect(self._set_attach_warning_limit)

        self.limits_menu.addAction(self.limit_string_action)
        self.limits_menu.addAction(self.limit_multiline_action)
        self.limits_menu.addAction(self.limit_binary_action)
        self.limits_menu.addAction(self.limit_attach_action)
        self.limits_menu.aboutToShow.connect(self.refresh_edit_limits_menu_entries)
        self.refresh_edit_limits_menu_entries()

        win.fileMenu.insertMenu(win.appExitAction, self.limits_menu)
        win.fileMenu.insertSeparator(win.appExitAction)

    def refresh_edit_limits_menu_entries(self) -> None:
        win = self._win
        string_limit = get_string_edit_warning_limit_chars()
        multiline_limit = get_multiline_edit_warning_limit_chars()
        binary_limit = get_binary_edit_warning_limit_bytes()
        attach_limit = get_attach_file_warning_limit_bytes()

        self.limit_string_action.setText(
            win.tr("String edit limit... ({value} chars)").format(value=counts(string_limit))
        )
        self.limit_multiline_action.setText(
            win.tr("Multiline text limit... ({value} chars)").format(value=counts(multiline_limit))
        )
        self.limit_binary_action.setText(
            win.tr("Bytes edit limit... ({value})").format(value=format_bytes(binary_limit))
        )
        self.limit_attach_action.setText(
            win.tr("Attach file size limit... ({value})").format(value=format_bytes(attach_limit))
        )

    def _prompt_limit_value(self, *, title: str, label: str, current: int) -> int | None:
        value, ok = QInputDialog.getInt(self._win, title, label, current, 1, 2_147_483_647, 1)
        if not ok:
            return None
        return int(value)

    def _set_string_warning_limit(self) -> None:
        win = self._win
        current = get_string_edit_warning_limit_chars()
        value = self._prompt_limit_value(
            title=win.tr("String Edit Warning Limit"),
            label=win.tr("Warn when string length exceeds (chars):"),
            current=current,
        )
        if value is None:
            return
        set_string_edit_warning_limit_chars(value)
        self.refresh_edit_limits_menu_entries()
        win.statusBar.showMessage(win.tr("Updated string edit warning limit"), 2000)

    def _set_multiline_warning_limit(self) -> None:
        win = self._win
        current = get_multiline_edit_warning_limit_chars()
        value = self._prompt_limit_value(
            title=win.tr("Multiline Edit Warning Limit"),
            label=win.tr("Warn when multiline length exceeds (chars):"),
            current=current,
        )
        if value is None:
            return
        set_multiline_edit_warning_limit_chars(value)
        self.refresh_edit_limits_menu_entries()
        win.statusBar.showMessage(win.tr("Updated multiline edit warning limit"), 2000)

    def _set_binary_warning_limit(self) -> None:
        win = self._win
        current = get_binary_edit_warning_limit_bytes()
        value = self._prompt_limit_value(
            title=win.tr("Bytes Edit Warning Limit"),
            label=win.tr("Warn when binary size exceeds (bytes):"),
            current=current,
        )
        if value is None:
            return
        set_binary_edit_warning_limit_bytes(value)
        self.refresh_edit_limits_menu_entries()
        win.statusBar.showMessage(win.tr("Updated bytes edit warning limit"), 2000)

    def _set_attach_warning_limit(self) -> None:
        win = self._win
        current = get_attach_file_warning_limit_bytes()
        value = self._prompt_limit_value(
            title=win.tr("Attach File Warning Limit"),
            label=win.tr("Warn when attaching file larger than (bytes):"),
            current=current,
        )
        if value is None:
            return
        set_attach_file_warning_limit_bytes(value)
        self.refresh_edit_limits_menu_entries()
        win.statusBar.showMessage(win.tr("Updated attach file warning limit"), 2000)
