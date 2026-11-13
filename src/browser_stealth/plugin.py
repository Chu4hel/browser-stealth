"""Плагин глубокой маскировки для интеграции с chutils.plugins."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.antidetect.core import (
    apply_antidetect_nodriver,
    apply_antidetect_playwright,
    apply_antidetect_selenium,
)

try:
    from chutils.plugins.interfaces import BrowserStealthPlugin as _ChutilsPluginInterface
except ImportError:
    _ChutilsPluginInterface = None


class BrowserStealthPlugin(ABC):
    """Типизированный интерфейс плагина глубокой маскировки браузера.

    Совпадает по контракту с chutils.plugins.interfaces.BrowserStealthPlugin;
    при наличии chutils реализация регистрируется в его ABC, поэтому
    issubclass/isinstance продолжают работать без наследования от untyped-класса.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Уникальное имя плагина.

        Returns:
            Строковый идентификатор плагина.
        """

    @abstractmethod
    def apply_playwright(self, context: Any, **kwargs: Any) -> None:
        """Применяет стелс-патчи к Playwright.

        Args:
            context: Объект BrowserContext или Page Playwright.
            **kwargs: Дополнительные параметры конфигурации маскировки.
        """

    @abstractmethod
    def apply_selenium(self, driver: Any, **kwargs: Any) -> None:
        """Применяет стелс-патчи к Selenium WebDriver.

        Args:
            driver: Экземпляр Selenium WebDriver.
            **kwargs: Дополнительные параметры конфигурации маскировки.
        """

    @abstractmethod
    def apply_nodriver(self, tab: Any, **kwargs: Any) -> None:
        """Применяет стелс-патчи к nodriver Tab.

        Args:
            tab: Вкладка nodriver Tab.
            **kwargs: Дополнительные параметры конфигурации маскировки.
        """


class BrowserStealthPluginImpl(BrowserStealthPlugin):
    """Реализация плагина браузерного антидетекта для chutils."""

    @property
    def name(self) -> str:
        """Уникальное имя плагина."""
        return "browser_stealth"

    def apply_playwright(self, context: Any, **kwargs: Any) -> None:
        """Применяет расширенные стелс-патчи к Playwright.

        Args:
            context: Объект BrowserContext или Page Playwright.
            **kwargs: Готовый AntidetectConfig в ключе config либо параметры для его создания.
        """
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
        """Применяет расширенные стелс-патчи к Selenium WebDriver.

        Args:
            driver: Экземпляр Selenium WebDriver.
            **kwargs: Готовый AntidetectConfig в ключе config либо параметры для его создания.
        """
        config = kwargs.get("config")
        if config is None:
            config = AntidetectConfig(**kwargs) if kwargs else AntidetectConfig.preset_minimal()
        apply_antidetect_selenium(driver, config=config)

    def apply_nodriver(self, tab: Any, **kwargs: Any) -> None:
        """Применяет расширенные стелс-патчи к nodriver Tab.

        Args:
            tab: Вкладка nodriver Tab.
            **kwargs: Готовый AntidetectConfig в ключе config либо параметры для его создания.
        """
        config = kwargs.get("config")
        if config is None:
            config = (
                AntidetectConfig(**kwargs) if kwargs else AntidetectConfig.preset_stealth_nodriver()
            )
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            loop.create_task(apply_antidetect_nodriver(tab, config=config))
        else:
            asyncio.run(apply_antidetect_nodriver(tab, config=config))


if _ChutilsPluginInterface is not None:
    # Виртуальная регистрация в ABC chutils: issubclass/isinstance работают
    # без наследования от untyped-модуля.
    _ChutilsPluginInterface.register(BrowserStealthPluginImpl)
