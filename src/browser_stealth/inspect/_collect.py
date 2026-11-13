"""Сбор узлов страницы одним вызовом JavaScript.

Модуль формирует компактное описание интерактивных и структурных элементов
основного документа. Обход дочерних фреймов намеренно не выполняется: как и в
:mod:`browser_stealth.humanize.safe_find`, кросс-доменные iframe не опрашиваются,
поэтому CDP-ошибка ``'DOM.getDocument' wasn't found`` не возникает. Сами iframe
попадают в снимок отдельными узлами с ``src``, чтобы агент знал об их наличии.
"""

from __future__ import annotations

import asyncio
import json
from typing import Any

from browser_stealth.exceptions import InspectionError

_JS_COLLECT = r"""
(function(cfg) {
  var options = cfg || {};
  var includeHidden = !!options.includeHidden;
  var maxNodes = options.maxNodes || 200;
  var textLimit = options.textLimit || 120;
  var selector = options.selector || [
    'a[href]', 'button', 'input', 'select', 'textarea', 'summary', 'label',
    '[role]', '[onclick]', '[contenteditable="true"]', 'iframe[src]',
    'h1', 'h2', 'h3', 'h4', 'h5', 'h6'
  ].join(',');

  var attributeNames = [
    'id', 'name', 'type', 'href', 'src', 'placeholder', 'alt', 'title',
    'aria-label', 'role', 'for', 'value', 'autocomplete', 'maxlength',
    'pattern', 'data-testid', 'data-test', 'data-qa'
  ];

  function norm(value) {
    return String(value == null ? '' : value).replace(/\s+/g, ' ').trim();
  }

  function cut(value) {
    var text = norm(value);
    return text.length > textLimit ? text.slice(0, textLimit) + '…' : text;
  }

  function readAttrs(el) {
    var attrs = {};
    for (var i = 0; i < attributeNames.length; i++) {
      var name = attributeNames[i];
      var value = el.getAttribute(name);
      if (value !== null && value !== '') attrs[name] = String(value);
    }
    return attrs;
  }

  function isVisible(el, rect, style) {
    if (!rect || rect.width <= 0 || rect.height <= 0) return false;
    if (!style) return true;
    if (style.visibility === 'hidden' || style.display === 'none' || style.opacity === '0') {
      return false;
    }
    if (el.offsetParent === null && style.position !== 'fixed' && style.position !== 'sticky') {
      return false;
    }
    return true;
  }

  function safeId(id) {
    return /^[A-Za-z][A-Za-z0-9_-]*$/.test(id) ? '#' + id : '';
  }

  function cssPath(el) {
    var byId = el.id ? safeId(el.id) : '';
    if (byId) return byId;
    var parts = [];
    var node = el;
    while (node && node.nodeType === 1 && node.tagName) {
      var tag = node.tagName.toLowerCase();
      if (tag === 'body' || tag === 'html') break;
      var parent = node.parentElement;
      var part = tag;
      var ownId = node.id ? safeId(node.id) : '';
      if (ownId) {
        part = ownId;
      } else if (parent && parent.children) {
        part += ':nth-child(' + (Array.prototype.indexOf.call(parent.children, node) + 1) + ')';
      }
      parts.unshift(part);
      if (ownId || parts.length >= 4) break;
      node = parent;
    }
    return parts.join(' > ');
  }

  function implicitRole(el, tag, type) {
    var explicit = el.getAttribute('role');
    if (explicit) return explicit;
    if (tag === 'a' && el.hasAttribute('href')) return 'link';
    if (tag === 'button' || tag === 'summary') return 'button';
    if (tag === 'select') return 'combobox';
    if (tag === 'textarea') return 'textbox';
    if (tag === 'iframe') return 'iframe';
    if (tag === 'label') return 'label';
    if (tag === 'h1' || tag === 'h2' || tag === 'h3' || tag === 'h4' || tag === 'h5' || tag === 'h6') {
      return 'heading';
    }
    if (tag === 'input') {
      if (type === 'checkbox') return 'checkbox';
      if (type === 'radio') return 'radio';
      if (type === 'hidden') return 'hidden';
      if (type === 'submit' || type === 'button' || type === 'reset' || type === 'image') {
        return 'button';
      }
      if (type === 'search') return 'searchbox';
      return 'textbox';
    }
    return tag;
  }

  function accessibleName(el, tag, type, text) {
    var aria = norm(el.getAttribute('aria-label'));
    if (aria) return aria;
    if (tag === 'img') return norm(el.getAttribute('alt'));
    if (tag === 'iframe') {
      return norm(el.getAttribute('title') || el.getAttribute('name') || el.getAttribute('src'));
    }
    if (tag === 'input' || tag === 'textarea') {
      var placeholder = norm(el.getAttribute('placeholder'));
      if (placeholder) return placeholder;
      if (tag === 'input' && (type === 'submit' || type === 'button' || type === 'reset')) {
        return norm(el.value || el.getAttribute('value'));
      }
      return '';
    }
    var title = norm(el.getAttribute('title'));
    if (title) return title;
    return text;
  }

  function nodeText(el, tag) {
    if (tag === 'input' || tag === 'textarea') return cut(el.value || '');
    if (tag === 'select') {
      var options = el.options;
      if (options && options.length && el.selectedIndex >= 0 && options[el.selectedIndex]) {
        return cut(options[el.selectedIndex].text);
      }
      return '';
    }
    return cut(el.textContent);
  }

  var result = {
    url: location.href,
    title: document.title || '',
    viewport: {
      width: window.innerWidth || 0,
      height: window.innerHeight || 0,
      scrollX: Math.round(window.scrollX || 0),
      scrollY: Math.round(window.scrollY || 0)
    },
    nodes: [],
    total: 0,
    truncated: false
  };

  if (!document.body || !document.body.querySelectorAll) return result;

  var candidates;
  try {
    candidates = document.body.querySelectorAll(selector);
  } catch (e) {
    return result;
  }

  for (var i = 0; i < candidates.length; i++) {
    var el = candidates[i];
    var tag = String(el.tagName || '').toLowerCase();
    if (!tag) continue;

    var type = String(el.getAttribute('type') || '').toLowerCase();
    if (type === 'hidden') continue;

    var rect = el.getBoundingClientRect ? el.getBoundingClientRect() : null;
    var style = window.getComputedStyle ? window.getComputedStyle(el) : null;
    var visible = isVisible(el, rect, style);
    if (!visible && !includeHidden) continue;

    var text = nodeText(el, tag);
    var node = {
      tag: tag,
      role: implicitRole(el, tag, type),
      name: accessibleName(el, tag, type, text),
      text: text,
      selector: cssPath(el),
      attrs: readAttrs(el),
      box: [
        Math.round(rect ? rect.left : 0),
        Math.round(rect ? rect.top : 0),
        Math.round(rect ? rect.width : 0),
        Math.round(rect ? rect.height : 0)
      ],
      visible: visible,
      enabled: !el.disabled && el.getAttribute('aria-disabled') !== 'true'
    };

    result.total += 1;
    if (result.nodes.length >= maxNodes) {
      result.truncated = true;
      continue;
    }
    result.nodes.push(node);
  }

  return result;
})
"""


_CDP_TYPES = frozenset(
    {"array", "bigint", "boolean", "function", "number", "object", "string", "symbol", "undefined"}
)


def _unwrap_cdp(value: Any) -> Any:
    """Рекурсивно разворачивает CDP-обёртки ``{type, value}`` и списки пар.

    ``Tab.evaluate`` в nodriver возвращает ответ в виде списка пар
    ``[key, RemoteObject]``, где вложенные объекты и массивы тоже обёрнуты.
    Без разворачивания снимок содержит словари вместо строк и чисел.

    Args:
        value: Сырое значение из ответа evaluate.

    Returns:
        Значение с обычными dict/list/str/int/bool.
    """
    if isinstance(value, dict):
        if value.get("type") in _CDP_TYPES and "value" in value:
            return _unwrap_cdp(value["value"])
        return {str(key): _unwrap_cdp(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        if value and all(
            isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[0], str)
            for item in value
        ):
            return {item[0]: _unwrap_cdp(item[1]) for item in value}
        return [_unwrap_cdp(item) for item in value]
    return value


def coerce_payload(raw: Any) -> dict[str, Any] | None:
    """Приводит ответ ``evaluate`` к словарю снимка.

    nodriver может вернуть уже разобранный объект, JSON-строку или список
    пар ``[key, value]`` с CDP-обёртками вложенных значений.

    Args:
        raw: Сырой результат выполнения JavaScript.

    Returns:
        Словарь снимка или None, если привести значение не удалось.
    """
    raw = _unwrap_cdp(raw)
    if isinstance(raw, dict):
        return raw
    if isinstance(raw, str):
        try:
            parsed = json.loads(raw)
        except (TypeError, ValueError):
            return None
        return parsed if isinstance(parsed, dict) else None
    if isinstance(raw, (list, tuple)):
        result: dict[str, Any] = {}
        for item in raw:
            if isinstance(item, (list, tuple)) and len(item) == 2 and isinstance(item[0], str):
                result[item[0]] = item[1]
        return result or None
    return None


async def collect(
    tab: Any,
    *,
    selector: str | None = None,
    include_hidden: bool = False,
    max_nodes: int = 200,
    text_limit: int = 120,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Собирает компактное описание узлов основного документа.

    Args:
        tab: Вкладка или страница с корутинным методом ``evaluate``.
        selector: CSS-селектор, ограничивающий выборку; None — набор по умолчанию.
        include_hidden: Включать ли невидимые элементы (с ``visible=False``).
        max_nodes: Максимальное число узлов в ответе.
        text_limit: Максимальная длина текста узла в символах.
        timeout: Таймаут выполнения JavaScript в секундах.

    Returns:
        Словарь с ключами ``url``, ``title``, ``viewport``, ``nodes``,
        ``total`` и ``truncated``.

    Raises:
        InspectionError: Если вкладка недоступна, JavaScript завершился ошибкой
            или ответ имеет неожиданный формат.
    """
    evaluate = getattr(tab, "evaluate", None)
    if not callable(evaluate):
        raise InspectionError("Вкладка не поддерживает evaluate и не может быть проинспектирована.")

    options: dict[str, Any] = {
        "includeHidden": include_hidden,
        "maxNodes": max_nodes,
        "textLimit": text_limit,
    }
    if selector:
        options["selector"] = selector

    script = f"({_JS_COLLECT})({json.dumps(options, ensure_ascii=False)})"
    try:
        raw = await asyncio.wait_for(evaluate(script), timeout=timeout)
    except TimeoutError as exc:
        raise InspectionError(f"Таймаут чтения DOM за {timeout} с.") from exc
    except Exception as exc:
        raise InspectionError(f"Не удалось прочитать DOM страницы: {exc}") from exc

    payload = coerce_payload(raw)
    if payload is None:
        raise InspectionError("Браузер вернул пустой или некорректный ответ при чтении DOM.")
    return payload


__all__ = ["coerce_payload", "collect"]
