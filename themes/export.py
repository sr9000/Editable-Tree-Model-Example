"""Copy the embedded built-in themes / icon assets into a writable folder.

This lets the user inspect and customise the themes shipped inside the
frozen application: ``ThemeRegistry`` already scans the user theme folder
on top of the built-ins, so any YAML the user edits there transparently
overrides the built-in of the same name.
"""

from __future__ import annotations

import logging
import shutil
from pathlib import Path

from themes.registry import _find_builtins_dir

LOGGER = logging.getLogger(__name__)


def export_builtins(dest: Path, *, overwrite: bool = False) -> tuple[int, int]:
    """Copy every built-in theme YAML and icon asset to *dest*.

    Layout written to *dest* mirrors ``themes/builtin/``::

        dest/
            light.yaml, dark.yaml, monokai.yaml, ...
            icons/            (per-JsonType icons referenced by theme styles)
            mingcute/         (the full Mingcute icon set)
            mingcute-light/   (referenced by the light themes)
            mingcute-dark/    (referenced by the dark themes)

    The YAMLs use *relative* icon search paths (``./mingcute-light`` etc.),
    so copying the full tree together keeps everything self-contained and
    immediately usable.

    Parameters
    ----------
    dest:
        Target directory.  Created (with parents) if missing.
    overwrite:
        ``False`` (default) leaves existing files alone - calling export
        twice never clobbers user edits.  ``True`` force-refreshes.

    Returns
    -------
    tuple[int, int]
        ``(copied, skipped)`` - files written vs. files left untouched.
    """
    src = _find_builtins_dir()
    if src is None:
        raise FileNotFoundError(
            "Built-in themes directory could not be located; "
            "the application is missing its bundled theme assets."
        )

    dest.mkdir(parents=True, exist_ok=True)
    copied = 0
    skipped = 0
    for source_path in _iter_files(src):
        rel = source_path.relative_to(src)
        # Skip Python package internals that may sit next to the YAMLs.
        if any(part.startswith("__") for part in rel.parts):
            continue
        if rel.suffix == ".pyc":
            continue

        target = dest / rel
        if target.exists() and not overwrite:
            skipped += 1
            continue

        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source_path, target)
        copied += 1

    LOGGER.info("export_builtins -> %s: %d copied, %d skipped", dest, copied, skipped)
    return copied, skipped


def _iter_files(root: Path):
    """Yield every regular file under *root* (recursive, sorted, stable)."""
    for path in sorted(root.rglob("*")):
        if path.is_file():
            yield path
