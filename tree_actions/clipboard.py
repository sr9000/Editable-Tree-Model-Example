import json
from typing import Any

import simplejson
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication, QTreeView

from mpq2py import mpq_json_default
from tree.model import JsonTreeModel
from tree.types import JsonType
from tree_actions.selection import _index_path, _is_ancestor, _resolve_model, _selected_rows, selection_shape
from tree_actions.selection import top_level_source_rows as _top_level_selected_rows

MIME_JSON_TREE = "application/x-json-tree"


def _get_val_str(item) -> str:
    return simplejson.dumps(item.to_json(), default=mpq_json_default, indent=2)


def _project_subtree(item, selected_paths: set[tuple[int, ...]], item_path: tuple[int, ...]) -> Any:
    """Recursively prune *item*'s subtree so only children that lead to a
    selected descendant survive.

    Children directly selected (``selected_paths`` contains their path)
    are kept whole. Containers that have any selected descendant beneath
    them are kept with their non-contributing siblings pruned. Leaves
    not on any selected path are dropped.
    """
    if item.json_type is JsonType.OBJECT:
        result: dict[str, Any] = {}
        for i, child in enumerate(item.child_items):
            child_path = item_path + (i,)
            if child_path in selected_paths:
                result[child.name] = child.to_json()
                continue
            if any(_path_starts_with(sp, child_path) for sp in selected_paths):
                result[child.name] = _project_subtree(child, selected_paths, child_path)
        return result
    if item.json_type is JsonType.ARRAY:
        result_arr: list[Any] = []
        for i, child in enumerate(item.child_items):
            child_path = item_path + (i,)
            if child_path in selected_paths:
                result_arr.append(child.to_json())
                continue
            if any(_path_starts_with(sp, child_path) for sp in selected_paths):
                result_arr.append(_project_subtree(child, selected_paths, child_path))
        return result_arr
    # Primitive — return as-is (only reachable when selected directly).
    return item.to_json()


def _path_starts_with(path: tuple[int, ...], prefix: tuple[int, ...]) -> bool:
    return len(path) > len(prefix) and path[: len(prefix)] == prefix


def _build_copy_entries(model: JsonTreeModel, rows) -> list[dict[str, Any]]:
    """Build clipboard entries from *rows*.

    Branches on selection shape:

    - **Disjoint** (or single): one entry per row, full subtree
      (current behaviour).
    - **Filter** (any ancestor/descendant pair): for each top-level
      ancestor whose subtree contains a selected descendant, produce a
      *projected* entry containing only paths leading to the selected
      descendants. Other top-level rows pass through whole.
    """
    if not rows:
        return []

    shape = selection_shape(rows)
    if shape != "filter":
        entries: list[dict[str, Any]] = []
        for idx in rows:
            item = model.get_item(idx)
            entries.append(
                {
                    "name": item.name if isinstance(item.name, str) else None,
                    "value": item.to_json(),
                }
            )
        return entries

    # Filter mode: build the projection.
    selected_paths = {_index_path(idx) for idx in rows}
    # Top-level ancestors are the rows whose path is not a strict
    # descendant of any other selected row.
    top_level = [idx for idx in rows if not any(_is_ancestor(other, idx) for other in rows if other is not idx)]
    top_level.sort(key=_index_path)

    entries = []
    for idx in top_level:
        item = model.get_item(idx)
        idx_path = _index_path(idx)
        # If any selected row is a strict descendant, project; else keep whole.
        has_selected_descendant = any(_path_starts_with(sp, idx_path) for sp in selected_paths)
        if has_selected_descendant:
            projected = _project_subtree(item, selected_paths, idx_path)
        else:
            projected = item.to_json()
        entries.append(
            {
                "name": item.name if isinstance(item.name, str) else None,
                "value": projected,
            }
        )
    return entries


def _entries_text_payload(model: JsonTreeModel, rows, entries: list[dict[str, Any]]) -> Any:
    if not entries:
        return None

    # For filter-mode selections, the entries list only includes top-level
    # ancestors. Restrict the same-parent / all-named check to the rows that
    # correspond to those entries.
    top_level = [idx for idx in rows if not any(_is_ancestor(other, idx) for other in rows if other is not idx)]
    if not top_level:
        top_level = list(rows)

    first_parent = top_level[0].parent()
    same_parent = all(idx.parent() == first_parent for idx in top_level)
    all_named = all(isinstance(entry.get("name"), str) and entry["name"] for entry in entries)

    if same_parent and all_named and len(entries) == len(top_level):
        parent_item = model.get_item(first_parent)
        if parent_item.json_type is JsonType.OBJECT:
            names = [entry["name"] for entry in entries]
            if len(set(names)) == len(names):
                return {entry["name"]: entry["value"] for entry in entries}

    if len(entries) == 1:
        return entries[0]["value"]
    return [entry["value"] for entry in entries]


# ---------------------------------------------------------------------------
# Public MIME (de)serializer — canonical wire format
# ---------------------------------------------------------------------------


def build_tree_mime(model: JsonTreeModel, source_rows) -> QMimeData | None:
    """Build a ``QMimeData`` object for *source_rows* (already sorted/pruned).

    Returns ``None`` when *source_rows* is empty.

    Wire format:
    - ``application/x-json-tree``: UTF-8 JSON ``{"entries": [{name, value}…]}``
    - ``text/plain``: human-readable value(s) (dict, list, or scalar literal)
    """
    rows = sorted(source_rows, key=_index_path)
    if not rows:
        return None

    entries = _build_copy_entries(model, rows)
    text_payload = _entries_text_payload(model, rows, entries)

    metadata = simplejson.dumps({"entries": entries}, default=mpq_json_default)
    text = simplejson.dumps(text_payload, default=mpq_json_default, indent=2)

    mime = QMimeData()
    mime.setData(MIME_JSON_TREE, metadata.encode("utf-8"))
    mime.setText(text)
    return mime


def entries_from_mime(mime: QMimeData) -> list[dict[str, Any]] | None:
    """Decode tree entries from a ``QMimeData`` object.

    Returns a list of ``{"name": str|None, "value": <json>}`` dicts, or
    ``None`` when the MIME data contains nothing paste-able.

    This is a pure function — it does **not** touch the system clipboard.
    """
    if mime is None:
        return None

    if mime.hasFormat(MIME_JSON_TREE):
        try:
            raw = mime.data(MIME_JSON_TREE).data().decode("utf-8")
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                entries = parsed.get("entries")
                if isinstance(entries, list):
                    normalized: list[dict[str, Any]] = []
                    for entry in entries:
                        if not isinstance(entry, dict) or "value" not in entry:
                            continue
                        name = entry.get("name")
                        normalized.append({"name": name if isinstance(name, str) else None, "value": entry["value"]})
                    if normalized:
                        return normalized

                items = parsed.get("items")
                if isinstance(items, list):
                    return [{"name": None, "value": value} for value in items]
        except Exception:
            pass

    text = mime.text().strip()
    if not text:
        return None

    try:
        parsed = json.loads(text)
    except Exception:
        return None

    if isinstance(parsed, dict):
        return [{"name": str(name), "value": value} for name, value in parsed.items()]
    if isinstance(parsed, list):
        return [{"name": None, "value": value} for value in parsed]
    return [{"name": None, "value": parsed}]


def _clipboard_entries() -> list[dict[str, Any]] | None:
    return entries_from_mime(QApplication.clipboard().mimeData())


# ---------------------------------------------------------------------------
# Clipboard copy actions — thin orchestrators over build_tree_mime
# ---------------------------------------------------------------------------


def copy_selection(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    # Step 9: pass the FULL selection so filter-mode (ancestor + descendant
    # both selected) projects ancestor subtrees down to selected descendants.
    rows = _selected_rows(tree_view)
    mime = build_tree_mime(model, rows)
    if mime is None:
        return False

    QApplication.clipboard().setMimeData(mime)
    return True


def copy_selection_with_name(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    rows = sorted(_top_level_selected_rows(tree_view), key=_index_path)
    if not rows:
        return False

    entries = _build_copy_entries(model, rows)

    if len(rows) == 1:
        item = model.get_item(rows[0])
        val_str = _get_val_str(item)
        if item.name is not None:
            name_str = simplejson.dumps(item.name, default=mpq_json_default)
            text = f"{name_str}: {val_str}"
        else:
            text = val_str
    else:
        text_payload = _entries_text_payload(model, rows, entries)
        text = simplejson.dumps(text_payload, default=mpq_json_default, indent=2)

    metadata = simplejson.dumps({"entries": entries}, default=mpq_json_default)
    mime = QMimeData()
    mime.setData(MIME_JSON_TREE, metadata.encode("utf-8"))
    mime.setText(text)
    QApplication.clipboard().setMimeData(mime)
    return True


def copy_selection_value_only(tree_view: QTreeView) -> bool:
    model, _proxy = _resolve_model(tree_view)
    if model is None:
        return False

    rows = sorted(_top_level_selected_rows(tree_view), key=_index_path)
    if not rows:
        return False

    if len(rows) == 1:
        item = model.get_item(rows[0])
        text = _get_val_str(item)
    else:
        entries = _build_copy_entries(model, rows)
        text_payload = _entries_text_payload(model, rows, entries)
        text = simplejson.dumps(text_payload, default=mpq_json_default, indent=2)

    mime = QMimeData()
    mime.setText(text)
    QApplication.clipboard().setMimeData(mime)
    return True
