import hashlib
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QModelIndex, QSettings, QSortFilterProxyModel, QTimer

import settings
from documents.seams.document_protocol import Document
from settings import APPLICATION_ID
from state.qsettings_coercion import _coerce_int, _coerce_int_list, _coerce_path, _coerce_paths

MAX_EXPANDED_PATHS = 5000
_RESTORE_BATCH_SIZE = 256
_SAVE_BATCH_SIZE = 256


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


def _is_large_load(tab: Document) -> bool:
    node_count = tab.model.estimated_item_count
    return isinstance(node_count, int) and node_count > settings.LOADING_AUTO_EXPAND_MAX_NODES


def _request_expand_paths_chunked(tab: Document, paths: list[tuple[int, ...]]) -> None:
    if not paths:
        return

    cursor = {"index": 0}

    def _emit_batch() -> None:
        start = cursor["index"]
        end = min(start + _RESTORE_BATCH_SIZE, len(paths))
        for i in range(start, end):
            tab.view_controller.request_expand(paths[i])
        cursor["index"] = end
        if cursor["index"] < len(paths):
            QTimer.singleShot(0, _emit_batch)

    QTimer.singleShot(0, _emit_batch)


def save(tab: Document) -> None:
    if not tab.io.file_path:
        return

    settings = QSettings(APPLICATION_ID, "view_state")
    settings.beginGroup(state_key(tab.io.file_path))

    widths = tab.view_controller.column_widths()
    expanded_paths: list[list[int]] = []
    for i, path in enumerate(tab.editing.move.iter_expanded_paths(), start=1):
        expanded_paths.append(list(path))
        if len(expanded_paths) >= MAX_EXPANDED_PATHS:
            break
        if i % _SAVE_BATCH_SIZE == 0:
            QCoreApplication.processEvents()

    current_path_tuple = tab.view_controller.current_path()
    current_path = list(current_path_tuple) if current_path_tuple is not None else []

    font_pt = int(tab.zoom_pt or tab.view.font().pointSize() or 10)

    settings.setValue("col_widths", widths)
    settings.setValue("expanded", expanded_paths)
    settings.setValue("current_path", current_path)
    settings.setValue("font_pt", font_pt)
    settings.endGroup()


def restore(tab: Document, *, defer_heavy: bool = False) -> bool:
    if not tab.io.file_path:
        return False

    settings = QSettings(APPLICATION_ID, "view_state")
    settings.beginGroup(state_key(tab.io.file_path))

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
        tab.appearance.set_font_pt(font_pt)

    if widths is not None:
        tab.view_controller.set_column_widths(widths)

    large_load = defer_heavy or _is_large_load(tab)

    if expanded is not None:
        tab.view_controller.request_collapse_all()
        expanded_paths = [tuple(path) for path in expanded]
        if large_load:
            _request_expand_paths_chunked(tab, expanded_paths)
        else:
            for path in expanded_paths:
                tab.view_controller.request_expand(path)

    if current_path is not None:
        selected = tuple(current_path)
        if large_load:
            tab.view_controller.request_select_paths_deferred([selected])
        else:
            tab.view_controller.request_select_paths([selected])

    return True


def discard(path: str) -> None:
    settings = QSettings(APPLICATION_ID, "view_state")
    settings.remove(state_key(path))


def capture_runtime_state(tab: Document) -> dict[str, object]:
    """Capture in-memory view state for model-root swaps."""
    return {
        "col_widths": tab.view_controller.column_widths(),
        "expanded": tab.editing.move.collect_expanded_paths()[:MAX_EXPANDED_PATHS],
        "current_path": tab.view_controller.current_path(),
        "h_scroll": int(tab.view.horizontalScrollBar().value()),
        "v_scroll": int(tab.view.verticalScrollBar().value()),
    }


def restore_runtime_state(tab: Document, snapshot: dict[str, object]) -> None:
    """Restore in-memory view state captured by :func:`capture_runtime_state`."""
    col_widths_obj = snapshot.get("col_widths")
    expanded_obj = snapshot.get("expanded")
    current_path_obj = snapshot.get("current_path")
    h_scroll_obj = snapshot.get("h_scroll")
    v_scroll_obj = snapshot.get("v_scroll")

    if isinstance(col_widths_obj, list):
        widths = [int(width) for width in col_widths_obj if isinstance(width, int)]
        if widths:
            tab.view_controller.set_column_widths(widths)

    expanded_paths: list[tuple[int, ...]] = []
    if isinstance(expanded_obj, list):
        for path in expanded_obj:
            if not isinstance(path, tuple):
                continue
            normalized = tuple(step for step in path if isinstance(step, int) and step >= 0)
            expanded_paths.append(normalized)

    if expanded_paths:
        tab.view_controller.request_collapse_all()
        if _is_large_load(tab):
            _request_expand_paths_chunked(tab, expanded_paths)
        else:
            for path in expanded_paths:
                tab.view_controller.request_expand(path)

    if isinstance(current_path_obj, tuple):
        current_path = tuple(step for step in current_path_obj if isinstance(step, int) and step >= 0)
        if current_path:
            if _is_large_load(tab):
                tab.view_controller.request_select_paths_deferred([current_path])
                tab.view_controller.request_scroll_to_deferred(current_path)
            else:
                tab.view_controller.request_select_paths([current_path])
                tab.view_controller.request_scroll_to(current_path)

    h_scroll = int(h_scroll_obj) if isinstance(h_scroll_obj, int) else 0
    v_scroll = int(v_scroll_obj) if isinstance(v_scroll_obj, int) else 0

    def _restore_scrollbars() -> None:
        tab.view.horizontalScrollBar().setValue(h_scroll)
        tab.view.verticalScrollBar().setValue(v_scroll)

    QTimer.singleShot(0, _restore_scrollbars)
