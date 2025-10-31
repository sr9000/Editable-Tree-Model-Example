import base64
import gzip
import zlib
from enum import StrEnum
from typing import Any

import gmpy2
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

        case gmpy2.mpq():
            if 0 <= value <= 1:
                return JsonType.PERCENT
            return JsonType.FLOAT

        case str(s):
            if s.find("\n") != -1:
                return JsonType.MULTI_LINE

            try:
                raw = base64.b64decode(s, validate=True)

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

            return JsonType.TEXT

        case list(_):
            return JsonType.ARRAY

        case dict(_):
            return JsonType.OBJECT

    raise Exception(f"`JsonType` is unknown for {value=}")


class JsonType(StrEnum):
    # Basic
    INTEGER = "integer"
    FLOAT = "float"
    TEXT = "text"
    BOOLEAN = "boolean"
    OBJECT = "object"
    ARRAY = "array"
    NULL = "null"

    # Extra Number
    PERCENT = "percent"

    # Multiline Text Format
    MULTI_LINE = "multi-line"

    # Datetime Text Format
    DATE = "date"
    DATETIME = "date-time"
    DATETIMEZONE = "dt+timezone"

    # Advanced Text Encoding
    BYTES = "bytes"  # base64
    ZLIB = "zlib"  # base64+zlib
    GZIP = "gzip"  # base64+gzip
