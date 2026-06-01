import simplejson
from gmpy2 import mpq

from io_formats import SAVE_FORMAT_JSON, SAVE_FORMAT_YAML, dump_text, load_file_with_format
from tree.types import JsonType, parse_json_type
from units.number_affix import AffixKind, NumberAffix


def _fixture_tree() -> dict[str, str | int | float]:
    return {
        "int_prefix_nospace": "$1234",
        "int_prefix_space": "$ 1234",
        "int_suffix_nospace": "1234%",
        "float_prefix_nospace": "$3.5",
        "float_suffix_space": "99.95 %",
        "float_suffix_nospace": "3.14rad",
        "bare_int": 1234,
        "bare_float": 3.14,
    }


def test_json_round_trip_is_stable_and_typed(tmp_path) -> None:
    payload = _fixture_tree()
    path = tmp_path / "affix.json"
    path.write_text(simplejson.dumps(payload, indent=2) + "\n", encoding="utf-8")

    loaded, fmt = load_file_with_format(str(path))
    assert fmt == SAVE_FORMAT_JSON
    assert isinstance(loaded["int_prefix_nospace"], NumberAffix)
    assert loaded["int_prefix_nospace"] == NumberAffix(AffixKind.CURRENCY, "$", False, 1234)
    assert parse_json_type(loaded["int_prefix_nospace"]) is JsonType.INTEGER_CURRENCY
    assert isinstance(loaded["bare_int"], int)

    first_dump = dump_text(str(path), loaded, save_format=SAVE_FORMAT_JSON)
    path.write_text(first_dump, encoding="utf-8")
    loaded2, _ = load_file_with_format(str(path))
    second_dump = dump_text(str(path), loaded2, save_format=SAVE_FORMAT_JSON)
    assert first_dump == second_dump


def test_yaml_round_trip_is_stable_and_typed(tmp_path) -> None:
    payload = _fixture_tree()
    path = tmp_path / "affix.yaml"
    path.write_text(dump_text(str(path), payload, save_format=SAVE_FORMAT_YAML), encoding="utf-8")

    loaded, fmt = load_file_with_format(str(path))
    assert fmt == SAVE_FORMAT_YAML
    assert isinstance(loaded["float_suffix_nospace"], NumberAffix)
    assert parse_json_type(loaded["float_suffix_nospace"]) is JsonType.FLOAT_UNITS
    assert loaded["bare_float"] == mpq("3.14")

    first_dump = dump_text(str(path), loaded, save_format=SAVE_FORMAT_YAML)
    path.write_text(first_dump, encoding="utf-8")
    loaded2, _ = load_file_with_format(str(path))
    second_dump = dump_text(str(path), loaded2, save_format=SAVE_FORMAT_YAML)
    assert first_dump == second_dump
