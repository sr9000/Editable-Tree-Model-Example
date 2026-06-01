#!/usr/bin/env bash
# Enforce the editors/ isolation contract (responsibility-segregation plan §2.5):
#   - Concrete widgets (editors/inline/**, editors/windowed/**) must NOT import
#     from app/, documents/, or tree/ -- they stay self-hosted, reusable QWidgets.
#   - The dispatch seam (top-level editors/*.py, e.g. factory.py / context.py) must
#     NOT import from app/ or documents/, but MAY import tree.* for type dispatch.
#
# Usage:
#   bash .githooks/_check_editors_isolation.sh
set -euo pipefail

fail=0

scan() {
    local label="$1"
    local pattern="$2"
    shift 2
    local f hits
    for f in "$@"; do
        [[ -f "$f" ]] || continue
        hits=$(grep -nE "$pattern" "$f" || true)
        if [[ -n "$hits" ]]; then
            echo "ERROR: $f violates editors isolation ($label):"
            echo "$hits"
            fail=1
        fi
    done
}

# Concrete widgets: no app / documents / tree.
mapfile -t WIDGETS < <(git ls-files 'editors/inline' 'editors/windowed' | grep -E '\.py$' || true)
if [[ ${#WIDGETS[@]} -gt 0 ]]; then
    scan "concrete widget imports app/documents/tree" \
        '^[[:space:]]*(from|import)[[:space:]]+(app|documents|tree)([.[:space:]]|$)' \
        "${WIDGETS[@]}"
fi

# Dispatch seam (top-level editors/*.py only): no app / documents (tree allowed).
mapfile -t SEAM < <(git ls-files 'editors/*.py' | grep -vE '^editors/(inline|windowed)/' || true)
if [[ ${#SEAM[@]} -gt 0 ]]; then
    scan "editors seam imports app/documents" \
        '^[[:space:]]*(from|import)[[:space:]]+(app|documents)([.[:space:]]|$)' \
        "${SEAM[@]}"
fi

exit $fail
