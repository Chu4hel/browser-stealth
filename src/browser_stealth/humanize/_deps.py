"""Проверка и импорт опциональных браузерных зависимостей."""

from __future__ import annotations

import importlib.util
import sys
from typing import Any

from browser_stealth.exceptions import OptionalDependencyError


def _ensure_playwright() -> None:
    """Проверяет доступность библиотеки playwright."""
    if "playwright" in sys.modules:
        return
    try:
        if importlib.util.find_spec("playwright") is None:
            raise ImportError()
    except (ImportError, ValueError):
        raise OptionalDependencyError(
            "Модуль 'playwright' не установлен. Для использования Playwright-интеграций "
            "установите его: pip install chutils[scraping] или pip install playwright.",
            dependency="playwright",
            hint="Выполните pip install chutils[scraping] или pip install playwright.",
        )


def _ensure_selenium() -> None:
    """Проверяет доступность библиотеки selenium."""
    if "selenium" in sys.modules:
        return
    try:
        if importlib.util.find_spec("selenium") is None:
            raise ImportError()
    except (ImportError, ValueError):
        raise OptionalDependencyError(
            "Модуль 'selenium' не установлен. Для использования Selenium-интеграций "
            "установите его: pip install chutils[scraping] или pip install selenium.",
            dependency="selenium",
            hint="Выполните pip install chutils[scraping] или pip install selenium.",
        )


def _ensure_nodriver() -> None:
    """Проверяет доступность библиотеки nodriver."""
    if "nodriver" in sys.modules:
        try:
            from unittest.mock import Mock

            is_mock = isinstance(sys.modules["nodriver"], Mock)
        except ImportError:
            is_mock = False
        if not is_mock:
            return
    try:
        if importlib.util.find_spec("nodriver") is None:
            raise ImportError()
    except (ImportError, ValueError):
        raise OptionalDependencyError(
            "Модуль 'nodriver' не установлен. Для использования nodriver-интеграций "
            "установите его в ваше окружение (например, pip install nodriver или uv add nodriver).",
            dependency="nodriver",
            hint="Установите пакет nodriver в ваше окружение (через pip, uv или poetry).",
        )


def _is_nodriver(obj: Any) -> bool:
    """Определяет, является ли переданный объект элементом или вкладкой nodriver."""
    try:
        from unittest.mock import Mock

        is_mock = isinstance(obj, Mock)
    except ImportError:
        is_mock = False

    if is_mock:
        return getattr(obj, "_is_nodriver", False) is True

    return hasattr(obj, "send") and callable(obj.send)


def _is_playwright(obj: Any) -> bool:
    """Определяет, является ли переданный объект страницей Playwright."""
    if obj is None:
        return True
    return not _is_nodriver(obj) and (
        hasattr(obj, "mouse")
        or hasattr(obj, "keyboard")
        or hasattr(obj, "evaluate")
        or hasattr(obj, "focus")
    )
