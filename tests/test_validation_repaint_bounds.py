from __future__ import annotations

from PySide6.QtCore import QModelIndex, QTimer

from documents.tab import JsonTab
from tree.model_roles import VALIDATION_SEVERITY_ROLE
from validation.schema_source import SchemaRef


def _make_tab(qtbot, data: dict, *, show_root: bool = True) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data, show_root=show_root)
    qtbot.addWidget(tab)
    return tab


def test_empty_validation_emits_no_data_changed(qtbot):
    tab = _make_tab(qtbot, {"a": 1})
    calls = {"count": 0}

    def _on_changed(_top, _bottom, roles):
        if VALIDATION_SEVERITY_ROLE in roles:
            calls["count"] += 1

    tab.model.dataChanged.connect(_on_changed)
    tab.validation.clear_schema()
    assert calls["count"] == 0


def test_single_issue_repaints_exact_path_and_ancestors(qtbot):
    tab = _make_tab(qtbot, {"parent": {"leaf": "bad"}}, show_root=True)
    repainted_paths: set[tuple[int, ...]] = set()

    def _on_changed(top, _bottom, roles):
        if VALIDATION_SEVERITY_ROLE not in roles:
            return
        source = top.siblingAtColumn(0)
        repainted_paths.add(tab.model._index_path(source))

    tab.model.dataChanged.connect(_on_changed)

    schema = {
        "type": "object",
        "properties": {
            "parent": {
                "type": "object",
                "properties": {"leaf": {"type": "integer"}},
            }
        },
    }
    tab.validation.set_schema(SchemaRef(path=None, inline=schema, origin="manual"))

    assert (0, 0) in repainted_paths
    assert (0,) in repainted_paths


def test_large_issue_sets_emit_repaints_in_batches_with_event_turn(qtbot, monkeypatch):
    data = {f"k{i}": "x" for i in range(80)}
    tab = _make_tab(qtbot, data)
    monkeypatch.setattr(tab.validation, "_REPAINT_BATCH_SIZE", 5)

    timer_turn = {"fired": False}
    emissions = {"count": 0}

    def _on_changed(_top, _bottom, roles):
        if VALIDATION_SEVERITY_ROLE in roles:
            emissions["count"] += 1

    tab.model.dataChanged.connect(_on_changed)
    QTimer.singleShot(0, lambda: timer_turn.__setitem__("fired", True))

    schema = {
        "type": "object",
        "additionalProperties": {"type": "integer"},
    }
    tab.validation.set_schema(SchemaRef(path=None, inline=schema, origin="manual"))

    qtbot.waitUntil(lambda: emissions["count"] >= 10, timeout=1500)
    assert timer_turn["fired"]
