"""Фабрики быстрого запуска браузеров с встроенным антидетектом."""

from __future__ import annotations

from .camoufox import launch_camoufox
from .nodriver import (
    ChromiumProcessManager,
    cleanup_duplicate_empty_tabs,
    close_tab,
    discover_active_cdp_endpoint,
    launch_nodriver,
    nodriver_session,
    safe_extract_dict,
    safe_get_or_open_tab,
    unpack_cdp_value,
)

__all__ = [
    "ChromiumProcessManager",
    "cleanup_duplicate_empty_tabs",
    "close_tab",
    "discover_active_cdp_endpoint",
    "launch_camoufox",
    "launch_nodriver",
    "nodriver_session",
    "safe_extract_dict",
    "safe_get_or_open_tab",
    "unpack_cdp_value",
]
