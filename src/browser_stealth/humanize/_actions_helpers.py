"""Вспомогательные утилиты, проверки зависимостей и маппинги клавиш для humanize actions."""

from __future__ import annotations

import asyncio
import json
import random
import time
from collections.abc import Coroutine
from typing import Any

from browser_stealth.logging import get_logger as setup_logger

from ._deps import (
    _ensure_nodriver,
    _ensure_playwright,
    _ensure_selenium,
    _is_nodriver,
    _is_playwright,
)
from ._typing_engine import (
    JS_DOM_HEAL_SCRIPT,
    JS_DOM_PASTE_SCRIPT,
    _async_type_nodriver,
    _async_type_playwright,
)

# Реэкспорт проверок зависимостей, JS-скриптов и движка ввода для обратной совместимости.

__all__ = [
    "JS_DOM_HEAL_SCRIPT",
    "JS_DOM_PASTE_SCRIPT",
    "_async_type_nodriver",
    "_async_type_playwright",
    "_build_selenium_key_map",
    "_ensure_nodriver",
    "_ensure_playwright",
    "_ensure_selenium",
    "_generate_scroll_points",
    "_is_connection_closed",
    "_is_nodriver",
    "_is_playwright",
    "_resolve_async_element_coordinates",
    "_run_with_timeout",
    "_safe_get_async_url",
    "async_human_sleep",
    "click",
    "human_sleep",
]

logger = setup_logger(__name__)

try:  # websockets доступен как транзитивная зависимость nodriver
    from websockets.exceptions import ConnectionClosed as _WebsocketsConnectionClosed
except (ImportError, AttributeError):  # pragma: no cover - websockets не установлен
    _WebsocketsConnectionClosed = None  # type: ignore[assignment,misc]


def _is_connection_closed(exc: BaseException) -> bool:
    """Определяет, вызвано ли исключение закрытием WebSocket-соединения с браузером.

    Args:
        exc: Перехваченное исключение.

    Returns:
        True, если браузер закрыт или соединение с CDP оборвано.
    """
    if _WebsocketsConnectionClosed is not None and isinstance(exc, _WebsocketsConnectionClosed):
        return True
    return type(exc).__name__ in {
        "ConnectionClosed",
        "ConnectionClosedError",
        "ConnectionClosedOK",
    }


async def _run_with_timeout(
    coro: Coroutine[Any, Any, Any],
    timeout: float | None = None,
) -> Any:
    """Выполняет корутину с опциональным ограничением по таймауту.

    Args:
        coro: Асинхронная корутина.
        timeout: Таймаут в секундах. Если None, выполняется без таймаута.

    Returns:
        Результат выполнения корутины или None, если браузер был закрыт.

    Raises:
        TimeoutError: При превышении допустимого таймаута.
    """
    try:
        if timeout is not None:
            return await asyncio.wait_for(coro, timeout=timeout)
        return await coro
    except TimeoutError as exc:
        raise TimeoutError(f"Действие превысило допустимый таймаут {timeout}с") from exc
    except Exception as exc:
        if _is_connection_closed(exc):
            logger.debug("Соединение с браузером закрыто, действие прервано штатно: %s", exc)
            return None
        raise


async def _safe_get_async_url(page_or_tab: Any) -> str:
    """Безопасно извлекает текущий URL страницы из объекта Playwright Page или nodriver Tab.

    Учитывает различия версий nodriver, где url может отсутствовать как прямой атрибут,
    находиться в target.url или требовать выполнения JavaScript window.location.href.

    Args:
        page_or_tab: Объект Playwright Page или nodriver Tab.

    Returns:
        Строка с текущим URL-адресом или пустая строка в случае неудачи.
    """
    if page_or_tab is None:
        return ""

    # 1. Прямой атрибут .url (Playwright, некоторые версии nodriver)
    url_attr = getattr(page_or_tab, "url", None)
    if isinstance(url_attr, str) and url_attr:
        return url_attr
    if callable(url_attr):
        try:
            res = url_attr()
            if isinstance(res, str) and res:
                return res
        except Exception:
            pass

    # 2. Атрибут .target.url (nodriver Tab.target)
    target = getattr(page_or_tab, "target", None)
    if target is not None:
        target_url = getattr(target, "url", None)
        if isinstance(target_url, str) and target_url:
            return target_url

    # 3. Fallback через evaluate JS
    if hasattr(page_or_tab, "evaluate") and callable(page_or_tab.evaluate):
        try:
            eval_res = await page_or_tab.evaluate("window.location.href")
            if isinstance(eval_res, str) and eval_res:
                return eval_res
        except Exception:
            pass

    return ""


def _get_lognormal_delay(min_seconds: float, max_seconds: float) -> float:
    """Генерирует логнормальное случайное время в заданном интервале.

    Args:
        min_seconds: Минимальное время задержки (в секундах).
        max_seconds: Максимальное время задержки (в секундах).

    Returns:
        Случайное значение задержки с нормальным/логнормальным распределением.
    """
    if min_seconds <= 0:
        return 0.0
    if min_seconds >= max_seconds:
        return min_seconds

    mean = (min_seconds + max_seconds) / 2
    sigma = (max_seconds - min_seconds) / 6.0  # 3-сигма правило
    val = random.gauss(mean, sigma)
    return max(min_seconds, min(val, max_seconds))


def human_sleep(min_seconds: float, max_seconds: float) -> None:
    """Синхронно задерживает выполнение на случайное время, имитируя поведение человека.

    Args:
        min_seconds: Минимальное время задержки (в секундах).
        max_seconds: Максимальное время задержки (в секундах).
    """
    import time

    delay = _get_lognormal_delay(min_seconds, max_seconds)
    time.sleep(delay)


async def async_human_sleep(min_seconds: float, max_seconds: float) -> None:
    """Асинхронно задерживает выполнение на случайное время, имитируя поведение человека.

    Args:
        min_seconds: Минимальное время задержки (в секундах).
        max_seconds: Максимальное время задержки (в секундах).
    """
    import asyncio

    delay = _get_lognormal_delay(min_seconds, max_seconds)
    await asyncio.sleep(delay)


def _build_selenium_key_map(keys_cls: Any) -> dict[str, Any]:
    """Строит маппинг строковых идентификаторов клавиш на константы Selenium Keys.

    Args:
        keys_cls: Класс selenium.webdriver.common.keys.Keys.

    Returns:
        Словарь соответствия символов константам Selenium Keys.
    """
    return {
        "ArrowLeft": getattr(keys_cls, "ARROW_LEFT", "ArrowLeft"),
        "ArrowRight": getattr(keys_cls, "ARROW_RIGHT", "ArrowRight"),
        "End": getattr(keys_cls, "END", "End"),
        "Home": getattr(keys_cls, "HOME", "Home"),
        "Backspace": getattr(keys_cls, "BACKSPACE", "Backspace"),
        "Delete": getattr(keys_cls, "DELETE", "Delete"),
    }


def _generate_scroll_points(
    start_x: int, start_y: int, target_x: int, target_y: int, steps: int
) -> list[tuple[int, int]]:
    """Генерирует промежуточные координаты для плавного скроллинга.

    Args:
        start_x: Текущая координата X.
        start_y: Текущая координата Y.
        target_x: Конечная координата X.
        target_y: Конечная координата Y.
        steps: Количество промежуточных шагов.

    Returns:
        Список пар координат (px, py).
    """
    points: list[tuple[int, int]] = []
    for i in range(steps):
        t = (i + 1) / steps
        px = int(start_x + (target_x - start_x) * t)
        py = int(start_y + (target_y - start_y) * t)
        points.append((px, py))
    return points


async def _resolve_async_element_coordinates(page: Any, selector: str) -> tuple[int, int]:
    """Определяет координаты клика внутри элемента для Playwright или nodriver."""
    if _is_nodriver(page):
        _ensure_nodriver()
        # 1. Сначала пробуем получить точные экранные координаты через JS getBoundingClientRect()
        # Это работает со сложными селекторами, псевдоклассами, запятыми, CDK Overlay и Shadow DOM
        if hasattr(page, "evaluate") and callable(page.evaluate):
            try:
                js_rect = (
                    "(function(sel) {"
                    "  var el = document.querySelector(sel);"
                    "  if (!el) return null;"
                    "  var rect = el.getBoundingClientRect();"
                    "  return {"
                    "    x: rect.left,"
                    "    y: rect.top,"
                    "    width: rect.width,"
                    "    height: rect.height"
                    "  };"
                    "})"
                )
                box_dict = await page.evaluate(f"({js_rect})({json.dumps(selector)})")
                if isinstance(box_dict, dict) and "x" in box_dict and "y" in box_dict:
                    bx = float(box_dict.get("x", 0.0))
                    by = float(box_dict.get("y", 0.0))
                    bw = float(box_dict.get("width", 0.0))
                    bh = float(box_dict.get("height", 0.0))
                    return (
                        int(bx + bw * random.uniform(0.3, 0.7)),
                        int(by + bh * random.uniform(0.3, 0.7)),
                    )
            except Exception:
                pass

        # 2. Fallback: поиск через внутренний page.find() nodriver
        try:
            elem = await page.find(selector)
            box = await elem.get_position() if hasattr(elem, "get_position") else None
            if box:
                return (
                    int(box.x + box.width * random.uniform(0.3, 0.7)),
                    int(box.y + box.height * random.uniform(0.3, 0.7)),
                )
        except Exception:
            pass

        return (100, 100)
    elif _is_playwright(page):
        _ensure_playwright()
        elem = await page.query_selector(selector) if hasattr(page, "query_selector") else None
        if elem is not None:
            box = await elem.bounding_box()
            if box:
                return (
                    int(box["x"] + box["width"] * random.uniform(0.3, 0.7)),
                    int(box["y"] + box["height"] * random.uniform(0.3, 0.7)),
                )
        return (100, 100)
    else:
        raise ValueError(
            f"Не удалось определить тип переданного объекта: {type(page)}. "
            "Убедитесь, что передан объект Playwright (Page) или nodriver (Tab/Element)."
        )


def click(
    driver: Any,
    selector: str | None = None,
    x: int | None = None,
    y: int | None = None,
    start: tuple[int, int] | None = None,
    algorithm: str = "windmouse",
    hold_time: tuple[float, float] = (0.06, 0.12),
) -> None:
    """Имитирует реалистичный клик мышью Selenium.

    Args:
        driver: Экземпляр Selenium WebDriver.
        selector: CSS-селектор целевого элемента (если x, y не заданы).
        x: Конечная координата X.
        y: Конечная координата Y.
        start: Начальные координаты курсора.
        algorithm: Алгоритм движения ('windmouse' или 'bezier').
        hold_time: Диапазон задержки удержания кнопки мыши (в секундах).
    """
    _ensure_selenium()
    from selenium.webdriver.common.action_chains import ActionChains
    from selenium.webdriver.common.by import By

    from .actions import move_mouse

    target_x = x
    target_y = y

    if target_x is None or target_y is None:
        if selector is None:
            raise ValueError("Необходимо указать координаты (x, y) или CSS-селектор selector.")
        element = driver.find_element(By.CSS_SELECTOR, selector)
        loc = element.location
        size = element.size
        target_x = int(loc["x"] + size["width"] * random.uniform(0.3, 0.7))
        target_y = int(loc["y"] + size["height"] * random.uniform(0.3, 0.7))

    move_mouse(driver, x=target_x, y=target_y, start=start, algorithm=algorithm)
    time.sleep(random.uniform(0.04, 0.12))

    hold_delay = (
        random.uniform(*hold_time) if hold_time and hold_time[1] > 0 else random.uniform(0.06, 0.12)
    )
    actions = ActionChains(driver)
    actions.click_and_hold().pause(hold_delay).release().perform()
    time.sleep(random.uniform(0.03, 0.08))
