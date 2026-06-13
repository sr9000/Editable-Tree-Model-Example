"""Load coordinator for file open and reload operations.

This module owns the open and reload flows. In this initial scaffold it
delegates to the current synchronous behavior. Later commits will add
worker parsing, progress reporting, chunked model build, and cancellation.
"""

from __future__ import annotations

from pathlib import Path

from PySide6.QtWidgets import QMessageBox

from documents.seams.document_protocol import Document
from io_formats.load import load_file_with_format


class LoadCoordinator:
    """Coordinates file open and reload operations.

    The coordinator is the single owner of loading flows. It receives
    callbacks to the main window for tab creation, status updates, and
    error presentation.
    """

    def __init__(self, window: MainWindow) -> None:
        self._window = window

    def open_file(self, path: str) -> bool:
        """Open a file and create a new tab.

        Returns True on success, False on failure.
        """
        from app.recent_files import push_recent

        resolved = str(Path(path).resolve())
        self._window.statusBar.showMessage(f"Loading: {resolved}", 0)
        try:
            data, source_format = load_file_with_format(resolved)
        except Exception as exc:
            self._window.statusBar.showMessage(f"Open failed: {resolved}", 3000)
            QMessageBox.critical(self._window, "Open failed", f"Could not open {resolved}:\n{exc}")
            return False

        tab = self._window._add_tab(data=data, file_path=resolved, save_format=source_format)
        if tab is None:
            return False
        push_recent(self._window, resolved)
        self._window.statusBar.showMessage(f"Opened: {resolved}", 2000)
        return True

    def reload_file(self, tab: Document, path: str) -> bool:
        """Reload a tab's content from disk.

        Returns True on success, False on failure.
        """
        resolved = str(Path(path).resolve())
        self._window.statusBar.showMessage(f"Reloading: {resolved}", 0)
        try:
            data, source_format = load_file_with_format(resolved)
        except Exception as exc:
            self._window.statusBar.showMessage(f"Reload failed: {resolved}", 3000)
            QMessageBox.critical(self._window, "Reload failed", f"Could not reload {resolved}:\n{exc}")
            return False

        root_index = tab.root_index()
        root_item = tab.root_item()
        changed = tab.editing.diff.apply(root_item, data, root_index)
        if changed:
            tab.undo_stack.clear()
        tab.undo_stack.setClean()
        tab.io.save_format = source_format
        tab.io.file_path = resolved
        tab.validation.revalidate()
        self._window._refresh_tab_presentation(tab)
        self._window.update_actions()
        self._window.statusBar.showMessage(f"Reloaded: {resolved}", 2000)
        return True


__all__ = ["LoadCoordinator"]
