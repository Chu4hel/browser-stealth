"""Тесты безопасной вставки в controlled inputs React/Vue/Angular."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest

from browser_stealth.humanize._typing_engine import (
    async_safe_insert_text,
    safe_dom_insert_text,
)
from browser_stealth.humanize.actions import async_type_text


@pytest.mark.asyncio
async def test_safe_dom_insert_text_uses_native_setter_and_events() -> None:
    """Вставка использует прототип value и beforeinput/input/change."""
    tab = AsyncMock()
    tab.evaluate = AsyncMock(return_value=True)

    result = await safe_dom_insert_text(tab, "#answer", "Готово")

    assert result is True
    script = tab.evaluate.call_args.args[0]
    assert "Object.getPrototypeOf" in script
    assert "getOwnPropertyDescriptor" in script
    assert "desc.set.call" in script
    assert "beforeinput" in script
    assert "insertFromPaste" in script
    assert "dispatchEvent" in script


@pytest.mark.asyncio
async def test_async_safe_insert_text_alias_and_timeout() -> None:
    """Алиас работает, а зависший evaluate не блокирует вызывающий код."""
    tab = AsyncMock()
    tab.evaluate = AsyncMock(return_value=True)
    assert await async_safe_insert_text(tab, "#answer", "Текст") is True

    slow_tab = AsyncMock()

    async def slow_evaluate(script: str) -> bool:
        await asyncio.sleep(1.0)
        return True

    slow_tab.evaluate = slow_evaluate
    assert await safe_dom_insert_text(slow_tab, "#answer", "Текст", timeout=0.01) is False


@pytest.mark.asyncio
async def test_async_type_text_can_disable_react_fallback() -> None:
    """react_fallback=False отключает DOM self-healing после посимвольного ввода."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.select = AsyncMock()
    tab.send = AsyncMock()
    tab.evaluate = AsyncMock()

    element = AsyncMock()
    element._is_nodriver = True
    tab.select.return_value = element

    await async_type_text(
        tab,
        selector="#answer",
        text="ok",
        error_rate=0.0,
        speed_wpm=500.0,
        react_fallback=False,
    )

    tab.evaluate.assert_not_awaited()
