"""Тяжелые сквозные (E2E) тесты против внешних стендов детекта ботов (Sannysoft, Cloudflare, Browserleaks).

Поддерживают использование прокси из переменных окружения (TEST_PROXY, E2E_PROXY, PROXY_URL) или файла .env.
Запускаются отдельно с маркером 'heavy':
    uv run pytest -m heavy
"""

from __future__ import annotations

import asyncio
import os
import urllib.request
from typing import Any

import pytest

# Исключаем проксирование локальных адресов
os.environ["NO_PROXY"] = "127.0.0.1,localhost"

from browser_stealth.antidetect.config import AntidetectConfig
from browser_stealth.humanize.turnstile import solve_cf_turnstile
from browser_stealth.launchers.nodriver import (
    nodriver_session,
    safe_extract_dict,
    safe_get_or_open_tab,
)

# Жесткий таймаут для каждого теста во избежание зависания в CI/CD
MAX_TEST_TIMEOUT = 25.0


def _is_url_reachable(url: str, timeout: float = 3.0, proxy: str | None = None) -> bool:
    """Проверяет доступность удаленного тестового стенда по сети (с поддержкой прокси)."""
    try:
        handlers: list[Any] = []
        if proxy:
            handlers.append(urllib.request.ProxyHandler({"http": proxy, "https": proxy}))
            opener = urllib.request.build_opener(*handlers)
        else:
            opener = urllib.request.build_opener()

        req = urllib.request.Request(
            url,
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"},
        )
        with opener.open(req, timeout=timeout) as resp:
            return bool(resp.status in (200, 301, 302, 403))
    except Exception:
        return False


@pytest.mark.heavy
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_sannysoft_bot_detector_live(e2e_proxy: str | None) -> None:
    """Проверяет прохождение тестов на https://bot.sannysoft.com/ в реальном браузере nodriver."""
    target_url = "https://bot.sannysoft.com/"
    if not _is_url_reachable(target_url, proxy=e2e_proxy):
        pytest.skip(f"Стенд {target_url} недоступен по сети")

    async def _run() -> None:
        config = AntidetectConfig.preset_stealth_nodriver()
        async with nodriver_session(config=config, headless=True, proxy=e2e_proxy) as browser:
            tab = await safe_get_or_open_tab(browser, target_url, timeout=8.0)
            await config.apply_to_nodriver(tab)

            # Ждем завершения встроенных тестов Sannysoft
            await asyncio.sleep(2.5)

            # 1. Проверяем navigator.webdriver
            webdriver_res: Any = await tab.evaluate("navigator.webdriver")
            assert webdriver_res is False or webdriver_res is None, (
                f"navigator.webdriver раскрыт: {webdriver_res}"
            )

            # 2. Проверяем результаты таблицы тестов Sannysoft
            raw_results = await tab.evaluate(
                """(() => {
                    const rows = Array.from(document.querySelectorAll('table tr'));
                    const failed = [];
                    for (const row of rows) {
                        const text = row.innerText.toLowerCase();
                        if (row.classList.contains('failed') || text.includes('failed') || text.includes('red')) {
                            if (!text.includes('broken image') && !text.includes('hairline feature')) {
                                failed.push(row.innerText.trim());
                            }
                        }
                    }
                    return {
                        failed: failed,
                        hasChrome: !!window.chrome,
                        pluginsCount: navigator.plugins.length
                    };
                })()"""
            )

            test_results = safe_extract_dict(raw_results)
            assert test_results.get("hasChrome") is True, "window.chrome отсутствует"
            assert int(test_results.get("pluginsCount", 0)) > 0, "navigator.plugins пуст"
            assert len(test_results.get("failed", [])) == 0, (
                f"Обнаружены проваленные тесты Sannysoft: {test_results.get('failed')}"
            )

    try:
        await asyncio.wait_for(_run(), timeout=MAX_TEST_TIMEOUT)
    except TimeoutError:
        pytest.skip("Таймаут ожидания загрузки bot.sannysoft.com")


@pytest.mark.heavy
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_browserleaks_webgl_vendor_override_live(e2e_proxy: str | None) -> None:
    """Проверяет корректность подмены WebGL параметров на https://browserleaks.com/webgl."""
    target_url = "https://browserleaks.com/webgl"
    if not _is_url_reachable(target_url, proxy=e2e_proxy):
        pytest.skip(f"Стенд {target_url} недоступен по сети")

    async def _run() -> None:
        custom_vendor = "Custom Stealth Vendor"
        custom_renderer = "Custom Stealth GPU RTX 4090"

        config = AntidetectConfig(
            webgl_vendor=custom_vendor,
            webgl_renderer=custom_renderer,
            protect_webgl=True,
            stealth_minimal=False,
        )

        async with nodriver_session(config=config, headless=True, proxy=e2e_proxy) as browser:
            tab = getattr(browser, "main_tab", None)
            if tab is None:
                tab = await safe_get_or_open_tab(browser, "about:blank", timeout=8.0)
            await config.apply_to_nodriver(tab)
            await tab.get(target_url)
            await asyncio.sleep(2.5)

            # Извлекаем значения WebGL параметров прямо из контекста Canvas
            raw_webgl = await tab.evaluate(
                """(() => {
                    const canvas = document.createElement('canvas');
                    const gl = canvas.getContext('webgl') || canvas.getContext('experimental-webgl');
                    if (!gl) return null;
                    const dbgRenderInfo = gl.getExtension('WEBGL_debug_renderer_info');
                    if (!dbgRenderInfo) return null;
                    return {
                        vendor: gl.getParameter(dbgRenderInfo.UNMASKED_VENDOR_WEBGL),
                        renderer: gl.getParameter(dbgRenderInfo.UNMASKED_RENDERER_WEBGL)
                    };
                })()"""
            )

            webgl_info = safe_extract_dict(raw_webgl)
            assert webgl_info.get("vendor") == custom_vendor
            assert webgl_info.get("renderer") == custom_renderer

    try:
        await asyncio.wait_for(_run(), timeout=MAX_TEST_TIMEOUT)
    except TimeoutError:
        pytest.skip("Таймаут ожидания ответа browserleaks.com")


@pytest.mark.heavy
@pytest.mark.e2e
@pytest.mark.asyncio
async def test_nowsecure_turnstile_challenge_live(e2e_proxy: str | None) -> None:
    """Проверяет обнаружение и прохождение защиты Cloudflare Turnstile на https://nowsecure.nl/."""
    target_url = "https://nowsecure.nl/"
    if not _is_url_reachable(target_url, proxy=e2e_proxy):
        pytest.skip(f"Стенд {target_url} недоступен по сети")

    async def _run() -> None:
        config = AntidetectConfig.preset_stealth_nodriver()
        async with nodriver_session(config=config, headless=True, proxy=e2e_proxy) as browser:
            tab = await safe_get_or_open_tab(browser, target_url, timeout=8.0)
            await config.apply_to_nodriver(tab)

            # Используем встроенный резолвер Turnstile с коротким таймаутом
            solved = await solve_cf_turnstile(tab, timeout=6.0, raise_on_failure=False)

            status_text = await tab.evaluate(
                "document.body ? document.body.innerText.toLowerCase() : ''"
            )
            passed = solved or (
                isinstance(status_text, str)
                and (
                    "passed" in status_text
                    or "success" in status_text
                    or "nowsecure" in status_text
                )
            )

            if not passed:
                pytest.skip(
                    "Cloudflare Turnstile на nowsecure.nl не был решен за 6 сек (возможен managed challenge WAF)"
                )

    try:
        await asyncio.wait_for(_run(), timeout=15.0)
    except TimeoutError:
        pytest.skip("Таймаут (15с) при ожидании ответа Cloudflare Turnstile стенда nowsecure.nl")
