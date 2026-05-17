from __future__ import annotations

from PySide6.QtCore import QSettings

from dialogs.attach_schema_dlg import AttachSchemaDialog
from settings import APPLICATION_ID
from state.recent_schemas import push_recent_schema
from validation.schema_registry import SchemaSource


def _settings() -> QSettings:
    return QSettings(APPLICATION_ID, "validation")


def setup_function() -> None:
    _settings().clear()


def teardown_function() -> None:
    _settings().clear()


def test_parse_source_accepts_existing_file(tmp_path):
    schema_path = tmp_path / "person.schema.json"
    schema_path.write_text('{"type":"object"}', encoding="utf-8")

    source = AttachSchemaDialog.parse_source(str(schema_path))

    assert source is not None
    assert source.kind == "file"
    assert source.key == str(schema_path.resolve())


def test_parse_source_accepts_http_url():
    source = AttachSchemaDialog.parse_source("https://example.com/person.schema.json")

    assert source is not None
    assert source.kind == "url"
    assert source.key == "https://example.com/person.schema.json"


def test_parse_source_rejects_missing_file(tmp_path):
    missing = tmp_path / "missing.schema.json"

    source = AttachSchemaDialog.parse_source(str(missing))

    assert source is None


def test_recent_combo_prefills_line_edit_on_selection(qtbot, tmp_path):
    schema_path = tmp_path / "person.schema.json"
    schema_path.write_text('{"type":"object"}', encoding="utf-8")
    file_source = SchemaSource.for_file(schema_path)
    url_source = SchemaSource.for_url("https://example.com/person.schema.json")
    push_recent_schema(file_source)
    push_recent_schema(url_source)

    dlg = AttachSchemaDialog(recent_sources=None)
    qtbot.addWidget(dlg)

    assert not dlg._recent_row_widget.isHidden()
    assert dlg._recent_combo.count() == 2

    dlg._recent_combo.setCurrentIndex(0)
    assert dlg._edit.text() == url_source.key


def test_recent_combo_row_hidden_when_empty(qtbot):
    dlg = AttachSchemaDialog(recent_sources=[])
    qtbot.addWidget(dlg)

    assert dlg._recent_row_widget.isHidden()
