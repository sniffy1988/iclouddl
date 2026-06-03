from __future__ import annotations

from pathlib import Path


def safe_dist_file(web_dist: Path, relative: str) -> Path | None:
    """Resolve a file under web_dist, rejecting path traversal."""
    if not relative or relative.startswith("/"):
        return None
    parts = relative.replace("\\", "/").split("/")
    if ".." in parts:
        return None
    root = web_dist.resolve()
    try:
        target = (root / relative).resolve()
        target.relative_to(root)
    except ValueError:
        return None
    return target if target.is_file() else None
