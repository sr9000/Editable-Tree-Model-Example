"""JSON schema validation helpers.

This package intentionally has no Qt dependencies.
"""

from validation.issue import ValidationIssue
from validation.index import IssueIndex
from validation.json_pointer import instance_path_to_model_path, model_path_to_instance_path
from validation.schema_source import SchemaRef, discover_schema, load_schema
from validation.validator import is_schema_valid, validate_document

__all__ = [
    "ValidationIssue",
    "IssueIndex",
    "SchemaRef",
    "discover_schema",
    "load_schema",
    "instance_path_to_model_path",
    "model_path_to_instance_path",
    "is_schema_valid",
    "validate_document",
]
