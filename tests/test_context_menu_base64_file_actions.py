from __future__ import annotations

import base64

from PySide6.QtCore import QItemSelectionModel
from PySide6.QtWidgets import QMessageBox

from documents.tab import JsonTab
from tree_actions.context_menu import attach_base64_from_file, save_base64_as_file


def _make_tab(qtbot, data) -> JsonTab:
    tab = JsonTab(lambda *_: None, data=data)
    qtbot.addWidget(tab)
    return tab


def _select_value_cell(tab: JsonTab, path: tuple[int, ...]) -> None:
    sm = tab.view.selectionModel()
    src = tab._index_from_path(path).siblingAtColumn(2)
    view = tab._source_to_view(src)
    sm.select(view, QItemSelectionModel.SelectionFlag.ClearAndSelect)
    sm.setCurrentIndex(view, QItemSelectionModel.SelectionFlag.NoUpdate)


def _value_at(tab: JsonTab, path: tuple[int, ...]) -> str:
    return str(tab.model.get_item(tab._index_from_path(path)).value)


def test_attach_base64_from_file_replaces_value(qtbot, tmp_path, monkeypatch):
    initial = base64.b64encode(b"seed payload for bytes").decode("ascii")
    tab = _make_tab(qtbot, {"blob": initial})
    _select_value_cell(tab, (0,))

    payload = b"new file payload"
    source = tmp_path / "payload.bin"
    source.write_bytes(payload)

    monkeypatch.setattr(
        "tree_actions.context_menu.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: (str(source), ""),
    )

    assert attach_base64_from_file(tab.view)
    assert _value_at(tab, (0,)) == base64.b64encode(payload).decode("ascii")


def test_attach_base64_from_file_warns_and_can_cancel_large_file(qtbot, tmp_path, monkeypatch):
    initial = base64.b64encode(b"seed payload for bytes").decode("ascii")
    tab = _make_tab(qtbot, {"blob": initial})
    _select_value_cell(tab, (0,))

    large = tmp_path / "large.bin"
    large.write_bytes(b"x" * (100 * 1024 + 1))

    monkeypatch.setattr(
        "tree_actions.context_menu.QFileDialog.getOpenFileName",
        lambda *_args, **_kwargs: (str(large), ""),
    )

    calls: list[str] = []

    def _warn(*_args, **_kwargs):
        calls.append("warned")
        return QMessageBox.StandardButton.No

    monkeypatch.setattr("tree_actions.context_menu.QMessageBox.warning", _warn)

    before = _value_at(tab, (0,))
    assert not attach_base64_from_file(tab.view)
    assert calls == ["warned"]
    assert _value_at(tab, (0,)) == before


def test_save_base64_as_file_writes_decoded_payload(qtbot, tmp_path, monkeypatch):
    payload = b"content to save"
    encoded = base64.b64encode(payload).decode("ascii")
    tab = _make_tab(qtbot, {"blob": encoded})
    _select_value_cell(tab, (0,))

    target = tmp_path / "out.bin"
    monkeypatch.setattr(
        "tree_actions.context_menu.QFileDialog.getSaveFileName",
        lambda *_args, **_kwargs: (str(target), ""),
    )

    assert save_base64_as_file(tab.view)
    assert target.read_bytes() == payload
