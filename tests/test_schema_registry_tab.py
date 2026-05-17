from __future__ import annotations

import importlib

from documents.tab import JsonTab
from validation.schema_registry import SchemaSource, schema_registry
from validation.schema_source import SchemaRef

schema_registry_module = importlib.import_module("validation.schema_registry")


def test_tabs_share_single_registry_entry_and_release_on_close(qtbot, tmp_path, monkeypatch):
    schema_path = tmp_path / "shared.schema.json"
    schema_path.write_text('{"type":"object"}', encoding="utf-8")

    calls = {"count": 0}

    def fake_load_schema(_ref):
        calls["count"] += 1
        return {"type": "object", "title": "shared"}

    monkeypatch.setattr(schema_registry_module, "load_schema", fake_load_schema)

    ref = SchemaRef(path=schema_path, inline=None, origin="manual")

    tab_a = JsonTab(lambda *_: None, data={"value": 1}, show_root=True)
    tab_b = JsonTab(lambda *_: None, data={"value": 2}, show_root=True)
    qtbot.addWidget(tab_a)
    qtbot.addWidget(tab_b)

    tab_a.set_schema(ref)
    tab_b.set_schema(ref)

    source = SchemaSource.for_file(schema_path)
    entry = schema_registry.lookup(source)
    assert entry is not None
    assert tab_a.schema is tab_b.schema
    assert tab_a.schema is entry.inline
    assert entry.ref_count == 2
    assert calls["count"] == 1

    tab_a.close()
    qtbot.wait(0)

    entry_after_first_close = schema_registry.lookup(source)
    assert entry_after_first_close is not None
    assert entry_after_first_close.ref_count == 1

    tab_b.close()
    qtbot.wait(0)

    assert schema_registry.lookup(source) is None
