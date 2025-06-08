import json
from typing import Any

import pytest

from jsontream import StreamingJSONEncoderWrapper


# Custom encoder for testing delegation
class CustomJSONEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

    def default(self, obj: Any) -> Any:
        if isinstance(obj, set):
            return list(obj)
        return super().default(obj)


@pytest.fixture
def encoder():
    return StreamingJSONEncoderWrapper(separators=(",", ":"))


def itself(x):
    return x


# Helper function to collect iterencode output into a single string
def collect_iterencode(encoder: StreamingJSONEncoderWrapper, obj: Any) -> str:
    return "".join(encoder.iterencode(obj))


def test_default_raises_for_generator(encoder):
    gen = map(itself, range(3))
    with pytest.raises(
        TypeError, match="Generators must be handled by iterencode, not default"
    ):
        encoder.default(gen)


def test_encode_raises_for_generator(encoder):
    gen = map(itself, range(3))
    with pytest.raises(
        TypeError, match="Generators must be handled by iterencode, not encode"
    ):
        encoder.encode(gen)


def test_iterencode_empty_generator_raises(encoder):
    gen = iter([])
    with pytest.raises(
        TypeError, match="Empty generators must be replaced with empty lists or dicts"
    ):
        list(encoder.iterencode(gen))


# Test list-like generators
def test_iterencode_list_generator(encoder):
    gen = iter([1, 2, 3])
    result = collect_iterencode(encoder, gen)
    assert result == "[1,2,3]"


def test_iterencode_nested_list_generator(encoder):

    def nested_gen():
        yield [1, 2]
        yield [3, 4]

    gen = nested_gen()
    result = collect_iterencode(encoder, gen)
    assert result == "[[1,2],[3,4]]"


# Test dict-like generators
def test_iterencode_dict_generator(encoder):
    gen = iter([("key1", 1), ("key2", 2), ("key3", 3)])
    result = collect_iterencode(encoder, gen)
    assert result == '{"key1":1,"key2":2,"key3":3}'


def test_iterencode_nested_dict_generator(encoder):

    def nested_gen():
        yield "outer1", {"inner1": 1, "inner2": 2}
        yield "outer2", {"inner3": 3, "inner4": 4}

    gen = nested_gen()
    result = collect_iterencode(encoder, gen)
    assert (
        result == '{"outer1":{"inner1":1,"inner2":2},"outer2":{"inner3":3,"inner4":4}}'
    )


def test_iterencode_dict_generator_invalid_tuple(encoder):
    gen = iter([("key1", 1, 2), ("key2", 2, 3)])  # Invalid tuple length (all len=3)
    with pytest.raises(TypeError, match="Only key-value \\(len=2\\) pairs are allowed"):
        list(encoder.iterencode(gen))


def test_iterencode_dict_generator_invalid_tuple_unpack(encoder):
    gen = iter([("key1", 1), ("key2", 2, 3)])  # Second tuple has len=3
    with pytest.raises(ValueError, match="too many values to unpack"):
        list(encoder.iterencode(gen))


# Test delegation to base encoder
def test_iterencode_delegates_to_base_encoder(encoder):
    data = {"a": 1, "b": [2, 3], "c": None}
    result = collect_iterencode(encoder, data)
    expected = json.dumps(data, separators=(",", ":"))
    assert result == expected


def test_iterencode_delegates_to_custom_encoder(encoder):
    data = {"a": {1, 2, 3}}  # Set should be handled by CustomJSONEncoder
    encoder = StreamingJSONEncoderWrapper(
        base_encoder_class=CustomJSONEncoder, separators=(",", ":")
    )
    result = collect_iterencode(encoder, data)
    expected = json.dumps(
        {"a": [1, 2, 3]}, separators=(",", ":")
    )  # Set converted to list
    assert result == expected


# Test mixed nested structures
def test_iterencode_mixed_nested_generator(encoder):

    def mixed_gen():
        yield "dict", (x for x in [("a", 1), ("b", 2)])
        yield "list", (x for x in [3, 4, 5])

    gen = mixed_gen()
    result = collect_iterencode(encoder, gen)
    assert result == '{"dict":{"a":1,"b":2},"list":[3,4,5]}'


# Test error handling for invalid types in base encoder
def test_iterencode_base_encoder_error(encoder):
    data = {"a": object()}  # Object is not JSON serializable
    with pytest.raises(TypeError, match="is not JSON serializable"):
        list(encoder.iterencode(data))


# Test streaming behavior (ensure chunks are yielded correctly)
def test_iterencode_streaming_chunks(encoder):
    gen = iter([1, 2, 3])
    chunks = list(encoder.iterencode(gen))
    assert len(chunks) > 1  # Should yield multiple chunks
    assert "".join(chunks) == "[1,2,3]"


def test_iterencode_dict_streaming_chunks(encoder):
    gen = iter([("key1", 1), ("key2", 2), ("key3", 3)])
    chunks = list(encoder.iterencode(gen))
    assert len(chunks) > 1  # Should yield multiple chunks
    assert "".join(chunks) == '{"key1":1,"key2":2,"key3":3}'
