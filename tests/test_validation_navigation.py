from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from validation.schema_source import SchemaRef
from validation.json_pointer import instance_path_to_model_path


def _qapp() -> QApplication:
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app


def test_issue_activation_selects_and_centers_offending_row(qtbot):
    app = _qapp()
    window = MainWindow(yaml_filename="")
    qtbot.addWidget(window)
    window.show()

    tab = window._add_tab(data={"a": {"b": "oops"}}, file_path=None)
    assert tab is not None

    tab.set_schema(
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

    issue = tab.issue_index.all_issues()[0]
    window.validation_dock.issueActivated.emit(issue, False)
    app.processEvents()

    current = tab._proxy_to_source(tab.view.currentIndex())
    assert current.isValid()
    assert tab._qualified_name(current.siblingAtColumn(0)).endswith(".a.b")
    assert ".a.b" in window.statusBar.currentMessage()


def test_stale_issue_path_is_reported_without_changing_selection(qtbot):
    app = _qapp()
    window = MainWindow(yaml_filename="")
    qtbot.addWidget(window)
    window.show()

    tab = window._add_tab(data={"a": {"b": "oops"}}, file_path=None)
    assert tab is not None

    tab.set_schema(
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
    stale_issue = tab.issue_index.all_issues()[0]

    root = tab.model.index(0, 0, QModelIndex())
    a_idx = tab.model.index(0, 0, root)
    b_idx = tab.model.index(0, 0, a_idx)
    assert b_idx.isValid()
    assert tab.push_remove_rows([b_idx])

    sentinel = tab._source_to_view(a_idx)
    tab.view.setCurrentIndex(sentinel)
    before = tab.view.currentIndex()

    window.validation_dock.issueActivated.emit(stale_issue, False)
    app.processEvents()

    assert tab.view.currentIndex() == before
    assert window.statusBar.currentMessage() == "Validation issue path no longer exists"


def test_go_to_schema_rule_works_for_url_backed_in_memory_schema(qtbot, monkeypatch):
    app = _qapp()
    window = MainWindow(yaml_filename="")
    qtbot.addWidget(window)
    window.show()

    schema_url = "https://example.com/person.schema.json"
    schema = {
        "$id": schema_url,
        "$schema": "https://json-schema.org/draft-07/schema",
        "type": "object",
        "properties": {
            "age": {
                "type": "integer",
                "minimum": 18,
            },
        },
    }

    def fail_if_refetched(url):
        raise AssertionError(f"URL schema should be reused from memory, not refetched: {url}")

    monkeypatch.setattr("validation.schema_source.load_schema_from_url", fail_if_refetched)

    tab = window._add_tab(data={"age": 15}, file_path=None)
    assert tab is not None
    tab.set_schema(SchemaRef(path=None, inline=schema, origin="manual", url=schema_url))

    issue = tab.issue_index.all_issues()[0]
    assert issue.schema_path == ("properties", "age", "minimum")

    window._on_go_to_schema_rule_requested(issue)
    app.processEvents()

    schema_tab = window._current_tab()
    assert schema_tab is not None
    assert schema_tab.schema_source is not None
    assert schema_tab.schema_source.key == schema_url

    current = schema_tab._proxy_to_source(schema_tab.view.currentIndex())
    assert current.isValid()
    assert schema_tab.model._index_path(current) == instance_path_to_model_path(schema, issue.schema_path)
