"""Worker thread for file parsing.

The worker runs ``load_file_with_format()`` in a QThread and emits
plain Python data back to the GUI thread. It must not create any Qt
widgets.
"""

from __future__ import annotations

from typing import Any, Callable

from PySide6.QtCore import QObject, QThread, Signal


class ParseWorker(QObject):
    """Worker that parses a file in a background thread.

    Signals
    -------
    finished(result)
        Emitted when parsing succeeds. ``result`` is a tuple of
        ``(data, source_format)``.
    failed(error_payload)
        Emitted when parsing fails. ``error_payload`` is a tuple of
        ``(error_type, error_message)``.
    stage(stage_name)
        Emitted to report progress stages.
    """

    finished = Signal(object)
    failed = Signal(object)
    stage = Signal(str)

    def __init__(
        self,
        path: str,
        parser: Callable[[str], tuple[Any, str]] | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self._path = path
        self._parser = parser

    def run(self) -> None:
        """Execute the parse operation.

        This method is called in the worker thread. It emits ``finished``
        on success or ``failed`` on exception.
        """
        try:
            self.stage.emit("reading/parsing file")
            if self._parser is not None:
                result = self._parser(self._path)
            else:
                from io_formats.load import load_file_with_format

                result = load_file_with_format(self._path)
            self.stage.emit("decoding number affixes")
            self.finished.emit(result)
        except Exception as exc:
            self.failed.emit((type(exc).__name__, str(exc)))


def start_parse_worker(
    path: str,
    parser: Callable[[str], tuple[Any, str]] | None = None,
) -> tuple[QThread, ParseWorker]:
    """Create and start a parse worker thread.

    Parameters
    ----------
    path : str
        The file path to parse.
    parser : Callable | None
        Optional custom parser for testing. If None, uses
        ``load_file_with_format``.

    Returns
    -------
    tuple[QThread, ParseWorker]
        The thread and worker objects. The caller must connect to the
        worker's signals and ensure the thread is cleaned up.
    """
    from PySide6.QtCore import Qt

    thread = QThread()
    worker = ParseWorker(path, parser=parser)
    worker.moveToThread(thread)
    thread.started.connect(worker.run)
    # Use QueuedConnection to ensure thread.quit() is called from the main thread
    worker.finished.connect(thread.quit, Qt.ConnectionType.QueuedConnection)
    worker.failed.connect(thread.quit, Qt.ConnectionType.QueuedConnection)
    thread.start()
    return thread, worker


__all__ = ["ParseWorker", "start_parse_worker"]
