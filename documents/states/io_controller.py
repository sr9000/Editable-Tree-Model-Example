"""Per-tab file IO controller."""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal
from PySide6.QtWidgets import QFileDialog

from io_formats import (
    SAVE_FORMAT_JSON,
    SAVE_FORMAT_JSONL,
    SAVE_FORMAT_YAML,
    SAVE_FORMAT_YAML_MULTI,
    detect_format,
    save_file,
)


class IoController(QObject):
    """Own the file path, save format, dirty flag, and save helpers for a tab."""

    dirtyChanged = Signal(bool)

    def __init__(self, tab, *, file_path: str | None, save_format: str | None) -> None:
        super().__init__(tab)
        self._tab = tab
        self.file_path: str | None = file_path
        self.save_format: str | None = save_format
        self._dirty: bool = False

    @property
    def dirty(self) -> bool:
        return self._dirty

    def set_dirty(self, dirty: bool) -> None:
        dirty = bool(dirty)
        if self._dirty == dirty:
            return
        self._dirty = dirty
        self.dirtyChanged.emit(dirty)

    def on_clean_changed(self, clean: bool) -> None:
        """Slot for ``QUndoStack.cleanChanged``."""
        self.set_dirty(not clean)

    def snapshot(self):
        return self._tab.model.root_item.to_json()

    def save(self) -> bool:
        tab = self._tab
        if not self.file_path:
            return self.save_as()
        try:
            save_file(self.file_path, tab.model.root_item.to_json(), save_format=self.save_format)
        except Exception as exc:
            tab.show_status(f"Save failed: {exc}", 4000)
            return False
        tab.undo_stack.setClean()
        tab.show_status(f"Saved: {self.file_path}", 2000)
        return True

    def save_as(self, path: str | None = None) -> bool:
        tab = self._tab
        target = path
        selected_filter = ""
        if not target:
            target, selected_filter = QFileDialog.getSaveFileName(
                tab,
                "Save As",
                self.file_path or "",
                "JSON (*.json);;JSON Lines (*.jsonl *.ndjson);;YAML (*.yaml *.yml);;YAML multi-document (*.yaml *.yml)",
            )
        if not target:
            return False
        if selected_filter.startswith("JSON Lines"):
            self.save_format = SAVE_FORMAT_JSONL
        elif selected_filter.startswith("YAML multi-document"):
            self.save_format = SAVE_FORMAT_YAML_MULTI
        elif selected_filter.startswith("YAML"):
            self.save_format = SAVE_FORMAT_YAML
        elif selected_filter.startswith("JSON"):
            self.save_format = SAVE_FORMAT_JSON
        elif target:
            try:
                self.save_format = detect_format(target)
            except ValueError:
                pass
        self.file_path = target
        return self.save()


__all__ = ["IoController"]
