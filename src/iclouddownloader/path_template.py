from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

DEFAULT_DOWNLOAD_PATH_TEMPLATE = "YYYY/MM/DD/{filename}"

# Path segments may use date tokens and/or {filename}
_TOKEN_PATTERN = re.compile(
    r"YYYY|YY|MM|DD|HH|mm|ss|\{filename\}",
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
            "Template must include date tokens (YYYY, MM, DD, …) and/or {filename}"
        )
    return template


def apply_path_template(template: str, dt: datetime, filename: str) -> Path:
    """Build a relative path under the user's download_dir.

    Supported tokens (case-sensitive):
      YYYY — 4-digit year
      YY   — 2-digit year
      MM   — month (01–12)
      DD   — day (01–31)
      HH   — hour (00–23)
      mm   — minute
      ss   — second
      {filename} — original iCloud filename
    """
    template = validate_path_template(template)
    parts = [p for p in template.split("/") if p]

    out: list[str] = []
    has_filename = False
    for part in parts:
        if part == "{filename}":
            out.append(filename)
            has_filename = True
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
