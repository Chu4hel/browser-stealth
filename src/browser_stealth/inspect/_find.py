"""Поиск элементов по тексту, роли или CSS-селектору."""

from __future__ import annotations

from typing import Any

from browser_stealth.inspect._collect import collect
from browser_stealth.inspect._nodes import normalize_node

DEFAULT_LIMIT = 10
"""Максимальное число совпадений по умолчанию."""


def _matches(
    node: dict[str, Any],
    *,
    text: str | None,
    exact: bool,
    role: str | None,
) -> bool:
    """Проверяет, удовлетворяет ли узел текстовому и ролевому фильтру.

    Args:
        node: Нормализованный узел страницы.
        text: Искомый текст или None, если фильтр по тексту не задан.
        exact: Требовать ли полное совпадение текста.
        role: Требуемая роль элемента или None.

    Returns:
        True, если узел подходит под все заданные фильтры.
    """
    if role is not None and str(node.get("role", "")).casefold() != role.casefold():
        return False
    if text is None:
        return True

    needle = " ".join(text.split()).casefold()
    if not needle:
        return True
    for key in ("name", "text"):
        value = str(node.get(key) or "").strip()
        if not value:
            continue
        haystack = " ".join(value.split()).casefold()
        if exact and haystack == needle:
            return True
        if not exact and needle in haystack:
            return True
    return False


async def find(
    tab: Any,
    *,
    text: str | None = None,
    role: str | None = None,
    selector: str | None = None,
    exact: bool = False,
    limit: int = DEFAULT_LIMIT,
    include_hidden: bool = False,
    max_nodes: int = 200,
    timeout: float = 10.0,
) -> list[dict[str, Any]]:
    """Ищет элементы страницы и возвращает их описания с CSS-селекторами.

    Поиск выполняется в основном документе. Найденные описания содержат
    ``selector``, который можно передать в :func:`browser_stealth.humanize.async_click`
    или ``tab.select``, а также ``box`` с координатами для собственных действий.

    Args:
        tab: Вкладка или страница с корутинным методом ``evaluate``.
        text: Подстрока имени или текста элемента; None — без фильтра.
        role: Роль элемента (``button``, ``link``, ``textbox`` и т.п.).
        selector: CSS-селектор, ограничивающий область поиска.
        exact: Требовать ли полное совпадение текста вместо подстроки.
        limit: Максимальное число совпадений.
        include_hidden: Включать ли невидимые элементы.
        max_nodes: Максимальное число просматриваемых узлов.
        timeout: Таймаут чтения DOM в секундах.

    Returns:
        Список описаний подходящих элементов (может быть пустым).

    Raises:
        InspectionError: Если вкладка недоступна или чтение DOM завершилось ошибкой.
        ValueError: Если не задан ни один критерий поиска или ``limit`` отрицателен.

    Example:
        >>> from browser_stealth import inspect
        >>> from browser_stealth.humanize import async_click
        >>> buttons = await inspect.find(tab, role="button", text="Войти")
        >>> await async_click(tab, selector=buttons[0]["selector"])
    """
    if text is None and role is None and selector is None:
        raise ValueError("Укажите хотя бы один критерий поиска: text, role или selector.")
    if limit < 0:
        raise ValueError("Параметр limit не может быть отрицательным.")
    if limit == 0:
        return []

    payload = await collect(
        tab,
        selector=selector,
        include_hidden=include_hidden,
        max_nodes=max_nodes,
        timeout=timeout,
    )

    matches: list[dict[str, Any]] = []
    raw_nodes = payload.get("nodes")
    if isinstance(raw_nodes, (list, tuple)):
        for raw in raw_nodes:
            node = normalize_node(raw)
            if node is None or not _matches(node, text=text, exact=exact, role=role):
                continue
            matches.append(node)
            if len(matches) >= limit:
                break
    return matches


__all__ = ["DEFAULT_LIMIT", "find"]
