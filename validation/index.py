from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from typing import Any

from validation.issue import ValidationIssue
from validation.json_pointer import instance_path_to_model_path


class IssueIndex:
    """Lookup index for validation issues by model path."""

    def __init__(self, issues: Iterable[ValidationIssue], root_data: Any):
        self._exact: dict[tuple[int, ...], list[ValidationIssue]] = defaultdict(list)
        self._severity: dict[tuple[int, ...], str] = {}
        self._ancestor: dict[tuple[int, ...], str] = {}
        self._affected_paths: set[tuple[int, ...]] = set()
        self._issues: list[ValidationIssue] = []
        self._count = 0

        for issue in issues:
            self._issues.append(issue)
            self._count += 1
            model_path = instance_path_to_model_path(root_data, issue.instance_path)
            if model_path is None:
                continue
            self._exact[model_path].append(issue)
            self._severity[model_path] = "error"
            self._affected_paths.add(model_path)

            for i in range(len(model_path)):
                ancestor = model_path[:i]
                self._ancestor[ancestor] = "error"
                self._affected_paths.add(ancestor)

    def severity_at(self, model_path: tuple[int, ...]) -> str | None:
        return self._severity.get(model_path)

    def issues_for(self, model_path: tuple[int, ...]) -> list[ValidationIssue]:
        return list(self._exact.get(model_path, ()))

    def ancestor_severity(self, model_path: tuple[int, ...]) -> str | None:
        return self._ancestor.get(model_path)

    def all_issues(self) -> list[ValidationIssue]:
        return list(self._issues)

    def is_empty(self) -> bool:
        return self._count == 0

    def affected_paths(self) -> set[tuple[int, ...]]:
        return set(self._affected_paths)

    def __len__(self) -> int:
        return self._count
