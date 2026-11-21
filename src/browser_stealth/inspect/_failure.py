"""Сбор диагностического контекста страницы при сбое."""

from __future__ import annotations

import asyncio
import json
from typing import Any

from browser_stealth.inspect._collect import coerce_payload
from browser_stealth.logging import get_logger

logger = get_logger(__name__)

_JS_FAILURE_CONTEXT = r"""
(() => {
  const norm = (value) => String(value == null ? '' : value)
    .replace(/\s+/g, ' ')
    .trim();
  const textOf = (el) => (el && el.innerText ? norm(el.innerText) : '');
  const bodyText = textOf(document.body);
  const modals = Array.from(
    document.querySelectorAll(
      '[role="dialog"], [data-qa*="modal"], [class*="Modal"], [class*="modal"]'
    )
  )
    .map(textOf)
    .filter(Boolean)
    .slice(0, 3)
    .map((text) => text.slice(0, 180));
  return JSON.stringify({
    page_url: window.location.href || '',
    page_title: document.title || '',
    h1_text: textOf(document.querySelector('h1')).slice(0, 200),
    has_login_form: Boolean(
      document.querySelector(
        '[data-qa*="login"], [data-testid*="login"], form[action*="login"], input[type="password"]'
      )
    ),
    has_captcha: Boolean(
      document.querySelector(
        '[data-qa*="captcha"], [class*="captcha"], iframe[src*="captcha"], iframe[src*="smartcaptcha"]'
      ) || /подтвердите, что вы не робот|проверка безопасности|captcha/i.test(bodyText)
    ),
    has_archive_marker: Boolean(
      document.querySelector(
        '[data-qa*="archive"], [class*="archive"], [class*="vacancy-title_archive"]'
      ) || /вакансия в архиве|архивная вакансия/i.test(bodyText)
    ),
    visible_modals: modals,
    body_snippet: bodyText.slice(0, 400)
  });
})()
"""


def _page_url(tab: Any) -> str:
    """Извлекает URL из атрибутов вкладки без выполнения JavaScript."""
    for value in (
        getattr(tab, "url", None),
        getattr(getattr(tab, "target", None), "url", None),
    ):
        if isinstance(value, str) and value:
            return value
    return ""


async def collect_page_failure_context(tab: Any, *, timeout: float = 2.0) -> dict[str, Any]:
    """Собирает URL, заголовок, заголовок h1, модалки и маркеры блокировок.

    Функция предназначена для вызова из ``except``-блока: она не выбрасывает
    ошибки браузера, а возвращает максимально полный снимок состояния страницы.
    В результат входят признаки формы логина, капчи и архива вакансии, а также
    короткий текстовый сниппет и тексты видимых модальных окон.

    Args:
        tab: Вкладка nodriver или совместимый объект с ``evaluate``.
        timeout: Таймаут чтения DOM в секундах.

    Returns:
        Словарь с диагностическим контекстом. При недоступной вкладке содержит
        только ``page_url`` (если его можно прочитать) и пустые значения.

    Example:
        >>> try:
        ...     await action()
        ... except Exception:
        ...     context = await inspect.collect_page_failure_context(tab)
    """
    result: dict[str, Any] = {
        "page_url": _page_url(tab),
        "page_title": "",
        "h1_text": "",
        "has_login_form": False,
        "has_captcha": False,
        "has_archive_marker": False,
        "visible_modals": [],
        "body_snippet": "",
    }
    evaluate = getattr(tab, "evaluate", None)
    if not callable(evaluate):
        return result

    try:
        raw = await asyncio.wait_for(evaluate(_JS_FAILURE_CONTEXT), timeout=timeout)
        payload = coerce_payload(raw)
        if payload is None and isinstance(raw, str):
            payload = json.loads(raw)
        if not isinstance(payload, dict):
            return result
    except TimeoutError:
        logger.debug("Таймаут сбора контекста страницы")
        return result
    except Exception as exc:
        logger.debug("Не удалось собрать контекст страницы: %s", exc)
        return result

    for key in ("page_url", "page_title", "h1_text", "body_snippet"):
        value = payload.get(key)
        if isinstance(value, str) and value:
            result[key] = value
    for key in ("has_login_form", "has_captcha", "has_archive_marker"):
        result[key] = bool(payload.get(key, False))
    modals = payload.get("visible_modals")
    if isinstance(modals, (list, tuple)):
        result["visible_modals"] = [str(item)[:180] for item in modals[:3] if str(item).strip()]
    if not result["page_url"]:
        result["page_url"] = _page_url(tab)
    return result


__all__ = ["collect_page_failure_context"]
