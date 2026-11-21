"""Каскадный поиск элементов за один CDP-вызов.

Последовательные ``tab.select()`` с таймаутами накапливают секунды ожидания,
если первые селекторы устарели после A/B-теста. Здесь все CSS-селекторы
проверяются одним JavaScript-вызовом ``document.querySelector``; только
найденный селектор превращается в нативный Element. Текстовые маркеры — это
безопасный fallback, который не обходит кросс-доменные iframe.
"""

from __future__ import annotations

import asyncio
import json
from collections.abc import Sequence
from inspect import isawaitable
from typing import Any

from browser_stealth.humanize.safe_find import async_find_by_text
from browser_stealth.logging import get_logger

logger = get_logger(__name__)

_JS_FIND_FIRST_SELECTOR = """
(function(selectors) {
  for (var i = 0; i < selectors.length; i++) {
    try {
      if (document.querySelector(selectors[i])) return selectors[i];
    } catch (e) {}
  }
  return null;
})
"""


def _as_sequence(value: str | Sequence[str] | None) -> list[str]:
    """Приводит строку или последовательность селекторов к списку строк."""
    if value is None:
        return []
    if isinstance(value, str):
        value = [value]
    return [str(item).strip() for item in value if str(item).strip()]


async def _select(tab: Any, selector: str, timeout: float) -> Any | None:
    """Получает нативный Element по селектору с поддержкой старого API."""
    select = getattr(tab, "select", None)
    if not callable(select):
        return None
    try:
        result = select(selector, timeout=timeout)
    except TypeError:
        result = select(selector)
    if not isawaitable(result):
        return result
    try:
        return await asyncio.wait_for(result, timeout=timeout)
    except TimeoutError:
        logger.debug("Таймаут получения Element по селектору %s", selector)
        return None
    except Exception as exc:
        logger.debug("Не удалось получить Element по селектору %s: %s", selector, exc)
        return None


async def async_find_cascade(
    tab: Any,
    selectors: str | Sequence[str],
    text_markers: str | Sequence[str] | None = None,
    *,
    timeout: float = 5.0,
) -> tuple[Any | None, str | None]:
    """Ищет элемент по списку CSS-селекторов, затем по текстовым маркерам.

    CSS-селекторы проверяются атомарно одним вызовом JavaScript. Это даёт один
    RTT вместо серии ``tab.select()`` с накоплением таймаутов. Если ни один
    селектор не подошёл, маркеры ищутся через
    :func:`browser_stealth.humanize.safe_find.async_find_by_text`, который
    ограничен основным документом и не зависает на сторонних iframe.

    Args:
        tab: Вкладка nodriver или совместимый объект с ``evaluate``/``select``.
        selectors: CSS-селектор или последовательность селекторов от primary к fallback.
        text_markers: Текст или последовательность текстовых маркеров для fallback.
        timeout: Таймаут одного JavaScript-вызова или получения Element.

    Returns:
        Кортеж ``(element, matched_by)``. ``matched_by`` — сработавший CSS-селектор
        или ``text:<marker>``. Если ничего не найдено, возвращается ``(None, None)``.

    Example:
        >>> element, matched = await inspect.async_find_cascade(
        ...     tab,
        ...     ["[data-qa='submit']", "button[type='submit']"],
        ...     text_markers=["Отправить"],
        ... )
    """
    selector_list = _as_sequence(selectors)
    marker_list = _as_sequence(text_markers)
    if tab is None or (not selector_list and not marker_list):
        return None, None

    evaluate = getattr(tab, "evaluate", None)
    if selector_list and callable(evaluate):
        script = f"({_JS_FIND_FIRST_SELECTOR})({json.dumps(selector_list, ensure_ascii=False)})"
        try:
            matched = await asyncio.wait_for(evaluate(script), timeout=timeout)
        except TimeoutError:
            logger.debug("Таймаут атомарного поиска по каскаду селекторов")
            matched = None
        except Exception as exc:
            logger.debug("Ошибка атомарного поиска по каскаду: %s", exc)
            matched = None

        if isinstance(matched, str) and matched:
            element = await _select(tab, matched, timeout)
            if element is not None:
                return element, matched

    # Совместимость с объектами без evaluate: последовательный select.
    if selector_list and not callable(evaluate):
        for selector in selector_list:
            element = await _select(tab, selector, timeout)
            if element is not None:
                return element, selector

    for marker in marker_list:
        try:
            element = await async_find_by_text(tab, marker, timeout=timeout)
        except Exception as exc:
            logger.debug("Ошибка поиска по текстовому маркеру %s: %s", marker, exc)
            continue
        if element is not None:
            return element, f"text:{marker}"

    return None, None


__all__ = ["async_find_cascade"]
