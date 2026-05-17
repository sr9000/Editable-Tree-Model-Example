import jsonschema

from validation.json_pointer import instance_path_to_model_path
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


# ── best_match / oneOf / anyOf unwrapping ─────────────────────────────────


def test_oneof_error_is_unwrapped_to_concrete_cause():
    """A oneOf schema violation should surface the most relevant leaf error,
    not the generic "is not valid under any of the given schemas" message."""
    schema = {
        "oneOf": [
            {"type": "object", "required": ["name"], "properties": {"name": {"type": "string"}}},
            {"type": "object", "required": ["id"], "properties": {"id": {"type": "integer"}}},
        ]
    }
    # name is present but has the wrong type — the first branch is the best match
    data = {"name": 42}

    issues = validate_document(data, schema)

    assert issues, "Expected at least one issue for invalid oneOf data"
    # None of the reported issues should be the opaque oneOf wrapper
    for issue in issues:
        assert issue.kind != "oneOf", f"Got a raw 'oneOf' wrapper error instead of a concrete cause: {issue.message!r}"


def test_anyof_error_is_unwrapped_to_concrete_cause():
    """An anyOf schema violation should surface the most relevant leaf error."""
    schema = {
        "anyOf": [
            {"type": "string", "minLength": 3},
            {"type": "integer", "minimum": 0},
        ]
    }
    data = "ab"  # string but too short; not an integer either

    issues = validate_document(data, schema)

    assert issues, "Expected at least one issue"
    for issue in issues:
        assert issue.kind != "anyOf", f"Got a raw 'anyOf' wrapper error instead of a concrete cause: {issue.message!r}"


def test_nested_oneof_unwraps_to_leaf():
    """Nested oneOf/anyOf should be unwrapped all the way to a leaf error."""
    schema = {
        "oneOf": [
            {
                "type": "object",
                "properties": {
                    "value": {
                        "oneOf": [
                            {"type": "integer", "minimum": 10},
                            {"type": "string", "minLength": 5},
                        ]
                    }
                },
                "required": ["value"],
            }
        ]
    }
    data = {"value": 3}  # integer but below minimum

    issues = validate_document(data, schema)

    assert issues
    for issue in issues:
        assert issue.kind not in (
            "oneOf",
            "anyOf",
        ), f"Wrapper error leaked through: kind={issue.kind!r}, message={issue.message!r}"


def test_valid_oneof_produces_no_issues():
    schema = {
        "oneOf": [
            {"type": "string"},
            {"type": "integer"},
        ]
    }
    assert validate_document("hello", schema) == []
    assert validate_document(7, schema) == []


def test_schema_path_resolves_local_ref_to_physical_definition():
    schema = {
        "type": "object",
        "properties": {
            "person": {"$ref": "#/definitions/person"},
        },
        "definitions": {
            "person": {
                "type": "object",
                "properties": {
                    "age": {"type": "integer", "minimum": 18},
                },
            }
        },
    }

    issues = validate_document({"person": {"age": 15}}, schema)

    assert len(issues) == 1
    assert issues[0].instance_path == ("person", "age")
    assert issues[0].schema_path == ("definitions", "person", "properties", "age", "minimum")
    assert instance_path_to_model_path(schema, issues[0].schema_path) is not None


def test_schema_path_resolves_nested_ref_inside_oneof_context():
    schema = {
        "type": "object",
        "properties": {
            "groups": {
                "type": "array",
                "items": {"$ref": "#/definitions/permission"},
            },
        },
        "definitions": {
            "permission": {
                "oneOf": [
                    {"type": "string", "enum": ["read", "edit"]},
                    {
                        "type": "object",
                        "required": ["type"],
                        "additionalProperties": False,
                        "properties": {
                            "type": {"const": "edit"},
                            "allowedPaths": {
                                "type": "array",
                                "items": {"type": "string", "format": "regex"},
                            },
                        },
                    },
                ]
            }
        },
    }

    issues = validate_document({"groups": [{"type": "edit", "allowedPaths": ["[bad"]}]}, schema)

    assert len(issues) == 1
    assert issues[0].instance_path == ("groups", 0, "allowedPaths", 0)
    assert issues[0].kind == "format"
    assert issues[0].schema_path == (
        "definitions",
        "permission",
        "oneOf",
        1,
        "properties",
        "allowedPaths",
        "items",
        "format",
    )
    assert instance_path_to_model_path(schema, issues[0].schema_path) is not None
