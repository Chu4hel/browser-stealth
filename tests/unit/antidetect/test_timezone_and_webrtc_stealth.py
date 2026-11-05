"""Тесты синхронизации часового пояса и герметизации WebRTC (Issue #04)."""

from __future__ import annotations

import shutil
import subprocess
from unittest.mock import AsyncMock, patch

import pytest

from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.antidetect.core import apply_antidetect_nodriver
from browser_stealth.antidetect.scripts import _get_antidetect_js


@pytest.mark.asyncio
async def test_apply_antidetect_nodriver_sends_timezone_override() -> None:
    """Проверяет отправку команды CDP emulation.set_timezone_override при наличии timezone."""
    tab = AsyncMock()
    config = AntidetectConfig(timezone="America/New_York")

    with patch("nodriver.cdp.emulation.set_timezone_override") as mock_tz:
        mock_tz.return_value = "mock_tz_command"
        await apply_antidetect_nodriver(tab, config=config)

        mock_tz.assert_called_once_with(timezone_id="America/New_York")
        assert "mock_tz_command" in [c[0][0] for c in tab.send.call_args_list]


def test_webrtc_script_icecandidate_filtering() -> None:
    """Проверяет наличие фильтрации хостовых IP-кандидатов в WebRTC обработчиках."""
    js = _get_antidetect_js(timezone="Europe/Berlin")

    assert "onicecandidate" in js
    assert "typ host" in js
    assert "addEventListener" in js
    assert "targetTimezone" in js
    assert "Europe/Berlin" in js


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js не установлен")
def test_intl_timezone_node_runtime() -> None:
    """Проверяет эмуляцию Intl.DateTimeFormat().resolvedOptions().timeZone в Node.js runtime."""
    js = _get_antidetect_js(timezone="Asia/Tokyo")

    node_runner = f"""
    const assert = require('assert');
    const window = globalThis;
    window.window = window;

    globalThis.document = {{ createElement: () => ({{}}) }};
    globalThis.navigator = {{ webdriver: true, plugins: [] }};

    {js}

    const resolved = Intl.DateTimeFormat().resolvedOptions();
    assert.strictEqual(resolved.timeZone, 'Asia/Tokyo', 'Часовой пояс Intl должен быть Asia/Tokyo');

    console.log('TIMEZONE_TEST_PASSED');
    """

    res = subprocess.run(
        ["node"],
        input=node_runner,
        capture_output=True,
        text=True,
        timeout=10,
        check=False,
    )
    assert res.returncode == 0, f"Node.js script failed:\n{res.stderr}\n{res.stdout}"
    assert "TIMEZONE_TEST_PASSED" in res.stdout
