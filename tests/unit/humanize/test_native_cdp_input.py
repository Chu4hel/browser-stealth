"""Тесты нативного CDP-ввода, изолированного буфера обмена и доверенных событий вставки."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from browser_stealth.antidetect.clipboard import (
    get_isolated_clipboard_text,
    set_isolated_clipboard_text,
)
from browser_stealth.humanize._actions_helpers import (
    JS_DOM_HEAL_SCRIPT,
    JS_DOM_PASTE_SCRIPT,
)
from browser_stealth.humanize.actions import async_type_text
from browser_stealth.humanize.behavior import BehavioralProfile


def _unpack_cdp_call(call_arg: Any) -> tuple[str, dict[str, Any]]:
    """Извлекает имя команды и аргументы из вызова tab.send (кортеж или CDP-генератор)."""
    if isinstance(call_arg, tuple):
        return call_arg[0], call_arg[1] if len(call_arg) > 1 and isinstance(
            call_arg[1], dict
        ) else {}
    if hasattr(call_arg, "__name__"):
        name = getattr(call_arg, "__name__")
        frame = getattr(call_arg, "gi_frame", None)
        return name, dict(frame.f_locals) if frame else {}
    return str(call_arg), {}


@pytest.mark.asyncio
async def test_async_type_text_cdp_insert_priority_over_dom() -> None:
    """Проверяет приоритет нативного CDP Input.insertText над DOM evaluate по умолчанию."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.find = AsyncMock()
    tab.send = AsyncMock()
    tab.evaluate = AsyncMock(return_value=True)

    mock_element = AsyncMock()
    mock_element._is_nodriver = True
    tab.find.return_value = mock_element

    text = "Длинный текст для нативной вставки через CDP Input.insertText"
    await async_type_text(
        tab,
        selector="#editor",
        text=text,
        paste_threshold=10,
        paste_delay_before=(0.0, 0.0),
        paste_delay_after=(0.0, 0.0),
    )

    # Приоритет отдается нативному CDP insert_text (isTrusted: true)
    unpacked_calls = [_unpack_cdp_call(c[0][0]) for c in tab.send.call_args_list]
    insert_calls = [c for c in unpacked_calls if c[0] == "insert_text"]
    assert len(insert_calls) == 1
    assert insert_calls[0][1].get("text") == text

    # DOM evaluate для paste не должен вызываться
    dom_paste_evals = [
        c[0][0] for c in tab.evaluate.call_args_list if "desc.set.call" in str(c[0][0])
    ]
    assert len(dom_paste_evals) == 0


@pytest.mark.asyncio
async def test_async_type_text_cdp_paste_mode_with_clipboard() -> None:
    """Проверяет режим cdp_paste: запись в изолированный буфер и нативный шорткат Ctrl+V с commands=['paste']."""
    tab = AsyncMock()
    tab._is_nodriver = True
    tab.find = AsyncMock()
    tab.send = AsyncMock()
    tab.evaluate = AsyncMock(return_value=True)

    mock_element = AsyncMock()
    mock_element._is_nodriver = True
    tab.find.return_value = mock_element

    text = "Большой фрагмент для вставки через изолированный буфер Ctrl+V"
    await async_type_text(
        tab,
        selector="#textarea",
        text=text,
        paste_threshold=10,
        paste_delay_before=(0.0, 0.0),
        paste_delay_after=(0.0, 0.0),
        paste_mode="cdp_paste",
    )

    # 1. Текст должен быть записан в изолированный клипборд вкладки через evaluate
    eval_calls = [c[0][0] for c in tab.evaluate.call_args_list]
    assert any("__lastCopiedText" in str(arg) for arg in eval_calls)

    # 2. Должны быть отправлены CDP key события: ControlLeft и KeyV с commands=['paste']
    unpacked_calls = [_unpack_cdp_call(c[0][0]) for c in tab.send.call_args_list]
    key_events = [c for c in unpacked_calls if c[0] == "dispatch_key_event"]
    assert len(key_events) >= 4

    paste_key_event = next(
        (
            k[1]
            for k in key_events
            if k[1].get("code") == "KeyV" and k[1].get("commands") == ["paste"]
        ),
        None,
    )
    assert paste_key_event is not None
    assert paste_key_event.get("modifiers") == 2


@pytest.mark.asyncio
async def test_set_and_get_isolated_clipboard_text() -> None:
    """Проверяет установку и считывание текста в изолированном буфере обмена."""
    mock_page = AsyncMock()
    mock_page.evaluate = AsyncMock(return_value=True)

    success = await set_isolated_clipboard_text(mock_page, "IsolatedSecretToken")
    assert success is True
    assert mock_page.evaluate.call_count == 1
    assert "IsolatedSecretToken" in mock_page.evaluate.call_args[0][0]

    mock_page.evaluate = AsyncMock(return_value="IsolatedSecretToken")
    retrieved = await get_isolated_clipboard_text(mock_page)
    assert retrieved == "IsolatedSecretToken"


def test_dom_scripts_trusted_input_events_structure() -> None:
    """Проверяет наличие InputEvent и beforeinput с insertFromPaste в fallback DOM скриптах."""
    assert "beforeinput" in JS_DOM_PASTE_SCRIPT
    assert "insertFromPaste" in JS_DOM_PASTE_SCRIPT
    assert "InputEvent" in JS_DOM_PASTE_SCRIPT

    assert "beforeinput" in JS_DOM_HEAL_SCRIPT
    assert "insertReplacementText" in JS_DOM_HEAL_SCRIPT
    assert "InputEvent" in JS_DOM_HEAL_SCRIPT


def test_behavioral_profile_paste_mode_configuration() -> None:
    """Проверяет дефолтное значение paste_mode в BehavioralProfile."""
    profile = BehavioralProfile(speed_wpm=180.0)
    assert profile.paste_mode == "cdp_insert"

    custom_profile = BehavioralProfile(paste_mode="cdp_paste")
    assert custom_profile.paste_mode == "cdp_paste"
