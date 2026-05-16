"""Integration tests for in-tree severity badge painting via JsonTab."""

from PySide6.QtCore import QModelIndex
from pytestqt.qtbot import QtBot

from documents.tab import JsonTab
from tree.model_roles import VALIDATION_SEVERITY_ROLE
from validation.schema_source import SchemaRef


def _make_tab(qtbot: QtBot, data: dict) -> JsonTab:
    tab = JsonTab(lambda: None, data=data)
    qtbot.addWidget(tab)
    return tab


# ---------------------------------------------------------------------------
# Provider is wired — role returns severity from the issue index
# ---------------------------------------------------------------------------


def test_validation_role_after_revalidate(qtbot):
    """After revalidate() the model returns the correct severity via the role."""
    schema = {
        "type": "object",
        "properties": {"name": {"type": "integer"}},
        "required": ["name"],
    }
    data = {"name": "not-an-integer"}

    tab = _make_tab(qtbot, data)
    tab.set_schema(SchemaRef(path=None, inline=schema, origin="inline"))

    # The issue index should now contain at least one error for /name
    assert len(tab.issue_index) > 0

    # Resolve "name" → model path (0,) because it's the first (and only) key
    idx = tab.model.index(0, 0, QModelIndex())
    assert idx.isValid()

    severity = tab.model.data(idx, VALIDATION_SEVERITY_ROLE)
    assert severity == "error"


def test_no_issues_role_returns_none(qtbot):
    """When no schema is set the role always returns None."""
    data = {"a": 1}
    tab = _make_tab(qtbot, data)
    tab.clear_schema()

    idx = tab.model.index(0, 0, QModelIndex())
    assert tab.model.data(idx, VALIDATION_SEVERITY_ROLE) is None


def test_clear_schema_removes_badges(qtbot):
    """Clearing the schema zeroes the issue index → role returns None."""
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
    data = {"x": "bad"}

    tab = _make_tab(qtbot, data)
    tab.set_schema(SchemaRef(path=None, inline=schema, origin="inline"))
    assert len(tab.issue_index) > 0  # has errors

    tab.clear_schema()
    assert len(tab.issue_index) == 0

    idx = tab.model.index(0, 0, QModelIndex())
    assert tab.model.data(idx, VALIDATION_SEVERITY_ROLE) is None


# ---------------------------------------------------------------------------
# dataChanged is emitted for VALIDATION_SEVERITY_ROLE on revalidate
# ---------------------------------------------------------------------------


def test_validation_changed_emits_data_changed(qtbot):
    """_on_validation_changed must emit model.dataChanged with VALIDATION_SEVERITY_ROLE."""
    data = {"a": 1}
    tab = _make_tab(qtbot, data)

    emitted_roles: list[list[int]] = []

    def _on_changed(top, bottom, roles):
        emitted_roles.append(list(roles))

    tab.model.dataChanged.connect(_on_changed)

    schema = {"type": "object", "properties": {"a": {"type": "string"}}}
    tab.set_schema(SchemaRef(path=None, inline=schema, origin="inline"))

    # At least one dataChanged emission should include VALIDATION_SEVERITY_ROLE
    assert any(VALIDATION_SEVERITY_ROLE in roles for roles in emitted_roles)


# ---------------------------------------------------------------------------
# Ancestor rows also receive a severity
# ---------------------------------------------------------------------------


def test_ancestor_gets_severity(qtbot):
    """A parent row whose child has an error should also show 'error'."""
    schema = {
        "type": "object",
        "properties": {
            "parent": {
                "type": "object",
                "properties": {"child": {"type": "integer"}},
            }
        },
    }
    data = {"parent": {"child": "bad"}}

    tab = _make_tab(qtbot, data)
    tab.set_schema(SchemaRef(path=None, inline=schema, origin="inline"))

    # "parent" is at model path (0,)
    parent_idx = tab.model.index(0, 0, QModelIndex())
    assert parent_idx.isValid()

    severity = tab.model.data(parent_idx, VALIDATION_SEVERITY_ROLE)
    assert severity == "error"
