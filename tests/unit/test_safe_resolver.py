"""Тесты безопасного резолвера элементов и защиты Tab.find (Issue #05)."""

from __future__ import annotations

import asyncio
import shutil
import subprocess
from unittest.mock import AsyncMock

import pytest

from browser_stealth.humanize.actions import async_scroll_to
from browser_stealth.humanize.safe_find import (
    _JS_FIND_BY_TEXT,
    MATCH_ATTRIBUTE,
    async_find_by_text,
    install_safe_find,
    safe_find_element,
)


class FakeProtocolException(Exception):
    """Имитация nodriver ProtocolException(-32601) у стороннего фрейма."""

    code = -32601


class FakeElement:
    """Минимальный нативный элемент, возвращаемый page.select()."""


class FakePage:
    """Вкладка с JS-поиском, возвращающая заданный результат."""

    def __init__(self, found: bool = True) -> None:
        self.found = found
        self.element = FakeElement()
        self.evaluate_calls: list[str] = []
        self.select_calls: list[tuple[str, float]] = []

    async def evaluate(self, script: str) -> object:
        self.evaluate_calls.append(script)
        if "querySelectorAll" in script:
            return "bs-marker-value" if self.found else None
        return True

    async def select(self, selector: str, timeout: float = 10) -> object:
        self.select_calls.append((selector, timeout))
        return self.element


@pytest.mark.asyncio
async def test_async_find_by_text_returns_element_and_cleans_marker() -> None:
    """Проверяет получение Element через маркер и удаление временного атрибута."""
    page = FakePage(found=True)

    element = await async_find_by_text(page, "Войти")

    assert element is page.element
    assert page.select_calls, "page.select должен получить элемент по маркеру"
    selector, _ = page.select_calls[0]
    assert MATCH_ATTRIBUTE in selector
    assert page.evaluate_calls[-1].count("removeAttribute") == 1


@pytest.mark.asyncio
async def test_async_find_by_text_returns_none_for_invisible_or_missing() -> None:
    """Проверяет, что при отсутствии видимого текста Element не запрашивается."""
    page = FakePage(found=False)

    element = await async_find_by_text(page, "Скрытый элемент")

    assert element is None
    assert page.select_calls == []


@pytest.mark.asyncio
async def test_safe_find_element_uses_substring_by_default() -> None:
    """Проверяет, что алиас safe_find_element выполняет поиск по подстроке."""
    page = FakePage(found=True)

    element = await safe_find_element(page, "часть текста")

    assert element is page.element
    find_script = next(s for s in page.evaluate_calls if "querySelectorAll" in s)
    assert "false" in find_script  # exact=False
    assert "contentWindow" not in find_script


def test_find_js_filters_invisible_nodes_and_never_touches_frames() -> None:
    """Проверяет наличие проверок видимости и отсутствие обхода фреймов в JS."""
    page = FakePage(found=True)
    asyncio.run(async_find_by_text(page, "Текст"))

    find_script = next(s for s in page.evaluate_calls if "querySelectorAll" in s)
    assert "getBoundingClientRect" in find_script
    assert "offsetParent" in find_script
    assert "getComputedStyle" in find_script
    assert "contentWindow" not in find_script
    assert "document.body.querySelectorAll" in find_script


@pytest.mark.asyncio
async def test_install_safe_find_does_not_call_native_iframe_search() -> None:
    """Проверяет, что по умолчанию нативный Tab.find с обходом iframe не вызывается."""
    page = FakePage(found=False)
    native_find = AsyncMock(side_effect=AssertionError("нативный find не должен вызываться"))
    page.find = native_find

    install_safe_find(page, search_iframes=False)
    result = await page.find("Отсутствующий текст")

    assert result is None
    native_find.assert_not_awaited()


@pytest.mark.asyncio
async def test_install_safe_find_swallows_protocol_exception_with_frames() -> None:
    """Проверяет, что ошибка -32601 у стороннего фрейма не всплывает наружу."""
    page = FakePage(found=False)

    async def native_find(text, best_match=True, return_enclosing_element=True, timeout=10):
        raise FakeProtocolException("'DOM.getDocument' wasn't found")

    page.find = native_find
    install_safe_find(page, search_iframes=True)

    assert await page.find("Отсутствующий текст") is None


@pytest.mark.asyncio
async def test_safe_find_leaves_no_orphan_tasks() -> None:
    """Проверяет, что поиск не создает фоновых задач после завершения."""
    page = FakePage(found=False)
    page.find = AsyncMock()
    install_safe_find(page, search_iframes=False)

    before = asyncio.all_tasks()
    await page.find("Нет такого текста")
    await asyncio.sleep(0)
    leftover = asyncio.all_tasks() - before

    assert not leftover, f"Остались фоновые задачи: {leftover}"


@pytest.mark.skipif(shutil.which("node") is None, reason="Node.js не установлен")
def test_safe_find_js_skips_hidden_and_script_nodes() -> None:
    """Проверяет в runtime, что JS-поиск игнорирует невидимые узлы и <script>."""
    node_script = f"""
    const assert = require('assert');
    const find = {_JS_FIND_BY_TEXT};

    function textNode(text) {{ return {{ nodeType: 3, textContent: text }}; }}
    function makeEl(tag, text, visible) {{
        return {{
            tagName: tag,
            childNodes: text === null ? [] : [textNode(text)],
            attrs: {{}},
            style: {{ position: 'static' }},
            offsetParent: visible ? {{}} : null,
            getBoundingClientRect: () => (visible ? {{ width: 120, height: 24 }} : {{ width: 0, height: 0 }}),
            setAttribute: function(key, value) {{ this.attrs[key] = value; }}
        }};
    }}

    const hidden = makeEl('BUTTON', 'Отправить', false);
    const scriptNode = makeEl('SCRIPT', 'Отправить', true);
    const visible = makeEl('BUTTON', 'Отправить форму', true);
    const nodes = [hidden, scriptNode, visible];

    global.window = globalThis;
    global.window.getComputedStyle = () => ({{ visibility: 'visible', display: 'block', opacity: '1', position: 'static' }});
    global.document = {{ body: {{ querySelectorAll: () => nodes }} }};

    // Подстрочный поиск: невидимая кнопка и script пропускаются
    assert.strictEqual(find('Отправить', false, 'data-bs-match', 'm1'), 'm1');
    assert.strictEqual(visible.attrs['data-bs-match'], 'm1');
    assert.strictEqual(hidden.attrs['data-bs-match'], undefined);
    assert.strictEqual(scriptNode.attrs['data-bs-match'], undefined);

    // Точное совпадение: видимый текст 'Отправить форму' не равен 'Отправить'
    assert.strictEqual(find('Отправить', true, 'data-bs-match', 'm2'), null);
    console.log('SAFE_FIND_JS_PASSED');
    """

    result = subprocess.run(
        ["node", "-e", node_script],
        check=False,
        capture_output=True,
        text=True,
        timeout=30,
    )

    assert result.returncode == 0, result.stderr
    assert "SAFE_FIND_JS_PASSED" in result.stdout


@pytest.mark.asyncio
async def test_actions_exit_gracefully_when_connection_closed() -> None:
    """Проверяет штатное завершение действия при закрытом WebSocket браузера."""
    from websockets.exceptions import ConnectionClosed

    page = AsyncMock()
    page.send = AsyncMock()
    page.evaluate = AsyncMock(side_effect=ConnectionClosed(None, None))

    assert await async_scroll_to(page, 0, 500) is None
