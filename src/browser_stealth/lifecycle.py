"""Управление очисткой ресурсов и хуками завершения."""

from __future__ import annotations

import asyncio
import atexit
import inspect
import sys
from collections.abc import Awaitable, Callable
from typing import Any

from browser_stealth.logging import get_logger as setup_logger

logger = setup_logger(__name__)

CleanupCallback = Callable[[], Any] | Callable[[], Awaitable[Any]]

_callbacks: list[CleanupCallback] = []
_atexit_registered = False


async def _await(awaitable: Awaitable[Any]) -> Any:
    """Оборачивает произвольный awaitable в корутину для asyncio.run и create_task.

    Args:
        awaitable: Любой awaitable объект.

    Returns:
        Результат выполнения awaitable.
    """
    return await awaitable


def _run_cleanups() -> None:
    """Выполняет все зарегистрированные функции очистки в порядке LIFO."""
    while _callbacks:
        cb = _callbacks.pop()
        try:
            res = cb()
            if inspect.isawaitable(res):
                try:
                    loop = asyncio.get_running_loop()
                except RuntimeError:
                    loop = None
                if loop and loop.is_running():
                    loop.create_task(_await(res))
                else:
                    asyncio.run(_await(res))
        except Exception as exc:
            logger.debug("Ошибка при выполнении cleanup функции %s: %s", cb, exc)


def register_cleanup(func: CleanupCallback) -> CleanupCallback:
    """Регистрирует функцию для вызова при завершении процесса.

    Args:
        func: Синхронная или асинхронная функция очистки.

    Returns:
        Переданная функция, что позволяет использовать декоратор.
    """
    global _atexit_registered
    if not _atexit_registered:
        atexit.register(_run_cleanups)
        _atexit_registered = True

    if func not in _callbacks:
        _callbacks.append(func)
    return func


def unregister_cleanup(func: CleanupCallback) -> bool:
    """Удаляет функцию из списка очистки.

    Args:
        func: Ранее зарегистрированная функция очистки.

    Returns:
        True, если функция была удалена, иначе False.
    """
    if func in _callbacks:
        _callbacks.remove(func)
        return True
    return False


def patch_windows_asyncio_transport_cleanup() -> None:
    """Устраняет баг Windows CPython при закрытии пайпов сабпроцессов в ProactorEventLoop.

    Предотвращает 'ValueError: I/O operation on closed pipe' при сборке мусора GC в __del__.
    """
    if sys.platform != "win32":
        return

    try:
        from asyncio.base_subprocess import BaseSubprocessTransport
        from asyncio.proactor_events import _ProactorBasePipeTransport

        for cls in (_ProactorBasePipeTransport, BaseSubprocessTransport):
            orig_del = getattr(cls, "__del__", None)
            if orig_del is not None and not getattr(orig_del, "_is_patched", False):

                def _safe_del(self: object, _orig: object = orig_del) -> None:
                    try:
                        if callable(_orig):
                            _orig(self)
                    except (ValueError, RuntimeError, OSError):
                        pass

                setattr(_safe_del, "_is_patched", True)
                setattr(cls, "__del__", _safe_del)
    except Exception:
        pass


patch_windows_asyncio_transport_cleanup()
