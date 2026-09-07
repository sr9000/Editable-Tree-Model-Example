#!/usr/bin/env bash
# Containerised PyInstaller build for EditableTreeModel.
#
# Builds the Docker image (packaging/docker/Dockerfile) with every dependency
# baked in, then runs PyInstaller inside it against the real source tree
# (bind-mounted READ-ONLY) to produce dist/EditableTreeModel.
#
# Requires a Docker daemon that can bind-mount this checkout — i.e. a local
# daemon or true Docker-in-Docker, not a remote/rootless daemon with a
# different filesystem view.
set -euo pipefail

# Resolve the repo root from this script's own location so it works from any cwd.
SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" >/dev/null 2>&1 && pwd)"
REPO="$(cd -- "$SCRIPT_DIR/../.." >/dev/null 2>&1 && pwd)"

IMAGE=editabletreemodel-build
BINARY="$REPO/dist/EditableTreeModel"

# The image needs pyproject.toml and poetry.lock, which live at the repo root.
# Using the repo root as the build context would ship the whole source tree to
# the daemon and make every source edit invalidate the dependency layer. Stage
# just those two files in a temp dir instead — never inside the repo, so a
# failed run cannot leave copies of the lockfile lying in the working tree.
CTX="$(mktemp -d)"
trap 'rm -rf "$CTX"' EXIT
cp "$REPO/pyproject.toml" "$REPO/poetry.lock" "$CTX/"

docker build -t "$IMAGE" -f "$SCRIPT_DIR/Dockerfile" "$CTX"

mkdir -p "$REPO/dist"

# Record the previous artifact's fingerprint. A stale binary from an earlier
# build satisfies every "is it an ELF, is it big" check, so freshness has to be
# proven rather than assumed — this is the difference between testing the build
# and testing the leftovers.
prev_fingerprint=""
[ -e "$BINARY" ] && prev_fingerprint="$(stat -c '%s:%Y' "$BINARY")"

docker run --rm --user "$(id -u):$(id -g)" \
    -v "$REPO:/src:ro" \
    -v "$REPO/dist:/out" \
    -w /src \
    "$IMAGE" \
    --noconfirm --clean --workpath /tmp/build --distpath /out EditableTreeModel.spec

# --- Verify, without depending on tools that may not be installed ----------
[ -f "$BINARY" ] || { echo "FAIL: $BINARY was not produced" >&2; exit 1; }

new_fingerprint="$(stat -c '%s:%Y' "$BINARY")"
if [ -n "$prev_fingerprint" ] && [ "$new_fingerprint" = "$prev_fingerprint" ]; then
    echo "FAIL: $BINARY is unchanged from before the build — stale artifact, not a fresh build" >&2
    exit 1
fi

# ELF magic (7f 45 4c 46). `file` is not installed everywhere; od is coreutils.
magic="$(od -An -tx1 -N4 "$BINARY" | tr -d ' \n')"
[ "$magic" = "7f454c46" ] || { echo "FAIL: $BINARY is not an ELF binary (magic=$magic)" >&2; exit 1; }

size="$(stat -c %s "$BINARY")"
[ "$size" -gt 20971520 ] || { echo "FAIL: $BINARY is only $size bytes (<20MB)" >&2; exit 1; }

echo "Build complete: $BINARY"
echo "  ELF64 executable, $size bytes ($((size / 1024 / 1024)) MB)"
