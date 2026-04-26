"""Compatibility imports for delegates."""

from delegates.bytes_codec import decode_bytes, encode_bytes
from delegates.name_delegate import NameDelegate
from delegates.type_delegate import JsonTypeDelegate
from delegates.value import ValueDelegate

__all__ = ["ValueDelegate", "JsonTypeDelegate", "NameDelegate", "decode_bytes", "encode_bytes"]
