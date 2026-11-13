"""Семантический снимок страницы для ИИ-агентов."""

from __future__ import annotations

from typing import Any

from browser_stealth.inspect._collect import collect
from browser_stealth.inspect._nodes import normalize_snapshot

DEFAULT_MAX_NODES = 200
"""Максимальное число узлов в снимке по умолчанию."""


async def snapshot(
    tab: Any,
    *,
    max_nodes: int = DEFAULT_MAX_NODES,
    include_hidden: bool = False,
    text_limit: int = 120,
    timeout: float = 10.0,
) -> dict[str, Any]:
    """Возвращает компактное описание страницы: URL, заголовок и элементы.

    Снимок содержит интерактивные элементы (ссылки, кнопки, поля, select,
    элементы с ``role``/``onclick``), заголовки, label и iframe основного
    документа. Для каждого узла отдаются роль, доступное имя, CSS-селектор,
    координаты, видимость и доступность. Дочерние фреймы не обходятся — они
    видны в снимке как узлы ``iframe`` с ``src``.

    Args:
        tab: Вкладка или страница с корутинным методом ``evaluate``.
        max_nodes: Максимальное число узлов в ответе.
        include_hidden: Включать ли невидимые элементы.
        text_limit: Максимальная длина текста узла в символах.
        timeout: Таймаут чтения DOM в секундах.

    Returns:
        Словарь с ключами ``url``, ``title``, ``viewport`` (``width``,
        ``height``, ``scrollX``, ``scrollY``), ``nodes`` (список описаний),
        ``total`` и ``truncated``.

    Raises:
        InspectionError: Если вкладка недоступна или чтение DOM завершилось ошибкой.

    Example:
        >>> from browser_stealth import inspect
        >>> page = await inspect.snapshot(tab, max_nodes=50)
        >>> [node["name"] for node in page["nodes"] if node["role"] == "button"]
        ['Войти', 'Зарегистрироваться']
    """
    payload = await collect(
        tab,
        include_hidden=include_hidden,
        max_nodes=max_nodes,
        text_limit=text_limit,
        timeout=timeout,
    )
    return normalize_snapshot(payload)


__all__ = ["DEFAULT_MAX_NODES", "snapshot"]
