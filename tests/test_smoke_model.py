from tree.model import JsonTreeModel


def test_construct_simple_model():
    model = JsonTreeModel({"a": 1, "b": [2, 3]})

    assert model.columnCount() == 3
    assert model.rowCount() == 2

    b_index = model.index(1, 0)
    assert model.rowCount(b_index) == 2
