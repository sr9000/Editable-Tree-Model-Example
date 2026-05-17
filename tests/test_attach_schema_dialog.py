from __future__ import annotations

from dialogs.attach_schema_dlg import AttachSchemaDialog


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
