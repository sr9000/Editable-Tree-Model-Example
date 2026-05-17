"""test_validation_yaml.py — YAML schemas and YAML document validation.

Verifies:
- A schema stored as a YAML file loads and validates correctly.
- An inline ``$schema: ./my.yaml`` key is discovered and applied.
- A YAML document that violates its YAML schema produces the right issues.
"""

from __future__ import annotations

import pytest


from pathlib import Path

from io_formats.load import load_file_with_format
from validation.schema_source import SchemaRef, discover_schema, load_schema
from validation.validator import validate_document

# ── helpers ──────────────────────────────────────────────────────────────


def _write_yaml_schema(path: Path) -> None:
    path.write_text(
        "type: object\n"
        "required:\n"
        "  - name\n"
        "properties:\n"
        "  name:\n"
        "    type: string\n"
        "  age:\n"
        "    type: integer\n",
        encoding="utf-8",
    )


# ── inline $schema reference ──────────────────────────────────────────────


def test_yaml_inline_schema_ref_is_discovered(tmp_path):
    schema_path = tmp_path / "person.yaml"
    _write_yaml_schema(schema_path)

    doc_path = tmp_path / "doc.yaml"
    doc_path.write_text(
        f"$schema: ./person.yaml\nname: Alice\nage: 30\n",
        encoding="utf-8",
    )

    data, _fmt = load_file_with_format(str(doc_path))
    ref = discover_schema(doc_path, data)

    assert ref.origin == "inline"
    assert ref.path == schema_path


def test_yaml_inline_schema_ref_loads_and_validates_ok(tmp_path):
    schema_path = tmp_path / "person.yaml"
    _write_yaml_schema(schema_path)

    doc_path = tmp_path / "doc.yaml"
    doc_path.write_text(
        f"$schema: ./person.yaml\nname: Alice\nage: 30\n",
        encoding="utf-8",
    )

    data, _fmt = load_file_with_format(str(doc_path))
    ref = discover_schema(doc_path, data)
    schema = load_schema(ref)

    assert schema is not None
    issues = validate_document(data, schema)
    # The document is valid — no issues expected
    assert issues == []


def test_yaml_inline_schema_ref_reports_type_violation(tmp_path):
    schema_path = tmp_path / "person.yaml"
    _write_yaml_schema(schema_path)

    doc_path = tmp_path / "doc.yaml"
    # "age" should be integer; we supply a string — expect a type error
    doc_path.write_text(
        f"$schema: ./person.yaml\nname: Alice\nage: thirty\n",
        encoding="utf-8",
    )

    data, _fmt = load_file_with_format(str(doc_path))
    ref = discover_schema(doc_path, data)
    schema = load_schema(ref)

    issues = validate_document(data, schema)
    assert len(issues) >= 1
    assert any(i.kind == "type" for i in issues)


# ── YAML schema loaded via SchemaRef (manual) ─────────────────────────────


def test_yaml_schema_file_loads_via_schema_ref(tmp_path):
    schema_path = tmp_path / "schema.yaml"
    _write_yaml_schema(schema_path)

    ref = SchemaRef(path=schema_path, inline=None, origin="manual")
    schema = load_schema(ref)

    assert schema is not None
    assert schema.get("type") == "object"
    assert "name" in schema.get("required", [])


def test_yaml_schema_missing_required_field_produces_required_issue(tmp_path):
    schema_path = tmp_path / "schema.yaml"
    _write_yaml_schema(schema_path)

    ref = SchemaRef(path=schema_path, inline=None, origin="manual")
    schema = load_schema(ref)
    assert schema is not None

    # Document missing the required "name" field
    issues = validate_document({"age": 30}, schema)
    assert len(issues) >= 1
    assert any(i.kind == "required" for i in issues)


def test_yaml_schema_via_sibling_file(tmp_path):
    # If a sibling "<doc>.schema.json" exists it should be picked up
    doc_path = tmp_path / "data.yaml"
    doc_path.write_text("name: Bob\n", encoding="utf-8")

    sibling = tmp_path / "data.schema.json"
    sibling.write_text('{"type": "object", "required": ["name"]}', encoding="utf-8")

    ref = discover_schema(doc_path, {"name": "Bob"})
    assert ref.origin == "sibling"
    assert ref.path == sibling


# ── sanitization round-trip ───────────────────────────────────────────────


def test_sanitize_then_validate_with_yaml_schema(tmp_path):
    """Sanitization (mpq → float) does not prevent a YAML schema from working."""
    from gmpy2 import mpq

    from validation._sanitize import to_jsonschema_input

    schema_path = tmp_path / "schema.yaml"
    schema_path.write_text(
        "type: object\nproperties:\n  ratio:\n    type: number\n",
        encoding="utf-8",
    )
    ref = SchemaRef(path=schema_path, inline=None, origin="manual")
    schema = load_schema(ref)
    assert schema is not None

    data = {"ratio": mpq("1/3")}
    sanitized = to_jsonschema_input(data)
    assert isinstance(sanitized["ratio"], float)

    issues = validate_document(sanitized, schema)
    assert issues == []
