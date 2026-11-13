"""Менеджер пула сессионных вкладок браузера (SessionTabPool / TabSession).

Обеспечивает изоляцию контекста между независимыми клиентами/сессиями
через привязку сессий к отдельным вкладкам браузера с поддержкой
LRU-вытеснения, очистки по TTL и предотвращения утечек ресурсов.
"""

from __future__ import annotations

import asyncio
import inspect
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any

from browser_stealth.launchers.nodriver import close_tab as _default_close_tab
from browser_stealth.logging import get_logger as setup_logger

logger = setup_logger(__name__)


@dataclass
class TabSession:
    """Метаданные активной сессии вкладки браузера."""

    session_id: str
    tab: Any
    created_at: float = field(default_factory=time.time)
    last_used_at: float = field(default_factory=time.time)
    request_count: int = 0
    message_count: int = 0


class SessionTabPool:
    """Оркестратор пула вкладок браузера с привязкой к сессиям, LRU-вытеснением и TTL."""

    def __init__(
        self,
        max_tabs: int = 5,
        session_ttl_seconds: float = 600.0,
        close_tab_fn: Callable[[Any], Awaitable[None]] | None = None,
    ) -> None:
        """Инициализирует менеджер пула сессионных вкладок.

        Args:
            max_tabs: Максимальное количество одновременно открытых сессионных вкладок.
            session_ttl_seconds: Время жизни неактивной сессии в секундах до закрытия по TTL.
            close_tab_fn: Пользовательская асинхронная функция безопасного закрытия вкладки.
        """
        self.max_tabs = max_tabs
        self.session_ttl_seconds = session_ttl_seconds
        self._close_tab_fn = close_tab_fn or _default_close_tab
        self._sessions: dict[str, TabSession] = {}
        self._lock = asyncio.Lock()

    @property
    def active_session_count(self) -> int:
        """Количество активных сессий в пуле."""
        return len(self._sessions)

    def get_session(self, session_id: str) -> TabSession | None:
        """Возвращает метаданные сессии по ID без изменения счетчиков.

        Args:
            session_id: Идентификатор сессии.

        Returns:
            Метаданные сессии TabSession или None, если сессия не зарегистрирована.
        """
        return self._sessions.get(session_id)

    def list_session_ids(self) -> list[str]:
        """Возвращает список идентификаторов всех зарегистрированных сессий.

        Returns:
            Список строковых идентификаторов сессий.
        """
        return list(self._sessions.keys())

    async def is_tab_alive(self, tab: Any) -> bool:
        """Проверяет, доступна ли еще вкладка в браузере (не закрыта ли она).

        Args:
            tab: Объект вкладки.

        Returns:
            True, если вкладка отвечает на команды, иначе False.
        """
        if tab is None:
            return False
        try:
            if hasattr(tab, "evaluate") and callable(tab.evaluate):
                res = tab.evaluate("1 + 1")
                if inspect.isawaitable(res):
                    res = await res
                return bool(res == 2)
            return True
        except Exception:
            return False

    async def _safe_close_tab(self, tab: Any) -> None:
        """Безопасно закрывает вкладку через настроенный обработчик."""
        try:
            res = self._close_tab_fn(tab)
            if inspect.isawaitable(res):
                await res
        except Exception as exc:
            logger.debug("Ошибка при закрытии вкладки сессии: %s", exc)

    async def get_or_create_tab(
        self,
        browser: Any,
        session_id: str,
        default_tab: Any = None,
        target_url: str | None = None,
        tab_factory: Callable[[str], Awaitable[Any]] | None = None,
        on_tab_created: Callable[[Any], Awaitable[None]] | None = None,
    ) -> tuple[Any, bool]:
        """Возвращает существующую вкладку для session_id или создает новую с соблюдением лимитов.

        Args:
            browser: Экземпляр браузера (nodriver.Browser или Playwright context).
            session_id: Уникальный идентификатор клиентской сессии.
            default_tab: Основная дефолтная вкладка (защищена от закрытия при очистке сирот).
            target_url: Стартовый URL новой вкладки.
            tab_factory: Опциональная кастомная фабрика создания новой вкладки.
            on_tab_created: Асинхронный хук инициализации после создания вкладки (например, антидетект).

        Returns:
            Кортеж (tab, is_new_tab).
        """
        async with self._lock:
            # 1. Проверяем наличие существующей вкладки
            existing = self._sessions.get(session_id)
            if existing is not None:
                if await self.is_tab_alive(existing.tab):
                    existing.last_used_at = time.time()
                    existing.request_count += 1
                    logger.debug(
                        "Использование существующей вкладки для сессии '%s' (запросов: %d)",
                        session_id,
                        existing.request_count,
                    )
                    return existing.tab, False
                logger.info("Вкладка сессии '%s' была закрыта, пересоздание...", session_id)
                self._sessions.pop(session_id, None)

            # 2. Очистка устаревших сессий по TTL
            now = time.time()
            expired_keys = [
                k
                for k, s in self._sessions.items()
                if now - s.last_used_at > self.session_ttl_seconds
            ]
            for exp_k in expired_keys:
                exp_s = self._sessions.pop(exp_k, None)
                if exp_s:
                    logger.info("Сессия '%s' устарела по TTL, закрытие вкладки...", exp_k)
                    await self._safe_close_tab(exp_s.tab)

            # 3. Закрытие осиротевших вкладок браузера (если список доступен)
            browser_tabs = getattr(browser, "tabs", None)
            if isinstance(browser_tabs, list):
                active_session_tab_ids = {id(s.tab) for s in self._sessions.values()}
                for extra_tab in list(browser_tabs):
                    if (
                        extra_tab is not default_tab
                        and id(extra_tab) not in active_session_tab_ids
                        and hasattr(extra_tab, "close")
                    ):
                        try:
                            logger.debug("Закрытие осиротевшей вкладки браузера: %s", extra_tab)
                            await self._safe_close_tab(extra_tab)
                        except Exception:
                            pass

            # 4. LRU-вытеснение старейшей сессии при превышении лимита
            while self._sessions and (
                len(self._sessions) >= self.max_tabs
                or (isinstance(browser_tabs, list) and len(browser_tabs) >= self.max_tabs)
            ):
                oldest_key = min(
                    self._sessions.keys(), key=lambda k: self._sessions[k].last_used_at
                )
                oldest_session = self._sessions.pop(oldest_key)
                logger.info(
                    "Лимит вкладок (%d) достигнут. LRU-вытеснение сессии '%s'...",
                    self.max_tabs,
                    oldest_key,
                )
                await self._safe_close_tab(oldest_session.tab)

            # 5. Создание новой изолированной вкладки
            logger.info("Создание новой вкладки для сессии '%s'...", session_id)
            if tab_factory is not None:
                new_tab = await tab_factory(session_id)
            elif hasattr(browser, "get") and callable(browser.get):
                # nodriver
                new_tab = await browser.get(target_url or "about:blank", new_tab=True)
            elif hasattr(browser, "new_page") and callable(browser.new_page):
                # Playwright
                new_tab = await browser.new_page()
                if target_url:
                    await new_tab.goto(target_url)
            else:
                raise RuntimeError(
                    f"Не удалось определить способ открытия новой вкладки в объекте {browser!r}"
                )

            if on_tab_created is not None:
                await on_tab_created(new_tab)

            session = TabSession(
                session_id=session_id,
                tab=new_tab,
                created_at=now,
                last_used_at=now,
                request_count=1,
                message_count=0,
            )
            self._sessions[session_id] = session
            return new_tab, True

    async def close_session(self, session_id: str) -> bool:
        """Закрывает конкретную сессию и ее вкладку браузера.

        Args:
            session_id: Идентификатор закрываемой сессии.

        Returns:
            True, если сессия найдена и закрыта, иначе False.
        """
        async with self._lock:
            session = self._sessions.pop(session_id, None)
            if session:
                await self._safe_close_tab(session.tab)
                return True
            return False

    async def close_all_sessions(self) -> None:
        """Закрывает все открытые сессионные вкладки."""
        async with self._lock:
            for session in list(self._sessions.values()):
                await self._safe_close_tab(session.tab)
            self._sessions.clear()


__all__ = [
    "SessionTabPool",
    "TabSession",
]
