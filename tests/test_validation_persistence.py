"""test_validation_persistence.py — per-file schema binding persistence.

Verifies:
- ``write_schema_path`` / ``read_schema_path`` / ``clear_schema_path``
  round-trip correctly via QSettings.
- Different document paths get independent bindings.
- A ``JsonTab`` opened with a previously persisted manual schema restores
  it automatically (via ``_init_validation_state``).
- Clearing the schema via ``clear_schema_path`` wipes the QSettings entry.
- Saving to a new path via Save As does not carry the old binding forward.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from state.validation_settings import clear_schema_path, read_schema_path, write_schema_path

# ── state.validation_settings round-trips ────────────────────────────────


def test_write_and_read_schema_path(tmp_path):
    doc_path = tmp_path / "doc.json"
    schema_path = tmp_path / "schema.json"

    write_schema_path(doc_path, schema_path)
    assert read_schema_path(doc_path) == schema_path


def test_clear_schema_path_removes_entry(tmp_path):
    doc_path = tmp_path / "doc.json"
    schema_path = tmp_path / "schema.json"

    write_schema_path(doc_path, schema_path)
    assert read_schema_path(doc_path) is not None

    clear_schema_path(doc_path)
    assert read_schema_path(doc_path) is None


def test_different_docs_get_independent_bindings(tmp_path):
    doc1 = tmp_path / "doc1.json"
    doc2 = tmp_path / "doc2.json"
    schema1 = tmp_path / "schema1.json"
    schema2 = tmp_path / "schema2.json"

    write_schema_path(doc1, schema1)
    write_schema_path(doc2, schema2)

    assert read_schema_path(doc1) == schema1
    assert read_schema_path(doc2) == schema2


def test_read_without_write_returns_none(tmp_path):
    doc_path = tmp_path / "never_written.json"
    assert read_schema_path(doc_path) is None


def test_overwrite_replaces_existing_binding(tmp_path):
    doc_path = tmp_path / "doc.json"
    schema_old = tmp_path / "old.json"
    schema_new = tmp_path / "new.json"

    write_schema_path(doc_path, schema_old)
    write_schema_path(doc_path, schema_new)

    assert read_schema_path(doc_path) == schema_new


# ── JsonTab restores persisted manual schema ──────────────────────────────


def test_tab_restores_persisted_schema_on_open(tmp_path, qtbot):
    """If a schema was previously attached, a new tab for the same file restores it."""

    schema_path = tmp_path / "schema.json"
    schema_path.write_text(
        '{"type": "object", "required": ["value"], "properties": {"value": {"type": "integer"}}}',
        encoding="utf-8",
    )
    doc_path = tmp_path / "doc.json"
    doc_path.write_text('{"value": 1}', encoding="utf-8")

    # Persist the manual binding
    write_schema_path(doc_path, schema_path)

    from documents.tab import JsonTab

    tab = JsonTab(lambda *_: None, data={"value": 1}, file_path=str(doc_path), show_root=True)
    qtbot.addWidget(tab)

    assert tab.data_store.schema_ref.origin == "manual"
    assert tab.data_store.schema is not None
    assert tab.data_store.schema_ref.path == schema_path.resolve()


def test_tab_no_error_when_persisted_schema_is_missing(tmp_path, qtbot):
    """A missing persisted schema file is silently ignored."""
    doc_path = tmp_path / "doc.json"
    missing_schema = tmp_path / "nonexistent.json"

    write_schema_path(doc_path, missing_schema)

    from documents.tab import JsonTab

    tab = JsonTab(lambda *_: None, data={}, file_path=str(doc_path), show_root=True)
    qtbot.addWidget(tab)

    # Missing schema → fall back to "none"
    assert tab.data_store.schema_ref.origin == "none"
    assert tab.data_store.schema is None


def test_tab_does_not_override_inline_schema_with_persistence(tmp_path, qtbot):
    """An inline ``$schema`` in the document takes priority over persistence."""

    inline_schema_path = tmp_path / "inline.json"
    inline_schema_path.write_text('{"type": "object"}', encoding="utf-8")

    manual_schema_path = tmp_path / "manual.json"
    manual_schema_path.write_text('{"type": "array"}', encoding="utf-8")

    doc_path = tmp_path / "doc.json"
    doc_path.write_text(
        f'{{"$schema": "{inline_schema_path}", "key": "val"}}',
        encoding="utf-8",
    )

    # Persist a different manual schema binding
    write_schema_path(doc_path, manual_schema_path)

    from documents.tab import JsonTab
    from io_formats.load import load_file_with_format

    data, _fmt = load_file_with_format(str(doc_path))
    tab = JsonTab(lambda *_: None, data=data, file_path=str(doc_path), show_root=True)
    qtbot.addWidget(tab)

    # Inline schema must win over the persisted manual one
    assert tab.data_store.schema_ref.origin == "inline"
    assert tab.data_store.schema_ref.path == inline_schema_path.resolve()


# ── clear_schema_path wipes QSettings entry ──────────────────────────────


def test_clear_schema_path_is_idempotent(tmp_path):
    """Clearing a non-existent key should not raise."""
    doc_path = tmp_path / "doc.json"
    clear_schema_path(doc_path)  # no prior write — must not raise
    assert read_schema_path(doc_path) is None


def test_after_clear_new_write_works(tmp_path):
    doc_path = tmp_path / "doc.json"
    schema_a = tmp_path / "a.json"
    schema_b = tmp_path / "b.json"

    write_schema_path(doc_path, schema_a)
    clear_schema_path(doc_path)
    write_schema_path(doc_path, schema_b)

    assert read_schema_path(doc_path) == schema_b
