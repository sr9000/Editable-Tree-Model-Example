from __future__ import annotations

import importlib
from pathlib import Path

from validation.schema_registry import SchemaRegistry
from validation.schema_types import SchemaSource

schema_registry_module = importlib.import_module("validation.schema_registry")


class _Tab:
    pass


def test_acquire_deduplicates_loads_and_tracks_ref_count(monkeypatch):
    registry = SchemaRegistry()
    source = SchemaSource.for_url("https://example.com/schema")

    calls = {"count": 0}

    def fake_load_schema(_ref):
        calls["count"] += 1
        return {"type": "object", "title": "once"}

    monkeypatch.setattr(schema_registry_module, "load_schema", fake_load_schema)

    tab_a = _Tab()
    tab_b = _Tab()

    entry_a = registry.acquire(source, tab_a)
    entry_b = registry.acquire(source, tab_b)

    assert entry_a is entry_b
    assert entry_a is not None
    assert entry_a.ref_count == 2
    assert calls["count"] == 1


def test_acquire_is_idempotent_for_same_source_tab_pair(monkeypatch):
    registry = SchemaRegistry()
    source = SchemaSource.for_url("https://example.com/schema")

    monkeypatch.setattr(schema_registry_module, "load_schema", lambda _ref: {"type": "object"})

    tab = _Tab()
    entry_first = registry.acquire(source, tab)
    entry_second = registry.acquire(source, tab)

    assert entry_first is entry_second
    assert entry_first is not None
    assert entry_first.ref_count == 1


def test_release_decrements_and_drops_entry(monkeypatch):
    registry = SchemaRegistry()
    source = SchemaSource.for_url("https://example.com/schema")

    monkeypatch.setattr(schema_registry_module, "load_schema", lambda _ref: {"type": "object"})

    tab_a = _Tab()
    tab_b = _Tab()

    registry.acquire(source, tab_a)
    registry.acquire(source, tab_b)

    registry.release(source, tab_a)
    entry = registry.lookup(source)
    assert entry is not None
    assert entry.ref_count == 1

    registry.release(source, tab_b)
    assert registry.lookup(source) is None
    assert registry.all_entries() == []


def test_reload_replaces_inline_and_emits_signal(monkeypatch):
    registry = SchemaRegistry()
    source = SchemaSource.for_url("HTTPS://example.com/schema/")

    payloads = [{"v": 1}, {"v": 2}]

    def fake_load_schema(_ref):
        return payloads.pop(0)

    monkeypatch.setattr(schema_registry_module, "load_schema", fake_load_schema)

    tab = _Tab()
    entry = registry.acquire(source, tab)
    assert entry is not None
    assert entry.inline == {"v": 1}

    seen = []
    registry.schemaReloaded.connect(lambda s: seen.append(s))

    reloaded = registry.reload(source)
    assert reloaded is entry
    assert reloaded is not None
    assert reloaded.inline == {"v": 2}
    assert seen == [source]


def test_schema_source_for_file_resolves_user_home():
    source = SchemaSource.for_file(Path("~/x.json"))
    expected = Path("~/x.json").expanduser().resolve()

    assert source.kind == "file"
    assert source.key == str(expected)
    assert source.display == "x.json"


def test_schema_source_for_url_normalizes_scheme_and_trailing_slash():
    source = SchemaSource.for_url(" HTTPS://Example.com/path/to/schema/ ")

    assert source.kind == "url"
    assert source.key == "https://Example.com/path/to/schema"
    assert source.display == "example.com/schema"


def test_acquire_pushes_recent_schema_only_on_success(monkeypatch):
    registry = SchemaRegistry()
    source = SchemaSource.for_url("https://example.com/schema")

    pushed: list[SchemaSource] = []
    monkeypatch.setattr(schema_registry_module, "push_recent_schema", lambda s: pushed.append(s))

    monkeypatch.setattr(schema_registry_module, "load_schema", lambda _ref: None)
    assert registry.acquire(source, _Tab()) is None
    assert pushed == []

    monkeypatch.setattr(schema_registry_module, "load_schema", lambda _ref: {"type": "object"})
    assert registry.acquire(source, _Tab()) is not None
    assert pushed == [source]


def test_reload_pushes_recent_schema_on_success(monkeypatch):
    registry = SchemaRegistry()
    source = SchemaSource.for_url("https://example.com/schema")

    payloads = [{"v": 1}, {"v": 2}]
    monkeypatch.setattr(schema_registry_module, "load_schema", lambda _ref: payloads.pop(0))

    pushed: list[SchemaSource] = []
    monkeypatch.setattr(schema_registry_module, "push_recent_schema", lambda s: pushed.append(s))

    assert registry.acquire(source, _Tab()) is not None
    assert pushed == [source]

    assert registry.reload(source) is not None
    assert pushed == [source, source]
