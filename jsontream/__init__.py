import json
from typing import Any, Iterable, Type


def new_streaming_json_factory(
    base_encoder_class: Type[json.JSONEncoder] = json.JSONEncoder,
) -> Type[json.JSONEncoder]:
    class _Inner(StreamingJSONEncoderWrapper):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(None, *args, base_encoder_class=base_encoder_class, **kwargs)

    return _Inner


class StreamingJSONEncoderWrapper(json.JSONEncoder):
    def __init__(
        self,
        base_encoder: json.JSONEncoder = None,
        base_encoder_class: Type[json.JSONEncoder] = json.JSONEncoder,
        *args,
        **kwargs,
    ):
        """
        Initialize the wrapper with a base JSONEncoder class.

        Args:
            base_encoder: An instance of JSONEncoder to use as the base encoder
            base_encoder_class: The JSONEncoder class to wrap (defaults to json.JSONEncoder)
            *args, **kwargs: Arguments to pass to the base encoder (e.g., separators, indent)
        """
        super().__init__(*args, **kwargs)

        if base_encoder is None:
            base_encoder = base_encoder_class(*args, **kwargs)

        self.base_encoder = base_encoder

        # Store encoder parameters for use in iterencode
        self.item_separator, self.key_separator = kwargs.get("separators", (",", ":"))
        self.indent = kwargs.get("indent")
        self.indent_str = "\n" + " " * (self.indent or 0)

        def offset(text: str) -> str:
            return text.replace("\n", self.indent_str)

        self.offset = offset

        if self.indent is not None:
            self.iterencode = self._pretty_iterencode
        else:
            self.iterencode = self._shrink_iterencode

    def default(self, obj: Any) -> Any:
        """Handle serialization, delegating to base encoder, but raise for generators."""
        if hasattr(obj, "__iter__"):
            if hasattr(obj, "__len__"):
                return self.base_encoder.default(obj)
            obj = iter(obj)

        if hasattr(obj, "__next__"):
            raise TypeError("Generators must be handled by iterencode, not default")
        else:
            # Delegate to the base encoder for all other types
            return self.base_encoder.default(obj)

    def encode(self, obj: Any) -> Any:
        """Handle serialization, delegating to base encoder, but raise for generators."""
        if hasattr(obj, "__iter__"):
            if hasattr(obj, "__len__"):
                return self.base_encoder.encode(obj)
            obj = iter(obj)

        if hasattr(obj, "__next__"):
            raise TypeError("Generators must be handled by iterencode, not encode")
        else:
            return self.base_encoder.encode(obj)

    def _get_indent_str(self, level: int) -> str:
        """Helper to generate indentation string based on indent setting."""
        if self.indent is None:
            return ""
        return "\n" + " " * (self.indent * level)

    def iterencode(self, obj: Any, _one_shot: bool = False) -> Iterable[str]: ...

    def _pretty_iterencode(self, obj: Any, _one_shot: bool = False) -> Iterable[str]:
        """Encode the object in a streaming fashion, handling generators specially."""
        if hasattr(obj, "__iter__"):
            if hasattr(obj, "__len__"):
                yield from self.base_encoder.iterencode(obj)
                return
            obj = iter(obj)

        if hasattr(obj, "__next__"):
            # Peek at the first item to determine if it's dict-like or list-like
            try:
                first_item = next(obj)
            except StopIteration:
                # Empty generator, encode as empty list
                raise TypeError(
                    "Empty generators must be replaced with empty lists or dicts before encoding"
                    ", because there is no way to distinguish zero-length list-like and dict-like generators"
                )

            # Check if first item is a tuple of length 2 (dict-like)
            if isinstance(first_item, tuple):
                if len(first_item) != 2:
                    raise TypeError(
                        f"Only key-value (len=2) pairs are allowed for tuples in dict-like generators"
                        f", got len={len(first_item)}"
                    )

                yield "{"

                # Process first item without comma
                key, value = first_item
                yield self.indent_str
                yield from map(self.offset, self.iterencode(key))
                yield self.key_separator
                yield from map(self.offset, self.iterencode(value))

                # Process remaining items with comma
                for key, value in obj:
                    yield self.item_separator
                    yield self.indent_str
                    yield from map(self.offset, self.iterencode(key))
                    yield self.key_separator
                    yield from map(self.offset, self.iterencode(value))

                yield "\n}"
            else:  # first item is not a tuple, so generator is list-like
                yield "["

                # Process first item without comma
                yield self.indent_str
                yield from map(self.offset, self.iterencode(first_item))

                # Process remaining items with comma
                for item in obj:
                    yield self.item_separator
                    yield self.indent_str
                    yield from map(self.offset, self.iterencode(item))

                yield "\n]"
        else:
            # Delegate to the base encoder for all other types
            yield from self.base_encoder.iterencode(obj)

    def _shrink_iterencode(self, obj: Any, _one_shot: bool = False) -> Iterable[str]:
        """Encode the object in a streaming fashion, handling generators specially."""
        if hasattr(obj, "__iter__"):
            if hasattr(obj, "__len__"):
                yield from self.base_encoder.iterencode(obj)
                return
            obj = iter(obj)

        if hasattr(obj, "__next__"):
            # Peek at the first item to determine if it's dict-like or list-like
            try:
                first_item = next(obj)
            except StopIteration:
                # Empty generator, encode as empty list
                raise TypeError(
                    "Empty generators must be replaced with empty lists or dicts before encoding"
                    ", because there is no way to distinguish zero-length list-like and dict-like generators"
                )

            # Check if first item is a tuple of length 2 (dict-like)
            if isinstance(first_item, tuple):
                if len(first_item) != 2:
                    raise TypeError(
                        f"Only key-value (len=2) pairs are allowed for tuples in dict-like generators"
                        f", got len={len(first_item)}"
                    )

                yield "{"

                # Process first item without comma
                key, value = first_item
                yield from self.iterencode(key)
                yield self.key_separator
                yield from self.iterencode(value)

                # Process remaining items with comma
                for key, value in obj:
                    yield self.item_separator
                    yield from self.iterencode(key)
                    yield self.key_separator
                    yield from self.iterencode(value)

                yield "}"
            else:  # first item is not a tuple, so generator is list-like
                yield "["

                # Process first item without comma
                yield from self.iterencode(first_item)

                # Process remaining items with comma
                for item in obj:
                    yield self.item_separator
                    yield from self.iterencode(item)

                yield "]"
        else:
            # Delegate to the base encoder for all other types
            yield from self.base_encoder.iterencode(obj)
