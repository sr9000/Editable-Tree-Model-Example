"""Tests for unsupported raw numeric values (RawNumericValue / RAW_FLOAT)."""

from __future__ import annotations

import pytest
import yaml
from PySide6.QtCore import QModelIndex

from core.raw_numeric import REASON_NON_FINITE, REASON_UNDERFLOW, RawNumericValue
from io_formats import SAVE_FORMAT_JSON, SAVE_FORMAT_YAML, dump_text
from mpq2py import MpqSafeLoader
from tree.model import JsonTreeModel
from tree.types import USER_SELECTABLE_TYPES, JsonType, canonical_type, parse_json_type
from validation._sanitize import to_jsonschema_input

_UNSAFE = "31e-327018450730"


# ---------------------------------------------------------------------------
# Type metadata
# ---------------------------------------------------------------------------


def test_raw_numeric_infers_raw_float_pseudo_type() -> None:
    assert parse_json_type(RawNumericValue(_UNSAFE)) is JsonType.RAW_FLOAT


def test_raw_float_is_not_user_selectable() -> None:
    assert JsonType.RAW_FLOAT not in USER_SELECTABLE_TYPES


def test_raw_float_canonical_parent_is_float() -> None:
    assert canonical_type(JsonType.RAW_FLOAT) is JsonType.FLOAT


# ---------------------------------------------------------------------------
# Saving / serialization
# ---------------------------------------------------------------------------


def test_yaml_roundtrip_preserves_raw_numeric_exactly() -> None:
    data = {"a": RawNumericValue(_UNSAFE), "b": RawNumericValue(".inf")}
    text = dump_text("f.yaml", data, save_format=SAVE_FORMAT_YAML)

    reloaded = yaml.load(text, Loader=MpqSafeLoader)
    assert isinstance(reloaded["a"], RawNumericValue)
    assert reloaded["a"].raw == _UNSAFE
    assert isinstance(reloaded["b"], RawNumericValue)
    assert reloaded["b"].raw == ".inf"


def test_json_dump_of_json_safe_raw_roundtrips() -> None:
    data = {"x": RawNumericValue(_UNSAFE, source_syntax="json")}
    text = dump_text("f.json", data, save_format=SAVE_FORMAT_JSON)
    assert f'"x": {_UNSAFE}' in text


def test_json_dump_of_non_json_safe_raw_raises_controlled_error() -> None:
    data = {"x": RawNumericValue(".inf", reason=REASON_NON_FINITE, source_syntax="yaml")}
    with pytest.raises(ValueError):
        dump_text("f.json", data, save_format=SAVE_FORMAT_JSON)


# ---------------------------------------------------------------------------
# Clipboard / drag-drop metadata fidelity
# ---------------------------------------------------------------------------


def test_clipboard_mime_roundtrip_preserves_raw_numeric(qtbot) -> None:
    from tree_actions.clipboard import build_tree_mime, entries_from_mime

    model = JsonTreeModel({"x": RawNumericValue(".inf", reason=REASON_NON_FINITE, source_syntax="yaml")})
    row0 = model.index(0, 0, QModelIndex())

    mime = build_tree_mime(model, [row0])
    assert mime is not None

    entries = entries_from_mime(mime)
    assert entries is not None
    value = entries[0]["value"]
    assert isinstance(value, RawNumericValue)
    assert value.raw == ".inf"
    assert value.reason == REASON_NON_FINITE


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def test_validation_sanitize_converts_raw_numeric_to_string() -> None:
    out = to_jsonschema_input({"x": RawNumericValue(_UNSAFE)})
    assert out["x"] == _UNSAFE


# ---------------------------------------------------------------------------
# Editor
# ---------------------------------------------------------------------------


def test_raw_float_editor_is_text_and_warns_once(qtbot) -> None:
    from PySide6.QtWidgets import QStyleOptionViewItem, QWidget

    from delegates.edit_context import DefaultEditContext
    from delegates.value import ValueDelegate
    from editors.inline.raw_numeric_line import RawNumericLineEdit

    class _RecordingContext(DefaultEditContext):
        def __init__(self) -> None:
            super().__init__()
            self.warn_reasons: list[str] = []

        def warn_raw_numeric_edit(self, parent, *, reason: str) -> None:  # type: ignore[override]
            self.warn_reasons.append(reason)

    model = JsonTreeModel({"x": RawNumericValue(_UNSAFE, reason=REASON_UNDERFLOW)})
    ctx = _RecordingContext()
    delegate = ValueDelegate(edit_context=ctx)

    parent = QWidget()
    qtbot.addWidget(parent)
    idx = model.index(0, 2, QModelIndex())

    editor = delegate.createEditor(parent, QStyleOptionViewItem(), idx)

    assert isinstance(editor, RawNumericLineEdit)
    assert ctx.warn_reasons == [REASON_UNDERFLOW]
