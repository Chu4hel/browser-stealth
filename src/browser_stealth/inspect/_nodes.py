"""Нормализация узлов, собранных JavaScript-сборщиком.

Модуль отвечает только за приведение сырых данных к предсказуемой структуре:
отбрасывает лишние атрибуты, проверяет типы и не добавляет пустые поля, чтобы
снимок оставался компактным для передачи языковой модели.
"""

from __future__ import annotations

from typing import Any

_ALLOWED_ATTRIBUTES = frozenset(
    {
        "alt",
        "aria-label",
        "autocomplete",
        "data-qa",
        "data-test",
        "data-testid",
        "for",
        "href",
        "id",
        "maxlength",
        "name",
        "pattern",
        "placeholder",
        "role",
        "src",
        "title",
        "type",
        "value",
    }
)


def normalize_attrs(raw: Any) -> dict[str, str]:
    """Оставляет только известные строковые атрибуты элемента.

    Args:
        raw: Сырой словарь атрибутов из JavaScript.

    Returns:
        Отфильтрованный словарь; пустой, если валидных атрибутов нет.
    """
    if not isinstance(raw, dict):
        return {}
    attrs: dict[str, str] = {}
    for key, value in raw.items():
        name = str(key)
        if name not in _ALLOWED_ATTRIBUTES or value is None:
            continue
        text = str(value).strip()
        if text:
            attrs[name] = text
    return attrs


def normalize_box(raw: Any) -> list[int] | None:
    """Приводит координаты и размеры элемента к списку из четырёх чисел.

    Args:
        raw: Сырое значение ``box`` из JavaScript.

    Returns:
        Список ``[x, y, width, height]`` или None, если формат неверен.
    """
    if not isinstance(raw, (list, tuple)) or len(raw) != 4:
        return None
    try:
        return [round(float(value)) for value in raw]
    except (TypeError, ValueError):
        return None


def normalize_node(raw: Any) -> dict[str, Any] | None:
    """Преобразует сырой узел в компактное описание для агента.

    Args:
        raw: Один узел из ответа JavaScript-сборщика.

    Returns:
        Словарь с полями ``tag``, ``role``, ``visible``, ``enabled`` и
        необязательными ``name``, ``text``, ``selector``, ``attrs``, ``box``;
        None, если узел некорректен.
    """
    if not isinstance(raw, dict):
        return None
    tag = str(raw.get("tag") or "").strip().lower()
    if not tag:
        return None

    node: dict[str, Any] = {
        "tag": tag,
        "role": str(raw.get("role") or tag).strip().lower(),
    }

    name = str(raw.get("name") or "").strip()
    if name:
        node["name"] = name

    text = str(raw.get("text") or "").strip()
    if text:
        node["text"] = text

    selector = str(raw.get("selector") or "").strip()
    if selector:
        node["selector"] = selector

    attrs = normalize_attrs(raw.get("attrs"))
    if attrs:
        node["attrs"] = attrs

    box = normalize_box(raw.get("box"))
    if box is not None:
        node["box"] = box

    node["visible"] = bool(raw.get("visible", True))
    node["enabled"] = bool(raw.get("enabled", True))
    return node


def normalize_snapshot(payload: dict[str, Any]) -> dict[str, Any]:
    """Приводит ответ сборщика к публичному формату снимка страницы.

    Args:
        payload: Словарь, полученный от JavaScript-сборщика.

    Returns:
        Словарь с ключами ``url``, ``title``, ``viewport``, ``nodes``,
        ``total`` и ``truncated``.
    """
    raw_nodes = payload.get("nodes")
    nodes: list[dict[str, Any]] = []
    if isinstance(raw_nodes, (list, tuple)):
        for raw in raw_nodes:
            node = normalize_node(raw)
            if node is not None:
                nodes.append(node)

    raw_viewport = payload.get("viewport")
    viewport: dict[str, int] = {}
    if isinstance(raw_viewport, dict):
        for key in ("width", "height", "scrollX", "scrollY"):
            value = raw_viewport.get(key)
            if isinstance(value, (int, float)):
                viewport[key] = int(value)

    total = payload.get("total")
    return {
        "url": str(payload.get("url") or ""),
        "title": str(payload.get("title") or ""),
        "viewport": viewport,
        "nodes": nodes,
        "total": int(total) if isinstance(total, (int, float)) else len(nodes),
        "truncated": bool(payload.get("truncated", False)),
    }


__all__ = [
    "normalize_attrs",
    "normalize_box",
    "normalize_node",
    "normalize_snapshot",
]
