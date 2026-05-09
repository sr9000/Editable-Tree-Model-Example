import json
from typing import Any

import simplejson
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication, QTreeView

from mpq2py import mpq_json_default
from tree.model import JsonTreeModel
from tree.types import JsonType
from tree_actions.selection import _index_path, _resolve_model, top_level_source_rows as _top_level_selected_rows

MIME_JSON_TREE = "application/x-json-tree"


def _get_val_str(item) -> str:
    return simplejson.dumps(item.to_json(), default=mpq_json_default, indent=2)


def _build_copy_entries(model: JsonTreeModel, rows) -> list[dict[str, Any]]:
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


def _entries_text_payload(model: JsonTreeModel, rows, entries: list[dict[str, Any]]) -> Any:
    if not entries:
        return None

    first_parent = rows[0].parent()
    same_parent = all(idx.parent() == first_parent for idx in rows)
    all_named = all(isinstance(entry.get("name"), str) and entry["name"] for entry in entries)

    if same_parent and all_named:
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

    rows = _top_level_selected_rows(tree_view)
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
