"""Безопасный резолвер элементов по видимому тексту.

Модуль заменяет рекурсивный обход фреймов в ``nodriver.Tab.find`` поиском
только в основном документе через JavaScript: сторонние iframe (реклама,
трекеры, sandbox-виджеты) не опрашиваются, поэтому CDP-ошибка
``'DOM.getDocument' wasn't found`` (code -32601) не возникает и не порождает
фоновых задач с необработанными исключениями.
"""

from __future__ import annotations

import asyncio
import json
import uuid
from typing import Any

from browser_stealth.logging import get_logger as setup_logger

logger = setup_logger(__name__)

MATCH_ATTRIBUTE = "data-bs-match"
"""Атрибут, которым временно маркируется найденный узел до получения Element."""

_JS_FIND_BY_TEXT = """
(function(text, exact, attribute, marker) {
  if (!text || !document.body || !document.body.querySelectorAll) return null;
  var target = String(text).replace(/\\s+/g, ' ').trim();
  if (!target) return null;
  var lowerTarget = target.toLowerCase();
  var nodes = document.body.querySelectorAll('*');
  var found = null;
  var foundLength = -1;
  var skipTags = { SCRIPT: 1, STYLE: 1, NOSCRIPT: 1, TEMPLATE: 1, SVG: 1, HEAD: 1 };

  for (var i = 0; i < nodes.length; i++) {
    var el = nodes[i];
    if (skipTags[el.tagName]) continue;

    var ownText = '';
    for (var j = 0; j < el.childNodes.length; j++) {
      var child = el.childNodes[j];
      if (child.nodeType === 3) ownText += child.textContent;
    }
    ownText = ownText.replace(/\\s+/g, ' ').trim();
    if (!ownText) continue;

    var isMatch = exact
      ? ownText === target
      : ownText.toLowerCase().indexOf(lowerTarget) !== -1;
    if (!isMatch) continue;

    var rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
    if (!rect || rect.width <= 0 || rect.height <= 0) continue;

    var style = window.getComputedStyle ? window.getComputedStyle(el) : null;
    if (style && (style.visibility === 'hidden' || style.display === 'none' || style.opacity === '0')) {
      continue;
    }
    if (typeof el.offsetParent !== 'undefined' && el.offsetParent === null) {
      if (!style || style.position !== 'fixed') continue;
    }

    // Предпочитаем самый компактный (глубокий) видимый носитель текста.
    if (found === null || ownText.length < foundLength) {
      found = el;
      foundLength = ownText.length;
    }
  }

  if (!found) return null;
  try {
    found.setAttribute(attribute, marker);
  } catch (e) {
    return null;
  }
  return marker;
})
"""

_JS_CLEAR_MATCH = """
(function(attribute, marker) {
  var el = document.querySelector('[' + attribute + '="' + marker + '"]');
  if (el) {
    try { el.removeAttribute(attribute); } catch (e) {}
  }
  return true;
})
"""


async def async_find_by_text(
    page: Any,
    text: str,
    *,
    exact: bool = False,
    timeout: float = 5.0,
    attribute: str = MATCH_ATTRIBUTE,
) -> Any | None:
    """Ищет видимый элемент по тексту только в основном документе.

    Поиск выполняется за один вызов ``evaluate`` (1-2 мс), без обхода
    дочерних фреймов. Найденный узел временно маркируется атрибутом
    ``attribute``, чтобы получить нативный ``Element`` через ``page.select``.

    Args:
        page: Вкладка nodriver (Tab) с методами ``evaluate`` и ``select``.
        text: Искомый текст элемента.
        exact: Если True, требуется точное совпадение текста узла.
        timeout: Таймаут поиска и получения Element в секундах.
        attribute: Имя временного атрибута-маркера.

    Returns:
        Нативный элемент страницы или None, если видимый элемент не найден.
    """
    if page is None or not isinstance(text, str) or not text.strip():
        return None

    marker = f"bs-{uuid.uuid4().hex}"
    js = f"({_JS_FIND_BY_TEXT})({json.dumps(text)}, {json.dumps(exact)}, {json.dumps(attribute)}, {json.dumps(marker)})"

    try:
        found = await asyncio.wait_for(page.evaluate(js), timeout=timeout)
    except TimeoutError:
        logger.debug("Таймаут поиска элемента по тексту '%s'", text)
        return None
    except Exception as exc:
        logger.debug("Сбой поиска элемента по тексту '%s': %s", text, exc)
        return None

    if not found:
        return None

    element: Any | None = None
    selector = f'[{attribute}="{marker}"]'
    try:
        element = await asyncio.wait_for(page.select(selector, timeout=timeout), timeout=timeout)
    except TimeoutError:
        logger.debug("Таймаут получения Element по маркеру '%s'", marker)
    except Exception as exc:
        logger.debug("Не удалось получить Element по маркеру '%s': %s", marker, exc)
    finally:
        try:
            await page.evaluate(
                f"({_JS_CLEAR_MATCH})({json.dumps(attribute)}, {json.dumps(marker)})"
            )
        except Exception:
            pass

    return element


async def safe_find_element(
    page: Any,
    text: str,
    *,
    exact: bool = False,
    timeout: float = 5.0,
) -> Any | None:
    """Алиас :func:`async_find_by_text` для безопасного поиска элемента по тексту.

    Args:
        page: Вкладка nodriver (Tab).
        text: Искомый текст элемента.
        exact: Если True, требуется точное совпадение текста узла.
        timeout: Таймаут поиска в секундах.

    Returns:
        Нативный элемент страницы или None.
    """
    return await async_find_by_text(page, text, exact=exact, timeout=timeout)


def install_safe_find(tab: Any, *, search_iframes: bool = False) -> Any:
    """Устанавливает безопасную обёртку на ``tab.find``.

    Обёртка сначала ищет видимый текст в основном документе. Обход дочерних
    фреймов отключён по умолчанию (``search_iframes=False``), поэтому
    недоверенные iframe не опрашиваются. Если обход разрешён, исключения
    ``ProtocolException``/``ConnectionClosed`` у нативного ``find``
    перехватываются и не всплывают наружу.

    Args:
        tab: Вкладка nodriver (Tab).
        search_iframes: Разрешить fallback на нативный ``Tab.find`` с обходом фреймов.

    Returns:
        Тот же объект вкладки с установленной обёрткой.
    """
    if tab is None or getattr(tab, "_bs_safe_find_installed", False):
        return tab

    original_find = getattr(tab, "find", None)
    if not callable(original_find):
        return tab

    async def safe_find(
        text: str,
        best_match: bool = True,
        return_enclosing_element: bool = True,
        timeout: float = 10.0,
    ) -> Any | None:
        element = await async_find_by_text(tab, text, exact=False, timeout=timeout)
        if element is not None:
            return element
        if not search_iframes:
            return None

        try:
            return await asyncio.wait_for(
                original_find(
                    text,
                    best_match=best_match,
                    return_enclosing_element=return_enclosing_element,
                    timeout=timeout,
                ),
                timeout=timeout,
            )
        except TimeoutError:
            logger.debug("Таймаут нативного Tab.find для текста '%s'", text)
        except Exception as exc:
            # ProtocolException (-32601) и ConnectionClosed не должны всплывать.
            logger.debug("Нативный Tab.find завершился ошибкой для текста '%s': %s", text, exc)
        return None

    try:
        setattr(tab, "find", safe_find)
        setattr(tab, "_bs_safe_find_installed", True)
    except Exception as exc:
        logger.debug("Не удалось установить безопасный Tab.find: %s", exc)
    return tab


__all__ = [
    "MATCH_ATTRIBUTE",
    "async_find_by_text",
    "install_safe_find",
    "safe_find_element",
]
