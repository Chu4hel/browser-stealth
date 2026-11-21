"""Тесты очистки паразитных пустых вкладок nodriver."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.launchers.nodriver import (
    cleanup_duplicate_empty_tabs,
    launch_nodriver,
)


def _tab(url: str) -> MagicMock:
    """Создаёт мок вкладки nodriver с заданным URL."""
    tab = MagicMock()
    tab.target = SimpleNamespace(url=url)
    tab.close = AsyncMock()
    return tab


def _browser(tabs: list[MagicMock], main_tab: MagicMock) -> MagicMock:
    """Создаёт мок браузера с вкладками и обновлением targets."""
    browser = MagicMock()
    browser.tabs = tabs
    browser.main_tab = main_tab
    browser.update_targets = AsyncMock()
    return browser


@pytest.mark.asyncio
async def test_cleanup_keeps_working_page_and_closes_blank_duplicates() -> None:
    """Основная пустая вкладка заменяется рабочей, дубликаты закрываются."""
    main = _tab("chrome://newtab/")
    work = _tab("https://example.com")
    duplicate = _tab("about:blank")
    browser = _browser([main, work, duplicate], main)

    closed = await cleanup_duplicate_empty_tabs(browser)

    assert closed == 2
    main.close.assert_awaited_once()
    duplicate.close.assert_awaited_once()
    work.close.assert_not_called()
    browser.update_targets.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_does_not_close_non_empty_tabs() -> None:
    """Непустые вкладки сохраняются, даже если они не main_tab."""
    main = _tab("https://example.com")
    other = _tab("https://example.org")
    blank = _tab("about:blank")
    browser = _browser([main, other, blank], main)

    closed = await cleanup_duplicate_empty_tabs(browser)

    assert closed == 1
    main.close.assert_not_called()
    other.close.assert_not_called()
    blank.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_keeps_one_tab_when_all_are_blank() -> None:
    """Если рабочих вкладок нет, остаётся main_tab, остальные закрываются."""
    main = _tab("about:blank")
    duplicate = _tab("chrome://new-tab-page/")
    browser = _browser([main, duplicate], main)

    closed = await cleanup_duplicate_empty_tabs(browser)

    assert closed == 1
    main.close.assert_not_called()
    duplicate.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_cleanup_returns_none_without_tabs() -> None:
    """Для браузера без вкладок очистка ничего не делает."""
    browser = _browser([], MagicMock())

    closed = await cleanup_duplicate_empty_tabs(browser)

    assert closed == 0
    browser.update_targets.assert_not_called()


@pytest.mark.asyncio
async def test_reattach_cleans_empty_tabs_and_configures_working_page() -> None:
    """При reattach пустая main_tab закрывается, конфиг применяется к рабочей."""
    blank = _tab("chrome://newtab/")
    work = _tab("https://example.com")
    browser = _browser([blank, work], blank)
    mock_uc = MagicMock()
    mock_uc.start = AsyncMock(return_value=browser)

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch(
            "browser_stealth.launchers.nodriver.discover_active_cdp_endpoint",
            return_value=("127.0.0.1", 9222),
        ),
        patch("browser_stealth.launchers.nodriver.sanitize_profile"),
        patch.object(AntidetectConfig, "apply_to_nodriver", new_callable=AsyncMock) as apply,
    ):
        result = await launch_nodriver(user_data_dir="/tmp/profile")

    assert result is browser
    blank.close.assert_awaited_once()
    work.close.assert_not_called()
    apply.assert_awaited_once_with(work)
