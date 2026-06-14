"""Presenter for tab add/close/reopen lifecycle (kill-gods Phase 3.1).

Owns the ``closed_tabs_stack`` and the add/close/reopen flows that used to
live directly on ``MainWindow``.

The presenter receives the Designer-generated ``QTabWidget`` (which stays
owned by ``MainWindow``) plus a reference to the window so it can reach the
other already-extracted controllers (theme/font/schema-pool/validation
dock/undo binding/status bar) without duplicating their state.
"""

from __future__ import annotations

from typing import Callable
from uuid import uuid4

from PySide6.QtCore import QObject, Qt, QTimer
from PySide6.QtWidgets import QApplication, QMessageBox, QTabWidget

import settings
import state.view_state as view_state
from app.loading.progress_dialog import LoadingProgressDialog
from documents.composition.dependencies import JsonTabServices
from documents.composition.factory import create_tab
from documents.composition.marker import JsonTabWidgetMarker
from documents.seams.document_protocol import Document
from tree.model import JsonTreeModel


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
    """Owns ``closed_tabs_stack`` and add/close/reopen flows for ``MainWindow``."""

    MAX_CLOSED_TABS = 10

    def __init__(self, tab_widget: QTabWidget, main_window) -> None:
        super().__init__(main_window)
        self._tab_widget = tab_widget
        self._win = main_window
        self.closed_tabs_stack: list[dict] = []
        self._close_progress_dialog: LoadingProgressDialog | None = None

    def _ensure_close_progress_dialog(self) -> LoadingProgressDialog:
        dialog = self._close_progress_dialog
        if dialog is None:
            dialog = LoadingProgressDialog(
                self._win,
                cancellable=False,
                delay_ms=settings.CLOSE_PROGRESS_DELAY_MS,
            )
            dialog.setWindowTitle("Closing tab")
            self._close_progress_dialog = dialog
        return dialog

    @staticmethod
    def _set_close_stage(dialog: LoadingProgressDialog, stage: str) -> None:
        try:
            dialog.set_stage(stage)
        except RuntimeError:
            pass

    @staticmethod
    def _finish_close_progress(dialog: LoadingProgressDialog, task_id: str, *, failed: bool) -> None:
        try:
            if failed:
                dialog.error(task_id)
            else:
                dialog.finish(task_id)
        except RuntimeError:
            pass

    # ── presentation helpers ──────────────────────────────────────────────

    def refresh_tab_presentation(self, tab: Document) -> None:
        index = self._tab_widget.indexOf(tab)
        if index < 0:
            return
        self._tab_widget.setTabText(index, tab.display_name())
        self._tab_widget.setTabToolTip(index, tab.io.file_path or "Untitled")

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
        prebuilt_model: JsonTreeModel | None = None,
        defer_first_presentation: bool = False,
        defer_validation_init: bool = False,
        on_presentation_complete: Callable[[Document], None] | None = None,
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
                prebuilt_model=prebuilt_model,
                defer_validation_init=defer_validation_init,
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

        if defer_first_presentation:
            QTimer.singleShot(
                0,
                lambda t=tab, cb=on_presentation_complete: self._run_initial_presentation(t, cb),
            )
        else:
            self._run_initial_presentation(tab, on_presentation_complete)
        return tab

    def _run_initial_presentation(
        self,
        tab: Document,
        on_presentation_complete: Callable[[Document], None] | None,
    ) -> None:
        win = self._win
        is_large_open = not self._should_expand_all_on_open(tab)
        if not is_large_open:
            tab.view_controller.request_expand_all()
        elif tab.root_index().isValid():
            tab.view_controller.request_expand(())

        tab.appearance.resize_key_columns()
        if tab.root_index().isValid() and not is_large_open:
            tab.view_controller.request_select_paths([()])
        view_state.restore(tab, defer_heavy=is_large_open)
        if is_large_open and tab.root_index().isValid():
            tab.view_controller.request_scroll_to_deferred(())
        # Re-broadcast: ``view_state.restore`` may have rewritten ``_font_pt``
        # from a previously-saved per-tab value; the global controller wins.
        win.fonts.subscribe(tab)

        win._bind_undo_signals(tab)
        win.update_actions()
        if on_presentation_complete is not None:
            on_presentation_complete(tab)

    @staticmethod
    def _should_expand_all_on_open(tab: Document) -> bool:
        node_count = tab.model.estimated_item_count
        if isinstance(node_count, int):
            return node_count <= settings.LOADING_AUTO_EXPAND_MAX_NODES
        return True

    # ── current-tab change ────────────────────────────────────────────────

    def on_tab_changed(self, _index: int) -> None:
        win = self._win
        tab = win._current_tab()
        win._bind_undo_signals(tab)
        win._dock_validation.bind_validation_status(tab)
        win.validation_dock.attach_tab(tab)
        if tab is not None:
            tab.appearance.resize_key_columns()
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

        if isinstance(widget, JsonTabWidgetMarker):
            if not win._confirm_close(widget):
                return

        dialog = self._ensure_close_progress_dialog()
        close_task_id = uuid4().hex
        failed = False
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        dialog.start(close_task_id)

        snapshot = None
        try:
            if isinstance(widget, JsonTabWidgetMarker):
                was_dirty = widget.io.dirty
                self._set_close_stage(dialog, "snapshot")

                # Build reopen snapshot: if user discarded dirty edits, remember file path only.
                if was_dirty and widget.io.dirty:
                    # Discard chosen — don't resurrect dirty state on reopen.
                    if widget.io.file_path:
                        snapshot = {
                            "data": None,
                            "file_path": widget.io.file_path,
                            "save_format": widget.io.save_format,
                        }
                else:
                    try:
                        snap_data = widget.root_data()
                    except Exception:  # noqa: BLE001
                        snap_data = {}
                    snapshot = {
                        "data": snap_data,
                        "file_path": widget.io.file_path,
                        "save_format": widget.io.save_format,
                    }

                self._set_close_stage(dialog, "unregistering schema")
                win._schema_tab_pool.unregister(widget)

                self._set_close_stage(dialog, "saving view state")
                view_state.save(widget)

            if widget is win._bound_undo_tab:
                win._bind_undo_signals(None)

            self._set_close_stage(dialog, "removing tab")
            self._tab_widget.removeTab(index)

            if widget is not None:
                self._set_close_stage(dialog, "destroying tab")
                widget.deleteLater()

            if snapshot is not None:
                self.closed_tabs_stack.append(snapshot)
                if len(self.closed_tabs_stack) > self.MAX_CLOSED_TABS:
                    self.closed_tabs_stack.pop(0)

            win.update_actions()
            current = win._current_tab()
            win._bind_undo_signals(current)
            win._dock_validation.bind_validation_status(current)
            win.validation_dock.attach_tab(current)
        except Exception:  # noqa: BLE001
            failed = True
            raise
        finally:
            self._finish_close_progress(dialog, close_task_id, failed=failed)
            while QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()

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
