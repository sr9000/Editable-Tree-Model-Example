from PySide6.QtCore import QModelIndex, Qt

from core.frozen_value import FrozenValue
from io_formats import SAVE_FORMAT_JSON, dump_text, load_file_with_format
from io_formats.load import _safe_parse_float
from tree.model import JsonTreeModel
from tree.types import JsonType, parse_json_type
from units.number_affix import parse_number_affix

_UNSAFE_NUMERIC = "31e-327018450730"


def test_affix_parser_rejects_unsafe_exponent_literal() -> None:
    assert parse_number_affix(f"$ {_UNSAFE_NUMERIC}") is None
    assert parse_number_affix(f"{_UNSAFE_NUMERIC} m/s") is None


def test_json_loader_freezes_unsafe_float_literal(tmp_path) -> None:
    path = tmp_path / "unsafe.json"
    path.write_text(
        '{"float": 31e-327018450730, "string": "$ 31e-327018450730"}\n',
        encoding="utf-8",
    )

    loaded, fmt = load_file_with_format(str(path))

    assert fmt == SAVE_FORMAT_JSON
    assert isinstance(loaded["float"], FrozenValue)
    assert loaded["float"].raw == _UNSAFE_NUMERIC
    assert loaded["string"] == "$ 31e-327018450730"
    assert parse_json_type(loaded["float"]) is JsonType.FLOAT

    dumped = dump_text(str(path), loaded, save_format=SAVE_FORMAT_JSON)
    assert '"float": 31e-327018450730' in dumped


def test_frozen_float_is_not_inline_editable() -> None:
    model = JsonTreeModel({"float": FrozenValue(_UNSAFE_NUMERIC)})

    item = model.get_item(model.index(0, 0, QModelIndex()))
    value_index = model.index(0, 2, QModelIndex())

    assert item.json_type is JsonType.FLOAT
    assert item.editable is False
    assert (model.flags(value_index) & Qt.ItemFlag.ItemIsEditable) == Qt.ItemFlag.NoItemFlags


def test_safe_parse_float_rejects_invalid_literal_before_mpq() -> None:
    parsed = _safe_parse_float("not-a-float")
    assert isinstance(parsed, FrozenValue)
    assert parsed.reason == "json-float-invalid"
