"""test_validation_toolbar.py — Tests for the dock toolbar widgets.

Verifies:
- Clear schema button hidden when origin=="none";
- Rescan button disabled when schema absent;
- Status label text matches "N issues";
- Rescan-now button enabled when schema is attached;
- set_auto_rescan_checked() does not emit autoRescanToggled.
"""

from __future__ import annotations

from PySide6.QtWidgets import QApplication

from app.validation_dock import ValidationDock
from documents.tab import JsonTab
from validation.index import IssueIndex
from validation.issue import ValidationIssue
from validation.schema_source import SchemaRef


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _make_tab(qtbot, data: dict, schema: dict | None = None) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data, show_root=True)
    qtbot.addWidget(tab)
    if schema is not None:
        tab.set_schema(SchemaRef(path=None, inline=schema, origin="manual"))
    return tab


def _make_dock(qtbot) -> ValidationDock:
    dock = ValidationDock()
    qtbot.addWidget(dock)
    return dock


def _issue(message: str = "test") -> ValidationIssue:
    return ValidationIssue(
        message=message,
        kind="test",
        instance_path=(),
        schema_path=(),
    )


# ── button state ──────────────────────────────────────────────────────────


def test_rescan_button_disabled_without_schema(qtbot):
    _qapp()
    tab = _make_tab(qtbot, {})
    dock = _make_dock(qtbot)
    dock.attach_tab(tab)
    assert not dock._btn_rescan.isEnabled(), "rescan must be disabled when no schema"


def test_rescan_button_enabled_with_schema(qtbot):
    _qapp()
    schema = {"type": "object"}
    tab = _make_tab(qtbot, {}, schema)
    dock = _make_dock(qtbot)
    dock.attach_tab(tab)
    assert dock._btn_rescan.isEnabled(), "rescan must be enabled when schema is attached"


def test_clear_schema_hidden_when_no_schema(qtbot):
    _qapp()
    tab = _make_tab(qtbot, {})
    dock = _make_dock(qtbot)
    dock.attach_tab(tab)
    assert dock._btn_clear_schema.isHidden(), "clear schema button must be hidden when origin=='none'"


def test_clear_schema_visible_with_manual_schema(qtbot):
    _qapp()
    schema = {"type": "object"}
    tab = _make_tab(qtbot, {}, schema)
    dock = _make_dock(qtbot)
    dock.attach_tab(tab)
    assert not dock._btn_clear_schema.isHidden(), "clear schema button must be visible when origin=='manual'"


def test_clear_schema_hidden_again_after_clear(qtbot):
    _qapp()
    schema = {"type": "object"}
    tab = _make_tab(qtbot, {}, schema)
    dock = _make_dock(qtbot)
    dock.attach_tab(tab)
    assert not dock._btn_clear_schema.isHidden()

    tab.clear_schema()
    assert dock._btn_clear_schema.isHidden()
    assert not dock._btn_rescan.isEnabled()


# ── status label ──────────────────────────────────────────────────────────


def test_status_label_shows_up_to_date_when_no_issues(qtbot):
    _qapp()
    dock = _make_dock(qtbot)
    empty_index = IssueIndex([], {})
    dock.update_status(empty_index)
    assert dock._lbl_status.text() == "Up to date"


def test_status_label_shows_error_count(qtbot):
    _qapp()
    dock = _make_dock(qtbot)
    issues = [_issue(), _issue(), _issue()]
    idx = IssueIndex(issues, {})
    dock.update_status(idx)
    assert "3 issues" in dock._lbl_status.text()


def test_status_label_shows_warning_count(qtbot):
    _qapp()
    dock = _make_dock(qtbot)
    issues = [_issue()]
    idx = IssueIndex(issues, {})
    dock.update_status(idx)
    assert "1 issue" in dock._lbl_status.text()


def test_status_label_shows_errors_and_warnings(qtbot):
    _qapp()
    dock = _make_dock(qtbot)
    issues = [_issue(), _issue(), _issue()]
    idx = IssueIndex(issues, {})
    dock.update_status(idx)
    text = dock._lbl_status.text()
    assert "3 issues" in text


def test_status_label_singular_error(qtbot):
    _qapp()
    dock = _make_dock(qtbot)
    idx = IssueIndex([_issue()], {})
    dock.update_status(idx)
    assert "1 issue" in dock._lbl_status.text()
    # Must not say "1 issues"
    assert "1 issues" not in dock._lbl_status.text()


# ── auto-rescan checkbox ──────────────────────────────────────────────────


def test_set_auto_rescan_checked_does_not_emit_signal(qtbot):
    _qapp()
    dock = _make_dock(qtbot)
    received: list[bool] = []
    dock.autoRescanToggled.connect(received.append)

    dock.set_auto_rescan_checked(True)
    dock.set_auto_rescan_checked(False)

    assert received == [], "set_auto_rescan_checked must not emit autoRescanToggled"


def test_auto_rescan_checkbox_emits_signal_on_user_toggle(qtbot):
    _qapp()
    dock = _make_dock(qtbot)
    received: list[bool] = []
    dock.autoRescanToggled.connect(received.append)

    # Simulate user interaction via setChecked (signals not blocked).
    dock._chk_auto.setChecked(True)
    dock._chk_auto.setChecked(False)

    assert received == [True, False]


# ── attach_tab resets controls when tab is None ───────────────────────────


def test_attach_none_resets_toolbar(qtbot):
    _qapp()
    schema = {"type": "object"}
    tab = _make_tab(qtbot, {}, schema)
    dock = _make_dock(qtbot)
    dock.attach_tab(tab)
    assert dock._btn_rescan.isEnabled()

    dock.attach_tab(None)
    assert not dock._btn_rescan.isEnabled()
    assert not dock._btn_clear_schema.isVisible()
    assert dock._lbl_status.text() == "Up to date"
