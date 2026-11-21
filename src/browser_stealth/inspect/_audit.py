"""Аудит надёжности CSS-селекторов на живой странице."""

from __future__ import annotations

import inspect
import time
from collections.abc import Mapping, Sequence
from typing import Any

from browser_stealth.inspect._cascade import _as_sequence, async_find_cascade
from browser_stealth.logging import get_logger

logger = get_logger(__name__)


def _normalize_selectors(
    selectors: Mapping[str, str | Sequence[str]] | str | Sequence[str],
) -> list[tuple[str, list[str]]]:
    """Приводит входной словарь/список к парам «имя — каскад селекторов»."""
    if isinstance(selectors, str):
        return [(selectors, [selectors])]
    if isinstance(selectors, Mapping):
        result: list[tuple[str, list[str]]] = []
        for name, value in selectors.items():
            cascade = _as_sequence(value)
            if cascade:
                result.append((str(name), cascade))
        return result
    return [(selector, [selector]) for selector in _as_sequence(selectors)]


async def audit_selectors(
    tab: Any,
    selectors: Mapping[str, str | Sequence[str]] | str | Sequence[str],
    *,
    timeout: float = 5.0,
    progress_callback: Any = None,
) -> dict[str, dict[str, Any]]:
    """Проверяет селекторы на странице и возвращает отчёт Selector Doctor.

    Для каждого имени выполняется один атомарный поиск по каскаду. Статус
    ``ok`` означает, что сработал первый (primary) селектор, ``fallback`` —
    что подошёл один из запасных, ``missing`` — что не найден ни один.

    Args:
        tab: Вкладка nodriver или совместимый объект с ``evaluate``/``select``.
        selectors: Словарь ``имя -> селектор или список селекторов`` либо
            последовательность CSS-селекторов.
        timeout: Таймаут поиска одного каскада в секундах.
        progress_callback: Необязательный sync/async колбэк
            ``(current, total, name)`` для UI.

    Returns:
        Словарь ``имя -> {status, primary, matched_by, latency_ms}``.

    Example:
        >>> report = await inspect.audit_selectors(
        ...     tab,
        ...     {"submit": ["[data-qa='submit']", "button[type='submit']"]},
        ... )
        >>> report["submit"]["status"]
        'ok'
    """
    normalized = _normalize_selectors(selectors)
    total = len(normalized)
    report: dict[str, dict[str, Any]] = {}
    for index, (name, cascade) in enumerate(normalized, start=1):
        if callable(progress_callback):
            try:
                callback_result = progress_callback(index, total, name)
                if inspect.isawaitable(callback_result):
                    await callback_result
            except Exception as exc:
                logger.debug("Ошибка progress_callback для %s: %s", name, exc)

        started = time.perf_counter()
        element, matched = await async_find_cascade(tab, cascade, timeout=timeout)
        latency_ms = round((time.perf_counter() - started) * 1000, 2)
        primary = cascade[0]
        if element is None or matched is None:
            status = "missing"
        elif matched == primary:
            status = "ok"
        else:
            status = "fallback"
        report[name] = {
            "status": status,
            "primary": primary,
            "matched_by": matched,
            "latency_ms": latency_ms,
        }
        logger.info(
            "Selector Doctor [%d/%d]: %s -> %s (%s, %.2f ms)",
            index,
            total,
            name,
            status.upper(),
            matched or "—",
            latency_ms,
        )
    return report


__all__ = ["audit_selectors"]
