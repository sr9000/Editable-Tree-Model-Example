"""test_validation_yaml_multi.py — YAML multi-document validation.

Verifies:
- ``validate_yaml_documents`` prefixes each issue's instance_path with
  the synthetic ``'[doc N]'`` token.
- Only the failing document emits issues; passing documents do not.
- The prefixed path resolves to the correct row via
  ``instance_path_to_model_path`` — the second top-level row for doc 1.
- ``max_issues`` is respected across documents.
- ``instance_path_to_model_path`` handles the ``'[doc N]'`` token in
  the new json_pointer implementation.
"""

from __future__ import annotations

import pytest

from validation.json_pointer import instance_path_to_model_path
from validation.yaml_validate import validate_yaml_documents

_PERSON_SCHEMA = {
    "type": "object",
    "required": ["name"],
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"},
    },
}

# Three-doc stream: doc 0 and doc 2 are valid; doc 1 violates "name" type.
_DOCS = [
    {"name": "Alice", "age": 30},
    {"name": 42, "age": 25},  # name should be string
    {"name": "Charlie"},
]


# ── prefix semantics ─────────────────────────────────────────────────────


def test_issues_carry_doc_prefix():
    issues = validate_yaml_documents(_DOCS, _PERSON_SCHEMA)
    assert len(issues) >= 1
    for issue in issues:
        assert isinstance(issue.instance_path[0], str)
        assert issue.instance_path[0].startswith("[doc ")


def test_only_failing_doc_emits_issues():
    issues = validate_yaml_documents(_DOCS, _PERSON_SCHEMA)
    # All issues should reference doc 1 (the only failing document)
    for issue in issues:
        assert issue.instance_path[0] == "[doc 1]", (
            f"Expected '[doc 1]', got '{issue.instance_path[0]}' — " f"message: {issue.message}"
        )


def test_passing_docs_produce_no_issues():
    # Single-doc stream with a valid document
    issues = validate_yaml_documents([{"name": "Dana"}], _PERSON_SCHEMA)
    assert issues == []


# ── path resolution ──────────────────────────────────────────────────────


def test_doc_prefixed_path_resolves_to_second_row():
    """issue.instance_path == ('[doc 1]', 'name') → model_path[0] == 1."""
    issues = validate_yaml_documents(_DOCS, _PERSON_SCHEMA)
    assert issues, "Expected at least one issue"

    # Find an issue on doc 1
    doc1_issues = [i for i in issues if i.instance_path[0] == "[doc 1]"]
    assert doc1_issues

    issue = doc1_issues[0]
    model_path = instance_path_to_model_path(_DOCS, issue.instance_path)
    assert model_path is not None, f"Could not resolve path {issue.instance_path!r}"
    # First element must be 1 — the second document (zero-based row 1)
    assert model_path[0] == 1


def test_doc_prefixed_path_for_nested_field():
    """('[doc 2]', 'age') should resolve to row (2, <row-of-age>)."""
    docs = [
        {"name": "Alice", "age": 30},
        {"name": "Bob", "age": 25},
        {"name": "Charlie", "age": "old"},  # age should be integer
    ]
    issues = validate_yaml_documents(docs, _PERSON_SCHEMA)
    doc2_issues = [i for i in issues if i.instance_path[0] == "[doc 2]"]
    assert doc2_issues

    issue = doc2_issues[0]
    model_path = instance_path_to_model_path(docs, issue.instance_path)
    assert model_path is not None
    assert model_path[0] == 2  # third document


# ── max_issues cap ────────────────────────────────────────────────────────


def test_max_issues_respected():
    schema = {"type": "array", "items": {"type": "integer"}}
    docs = [["a", "b", "c"]] * 10  # 3 issues per doc, 10 docs = 30 total
    issues = validate_yaml_documents(docs, schema, max_issues=7)
    assert len(issues) == 7


def test_max_issues_zero_returns_empty():
    issues = validate_yaml_documents(_DOCS, _PERSON_SCHEMA, max_issues=0)
    assert issues == []


# ── instance_path_to_model_path with [doc N] token ───────────────────────


def test_json_pointer_handles_doc_token_at_root_list():
    root = [{"a": 1}, {"a": 2}, {"a": 3}]
    path = instance_path_to_model_path(root, ("[doc 0]",))
    assert path == (0,)


def test_json_pointer_handles_doc_token_multi_level():
    root = [{"items": [10, 20, 30]}, {"items": [40, 50]}]
    path = instance_path_to_model_path(root, ("[doc 1]", "items", 1))
    assert path == (1, 0, 1)  # row 1 in root list → row 0 for "items" key → index 1


def test_json_pointer_plain_int_still_works():
    root = [{"x": 99}, {"x": 88}]
    path = instance_path_to_model_path(root, (0, "x"))
    assert path == (0, 0)


def test_json_pointer_invalid_doc_token_returns_none():
    root = [{"a": 1}]
    # "[doc 99]" is out-of-bounds
    path = instance_path_to_model_path(root, ("[doc 99]", "a"))
    assert path is None
