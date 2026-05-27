from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from app.validation_dock import ValidationDock
from documents.tab import JsonTab
from validation.schema_source import SchemaRef


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def _failing_schema() -> dict:
    return {
        "type": "object",
        "properties": {
            "value": {"type": "integer"},
        },
        "required": ["value"],
    }


def _make_tab(qtbot, data: dict, schema: dict | None = None) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data, show_root=True)
    qtbot.addWidget(tab)
    if schema is not None:
        tab.set_schema(SchemaRef(path=None, inline=schema, origin="manual"))
    return tab


def test_validation_dock_attach_tab_updates_list_rows(qtbot):
    _qapp()
    dock = ValidationDock()
    qtbot.addWidget(dock)

    bad_tab = _make_tab(qtbot, {"value": "oops"}, _failing_schema())
    assert len(bad_tab.data_store.issue_index) == 1

    dock.attach_tab(bad_tab)
    assert dock.model.rowCount() == 1

    clean_tab = _make_tab(qtbot, {"value": 5}, _failing_schema())
    assert len(clean_tab.data_store.issue_index) == 0

    dock.attach_tab(clean_tab)
    assert dock.model.rowCount() == 0


def test_view_validation_panel_action_toggles_dock_visibility(qtbot):
    _qapp()
    window = MainWindow(yaml_filename="")
    qtbot.addWidget(window)
    window.show()

    window.validation_dock.setVisible(True)
    window.viewValidationPanelAction.setChecked(True)

    window.viewValidationPanelAction.trigger()
    assert not window.validation_dock.isVisible()
    assert not window.viewValidationPanelAction.isChecked()

    window.viewValidationPanelAction.trigger()
    assert window.validation_dock.isVisible()
    assert window.viewValidationPanelAction.isChecked()
