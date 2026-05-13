"""Phase 5.1 — carry-over & foundations regression tests.

Covers:
* `mergeWith` collapses consecutive same-path edits within the merge window.
* Programmatic type changes do *not* re-open the value editor (the
  ``_interactive`` flag stays ``False``); the smoke regression is also
  covered by ``test_smoke_mainwindow``.
* Decode failures on malformed BYTES/ZLIB/GZIP payloads are reported via
  the status callback instead of escaping ``ValueDelegate.createEditor``.
"""

from PySide6.QtCore import QModelIndex, Qt
from PySide6.QtWidgets import QStyleOptionViewItem, QWidget

from documents.tab import _CMD_ID_EDIT_VALUE, _CMD_ID_RENAME, _MERGE_WINDOW_SECONDS, JsonTab
from tree.types import JsonType


def _row_named(tab: JsonTab, name: str) -> int | None:
    for r in range(tab.model.rowCount(QModelIndex())):
        if tab.model.get_item(tab.model.index(r, 0, QModelIndex())).name == name:
            return r
    return None


# ---------------------------------------------------------------------------
# mergeWith()
# ---------------------------------------------------------------------------


def test_command_ids_are_distinct_and_stable():
    """Sanity check on the merge-id constants."""
    assert _CMD_ID_EDIT_VALUE != _CMD_ID_RENAME
    assert _CMD_ID_EDIT_VALUE != -1
    assert _CMD_ID_RENAME != -1


def test_consecutive_edits_to_same_path_merge(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)
    answer_row = _row_named(tab, "answer")
    assert answer_row is not None
    value_idx = tab.model.index(answer_row, 2, QModelIndex())

    before = tab.undo_stack.count()
    assert tab.commit_set_data(value_idx, 100, Qt.ItemDataRole.EditRole)
    assert tab.commit_set_data(value_idx, 101, Qt.ItemDataRole.EditRole)
    assert tab.commit_set_data(value_idx, 102, Qt.ItemDataRole.EditRole)
    assert tab.undo_stack.count() - before == 1, "consecutive same-path edits should merge"

    tab.undo_stack.undo()
    item = tab.model.get_item(tab.model.index(answer_row, 0, QModelIndex()))
    assert item.value == 42


def test_edits_outside_merge_window_do_not_merge(qtbot, monkeypatch):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)
    answer_row = _row_named(tab, "answer")
    assert answer_row is not None
    value_idx = tab.model.index(answer_row, 2, QModelIndex())

    fake_t = [1000.0]
    monkeypatch.setattr("time.monotonic", lambda: fake_t[0])

    before = tab.undo_stack.count()
    assert tab.commit_set_data(value_idx, 100, Qt.ItemDataRole.EditRole)
    fake_t[0] += _MERGE_WINDOW_SECONDS + 0.1
    assert tab.commit_set_data(value_idx, 101, Qt.ItemDataRole.EditRole)
    assert tab.undo_stack.count() - before == 2


def test_rename_commands_merge(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)
    name_idx = tab.model.index(0, 0, QModelIndex())

    before = tab.undo_stack.count()
    assert tab.commit_set_data(name_idx, "first", Qt.ItemDataRole.EditRole)
    assert tab.commit_set_data(name_idx, "second", Qt.ItemDataRole.EditRole)
    assert tab.undo_stack.count() - before == 1
    assert tab.model.get_item(name_idx).name == "second"


# ---------------------------------------------------------------------------
# Decode-failure surfacing
# ---------------------------------------------------------------------------


def test_malformed_bytes_payload_does_not_raise_in_create_editor(qtbot):
    captured: list[tuple[str, int]] = []

    def status(msg: str, ms: int = 0) -> None:
        captured.append((msg, ms))

    tab = JsonTab(lambda *_: None, status_message_callback=status)
    qtbot.addWidget(tab)

    type_idx = tab.model.index(0, 1, QModelIndex())
    value_idx = tab.model.index(0, 2, QModelIndex())
    name_idx = tab.model.index(0, 0, QModelIndex())

    tab.model.setData(type_idx, JsonType.BYTES, Qt.ItemDataRole.EditRole)
    item = tab.model.get_item(name_idx)
    item.value = "!!!not-base64!!!"

    delegate = tab.value_delegate
    parent = QWidget(tab)
    qtbot.addWidget(parent)
    opt = QStyleOptionViewItem()

    editor = delegate.createEditor(parent, opt, value_idx)
    assert editor is None
    assert any("Decode failed" in msg for msg, _ in captured)


# ---------------------------------------------------------------------------
# Auto-reopen / interactive flag wiring
# ---------------------------------------------------------------------------


def test_programmatic_type_change_does_not_set_interactive_flag(qtbot):
    tab = JsonTab(lambda *_: None)
    qtbot.addWidget(tab)
    type_idx = tab.model.index(0, 1, QModelIndex())

    tab.model.setData(type_idx, JsonType.STRING, Qt.ItemDataRole.EditRole)
    assert tab.type_delegate._interactive is False
