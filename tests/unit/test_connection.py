"""Тесты модуля browser_stealth.connection."""

from __future__ import annotations

from enum import Enum
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from browser_stealth.connection import (
    BROWSER_DETACHED_ATTR,
    check_browser_alive,
    detach_for_restart,
    extract_cdp_endpoint,
    get_browser_main_tab,
    is_browser_connection_error,
    is_ws_closed,
    ping_browser_tab,
)


class _WsState(Enum):
    """Минимальный аналог websockets.protocol.State."""

    OPEN = 1
    CLOSING = 2
    CLOSED = 3


class _ConnectionClosed(Exception):
    """Исключение с именем, которое распознаёт классификатор."""


def _tab(*, closed: bool = False, evaluate_result: object = 2) -> SimpleNamespace:
    """Создаёт мок вкладки nodriver."""
    return SimpleNamespace(
        closed=closed,
        socket=None,
        websocket=None,
        evaluate=AsyncMock(return_value=evaluate_result),
    )


def test_is_browser_connection_error() -> None:
    """Классификатор распознаёт сетевые ошибки и текстовые маркеры."""
    assert is_browser_connection_error(BrokenPipeError()) is True
    assert is_browser_connection_error(_ConnectionClosed()) is True
    assert is_browser_connection_error(RuntimeError("target closed")) is True
    assert is_browser_connection_error(ValueError("invalid selector")) is False


def test_is_ws_closed_supports_state_codes_and_legacy_flags() -> None:
    """Проверка WebSocket учитывает State, close_code и старые атрибуты."""
    assert is_ws_closed(None) is False
    assert is_ws_closed(SimpleNamespace(state=_WsState.CLOSED)) is True
    assert is_ws_closed(SimpleNamespace(state=_WsState.CLOSING)) is True
    assert is_ws_closed(SimpleNamespace(state=_WsState.OPEN)) is False
    assert is_ws_closed(SimpleNamespace(close_code=1000)) is True
    assert is_ws_closed(SimpleNamespace(closed=True)) is True
    assert is_ws_closed(SimpleNamespace(open=False)) is True


def test_get_browser_main_tab_falls_back_when_property_raises() -> None:
    """При StopIteration в main_tab возвращается первая вкладка."""
    tab = _tab()

    class Browser:
        def __init__(self) -> None:
            self.tabs = [tab]

        @property
        def main_tab(self) -> object:
            raise StopIteration

    assert get_browser_main_tab(Browser()) is tab


def test_check_browser_alive_for_remote_cdp_ignores_stopped() -> None:
    """Для внешнего CDP stopped=True не должен давать ложный False."""
    tab = _tab()
    browser = SimpleNamespace(
        _process=None,
        stopped=True,
        socket=None,
        main_tab=tab,
        tabs=[tab],
    )

    assert check_browser_alive(browser) is True


def test_check_browser_alive_detects_exited_process() -> None:
    """Завершённый локальный процесс считается мёртвым."""
    browser = SimpleNamespace(_process=SimpleNamespace(returncode=1))

    assert check_browser_alive(browser) is False


def test_check_browser_alive_uses_other_tab_after_main_closed() -> None:
    """Если main_tab закрыт, проверяется другая живая вкладка."""
    closed_tab = _tab(closed=True)
    alive_tab = _tab()
    browser = SimpleNamespace(
        _process=None,
        socket=None,
        main_tab=closed_tab,
        tabs=[closed_tab, alive_tab],
    )

    assert check_browser_alive(browser) is True
    assert browser.main_tab is alive_tab


@pytest.mark.asyncio
async def test_ping_browser_tab_returns_true_for_working_tab() -> None:
    """CDP-пинг 1+1 возвращает True для живой вкладки."""
    tab = _tab(evaluate_result=2)
    browser = SimpleNamespace(
        _process=None,
        stopped=True,
        socket=None,
        main_tab=tab,
        tabs=[tab],
    )

    assert await ping_browser_tab(browser) is True


@pytest.mark.asyncio
async def test_ping_browser_tab_returns_false_for_dead_tab() -> None:
    """CDP-пинг возвращает False, если вкладка не отвечает."""
    assert await ping_browser_tab(None) is False


def test_extract_cdp_endpoint_from_config_and_websocket() -> None:
    """Endpoint извлекается из config и WebSocket URL, включая IPv6."""
    config_browser = SimpleNamespace(config=SimpleNamespace(host="0.0.0.0", port=9222))
    assert extract_cdp_endpoint(config_browser) == {"host": "127.0.0.1", "port": 9222}

    ws_browser = SimpleNamespace(websocket_url="ws://[::1]:9333/devtools/browser/test")
    assert extract_cdp_endpoint(ws_browser) == {"host": "::1", "port": 9333}

    info_browser = SimpleNamespace(
        info={"webSocketDebuggerUrl": "ws://127.0.0.1:9444/devtools/browser/test"}
    )
    assert extract_cdp_endpoint(info_browser) == {"host": "127.0.0.1", "port": 9444}


@pytest.mark.asyncio
async def test_detach_for_restart_closes_socket_without_stop() -> None:
    """Graceful detach закрывает WebSocket, но не вызывает stop процесса."""
    browser = SimpleNamespace(
        config=SimpleNamespace(host="127.0.0.1", port=9222),
        aclose=AsyncMock(),
        stop=AsyncMock(),
    )

    endpoint = await detach_for_restart(browser)

    assert endpoint == {"host": "127.0.0.1", "port": 9222}
    assert getattr(browser, BROWSER_DETACHED_ATTR) is True
    browser.aclose.assert_awaited_once()
    browser.stop.assert_not_called()
