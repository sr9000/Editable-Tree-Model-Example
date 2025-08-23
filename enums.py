import base64
from enum import StrEnum
from typing import Any


def parse_json_type(value: Any) -> "JsonType":
    match value:
        case None:
            return JsonType.NULL

        case bool(_):
            return JsonType.BOOLEAN

        case int(_):
            return JsonType.INTEGER

        case float(_):
            return JsonType.FLOAT

        case str(s):
            if s.find("\n") != -1:
                return JsonType.MULTI_LINE

            try:
                binary = base64.b64decode(s)
                return JsonType.BYTES
            except:
                pass

            return JsonType.SINGLE_LINE

        case list(_):
            return JsonType.ARRAY

        case dict(_):
            return JsonType.OBJECT

    raise Exception(f"`JsonType` is unknown for {value=}")


class JsonType(StrEnum):

    # Number
    FLOAT = "float"
    INTEGER = "integer"

    # Text
    SINGLE_LINE = "single-line"
    MULTI_LINE = "multi-line"
    BYTES = "bytes"

    # Boolean
    BOOLEAN = "boolean"

    # Composite
    OBJECT = "object"
    ARRAY = "array"

    # Empty
    NULL = "null"
