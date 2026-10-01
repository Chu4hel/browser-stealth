"""Реэкспорт функционала антидетекта из browser_stealth.antidetect.core."""

from browser_stealth.antidetect.core import *
from browser_stealth.antidetect.core import (
    ANTIDETECT_JS_SCRIPT,
    apply_antidetect_nodriver,
    apply_antidetect_playwright,
    apply_antidetect_selenium,
    get_browser_launch_args,
    get_client_hints,
)

__all__ = [
    "ANTIDETECT_JS_SCRIPT",
    "apply_antidetect_nodriver",
    "apply_antidetect_playwright",
    "apply_antidetect_selenium",
    "get_browser_launch_args",
    "get_client_hints",
]
