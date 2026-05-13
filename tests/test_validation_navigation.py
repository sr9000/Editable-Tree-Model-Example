from PySide6.QtCore import QModelIndex
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
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
