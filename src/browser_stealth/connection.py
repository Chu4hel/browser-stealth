"""Диагностика сокетов, процессов и состояния соединения с браузером.

Модуль помогает отличить живое CDP-подключение от закрытого окна или
разорванного WebSocket. Это особенно важно для браузеров, подключённых к
внешнему Chromium: у них ``browser._process is None``, а ``browser.stopped``
в nodriver возвращает True даже при рабочем соединении.
"""

from __future__ import annotations

import asyncio
import inspect
from typing import Any
from urllib.parse import urlparse

from browser_stealth.logging import get_logger

logger = get_logger(__name__)

BROWSER_DETACHED_ATTR = "_browser_stealth_detached"


def is_browser_connection_error(exc: BaseException) -> bool:
    """Определяет, вызвано ли исключение разрывом связи с браузером.

    Args:
        exc: Проверяемое исключение.

    Returns:
        True, если ошибка указывает на закрытие процесса или WebSocket Chromium.
    """
    if isinstance(
        exc,
        (
            ConnectionError,
            ConnectionResetError,
            ConnectionRefusedError,
            ConnectionAbortedError,
            BrokenPipeError,
        ),
    ):
        return True

    if "ConnectionClosed" in type(exc).__name__:
        return True

    message = str(exc).lower()
    markers = (
        "no close frame received or sent",
        "websocket is not connected",
        "connection closed",
        "connection is closed",
        "closed websocket",
        "broken pipe",
        "connection reset",
        "target closed",
        "session closed",
        "cannot connect to host",
        "connect call failed",
    )
    return any(marker in message for marker in markers)


def is_ws_closed(ws: Any) -> bool:
    """Проверяет, закрыто ли соединение WebSocket.

    Поддерживает ``websockets>=14`` (``State.CLOSING``/``State.CLOSED``),
    старые версии и mock-объекты.

    Args:
        ws: Объект WebSocket или None.

    Returns:
        True, если WebSocket закрыт или находится в процессе закрытия.
    """
    if ws is None:
        return False

    state = getattr(ws, "state", None)
    if state is not None:
        state_name = getattr(state, "name", None)
        if isinstance(state_name, str) and state_name.upper() in {"CLOSING", "CLOSED"}:
            return True
        if isinstance(state, str) and state.upper() in {"CLOSING", "CLOSED"}:
            return True
        state_value = getattr(state, "value", None)
        if isinstance(state_value, int) and state_value >= 2:
            return True

    close_code = getattr(ws, "close_code", None)
    if isinstance(close_code, int):
        return True
    if getattr(ws, "closed", None) is True:
        return True
    return getattr(ws, "open", None) is False


def get_browser_main_tab(browser: Any) -> Any | None:
    """Безопасно извлекает главную или первую доступную вкладку браузера.

    Встроенное свойство ``nodriver.Browser.main_tab`` выбрасывает
    ``StopIteration``, если вкладок типа ``page`` ещё нет. Функция
    перехватывает эту ситуацию и возвращает первую вкладку из ``browser.tabs``.

    Args:
        browser: Экземпляр браузера nodriver или mock.

    Returns:
        Активная вкладка или None.
    """
    if browser is None:
        return None

    try:
        tab = getattr(browser, "main_tab", None)
        if tab is not None:
            return tab
    except Exception as exc:
        logger.debug("Не удалось получить main_tab у браузера: %s", exc)

    tabs = getattr(browser, "tabs", None)
    if isinstance(tabs, (list, tuple)) and tabs:
        return tabs[0]
    return None


def check_browser_alive(browser: Any) -> bool:
    """Проверяет, жив ли процесс браузера и активно ли WebSocket-соединение.

    Поддерживает как локальный дочерний процесс nodriver, так и подключение к
    уже запущенному Chromium через удалённый CDP-порт.

    Args:
        browser: Экземпляр браузера nodriver или mock.

    Returns:
        True, если процесс не завершён и сокет не закрыт.
    """
    if browser is None:
        return False

    process = getattr(browser, "_process", None)
    if process is not None:
        returncode = getattr(process, "returncode", None)
        if isinstance(returncode, int):
            return False

        poll_method = getattr(process, "poll", None)
        if callable(poll_method):
            try:
                poll_result = poll_method()
                if inspect.iscoroutine(poll_result):
                    poll_result.close()
                elif isinstance(poll_result, int):
                    return False
            except Exception as exc:
                logger.debug("Ошибка проверки статуса процесса браузера: %s", exc)

        if getattr(browser, "stopped", None) is True:
            return False

    browser_socket = getattr(browser, "socket", None)
    if browser_socket is not None and is_ws_closed(browser_socket):
        return False

    main_tab = get_browser_main_tab(browser)
    if main_tab is not None:
        tab_closed = getattr(main_tab, "closed", None) is True
        tab_socket = getattr(main_tab, "socket", None) or getattr(main_tab, "websocket", None)
        if tab_closed or is_ws_closed(tab_socket):
            tabs = getattr(browser, "tabs", None)
            found_alive = False
            if isinstance(tabs, (list, tuple)):
                for candidate in tabs:
                    c_tab_closed = getattr(candidate, "closed", None) is True
                    c_socket = getattr(candidate, "socket", None) or getattr(
                        candidate, "websocket", None
                    )
                    if not c_tab_closed and not is_ws_closed(c_socket):
                        found_alive = True
                        try:
                            browser.main_tab = candidate
                        except (AttributeError, TypeError):
                            pass
                        break
            if not found_alive:
                return False

    return True


async def ping_browser_tab(browser: Any, timeout: float = 1.5) -> bool:
    """Выполняет быстрый асинхронный CDP-пинг основной вкладки.

    Args:
        browser: Экземпляр браузера nodriver.
        timeout: Максимальное время ожидания ответа в секундах.

    Returns:
        True, если вкладка ответила на команду CDP, иначе False.
    """
    if not check_browser_alive(browser):
        return False

    tab = get_browser_main_tab(browser)
    if tab is None or not hasattr(tab, "evaluate"):
        return False

    try:
        result = await asyncio.wait_for(tab.evaluate("1+1"), timeout=timeout)
        return bool(result == 2)
    except Exception as exc:
        logger.debug("Пинг вкладки браузера не удался: %s", exc)
        return False


def extract_cdp_endpoint(browser: Any) -> dict[str, Any] | None:
    """Извлекает хост и порт CDP из объекта браузера nodriver.

    Args:
        browser: Экземпляр браузера или None.

    Returns:
        Словарь с ключами ``host`` и ``port`` или None.
    """
    if browser is None:
        return None

    config = getattr(browser, "config", None)
    if config is not None:
        host = getattr(config, "host", None) or "127.0.0.1"
        port = getattr(config, "port", None)
        if isinstance(port, int) and 0 < port <= 65535:
            return {"host": _normalize_host(host), "port": port}

    for ws_url in (
        getattr(browser, "websocket_url", None),
        getattr(getattr(browser, "info", None), "webSocketDebuggerUrl", None),
    ):
        endpoint = _endpoint_from_ws_url(ws_url)
        if endpoint is not None:
            return endpoint

    info = getattr(browser, "info", None)
    if isinstance(info, dict):
        return _endpoint_from_ws_url(info.get("webSocketDebuggerUrl"))
    return None


async def detach_for_restart(
    browser: Any,
    *,
    timeout: float = 3.0,
) -> dict[str, Any] | None:
    """Отвязывает WebSocket браузера, не завершая процесс Chromium.

    Функция закрывает CDP-соединение и помечает браузер как отвязанный, чтобы
    обработчики очистки не вызвали ``browser.stop()``. Окно Chromium остаётся
    открытым для повторного подключения после рестарта сервиса.

    Args:
        browser: Экземпляр браузера nodriver.
        timeout: Максимальное время ожидания закрытия WebSocket в секундах.

    Returns:
        Словарь с координатами CDP или None, если браузер не передан.
    """
    if browser is None:
        return None

    endpoint = extract_cdp_endpoint(browser)
    setattr(browser, BROWSER_DETACHED_ATTR, True)

    close_method = getattr(browser, "aclose", None)
    if not callable(close_method):
        close_method = getattr(getattr(browser, "socket", None), "close", None)
    if callable(close_method):
        result = close_method()
        if inspect.isawaitable(result):
            try:
                await asyncio.wait_for(result, timeout=timeout)
            except TimeoutError:
                logger.debug("Таймаут отвязки WebSocket браузера (%.1f с)", timeout)
            except Exception as exc:
                logger.debug("Ошибка отвязки WebSocket браузера: %s", exc)

    logger.info(
        "Сессия браузера отвязана для рестарта (CDP: %s). Окно Chromium сохранено.",
        endpoint,
    )
    return endpoint


def _normalize_host(host: str) -> str:
    """Приводит адрес прослушивания к хосту, доступному для подключения."""
    normalized = host.strip().strip("[]")
    if normalized in {"", "*", "0.0.0.0", "::"}:
        return "127.0.0.1"
    return normalized


def _endpoint_from_ws_url(ws_url: Any) -> dict[str, Any] | None:
    """Извлекает хост и порт из WebSocket URL CDP."""
    if not isinstance(ws_url, str) or not ws_url:
        return None
    parsed = urlparse(ws_url)
    if parsed.scheme not in {"ws", "wss"} or parsed.hostname is None:
        return None
    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "wss" else 80
    return {"host": _normalize_host(parsed.hostname), "port": int(port)}


__all__ = [
    "BROWSER_DETACHED_ATTR",
    "check_browser_alive",
    "detach_for_restart",
    "extract_cdp_endpoint",
    "get_browser_main_tab",
    "is_browser_connection_error",
    "is_ws_closed",
    "ping_browser_tab",
]
