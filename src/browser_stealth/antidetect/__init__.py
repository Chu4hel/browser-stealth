"""Подсистема антидетекта и маскировки браузерных сред."""

from __future__ import annotations

from .clipboard import (
    GET_COPIED_CLIPBOARD_JS,
    INSTALL_CLIPBOARD_HOOK_JS,
    apply_clipboard_isolation,
    get_isolated_clipboard_text,
)
from .config import AntidetectConfig
from .core import (
    ANTIDETECT_JS_SCRIPT,
    _ensure_nodriver,
    _ensure_playwright,
    _ensure_selenium,
    apply_antidetect_nodriver,
    apply_antidetect_playwright,
    apply_antidetect_selenium,
    extract_clearance_cookies,
    get_browser_launch_args,
    get_client_hints,
)
from .flags import (
    UNSUPPORTED_CHROMIUM_FLAGS,
    FlagPolicy,
    UnsupportedFlag,
    UnsupportedFlagRule,
    find_unsupported_flags,
    raise_for_unsupported_flags,
    sanitize_browser_args,
)
from .scripts import (
    DEFAULT_DEVICE_MEMORY,
    DEFAULT_HARDWARE_CONCURRENCY,
    DEFAULT_WEBGL_RENDERER,
    DEFAULT_WEBGL_VENDOR,
    _get_antidetect_js,
)

__all__ = [
    "ANTIDETECT_JS_SCRIPT",
    "DEFAULT_DEVICE_MEMORY",
    "DEFAULT_HARDWARE_CONCURRENCY",
    "DEFAULT_WEBGL_RENDERER",
    "DEFAULT_WEBGL_VENDOR",
    "GET_COPIED_CLIPBOARD_JS",
    "INSTALL_CLIPBOARD_HOOK_JS",
    "UNSUPPORTED_CHROMIUM_FLAGS",
    "AntidetectConfig",
    "FlagPolicy",
    "UnsupportedFlag",
    "UnsupportedFlagRule",
    "_ensure_nodriver",
    "_ensure_playwright",
    "_ensure_selenium",
    "_get_antidetect_js",
    "apply_antidetect_nodriver",
    "apply_antidetect_playwright",
    "apply_antidetect_selenium",
    "apply_clipboard_isolation",
    "extract_clearance_cookies",
    "find_unsupported_flags",
    "get_browser_launch_args",
    "get_client_hints",
    "get_isolated_clipboard_text",
    "raise_for_unsupported_flags",
    "sanitize_browser_args",
]
