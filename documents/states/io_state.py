"""IoState -- file-IO substate for a :class:`documents.tab.JsonTab`.

Per Plan 20 Phase I (I1): the IO axis (path, save format, dirty flag,
save/save_as/snapshot orchestration) is one of four substates that
``JsonTabData`` composes.  Moved here verbatim from
``documents/tab_io_controller.py``; the old module re-exports
:class:`IoState` under the legacy ``TabIOController`` name so existing
tests and any not-yet-migrated callers keep working.
"""

from __future__ import annotations

from PySide6.QtCore import QObject, Signal

from documents.tab_io import save as _io_save
from documents.tab_io import save_as as _io_save_as
from documents.tab_io import snapshot as _io_snapshot


class IoState(QObject):
    """Per-tab IO substate.

    Owns the file path, save format and dirty flag for a single
    :class:`documents.tab.JsonTab`, and orchestrates the
    :mod:`documents.tab_io` save/load primitives.
    """

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


__all__ = ["IoState"]
