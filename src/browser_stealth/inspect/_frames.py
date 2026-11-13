"""Дерево фреймов страницы для планирования обхода."""

from __future__ import annotations

import asyncio
from typing import Any

from browser_stealth.exceptions import InspectionError

_FRAME_FIELDS = ("id_", "parent_id", "url", "name", "security_origin")


def _read(obj: Any, name: str) -> Any:
    """Читает поле из объекта или словаря CDP.

    Args:
        obj: Объект CDP, словарь или None.
        name: Имя поля.

    Returns:
        Значение поля или None, если его нет.
    """
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _flatten(tree: Any, depth: int, result: list[dict[str, Any]]) -> None:
    """Рекурсивно обходит FrameTree и добавляет фреймы в список.

    Args:
        tree: Узел дерева фреймов (CDP FrameTree, словарь или None).
        depth: Текущая глубина вложенности.
        result: Накопительный список описаний фреймов.
    """
    if tree is None:
        return

    frame = _read(tree, "frame")
    if frame is not None:
        entry: dict[str, Any] = {"depth": depth}
        for field in _FRAME_FIELDS:
            value = _read(frame, field)
            if value is not None:
                key = "id" if field == "id_" else field
                entry[key] = str(value)
        result.append(entry)

    children = _read(tree, "child_frames")
    if children is None:
        children = _read(tree, "childFrames")
    if isinstance(children, (list, tuple)):
        for child in children:
            _flatten(child, depth + 1, result)


async def frames(tab: Any, *, timeout: float = 10.0) -> list[dict[str, Any]]:
    """Возвращает плоский список фреймов страницы с глубиной вложенности.

    Каждый элемент содержит ``id``, ``parent_id`` (кроме главного фрейма),
    ``url``, ``name``, ``security_origin`` и ``depth``. Функция не выполняет
    действий во фреймах: она нужна, чтобы агент увидел, что часть страницы
    находится за пределами основного документа (например, оплата или виджет
    входа), и мог принять решение об отдельном подключении.

    Args:
        tab: Вкладка nodriver с методом ``get_frame_tree``.
        timeout: Таймаут получения дерева фреймов в секундах.

    Returns:
        Список описаний фреймов в порядке обхода в глубину; главный фрейм первый.

    Raises:
        InspectionError: Если вкладка не поддерживает дерево фреймов или
            CDP-вызов завершился ошибкой.

    Example:
        >>> from browser_stealth import inspect
        >>> tree = await inspect.frames(tab)
        >>> [f["url"] for f in tree if f["depth"] > 0]
        ['https://widget.example.com/login']
    """
    get_frame_tree = getattr(tab, "get_frame_tree", None)
    if not callable(get_frame_tree):
        raise InspectionError("Вкладка не поддерживает get_frame_tree.")

    try:
        tree = get_frame_tree()
        if asyncio.iscoroutine(tree):
            tree = await asyncio.wait_for(tree, timeout=timeout)
    except TimeoutError as exc:
        raise InspectionError(f"Таймаут получения дерева фреймов за {timeout} с.") from exc
    except Exception as exc:
        raise InspectionError(f"Не удалось получить дерево фреймов: {exc}") from exc

    result: list[dict[str, Any]] = []
    _flatten(tree, 0, result)
    return result


__all__ = ["frames"]
