"""Подсистема антидетекта и маскировки браузерных сред."""

from __future__ import annotations

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
    "AntidetectConfig",
    "_ensure_nodriver",
    "_ensure_playwright",
    "_ensure_selenium",
    "_get_antidetect_js",
    "apply_antidetect_nodriver",
    "apply_antidetect_playwright",
    "apply_antidetect_selenium",
    "extract_clearance_cookies",
    "get_browser_launch_args",
    "get_client_hints",
]
