"""Разбор значений CDP evaluate и извлечение словарей из ответов nodriver."""

from __future__ import annotations

import json

from browser_stealth.logging import get_logger

logger = get_logger(__name__)


def unpack_cdp_value(v: object) -> object:
    """Рекурсивно извлекает примитивные значения из структур CDP.

    Args:
        v: Значение CDP: dict, list, пара key/value или примитив.

    Returns:
        Развернутое значение: dict, list или примитив без оберток CDP.
    """
    if isinstance(v, dict):
        if "value" in v:
            return unpack_cdp_value(v["value"])
        return {str(k): unpack_cdp_value(val) for k, val in v.items()}
    if isinstance(v, list):
        if v and all(
            isinstance(i, (list, tuple)) and len(i) == 2 and isinstance(i[0], str) for i in v
        ):
            return safe_extract_dict(v)
        return [unpack_cdp_value(i) for i in v]
    return v


def safe_extract_dict(val: object) -> dict[str, object]:
    """Безопасно извлекает словарь из результата evaluate (строка JSON, список пар или dict).

    Args:
        val: Сырой результат вызова tab.evaluate.

    Returns:
        Распакованный словарь с данными.
    """
    if isinstance(val, dict):
        return val
    if isinstance(val, str):
        try:
            parsed = json.loads(val)
            if isinstance(parsed, dict):
                return parsed
        except Exception as exc:
            logger.debug(
                "Ошибка десериализации JSON из CDP evaluate: %s (val[:100]=%r)",
                exc,
                val[:100] if isinstance(val, str) else val,
            )
            return {}
    if isinstance(val, list):
        res: dict[str, object] = {}
        for item in val:
            if isinstance(item, (list, tuple)) and len(item) == 2:
                k, v = item
                if isinstance(k, str):
                    res[k] = unpack_cdp_value(v)
            elif isinstance(item, dict) and "name" in item and "value" in item:
                res[str(item["name"])] = unpack_cdp_value(item["value"])
        return res
    return {}


__all__ = ["safe_extract_dict", "unpack_cdp_value"]
