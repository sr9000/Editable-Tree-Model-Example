"""Tests for VALIDATION_SEVERITY_ROLE on JsonTreeModel."""
import pytest
from PySide6.QtCore import QModelIndex

from tree.model import JsonTreeModel
from tree.model_roles import VALIDATION_SEVERITY_ROLE
from validation.index import IssueIndex

def _build_model(data):
    return JsonTreeModel(data)


def _path_index(model, *rows):
    """Resolve a chain of rows from the model root to a QModelIndex."""
    idx = QModelIndex()
    for row in rows:
        idx = model.index(row, 0, idx)
    return idx


def _issue(instance_path: tuple, severity: str = "error") -> "ValidationIssue":
    from validation.issue import ValidationIssue

    return ValidationIssue(
        severity=severity,  # type: ignore[arg-type]
        message="test",
        instance_path=instance_path,
        schema_path=(),
        kind="test",
    )


# ---------------------------------------------------------------------------
# provider absent → always None
# ---------------------------------------------------------------------------

def test_no_provider_returns_none():
    model = _build_model({"a": 1})
    idx = _path_index(model, 0)
    assert model.data(idx, VALIDATION_SEVERITY_ROLE) is None


# ---------------------------------------------------------------------------
# exact severity
# ---------------------------------------------------------------------------

def test_exact_error():
    data = {"a": {"b": 1}}
    issues = [_issue(("a", "b"), "error")]
    index = IssueIndex(issues, data)

    model = _build_model(data)
    model.set_issue_index_provider(
        lambda path: index.severity_at(path) or index.ancestor_severity(path)
    )

    # /a/b → model path (0, 0) — child 0 of child 0
    idx_ab = _path_index(model, 0, 0)
    assert model.data(idx_ab, VALIDATION_SEVERITY_ROLE) == "error"


def test_exact_warning():
    data = {"x": 42}
    issues = [_issue(("x",), "warning")]
    index = IssueIndex(issues, data)

    model = _build_model(data)
    model.set_issue_index_provider(
        lambda path: index.severity_at(path) or index.ancestor_severity(path)
    )

    idx_x = _path_index(model, 0)
    assert model.data(idx_x, VALIDATION_SEVERITY_ROLE) == "warning"


# ---------------------------------------------------------------------------
# ancestor severity
# ---------------------------------------------------------------------------

def test_ancestor_severity_propagates():
    data = {"a": {"b": {"c": 1}}}
    issues = [_issue(("a", "b", "c"), "error")]
    index = IssueIndex(issues, data)

    model = _build_model(data)
    model.set_issue_index_provider(
        lambda path: index.severity_at(path) or index.ancestor_severity(path)
    )

    # /a → model path (0,) — ancestor of the error
    idx_a = _path_index(model, 0)
    assert model.data(idx_a, VALIDATION_SEVERITY_ROLE) == "error"


# ---------------------------------------------------------------------------
# provider removal → None again
# ---------------------------------------------------------------------------

def test_provider_removal():
    data = {"k": 1}
    issues = [_issue(("k",), "error")]
    index = IssueIndex(issues, data)

    model = _build_model(data)
    model.set_issue_index_provider(
        lambda path: index.severity_at(path) or index.ancestor_severity(path)
    )
    idx = _path_index(model, 0)
    assert model.data(idx, VALIDATION_SEVERITY_ROLE) == "error"

    model.set_issue_index_provider(None)
    assert model.data(idx, VALIDATION_SEVERITY_ROLE) is None


# ---------------------------------------------------------------------------
# no issues → None everywhere
# ---------------------------------------------------------------------------

def test_empty_issue_index():
    data = {"a": 1}
    index = IssueIndex([], data)

    model = _build_model(data)
    model.set_issue_index_provider(
        lambda path: index.severity_at(path) or index.ancestor_severity(path)
    )

    idx = _path_index(model, 0)
    assert model.data(idx, VALIDATION_SEVERITY_ROLE) is None
