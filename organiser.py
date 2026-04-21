"""
organiser.py
------------
Handles all filesystem operations: moving PDFs into their classified folders,
resolving filename collisions, and routing failed files to an _errors folder.
"""

import logging
import shutil
from pathlib import Path

logger = logging.getLogger(__name__)


class OrganiserError(Exception):
    """Raised when a file cannot be moved for filesystem-level reasons."""


def organise_pdf(src_path: str | Path, base_output_dir: str | Path, relative_folder: str) -> Path:
    """
    Move a PDF from src_path into <base_output_dir>/<relative_folder>/.

    Behaviour:
        - Creates the destination folder tree if it doesn't exist (no error if already there).
        - If the exact filename already exists at the destination, appends _1, _2, … until unique.
        - Returns the final destination Path.

    Args:
        src_path:        Path to the source PDF.
        base_output_dir: Root output directory (e.g. './organised').
        relative_folder: Subfolder path returned by the classifier (e.g. 'Exams/Civil_Services').

    Raises:
        OrganiserError — if the source file doesn't exist or the move fails.
    """
    src  = Path(src_path)
    dest_dir = Path(base_output_dir) / relative_folder

    if not src.exists():
        raise OrganiserError(f"Source file not found: {src}")

    # exist_ok=True: no exception if the folder was already created by a previous run
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise OrganiserError(f"Cannot create destination directory '{dest_dir}': {exc}") from exc

    dest = _resolve_collision(dest_dir / src.name)

    try:
        shutil.move(str(src), str(dest))
        logger.info("Moved  %-55s  →  %s", src.name, dest)
        return dest
    except (shutil.Error, OSError) as exc:
        raise OrganiserError(f"Failed to move '{src}' to '{dest}': {exc}") from exc


def move_to_error(src_path: str | Path, base_output_dir: str | Path, reason: str) -> Path | None:
    """
    Move a PDF that failed processing into <base_output_dir>/_errors/<reason>/.
    Reason string is sanitised to be filesystem-safe (max 40 chars).

    Returns the destination path, or None if even the error move failed.
    """
    import re
    safe_reason = re.sub(r"[^\w-]", "_", reason)[:40] or "unknown"

    try:
        dest = organise_pdf(src_path, base_output_dir, f"_errors/{safe_reason}")
        logger.warning("Error file moved to: %s", dest)
        return dest
    except OrganiserError as exc:
        logger.error("Could not move error file '%s': %s", src_path, exc)
        return None


# ── Internal helpers ──────────────────────────────────────────────────────────

def _resolve_collision(dest: Path) -> Path:
    """
    If dest already exists, append _1, _2, … to the stem until the path is free.

    Example:
        report.pdf  →  report_1.pdf  →  report_2.pdf  …
    """
    if not dest.exists():
        return dest

    stem, suffix, parent = dest.stem, dest.suffix, dest.parent
    counter = 1
    candidate = dest
    while candidate.exists():
        candidate = parent / f"{stem}_{counter}{suffix}"
        counter += 1

    logger.debug("Collision resolved: '%s' → '%s'", dest.name, candidate.name)
    return candidate
