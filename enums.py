import base64
import gzip
import zlib
from datetime import date, datetime, time
from enum import StrEnum
from typing import Any

import gmpy2

from datetime_editor import parse_datetime_text


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

        case gmpy2.mpq():
            if 0 <= value <= 1:
                return JsonType.PERCENT
            return JsonType.FLOAT

        case str(s):
            if s.find("\n") != -1:
                return JsonType.MULTILINE

            try:
                raw = base64.b64decode(s, validate=True)

                try:
                    unzlibbed = zlib.decompress(raw)
                    return JsonType.ZLIB
                except Exception:
                    pass

                try:
                    ungzipped = gzip.decompress(raw)
                    return JsonType.GZIP
                except Exception:
                    pass

                return JsonType.BYTES
            except Exception:
                pass

            try:
                val = parse_datetime_text(s)
                match val:
                    case datetime(tzinfo=None):
                        return JsonType.DATETIME
                    case datetime():
                        return JsonType.DATETIMEZONE
                    case time():
                        return JsonType.TIME
                    case date():
                        return JsonType.DATE
            except Exception:
                pass

            return JsonType.STRING

        case list(_):
            return JsonType.ARRAY

        case dict(_):
            return JsonType.OBJECT

    raise Exception(f"`JsonType` is unknown for {value=}")


class JsonType(StrEnum):
    # Basic
    INTEGER = "integer"
    FLOAT = "float"
    STRING = "string"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"

    # Extra Number
    PERCENT = "percent"

    # Multiline Text Format
    MULTILINE = "multiline"

    # Datetime Text Format
    DATE = "date"
    TIME = "time"
    DATETIME = "datetime"
    DATETIMEZONE = "dt+timezone"

    # Advanced Text Encoding
    BYTES = "bytes"  # base64
    ZLIB = "zlib"  # base64+zlib
    GZIP = "gzip"  # base64+gzip
