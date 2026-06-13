"""Load coordinator for file open and reload operations.

This module owns the open and reload flows. It integrates worker parsing,
progress reporting, chunked model build, and the delayed progress widget.
"""

from __future__ import annotations

import uuid
from pathlib import Path

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QMessageBox

from app.loading.progress import (
    STAGE_BINDING_UI,
    STAGE_COMPLETE,
    STAGE_DISCOVERING_SCHEMA,
    STAGE_READING_PARSING,
    STAGE_VALIDATING_DOCUMENT,
    ProgressReporter,
)
from app.loading.progress_dialog import LoadingProgressDialog
from documents.seams.document_protocol import Document
from io_formats.load import load_file_with_format


class LoadCoordinator(QObject):
    """Coordinates file open and reload operations.

    The coordinator is the single owner of loading flows. It receives
    callbacks to the main window for tab creation, status updates, and
    error presentation.

    Signals
    -------
    stage_changed(stage_name)
        Emitted when the loading stage changes.
    """

    stage_changed = Signal(str)

    def __init__(self, window, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._reporter: ProgressReporter | None = None
        self._progress_dialog: LoadingProgressDialog | None = None
        self._current_task_id: str | None = None

    def set_reporter(self, reporter: ProgressReporter | None) -> None:
        """Set the progress reporter for stage notifications."""
        self._reporter = reporter

    def _emit_stage(self, stage: str) -> None:
        """Emit a stage change signal and notify the reporter."""
        self.stage_changed.emit(stage)
        if self._reporter is not None:
            self._reporter.stage(stage)
        if self._progress_dialog is not None:
            self._progress_dialog.set_stage(stage)

    def _start_progress(self, task_id: str) -> None:
        """Start tracking a load task with the progress widget."""
        self._current_task_id = task_id
        if self._progress_dialog is None:
            self._progress_dialog = LoadingProgressDialog(self._window)
        self._progress_dialog.start(task_id)

    def _finish_progress(self, task_id: str) -> None:
        """Finish tracking a load task."""
        if self._progress_dialog is not None:
            self._progress_dialog.finish(task_id)
        self._current_task_id = None

    def _error_progress(self, task_id: str) -> None:
        """Mark a load task as failed."""
        if self._progress_dialog is not None:
            self._progress_dialog.error(task_id)
        self._current_task_id = None

    def open_file(self, path: str) -> bool:
        """Open a file and create a new tab.

        Returns True on success, False on failure.
        """
        from app.recent_files import push_recent

        task_id = str(uuid.uuid4())
        self._start_progress(task_id)

        resolved = str(Path(path).resolve())
        self._window.statusBar.showMessage(f"Loading: {resolved}", 0)

        self._emit_stage(STAGE_READING_PARSING)
        try:
            data, source_format = load_file_with_format(resolved)
        except Exception as exc:
            self._error_progress(task_id)
            self._window.statusBar.showMessage(f"Open failed: {resolved}", 3000)
            QMessageBox.critical(self._window, "Open failed", f"Could not open {resolved}:\n{exc}")
            return False

        self._emit_stage(STAGE_BINDING_UI)
        tab = self._window._add_tab(data=data, file_path=resolved, save_format=source_format)
        if tab is None:
            self._error_progress(task_id)
            return False

        self.run_schema_discovery_and_validation(tab)

        push_recent(self._window, resolved)
        self._window.statusBar.showMessage(f"Opened: {resolved}", 2000)
        self._finish_progress(task_id)
        return True

    def reload_file(self, tab: Document, path: str) -> bool:
        """Reload a tab's content from disk.

        Returns True on success, False on failure.
        """
        task_id = str(uuid.uuid4())
        self._start_progress(task_id)

        resolved = str(Path(path).resolve())
        self._window.statusBar.showMessage(f"Reloading: {resolved}", 0)

        self._emit_stage(STAGE_READING_PARSING)
        try:
            data, source_format = load_file_with_format(resolved)
        except Exception as exc:
            self._error_progress(task_id)
            self._window.statusBar.showMessage(f"Reload failed: {resolved}", 3000)
            QMessageBox.critical(self._window, "Reload failed", f"Could not reload {resolved}:\n{exc}")
            return False

        self._emit_stage(STAGE_BINDING_UI)
        root_index = tab.root_index()
        root_item = tab.root_item()
        changed = tab.editing.diff.apply(root_item, data, root_index)
        if changed:
            tab.undo_stack.clear()
        tab.undo_stack.setClean()
        tab.io.save_format = source_format
        tab.io.file_path = resolved

        self.run_schema_discovery_and_validation(tab)

        self._window._refresh_tab_presentation(tab)
        self._window.update_actions()
        self._window.statusBar.showMessage(f"Reloaded: {resolved}", 2000)
        self._finish_progress(task_id)
        return True

    def run_schema_discovery_and_validation(self, tab: Document) -> None:
        """Run schema discovery and validation with stage reporting.

        This method emits the discovering schema and validating document
        stages, then runs the tab's validation revalidate method.
        """
        self._emit_stage(STAGE_DISCOVERING_SCHEMA)
        # Schema discovery happens automatically during tab creation
        # via the validation controller's initialization

        self._emit_stage(STAGE_VALIDATING_DOCUMENT)
        tab.validation.revalidate()

        self._emit_stage(STAGE_COMPLETE)


__all__ = ["LoadCoordinator"]
