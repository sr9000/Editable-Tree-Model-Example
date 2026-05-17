from validation.index import IssueIndex
from validation.issue import ValidationIssue


def _issue(path, *, kind="type"):
    return ValidationIssue(
        message="problem",
        instance_path=path,
        schema_path=("properties",),
        kind=kind,
    )


def test_issue_index_exact_and_ancestor_severity():
    root_data = {"obj": {"leaf": 1}, "ok": 2}
    idx = IssueIndex([_issue(("obj", "leaf"))], root_data)

    assert idx.severity_at((0, 0)) == "error"
    assert idx.ancestor_severity((0,)) == "error"
    assert idx.ancestor_severity(()) == "error"


def test_issue_index_issues_for_returns_exact_only():
    root_data = {"obj": {"leaf": 1}, "tail": 2}
    issues = [_issue(("obj", "leaf"), kind="type"), _issue(("tail",), kind="minimum")]
    idx = IssueIndex(issues, root_data)

    exact = idx.issues_for((1,))
    assert len(exact) == 1
    assert exact[0].kind == "minimum"
    assert idx.issues_for((0,)) == []


def test_issue_index_missing_paths_are_skipped_but_length_preserved():
    root_data = {"obj": {"leaf": 1}}
    idx = IssueIndex([_issue(("obj", "leaf")), _issue(("obj", "missing"))], root_data)

    assert len(idx) == 2
    assert idx.severity_at((0, 0)) == "error"
    assert idx.severity_at((0, 1)) is None


def test_issue_index_empty_index_is_safe():
    idx = IssueIndex([], {"a": 1})
    assert len(idx) == 0
    assert idx.severity_at((0,)) is None
    assert idx.ancestor_severity((0,)) is None
    assert idx.issues_for((0,)) == []
