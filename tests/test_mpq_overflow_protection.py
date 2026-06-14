from PySide6.QtCore import QModelIndex, Qt

from core.raw_numeric import REASON_INVALID_FORMAT, RawNumericValue
from io_formats import SAVE_FORMAT_JSON, dump_text, load_file_with_format
from io_formats.load import _safe_parse_float
from tree.model import JsonTreeModel
from tree.types import JsonType, parse_json_type
from units.number_affix import parse_number_affix

_UNSAFE_NUMERIC = "31e-327018450730"


def test_affix_parser_rejects_unsafe_exponent_literal() -> None:
    assert parse_number_affix(f"$ {_UNSAFE_NUMERIC}") is None
    assert parse_number_affix(f"{_UNSAFE_NUMERIC} m/s") is None


def test_json_loader_preserves_unsafe_float_literal_as_raw(tmp_path) -> None:
    path = tmp_path / "unsafe.json"
    path.write_text(
        '{"float": 31e-327018450730, "string": "$ 31e-327018450730"}\n',
        encoding="utf-8",
    )

    loaded, fmt = load_file_with_format(str(path))

    assert fmt == SAVE_FORMAT_JSON
    assert isinstance(loaded["float"], RawNumericValue)
    assert loaded["float"].raw == _UNSAFE_NUMERIC
    assert loaded["string"] == "$ 31e-327018450730"
    assert parse_json_type(loaded["float"]) is JsonType.RAW_FLOAT

    # The raw token is a valid JSON number, so it round-trips byte-for-byte.
    dumped = dump_text(str(path), loaded, save_format=SAVE_FORMAT_JSON)
    assert '"float": 31e-327018450730' in dumped


def test_raw_numeric_value_is_inline_editable() -> None:
    model = JsonTreeModel({"float": RawNumericValue(_UNSAFE_NUMERIC)})

    item = model.get_item(model.index(0, 0, QModelIndex()))
    value_index = model.index(0, 2, QModelIndex())

    assert item.json_type is JsonType.RAW_FLOAT
    assert item.editable is True
    assert (model.flags(value_index) & Qt.ItemFlag.ItemIsEditable) == Qt.ItemFlag.ItemIsEditable


def test_editing_raw_numeric_into_supported_number_converts_to_float() -> None:
    model = JsonTreeModel({"float": RawNumericValue(_UNSAFE_NUMERIC)})
    item = model.get_item(model.index(0, 0, QModelIndex()))
    value_index = model.index(0, 2, QModelIndex())

    assert model.setData(value_index, "1.5", Qt.ItemDataRole.EditRole) is True
    assert item.json_type is JsonType.FLOAT
    assert not isinstance(item.value, RawNumericValue)


def test_editing_raw_numeric_unchanged_preserves_raw() -> None:
    model = JsonTreeModel({"float": RawNumericValue(_UNSAFE_NUMERIC)})
    item = model.get_item(model.index(0, 0, QModelIndex()))
    value_index = model.index(0, 2, QModelIndex())

    assert model.setData(value_index, _UNSAFE_NUMERIC, Qt.ItemDataRole.EditRole) is True
    assert item.json_type is JsonType.RAW_FLOAT
    assert isinstance(item.value, RawNumericValue)
    assert item.value.raw == _UNSAFE_NUMERIC


def test_editing_raw_numeric_into_unsupported_but_valid_shape_stays_raw() -> None:
    model = JsonTreeModel({"float": RawNumericValue(_UNSAFE_NUMERIC)})
    item = model.get_item(model.index(0, 0, QModelIndex()))
    value_index = model.index(0, 2, QModelIndex())

    # Still underflowing, but matches the narrow edit grammar → kept raw.
    assert model.setData(value_index, "9e-99999", Qt.ItemDataRole.EditRole) is True
    assert item.json_type is JsonType.RAW_FLOAT
    assert isinstance(item.value, RawNumericValue)
    assert item.value.raw == "9e-99999"


def test_editing_raw_numeric_with_invalid_text_is_rejected() -> None:
    model = JsonTreeModel({"float": RawNumericValue(_UNSAFE_NUMERIC)})
    item = model.get_item(model.index(0, 0, QModelIndex()))
    value_index = model.index(0, 2, QModelIndex())

    assert model.setData(value_index, "not-a-number", Qt.ItemDataRole.EditRole) is False
    assert item.json_type is JsonType.RAW_FLOAT
    assert item.value.raw == _UNSAFE_NUMERIC


def test_safe_parse_float_rejects_invalid_literal_before_mpq() -> None:
    parsed = _safe_parse_float("not-a-float")
    assert isinstance(parsed, RawNumericValue)
    assert parsed.reason == REASON_INVALID_FORMAT
