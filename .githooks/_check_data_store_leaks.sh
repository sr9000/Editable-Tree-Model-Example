#!/usr/bin/env bash
# Shared guard invoked from .githooks/pre-commit (staged scope) and
# .githooks/pre-commit-ci (whole-tree scope) to forbid new leaks of
# JsonTab.data_store internals into production code outside documents/.
#
# Per plans/20-decouple-jsontab.md Phase B/C/D/E/F: each phase migrates
# external callers off a specific attribute, then appends that attribute
# to FORBIDDEN_DATA_STORE_ATTRS below so the leak cannot return.
#
# Usage:
#   bash .githooks/_check_data_store_leaks.sh <file> [<file> ...]
# Exits 0 if all listed files are clean, 1 otherwise. Skips files in
# documents/ and tests/ (test reach-in is allowed per the design report).

set -euo pipefail

# Attributes that have been fully migrated and must not return.
# Order matches plan §3 phases.
FORBIDDEN_DATA_STORE_ATTRS=(
    "mutations"        # Phase B (B4)
    "file_path"        # Phase C (C4)
    "is_dirty"         # Phase C (C4)
    "is_read_only"     # Phase C (C4)
    "save_format"      # Phase C (C4)
    "undo_stack"       # Phase F (F1-light)
    "schema_source"    # Phase F (F3)
    "schema_ref"       # Phase F (F3)
)

if [[ ${#FORBIDDEN_DATA_STORE_ATTRS[@]} -eq 0 ]]; then
    exit 0
fi

# Build a single alternation: \bdata_store\.(mutations|file_path|...)\b
pattern="\\bdata_store\\.($(IFS='|'; echo "${FORBIDDEN_DATA_STORE_ATTRS[*]}"))\\b"

fail=0
for f in "$@"; do
    [[ -f "$f" ]] || continue
    case "$f" in
        documents/*|tests/*) continue ;;
    esac
    if grep -nE "$pattern" "$f" >/dev/null; then
        echo "ERROR: $f reintroduces a retired data_store leak (see plans/20-decouple-jsontab.md):"
        grep -nE "$pattern" "$f"
        fail=1
    fi
done

exit $fail
