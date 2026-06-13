from __future__ import annotations

import json
import time
from pathlib import Path

import pytest

from app.loading.coordinator import LoadCoordinator
from app.main_window import MainWindow
from app.tab_lifecycle import TabLifecyclePresenter
from documents.controllers.validation import TabValidationController
from documents.controllers.view import ViewController
from documents.tab import JsonTab


def _write_json(path: Path, payload) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _cleanup(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        maybe_tab = win.tabWidget.widget(i)
        if isinstance(maybe_tab, JsonTab):
            maybe_tab.undo_stack.setClean()
    win.close()
    win.deleteLater()


def _time_method(monkeypatch, cls, method_name: str, timings: dict[str, float]) -> None:
    original = getattr(cls, method_name)  # allow: perf test wraps known methods by name

    def _wrapped(self, *args, **kwargs):
        started = time.perf_counter()
        try:
            return original(self, *args, **kwargs)
        finally:
            timings[method_name] = timings.get(method_name, 0.0) + (time.perf_counter() - started)

    monkeypatch.setattr(cls, method_name, _wrapped)


@pytest.mark.perf
def test_post_build_phase_timing_smoke(qtbot, tmp_path, monkeypatch):
    timings: dict[str, float] = {}
    _time_method(monkeypatch, LoadCoordinator, "_bind_open", timings)
    _time_method(monkeypatch, TabLifecyclePresenter, "add_tab", timings)
    _time_method(monkeypatch, TabLifecyclePresenter, "_run_initial_presentation", timings)
    _time_method(monkeypatch, TabValidationController, "revalidate", timings)
    _time_method(monkeypatch, TabValidationController, "revalidate_loading_data", timings)
    _time_method(monkeypatch, ViewController, "_apply_select", timings)

    doc = tmp_path / "data.json"
    schema = tmp_path / "data.schema.json"
    schema.write_text('{"type":"object","additionalProperties":{"type":"integer"}}', encoding="utf-8")
    payload = {f"k{i}": "bad" for i in range(250)}
    _write_json(doc, payload)

    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        assert win._open_path(str(doc))
    finally:
        _cleanup(win)

    assert "_bind_open" in timings
    assert "add_tab" in timings
    assert "_run_initial_presentation" in timings
    assert "revalidate_loading_data" in timings or "revalidate" in timings
