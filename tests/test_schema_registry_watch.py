from __future__ import annotations

import importlib

from documents.tab import JsonTab
from validation.schema_registry import SchemaRegistry, SchemaSource
from validation.schema_source import SchemaRef

schema_registry_module = importlib.import_module("validation.schema_registry")


class _Tab:
    pass


def test_file_change_reloads_in_place_and_revalidates_tab(qtbot, tmp_path, monkeypatch):
    registry = SchemaRegistry()
    monkeypatch.setattr(schema_registry_module, "schema_registry", registry, raising=False)

    schema_path = tmp_path / "live.schema.json"
    schema_path.write_text(
        '{"type":"object","properties":{"v":{"type":"integer"}},"required":["v"]}',
        encoding="utf-8",
    )

    source = SchemaSource.for_file(schema_path)

    tab = JsonTab(lambda *_: None, data={"v": 1}, show_root=True)
    qtbot.addWidget(tab)
    tab.set_schema(SchemaRef(path=schema_path, inline=None, origin="manual"))

    entry = registry.lookup(source)
    assert entry is not None
    assert len(tab.data_store.issue_index.all_issues()) == 0

    seen: list[SchemaSource] = []
    registry.schemaReloaded.connect(lambda reloaded: seen.append(reloaded))

    schema_path.write_text(
        '{"type":"object","properties":{"v":{"type":"string"}},"required":["v"]}',
        encoding="utf-8",
    )

    watcher = registry._watcher
    assert watcher is not None
    assert source.key in watcher.files()

    watcher.fileChanged.emit(source.key)

    assert seen == [source]
    assert entry.inline["properties"]["v"]["type"] == "string"
    assert len(tab.data_store.issue_index.all_issues()) == 1


def test_url_sources_are_not_watched(monkeypatch):
    registry = SchemaRegistry()
    source = SchemaSource.for_url("https://example.com/schema")

    monkeypatch.setattr(schema_registry_module, "load_schema", lambda _ref: {"type": "object"})

    entry = registry.acquire(source, _Tab())

    assert entry is not None
    assert registry._watcher is None
