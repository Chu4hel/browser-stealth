"""Unit-тесты для модуля запуска nodriver (launch_nodriver, nodriver_session)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.connection import BROWSER_DETACHED_ATTR
from browser_stealth.launchers.nodriver import (
    _get_nodriver_module,
    launch_nodriver,
    nodriver_session,
)


def test_get_nodriver_module_not_installed() -> None:
    """Проверка выброса понятной ошибки при отсутствии nodriver."""
    with patch.dict("sys.modules", {"nodriver": None}):
        with patch("builtins.__import__", side_effect=ImportError("No module named 'nodriver'")):
            with pytest.raises(
                ImportError,
                match="Для использования nodriver необходимо установить библиотеку",
            ):
                _get_nodriver_module()


@pytest.mark.asyncio
async def test_launch_nodriver_default() -> None:
    """Проверка запуска nodriver со стандартным пресетом AntidetectConfig и stealth-аргументами."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_tab = MagicMock()
    mock_browser.main_tab = mock_tab
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch.object(AntidetectConfig, "apply_to_nodriver", new_callable=AsyncMock) as mock_apply,
    ):
        browser = await launch_nodriver(headless=True)
        assert browser is mock_browser
        assert mock_uc.start.called

        _, kwargs = mock_uc.start.call_args
        assert kwargs["headless"] is True
        args = kwargs["browser_args"]
        assert not any("--disable-blink-features=AutomationControlled" in a for a in args)
        assert any("--disable-dev-shm-usage" in a for a in args)

        # Проверяем, что к вкладке применен стелс-конфиг
        assert mock_apply.called


@pytest.mark.asyncio
async def test_launch_nodriver_uses_discovered_browser_executable() -> None:
    """Без явного пути launch_nodriver использует найденный браузер."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.main_tab = MagicMock()
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch(
            "browser_stealth.launchers.nodriver.discover_browser_executable",
            return_value="/discovered/chrome",
        ) as mock_discover,
        patch("browser_stealth.launchers.nodriver.ensure_local_no_proxy") as mock_guard,
        patch.object(AntidetectConfig, "apply_to_nodriver", new_callable=AsyncMock),
    ):
        await launch_nodriver(headless=True)

    mock_guard.assert_called_once_with()
    mock_discover.assert_called_once_with(None)
    _, kwargs = mock_uc.start.call_args
    assert kwargs["browser_executable_path"] == "/discovered/chrome"


@pytest.mark.asyncio
async def test_launch_nodriver_with_proxy_and_custom_args() -> None:
    """Проверка добавления аргументов прокси и пользовательских флагов."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.main_tab = MagicMock()
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch("browser_stealth.launchers.nodriver.AntidetectConfig.apply_to_nodriver", AsyncMock()),
    ):
        await launch_nodriver(
            proxy="http://1.2.3.4:8080",
            browser_args=["--custom-flag=test"],
        )
        _, kwargs = mock_uc.start.call_args
        args = kwargs["browser_args"]
        assert "--custom-flag=test" in args
        assert any("--proxy-server=" in a for a in args)


@pytest.mark.asyncio
async def test_nodriver_session_context_manager() -> None:
    """Проверка корректного закрытия браузера в nodriver_session."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.main_tab = MagicMock()
    mock_browser.stop = AsyncMock()
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch("browser_stealth.launchers.nodriver.AntidetectConfig.apply_to_nodriver", AsyncMock()),
    ):
        async with nodriver_session(headless=False) as browser:
            assert browser is mock_browser
            assert not mock_browser.stop.called

        # После выхода из контекста вызван stop()
        assert mock_browser.stop.called


@pytest.mark.asyncio
async def test_launch_nodriver_user_data_dir_and_executable(tmp_path: Path) -> None:
    """Проверка передачи user_data_dir и browser_executable_path в uc.start."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.main_tab = MagicMock()
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch("browser_stealth.launchers.nodriver.AntidetectConfig.apply_to_nodriver", AsyncMock()),
    ):
        await launch_nodriver(
            user_data_dir=tmp_path,
            browser_executable_path="/usr/bin/google-chrome",
        )
        _, kwargs = mock_uc.start.call_args
        assert kwargs["user_data_dir"] == str(tmp_path.resolve())
        assert kwargs["browser_executable_path"] == "/usr/bin/google-chrome"


@pytest.mark.asyncio
async def test_launch_nodriver_sanitizes_profile(tmp_path: Path) -> None:
    """Проверка вызова sanitize_profile перед стартом nodriver при указании user_data_dir."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.main_tab = MagicMock()
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch("browser_stealth.launchers.nodriver.AntidetectConfig.apply_to_nodriver", AsyncMock()),
        patch("browser_stealth.launchers.nodriver.sanitize_profile") as mock_sanitize,
    ):
        await launch_nodriver(user_data_dir=tmp_path)
        mock_sanitize.assert_called_once_with(tmp_path.resolve())


@pytest.mark.asyncio
async def test_launch_nodriver_waits_for_slow_cdp() -> None:
    """Проверка подключения к Chromium, не успевшему открыть порт CDP за таймаут nodriver."""
    from types import SimpleNamespace

    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.info = None
    mock_browser.main_tab = MagicMock()
    mock_browser._process = MagicMock(returncode=None)
    mock_browser._http.get = AsyncMock(
        return_value={"webSocketDebuggerUrl": "ws://127.0.0.1/devtools"}
    )
    mock_browser.attach = AsyncMock()
    mock_browser.update_targets = AsyncMock()
    mock_uc.ContraDict = lambda value, silent=True: SimpleNamespace(
        webSocketDebuggerUrl=value["webSocketDebuggerUrl"]
    )
    # До запуска экземпляров нет, после неудачной попытки появляется один незавершенный.
    mock_uc.util.get_registered_instances.side_effect = [set(), {mock_browser}]
    mock_uc.start = AsyncMock(side_effect=Exception("Failed to connect to browser"))

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch("browser_stealth.launchers.nodriver.AntidetectConfig.apply_to_nodriver", AsyncMock()),
    ):
        browser = await launch_nodriver(headless=True)

    assert browser is mock_browser
    assert mock_browser.attach.called
    assert mock_browser.update_targets.called
    assert mock_browser.info is not None


@pytest.mark.asyncio
async def test_launch_nodriver_reports_chrome_stderr_on_crash() -> None:
    """Проверка попадания stderr Chromium в ошибку, если процесс упал при старте."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.info = None
    mock_browser.main_tab = MagicMock()
    mock_browser._process = MagicMock(returncode=1)
    mock_browser._process.stderr.read = AsyncMock(
        return_value=b"[FATAL:zygote_host_impl_linux.cc] Running as root without --no-sandbox"
    )
    mock_uc.util.get_registered_instances.side_effect = [set(), {mock_browser}]
    mock_uc.start = AsyncMock(side_effect=Exception("Failed to connect to browser"))

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch("browser_stealth.launchers.nodriver.AntidetectConfig.apply_to_nodriver", AsyncMock()),
    ):
        with pytest.raises(RuntimeError) as exc_info:
            await launch_nodriver(headless=True)

    message = str(exc_info.value)
    assert "кодом 1" in message
    assert "Running as root without --no-sandbox" in message
    assert not mock_browser.attach.called


def test_scraping_module_exports() -> None:
    """Проверка ленивого экспорта launch_nodriver и nodriver_session из browser_stealth."""
    import browser_stealth

    assert hasattr(browser_stealth, "launch_nodriver")
    assert hasattr(browser_stealth, "nodriver_session")
    assert hasattr(browser_stealth, "close_tab")
    assert hasattr(browser_stealth, "discover_active_cdp_endpoint")
    assert "launch_nodriver" in browser_stealth.__all__
    assert "nodriver_session" in browser_stealth.__all__
    assert "close_tab" in browser_stealth.__all__
    assert "discover_active_cdp_endpoint" in browser_stealth.__all__


@pytest.mark.asyncio
async def test_launch_nodriver_reattaches_to_active_profile(tmp_path: Path) -> None:
    """При auto_reattach подключение идёт к найденному CDP без санитизации профиля."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.main_tab = MagicMock()
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch(
            "browser_stealth.launchers.nodriver.discover_active_cdp_endpoint",
            return_value=("127.0.0.1", 9222),
        ) as mock_discover,
        patch("browser_stealth.launchers.nodriver.sanitize_profile") as mock_sanitize,
        patch.object(AntidetectConfig, "apply_to_nodriver", new_callable=AsyncMock) as mock_apply,
    ):
        browser = await launch_nodriver(user_data_dir=tmp_path)

    assert browser is mock_browser
    mock_discover.assert_called_once_with(tmp_path)
    mock_sanitize.assert_not_called()
    assert getattr(mock_browser, "_browser_stealth_reattached") is True
    assert mock_apply.called

    _, kwargs = mock_uc.start.call_args
    assert kwargs["host"] == "127.0.0.1"
    assert kwargs["port"] == 9222
    assert "user_data_dir" not in kwargs


@pytest.mark.asyncio
async def test_launch_nodriver_can_disable_auto_reattach(tmp_path: Path) -> None:
    """При auto_reattach=False профиль не проверяется на активный CDP."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.main_tab = MagicMock()
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch("browser_stealth.launchers.nodriver.discover_active_cdp_endpoint") as mock_discover,
        patch("browser_stealth.launchers.nodriver.sanitize_profile"),
        patch.object(AntidetectConfig, "apply_to_nodriver", new_callable=AsyncMock),
    ):
        await launch_nodriver(user_data_dir=tmp_path, auto_reattach=False)

    mock_discover.assert_not_called()
    _, kwargs = mock_uc.start.call_args
    assert kwargs["user_data_dir"] == str(tmp_path)


@pytest.mark.asyncio
async def test_nodriver_session_keeps_reattached_browser_running() -> None:
    """Выход из сессии закрывает CDP-соединение, но не гасит чужой Chromium."""
    mock_browser = MagicMock()
    mock_browser.stop = AsyncMock()
    mock_browser.aclose = AsyncMock()
    mock_browser._browser_stealth_reattached = True

    with patch(
        "browser_stealth.launchers.nodriver.launch_nodriver",
        new=AsyncMock(return_value=mock_browser),
    ):
        async with nodriver_session() as browser:
            assert browser is mock_browser

    mock_browser.stop.assert_not_called()
    mock_browser.aclose.assert_called_once()


@pytest.mark.asyncio
async def test_nodriver_session_skips_stop_after_graceful_detach() -> None:
    """После detach_for_restart выход из сессии не завершает Chromium."""
    mock_browser = MagicMock()
    mock_browser.stop = AsyncMock()
    setattr(mock_browser, BROWSER_DETACHED_ATTR, True)

    with patch(
        "browser_stealth.launchers.nodriver.launch_nodriver",
        new=AsyncMock(return_value=mock_browser),
    ):
        async with nodriver_session() as browser:
            assert browser is mock_browser

    mock_browser.stop.assert_not_called()


@pytest.mark.asyncio
async def test_close_tab_success() -> None:
    """Проверка успешного закрытия вкладки nodriver."""
    from browser_stealth.launchers.nodriver import close_tab

    mock_tab = MagicMock()
    mock_tab.close = AsyncMock()

    await close_tab(mock_tab, timeout=1.0)
    mock_tab.close.assert_called_once()


@pytest.mark.asyncio
async def test_close_tab_timeout_handled() -> None:
    """Проверка обработки таймаута при зависшем CDP close."""
    import asyncio

    from browser_stealth.launchers.nodriver import close_tab

    mock_tab = MagicMock()

    async def slow_close() -> None:
        await asyncio.sleep(1.0)

    mock_tab.close = slow_close

    # Не должно выбрасывать TimeoutError
    await close_tab(mock_tab, timeout=0.05)


@pytest.mark.asyncio
async def test_close_tab_exception_handled() -> None:
    """Проверка обработки исключений при закрытии вкладки nodriver."""
    from browser_stealth.launchers.nodriver import close_tab

    mock_tab = MagicMock()
    mock_tab.close = AsyncMock(side_effect=RuntimeError("CDP connection lost"))

    # Не должно выбрасывать исключение
    await close_tab(mock_tab, timeout=1.0)
