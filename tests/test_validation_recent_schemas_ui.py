from __future__ import annotations

import importlib

from PySide6.QtCore import QSettings

from app.main_window import MainWindow
from app.validation_dock import ValidationDock
from settings import APPLICATION_ID
from state.recent_schemas import push_recent_schema
from validation.schema_registry import SchemaSource

schema_registry_module = importlib.import_module("validation.schema_registry")


def _settings() -> QSettings:
    return QSettings(APPLICATION_ID, "validation")


def setup_function() -> None:
    _settings().clear()


def teardown_function() -> None:
    _settings().clear()


def test_dock_recent_menu_shows_labels_and_enabled_state(qtbot, tmp_path):
    missing = SchemaSource.for_file(tmp_path / "missing.schema.json")
    url_source = SchemaSource.for_url("https://example.com/person.schema.json")
    push_recent_schema(missing)
    push_recent_schema(url_source)

    dock = ValidationDock()
    qtbot.addWidget(dock)
    dock._rebuild_recent_menu()

    actions = dock._recent_menu.actions()
    texts = [a.text() for a in actions]
    assert texts == [f"🌐 {url_source.display}", f"📂 {missing.display}"]
    assert actions[0].isEnabled()
    assert not actions[1].isEnabled()

    with qtbot.waitSignal(dock.attachRecentSchemaRequested, timeout=1000) as captured:
        actions[0].trigger()
    assert captured.args == [url_source]


def test_clicking_recent_menu_entry_attaches_schema_on_current_tab(qtbot, monkeypatch):
    url_source = SchemaSource.for_url("https://example.com/person.schema.json")
    push_recent_schema(url_source)

    monkeypatch.setattr(schema_registry_module, "load_schema", lambda _ref: {"type": "object"})

    window = MainWindow(yaml_filename="")
    qtbot.addWidget(window)
    window.create_new_file()

    tab = window._current_tab()
    assert tab is not None

    window.validation_dock.attach_tab(tab)
    window.validation_dock._rebuild_recent_menu()

    actions = window.validation_dock._recent_menu.actions()
    assert len(actions) == 1
    actions[0].trigger()

    assert tab.data_store.schema_source == url_source
    assert tab.data_store.schema is not None
