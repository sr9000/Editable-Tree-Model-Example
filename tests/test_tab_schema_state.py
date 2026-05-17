from pathlib import Path

from documents.tab import JsonTab
from validation.schema_source import SchemaRef


def test_tab_initializes_schema_and_validation_state_from_inline_ref(qtbot, tmp_path):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        '{"type":"object","properties":{"value":{"type":"integer"},"$schema":{"type":"string"}},"required":["value"]}',
        encoding="utf-8",
    )

    data = {
        "$schema": str(schema_path),
        "value": 10,
    }

    tab = JsonTab(lambda *_: None, data=data, file_path=str(tmp_path / "doc.json"), show_root=True)
    qtbot.addWidget(tab)

    assert tab.schema_ref.origin == "inline"
    assert tab.schema is not None
    assert len(tab.issue_index) == 0


def test_tab_set_schema_emits_signals_and_revalidates(qtbot):
    tab = JsonTab(lambda *_: None, data={"value": 10}, show_root=True)
    qtbot.addWidget(tab)

    schema = {
        "type": "object",
        "properties": {
            "value": {"type": "string"},
        },
        "required": ["value"],
    }

    with qtbot.waitSignal(tab.schemaChanged, timeout=1000):
        with qtbot.waitSignal(tab.validationChanged, timeout=1000):
            tab.set_schema(SchemaRef(path=None, inline=schema, origin="manual"))

    assert tab.schema_ref.origin == "manual"
    assert tab.schema is not None
    assert len(tab.issue_index) == 1


def test_tab_set_schema_path_sets_file_schema_source(qtbot, tmp_path):
    schema_path = tmp_path / "schema.json"
    schema_path.write_text('{"type":"object","properties":{"value":{"type":"integer"}}}', encoding="utf-8")

    tab = JsonTab(lambda *_: None, data={"value": 10}, show_root=True)
    qtbot.addWidget(tab)

    tab.set_schema(SchemaRef(path=schema_path, inline=None, origin="manual"))

    assert tab.schema_source is not None
    assert tab.schema_source.kind == "file"


def test_tab_clear_schema_resets_to_none_and_clears_issue_index(qtbot):
    tab = JsonTab(lambda *_: None, data={"value": 10}, show_root=True)
    qtbot.addWidget(tab)

    schema = {
        "type": "object",
        "properties": {
            "value": {"type": "string"},
        },
        "required": ["value"],
    }
    tab.set_schema(SchemaRef(path=None, inline=schema, origin="manual"))
    assert len(tab.issue_index) == 1

    with qtbot.waitSignal(tab.validationChanged, timeout=1000):
        tab.clear_schema()

    assert tab.schema_ref.origin == "none"
    assert tab.schema is None
    assert len(tab.issue_index) == 0


def test_validation_settings_stub_roundtrip(tmp_path):
    from state.validation_settings import read_schema_path, write_schema_path

    doc_path = tmp_path / "doc.json"
    schema_path = tmp_path / "schema.json"

    write_schema_path(Path(doc_path), Path(schema_path))
    assert read_schema_path(Path(doc_path)) == schema_path
