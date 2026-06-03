from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated

from pydantic import PlainSerializer


def serialize_api_datetime(value: datetime) -> str:
    """Emit UTC with Z suffix so browsers convert to the viewer's timezone."""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    else:
        value = value.astimezone(timezone.utc)
    return value.strftime("%Y-%m-%dT%H:%M:%SZ")


ApiDateTime = Annotated[datetime, PlainSerializer(serialize_api_datetime)]
