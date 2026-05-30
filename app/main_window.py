# Ported from: https://code.qt.io/cgit/qt/qtbase.git/tree/examples/widgets/itemviews/editabletreemodel

from pathlib import Path

from PySide6.QtCore import QByteArray, QMimeData, QSettings, QTimer
from PySide6.QtGui import QAction, QFont, QFontDatabase, QKeySequence
from PySide6.QtWidgets import (
    QApplication,
    QDialog,
    QFileDialog,
    QFontDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QTreeView,
    QUndoView,
)

import state.view_state as view_state
from app.app_settings import AppSettingsPresenter
from app.close_confirm import confirm_close
from app.font_controller import FontController
from app.history import bind_undo_signals, setup_history_menu
from app.main_window_actions import setup_connections as setup_main_window_connections
from app.main_window_actions import update_actions as update_main_window_actions
from app.recent_files import push_recent, refresh_recent_menu
from app.schema_tab_pool import SchemaTabPool
from app.tab_lifecycle import TabLifecyclePresenter
from app.theme_controller import ThemeController
from app.validation_presenter import DockValidationPresenter
from documents.document_protocol import Document
from documents.tab_marker import JsonTabWidgetMarker
from io_formats.load import load_file_with_format
from mainwindow import Ui_MainWindow
from settings import APPLICATION_ID, WINDOW_DEFAULT_SIZE
from tree_actions.clipboard import clipboard_to_tab_data
from tree_actions.field_case import FIELD_CASE_LABELS, FIELD_CASE_ORDER, FieldCase
from tree_actions.structure import collapse_all, delete_selection, expand_all
from tree_actions.structure import switch_document_case as switch_case_document


class MainWindow(QMainWindow, Ui_MainWindow):

    @staticmethod
    def _coerce_bool(value, *, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            lowered = value.strip().casefold()
            if lowered in {"1", "true", "yes", "on"}:
                return True
            if lowered in {"0", "false", "no", "off"}:
                return False
        return default

    @staticmethod
    def _normalize_font_for_dialog(seed: QFont) -> QFont:
        font = QFont(seed)
        if font.pointSizeF() <= 0:
            font.setPointSize(10)
        return font

    @staticmethod
    def _unpack_font_dialog_result(result) -> tuple[QFont | None, bool]:
        # PySide can expose getFont() tuple order as (QFont, bool) or (bool, QFont)
        # depending on binding/runtime details.
        if isinstance(result, tuple) and len(result) == 2:
            first, second = result
            if isinstance(first, QFont) and isinstance(second, bool):
                return first, second
            if isinstance(first, bool) and isinstance(second, QFont):
                return second, first
        return None, False

    def __init__(self, yaml_filename: str, parent=None):
        super().__init__(parent)
        self.setupUi(self)
        self.setAcceptDrops(True)
        self._history_dialog: QDialog | None = None
        self._history_view: QUndoView | None = None
        self._bound_undo_tab: Document | None = None
        self._startup_window_mode: str = "normal"
        self._settings = QSettings(APPLICATION_ID, "app")
        # All font preferences (regular family, monospace family, editor
        # point size, monospace-fields toggle) live in a single controller
        # that persists itself and broadcasts to subscribed tabs. See
        # ``app/font_controller.py``.
        self.fonts = FontController(self._settings, self)
        self._theme_controller = ThemeController(self, self._on_theme_applied)
        self._theme_registry = self._theme_controller.registry
        self._theme = self._theme_controller.theme
        self._icon_provider = self._theme_controller.icon_provider
        self._schema_tab_pool = SchemaTabPool(self)
        self._tab_lifecycle = TabLifecyclePresenter(self.tabWidget, self)
        self._theme_follow_action = self._theme_controller.follow_action
        self._recent_menu = QMenu("Recent", self)
        self.fileMenu.insertMenu(self.appExitAction, self._recent_menu)
        self.fileReloadAction = QAction("Reload from Disk", self)
        self.fileReloadAction.setShortcut(QKeySequence("Ctrl+R"))
        self.fileMenu.insertAction(self.fileSaveAction, self.fileReloadAction)
        self.fileMenu.insertSeparator(self.appExitAction)
        # ── New From Clipboard ──────────────────────────────────────────────
        self.fileNewFromClipboardAction = QAction("New From Clipboard", self)
        self.fileNewFromClipboardAction.setShortcut(QKeySequence("Ctrl+Space"))
        self.fileMenu.insertAction(self.fileOpenAction, self.fileNewFromClipboardAction)
        # ── Copy-as-YAML toggle ─────────────────────────────────────────────
        self._copyAsYamlAction = QAction(self.tr("Copy as YAML text"), self)
        self._copyAsYamlAction.setCheckable(True)
        from state.clipboard_settings import CLIPBOARD_TEXT_FORMAT_YAML, get_clipboard_text_format

        self._copyAsYamlAction.setChecked(get_clipboard_text_format() == CLIPBOARD_TEXT_FORMAT_YAML)
        self._copyAsYamlAction.toggled.connect(self._on_copy_as_yaml_toggled)
        self.fileMenu.insertAction(self.appExitAction, self._copyAsYamlAction)
        # ── Close / Reopen tabs ─────────────────────────────────────────────
        self.fileCloseTabAction = QAction("Close Tab", self)
        self.fileCloseTabAction.setShortcut(QKeySequence("Ctrl+W"))
        self.fileReopenTabAction = QAction("Reopen Closed Tab", self)
        self.fileReopenTabAction.setShortcut(QKeySequence("Ctrl+Shift+T"))
        self.fileMenu.insertAction(self.appExitAction, self.fileCloseTabAction)
        self.fileMenu.insertAction(self.appExitAction, self.fileReopenTabAction)
        self._app_settings = AppSettingsPresenter(self)
        refresh_recent_menu(self)
        self._dock_validation = DockValidationPresenter(self)
        self._setup_switch_case_actions_menu()
        self._setup_font_actions()
        self._setup_monospace_action()
        setup_history_menu(self)
        self.setup_model(yaml_filename)
        self.setup_connections()
        self._restore_window_geometry()

    def _restore_window_geometry(self) -> None:
        geometry = self._settings.value("window/geometry")
        restored = False
        if isinstance(geometry, QByteArray):
            restored = self.restoreGeometry(geometry)
        elif isinstance(geometry, (bytes, bytearray)):
            restored = self.restoreGeometry(QByteArray(bytes(geometry)))

        if not restored:
            self.resize(*WINDOW_DEFAULT_SIZE)

        if self._coerce_bool(self._settings.value("window/fullscreen", False), default=False):
            self._startup_window_mode = "fullscreen"
            return

        if self._coerce_bool(self._settings.value("window/maximized", False), default=False):
            self._startup_window_mode = "maximized"
            return

        self._startup_window_mode = "normal"

    def show_with_restored_mode(self) -> None:
        self.show()

        if self._startup_window_mode == "fullscreen":
            QTimer.singleShot(100, self.showFullScreen)
            return

        if self._startup_window_mode == "maximized":
            QTimer.singleShot(100, self.showMaximized)
            return

    @staticmethod
    def _local_paths_from_mime(mime: QMimeData) -> list[str]:
        """Return deduplicated absolute local file paths from a MIME payload."""
        paths: list[str] = []
        seen: set[str] = set()
        for url in mime.urls():
            if not url.isLocalFile():
                continue
            resolved = str(Path(url.toLocalFile()).resolve())
            if resolved in seen:
                continue
            seen.add(resolved)
            paths.append(resolved)
        return paths

    def dragEnterEvent(self, event) -> None:  # type: ignore[override]
        if self._local_paths_from_mime(event.mimeData()):
            event.acceptProposedAction()
            return
        event.ignore()

    def dropEvent(self, event) -> None:  # type: ignore[override]
        paths = self._local_paths_from_mime(event.mimeData())
        if not paths:
            event.ignore()
            return

        opened_any = False
        for path in paths:
            opened_any = self._open_path(path) or opened_any

        if opened_any:
            event.acceptProposedAction()
            return
        event.ignore()

    def _setup_validation_dock(self) -> None:  # pragma: no cover - retained for back-compat
        return

    def _setup_schemas_menu(self) -> None:  # pragma: no cover - retained for back-compat
        return

    def _rebuild_schemas_menu(self) -> None:
        self._dock_validation.rebuild_schemas_menu()

    def _on_go_to_schema_rule_requested(self, issue) -> None:
        self._dock_validation.on_go_to_schema_rule_requested(issue)

    # ── Edit-warning-limits + secret-prefixes presenter shims (Phase 3.2) ─

    @property
    def _limits_menu(self):
        return self._app_settings.limits_menu

    @property
    def _limit_string_action(self):
        return self._app_settings.limit_string_action

    @property
    def _limit_multiline_action(self):
        return self._app_settings.limit_multiline_action

    @property
    def _limit_binary_action(self):
        return self._app_settings.limit_binary_action

    @property
    def _limit_attach_action(self):
        return self._app_settings.limit_attach_action

    @property
    def _secret_prefixes_action(self):
        return self._app_settings.secret_prefixes_action

    def _refresh_edit_limits_menu_entries(self) -> None:
        self._app_settings.refresh_edit_limits_menu_entries()

    def _bind_validation_status(self, tab) -> None:
        self._dock_validation.bind_validation_status(tab)

    def _on_tab_validation_changed(self, issue_index) -> None:
        self._dock_validation.on_tab_validation_changed(issue_index)

    # ─────────────────────────────────────────────────────────────────────

    def _on_validation_issue_activated(self, issue, *, edit: bool = False) -> None:
        self._dock_validation.on_validation_issue_activated(issue, edit=edit)

    def _setup_monospace_action(self) -> None:
        self.viewMonospaceFieldsAction = QAction("Monospace Names && Values", self)
        self.viewMonospaceFieldsAction.setCheckable(True)
        self.viewMonospaceFieldsAction.setShortcut(QKeySequence("Ctrl+Shift+M"))
        self.viewMonospaceFieldsAction.setChecked(self.fonts.profile.monospace_fields_enabled)

        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.viewMonospaceFieldsAction)

    def _setup_switch_case_actions_menu(self) -> None:
        self.switchCaseMenu = QMenu(self.tr("Switch Case"), self)
        self.actionsMenu.addSeparator()
        self.actionsMenu.addMenu(self.switchCaseMenu)
        self._switch_case_actions: dict[FieldCase, QAction] = {}
        for case_style in FIELD_CASE_ORDER:
            action = QAction(FIELD_CASE_LABELS[case_style], self)
            action.setData(case_style)
            self.switchCaseMenu.addAction(action)
            self._switch_case_actions[case_style] = action

    def _setup_font_actions(self) -> None:
        self.viewSelectRegularFontAction = QAction("Select Regular Font...", self)
        self.viewSelectMonospaceFontAction = QAction("Select Monospace Font...", self)

        self.viewMenu.addSeparator()
        self.viewMenu.addAction(self.viewSelectRegularFontAction)
        self.viewMenu.addAction(self.viewSelectMonospaceFontAction)

    def _on_copy_as_yaml_toggled(self, checked: bool) -> None:
        from state.clipboard_settings import (
            CLIPBOARD_TEXT_FORMAT_JSON,
            CLIPBOARD_TEXT_FORMAT_YAML,
            set_clipboard_text_format,
        )

        set_clipboard_text_format(CLIPBOARD_TEXT_FORMAT_YAML if checked else CLIPBOARD_TEXT_FORMAT_JSON)
        fmt = "YAML" if checked else "JSON"
        self.statusBar.showMessage(self.tr("Copy text format: {fmt}").format(fmt=fmt), 2000)

    def setup_model(self, yaml_filename: str):
        if not yaml_filename:
            return
        self._open_path(yaml_filename)

    def _current_tab(self) -> Document | None:
        tab = self.tabWidget.currentWidget()
        return tab if isinstance(tab, JsonTabWidgetMarker) else None

    def _current_view(self) -> QTreeView | None:
        tab = self._current_tab()
        return tab.view if tab is not None else None

    def setup_connections(self):
        setup_main_window_connections(self)

    def _theme_tabs(self) -> list[Document]:
        tabs: list[Document] = []
        for i in range(self.tabWidget.count()):
            widget = self.tabWidget.widget(i)
            if isinstance(widget, JsonTabWidgetMarker):
                tabs.append(widget)
        return tabs

    def _on_theme_applied(self, theme, icon_provider) -> None:
        self._theme = theme
        self._icon_provider = icon_provider
        for tab in self._theme_tabs():
            tab.appearance.set_theme(theme, icon_provider)

    def _apply_theme(self, theme) -> None:
        self._theme_controller.apply_theme(theme)

    def _setup_theme_menu(self) -> None:
        self._theme_controller.setup_theme_menu(self.viewMenu)
        self._theme_follow_action = self._theme_controller.follow_action

    def _on_theme_selected(self, name: str) -> None:
        self._theme_controller.on_theme_selected(name)

    def _on_follow_system_toggled(self, checked: bool) -> None:
        self._theme_controller.on_follow_system_toggled(checked)

    def _on_theme_fs_event(self, _path: str) -> None:
        self._theme_controller.on_theme_fs_event(_path)

    def _on_system_color_scheme_changed(self, *_args) -> None:
        self._theme_controller.on_system_color_scheme_changed(*_args)

    def _bind_undo_signals(self, tab: Document | None) -> None:
        bind_undo_signals(self, tab)

    def _on_tab_changed(self, _index: int) -> None:
        self._tab_lifecycle.on_tab_changed(_index)

    def _refresh_tab_presentation(self, tab: Document) -> None:
        self._tab_lifecycle.refresh_tab_presentation(tab)

    def _add_tab(self, *, data=None, file_path: str | None = None, save_format: str | None = None) -> Document | None:
        return self._tab_lifecycle.add_tab(data=data, file_path=file_path, save_format=save_format)

    def _on_tab_dirty(self, tab: Document) -> None:
        self._tab_lifecycle.on_tab_dirty(tab)

    @property
    def _closed_tabs_stack(self) -> list[dict]:
        # Deprecated: presenter now owns the stack. Kept for tests/back-compat.
        return self._tab_lifecycle.closed_tabs_stack

    @property
    def _MAX_CLOSED_TABS(self) -> int:  # noqa: N802 — deprecated shim
        return TabLifecyclePresenter.MAX_CLOSED_TABS

    def _open_path(self, path: str) -> bool:
        resolved = str(Path(path).resolve())
        self.statusBar.showMessage(f"Loading: {resolved}", 0)
        try:
            data, source_format = load_file_with_format(resolved)
        except Exception as exc:
            self.statusBar.showMessage(f"Open failed: {resolved}", 3000)
            QMessageBox.critical(self, "Open failed", f"Could not open {resolved}:\n{exc}")
            return False

        tab = self._add_tab(data=data, file_path=resolved, save_format=source_format)
        if tab is None:
            return False
        push_recent(self, resolved)
        self.statusBar.showMessage(f"Opened: {resolved}", 2000)
        return True

    def _save_tab(self, tab: Document, *, save_as: bool = False) -> bool:
        from state.validation_settings import clear_schema_path

        if tab.is_read_only:
            return False
        old_path = tab.io.file_path
        ok = tab.save_as() if save_as else tab.save()
        if not ok:
            return False
        if save_as and isinstance(old_path, str) and tab.io.file_path and old_path != tab.io.file_path:
            view_state.discard(old_path)
            clear_schema_path(Path(old_path))
        view_state.save(tab)
        if tab.io.file_path:
            push_recent(self, tab.io.file_path)
        self._on_tab_dirty(tab)
        return True

    def _confirm_reload_dirty_tab(self, tab: Document) -> str:
        if not tab.io.dirty:
            return "reload"

        name = tab.display_name().replace(" *", "")
        box = QMessageBox(self)
        box.setWindowTitle("Reload from disk")
        box.setIcon(QMessageBox.Icon.Warning)
        box.setText(f"'{name}' has unsaved in-memory changes.")
        box.setInformativeText("Choose whether to discard memory edits or save them and overwrite disk data.")

        discard_btn = box.addButton(QMessageBox.StandardButton.Discard)
        overwrite_btn = box.addButton(QMessageBox.StandardButton.Save)
        cancel_btn = box.addButton(QMessageBox.StandardButton.Cancel)
        box.setDefaultButton(cancel_btn)
        box.exec()

        clicked = box.clickedButton()
        if clicked is discard_btn:
            return "reload"
        if clicked is overwrite_btn:
            return "overwrite"
        return "cancel"

    def _reload_tab_from_path(self, tab: Document, path: str) -> bool:
        resolved = str(Path(path).resolve())
        self.statusBar.showMessage(f"Reloading: {resolved}", 0)
        try:
            data, source_format = load_file_with_format(resolved)
        except Exception as exc:
            self.statusBar.showMessage(f"Reload failed: {resolved}", 3000)
            QMessageBox.critical(self, "Reload failed", f"Could not reload {resolved}:\n{exc}")
            return False

        root_index = tab.root_index()
        root_item = tab.root_item()
        changed = tab.editing.diff_apply(root_item, data, root_index)
        if changed:
            tab.undo_stack.clear()
        tab.undo_stack.setClean()
        tab.io.save_format = source_format
        tab.io.file_path = resolved
        tab.validation.revalidate()
        self._refresh_tab_presentation(tab)
        self.update_actions()
        self.statusBar.showMessage(f"Reloaded: {resolved}", 2000)
        return True

    def _confirm_close(self, tab: Document, *, prompt_for_untitled_nonempty: bool = True) -> bool:
        return confirm_close(self, tab, prompt_for_untitled_nonempty=prompt_for_untitled_nonempty)

    def open_file_dialog(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Open",
            "",
            "All supported (*.json *.jsonl *.ndjson *.yaml *.yml);;JSON (*.json);;JSON Lines (*.jsonl *.ndjson);;YAML (*.yaml *.yml)",
        )
        if not path:
            return
        self._open_path(path)

    def save_file(self) -> None:
        tab = self._current_tab()
        if tab is None:
            return
        self._save_tab(tab, save_as=False)

    def save_file_as(self) -> None:
        tab = self._current_tab()
        if tab is None:
            return
        self._save_tab(tab, save_as=True)

    def reload_from_disk(self) -> None:
        tab = self._current_tab()
        if tab is None or tab.is_read_only or not tab.io.file_path:
            return
        decision = self._confirm_reload_dirty_tab(tab)
        if decision == "cancel":
            return
        if decision == "overwrite" and not self._save_tab(tab, save_as=False):
            return
        self._reload_tab_from_path(tab, tab.io.file_path)

    def create_new_file(self):
        self._add_tab(data={}, file_path=None)

    def new_from_clipboard(self) -> None:
        data, save_format = clipboard_to_tab_data()
        if data is None:
            self.statusBar.showMessage("Clipboard does not contain valid JSON or YAML", 3000)
            return
        tab = self._add_tab(data=data, file_path=None, save_format=save_format)
        if tab is not None:
            self.statusBar.showMessage("New tab created from clipboard", 2000)

    def close_current_tab(self) -> None:
        self._tab_lifecycle.close_current_tab()

    def reopen_closed_tab(self) -> None:
        self._tab_lifecycle.reopen_closed_tab()

    def close_tab(self, index: int) -> None:
        self._tab_lifecycle.close_tab(index)

    def insert_child(self):
        tab = self._current_tab()
        if tab is None:
            return

        if not tab.editing.do_insert_child():
            return

        self.update_actions()

    def insert_row_before(self):
        tab = self._current_tab()
        if tab is None:
            return

        if not tab.editing.do_insert_sibling_before():
            return

        self.update_actions()

    def insert_row_after(self):
        tab = self._current_tab()
        if tab is None:
            return

        if not tab.editing.do_insert_sibling_after():
            return

        self.update_actions()

    def insert_row(self):
        # Backward-compatible helper used by old call sites.
        self.insert_row_after()

    def remove_row(self):
        view = self._current_view()
        if view is None:
            return

        if delete_selection(view):
            self.update_actions()

    def switch_document_case(self, case_style: FieldCase) -> None:
        view = self._current_view()
        if view is None:
            return
        if switch_case_document(view, case_style):
            self.statusBar.showMessage(f"Switched field names to {FIELD_CASE_LABELS[case_style]}", 1500)
            self.update_actions()

    def expand_all(self) -> None:
        view = self._current_view()
        if view is None:
            return
        expand_all(view)

    def collapse_all(self) -> None:
        view = self._current_view()
        if view is None:
            return
        collapse_all(view)

    def zoom_in(self) -> None:
        self.fonts.zoom_in()

    def zoom_out(self) -> None:
        self.fonts.zoom_out()

    def reset_zoom(self) -> None:
        self.fonts.reset_zoom()

    def set_editor_font_point_size(self, point_size: int) -> None:
        self.fonts.set_point_size(point_size)

    def toggle_monospace_fields(self, enabled: bool) -> None:
        self.fonts.set_monospace_fields_enabled(enabled)

    def set_regular_font_family(self, family: str) -> None:
        self.fonts.set_regular_family(family)

    def set_monospace_font_family(self, family: str) -> None:
        self.fonts.set_monospace_family(family)

    def select_regular_font(self) -> None:
        tab = self._current_tab()
        seed = QFont(tab.view.font()) if tab is not None else QFont(self.font())
        if self.fonts.profile.regular_family:
            seed.setFamily(self.fonts.profile.regular_family)
        seed = self._normalize_font_for_dialog(seed)
        chosen, ok = self._unpack_font_dialog_result(QFontDialog.getFont(seed, self, "Select Regular Font"))
        if not ok or chosen is None:
            return
        self.fonts.set_regular_family(chosen.family())

    def select_monospace_font(self) -> None:
        seed = QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont)
        if self.fonts.profile.monospace_family:
            seed.setFamily(self.fonts.profile.monospace_family)
        seed = self._normalize_font_for_dialog(seed)
        chosen, ok = self._unpack_font_dialog_result(QFontDialog.getFont(seed, self, "Select Monospace Font"))
        if not ok or chosen is None:
            return
        self.fonts.set_monospace_family(chosen.family())

    def update_actions(self):
        update_main_window_actions(self)

    def copy_current_file_path(self) -> None:
        """Put the absolute path of the current tab on the system clipboard."""
        tab = self._current_tab()
        if tab is None or not tab.io.file_path:
            self.statusBar.showMessage(self.tr("No file path to copy"), 2000)
            return
        QApplication.clipboard().setText(tab.io.file_path)
        self.statusBar.showMessage(self.tr("Copied: {path}").format(path=tab.io.file_path), 2000)

    def closeEvent(self, event) -> None:  # type: ignore[override]
        self._theme_controller.shutdown()
        for i in range(self.tabWidget.count() - 1, -1, -1):
            widget = self.tabWidget.widget(i)
            if isinstance(widget, JsonTabWidgetMarker) and not self._confirm_close(
                widget, prompt_for_untitled_nonempty=False
            ):
                event.ignore()
                return
            if isinstance(widget, JsonTabWidgetMarker):
                view_state.save(widget)
        self._settings.setValue("window/geometry", self.saveGeometry())
        self._settings.setValue("window/fullscreen", self.isFullScreen())
        self._settings.setValue("window/maximized", self.isMaximized())
        self._settings.setValue("validation/dock_state", self.saveState())
        self._settings.setValue("validation/dock_visible", self.validation_dock.isVisible())
        super().closeEvent(event)
