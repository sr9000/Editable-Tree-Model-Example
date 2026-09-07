#!/usr/bin/env bash
# Shared guard invoked from .githooks/pre-commit (staged scope) and
# .githooks/pre-commit-ci (whole-tree scope) to forbid imports of the
# concrete ``JsonTab`` class from outside ``documents/``.
#
# External callers must depend on the typed façade
# documents.seams.document_protocol.Document instead of the concrete tab
# widget. Construction goes through documents.composition.factory;
# runtime isinstance checks use documents.composition.marker.JsonTabWidgetMarker.
#
# Tests are exempt: per the same plan §0 rule 8, test reach-in is
# migrated phase-by-phase and the test suite retains full access to
# the concrete class via ``from documents.tab import JsonTab``.
#
# Usage:
#   bash .githooks/_check_jsontab_import_leaks.sh <file> [<file> ...]
# Exits 0 if all listed files are clean, 1 otherwise. Skips files in
# documents/ and tests/.

set -euo pipefail

# Match any import of the bare ``JsonTab`` symbol. ``\bJsonTab\b`` does
# not match ``JsonTabServices`` / ``JsonTabWidgetMarker`` (the trailing
# word boundary fails because the next char is a word char), so those
# legitimate imports are not affected.
patterns=(
    '^[[:space:]]*from[[:space:]]+documents\.tab[[:space:]]+import[[:space:]]+[^#]*\bJsonTab\b'
    '^[[:space:]]*from[[:space:]]+documents\.tab[[:space:]]+import[[:space:]]+\([^)]*\bJsonTab\b'
    '^[[:space:]]*import[[:space:]]+documents\.tab[[:space:]]+as[[:space:]]+'
)

fail=0
for f in "$@"; do
    [[ -f "$f" ]] || continue
    case "$f" in
        documents/*|tests/*) continue ;;
    esac
    for pat in "${patterns[@]}"; do
        if grep -nE "$pat" "$f" >/dev/null; then
            echo "ERROR: $f imports JsonTab from outside documents/:"
            grep -nE "$pat" "$f"
            echo "  Hint: use documents.seams.document_protocol.Document for typing,"
            echo "        documents.composition.factory for construction,"
            echo "        documents.composition.marker.JsonTabWidgetMarker for isinstance."
            fail=1
        fi
    done
done

exit $fail
