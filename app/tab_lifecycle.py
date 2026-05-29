"""Presenter for tab add/close/reopen lifecycle (kill-gods Phase 3.1).

Owns the ``_closed_tabs_stack`` and the add/close/reopen flows that used to
live directly on ``MainWindow``. ``MainWindow`` retains thin wrappers and a
deprecated ``_closed_tabs_stack`` property pointing at this presenter for
backwards compatibility with the existing test suite.

The presenter receives the Designer-generated ``QTabWidget`` (which stays
owned by ``MainWindow``) plus a reference to the window so it can reach the
other already-extracted controllers (theme/font/schema-pool/validation
dock/undo binding/status bar) without duplicating their state.
"""

from __future__ import annotations

from PySide6.QtCore import QObject
from PySide6.QtWidgets import QMessageBox, QTabWidget

import state.view_state as view_state
from documents.document_protocol import Document
from documents.tab_dependencies import JsonTabServices
from documents.tab_factory import create_tab
from documents.tab_marker import JsonTabWidgetMarker


class _MainWindowJsonTabHost:
    def __init__(self, window) -> None:
        self._window = window

    def refresh_actions(self) -> None:
        self._window.update_actions()

    def show_status_message(self, message: str, timeout_ms: int = 0) -> None:
        self._window.statusBar.showMessage(message, timeout_ms)

    def show_permanent_message(self, message: str) -> None:
        self._window.statusBar.showMessage(message, 0)


class TabLifecyclePresenter(QObject):
    """Owns ``_closed_tabs_stack`` and add/close/reopen flows for ``MainWindow``."""

    MAX_CLOSED_TABS = 10

    def __init__(self, tab_widget: QTabWidget, main_window) -> None:
        super().__init__(main_window)
        self._tab_widget = tab_widget
        self._win = main_window
        self.closed_tabs_stack: list[dict] = []

    # ── presentation helpers ──────────────────────────────────────────────

    def refresh_tab_presentation(self, tab: Document) -> None:
        index = self._tab_widget.indexOf(tab)
        if index < 0:
            return
        self._tab_widget.setTabText(index, tab.display_name())
        self._tab_widget.setTabToolTip(index, tab.file_path or "Untitled")

    def on_tab_dirty(self, tab: Document) -> None:
        self.refresh_tab_presentation(tab)
        self._win.update_actions()

    # ── add ───────────────────────────────────────────────────────────────

    def add_tab(
        self,
        *,
        data=None,
        file_path: str | None = None,
        save_format: str | None = None,
    ) -> Document | None:
        from state.validation_settings import auto_rescan_enabled

        win = self._win
        try:
            tab = create_tab(
                data=data,
                file_path=file_path,
                show_root=True,
                parent=win,
                save_format=save_format,
                services=JsonTabServices(
                    host=_MainWindowJsonTabHost(win),
                    theme=win._theme,
                    icon_provider=win._icon_provider,
                ),
            )
        except Exception as exc:  # noqa: BLE001
            QMessageBox.critical(win, "Error", f"Failed to create tab:\n{exc}")
            return None

        tab.validation.set_auto_rescan(auto_rescan_enabled())

        tab_index = self._tab_widget.addTab(tab, tab.display_name())
        self._tab_widget.setCurrentIndex(tab_index)
        self.refresh_tab_presentation(tab)
        win.fonts.subscribe(tab)
        tab.dirtyChanged.connect(lambda _dirty, t=tab: self.on_tab_dirty(t))

        tab.view_controller.request_expand_all()
        tab.resize_key_columns()
        if tab.root_index().isValid():
            tab.view_controller.request_select_paths([()])
        view_state.restore(tab)
        # Re-broadcast: ``view_state.restore`` may have rewritten ``_font_pt``
        # from a previously-saved per-tab value; the global controller wins.
        win.fonts.subscribe(tab)

        win._bind_undo_signals(tab)
        win.update_actions()
        return tab

    # ── current-tab change ────────────────────────────────────────────────

    def on_tab_changed(self, _index: int) -> None:
        win = self._win
        tab = win._current_tab()
        win._bind_undo_signals(tab)
        win._bind_validation_status(tab)
        win.validation_dock.attach_tab(tab)
        if tab is not None:
            tab.resize_key_columns()
        if win._history_dialog is not None and win._history_dialog.isVisible():
            if tab is not None and win._history_view is not None:
                win._history_view.setStack(tab.undo_stack)
        win.update_actions()

    # ── close ─────────────────────────────────────────────────────────────

    def close_current_tab(self) -> None:
        win = self._win
        tab = win._current_tab()
        if tab is None:
            return
        index = self._tab_widget.indexOf(tab)
        if index >= 0:
            self.close_tab(index)

    def close_tab(self, index: int) -> None:
        win = self._win
        widget = self._tab_widget.widget(index)

        snapshot = None
        if isinstance(widget, JsonTabWidgetMarker):
            was_dirty = widget.is_dirty
            if not win._confirm_close(widget):
                return
            # Build reopen snapshot: if user discarded dirty edits, remember file path only.
            if was_dirty and widget.is_dirty:
                # Discard chosen — don't resurrect dirty state on reopen.
                if widget.file_path:
                    snapshot = {
                        "data": None,
                        "file_path": widget.file_path,
                        "save_format": widget.save_format,
                    }
            else:
                try:
                    snap_data = widget.root_data()
                except Exception:  # noqa: BLE001
                    snap_data = {}
                snapshot = {
                    "data": snap_data,
                    "file_path": widget.file_path,
                    "save_format": widget.save_format,
                }
            win._schema_tab_pool.unregister(widget)
            view_state.save(widget)
        if widget is win._bound_undo_tab:
            win._bind_undo_signals(None)
        self._tab_widget.removeTab(index)
        if widget is not None:
            widget.deleteLater()

        if snapshot is not None:
            self.closed_tabs_stack.append(snapshot)
            if len(self.closed_tabs_stack) > self.MAX_CLOSED_TABS:
                self.closed_tabs_stack.pop(0)

        win.update_actions()
        current = win._current_tab()
        win._bind_undo_signals(current)
        win._bind_validation_status(current)
        win.validation_dock.attach_tab(current)

    # ── reopen ────────────────────────────────────────────────────────────

    def reopen_closed_tab(self) -> None:
        win = self._win
        if not self.closed_tabs_stack:
            return
        snapshot = self.closed_tabs_stack.pop()
        data = snapshot.get("data")
        file_path = snapshot.get("file_path")
        save_format = snapshot.get("save_format")
        if data is None:
            # User had discarded dirty changes — reload clean from disk if possible.
            if file_path:
                win._open_path(file_path)
            else:
                self.add_tab(data={})
        else:
            self.add_tab(data=data, file_path=file_path, save_format=save_format)
        win.statusBar.showMessage("Reopened closed tab", 2000)
        win.update_actions()
