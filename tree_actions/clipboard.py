import json
from typing import Any

import simplejson
import yaml
from PySide6.QtCore import QMimeData
from PySide6.QtWidgets import QApplication, QTreeView

from core.raw_numeric import REASON_UNKNOWN, RawNumericValue
from io_formats import SAVE_FORMAT_JSON, load_text_with_format
from mpq2py import MpqSafeDumper, mpq_json_default, raw_numeric_is_json_safe
from tree.model import JsonTreeModel
from tree.types import JsonType
from tree_actions.selection import _index_path, _is_ancestor, _resolve_model, _selected_rows, selection_shape
from tree_actions.selection import top_level_source_rows as _top_level_selected_rows

MIME_JSON_TREE = "application/x-json-tree"


def _clipboard_text_default(obj: Any):
    """Lenient default for *human-readable* clipboard text.

    Raw numeric values are emitted as JSON number tokens when valid, otherwise
    as a quoted string so copying never produces invalid JSON. High-fidelity
    round-tripping is handled separately by the tagged MIME metadata.
    """
    if isinstance(obj, RawNumericValue):
        if raw_numeric_is_json_safe(obj.raw):
            return simplejson.RawJSON(obj.raw.strip())
        return obj.raw
    return mpq_json_default(obj)


def _mime_meta_default(obj: Any):
    """Strict, lossless default for app-internal MIME metadata.

    Raw numeric values are encoded as a tagged object so paste can reconstruct
    the exact :class:`RawNumericValue` (and keep it as RAW_FLOAT).
    """
    if isinstance(obj, RawNumericValue):
        return {
            "__raw_numeric__": True,
            "raw": obj.raw,
            "reason": obj.reason,
            "source_syntax": obj.source_syntax,
        }
    return mpq_json_default(obj)


def _revive_raw_numeric(value: Any) -> Any:
    """Reconstruct tagged raw numeric objects produced by ``_mime_meta_default``."""
    if isinstance(value, dict):
        if value.get("__raw_numeric__") is True and isinstance(value.get("raw"), str):
            return RawNumericValue(
                raw=value["raw"],
                reason=value.get("reason") or REASON_UNKNOWN,
                source_syntax=value.get("source_syntax") or "",
            )
        return {k: _revive_raw_numeric(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_revive_raw_numeric(v) for v in value]
    return value


def _dump_text(payload: Any) -> str:
    """Serialize *payload* to a string using the configured clipboard text format."""
    from state.clipboard_settings import CLIPBOARD_TEXT_FORMAT_YAML, get_clipboard_text_format

    if get_clipboard_text_format() == CLIPBOARD_TEXT_FORMAT_YAML:
        try:
            return yaml.dump(payload, Dumper=MpqSafeDumper, allow_unicode=True, default_flow_style=False).rstrip()
        except yaml.representer.RepresenterError:
            # Some app-native values (for example NumberAffix) are JSON-serializable
            # via mpq_json_default but do not have direct YAML representers.
            normalized = json.loads(simplejson.dumps(payload, default=_clipboard_text_default))
            return yaml.dump(normalized, Dumper=MpqSafeDumper, allow_unicode=True, default_flow_style=False).rstrip()
    return simplejson.dumps(payload, default=_clipboard_text_default, indent=2)


def _get_val_str(item) -> str:
    return _dump_text(item.to_json())


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


def _path_relative_to_root(model: JsonTreeModel, index) -> tuple[int, ...]:
    """Return an index path relative to ``model.root_item``.

    This path intentionally excludes the synthetic root row when
    ``show_root=True`` so drag metadata matches ``documents.tab_paths``.
    """
    if not index.isValid():
        return ()
    root_item = model.root_item
    if model.get_item(index) is root_item:
        return ()
    path: list[int] = []
    cursor = index
    while cursor.isValid() and model.get_item(cursor) is not root_item:
        path.append(cursor.row())
        cursor = cursor.parent()
    return tuple(reversed(path))


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

    source_paths = [list(_path_relative_to_root(model, idx)) for idx in rows]
    metadata = simplejson.dumps({"entries": entries, "source_paths": source_paths}, default=_mime_meta_default)
    text = _dump_text(text_payload)

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
                        normalized.append(
                            {
                                "name": name if isinstance(name, str) else None,
                                "value": _revive_raw_numeric(entry["value"]),
                            }
                        )
                    if normalized:
                        return normalized

                items = parsed.get("items")
                if isinstance(items, list):
                    return [{"name": None, "value": _revive_raw_numeric(value)} for value in items]
        except Exception:
            pass

    text = mime.text().strip()
    if not text:
        return None

    parsed, _fmt = load_text_with_format(text, allow_scalar_yaml=False)
    if parsed is None:
        return None

    if isinstance(parsed, dict):
        return [{"name": str(name), "value": value} for name, value in parsed.items()]
    if isinstance(parsed, list):
        return [{"name": None, "value": value} for value in parsed]
    return [{"name": None, "value": parsed}]


def source_paths_from_mime(mime: QMimeData) -> list[tuple[int, ...]] | None:
    """Decode optional drag source paths from ``application/x-json-tree``.

    Returns ``None`` when source paths are absent or malformed.
    """
    if mime is None or not mime.hasFormat(MIME_JSON_TREE):
        return None
    try:
        raw = mime.data(MIME_JSON_TREE).data().decode("utf-8")
        parsed = json.loads(raw)
    except Exception:
        return None
    if not isinstance(parsed, dict):
        return None
    raw_paths = parsed.get("source_paths")
    if not isinstance(raw_paths, list):
        return None
    decoded: list[tuple[int, ...]] = []
    for path in raw_paths:
        if not isinstance(path, list) or not all(isinstance(row, int) and row >= 0 for row in path):
            return None
        decoded.append(tuple(path))
    return decoded


def _clipboard_entries() -> list[dict[str, Any]] | None:
    return entries_from_mime(QApplication.clipboard().mimeData())


def clipboard_text_is_valid_data() -> bool:
    """Return True when the system clipboard contains pasteable JSON/YAML or in-app tree data."""
    return entries_from_mime(QApplication.clipboard().mimeData()) is not None


def clipboard_to_tab_data() -> tuple[Any, str | None]:
    """Parse the system clipboard and return (data, save_format) for opening in a new tab.

    Returns (None, None) when the clipboard contains nothing usable.
    save_format uses SAVE_FORMAT_* constants from io_formats.detect.
    """
    mime = QApplication.clipboard().mimeData()
    if mime is None:
        return None, None

    # Internal app MIME takes priority.
    if mime.hasFormat(MIME_JSON_TREE):
        entries = entries_from_mime(mime)
        if entries:
            data = entries[0]["value"] if len(entries) == 1 else [e["value"] for e in entries]
            return data, SAVE_FORMAT_JSON

    text = mime.text().strip()
    if not text:
        return None, None

    data, save_format = load_text_with_format(text, allow_scalar_yaml=False)
    return data, save_format


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
    text_payload = _entries_text_payload(model, rows, entries)
    text = _dump_text(text_payload)

    metadata = simplejson.dumps({"entries": entries}, default=_mime_meta_default)
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
        text = _dump_text(item.to_json())
    else:
        entries = _build_copy_entries(model, rows)
        text_payload = _entries_text_payload(model, rows, entries)
        text = _dump_text(text_payload)

    mime = QMimeData()
    mime.setText(text)
    QApplication.clipboard().setMimeData(mime)
    return True
