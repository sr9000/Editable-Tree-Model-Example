"""test_validation_autorescan.py — Integration tests for hot auto-rescan.

Scenarios:
- enable auto_rescan → mutate a value → validationChanged fires and
  the dock's issue count reflects the new state;
- disable auto_rescan → mutate → issue count stays stale until
  Rescan-now is triggered manually.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.validation_dock import ValidationDock
from documents.tab import JsonTab
from tree.types import JsonType
from validation.schema_source import SchemaRef


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _int_schema() -> dict:
    """Schema: root object must have an integer field 'val'."""
    return {
        "type": "object",
        "properties": {"val": {"type": "integer"}},
        "required": ["val"],
    }


def _make_tab(qtbot, data: dict, schema: dict | None = None) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data, show_root=True)
    qtbot.addWidget(tab)
    if schema is not None:
        tab.data_store.validation.set_schema(SchemaRef(path=None, inline=schema, origin="manual"))
    return tab


def _val_value_index(tab: JsonTab):
    """Return the source model QModelIndex for the value cell of key 'val'."""
    # With show_root=True: model.index(0,0) is the root document object.
    doc_idx = tab.data_store.model.index(0, 0)
    # First child of doc is 'val'.
    val_name_idx = tab.data_store.model.index(0, 0, doc_idx)
    return val_name_idx.siblingAtColumn(2)


# ── tests ─────────────────────────────────────────────────────────────────


def test_auto_rescan_on_value_edit_triggers_revalidation(qtbot):
    """auto_rescan=True → edit value → validationChanged fires automatically."""
    _qapp()
    tab = _make_tab(qtbot, {"val": 5}, _int_schema())
    dock = ValidationDock()
    qtbot.addWidget(dock)
    dock.attach_tab(tab)

    assert len(tab.data_store.issue_index) == 0, "should start valid"

    tab.data_store.validation.set_auto_rescan(True)

    # Change the type of 'val' from INTEGER to STRING so the schema rejects it.
    val_name_idx = tab.data_store.model.index(0, 0, tab.data_store.model.index(0, 0))
    type_idx = val_name_idx.siblingAtColumn(1)
    with qtbot.waitSignal(tab.validationChanged, timeout=500):
        tab.push_change_type(type_idx, JsonType.STRING)

    assert len(tab.data_store.issue_index) > 0, "should detect schema violation after auto-rescan"
    assert dock.model.rowCount() > 0, "dock list should reflect new issues"


def test_auto_rescan_off_mutation_does_not_trigger_revalidation(qtbot):
    """auto_rescan=False → mutate → issue count stays stale."""
    _qapp()
    tab = _make_tab(qtbot, {"val": 5}, _int_schema())
    dock = ValidationDock()
    qtbot.addWidget(dock)
    dock.attach_tab(tab)

    assert len(tab.data_store.issue_index) == 0

    tab.data_store.validation.set_auto_rescan(False)

    val_name_idx = tab.data_store.model.index(0, 0, tab.data_store.model.index(0, 0))
    type_idx = val_name_idx.siblingAtColumn(1)
    tab.push_change_type(type_idx, JsonType.STRING)

    # Allow up to 400 ms for any spurious revalidation to fire.
    qtbot.wait(400)

    assert len(tab.data_store.issue_index) == 0, "without auto-rescan, issue count should stay stale"
    assert dock.model.rowCount() == 0, "dock list should stay stale too"


def test_rescan_now_updates_issues_when_auto_rescan_off(qtbot):
    """Rescan-now triggers revalidation even when auto_rescan is off."""
    _qapp()
    tab = _make_tab(qtbot, {"val": 5}, _int_schema())
    dock = ValidationDock()
    qtbot.addWidget(dock)
    dock.attach_tab(tab)

    tab.data_store.validation.set_auto_rescan(False)

    val_name_idx = tab.data_store.model.index(0, 0, tab.data_store.model.index(0, 0))
    type_idx = val_name_idx.siblingAtColumn(1)
    tab.push_change_type(type_idx, JsonType.STRING)

    assert len(tab.data_store.issue_index) == 0, "pre-condition: stale"

    with qtbot.waitSignal(tab.validationChanged, timeout=500):
        tab.data_store.validation.revalidate()

    assert len(tab.data_store.issue_index) > 0
    assert dock.model.rowCount() > 0


def test_auto_rescan_toggle_on_off_cancels_pending_debounce(qtbot):
    """Toggling auto_rescan off while a debounce is pending cancels it."""
    _qapp()
    tab = _make_tab(qtbot, {"val": 5}, _int_schema())
    qtbot.addWidget(tab)

    tab.data_store.validation.set_auto_rescan(True)

    # Arm the debounce by simulating a rowsInserted signal.
    tab.data_store.validation._schedule_debounced_revalidation()
    assert tab.data_store.validation.debounce_timer.isActive(), "timer should be active"

    # Disable auto-rescan — timer must be stopped.
    tab.data_store.validation.set_auto_rescan(False)
    assert not tab.data_store.validation.debounce_timer.isActive(), "timer should be cancelled"


def test_auto_rescan_property_reflects_set(qtbot):
    """auto_rescan property tracks set_auto_rescan() calls."""
    _qapp()
    tab = JsonTab(lambda *_: None, data={}, show_root=True)
    qtbot.addWidget(tab)

    assert tab.data_store.auto_rescan is False
    tab.data_store.validation.set_auto_rescan(True)
    assert tab.data_store.auto_rescan is True
    tab.data_store.validation.set_auto_rescan(False)
    assert tab.data_store.auto_rescan is False
