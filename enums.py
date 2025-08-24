import base64, zlib, gzip
from enum import StrEnum
from typing import Any
from dateutil.parser import isoparse

def parse_json_type(value: Any) -> "JsonType":
    match value:
        case None:
            return JsonType.NULL

        case bool(_):
            return JsonType.BOOLEAN

        case int(_):
            return JsonType.INTEGER

        case float(x):
            if 0 <= x <= 1:
                return JsonType.PERCENT
            return JsonType.FLOAT

        case str(s):
            if s.find("\n") != -1:
                return JsonType.MULTI_LINE

            try:
                raw = base64.b64decode(s)

                try:
                    unzlibbed = zlib.decompress(raw)
                    return JsonType.ZLIB
                except:
                    pass

                try:
                    ungzipped = gzip.decompress(raw)
                    return JsonType.GZIP
                except:
                    pass

                return JsonType.BYTES
            except:
                pass

            try:
                dt = isoparse(s)

                if dt.hour == 0 and dt.minute == 0 and dt.second == 0 and dt.microsecond == 0 and len(s) <= 11:
                    return JsonType.DATE

                if dt.tzinfo is not None:
                    return JsonType.DATETIMEZONE

                return JsonType.DATETIME
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
    INTEGER = "integer"

    FLOAT = "float"
    PERCENT = "percent"

    # Text
    SINGLE_LINE = "single-line"
    DATE = "date"
    DATETIME = "date-time"
    DATETIMEZONE = "dt+timezone"

    MULTI_LINE = "multi-line"
    BYTES = "bytes"  # base64
    ZLIB = "zlib"  # base64+zlib
    GZIP = "gzip"  # base64+gzip

    # Boolean
    BOOLEAN = "boolean"

    # Composite
    OBJECT = "object"
    ARRAY = "array"

    # Empty
    NULL = "null"
