"""Тесты реалистичного движения мыши, физического клика и рандомизации задержек."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from browser_stealth.humanize.actions import async_click, async_type_text, type_text
from browser_stealth.humanize.behavior import BehavioralProfile
from browser_stealth.humanize.consent import _handle_consent_dialog, _handle_consent_dialog_sync


@pytest.mark.asyncio
async def test_handle_consent_dialog_uses_async_click() -> None:
    """Проверяет, что _handle_consent_dialog выполняет физический async_click по координатам."""
    tab = AsyncMock()
    tab.evaluate.return_value = {"found": True, "x": 350.5, "y": 420.0}

    with (
        patch("browser_stealth.humanize.actions.async_click", new_callable=AsyncMock) as mock_click,
        patch("browser_stealth.humanize.consent.async_human_sleep", new_callable=AsyncMock),
    ):
        result = await _handle_consent_dialog(tab)

        assert result is True
        mock_click.assert_awaited_once_with(tab, x=350, y=420)


def test_handle_consent_dialog_sync_uses_click() -> None:
    """Проверяет, что _handle_consent_dialog_sync выполняет физический click по координатам."""
    driver = MagicMock()
    driver.execute_script.return_value = {"found": True, "x": 512.0, "y": 600.0}

    with (
        patch("browser_stealth.humanize.actions.click") as mock_click,
        patch("browser_stealth.humanize.consent.human_sleep"),
    ):
        result = _handle_consent_dialog_sync(driver)

        assert result is True
        mock_click.assert_called_once_with(driver, x=512, y=600)


@pytest.mark.asyncio
async def test_async_type_text_post_typing_delay_and_jitter() -> None:
    """Проверяет выполнение задержки post_typing_delay и отправку микроджиттера мыши."""
    tab = AsyncMock()
    # Mocking nodriver behavior
    tab.send = AsyncMock()
    tab._stealth_mouse_pos = (100, 200)

    with (
        patch("browser_stealth.humanize.actions._is_nodriver", return_value=True),
        patch("browser_stealth.humanize.actions._is_playwright", return_value=False),
        patch(
            "browser_stealth.humanize.actions._async_type_nodriver", new_callable=AsyncMock
        ) as mock_type,
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        await async_type_text(
            tab,
            selector="#input",
            text="hello",
            post_typing_delay=(0.3, 0.5),
            jitter_mouse=True,
        )

        mock_type.assert_awaited_once()
        # Проверяем, что sleep был вызван с задержкой в диапазоне (0.3, 0.5)
        sleep_calls = [
            c.args[0]
            for c in mock_sleep.call_args_list
            if len(c.args) > 0 and 0.29 <= c.args[0] <= 0.51
        ]
        assert len(sleep_calls) >= 1

        # Проверяем отправку cdp Input.dispatchMouseEvent с type_='mouseMoved'
        assert tab.send.called


@pytest.mark.asyncio
async def test_async_type_text_no_jitter_when_disabled() -> None:
    """Проверяет отсутствие микроджиттера мыши, если jitter_mouse=False."""
    tab = AsyncMock()
    tab.send = AsyncMock()

    with (
        patch("browser_stealth.humanize.actions._is_nodriver", return_value=True),
        patch("browser_stealth.humanize.actions._is_playwright", return_value=False),
        patch("browser_stealth.humanize.actions._async_type_nodriver", new_callable=AsyncMock),
        patch("asyncio.sleep", new_callable=AsyncMock),
    ):
        await async_type_text(
            tab,
            selector="#input",
            text="hello",
            post_typing_delay=(0.1, 0.2),
            jitter_mouse=False,
        )

        # tab.send не должен вызываться для jitter
        assert not tab.send.called


def test_type_text_selenium_post_typing_delay_and_jitter() -> None:
    """Проверяет, что синхронный type_text выполняет паузу и сдвиг курсора."""
    driver = MagicMock()
    elem = MagicMock()
    driver.find_element.return_value = elem

    with (
        patch("browser_stealth.humanize.actions._ensure_selenium"),
        patch("time.sleep") as mock_sleep,
        patch("selenium.webdriver.common.action_chains.ActionChains") as mock_actions_cls,
    ):
        mock_actions = MagicMock()
        mock_actions_cls.return_value = mock_actions
        mock_actions.move_by_offset.return_value = mock_actions

        type_text(
            driver,
            selector="#input",
            text="hello",
            post_typing_delay=(0.25, 0.5),
            jitter_mouse=True,
        )

        # Проверяем вызов паузы post_typing_delay
        delays = [c.args[0] for c in mock_sleep.call_args_list if 0.24 <= c.args[0] <= 0.51]
        assert len(delays) >= 1

        # Проверяем, что ActionChains.move_by_offset был вызван
        mock_actions.move_by_offset.assert_called_once()
        mock_actions.perform.assert_called()


@pytest.mark.asyncio
async def test_async_click_hold_time_default() -> None:
    """Проверяет диапазон удержания кнопки мыши (60-120 мс) по умолчанию в async_click."""
    page = AsyncMock()
    page.mouse = AsyncMock()

    with (
        patch("browser_stealth.humanize.actions._is_nodriver", return_value=False),
        patch("browser_stealth.humanize.actions._is_playwright", return_value=True),
        patch("browser_stealth.humanize.actions._ensure_playwright"),
        patch("browser_stealth.humanize.actions.async_move_mouse", new_callable=AsyncMock),
        patch("asyncio.sleep", new_callable=AsyncMock) as mock_sleep,
    ):
        await async_click(page, x=100, y=100)

        # Вторым вызовом sleep внутри _click идет hold_delay (0.06 - 0.12)
        sleep_args = [c.args[0] for c in mock_sleep.call_args_list if len(c.args) > 0]
        # Проверяем, что хотя бы один вызов sleep находится в диапазоне 0.059 - 0.121
        hold_calls = [arg for arg in sleep_args if 0.059 <= arg <= 0.121]
        assert len(hold_calls) >= 1


def test_behavioral_profile_new_fields_and_seed() -> None:
    """Проверяет настройки post_typing_delay, jitter_mouse и click_hold_time в BehavioralProfile."""
    profile = BehavioralProfile()
    assert profile.click_hold_time == (0.06, 0.12)
    assert profile.post_typing_delay == (0.25, 0.8)
    assert profile.jitter_mouse is True

    seeded = BehavioralProfile.from_seed("profile-user-seed")
    assert 0.05 <= seeded.click_hold_time[0] <= 0.09
    assert seeded.click_hold_time[1] > seeded.click_hold_time[0]
    assert 0.19 <= seeded.post_typing_delay[0] <= 0.4
    assert seeded.post_typing_delay[1] > seeded.post_typing_delay[0]
