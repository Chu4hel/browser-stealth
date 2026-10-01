"""Инициализация пакета профилей браузеров."""

from browser_stealth.profiles.hygiene import (
    is_profile_locked,
    sanitize_profile,
    sanitize_profile_crash_state,
)
from browser_stealth.profiles.manager import ProfileManager
from browser_stealth.profiles.models import (
    BrowserProfile,
    CookieData,
    HeaderData,
    StorageData,
)
from browser_stealth.profiles.storage import (
    load_profile_from_file,
    save_profile_to_file,
)

__all__ = [
    "BrowserProfile",
    "CookieData",
    "HeaderData",
    "ProfileManager",
    "StorageData",
    "is_profile_locked",
    "load_profile_from_file",
    "sanitize_profile",
    "sanitize_profile_crash_state",
    "save_profile_to_file",
]
