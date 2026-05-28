"""JSON schema validation helpers.

This package intentionally has no Qt dependencies.
"""

from validation._sanitize import to_jsonschema_input
from validation.index import IssueIndex
from validation.issue import ValidationIssue
from validation.schema_registry import SchemaEntry, SchemaRegistry, SchemaSource, get_schema_registry
from validation.json_pointer import instance_path_to_model_path, model_path_to_instance_path
from validation.schema_source import discover_schema, load_schema
from validation.schema_types import SchemaRef
from validation.validator import is_schema_valid, validate_document
from validation.yaml_validate import validate_yaml_documents

__all__ = [
    "ValidationIssue",
    "IssueIndex",
    "SchemaRef",
    "SchemaSource",
    "SchemaEntry",
    "SchemaRegistry",
    "get_schema_registry",
    "discover_schema",
    "load_schema",
    "instance_path_to_model_path",
    "model_path_to_instance_path",
    "is_schema_valid",
    "validate_document",
    "validate_yaml_documents",
    "to_jsonschema_input",
]
