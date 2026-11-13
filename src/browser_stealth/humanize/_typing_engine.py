"""Посимочный ввод и DOM/CDP-вставка текста для Playwright и nodriver."""

from __future__ import annotations

import asyncio
import json
import random
import sys
from typing import Any

from browser_stealth.logging import get_logger as setup_logger

from ._deps import _ensure_nodriver, _ensure_playwright

logger = setup_logger(__name__)


JS_DOM_PASTE_SCRIPT = (
    "(function(sel, val) {"
    "  var el = document.querySelector(sel);"
    "  if (!el) return false;"
    "  var proto = Object.getPrototypeOf(el);"
    "  var desc = Object.getOwnPropertyDescriptor(proto, 'value') || "
    "             Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value') || "
    "             Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');"
    "  try {"
    "    el.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, cancelable: true, inputType: 'insertFromPaste', data: val }));"
    "  } catch (e) {}"
    "  if (desc && desc.set) {"
    "    desc.set.call(el, val);"
    "  } else if ('value' in el) {"
    "    el.value = val;"
    "  } else {"
    "    el.textContent = val;"
    "  }"
    "  try {"
    "    el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertFromPaste', data: val }));"
    "  } catch (e) {"
    "    el.dispatchEvent(new Event('input', { bubbles: true }));"
    "  }"
    "  el.dispatchEvent(new Event('change', { bubbles: true }));"
    "  return true;"
    "})"
)


JS_DOM_HEAL_SCRIPT = (
    "(function(sel, expected) {"
    "  var el = document.querySelector(sel);"
    "  if (!el) return;"
    "  var current = el.value !== undefined ? el.value : el.textContent;"
    "  if (current !== expected) {"
    "    var proto = Object.getPrototypeOf(el);"
    "    var desc = Object.getOwnPropertyDescriptor(proto, 'value') || "
    "               Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value') || "
    "               Object.getOwnPropertyDescriptor(HTMLTextAreaElement.prototype, 'value');"
    "    try {"
    "      el.dispatchEvent(new InputEvent('beforeinput', { bubbles: true, cancelable: true, inputType: 'insertReplacementText', data: expected }));"
    "    } catch (e) {}"
    "    if (desc && desc.set) {"
    "      desc.set.call(el, expected);"
    "    } else if ('value' in el) {"
    "      el.value = expected;"
    "    } else {"
    "      el.textContent = expected;"
    "    }"
    "    try {"
    "      el.dispatchEvent(new InputEvent('input', { bubbles: true, inputType: 'insertReplacementText', data: expected }));"
    "    } catch (e) {"
    "      el.dispatchEvent(new Event('input', { bubbles: true }));"
    "    }"
    "    el.dispatchEvent(new Event('change', { bubbles: true }));"
    "  }"
    "})"
)


async def _dom_safe_paste(page: Any, selector: str, text: str) -> bool:
    """Безопасно вставляет текст через DOM Prototype Setter с диспатчем input/change.

    Args:
        page: Объект страницы Playwright или вкладки nodriver.
        selector: CSS-селектор целевого элемента.
        text: Вставляемый текст.

    Returns:
        True, если вставка через JS выполнена успешно, иначе False.
    """
    if hasattr(page, "evaluate") and callable(page.evaluate):
        try:
            res = await page.evaluate(
                f"({JS_DOM_PASTE_SCRIPT})({json.dumps(selector)}, {json.dumps(text)})"
            )
            return res is True
        except Exception:
            return False
    return False


async def _dom_safe_heal(page: Any, selector: str, expected_text: str) -> None:
    """Выполняет сверку и самовосстановление значения поля ввода через DOM.

    Args:
        page: Объект страницы Playwright или вкладки nodriver.
        selector: CSS-селектор целевого элемента.
        expected_text: Ожидаемый итоговый текст.
    """
    if hasattr(page, "evaluate") and callable(page.evaluate):
        try:
            await page.evaluate(
                f"({JS_DOM_HEAL_SCRIPT})({json.dumps(selector)}, {json.dumps(expected_text)})"
            )
        except Exception:
            pass


async def _cdp_native_paste(
    page: Any,
    selector: str,
    text: str,
    *,
    is_mac: bool = False,
) -> bool:
    """Выполняет нативную CDP-вставку текста через изолированный буфер обмена и шорткат Ctrl+V / Cmd+V.

    Args:
        page: Вкладка nodriver (Tab).
        selector: CSS-селектор целевого элемента.
        text: Текст для вставки.
        is_mac: Если True, использует Command (modifiers=8), иначе Control (modifiers=2).

    Returns:
        True, если нативная вставка выполнена успешно, иначе False.
    """
    _ensure_nodriver()
    from nodriver.cdp import input_ as cdp_input

    try:
        from browser_stealth.antidetect.clipboard import set_isolated_clipboard_text

        # 1. Помещаем текст в изолированный буфер обмена вкладки
        await set_isolated_clipboard_text(page, text)

        # 2. Фокусируем элемент
        element = await page.find(selector)
        await element.focus()

        # 3. Отправляем нативные CDP нажатия клавиш Ctrl+V / Cmd+V с командой paste
        modifiers = 8 if is_mac else 2
        mod_key = "Meta" if is_mac else "Control"
        mod_code = "MetaLeft" if is_mac else "ControlLeft"
        vk_code = 91 if is_mac else 17

        await page.send(
            cdp_input.dispatch_key_event(
                type_="rawKeyDown",
                key=mod_key,
                code=mod_code,
                windows_virtual_key_code=vk_code,
                native_virtual_key_code=vk_code,
                modifiers=modifiers,
            )
        )
        await page.send(
            cdp_input.dispatch_key_event(
                type_="rawKeyDown",
                key="v",
                code="KeyV",
                windows_virtual_key_code=86,
                native_virtual_key_code=86,
                modifiers=modifiers,
                commands=["paste"],
            )
        )
        await page.send(
            cdp_input.dispatch_key_event(
                type_="keyUp",
                key="v",
                code="KeyV",
                windows_virtual_key_code=86,
                native_virtual_key_code=86,
                modifiers=modifiers,
            )
        )
        await page.send(
            cdp_input.dispatch_key_event(
                type_="keyUp",
                key=mod_key,
                code=mod_code,
                windows_virtual_key_code=vk_code,
                native_virtual_key_code=vk_code,
            )
        )
        return True
    except Exception as exc:
        logger.debug("Сбой нативной вставки через CDP paste shortcut: %s", exc)
        return False


async def _async_type_nodriver(
    page: Any,
    selector: str,
    text: str,
    *,
    error_rate: float,
    speed_wpm: float,
    key_hold_time: tuple[float, float],
    layout_error_rate: float,
    delayed_fix_rate: float,
    paste_threshold: int | None,
    paste_delay_before: tuple[float, float],
    paste_delay_after: tuple[float, float],
    delay_gen: Any,
    typo_gen: Any,
    paste_mode: str = "cdp_insert",
) -> None:
    """Выполняет посимвольный ввод или paste для nodriver."""
    _ensure_nodriver()
    from nodriver.cdp import input_ as cdp_input

    element = await page.find(selector)
    await element.focus()

    if paste_threshold is not None and len(text) >= paste_threshold:
        if paste_delay_before and paste_delay_before[1] > 0:
            await asyncio.sleep(random.uniform(*paste_delay_before))

        if paste_mode == "cdp_paste":
            success = await _cdp_native_paste(page, selector, text)
            if not success:
                await page.send(cdp_input.insert_text(text=text))
        elif paste_mode == "dom":
            pasted = await _dom_safe_paste(page, selector, text)
            if not pasted:
                await page.send(cdp_input.insert_text(text=text))
        else:  # по умолчанию "cdp_insert"
            try:
                await page.send(cdp_input.insert_text(text=text))
            except Exception:
                await _dom_safe_paste(page, selector, text)

        if paste_delay_after and paste_delay_after[1] > 0:
            await asyncio.sleep(random.uniform(*paste_delay_after))
        return

    char_delay = 60.0 / (speed_wpm * 5)
    sequence = typo_gen.generate_sequence(
        text,
        error_rate=error_rate,
        layout_error_rate=layout_error_rate,
        delayed_fix_rate=delayed_fix_rate,
    )

    for action in sequence:
        if action.action == "type":
            c = action.char
            await page.send(
                cdp_input.dispatch_key_event(type_="keyDown", text=c, unmodified_text=c, key=c)
            )
            if key_hold_time and key_hold_time[1] > 0:
                await asyncio.sleep(random.uniform(*key_hold_time))
            await page.send(
                cdp_input.dispatch_key_event(type_="keyUp", text=c, unmodified_text=c, key=c)
            )
        elif action.action == "backspace":
            await page.send(
                cdp_input.dispatch_key_event(
                    type_="rawKeyDown",
                    key="Backspace",
                    code="Backspace",
                    windows_virtual_key_code=8,
                    native_virtual_key_code=8,
                    commands=["deleteContentBackward"],
                )
            )
            if key_hold_time and key_hold_time[1] > 0:
                await asyncio.sleep(random.uniform(*key_hold_time))
            await page.send(
                cdp_input.dispatch_key_event(
                    type_="keyUp",
                    key="Backspace",
                    code="Backspace",
                    windows_virtual_key_code=8,
                    native_virtual_key_code=8,
                )
            )
        elif action.action == "key":
            k = action.char
            vk = {
                "ArrowLeft": 37,
                "ArrowUp": 38,
                "ArrowRight": 39,
                "ArrowDown": 40,
                "Backspace": 8,
                "Enter": 13,
            }.get(k, 0)
            extra: dict[str, Any] = (
                {"commands": ["deleteContentBackward"]} if k == "Backspace" else {}
            )
            await page.send(
                cdp_input.dispatch_key_event(
                    type_="rawKeyDown",
                    key=k,
                    code=k,
                    windows_virtual_key_code=vk,
                    native_virtual_key_code=vk,
                    **extra,
                )
            )
            if key_hold_time and key_hold_time[1] > 0:
                await asyncio.sleep(random.uniform(*key_hold_time))
            await page.send(
                cdp_input.dispatch_key_event(
                    type_="keyUp",
                    key=k,
                    code=k,
                    windows_virtual_key_code=vk,
                    native_virtual_key_code=vk,
                )
            )

        delay = delay_gen.generate(char_delay)
        if delay > 0:
            await asyncio.sleep(delay)

    await _dom_safe_heal(page, selector, text)


async def _async_type_playwright(
    page: Any,
    selector: str,
    text: str,
    *,
    error_rate: float,
    speed_wpm: float,
    layout_error_rate: float,
    delayed_fix_rate: float,
    paste_threshold: int | None,
    paste_delay_before: tuple[float, float],
    paste_delay_after: tuple[float, float],
    delay_gen: Any,
    typo_gen: Any,
    paste_mode: str = "cdp_insert",
) -> None:
    """Выполняет посимвольный ввод или paste для Playwright."""
    _ensure_playwright()
    await page.focus(selector)

    if paste_threshold is not None and len(text) >= paste_threshold:
        if paste_delay_before and paste_delay_before[1] > 0:
            await asyncio.sleep(random.uniform(*paste_delay_before))

        if paste_mode == "cdp_paste":
            try:
                from browser_stealth.antidetect.clipboard import set_isolated_clipboard_text

                await set_isolated_clipboard_text(page, text)
                mod = "Meta" if sys.platform == "darwin" else "Control"
                await page.keyboard.press(f"{mod}+KeyV")
            except Exception:
                await page.keyboard.insert_text(text)
        elif paste_mode == "dom":
            pasted = await _dom_safe_paste(page, selector, text)
            if not pasted:
                await page.keyboard.insert_text(text)
        else:
            await page.keyboard.insert_text(text)

        if paste_delay_after and paste_delay_after[1] > 0:
            await asyncio.sleep(random.uniform(*paste_delay_after))
        return

    char_delay = 60.0 / (speed_wpm * 5)
    sequence = typo_gen.generate_sequence(
        text,
        error_rate=error_rate,
        layout_error_rate=layout_error_rate,
        delayed_fix_rate=delayed_fix_rate,
    )

    for action in sequence:
        if action.action == "type":
            await page.keyboard.type(action.char)
        elif action.action == "backspace":
            await page.keyboard.press("Backspace")
        elif action.action == "key":
            await page.keyboard.press(action.char)

        delay = delay_gen.generate(char_delay)
        if delay > 0:
            await asyncio.sleep(delay)

    await _dom_safe_heal(page, selector, text)
