from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

DEFAULT_DOWNLOAD_PATH_TEMPLATE = "YYYY/MM/DD/{filename}"

_TOKEN_PATTERN = re.compile(
    r"YYYY|YY|MM|DD|HH|mm|ss|\{filename\}|\{source\}",
    re.IGNORECASE,
)


def validate_path_template(template: str) -> str:
    template = template.strip().replace("\\", "/")
    if not template:
        raise ValueError("Path template cannot be empty")
    if ".." in template.split("/"):
        raise ValueError("Path template cannot contain '..'")
    if not _TOKEN_PATTERN.search(template):
        raise ValueError(
            "Template must include date tokens (YYYY, MM, DD, …), {source}, and/or {filename}"
        )
    return template


def apply_path_template(
    template: str,
    dt: datetime,
    filename: str,
    *,
    source: str | None = None,
) -> Path:
    """Build a relative path under the user's download_dir."""
    template = validate_path_template(template)
    parts = [p for p in template.split("/") if p]

    out: list[str] = []
    has_filename = False
    for part in parts:
        if part == "{filename}":
            out.append(filename)
            has_filename = True
            continue
        if part == "{source}":
            if source:
                out.append(source)
            continue
        segment = (
            part.replace("YYYY", f"{dt.year:04d}")
            .replace("YY", f"{dt.year % 100:02d}")
            .replace("MM", f"{dt.month:02d}")
            .replace("DD", f"{dt.day:02d}")
            .replace("HH", f"{dt.hour:02d}")
            .replace("mm", f"{dt.minute:02d}")
            .replace("ss", f"{dt.second:02d}")
        )
        out.append(segment)

    if not has_filename:
        out.append(filename)

    return Path(*out)
