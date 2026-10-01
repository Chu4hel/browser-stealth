"""Управление очисткой ресурсов и хуками завершения."""

from __future__ import annotations

import asyncio
import atexit
import inspect
import logging
from collections.abc import Awaitable, Callable
from typing import Any

logger = logging.getLogger("browser_stealth.lifecycle")

CleanupCallback = Callable[[], Any] | Callable[[], Awaitable[Any]]

_callbacks: list[CleanupCallback] = []
_atexit_registered = False


def _run_cleanups() -> None:
    """Выполняет все зарегистрированные функции очистки в порядке LIFO."""
    while _callbacks:
        cb = _callbacks.pop()
        try:
            if inspect.iscoroutinefunction(cb):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    loop.create_task(cb())
                else:
                    asyncio.run(cb())
            else:
                res = cb()
                if inspect.isawaitable(res):
                    try:
                        loop = asyncio.get_running_loop()
                    except RuntimeError:
                        loop = None
                    if loop and loop.is_running():
                        loop.create_task(res)
                    else:
                        asyncio.run(res)
        except Exception as exc:
            logger.debug("Ошибка при выполнении cleanup функции %s: %s", cb, exc)


def register_cleanup(func: CleanupCallback) -> CleanupCallback:
    """Регистрирует функцию для вызова при завершении процесса."""
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(_run_cleanups)
        _atexit_registered = True

    if func not in _callbacks:
        _callbacks.append(func)
    return func


def unregister_cleanup(func: CleanupCallback) -> bool:
    """Удаляет функцию из списка очистки."""
    if func in _callbacks:
        _callbacks.remove(func)
        return True
    return False
