from __future__ import annotations

import time
from datetime import date
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent
from PySide6.QtWidgets import QApplication

import app.tab_lifecycle as tab_lifecycle_module
from app.main_window import MainWindow
from documents.tab import JsonTab


def _cleanup(win: MainWindow) -> None:
    for i in range(win.tabWidget.count()):
        maybe_tab = win.tabWidget.widget(i)
        if isinstance(maybe_tab, JsonTab):
            maybe_tab.undo_stack.setClean()
    win.close()
    win.deleteLater()
    QApplication.processEvents()


def _format_close_phase_report(
    rows: list[tuple[str, float]], dominant: str, path_choice: str, report_date: date
) -> str:
    lines: list[str] = []
    lines.append(f"# Close Phase Timing Report — {report_date.isoformat()}")
    lines.append("")
    lines.append("## Phase timings")
    lines.append("")
    lines.append("| Phase | Elapsed (ms) |")
    lines.append("|---|---:|")
    for name, elapsed_ms in rows:
        lines.append(f"| {name} | {elapsed_ms:.3f} |")
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- Dominant phase: **{dominant}**")
    lines.append(f"- Chosen implementation path: **{path_choice}**")
    lines.append("")
    return "\n".join(lines)


@pytest.mark.perf
def test_close_phase_timing_report_smoke(qtbot, tmp_path, monkeypatch):
    win = MainWindow(yaml_filename="")
    qtbot.addWidget(win)
    try:
        payload = {
            "items": [
                {
                    "id": i,
                    "name": f"item-{i}",
                    "meta": {"a": i, "b": i * 2, "c": [i, i + 1, i + 2]},
                }
                for i in range(2500)
            ]
        }
        tab = win._add_tab(data=payload, file_path=str(tmp_path / "close-phase.json"))
        assert isinstance(tab, JsonTab)
        initial_tab_count = win.tabWidget.count()
        index = win.tabWidget.indexOf(tab)
        assert index >= 0

        timings_ms = {
            "snapshot_root_data": 0.0,
            "schema_unregister": 0.0,
            "view_state_save": 0.0,
            "remove_tab": 0.0,
            "delete_later": 0.0,
            "forced_deferred_delete": 0.0,
        }

        # Phase 1: snapshot
        original_root_data = tab.root_data

        def timed_root_data():
            started = time.perf_counter()
            try:
                return original_root_data()
            finally:
                timings_ms["snapshot_root_data"] += (time.perf_counter() - started) * 1000.0

        monkeypatch.setattr(tab, "root_data", timed_root_data)

        # Phase 3: schema unregister
        original_unregister = win._schema_tab_pool.unregister

        def timed_unregister(widget):
            started = time.perf_counter()
            try:
                return original_unregister(widget)
            finally:
                timings_ms["schema_unregister"] += (time.perf_counter() - started) * 1000.0

        monkeypatch.setattr(win._schema_tab_pool, "unregister", timed_unregister)

        # Phase 4: save view state
        original_view_state_save = tab_lifecycle_module.view_state.save

        def timed_view_state_save(widget):
            started = time.perf_counter()
            try:
                return original_view_state_save(widget)
            finally:
                timings_ms["view_state_save"] += (time.perf_counter() - started) * 1000.0

        monkeypatch.setattr(tab_lifecycle_module.view_state, "save", timed_view_state_save)

        # Phase 5: remove tab
        original_remove_tab = win.tabWidget.removeTab

        def timed_remove_tab(i):
            started = time.perf_counter()
            try:
                return original_remove_tab(i)
            finally:
                timings_ms["remove_tab"] += (time.perf_counter() - started) * 1000.0

        monkeypatch.setattr(win.tabWidget, "removeTab", timed_remove_tab)

        # Phase 6a: deleteLater scheduling
        original_delete_later = tab.deleteLater

        def timed_delete_later():
            started = time.perf_counter()
            try:
                return original_delete_later()
            finally:
                timings_ms["delete_later"] += (time.perf_counter() - started) * 1000.0

        monkeypatch.setattr(tab, "deleteLater", timed_delete_later)

        # Trigger close path under measurement
        win._tab_lifecycle.close_tab(index)

        # Phase 6b: forced deferred deletion processing
        started = time.perf_counter()
        QApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        QApplication.processEvents()
        timings_ms["forced_deferred_delete"] = (time.perf_counter() - started) * 1000.0

        assert win.tabWidget.count() == initial_tab_count - 1

        rows = [
            ("snapshot_root_data", timings_ms["snapshot_root_data"]),
            ("schema_unregister", timings_ms["schema_unregister"]),
            ("view_state_save", timings_ms["view_state_save"]),
            ("remove_tab", timings_ms["remove_tab"]),
            ("delete_later", timings_ms["delete_later"]),
            ("forced_deferred_delete", timings_ms["forced_deferred_delete"]),
        ]
        dominant = max(rows, key=lambda row: row[1])[0]
        path_choice = "chunk/yield" if dominant in {"snapshot_root_data", "view_state_save"} else "atomic pre-show"

        report_path = tmp_path / f"close-phase-timing-{date.today().isoformat()}.md"
        report_path.write_text(_format_close_phase_report(rows, dominant, path_choice, date.today()), encoding="utf-8")
        report_text = report_path.read_text(encoding="utf-8")

        assert "snapshot_root_data" in report_text
        assert "schema_unregister" in report_text
        assert "view_state_save" in report_text
        assert "remove_tab" in report_text
        assert "delete_later" in report_text
        assert "forced_deferred_delete" in report_text
        assert "Dominant phase" in report_text
        assert "Chosen implementation path" in report_text
    finally:
        _cleanup(win)
