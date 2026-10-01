"""Плагин глубокой маскировки для интеграции с chutils.plugins."""

from __future__ import annotations

import asyncio
from typing import Any

try:
    from chutils.plugins.interfaces import BrowserStealthPlugin
except ImportError:
    class BrowserStealthPlugin:  # type: ignore[no-redef]
        """Fallback интерфейс BasePlugin."""

from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.antidetect.core import (
    apply_antidetect_nodriver,
    apply_antidetect_playwright,
    apply_antidetect_selenium,
)


class BrowserStealthPluginImpl(BrowserStealthPlugin):
    """Реализация плагина браузерного антидетекта для chutils."""

    @property
    def name(self) -> str:
        """Уникальное имя плагина."""
        return "browser_stealth"

    def apply_playwright(self, context: Any, **kwargs: Any) -> None:
        """Применяет расширенные стелс-патчи к Playwright."""
        config = kwargs.get("config")
        if config is None:
            config = AntidetectConfig(**kwargs) if kwargs else AntidetectConfig.preset_minimal()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(apply_antidetect_playwright(context, config=config))
        else:
            asyncio.run(apply_antidetect_playwright(context, config=config))

    def apply_selenium(self, driver: Any, **kwargs: Any) -> None:
        """Применяет расширенные стелс-патчи к Selenium WebDriver."""
        config = kwargs.get("config")
        if config is None:
            config = AntidetectConfig(**kwargs) if kwargs else AntidetectConfig.preset_minimal()
        apply_antidetect_selenium(driver, config=config)

    def apply_nodriver(self, tab: Any, **kwargs: Any) -> None:
        """Применяет расширенные стелс-патчи к nodriver Tab."""
        config = kwargs.get("config")
        if config is None:
            config = AntidetectConfig(**kwargs) if kwargs else AntidetectConfig.preset_stealth_nodriver()
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(apply_antidetect_nodriver(tab, config=config))
        else:
            asyncio.run(apply_antidetect_nodriver(tab, config=config))
