from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from validation.issue import ValidationIssue
from validation.json_pointer import instance_path_to_model_path

_SEVERITY_RANK = {
    "warning": 1,
    "error": 2,
}


class IssueIndex:
    """Lookup index for validation issues by model path."""

    def __init__(self, issues: Iterable[ValidationIssue], root_data: Any):
        self._exact: dict[tuple[int, ...], list[ValidationIssue]] = defaultdict(list)
        self._severity: dict[tuple[int, ...], str] = {}
        self._ancestor: dict[tuple[int, ...], str] = {}
        self._issues: list[ValidationIssue] = []
        self._count = 0

        for issue in issues:
            self._issues.append(issue)
            self._count += 1
            model_path = instance_path_to_model_path(root_data, issue.instance_path)
            if model_path is None:
                continue
            self._exact[model_path].append(issue)
            self._severity[model_path] = _max_severity(self._severity.get(model_path), issue.severity)

            for i in range(len(model_path)):
                ancestor = model_path[:i]
                self._ancestor[ancestor] = _max_severity(self._ancestor.get(ancestor), issue.severity)

    def severity_at(self, model_path: tuple[int, ...]) -> str | None:
        return self._severity.get(model_path)

    def issues_for(self, model_path: tuple[int, ...]) -> list[ValidationIssue]:
        return list(self._exact.get(model_path, ()))

    def ancestor_severity(self, model_path: tuple[int, ...]) -> str | None:
        return self._ancestor.get(model_path)

    def all_issues(self) -> list[ValidationIssue]:
        return list(self._issues)

    def __len__(self) -> int:
        return self._count


def _max_severity(left: str | None, right: str | None) -> str | None:
    if left is None:
        return right
    if right is None:
        return left
    return left if _SEVERITY_RANK.get(left, 0) >= _SEVERITY_RANK.get(right, 0) else right
