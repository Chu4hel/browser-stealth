"""Подсистема кроссбраузерного управления и антидетекта через WebDriver BiDi."""

from __future__ import annotations

from browser_stealth.bidi.antidetect import apply_antidetect_bidi
from browser_stealth.bidi.client import BiDiClient
from browser_stealth.bidi.exceptions import (
    BiDiCommandError,
    BiDiConnectionError,
    BiDiError,
    BiDiTimeoutError,
)
from browser_stealth.bidi.session import BiDiSession, bidi_session, extract_bidi_url

__all__ = [
    "BiDiClient",
    "BiDiCommandError",
    "BiDiConnectionError",
    "BiDiError",
    "BiDiSession",
    "BiDiTimeoutError",
    "apply_antidetect_bidi",
    "bidi_session",
    "extract_bidi_url",
]
