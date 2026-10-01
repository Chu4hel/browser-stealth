"""Next-generation browser antidetect, human-like behavior emulation, and profile warmer.

Библиотека глубокой маскировки и эмуляции поведения человека для nodriver, Playwright, Selenium и WebDriver BiDi.
"""

from __future__ import annotations

from . import (
    antidetect,
    bidi,
    concurrency,
    fingerprint,
    humanize,
    launchers,
    profiles,
    proxy,
    testing,
)
from .antidetect.config import AntidetectConfig
from .antidetect.core import (
    ANTIDETECT_JS_SCRIPT,
    apply_antidetect_nodriver,
    apply_antidetect_playwright,
    apply_antidetect_selenium,
    get_browser_launch_args,
    get_client_hints,
)
from .bidi.client import BiDiClient
from .bidi.session import BiDiSession, bidi_session
from .exceptions import BrowserStealthError, OptionalDependencyError
from .humanize.actions import (
    TouchGestureGenerator,
    TouchPoint,
    async_click,
    async_human_sleep,
    async_move_mouse,
    async_scroll_to,
    async_touch_swipe,
    async_touch_tap,
    async_type_text,
    click,
    human_sleep,
    move_mouse,
    scroll_to,
    type_text,
)
from .humanize.behavior import BehavioralProfile
from .humanize.math_utils import (
    BezierCurveGenerator,
    JitterDelayGenerator,
    KeyboardTypoGenerator,
    WindMouseGenerator,
)
from .humanize.turnstile import (
    detect_cf_turnstile,
    is_cf_turnstile_solved,
    solve_cf_turnstile,
)
from .humanize.warmer import ProfileWarmer, SyncProfileWarmer
from .launchers import camoufox, nodriver
from .launchers.nodriver import launch_nodriver
from .profiles.manager import ProfileManager
from .profiles.models import BrowserProfile
from .proxy.models import ProxyConfig, ProxyHealthResult
from .proxy.parser import parse_proxy
from .proxy.pool import ProxyPool

__version__ = "0.1.0"

__all__ = [
    "ANTIDETECT_JS_SCRIPT",
    "AntidetectConfig",
    "BehavioralProfile",
    "BezierCurveGenerator",
    "BiDiClient",
    "BiDiSession",
    "BrowserProfile",
    "BrowserStealthError",
    "JitterDelayGenerator",
    "KeyboardTypoGenerator",
    "OptionalDependencyError",
    "ProfileManager",
    "ProfileWarmer",
    "ProxyConfig",
    "ProxyHealthResult",
    "ProxyPool",
    "SyncProfileWarmer",
    "TouchGestureGenerator",
    "TouchPoint",
    "WindMouseGenerator",
    "antidetect",
    "apply_antidetect_nodriver",
    "apply_antidetect_playwright",
    "apply_antidetect_selenium",
    "async_click",
    "async_human_sleep",
    "async_move_mouse",
    "async_scroll_to",
    "async_touch_swipe",
    "async_touch_tap",
    "async_type_text",
    "bidi",
    "bidi_session",
    "camoufox",
    "click",
    "concurrency",
    "detect_cf_turnstile",
    "fingerprint",
    "get_browser_launch_args",
    "get_client_hints",
    "human_sleep",
    "humanize",
    "is_cf_turnstile_solved",
    "launch_nodriver",
    "launchers",
    "move_mouse",
    "nodriver",
    "parse_proxy",
    "profiles",
    "proxy",
    "scroll_to",
    "solve_cf_turnstile",
    "testing",
    "type_text",
]
