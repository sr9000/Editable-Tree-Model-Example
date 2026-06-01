import pytest

from settings import SECRET_WORD_PREFIXES
from state.secret_settings import get_secret_word_prefixes, set_secret_word_prefixes
from tree.model import JsonTreeModel
from tree.types import JsonType


@pytest.fixture(autouse=True)
def _restore_defaults():
    set_secret_word_prefixes(SECRET_WORD_PREFIXES)
    yield
    set_secret_word_prefixes(SECRET_WORD_PREFIXES)


def _first_item_type(model: JsonTreeModel) -> JsonType:
    item = model.get_item(model.index(0, 0))
    return item.json_type


def test_added_prefix_detects_new_secret_field():
    set_secret_word_prefixes(("dbpass",))
    model = JsonTreeModel({"dbpassword": "plain-secret"})
    assert _first_item_type(model) is JsonType.SECRET_LINE


def test_removing_passw_stops_new_password_autopromotion():
    set_secret_word_prefixes(("token", "secret"))
    model = JsonTreeModel({"password": "plain-secret"})
    assert _first_item_type(model) is JsonType.STRING


def test_prefixes_persist_and_restore():
    expected = ("dbpass", "private")
    set_secret_word_prefixes(expected)
    assert get_secret_word_prefixes() == expected
