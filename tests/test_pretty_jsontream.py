import json
from io import StringIO
from typing import Any, Type

from jsontream import new_streaming_json_factory


# Custom encoder for testing delegation
class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj: Any) -> Any:
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)


# Helper function to use json.dump with the encoder
def dump_to_string(obj: Any, encoder_cls: Type[json.JSONEncoder], **kwargs) -> str:
    output = StringIO()
    json.dump(obj, output, cls=encoder_cls, **kwargs)
    return output.getvalue()


# Test with custom separators and indentation
def test_custom_separators_and_indentation():
    # Create encoder instances
    default_encoder = new_streaming_json_factory(base_encoder_class=json.JSONEncoder)
    custom_encoder = new_streaming_json_factory(base_encoder_class=CustomJSONEncoder)

    # Custom separators and indentation
    separators = (", ", ": ")  # Custom separators for compact output
    indent = 4  # Custom indentation size

    # Test 1: List-like generator with custom separators and indentation
    list_gen = (x for x in [1, 2, 3])
    result_list = dump_to_string(
        list_gen, default_encoder, separators=separators, indent=indent
    )
    expected_list = "[\n    1, \n    2, \n    3\n]"
    assert result_list == expected_list

    # Test 2: Dict-like generator with custom separators and indentation
    dict_gen = iter([("key1", 1), ("key2", 2), ("key3", 3)])
    result_dict = dump_to_string(
        dict_gen, default_encoder, separators=separators, indent=indent
    )
    expected_dict = '{\n    "key1": 1, \n    "key2": 2, \n    "key3": 3\n}'
    assert result_dict == expected_dict

    # Test 3: Non-generator object with custom separators and indentation
    data = {"a": [1, 2, 3], "b": {"x": 1, "y": 2}}
    result_data = dump_to_string(
        data, default_encoder, separators=separators, indent=indent
    )
    expected_data = '{\n    "a": [\n        1, \n        2, \n        3\n    ], \n    "b": {\n        "x": 1, \n        "y": 2\n    }\n}'
    assert result_data == expected_data

    # Test 4: Custom encoder with set, custom separators, and indentation
    set_data = {"a": {1, 2, 3}}
    result_set = dump_to_string(
        set_data, custom_encoder, separators=separators, indent=indent
    )
    expected_set = '{\n    "a": [\n        1, \n        2, \n        3\n    ]\n}'
    assert result_set == expected_set

    # Test 5: Nested generator with custom separators and indentation
    def nested_gen():
        yield "list", (x for x in [1, 2, 3])
        yield "dict", (x for x in [("x", 1), ("y", 2)])

    nested_gen_instance = nested_gen()
    result_nested = dump_to_string(
        nested_gen_instance, default_encoder, separators=separators, indent=indent
    )
    expected_nested = '{\n    "list": [\n        1, \n        2, \n        3\n    ], \n    "dict": {\n        "x": 1, \n        "y": 2\n    }\n}'
    assert result_nested == expected_nested

    # Test 6: nested keys generator
    def nested_keys():
        yield "abc", dict([("key1", 1), ("key2", 2), ("key3", 3)])
        yield "xyz", dict([("key1", 1), ("key2", 2), ("key3", 3)])

    nested_keys_instance = nested_keys()
    result_nested_keys = dump_to_string(
        nested_keys_instance, default_encoder, separators=separators, indent=indent
    )
    expected_nested_keys = (
        "{\n"
        '    "abc": {\n'
        '        "key1": 1, \n'
        '        "key2": 2, \n'
        '        "key3": 3\n'
        "    }, \n"
        '    "xyz": {\n'
        '        "key1": 1, \n'
        '        "key2": 2, \n'
        '        "key3": 3\n'
        "    }\n"
        "}"
    )
    assert result_nested_keys == expected_nested_keys
