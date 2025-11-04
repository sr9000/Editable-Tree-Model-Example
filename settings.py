from enum import StrEnum

APPLICATION_ID = "org.jeditor.204b2a8a-e956-4c62-911d-cfb29a4fe257"
MODAL_WINDOW_SIZE = (600, 440)
WINDOW_DEFAULT_SIZE = (800, 600)


class IntegerInfo(StrEnum):
    NONE = "none"
    HEX = "hex"
    OCT = "octal"
    BIN = "binary"


class FloatInfo(StrEnum):
    NONE = "none"
    FLOAT128 = "float128"
    FLOAT64 = "float64"
    FLOAT32 = "float32"
    FLOAT16 = "float16"


class MultiLineInfo(StrEnum):
    NONE = "none"
    WC = "wc"  # lines, words, chars


class SingleLineInfo(StrEnum):
    NONE = "none"
    BYTES = "bytes"
    RUNES = "runes"
    GRAPHEMES = "graphemes"
