from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from validation.json_pointer import instance_path_to_model_path
from validation.schema_source import SchemaRef


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
    window.validation_dock.issueActivated.emit(issue, False)
    app.processEvents()

    current = tab.view_controller.proxy_to_source(tab.view.currentIndex())
    assert current.isValid()
    assert tab.view_controller.qualified_name(current.siblingAtColumn(0)).endswith(".a.b")
    assert ".a.b" in window.statusBar.currentMessage()


def test_stale_issue_path_is_reported_without_changing_selection(qtbot):
    app = _qapp()
    window = MainWindow(yaml_filename="")
    qtbot.addWidget(window)
    window.show()

    tab = window._add_tab(data={"a": {"b": "oops"}}, file_path=None)
    assert tab is not None

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
    stale_issue = tab.validation.issue_index.all_issues()[0]

    root = tab.model.index(0, 0, QModelIndex())
    a_idx = tab.model.index(0, 0, root)
    b_idx = tab.model.index(0, 0, a_idx)
    assert b_idx.isValid()
    assert tab.editing.commands.push_remove_rows([b_idx])

    sentinel = tab.view_controller.source_to_view(a_idx)
    tab.view.setCurrentIndex(sentinel)
    before = tab.view.currentIndex()

    window.validation_dock.issueActivated.emit(stale_issue, False)
    app.processEvents()

    assert tab.view.currentIndex() == before
    assert window.statusBar.currentMessage() == "Validation issue path no longer exists"

    # Restore tab state so teardown does not see this test-only edit as unsaved work.
    tab.undo_stack.undo()
    app.processEvents()


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
    tab.validation.set_schema(SchemaRef(path=None, inline=schema, origin="manual", url=schema_url))

    issue = tab.validation.issue_index.all_issues()[0]
    assert issue.schema_path == ("properties", "age", "minimum")

    before_count = window.tabWidget.count()
    window._on_go_to_schema_rule_requested(issue)
    app.processEvents()

    first_schema_tab = window._current_tab()
    assert first_schema_tab is not None
    assert first_schema_tab.validation.schema_source is not None
    assert first_schema_tab.validation.schema_source.key == schema_url
    assert first_schema_tab.editability.is_read_only
    assert window.tabWidget.count() == before_count + 1

    window._on_go_to_schema_rule_requested(issue)
    app.processEvents()

    schema_tab = window._current_tab()
    assert schema_tab is first_schema_tab
    assert window.tabWidget.count() == before_count + 1

    current = schema_tab.view_controller.proxy_to_source(schema_tab.view.currentIndex())
    assert current.isValid()
    assert schema_tab.model._index_path(current) == instance_path_to_model_path(schema, issue.schema_path)


def test_go_to_schema_rule_focuses_existing_file_backed_schema_tab(qtbot, tmp_path):
    app = _qapp()
    schema_path = tmp_path / "person.schema.json"
    schema_path.write_text(
        '{"type":"object","properties":{"age":{"type":"integer","minimum":18}}}',
        encoding="utf-8",
    )

    window = MainWindow(yaml_filename="")
    qtbot.addWidget(window)
    window.show()

    tab = window._add_tab(data={"age": 15}, file_path=None)
    assert tab is not None
    tab.validation.set_schema(SchemaRef(path=schema_path, inline=None, origin="manual"))

    issue = tab.validation.issue_index.all_issues()[0]
    assert issue.schema_path == ("properties", "age", "minimum")

    assert window._open_path(str(schema_path))
    app.processEvents()
    existing_schema_tab = window._current_tab()
    assert existing_schema_tab is not None
    assert existing_schema_tab.io.file_path == str(schema_path.resolve())

    window.tabWidget.setCurrentWidget(tab)
    before_count = window.tabWidget.count()

    window._on_go_to_schema_rule_requested(issue)
    app.processEvents()

    assert window.tabWidget.count() == before_count
    assert window._current_tab() is existing_schema_tab
