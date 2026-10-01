"""Реэкспорт скриптов антидетекта из browser_stealth.antidetect.scripts."""

from browser_stealth.antidetect.scripts import *
from browser_stealth.antidetect.scripts import (
    DEFAULT_DEVICE_MEMORY,
    DEFAULT_HARDWARE_CONCURRENCY,
    DEFAULT_WEBGL_RENDERER,
    DEFAULT_WEBGL_VENDOR,
    _get_antidetect_js,
)

__all__ = [
    "DEFAULT_DEVICE_MEMORY",
    "DEFAULT_HARDWARE_CONCURRENCY",
    "DEFAULT_WEBGL_RENDERER",
    "DEFAULT_WEBGL_VENDOR",
    "_get_antidetect_js",
]
