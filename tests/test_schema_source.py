from pathlib import Path

from validation.schema_source import discover_schema, load_schema


def test_discover_schema_prefers_inline_local_ref_over_sibling(tmp_path):
    doc_path = tmp_path / "doc.json"
    doc_path.write_text("{}", encoding="utf-8")

    inline_schema_path = tmp_path / "inline.yaml"
    inline_schema_path.write_text("type: object\nproperties:\n  value:\n    type: integer\n", encoding="utf-8")

    sibling_schema_path = tmp_path / "doc.schema.json"
    sibling_schema_path.write_text('{"type": "object", "required": ["missing"]}', encoding="utf-8")

    data = {"$schema": "./inline.yaml", "value": 1}
    ref = discover_schema(doc_path, data)

    assert ref.origin == "inline"
    assert isinstance(ref.path, Path)
    assert ref.path == inline_schema_path
    loaded = load_schema(ref)
    assert loaded is not None
    assert loaded.get("type") == "object"


def test_discover_schema_ignores_remote_schema_url():
    ref = discover_schema(None, {"$schema": "https://example.com/schema.json", "value": 1})
    assert ref.origin == "none"
    assert ref.path is None
    assert ref.inline is None


def test_discover_schema_falls_back_to_sibling_schema(tmp_path):
    doc_path = tmp_path / "sample.yaml"
    doc_path.write_text("value: 1\n", encoding="utf-8")

    sibling_schema_path = tmp_path / "sample.schema.json"
    sibling_schema_path.write_text('{"type": "object", "required": ["value"]}', encoding="utf-8")

    ref = discover_schema(doc_path, {"value": 1})

    assert ref.origin == "sibling"
    assert ref.path == sibling_schema_path
    loaded = load_schema(ref)
    assert loaded is not None
    assert loaded.get("required") == ["value"]


def test_load_schema_supports_yaml_files(tmp_path):
    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text("type: object\nrequired:\n  - value\n", encoding="utf-8")

    ref = discover_schema(tmp_path / "doc.json", {"$schema": "schema.yaml", "value": 1})
    loaded = load_schema(ref)

    assert ref.origin == "inline"
    assert loaded is not None
    assert loaded.get("required") == ["value"]
