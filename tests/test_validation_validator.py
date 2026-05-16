import jsonschema
import pytest


from validation.validator import is_schema_valid, validate_document


def test_validate_document_ok_returns_empty_list():
    data = {"name": "Alice", "age": 30}
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
    }

    issues = validate_document(data, schema)
    assert issues == []


def test_validate_document_missing_required_reports_required_kind():
    data = {"age": 30}
    schema = {
        "type": "object",
        "properties": {
            "name": {"type": "string"},
            "age": {"type": "integer"},
        },
        "required": ["name", "age"],
    }

    issues = validate_document(data, schema)
    assert len(issues) == 1
    assert issues[0].kind == "required"
    assert issues[0].severity == "error"


def test_validate_document_type_error_reports_type_kind():
    data = {"age": "thirty"}
    schema = {
        "type": "object",
        "properties": {
            "age": {"type": "integer"},
        },
        "required": ["age"],
    }

    issues = validate_document(data, schema)
    assert len(issues) == 1
    assert issues[0].kind == "type"
    assert issues[0].instance_path in {("age",), ("properties", "age")}


def test_validate_document_respects_max_issues_limit():
    data = ["a", "b", "c", "d", "e"]
    schema = {
        "type": "array",
        "items": {"type": "integer"},
    }

    issues = validate_document(data, schema, max_issues=3)
    assert len(issues) == 3


def test_is_schema_valid_reports_invalid_schema():
    schema = {
        "type": "object",
        "properties": {
            "value": {"type": "does-not-exist"},
        },
    }

    ok, error = is_schema_valid(schema)
    assert ok is False
    assert isinstance(error, str)
    assert error


def test_jsonschema_dependency_is_available_for_validation_step():
    assert jsonschema is not None
