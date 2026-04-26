import hashlib
from pathlib import Path
from typing import Any

from PySide6.QtCore import QSettings

from settings import APPLICATION_ID

MAX_EXPANDED_PATHS = 5000


def state_key(path: str) -> str:
    resolved = str(Path(path).resolve())
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:16]
    return f"view_state/{digest}"


def _coerce_int(value: Any) -> int | None:
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _coerce_int_list(value: Any) -> list[int] | None:
    if not isinstance(value, (list, tuple)):
        return None
    coerced: list[int] = []
    for part in value:
        number = _coerce_int(part)
        if number is None:
            return None
        coerced.append(number)
    return coerced


def _coerce_path(value: Any) -> tuple[int, ...] | None:
    if isinstance(value, str):
        stripped = value.strip()
        if stripped == "":
            return ()
        # Accept either "0/1/2" or "0,1,2" for portability.
        separator = "/" if "/" in stripped else ","
        parts = [p for p in stripped.split(separator) if p != ""]
        coerced = _coerce_int_list(parts)
        return tuple(coerced) if coerced is not None else None

    coerced = _coerce_int_list(value)
    return tuple(coerced) if coerced is not None else None


def _coerce_paths(value: Any) -> list[tuple[int, ...]] | None:
    if not isinstance(value, (list, tuple)):
        return None
    paths: list[tuple[int, ...]] = []
    for entry in value:
        path = _coerce_path(entry)
        if path is None:
            return None
        paths.append(path)
    return paths


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
            idx = tab._index_from_path(path)
            if idx.isValid():
                tab.view.expand(idx)

    if current_path is not None:
        current_index = tab._index_from_path(current_path)
        if current_index.isValid():
            # Always select column 0 when restoring row focus.
            row_index = current_index.siblingAtColumn(0)
            tab.view.setCurrentIndex(row_index)

    return True


def discard(path: str) -> None:
    settings = QSettings(APPLICATION_ID, "view_state")
    settings.remove(state_key(path))
