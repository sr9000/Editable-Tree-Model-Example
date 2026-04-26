import hashlib
from pathlib import Path

from PySide6.QtCore import QSettings

from settings import APPLICATION_ID
from state.qsettings_coercion import _coerce_int, _coerce_int_list, _coerce_path, _coerce_paths

MAX_EXPANDED_PATHS = 5000


def state_key(path: str) -> str:
    resolved = str(Path(path).resolve())
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:16]
    return f"view_state/{digest}"



def save(tab) -> None:
    if not getattr(tab, "file_path", None):
        return

    settings = QSettings(APPLICATION_ID, "view_state")
    settings.beginGroup(state_key(tab.file_path))

    widths = [int(tab.view.columnWidth(column)) for column in range(tab.model.columnCount())]
    expanded_paths = [list(path) for path in tab._collect_expanded_paths()[:MAX_EXPANDED_PATHS]]

    current_index = tab.view.currentIndex()
    current_path = list(tab._index_path(current_index)) if current_index.isValid() else []

    font_pt = int(getattr(tab, "_font_pt", tab.view.font().pointSize() or 10))

    settings.setValue("col_widths", widths)
    settings.setValue("expanded", expanded_paths)
    settings.setValue("current_path", current_path)
    settings.setValue("font_pt", font_pt)
    settings.endGroup()


def restore(tab) -> bool:
    if not getattr(tab, "file_path", None):
        return False

    settings = QSettings(APPLICATION_ID, "view_state")
    settings.beginGroup(state_key(tab.file_path))

    raw_widths = settings.value("col_widths")
    raw_expanded = settings.value("expanded")
    raw_current = settings.value("current_path")
    raw_font_pt = settings.value("font_pt")

    settings.endGroup()

    widths = _coerce_int_list(raw_widths)
    expanded = _coerce_paths(raw_expanded)
    current_path = _coerce_path(raw_current)
    font_pt = _coerce_int(raw_font_pt)

    has_state = any(value is not None for value in (widths, expanded, current_path, font_pt))
    if not has_state:
        return False

    if font_pt is not None and hasattr(tab, "_set_font_pt"):
        tab._set_font_pt(font_pt)

    if widths is not None:
        for column, width in enumerate(widths[: tab.model.columnCount()]):
            if width > 0:
                tab.view.setColumnWidth(column, width)

    if expanded is not None:
        tab.view.collapseAll()
        for path in expanded:
            source_index = tab._index_from_path(path)
            view_index = tab._source_to_view(source_index)
            if view_index.isValid():
                tab.view.expand(view_index)

    if current_path is not None:
        source_index = tab._index_from_path(current_path)
        current_index = tab._source_to_view(source_index)
        if current_index.isValid():
            # Always select column 0 when restoring row focus.
            row_index = current_index.siblingAtColumn(0)
            tab.view.setCurrentIndex(row_index)

    return True


def discard(path: str) -> None:
    settings = QSettings(APPLICATION_ID, "view_state")
    settings.remove(state_key(path))
