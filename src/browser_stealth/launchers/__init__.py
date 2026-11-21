"""Фабрики быстрого запуска браузеров с встроенным антидетектом."""

from __future__ import annotations

from ._browser_paths import discover_browser_executable, resolve_profile_dir
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
    "discover_browser_executable",
    "launch_camoufox",
    "launch_nodriver",
    "nodriver_session",
    "resolve_profile_dir",
    "safe_extract_dict",
    "safe_get_or_open_tab",
    "unpack_cdp_value",
]
