"""Integration tests for in-tree severity badge painting via JsonTab."""

from PySide6.QtCore import QModelIndex
from pytestqt.qtbot import QtBot

from documents.tab import JsonTab
from tree.model_roles import VALIDATION_SEVERITY_ROLE
from validation.schema_source import SchemaRef


def _make_tab(qtbot: QtBot, data: dict, *, show_root: bool = False) -> JsonTab:
    tab = JsonTab(lambda: None, data=data, show_root=show_root)
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
    tab.validation.set_schema(SchemaRef(path=None, inline=schema, origin="inline"))

    # The issue index should now contain at least one error for /name
    assert len(tab.validation.issue_index) > 0

    # Resolve "name" → model path (0,) because it's the first (and only) key
    idx = tab.model.index(0, 0, QModelIndex())
    assert idx.isValid()

    severity = tab.model.data(idx, VALIDATION_SEVERITY_ROLE)
    assert severity == "error"


def test_no_issues_role_returns_none(qtbot):
    """When no schema is set the role always returns None."""
    data = {"a": 1}
    tab = _make_tab(qtbot, data)
    tab.validation.clear_schema()

    idx = tab.model.index(0, 0, QModelIndex())
    assert tab.model.data(idx, VALIDATION_SEVERITY_ROLE) is None


def test_clear_schema_removes_badges(qtbot):
    """Clearing the schema zeroes the issue index → role returns None."""
    schema = {"type": "object", "properties": {"x": {"type": "integer"}}}
    data = {"x": "bad"}

    tab = _make_tab(qtbot, data)
    tab.validation.set_schema(SchemaRef(path=None, inline=schema, origin="inline"))
    assert len(tab.validation.issue_index) > 0  # has errors

    tab.validation.clear_schema()
    assert len(tab.validation.issue_index) == 0

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
    tab.validation.set_schema(SchemaRef(path=None, inline=schema, origin="inline"))

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
    tab.validation.set_schema(SchemaRef(path=None, inline=schema, origin="inline"))

    # "parent" is at model path (0,)
    parent_idx = tab.model.index(0, 0, QModelIndex())
    assert parent_idx.isValid()

    severity = tab.model.data(parent_idx, VALIDATION_SEVERITY_ROLE)
    assert severity == "error"


# ---------------------------------------------------------------------------
# Regression: show_root=True must not offset model paths (real-app default)
# ---------------------------------------------------------------------------


def test_severity_with_show_root(qtbot):
    """With show_root=True the virtual root row must not shift model paths.

    Before the fix, _index_path included the root item's own row (0), so
    every data path was off by one level and severity was never returned.
    """
    schema = {
        "type": "object",
        "properties": {"age": {"type": "integer", "minimum": 18}},
    }
    data = {"firstName": "Indra", "lastName": "Sen", "age": 17}

    tab = _make_tab(qtbot, data, show_root=True)
    tab.validation.set_schema(SchemaRef(path=None, inline=schema, origin="inline"))

    assert len(tab.validation.issue_index) == 1, "expected one minimum-violation issue"

    # With show_root=True the visible tree is: root(0) → firstName(0), lastName(1), age(2)
    root_idx = tab.model.index(0, 0, QModelIndex())
    age_idx = tab.model.index(2, 0, root_idx)
    assert age_idx.isValid()

    # _index_path must return (2,) — the data-relative path — not (0, 2)
    assert tab.model._index_path(age_idx) == (2,)

    # Both the exact row and its ancestor (the root) must carry severity
    assert tab.model.data(age_idx, VALIDATION_SEVERITY_ROLE) == "error"
    assert tab.model.data(root_idx, VALIDATION_SEVERITY_ROLE) == "error"
