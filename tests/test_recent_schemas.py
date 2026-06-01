from __future__ import annotations

from PySide6.QtCore import QSettings

from settings import APPLICATION_ID
from state.recent_schemas import RECENT_SCHEMAS_CAP, clear_recent_schemas, push_recent_schema, recent_schemas
from state.validation_settings import _RECENT_SCHEMAS_KEY
from validation.schema_types import SchemaSource


def _settings() -> QSettings:
    return QSettings(APPLICATION_ID, "validation")


def setup_function() -> None:
    _settings().clear()


def teardown_function() -> None:
    _settings().clear()


def test_push_recent_schema_orders_most_recent_first(tmp_path):
    a = SchemaSource.for_file(tmp_path / "a.schema.json")
    b = SchemaSource.for_url("https://example.com/b")
    c = SchemaSource.for_file(tmp_path / "c.schema.json")

    push_recent_schema(a)
    push_recent_schema(b)
    push_recent_schema(c)

    assert recent_schemas() == [c, b, a]


def test_push_recent_schema_deduplicates_and_moves_to_front(tmp_path):
    a = SchemaSource.for_file(tmp_path / "a.schema.json")
    b = SchemaSource.for_url("https://example.com/b")

    push_recent_schema(a)
    push_recent_schema(b)
    push_recent_schema(a)

    assert recent_schemas() == [a, b]


def test_recent_schemas_enforces_cap(tmp_path):
    sources = [SchemaSource.for_file(tmp_path / f"s{i}.schema.json") for i in range(RECENT_SCHEMAS_CAP + 1)]
    for source in sources:
        push_recent_schema(source)

    recents = recent_schemas()
    assert len(recents) == RECENT_SCHEMAS_CAP
    assert recents[0] == sources[-1]
    assert sources[0] not in recents


def test_recent_schemas_filters_malformed_payload_entries(tmp_path):
    valid = SchemaSource.for_file(tmp_path / "ok.schema.json")
    _settings().setValue(_RECENT_SCHEMAS_KEY, ["garbage", "unknown:value", "url:", f"file:{valid.key}"])

    assert recent_schemas() == [valid]


def test_clear_recent_schemas_empties_list(tmp_path):
    push_recent_schema(SchemaSource.for_file(tmp_path / "a.schema.json"))
    assert recent_schemas()

    clear_recent_schemas()

    assert recent_schemas() == []
