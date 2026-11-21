"""Работа с вкладками nodriver: закрытие, выбор основной и безопасная навигация."""

from __future__ import annotations

import asyncio
import inspect
import time
from typing import Any

from browser_stealth.logging import get_logger

logger = get_logger(__name__)

_EMPTY_TAB_URLS = frozenset(
    {
        "",
        "about:blank",
        "chrome://newtab",
        "chrome://new-tab-page",
        "data:,",
    }
)


async def close_tab(tab: Any, *, timeout: float = 3.0) -> None:
    """Безопасно закрывает вкладку nodriver с защитой от зависания CDP-сокета.

    Если вкладка потерпела крах (Renderer Crash) или CDP не отвечает,
    операция прерывается по истечении таймаута без зависания вызывающего потока.

    Args:
        tab: Объект вкладки nodriver (nodriver.Tab).
        timeout: Максимальное время ожидания закрытия вкладки в секундах.
    """
    close_method = getattr(tab, "close", None)
    if callable(close_method):
        res = close_method()
        if inspect.isawaitable(res):
            try:
                await asyncio.wait_for(res, timeout=timeout)
            except TimeoutError:
                logger.debug(
                    f"Таймаут ({timeout}с) при закрытии вкладки nodriver, принудительное завершение."
                )
            except Exception as exc:
                logger.debug(f"Ошибка при закрытии вкладки nodriver: {exc}")


def _tab_url(tab: Any) -> str:
    """Возвращает URL вкладки nodriver без учёта регистра и якоря.

    Args:
        tab: Объект вкладки nodriver.

    Returns:
        URL вкладки или пустая строка, если его не удалось определить.
    """
    target = getattr(tab, "target", None)
    url = getattr(target, "url", None)
    if not isinstance(url, str):
        try:
            url = getattr(tab, "url", None)
        except Exception:
            url = None
    return url.strip() if isinstance(url, str) else ""


def _is_empty_tab(tab: Any) -> bool:
    """Проверяет, является ли вкладка пустой/new-tab страницей.

    Args:
        tab: Объект вкладки nodriver.

    Returns:
        True, если вкладка не содержит рабочей страницы.
    """
    normalized = _tab_url(tab).lower()
    if not normalized:
        return True
    base_url = normalized.split("#", 1)[0].split("?", 1)[0].rstrip("/")
    return base_url in _EMPTY_TAB_URLS


def _pick_primary_tab(browser: Any, page_tabs: list[Any] | None = None) -> Any | None:
    """Выбирает вкладку, которую нужно оставить основной.

    Предпочитает непустую ``main_tab``, затем первую непустую вкладку. Если
    рабочих страниц нет, возвращает ``main_tab`` или первую доступную.

    Args:
        browser: Экземпляр nodriver.Browser.
        page_tabs: Заранее отфильтрованный список вкладок.

    Returns:
        Основная вкладка или None, если вкладок нет.
    """
    if page_tabs is None:
        tabs = getattr(browser, "tabs", None)
        if not isinstance(tabs, (list, tuple)):
            return None
        page_tabs = [tab for tab in tabs if callable(getattr(tab, "close", None))]
    if not page_tabs:
        return None

    main_tab = getattr(browser, "main_tab", None)
    if main_tab in page_tabs and not _is_empty_tab(main_tab):
        return main_tab
    for tab in page_tabs:
        if not _is_empty_tab(tab):
            return tab
    return main_tab if main_tab in page_tabs else page_tabs[0]


async def cleanup_duplicate_empty_tabs(
    browser: Any,
    *,
    keep_tab: Any | None = None,
    timeout: float = 3.0,
) -> int:
    """Закрывает лишние пустые вкладки, оставляя основную рабочую страницу.

    Пустыми считаются ``about:blank``, ``chrome://newtab``,
    ``chrome://new-tab-page`` и вкладки без определённого URL. Непустые
    вкладки не закрываются.

    Args:
        browser: Экземпляр nodriver.Browser.
        keep_tab: Вкладка, которую нужно сохранить принудительно.
        timeout: Таймаут закрытия каждой вкладки в секундах.

    Returns:
        Количество закрытых лишних вкладок.
    """
    tabs = getattr(browser, "tabs", None)
    if not isinstance(tabs, (list, tuple)):
        return 0

    page_tabs = [tab for tab in tabs if callable(getattr(tab, "close", None))]
    if len(page_tabs) <= 1:
        return 0

    if keep_tab not in page_tabs:
        keep_tab = None
    if keep_tab is None:
        keep_tab = _pick_primary_tab(browser, page_tabs)

    closed = 0
    for tab in page_tabs:
        if tab is keep_tab or not _is_empty_tab(tab):
            continue
        await close_tab(tab, timeout=timeout)
        closed += 1

    if closed:
        logger.info("Закрыто %d пустых вкладок Chromium", closed)
        updater = getattr(browser, "update_targets", None)
        if callable(updater):
            result = updater()
            if inspect.isawaitable(result):
                await result

    return closed


async def safe_get_or_open_tab(
    browser: Any,
    url: str,
    timeout: float = 10.0,
) -> Any:
    """Безопасно переходит по URL или открывает новую вкладку с защитой от race conditions nodriver.

    Предотвращает RuntimeError('coroutine raised StopIteration'), возникающий в nodriver,
    когда browser.get(new_tab=False) вызывается до момента регистрации начального page target.

    Args:
        browser: Экземпляр nodriver Browser.
        url: Целевой URL веб-страницы.
        timeout: Таймаут ожидания появления открытой страницы (сек).

    Returns:
        Объект активной вкладки Tab.
    """
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            if hasattr(browser, "update_targets") and callable(browser.update_targets):
                res_upd = browser.update_targets()
                if inspect.isawaitable(res_upd):
                    await res_upd
            targets = getattr(browser, "targets", None)
            if isinstance(targets, list):
                page_tabs = [
                    t
                    for t in targets
                    if getattr(getattr(t, "target", None), "type_", None) == "page"
                ]
                if page_tabs:
                    break
            elif targets is not None:
                break
        except Exception:
            pass
        await asyncio.sleep(0.15)

    try:
        return await browser.get(url)
    except (StopIteration, RuntimeError, Exception) as exc:
        if "StopIteration" in str(exc) or isinstance(exc, StopIteration):
            logger.warning(
                "nodriver browser.get() вызвал ошибку race condition (%s), принудительно открываем через new_tab=True...",
                exc,
            )
            return await browser.get(url, new_tab=True)
        raise


__all__ = [
    "cleanup_duplicate_empty_tabs",
    "close_tab",
    "safe_get_or_open_tab",
]
