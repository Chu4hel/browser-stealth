"""Next-generation browser antidetect, human-like behavior emulation, and profile warmer.

Библиотека глубокой маскировки и эмуляции поведения человека для nodriver, Playwright, Selenium и WebDriver BiDi.
"""

from __future__ import annotations

from . import (
    antidetect,
    bidi,
    captcha,
    concurrency,
    connection,
    env,
    fingerprint,
    forms,
    humanize,
    inspect,
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
from .antidetect.flags import (
    UNSUPPORTED_CHROMIUM_FLAGS,
    FlagPolicy,
    UnsupportedFlag,
    UnsupportedFlagRule,
    find_unsupported_flags,
    raise_for_unsupported_flags,
    sanitize_browser_args,
)
from .bidi.client import BiDiClient
from .bidi.session import BiDiSession, bidi_session
from .captcha import (
    CaptchaSnapshot,
    captcha_snapshot,
    capture_captcha_snapshot,
    detect_hh_captcha,
    save_captcha_snapshot,
    wait_for_manual_captcha_resolution,
)
from .connection import (
    check_browser_alive,
    detach_for_restart,
    extract_cdp_endpoint,
    get_browser_main_tab,
    is_browser_connection_error,
    is_ws_closed,
    ping_browser_tab,
)
from .crypto import decrypt_portable, encrypt_portable
from .env import LOCAL_NO_PROXY_HOSTS, ensure_local_no_proxy
from .exceptions import (
    BrowserStealthError,
    InspectionError,
    OptionalDependencyError,
    UnsupportedBrowserFlagError,
)
from .forms import FormQuestion, extract_form_questions, fill_form
from .humanize.actions import (
    TouchGestureGenerator,
    TouchPoint,
    async_click,
    async_human_sleep,
    async_move_mouse,
    async_safe_insert_text,
    async_scroll_to,
    async_touch_swipe,
    async_touch_tap,
    async_type_text,
    click,
    human_sleep,
    move_mouse,
    safe_dom_insert_text,
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
from .inspect import (
    async_find_cascade,
    audit_selectors,
    capture_page_snapshot_mhtml,
    collect_page_failure_context,
)
from .launchers import camoufox, nodriver
from .launchers.camoufox import launch_camoufox
from .launchers.nodriver import (
    cleanup_duplicate_empty_tabs,
    close_tab,
    discover_active_cdp_endpoint,
    discover_browser_executable,
    launch_nodriver,
    nodriver_session,
    resolve_profile_dir,
)
from .profiles.manager import ProfileManager
from .profiles.models import BrowserProfile
from .proxy.models import ProxyConfig, ProxyHealthResult
from .proxy.parser import parse_proxy
from .proxy.pool import ProxyPool

__version__ = "0.4.0"

__all__ = [
    "ANTIDETECT_JS_SCRIPT",
    "LOCAL_NO_PROXY_HOSTS",
    "UNSUPPORTED_CHROMIUM_FLAGS",
    "AntidetectConfig",
    "BehavioralProfile",
    "BezierCurveGenerator",
    "BiDiClient",
    "BiDiSession",
    "BrowserProfile",
    "BrowserStealthError",
    "CaptchaSnapshot",
    "FlagPolicy",
    "FormQuestion",
    "InspectionError",
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
    "UnsupportedBrowserFlagError",
    "UnsupportedFlag",
    "UnsupportedFlagRule",
    "WindMouseGenerator",
    "antidetect",
    "apply_antidetect_nodriver",
    "apply_antidetect_playwright",
    "apply_antidetect_selenium",
    "async_click",
    "async_find_cascade",
    "async_human_sleep",
    "async_move_mouse",
    "async_safe_insert_text",
    "async_scroll_to",
    "async_touch_swipe",
    "async_touch_tap",
    "async_type_text",
    "audit_selectors",
    "bidi",
    "bidi_session",
    "camoufox",
    "captcha",
    "captcha_snapshot",
    "capture_captcha_snapshot",
    "capture_page_snapshot_mhtml",
    "check_browser_alive",
    "cleanup_duplicate_empty_tabs",
    "click",
    "close_tab",
    "collect_page_failure_context",
    "concurrency",
    "connection",
    "decrypt_portable",
    "detach_for_restart",
    "detect_cf_turnstile",
    "detect_hh_captcha",
    "discover_active_cdp_endpoint",
    "discover_browser_executable",
    "encrypt_portable",
    "ensure_local_no_proxy",
    "env",
    "extract_cdp_endpoint",
    "extract_form_questions",
    "fill_form",
    "find_unsupported_flags",
    "fingerprint",
    "forms",
    "get_browser_launch_args",
    "get_browser_main_tab",
    "get_client_hints",
    "human_sleep",
    "humanize",
    "inspect",
    "is_browser_connection_error",
    "is_cf_turnstile_solved",
    "is_ws_closed",
    "launch_camoufox",
    "launch_nodriver",
    "launchers",
    "move_mouse",
    "nodriver",
    "nodriver_session",
    "parse_proxy",
    "ping_browser_tab",
    "profiles",
    "proxy",
    "raise_for_unsupported_flags",
    "resolve_profile_dir",
    "safe_dom_insert_text",
    "sanitize_browser_args",
    "save_captcha_snapshot",
    "scroll_to",
    "solve_cf_turnstile",
    "testing",
    "type_text",
    "wait_for_manual_captcha_resolution",
]
