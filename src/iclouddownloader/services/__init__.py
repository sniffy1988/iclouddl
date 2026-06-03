"""Service layer — import submodules directly (e.g. sync_service.SyncService)."""

from __future__ import annotations

import importlib
from typing import Any

__all__ = ["AuthService", "SyncService", "UserService"]


def __getattr__(name: str) -> Any:
    if name == "AuthService":
        return importlib.import_module("iclouddownloader.services.auth_service").AuthService
    if name == "SyncService":
        return importlib.import_module("iclouddownloader.services.sync_service").SyncService
    if name == "UserService":
        return importlib.import_module("iclouddownloader.services.user_service").UserService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
