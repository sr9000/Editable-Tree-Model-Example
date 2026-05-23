from PySide6.QtCore import QModelIndex, Qt

from io_formats.detect import SAVE_FORMAT_JSON
from io_formats.dump import dump_text
from io_formats.load import load_file_with_format
from tree.model import JsonTreeModel
from tree.types import JsonType


def _save_and_reload(tmp_path, data):
    path = tmp_path / "secret.json"
    path.write_text(dump_text(str(path), data, save_format=SAVE_FORMAT_JSON), encoding="utf-8")
    loaded, _fmt = load_file_with_format(str(path))
    return JsonTreeModel(loaded)


def test_password_roundtrip_restores_secret_line(tmp_path):
    model = _save_and_reload(tmp_path, {"password": "plain-secret"})
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.SECRET_LINE


def test_private_key_roundtrip_restores_secret_text(tmp_path):
    model = _save_and_reload(tmp_path, {"private_key": "-----BEGIN-----\nabc\n-----END-----"})
    item = model.get_item(model.index(0, 0, QModelIndex()))
    assert item.json_type is JsonType.SECRET_TEXT


def test_sticky_secret_without_matching_name_falls_back_to_string_on_reload(tmp_path):
    original = JsonTreeModel({"password": "plain-secret"})
    name_idx = original.index(0, 0, QModelIndex())
    assert original.setData(name_idx, "notes", Qt.ItemDataRole.EditRole)
    assert original.get_item(name_idx).json_type is JsonType.SECRET_LINE

    reloaded = _save_and_reload(tmp_path, original.root_item.to_json())
    item = reloaded.get_item(reloaded.index(0, 0, QModelIndex()))
    assert item.name == "notes"
    assert item.json_type is JsonType.STRING
