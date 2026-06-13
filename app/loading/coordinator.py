"""Load coordinator for file open and reload operations.

This module owns the open and reload flows. It integrates worker parsing,
progress reporting, chunked model build, and the delayed progress widget.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from PySide6.QtCore import QObject, Qt, QThread, QTimer, Signal
from PySide6.QtWidgets import QApplication, QMessageBox

import state.view_state as view_state
from app.loading.builder import ChunkedTreeBuilder
from app.loading.cancellation import CancellationToken
from app.loading.progress import (
    STAGE_APPLYING_RELOAD,
    STAGE_BINDING_UI,
    STAGE_COMPLETE,
    STAGE_DISCOVERING_SCHEMA,
    STAGE_VALIDATING_DOCUMENT,
    ProgressReporter,
)
from app.loading.progress_dialog import LoadingProgressDialog
from app.loading.worker import ParseWorker
from documents.seams.document_protocol import Document
from settings import LOADING_HARD_TIMEOUT_SECONDS
from tree.model import JsonTreeModel


@dataclass
class _LoadTask:
    task_id: str
    mode: str
    path: str
    tab: Document | None = None
    thread: QThread | None = None
    worker: ParseWorker | None = None
    builder: ChunkedTreeBuilder | None = None
    data: Any = None
    source_format: str | None = None
    token: CancellationToken = field(default_factory=CancellationToken)


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
    task_finished = Signal(str, bool)
    _parse_succeeded = Signal(str, object)
    _parse_failed = Signal(str, object)

    def __init__(self, window, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self._window = window
        self._reporter: ProgressReporter | None = None
        self._progress_dialog: LoadingProgressDialog | None = None
        self._current_task_id: str | None = None
        self._tasks: dict[str, _LoadTask] = {}
        self._completed_task_results: dict[str, bool] = {}
        self._cancelled_task_ids: set[str] = set()
        self._parse_succeeded.connect(self._on_parse_finished, Qt.ConnectionType.QueuedConnection)
        self._parse_failed.connect(self._on_parse_failed, Qt.ConnectionType.QueuedConnection)

    def set_reporter(self, reporter: ProgressReporter | None) -> None:
        """Set the progress reporter for stage notifications."""
        self._reporter = reporter

    def _emit_stage(self, stage: str) -> None:
        """Emit a stage change signal and notify the reporter."""
        self.stage_changed.emit(stage)
        if self._reporter is not None:
            self._reporter.stage(stage)
        if self._progress_dialog is not None:
            try:
                self._progress_dialog.set_stage(stage)
            except RuntimeError:
                self._progress_dialog = None

    def stage(self, name: str) -> None:
        """ProgressReporter entry point used by builders."""
        self._emit_stage(name)

    def tick(self, done: int, total: int) -> None:
        """ProgressReporter entry point used by builders."""
        if self._reporter is not None:
            self._reporter.tick(done, total)
        if self._progress_dialog is not None:
            try:
                self._progress_dialog.set_progress(done, total)
            except RuntimeError:
                self._progress_dialog = None

    def detail(self, processed: int, path: str) -> None:
        """ProgressReporter detail entry point used by builders/workers."""
        if self._reporter is not None and isinstance(self._reporter, ProgressReporter):
            self._reporter.detail(processed, path)
        if self._progress_dialog is not None:
            try:
                self._progress_dialog.set_detail(processed, path)
            except RuntimeError:
                self._progress_dialog = None

    def _start_progress(self, task: _LoadTask) -> None:
        """Start tracking a load task with the progress widget."""
        self._current_task_id = task.task_id
        if self._progress_dialog is None:
            self._progress_dialog = LoadingProgressDialog(self._window, cancellable=True)
        try:
            self._progress_dialog.start(task.task_id, cancellation_token=task.token, on_cancel=self.cancel_current)
        except RuntimeError:
            self._progress_dialog = LoadingProgressDialog(self._window, cancellable=True)
            self._progress_dialog.start(task.task_id, cancellation_token=task.token, on_cancel=self.cancel_current)

    def cancel_current(self) -> None:
        """Cancel the active load task and unblock any blocking caller."""
        task_id = self._current_task_id
        if task_id is None:
            return

        task = self._tasks.get(task_id)
        if task is None:
            self._current_task_id = None
            return

        task.token.cancel()
        self._cancelled_task_ids.add(task_id)
        self._finish_progress(task_id)
        if task.mode == "reload":
            self._window.statusBar.showMessage("Reload cancelled", 3000)
        else:
            self._window.statusBar.showMessage("Open cancelled", 3000)

        # Parse-stage cancel is completed immediately. Build-stage cancel
        # completes when the builder observes the token and emits cancelled.
        if task.builder is None:
            self._complete_task(task_id, False)

    def _finish_progress(self, task_id: str) -> None:
        """Finish tracking a load task."""
        if self._progress_dialog is not None:
            try:
                self._progress_dialog.finish(task_id)
            except RuntimeError:
                self._progress_dialog = None
        self._current_task_id = None

    def _error_progress(self, task_id: str) -> None:
        """Mark a load task as failed."""
        if self._progress_dialog is not None:
            try:
                self._progress_dialog.error(task_id)
            except RuntimeError:
                self._progress_dialog = None
        self._current_task_id = None

    def _begin_task(self, mode: str, path: str, tab: Document | None = None) -> _LoadTask | None:
        """Create and register a loading task."""
        if self._current_task_id is not None:
            self._window.statusBar.showMessage("A file is already loading", 3000)
            return None

        task_id = str(uuid.uuid4())
        resolved = str(Path(path).resolve())
        task = _LoadTask(task_id=task_id, mode=mode, path=resolved, tab=tab)
        self._tasks[task_id] = task
        self._start_progress(task)
        return task

    def _start_parse_worker(
        self,
        task: _LoadTask,
        parser: Callable[[str], tuple[Any, str]] | None = None,
    ) -> None:
        """Start file parsing after all signal handlers are connected."""
        thread = QThread(self)
        worker = ParseWorker(task.path, parser=parser)
        worker.moveToThread(thread)
        task.thread = thread
        task.worker = worker

        thread.started.connect(worker.run)
        worker.stage.connect(self._emit_stage, Qt.ConnectionType.QueuedConnection)
        worker.detail.connect(self.detail, Qt.ConnectionType.QueuedConnection)
        worker.finished.connect(lambda result, task_id=task.task_id: self._parse_succeeded.emit(task_id, result))
        worker.failed.connect(
            lambda error_payload, task_id=task.task_id: self._parse_failed.emit(task_id, error_payload)
        )
        worker.finished.connect(thread.quit, Qt.ConnectionType.QueuedConnection)
        worker.failed.connect(thread.quit, Qt.ConnectionType.QueuedConnection)
        thread.finished.connect(worker.deleteLater)
        thread.finished.connect(thread.deleteLater)
        thread.start()

    def _run_blocking(self, task_id: str | None) -> bool:
        """Wait for an asynchronous load while keeping the GUI event loop alive."""
        if task_id is None:
            return False

        completed = self._completed_task_results.pop(task_id, None)
        if completed is not None:
            return completed

        deadline = time.monotonic() + LOADING_HARD_TIMEOUT_SECONDS
        while task_id in self._tasks and task_id not in self._completed_task_results:
            if time.monotonic() >= deadline:
                self._error_progress(task_id)
                self._tasks.pop(task_id, None)
                self._window.statusBar.showMessage("Loading timed out", 3000)
                return False
            QApplication.processEvents()
            time.sleep(0.001)

        return self._completed_task_results.pop(task_id, False)

    def open_file_async(
        self,
        path: str,
        *,
        parser: Callable[[str], tuple[Any, str]] | None = None,
    ) -> str | None:
        """Start opening a file and return immediately."""
        task = self._begin_task("open", path)
        if task is None:
            return None
        self._window.statusBar.showMessage(f"Loading: {task.path}", 0)
        self._start_parse_worker(task, parser=parser)
        return task.task_id

    def reload_file_async(
        self,
        tab: Document,
        path: str,
        *,
        parser: Callable[[str], tuple[Any, str]] | None = None,
    ) -> str | None:
        """Start reloading a file and return immediately."""
        task = self._begin_task("reload", path, tab=tab)
        if task is None:
            return None
        self._window.statusBar.showMessage(f"Reloading: {task.path}", 0)
        self._start_parse_worker(task, parser=parser)
        return task.task_id

    def open_file(self, path: str) -> bool:
        """Open a file and create a new tab.

        Returns True on success, False on failure.
        """
        return self._run_blocking(self.open_file_async(path))

    def reload_file(self, tab: Document, path: str) -> bool:
        """Reload a tab's content from disk.

        Returns True on success, False on failure.
        """
        return self._run_blocking(self.reload_file_async(tab, path))

    def _on_parse_finished(self, task_id: str, result: object) -> None:
        """Resume the load after background parsing succeeds."""
        if task_id in self._cancelled_task_ids:
            self._cancelled_task_ids.discard(task_id)
            return
        task = self._tasks.get(task_id)
        if task is None:
            return
        data, source_format = result
        task.data = data
        task.source_format = source_format
        builder = ChunkedTreeBuilder(
            data,
            show_root=True,
            reporter=self,
            cancellation_token=task.token,
            icon_provider=self._window._icon_provider,
            parent=self,
        )
        task.builder = builder
        builder.finished.connect(
            lambda model, finished_task_id=task_id: self._on_build_finished(finished_task_id, model)
        )
        builder.cancelled.connect(lambda cancelled_task_id=task_id: self._on_build_cancelled(cancelled_task_id))
        builder.start()

    def _on_parse_failed(self, task_id: str, error_payload: object) -> None:
        """Complete a task through the user-facing error path."""
        if task_id in self._cancelled_task_ids:
            self._cancelled_task_ids.discard(task_id)
            return
        task = self._tasks.get(task_id)
        if task is None:
            return
        _error_type, error_message = error_payload
        self._error_progress(task_id)
        if task.mode == "reload":
            self._window.statusBar.showMessage(f"Reload failed: {task.path}", 3000)
            QMessageBox.critical(self._window, "Reload failed", f"Could not reload {task.path}:\n{error_message}")
        else:
            self._window.statusBar.showMessage(f"Open failed: {task.path}", 3000)
            QMessageBox.critical(self._window, "Open failed", f"Could not open {task.path}:\n{error_message}")
        self._complete_task(task_id, False)

    def _on_build_finished(self, task_id: str, model: object) -> None:
        """Bind or apply the fully built model after chunked construction."""
        task = self._tasks.get(task_id)
        if task is None:
            return

        task.builder = None

        if task.mode == "reload":
            ok = self._apply_reload(task, model)
            if not ok:
                self._complete_task(task_id, False)
        else:
            self._bind_open(task, model)

    def _on_build_cancelled(self, task_id: str) -> None:
        """Finalize cooperative cancellation when chunked build aborts."""
        task = self._tasks.get(task_id)
        if task is None:
            return
        task.builder = None
        self._complete_task(task_id, False)

    def _bind_open(self, task: _LoadTask, model: object) -> None:
        """Create a tab from a prebuilt model and finish open bookkeeping."""
        task_id = task.task_id

        self._emit_stage(STAGE_BINDING_UI)
        tab = self._window._add_tab(
            data=task.data,
            file_path=task.path,
            save_format=task.source_format,
            prebuilt_model=model,
            defer_first_presentation=True,
            defer_validation_init=True,
            on_presentation_complete=lambda opened_tab: self._finish_open_binding(task_id, opened_tab),
        )
        if tab is None:
            self._error_progress(task.task_id)
            self._complete_task(task.task_id, False)

    def _finish_open_binding(self, task_id: str, tab: Document) -> None:
        """Finalize an open task after deferred first-presentation work."""
        from app.recent_files import push_recent

        task = self._tasks.get(task_id)
        if task is None:
            return

        self.run_schema_discovery_and_validation(tab, parsed_data=task.data)

        push_recent(self._window, task.path)
        self._window.statusBar.showMessage(f"Opened: {task.path}", 2000)
        self._finish_progress(task_id)
        self._complete_task(task_id, True)

    def _apply_reload(self, task: _LoadTask, model: object) -> bool:
        """Apply parsed reload data to the target tab at the commit point."""
        tab = task.tab
        if tab is None:
            self._error_progress(task.task_id)
            return False

        if not isinstance(model, JsonTreeModel):
            self._error_progress(task.task_id)
            return False

        previous_view_state = view_state.capture_runtime_state(tab)
        changed = True

        if task.token.is_cancelled:
            if self._current_task_id == task.task_id:
                self._finish_progress(task.task_id)
                self._window.statusBar.showMessage("Reload cancelled", 3000)
            return False

        self._emit_stage(STAGE_APPLYING_RELOAD)
        tab.model.replace_root_item(model.root_item, estimated_item_count=model.estimated_item_count)
        if changed:
            tab.undo_stack.clear()
        tab.undo_stack.setClean()
        tab.io.save_format = task.source_format
        tab.io.file_path = task.path

        view_state.restore_runtime_state(tab, previous_view_state)

        QTimer.singleShot(0, lambda task_id=task.task_id: self._finish_reload_apply(task_id))
        return True

    def _finish_reload_apply(self, task_id: str) -> None:
        """Finalize reload on a later event-loop turn for post-build responsiveness."""
        task = self._tasks.get(task_id)
        if task is None:
            return
        tab = task.tab
        if tab is None:
            self._error_progress(task_id)
            self._complete_task(task_id, False)
            return

        self.run_schema_discovery_and_validation(tab, parsed_data=task.data)

        self._window._refresh_tab_presentation(tab)
        self._window.update_actions()
        self._window.statusBar.showMessage(f"Reloaded: {task.path}", 2000)
        self._finish_progress(task_id)
        self._complete_task(task_id, True)

    def _complete_task(self, task_id: str, ok: bool) -> None:
        """Release task-owned objects and announce completion."""
        self._tasks.pop(task_id, None)
        self._cancelled_task_ids.discard(task_id)
        self._completed_task_results[task_id] = ok
        self.task_finished.emit(task_id, ok)

    def run_schema_discovery_and_validation(self, tab: Document, *, parsed_data: Any | None = None) -> None:
        """Run schema discovery and validation with stage reporting.

        This method emits the discovering schema and validating document
        stages, then runs the tab's validation revalidate method.
        """
        doc_path = Path(tab.io.file_path).expanduser().resolve() if tab.io.file_path else None

        self._emit_stage(STAGE_DISCOVERING_SCHEMA)
        discovery_data = parsed_data if parsed_data is not None else tab.model.root_item.to_json()
        tab.validation.init_state(discovery_data, doc_path=doc_path, revalidate=False)

        self._emit_stage(STAGE_VALIDATING_DOCUMENT)
        if parsed_data is None:
            tab.validation.revalidate()
        else:
            tab.validation.revalidate_loading_data(parsed_data)

        self._emit_stage(STAGE_COMPLETE)


__all__ = ["LoadCoordinator"]
