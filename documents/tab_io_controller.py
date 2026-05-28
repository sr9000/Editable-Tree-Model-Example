"""Tab-scoped file/IO state controller.

Owns the path, save format and dirty flag for a document tab.  Orchestrates
the IO primitives in ``documents/tab_io.py`` (save/save_as/snapshot) without
duplicating them.  Parented to the host tab for clean teardown.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from documents.tab_io import save as _io_save
from documents.tab_io import save_as as _io_save_as
from documents.tab_io import snapshot as _io_snapshot


class TabIOController(QObject):
    """Holds path/save-format/dirty for a single JsonTab."""

    dirtyChanged = Signal(bool)

    def __init__(self, tab, *, file_path: str | None, save_format: str | None) -> None:
        super().__init__(tab)
        self._tab = tab
        self.file_path: str | None = file_path
        self.save_format: str | None = save_format
        self._dirty: bool = False

    # ----- dirty flag ----------------------------------------------------
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

    # ----- save/load orchestration ---------------------------------------
    def save(self) -> bool:
        return _io_save(self._tab)

    def save_as(self, path: str | None = None) -> bool:
        return _io_save_as(self._tab, path=path)

    def snapshot(self):
        return _io_snapshot(self._tab)


__all__ = ["TabIOController"]
