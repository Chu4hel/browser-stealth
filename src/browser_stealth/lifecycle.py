"""Управление очисткой ресурсов и хуками завершения."""

from __future__ import annotations

import asyncio
import atexit
import inspect
import logging
import sys
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
                        loop.create_task(res)  # type: ignore[arg-type]
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
