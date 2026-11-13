"""Тесты защиты от неподдерживаемых флагов Chromium."""

from __future__ import annotations

import logging
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from browser_stealth.antidetect import get_browser_launch_args
from browser_stealth.antidetect.flags import (
    FlagPolicy,
    find_unsupported_flags,
    raise_for_unsupported_flags,
    sanitize_browser_args,
)
from browser_stealth.exceptions import UnsupportedBrowserFlagError
from browser_stealth.launchers.nodriver import ChromiumProcessManager, launch_nodriver


def test_recommended_args_are_clean() -> None:
    """Рекомендуемый набор аргументов не содержит неподдерживаемых флагов."""
    args = get_browser_launch_args()
    assert find_unsupported_flags(args) == ()
    assert sanitize_browser_args(args) == args


@pytest.mark.parametrize(
    ("argument", "expected_flag"),
    [
        ("--disable-blink-features=AutomationControlled", "--disable-blink-features"),
        (
            "--disable-blink-features=SomeFeature,AutomationControlled",
            "--disable-blink-features",
        ),
        ("--use-fake-ui-for-media-stream", "--use-fake-ui-for-media-stream"),
        ("--use-fake-device-for-media-stream", "--use-fake-device-for-media-stream"),
        ("--enable-automation", "--enable-automation"),
        ("--enable-automation=true", "--enable-automation"),
        ("--headless=old", "--headless=old"),
        ("--headless=chrome", "--headless=chrome"),
    ],
)
def test_find_unsupported_flags(argument: str, expected_flag: str) -> None:
    """Обнаружение известных неподдерживаемых флагов."""
    violations = find_unsupported_flags([argument, "--no-first-run"])
    assert len(violations) == 1
    assert violations[0].argument == argument
    assert violations[0].flag == expected_flag
    assert violations[0].rule.reason


def test_safe_lookalike_flags_are_allowed() -> None:
    """Похожие, но безопасные флаги не блокируются."""
    args = [
        "--disable-blink-features=SomeFeature",
        "--disable-blink-features=AutomationControlledOther",
        "--headless=new",
        "--enable-features=NetworkService",
    ]
    assert find_unsupported_flags(args) == ()
    assert sanitize_browser_args(args) == args


def test_sanitize_removes_unsupported_flags(caplog: pytest.LogCaptureFixture) -> None:
    """Политика SANITIZE удаляет опасные флаги и пишет предупреждение."""
    caplog.set_level(logging.WARNING, logger="browser_stealth.antidetect.flags")

    result = sanitize_browser_args(
        [
            "--no-first-run",
            "--disable-blink-features=AutomationControlled",
            "--use-fake-ui-for-media-stream",
            "--mute-audio",
        ]
    )

    assert result == ["--no-first-run", "--mute-audio"]
    assert any("AutomationControlled" in record.message for record in caplog.records)
    assert any("fake-ui-for-media-stream" in record.message for record in caplog.records)


def test_sanitize_strips_only_dangerous_blink_feature() -> None:
    """Из списка Blink-фич удаляется только AutomationControlled."""
    result = sanitize_browser_args(
        ["--disable-blink-features=SomeFeature,AutomationControlled,AnotherFeature"]
    )
    assert result == ["--disable-blink-features=SomeFeature,AnotherFeature"]


def test_sanitize_is_idempotent() -> None:
    """Повторная санация не меняет результат."""
    once = sanitize_browser_args(["--disable-blink-features=AutomationControlled"])
    assert sanitize_browser_args(once) == once == []


def test_error_policy_raises_with_flags() -> None:
    """Политика ERROR прерывает запуск и перечисляет все нарушения."""
    with pytest.raises(UnsupportedBrowserFlagError) as exc_info:
        sanitize_browser_args(
            [
                "--use-fake-ui-for-media-stream",
                "--no-first-run",
                "--enable-automation",
            ],
            policy=FlagPolicy.ERROR,
        )

    assert exc_info.value.flags == (
        "--use-fake-ui-for-media-stream",
        "--enable-automation",
    )
    assert "--use-fake-ui-for-media-stream" in str(exc_info.value)


def test_ignore_policy_keeps_arguments(caplog: pytest.LogCaptureFixture) -> None:
    """Политика IGNORE оставляет аргументы, но предупреждает о рисках."""
    caplog.set_level(logging.WARNING, logger="browser_stealth.antidetect.flags")
    args = ["--enable-automation"]

    assert sanitize_browser_args(args, policy="ignore") == args
    assert any("передан без изменений" in record.message for record in caplog.records)


def test_invalid_policy_raises_value_error() -> None:
    """Неизвестная политика приводит к ValueError."""
    with pytest.raises(ValueError):
        sanitize_browser_args(["--no-first-run"], policy="unknown")


def test_raise_for_unsupported_flags() -> None:
    """Строгая проверка выбрасывает исключение только при нарушениях."""
    raise_for_unsupported_flags(["--no-first-run", "--mute-audio"])
    with pytest.raises(UnsupportedBrowserFlagError):
        raise_for_unsupported_flags(["--use-fake-device-for-media-stream"])


@pytest.mark.asyncio
async def test_launch_nodriver_sanitizes_user_args() -> None:
    """launch_nodriver по умолчанию удаляет опасные пользовательские флаги."""
    mock_uc = MagicMock()
    mock_browser = MagicMock()
    mock_browser.main_tab = MagicMock()
    mock_uc.start = AsyncMock(return_value=mock_browser)

    with (
        patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc),
        patch("browser_stealth.launchers.nodriver.AntidetectConfig.apply_to_nodriver", AsyncMock()),
    ):
        await launch_nodriver(
            headless=True,
            browser_args=[
                "--disable-blink-features=AutomationControlled",
                "--custom-flag=test",
            ],
        )

    _, kwargs = mock_uc.start.call_args
    args = kwargs["browser_args"]
    assert "--custom-flag=test" in args
    assert not any("AutomationControlled" in arg for arg in args)


@pytest.mark.asyncio
async def test_launch_nodriver_strict_policy_raises() -> None:
    """launch_nodriver с FlagPolicy.ERROR не запускает браузер при опасном флаге."""
    mock_uc = MagicMock()
    mock_uc.start = AsyncMock()

    with patch("browser_stealth.launchers.nodriver._get_nodriver_module", return_value=mock_uc):
        with pytest.raises(UnsupportedBrowserFlagError):
            await launch_nodriver(
                headless=True,
                browser_args=["--use-fake-ui-for-media-stream"],
                browser_args_policy=FlagPolicy.ERROR,
            )

    assert not mock_uc.start.called


@pytest.mark.asyncio
async def test_chromium_process_manager_sanitizes_extra_args(tmp_path: Path) -> None:
    """ChromiumProcessManager удаляет опасные флаги из extra_args."""
    mock_browser = MagicMock()
    mock_browser.tabs = []
    mock_browser.update_targets = AsyncMock()
    mock_browser.stop = MagicMock()

    manager = ChromiumProcessManager()
    with patch("nodriver.start", new=AsyncMock(return_value=mock_browser)) as mock_start:
        await manager.launch(
            profile_path=tmp_path / "profile",
            headless=True,
            extra_args=[
                "--disable-blink-features=AutomationControlled",
                "--custom-flag=test",
            ],
        )

    args = mock_start.call_args.kwargs["browser_args"]
    assert "--custom-flag=test" in args
    assert not any("AutomationControlled" in arg for arg in args)
