from __future__ import annotations

from PySide6.QtCore import QSettings
from PySide6.QtWidgets import QApplication

from app.main_window import MainWindow
from settings import APPLICATION_ID
from state.recent_schemas import push_recent_schema
from validation.schema_registry import SchemaSource


def _settings() -> QSettings:
    return QSettings(APPLICATION_ID, "validation")


def setup_function() -> None:
    _settings().clear()


def teardown_function() -> None:
    _settings().clear()


def test_schemas_menu_recent_entries_show_local_and_url_labels(qtbot, tmp_path):
    local_path = tmp_path / "local.schema.json"
    local_path.write_text('{"type":"object"}', encoding="utf-8")

    local_source = SchemaSource.for_file(local_path)
    url_source = SchemaSource.for_url("https://example.com/person.schema.json")
    push_recent_schema(local_source)
    push_recent_schema(url_source)

    window = MainWindow(yaml_filename="")
    qtbot.addWidget(window)
    window._rebuild_schemas_menu()

    labels = [action.text() for action in window._schemas_recent_menu.actions()]
    assert labels == [f"URL — {url_source.display}", f"Local — {local_source.display}"]


def test_schemas_menu_recent_url_opens_read_only_tab_and_disables_edit_actions(qtbot, monkeypatch):
    app = QApplication.instance() or QApplication([])
    url_source = SchemaSource.for_url("https://example.com/person.schema.json")
    push_recent_schema(url_source)

    monkeypatch.setattr(
        "validation.schema_source.load_schema_from_url",
        lambda _url: {"type": "object", "properties": {"age": {"type": "integer"}}},
    )

    window = MainWindow(yaml_filename="")
    qtbot.addWidget(window)
    window.create_new_file()

    window._rebuild_schemas_menu()
    actions = window._schemas_recent_menu.actions()
    assert len(actions) == 1

    before_count = window.tabWidget.count()
    actions[0].trigger()
    app.processEvents()

    tab = window._current_tab()
    assert tab is not None
    assert tab.schema_source == url_source
    assert tab.is_read_only
    assert window.tabWidget.count() == before_count + 1

    window.update_actions()
    assert not window.fileSaveAction.isEnabled()
    assert not window.fileSaveAsAction.isEnabled()
    assert not window.rowInsertAction.isEnabled()
    assert not window.rowInsertAfterAction.isEnabled()
    assert not window.rowRemoveAction.isEnabled()

    window._rebuild_schemas_menu()
    window._schemas_copy_path_action.trigger()
    assert QApplication.clipboard().text() == url_source.key

    # Re-triggering the same source must focus/reuse the existing viewer tab.
    window._schemas_recent_menu.actions()[0].trigger()
    app.processEvents()
    assert window.tabWidget.count() == before_count + 1
