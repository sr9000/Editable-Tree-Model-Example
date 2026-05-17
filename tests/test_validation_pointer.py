from gmpy2 import mpq

from validation.json_pointer import instance_path_to_model_path, model_path_to_instance_path

DATA = {
    "obj": {
        "arr": [
            {"leaf": "x"},
            {"leaf": "y"},
        ],
        "other": 10,
    },
    "tail": mpq("1/3"),
}


def test_instance_path_root_round_trip():
    assert instance_path_to_model_path(DATA, ()) == ()
    assert model_path_to_instance_path(DATA, ()) == ()


def test_instance_path_to_model_path_nested_object_array():
    # obj -> arr -> [1] -> leaf
    assert instance_path_to_model_path(DATA, ("obj", "arr", 1, "leaf")) == (0, 0, 1, 0)


def test_instance_path_to_model_path_missing_key_returns_none():
    assert instance_path_to_model_path(DATA, ("obj", "missing")) is None


def test_model_path_to_instance_path_nested_round_trip():
    model_path = (0, 0, 0, 0)
    assert model_path_to_instance_path(DATA, model_path) == ("obj", "arr", 0, "leaf")


def test_model_path_to_instance_path_invalid_path_raises():
    try:
        model_path_to_instance_path(DATA, (9,))
    except ValueError as exc:
        assert "outside" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("Expected ValueError for invalid model path")
