#!/usr/bin/env bash
# Enforce the tree/ isolation contract (refactor-tree-upward-imports plan §4):
#   - tree/*.py must NOT import from app/, documents/, editors/, delegates/,
#     state/, or validation/ — tree/ is the low-level data package.
#   - Lazy imports inside function bodies are also forbidden (the dependency
#     direction is wrong regardless of when the import executes).
#
# Allowlist: specific lines that are permitted because they live inside
# _default_secret_name_predicate (a lazy fallback that keeps headless
# test fixtures working; the real predicate is injected at composition time).
#
# Usage:
#   bash .githooks/_check_tree_isolation.sh
set -euo pipefail

# Allowlisted lines: file:linenumber pairs that are permitted.
ALLOWLIST=(
    "tree/item.py:30"
    "tree/item.py:31"
)

is_allowlisted() {
    local path="$1"
    local lineno="$2"
    for allowed in "${ALLOWLIST[@]}"; do
        [[ "${path}:${lineno}" == "$allowed" ]] && return 0
    done
    return 1
}

fail=0

# tree/ files: no app / documents / editors / delegates / state / validation.
mapfile -t TREE_FILES < <(git ls-files 'tree' | grep -E '\.py$' || true)

for f in "${TREE_FILES[@]}"; do
    [[ -f "$f" ]] || continue
    while IFS= read -r line; do
        # Extract line number from grep output (format: "25:    from state...")
        lineno="${line%%:*}"
        rest="${line#*:}"
        if is_allowlisted "$f" "$lineno"; then
            continue
        fi
        echo "ERROR: $f violates tree isolation (line $lineno):"
        echo "  $rest"
        fail=1
    done < <(grep -nE '^[[:space:]]*(from|import)[[:space:]]+(app|documents|editors|delegates|state|validation)([.[:space:]]|$)' "$f" || true)
done

exit $fail
