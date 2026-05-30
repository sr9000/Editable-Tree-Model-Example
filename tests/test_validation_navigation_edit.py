from PySide6.QtWidgets import QApplication

from documents.tab import JsonTab
from validation.schema_source import SchemaRef


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_goto_validation_issue_edit_targets_value_column_for_leaf(qtbot):
    _qapp()
    tab = JsonTab(lambda *_: None, data={"a": {"b": "oops"}}, show_root=True)
    qtbot.addWidget(tab)

    tab.validation.set_schema(
        SchemaRef(
            path=None,
            inline={
                "type": "object",
                "properties": {
                    "a": {
                        "type": "object",
                        "properties": {"b": {"type": "integer"}},
                    }
                },
            },
            origin="manual",
        )
    )
    issue = tab.validation.issue_index.all_issues()[0]

    assert tab.validation.goto_validation_issue(issue, edit=True)

    current = tab.view_controller.proxy_to_source(tab.view.currentIndex())
    assert current.isValid()
    assert tab.view_controller.qualified_name(current.siblingAtColumn(0)).endswith(".a.b")
    assert current.column() == 2


def test_goto_validation_issue_edit_ignores_container_value_cell(qtbot):
    _qapp()
    tab = JsonTab(lambda *_: None, data={"a": {"b": 1}}, show_root=True)
    qtbot.addWidget(tab)

    tab.validation.set_schema(
        SchemaRef(
            path=None,
            inline={
                "type": "object",
                "properties": {
                    "a": {"type": "string"},
                },
            },
            origin="manual",
        )
    )
    issue = tab.validation.issue_index.all_issues()[0]

    assert tab.validation.goto_validation_issue(issue, edit=True)

    current = tab.view_controller.proxy_to_source(tab.view.currentIndex())
    assert current.isValid()
    assert tab.view_controller.qualified_name(current.siblingAtColumn(0)).endswith(".a")
    assert current.column() == 0
