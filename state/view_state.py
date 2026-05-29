import hashlib
from pathlib import Path

from PySide6.QtCore import QModelIndex, QSettings, QSortFilterProxyModel

from settings import APPLICATION_ID
from state.qsettings_coercion import _coerce_int, _coerce_int_list, _coerce_path, _coerce_paths

MAX_EXPANDED_PATHS = 5000


def _source_to_view_index(view, source_index: QModelIndex) -> QModelIndex:
    model = view.model()
    if isinstance(model, QSortFilterProxyModel):
        return model.mapFromSource(source_index)
    return source_index


def iter_expanded_relative_paths(view, source_index: QModelIndex):
    """Yield expanded descendant paths relative to *source_index*.

    Relative paths are tuples of row numbers and never include the source root
    itself. Example: ``(2, 0)`` means child row 2, then its child row 0.
    """
    if not source_index.isValid():
        return

    model = source_index.model()

    def walk(parent: QModelIndex, rel_prefix: tuple[int, ...]):
        for row in range(model.rowCount(parent)):
            child = model.index(row, 0, parent)
            if not child.isValid():
                continue
            rel = rel_prefix + (row,)
            view_child = _source_to_view_index(view, child)
            if view_child.isValid() and view.isExpanded(view_child):
                yield rel
            yield from walk(child, rel)

    yield from walk(source_index, ())


def apply_expanded_relative_paths(view, source_index: QModelIndex, paths) -> None:
    """Expand descendants under *source_index* from relative row-path tuples."""
    if not source_index.isValid():
        return

    model = source_index.model()
    for rel in paths:
        cursor = source_index
        ok = True
        for row in rel:
            cursor = model.index(int(row), 0, cursor)
            if not cursor.isValid():
                ok = False
                break
        if not ok:
            continue
        view_idx = _source_to_view_index(view, cursor)
        if view_idx.isValid():
            view.setExpanded(view_idx, True)


def state_key(path: str) -> str:
    resolved = str(Path(path).resolve())
    digest = hashlib.sha1(resolved.encode("utf-8")).hexdigest()[:16]
    return f"view_state/{digest}"


def save(tab) -> None:
    if not tab.file_path:
        return

    settings = QSettings(APPLICATION_ID, "view_state")
    settings.beginGroup(state_key(tab.file_path))

    widths = [int(tab.view.columnWidth(column)) for column in range(tab.model.columnCount())]
    expanded_paths = [list(path) for path in tab._collect_expanded_paths()[:MAX_EXPANDED_PATHS]]

    current_path_tuple = tab.view_controller.current_path()
    current_path = list(current_path_tuple) if current_path_tuple is not None else []

    font_pt = int(tab._font_pt or tab.view.font().pointSize() or 10)

    settings.setValue("col_widths", widths)
    settings.setValue("expanded", expanded_paths)
    settings.setValue("current_path", current_path)
    settings.setValue("font_pt", font_pt)
    settings.endGroup()


def restore(tab) -> bool:
    if not tab.file_path:
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

    if font_pt is not None:
        tab._set_font_pt(font_pt)

    if widths is not None:
        for column, width in enumerate(widths[: tab.model.columnCount()]):
            if width > 0:
                tab.view.setColumnWidth(column, width)
        # The persisted widths represent the user's last explicit preference;
        # treat name (0) and type (1) columns as user-sized so zoom helpers
        # won't snap them back to content width.
        tab._user_sized_columns.update(c for c in (0, 1) if c < len(widths) and widths[c] > 0)

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
