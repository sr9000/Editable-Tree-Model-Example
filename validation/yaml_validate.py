"""validation/yaml_validate.py — validate a sequence of YAML documents against a schema.

Each document is validated independently and its issues are prefixed with a
synthetic ``'[doc N]'`` token in ``instance_path`` so navigation can
identify the source document.  The ``instance_path_to_model_path`` helper in
``validation/json_pointer.py`` understands this prefix and translates it to
the N-th row of the root array in the tree model.
"""
from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import Any

from validation.issue import ValidationIssue
from validation.validator import validate_document


def validate_yaml_documents(
    docs: Sequence[Any],
    schema: Mapping[str, Any],
    *,
    max_issues: int = 500,
) -> list[ValidationIssue]:
    """Validate each document in *docs* against *schema*.

    Issues are emitted with ``instance_path`` prefixed by ``'[doc N]'`` where
    *N* is the zero-based document index.  This prefix is later consumed by
    ``instance_path_to_model_path`` when mapping issues to tree-model rows::

        ("[doc 0]", "a", 1)  →  model path  (0, <row of "a">, 1)

    Navigation code that needs to switch to a multi-doc tab should strip the
    prefix and use *N* as the tab/row index.

    Args:
        docs:       Sequence of Python objects, one per YAML document.
        schema:     JSON Schema mapping accepted by ``validate_document``.
        max_issues: Upper bound on the total number of emitted issues.

    Returns:
        List of :class:`~validation.issue.ValidationIssue` with prefixed
        ``instance_path`` values.
    """
    issues: list[ValidationIssue] = []
    for doc_idx, doc in enumerate(docs):
        remaining = max_issues - len(issues)
        if remaining <= 0:
            break
        prefix: tuple[str | int, ...] = (f"[doc {doc_idx}]",)
        for issue in validate_document(doc, schema, max_issues=remaining):
            issues.append(
                ValidationIssue(
                    severity=issue.severity,
                    message=issue.message,
                    instance_path=prefix + issue.instance_path,
                    schema_path=issue.schema_path,
                    kind=issue.kind,
                )
            )
            if len(issues) >= max_issues:
                return issues
    return issues
